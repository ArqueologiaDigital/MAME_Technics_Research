#!/usr/bin/env python3
"""kn5000_dsp_perframe.py -- the EXACT per-sample-frame execution trace of the
KN5000 effects DSP (IC311, NEC uPD6383GF-3BA).

Everything else in this series analyses the microcode as a static CORPUS: 2974
body words over 38 images, counted by vocabulary.  That is the wrong denominator
for "what has to be decoded before audio can flow".  The machine does not run a
corpus -- every sample frame it runs ONE ordered list of words, and that list is
short, fixed, and mostly NOT the body corpus.

This tool builds that list from measured data and reports it.

Control-flow model used (all of it established, each claim cited in the note
notes/dsp-perframe-execution.md):

    Fs edge -> PC := 0                              hardware restart, no software loop
       0..48   common header, unit-0 preamble       (uploaded, resident)
         49    400.1.0E.000  CALL unit 0            -> body at I-RAM 84, RETURNs to 50
      50..58   common header, unit-1 preamble
         59    400.1.0F.007  CALL unit 1            -> body at I-RAM 200, RETURNs to 60
      60..82   epilogue / output stage              (23 words, host-patched at 64 and 71)
         82    C00.A.47.407  wait for the next Fs

Inputs:
    <capture.txt>     a uC-IF capture from the MAME upd6383 device
                      (notes/data/kn5000_dsp1_upload_coldboot.txt, or a fresh one).
                      Supplies the RESIDENT scaffolding: header 0..59, epilogue
                      60..82, and the run-time patches at 64 / 71.
    <subprogram.rom>  kn5000_subprogram_v142.rom -- supplies the effect bodies
                      (byte-verified identical to the captured ones).

Usage:
    python3 tools/kn5000_dsp_perframe.py <capture.txt> <subprogram.rom>
    python3 tools/kn5000_dsp_perframe.py <capture.txt> <rom> --algo 0   # one trace
    python3 tools/kn5000_dsp_perframe.py <capture.txt> <rom> --md       # markdown tables

Findings are written up in notes/dsp-perframe-execution.md.
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kn5000_dsp_wordfields import parse, as_int                       # noqa: E402
from kn5000_dsp_extract import Rom, parse_stream, ALGO_TABLE, N_ALGOS  # noqa: E402

DSPTREE = os.path.expanduser("~/compartilhado/kn5000-roms-disasm/dsp/tools")
sys.path.insert(0, DSPTREE)
import dsp_disasm as D                                                # noqa: E402

HDR, HDR_N = 0, 60
EPI, EPI_N = 60, 23
U0, U1 = 84, 200
CALL0, CALL1 = 49, 59          # the two unit-tagged END words in the header
PATCH_SLOTS = (64, 71)


# --------------------------------------------------------------------------
def fields(w):
    return D.hi12(w), D.class4(w), D.addr8(w), D.lo12(w)


def fmt(w):
    return "%03X.%X.%02X.%03X" % fields(w)


def family(w):
    """(hi12, class4, lo12) -- addr8 is a pointer delta / unit tag / table
    selector (MEASURED), i.e. an OPERAND, so it is excluded from the opcode
    identity.  This is the same family key the worklist in
    notes/kn5000-dsp-core-draft.md ranks."""
    hi, cl, ad, lo = fields(w)
    return (hi, cl, lo)


def famstr(f):
    return "%03X.%X.**.%03X" % (f[0], f[1], f[2])


def is_term(w):
    return D.is_end(w) and D.class4(w) == 1 and D.addr8(w) in (0x0E, 0x0F)


MNEMONIC = {}


def mnemonic(w):
    hi, cl, ad, lo = fields(w)
    if hi == 0x000 and cl == 2 and ad == 0 and lo == 0x000:  return "nop"
    if D.is_rstcur(w):                                       return "rstcur"
    if hi == 0x801 and cl == 0 and lo == 0x821:              return "ldptr #$%02X" % ad
    if hi == 0x202 and cl == 0xA and lo == 0x1D5:            return "mac (p)+%d" % s8(ad)
    if hi == 0x202 and cl == 0xA and lo == 0x1D4:            return "mac.lb (p)+%d" % s8(ad)
    if hi == 0x212 and cl == 0xA and lo == 0x407:            return "mulst (p)+%d" % s8(ad)
    return None


def s8(v):
    return v - 256 if v & 0x80 else v


# --------------------------------------------------------------------------
def load_resident(cap):
    """header, epilogue and the final host patches, from the live capture."""
    blocks = parse(cap)
    hdr = epi = None
    patch = {}
    for _, a, ws in blocks:
        if a == HDR and len(ws) == HDR_N:
            hdr = [as_int(w) for w in ws]
        elif a == EPI and len(ws) == EPI_N:
            epi = [as_int(w) for w in ws]
        elif a in PATCH_SLOTS and len(ws) == 1:
            patch[a] = as_int(ws[0])           # last write wins = live state
    if hdr is None or epi is None:
        sys.exit("capture has no 60-word header / 23-word epilogue block")
    return hdr, epi, patch


def load_bodies(rompath):
    """{blob: (load_addr, [words], [algo ids])} over the whole ROM pool."""
    rom = Rom(rompath)
    out = {}
    for i in range(N_ALGOS):
        try:
            iram, _, _ = parse_stream(rom, rom.u32le(ALGO_TABLE + 4 * i))
        except Exception:
            continue
        for a, ws, _ in iram:
            if a not in (U0, U1):
                continue
            blob = bytes(b for w in ws for b in w)
            words = [int.from_bytes(blob[k:k + 5], "big") for k in range(0, len(blob), 5)]
            key = (a, blob)
            if key in out:
                out[key][2].append(i)
            else:
                out[key] = (a, words, [i])
    return out


def body_of(bodies, algo):
    for (a, _blob), (load, words, algos) in bodies.items():
        if algo in algos:
            return load, words, algos
    raise KeyError(algo)


# --------------------------------------------------------------------------
def frame_trace(hdr, epi, patch, u0_words, u1_words):
    """The ordered list of (iram_addr, word, region) executed in ONE frame."""
    resident_epi = list(epi)
    for a, w in patch.items():
        resident_epi[a - EPI] = w

    t = []
    t += [(i, hdr[i], "header/pre0") for i in range(0, CALL0 + 1)]
    t += [(U0 + i, w, "unit-0 body") for i, w in enumerate(u0_words)]
    t += [(i, hdr[i], "header/pre1") for i in range(CALL0 + 1, CALL1 + 1)]
    t += [(U1 + i, w, "unit-1 body") for i, w in enumerate(u1_words)]
    t += [(EPI + i, w, "epilogue") for i, w in enumerate(resident_epi)]
    return t


def stats(trace):
    words = [w for _, w, _ in trace]
    fams = [family(w) for w in words]
    return {
        "n": len(words),
        "distinct_words": len(set(words)),
        "distinct_families": len(set(fams)),
        "decoded_words": sum(1 for w in words if D.decoded(w)),
        "decoded_families": len(set(family(w) for w in words if D.decoded(w))),
        "classA": sum(1 for w in words if D.class4(w) == 0xA),
        "cursor": sum(1 for w in words if D.cursor_fetch(w)),
        "stores": sum(1 for w in words if (D.hi12(w) & D.HI_ST) and not (D.hi12(w) & D.HI_ESC)),
        "dram": sum(1 for w in words if D.hi12(w) == 0x880),
        "fams": collections.Counter(fams),
        "words": words,
    }


# --------------------------------------------------------------------------
def dump_trace(trace, md=False):
    """Address-ordered execution table.  The `cur' column is the RUNNING
    coefficient-cursor index if the cursor were NEVER reset across the whole
    frame -- see the note: whether the CALL resets it or switches bank (BNK-R)
    is an OPEN question this per-frame view is the first to pose."""
    k = 0
    if md:
        print("| # | I-RAM | word (36-bit) | fields | cur | decode / landmark | region |")
        print("|---:|---:|---|---|---:|---|---|")
    for n, (a, w, region) in enumerate(trace):
        m = mnemonic(w)
        ann = D.annotate(w)
        dec = m if m else ("?word" + ("  " + ann if ann else ""))
        cur = ""
        if D.is_rstcur(w):
            k = 0
        if D.coeff_consumer(w):
            cur = "%d" % k
            k += 1
        if md:
            print("| %d | %3d | `%010X` | `%s` | %s | %s | %s |"
                  % (n, a, w, fmt(w), cur, dec.replace("|", "\\|"), region))
        else:
            print("  %3d  %3d  %010X  %s %4s %s   [%s]" % (n, a, w, fmt(w), cur, dec, region))


def report(name, trace, md=False):
    s = stats(trace)
    reg = collections.Counter(r for _, _, r in trace)
    print()
    print("=" * 78)
    print("FRAME TRACE: %s" % name)
    print("=" * 78)
    print("  words executed per frame  : %d   (each EXACTLY ONCE -- straight-line, no loops)"
          % s["n"])
    for r in ("header/pre0", "unit-0 body", "header/pre1", "unit-1 body", "epilogue"):
        print("      %-12s %3d" % (r, reg[r]))
    print("  distinct 36-bit words     : %d" % s["distinct_words"])
    print("  distinct (hi12,class4,lo12) FAMILIES : %d" % s["distinct_families"])
    print("  words already decoded     : %d / %d  (%.1f %%)  in %d of the 6 known forms"
          % (s["decoded_words"], s["n"], 100.0 * s["decoded_words"] / s["n"],
             s["decoded_families"]))
    print("  class-A coefficient multiplies: %d ; cursor-fetch words: %d ; "
          "acc->mem stores: %d ; DRAM-bracket words: %d"
          % (s["classA"], s["cursor"], s["stores"], s["dram"]))
    perreg = collections.Counter()
    for a, w, r in trace:
        if D.class4(w) == 0xA:
            perreg[r] += 1
    print("  class-A per region: " + "  ".join("%s=%d" % (k, v) for k, v in perreg.items()))
    return s


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cap, rompath = sys.argv[1], sys.argv[2]
    md = "--md" in sys.argv
    only = None
    if "--algo" in sys.argv:
        only = int(sys.argv[sys.argv.index("--algo") + 1])

    hdr, epi, patch = load_resident(cap)
    bodies = load_bodies(rompath)

    u1_load, u1_words, u1_algos = body_of(bodies, 16)      # the ONLY unit-1 image
    assert u1_load == U1 and is_term(u1_words[-1])

    # smallest unit-0 body first
    plan = [(0, "NO OPERATION  (through / no-effect, 42 slots)"),
            (36, "COMPRESSOR"),
            (1, "CHORUS  (the cold-boot default)"),
            (39, "PARAMETRIC EQ")]
    if only is not None:
        plan = [(only, "algo %d" % only)]

    allstats = {}
    for algo, label in plan:
        u0_load, u0_words, u0_algos = body_of(bodies, algo)
        assert u0_load == U0 and is_term(u0_words[-1]), "algo %d has no unit-0 terminator" % algo
        tr = frame_trace(hdr, epi, patch, u0_words, u1_words)
        s = report("%s  +  ROOM REVERB (unit 1, algos %d..%d)"
                   % (label, min(u1_algos), max(u1_algos)), tr, md)
        allstats[algo] = (label, tr, s)
        if only is not None:
            print()
            dump_trace(tr, md)

    if "--sets" in sys.argv:
        for algo, (label, tr, s) in sorted(allstats.items(), key=lambda kv: kv[1][2]["n"]):
            print()
            print("-" * 78)
            print("DISTINCT FAMILY SET -- %s  (%d words/frame, %d families)"
                  % (label, s["n"], s["distinct_families"]))
            print("-" * 78)
            line = []
            for f, n in sorted(s["fams"].items(), key=lambda kv: (-kv[1], famstr(kv[0]))):
                mark = "*" if any(D.decoded(w) for _, w, _ in tr if family(w) == f) else " "
                line.append("%s%s x%d" % (mark, famstr(f), n))
            for i in range(0, len(line), 4):
                print("   " + "   ".join("%-22s" % x for x in line[i:i + 4]))
            print("   ('*' = one of the six decoded forms)")

    if only is not None:
        return

    # ---- the ALWAYS-EXECUTED core: scaffolding + reverb ----------------
    scaff = [(i, hdr[i], "header") for i in range(HDR_N)]
    resident_epi = list(epi)
    for a, w in patch.items():
        resident_epi[a - EPI] = w
    scaff += [(EPI + i, w, "epilogue") for i, w in enumerate(resident_epi)]
    print()
    print("=" * 78)
    print("THE ALWAYS-EXECUTED SCAFFOLDING (header 0..59 + epilogue 60..82)")
    print("  -- runs every frame for EVERY effect, and carries the audio I/O")
    print("=" * 78)
    ss = stats(scaff)
    print("  words: %d   distinct: %d   families: %d   decoded: %d"
          % (ss["n"], ss["distinct_words"], ss["distinct_families"], ss["decoded_words"]))

    rev = [(U1 + i, w, "unit-1 body") for i, w in enumerate(u1_words)]
    rs = stats(rev)
    print("  reverb body alone: words %d  distinct %d  families %d  decoded %d"
          % (rs["n"], rs["distinct_words"], rs["distinct_families"], rs["decoded_words"]))

    core = scaff + rev
    cs = stats(core)
    print("  scaffolding + reverb (the floor, present in EVERY frame): "
          "words %d  distinct %d  families %d  decoded %d"
          % (cs["n"], cs["distinct_words"], cs["distinct_families"], cs["decoded_words"]))

    # ---- how much of the scaffolding is INVISIBLE to the body corpus ----
    corpus = collections.Counter()
    for (a, _blob), (load, words, algos) in bodies.items():
        for w in words:
            corpus[family(w)] += 1
    sfams = set(family(w) for _, w, _ in scaff)
    only_scaff = sorted(f for f in sfams if f not in corpus)
    print("  scaffolding families that NEVER occur in any of the 38 effect bodies: "
          "%d of %d" % (len(only_scaff), len(sfams)))
    print("     " + "  ".join(famstr(f) for f in only_scaff))

    # ---- blocking families, ranked by per-frame occurrence -------------
    print()
    print("=" * 78)
    print("UNDECODED FAMILIES ON THE CRITICAL PATH OF THE *MINIMUM* AUDIO FRAME")
    print("  (NO OPERATION + reverb; 'execs' = executions in ONE sample frame)")
    print("=" * 78)
    label0, tr0, s0 = allstats[0]
    where = collections.defaultdict(set)
    for a, w, r in tr0:
        where[family(w)].add(r.split("/")[0])
    undec = sorted(((f, n) for f, n in s0["fams"].items()
                    if not any(D.decoded(w) for _, w, _ in tr0 if family(w) == f)),
                   key=lambda kv: (-kv[1], famstr(kv[0])))
    print("  %-18s %6s  %s" % ("family", "execs", "regions"))
    for f, n in undec:
        print("  %-18s %6d  %s" % (famstr(f), n, ",".join(sorted(where[f]))))
    print("  -> %d undecoded families, %d executions, in the minimum frame"
          % (len(undec), sum(n for _, n in undec)))

    # ---- corpus-wide frame-size extremes --------------------------------
    print()
    print("=" * 78)
    print("FRAME SIZE OVER THE WHOLE CORPUS")
    print("=" * 78)
    u0lens = sorted(set(len(w) for (a, _b), (ld, w, al) in bodies.items() if ld == U0))
    u1lens = sorted(set(len(w) for (a, _b), (ld, w, al) in bodies.items() if ld == U1))
    print("  unit-0 body lengths : %s" % u0lens)
    print("  unit-1 body lengths : %s" % u1lens)
    lo = HDR_N + min(u0lens) + max(u1lens) + EPI_N
    hi = HDR_N + max(u0lens) + max(u1lens) + EPI_N
    print("  frame slots: min %d  max %d   (60 header + body0 + 133 reverb + 23 epilogue)"
          % (lo, hi))
    print("  25 MHz / 44 100 Hz = 567 cycles per frame -> %.2f..%.2f cycles per word"
          % (567.0 / hi, 567.0 / lo))


if __name__ == "__main__":
    main()
