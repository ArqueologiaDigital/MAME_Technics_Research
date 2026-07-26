#!/usr/bin/env python3
"""kn5000_dsp_critpath.py -- DECODE COVERAGE ON THE CRITICAL PATH (uPD6383GF).

Every statistic in notes/dsp-critical-path-coverage.md is produced here.

The point of this instrument: every previous coverage number in this series was
computed over the 38 EFFECT BODY images (2974 words).  Those 2974 words EXCLUDE
the 83 scaffolding words at I-RAM 0..82 by construction -- and the scaffolding is
the only code that touches the audio boundary.  So this tool assembles the words
that ACTUALLY EXECUTE in one sample frame

    header    I-RAM  0..59   60 words   (live cold-boot capture)
    unit-0 body      84..               (ROM corpus; live cold boot = algo 1)
    epilogue  I-RAM 60..82   23 words   (live capture) -- runs AFTER unit 1
    unit-1 body     200..               (ROM corpus; algo 16, the only unit-1 image)

and classifies each of them against the six decoded forms, so that the coverage
figure is computed over what runs rather than over what was easy to collect.

Ranking is by AUDIO-BLOCKING, not frequency: a word that carries the sample in or
out executes ONCE per frame -- the lowest possible corpus frequency -- which is
exactly why the frequency-ranked worklist never reaches it.

Usage:
    python3 tools/kn5000_dsp_critpath.py \
        [notes/data/kn5000_dsp1_upload_coldboot.txt] \
        [~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom]
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# the disassembler mirror lives in the KN5000 disassembly repo and is the living
# ISA reference; import it rather than re-implementing the six forms here.
for cand in (os.path.expanduser("~/compartilhado/kn5000-roms-disasm/dsp/tools"),
             os.path.join(HERE, "..", "..", "kn5000-roms-disasm", "dsp", "tools")):
    if os.path.isdir(cand):
        sys.path.insert(0, cand)
        break

from kn5000_dsp_wordfields import parse, as_int                    # noqa: E402
from kn5000_dsp_extract import (Rom, parse_stream, ALGO_TABLE,     # noqa: E402
                                N_ALGOS)
import dsp_disasm as D                                             # noqa: E402

DEF_CAP = os.path.join(HERE, "..", "notes", "data",
                       "kn5000_dsp1_upload_coldboot.txt")
DEF_ROM = os.path.expanduser("~/compartilhado/kn5000-roms-disasm/original_ROMs/"
                             "kn5000_subprogram_v142.rom")
DEF_TSV = os.path.expanduser("~/compartilhado/kn5000-roms-disasm/dsp/programs.tsv")


def wstr(w):
    return "%03X.%X.%02X.%03X" % D.fields(w)


def fam(w):
    return (D.hi12(w), D.class4(w), D.lo12(w))


def fstr(f):
    return "%03X.%X.**.%03X" % f


def form_of(w):
    """Which of the six decoded forms, or None."""
    hi, cl, ad, lo = D.fields(w)
    if not D.decoded(w):
        return None
    if hi == 0x000:
        return "nop"
    if hi == 0x801 and lo == 0x821:
        return "ldptr"
    if hi == 0x801:
        return "rstcur"
    if hi == 0x202 and lo == 0x1d5:
        return "mac"
    if hi == 0x202:
        return "mac.lb"
    return "mulst"


def is_escape(w):
    return bool(D.hi12(w) & 0x800)


def bit4_store(w):
    """hi12 bit 4 = write accumulator to mem[ptr] (MEASURED), only outside the
    format escape."""
    return bool(D.hi12(w) & 0x010) and not is_escape(w)


def load_scaffolding(path):
    blocks = parse(path)
    H = [as_int(w) for w in [ws for _, a, ws in blocks if a == 0][0]]
    S = [as_int(w) for w in [ws for _, a, ws in blocks if a == 60][0]]
    live84 = [ws for _, a, ws in blocks if a == 84]
    live200 = [ws for _, a, ws in blocks if a == 200]
    patch = [(a, as_int(ws[0])) for _, a, ws in blocks if a in (64, 71)]
    return (H, S,
            [as_int(w) for w in live84[0]] if live84 else None,
            [as_int(w) for w in live200[0]] if live200 else None,
            patch)


def load_bodies(rompath):
    rom = Rom(rompath)
    seen, imgs = set(), []
    for i in range(N_ALGOS):
        try:
            iram, _, _ = parse_stream(rom, rom.u32le(ALGO_TABLE + 4 * i))
        except Exception:
            continue
        for a, ws, _ in iram:
            if a not in (84, 200):
                continue                       # the malformed slots
            blob = bytes(b for w in ws for b in w)
            if blob in seen:
                continue
            seen.add(blob)
            imgs.append((i, a, [int.from_bytes(blob[k:k + 5], "big")
                                for k in range(0, len(blob), 5)]))
    return imgs


def load_names(path):
    out = {}
    try:
        for ln in open(path):
            if ln.startswith("#"):
                continue
            f = ln.rstrip("\n").split("\t")
            if len(f) > 1 and f[0].isdigit():
                out[int(f[0])] = f[1]
    except OSError:
        pass
    return out


def rule(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def main():
    cap = sys.argv[1] if len(sys.argv) > 1 else DEF_CAP
    romp = sys.argv[2] if len(sys.argv) > 2 else DEF_ROM
    H, S, live0, live1, patch = load_scaffolding(cap)
    imgs = load_bodies(romp)
    names = load_names(DEF_TSV)
    allbody = [w for _, _, W in imgs for w in W]
    bodyw = collections.Counter(allbody)
    bodyf = collections.Counter(fam(w) for w in allbody)
    byalgo = {i: W for i, _, W in imgs}

    # ------------------------------------------------------------------ 1
    rule("1. WHAT IS ON THE FRAME PATH")
    print("  header   I-RAM  0..59 : %3d words   (live capture)" % len(H))
    print("  epilogue I-RAM 60..82 : %3d words   (live capture)" % len(S))
    for nm, cw in (("live unit-0 body @84 ", live0), ("live unit-1 body @200", live1)):
        if cw is None:
            continue
        hit = [i for i, a, W in imgs if W == cw]
        print("  %s : %3d words   byte-identical to ROM algo %s %s"
              % (nm, len(cw), hit, [names.get(i, "") for i in hit]))
    print("  ROM corpus            : %3d distinct images, %d words"
          % (len(imgs), len(allbody)))

    # ------------------------------------------------------------------ 2
    rule("2. DECODED COVERAGE PER REGION  (all six forms ARE implemented in the core)")
    frame = H + (live0 or []) + S + (live1 or [])
    simplest = H + byalgo.get(0, []) + S + (live1 or [])
    regions = [("header  @0", H), ("epilogue @60", S)]
    if live0:
        regions.append(("unit-0 body @84", live0))
    if live1:
        regions.append(("unit-1 body @200", live1))
    regions += [("LIVE FRAME", frame),
                ("simplest frame (NO OP)", simplest),
                ("scaffolding alone", H + S),
                ("all 38 ROM bodies", allbody)]
    print("  %-24s %6s %8s %10s %8s   forms" % ("region", "words", "decoded",
                                                "undecoded", "%dec"))
    for nm, W in regions:
        d = sum(1 for w in W if D.decoded(w))
        c = collections.Counter(form_of(w) for w in W if D.decoded(w))
        print("  %-24s %6d %8d %10d %7.1f%%   %s"
              % (nm, len(W), d, len(W) - d, 100.0 * d / max(1, len(W)),
                 dict(c) if c else "{}"))

    # ------------------------------------------------------------------ 3
    rule("3. PER-IMAGE DECODED COUNT -- can the decoded subset run ANY program?")
    rows = sorted((sum(1 for w in W if D.decoded(w)) / len(W), i, a, len(W),
                   sum(1 for w in W if D.decoded(w))) for i, a, W in imgs)
    for frac, i, a, n, d in rows:
        print("  %-22s unit %d  %4d words  %3d decoded  %5.1f%%"
              % (names.get(i, "algo%d" % i)[:22], 0 if a == 84 else 1, n, d,
                 100 * frac))
    z = [names.get(i, "algo%d" % i) for f, i, a, n, d in rows if d == 0]
    print("\n  images with ZERO decoded words: %d of %d -> %s" % (len(z), len(rows), z))

    # ------------------------------------------------------------------ 4
    rule("4. THE SCAFFOLDING IS A VOCABULARY ISLAND")
    sc = H + S
    print("  distinct words in header+epilogue          : %d" % len(set(sc)))
    print("  ... occurring in NO body word (of %d)     : %d"
          % (len(allbody), sum(1 for w in set(sc) if w not in bodyw)))
    print("  distinct (hi12,class4,lo12) families       : %d" % len(set(map(fam, sc))))
    print("  ... occurring in NO body                   : %d"
          % sum(1 for f in set(map(fam, sc)) if f not in bodyf))
    und = [w for w in sc if not D.decoded(w)]
    top = collections.Counter(fam(w) for w in und).most_common(1)
    print("  most frequent undecoded family here        : %s x%d"
          % (fstr(top[0][0]), top[0][1]) if top else "")
    print("\n  class4 census                header  epilogue   bodies")
    for cl in range(16):
        h = sum(1 for w in H if D.class4(w) == cl)
        s = sum(1 for w in S if D.class4(w) == cl)
        b = sum(1 for w in allbody if D.class4(w) == cl)
        if h or s or b:
            mark = "   <-- SCAFFOLDING-ONLY" if b == 0 and (h or s) else ""
            print("    class %X                   %6d %9d %8d%s" % (cl, h, s, b, mark))
    for hi in (0xC00, 0xC40):
        h = [(k, wstr(w)) for k, w in enumerate(H) if D.hi12(w) == hi]
        s = [(60 + k, wstr(w)) for k, w in enumerate(S) if D.hi12(w) == hi]
        b = sum(1 for w in allbody if D.hi12(w) == hi)
        print("    hi12 == 0x%03X : header %s epilogue %s bodies %d" % (hi, h, s, b))

    # ------------------------------------------------------------------ 5
    rule("5. MEASURED SEMANTICS THE CORE DOES NOT APPLY TO UNDECODED WORDS")
    print("  %-24s %8s %10s %12s" % ("region", "class-A", "  of which", "not executed"))
    for nm, W in (("LIVE FRAME", frame), ("all 38 ROM bodies", allbody),
                  ("scaffolding", sc)):
        a = [w for w in W if D.class4(w) == 0xA]
        b4 = [w for w in W if bit4_store(w)]
        print("  %-24s %8d %10s %12d"
              % (nm, len(a), "decoded " + str(sum(1 for w in a if D.decoded(w))),
                 sum(1 for w in a if not D.decoded(w))))
        print("  %-24s %8d %10s %12d"
              % ("  (bit-4 stores)", len(b4),
                 "decoded " + str(sum(1 for w in b4 if D.decoded(w))),
                 sum(1 for w in b4 if not D.decoded(w))))

    # ------------------------------------------------------------------ 6
    rule("6. THE CURSOR CONTRADICTION")
    pre = H[:49]                       # everything before the unit-0 CALL
    print("  header words before the unit-0 CALL (I-RAM 0..48):")
    print("     strict class-A          : %d" % sum(1 for w in pre if D.class4(w) == 0xA))
    print("     bit-23 (cursor fetch)   : %d" % sum(1 for w in pre if (w >> 23) & 1))
    for nm, W in (("header", H), ("epilogue", S), ("2974 body words", allbody)):
        print("  rstcur (801.0.00.021) in %-16s: %d"
              % (nm, sum(1 for w in W if D.is_rstcur(w))))
    print("  => a single free-running cursor would be ~21 when unit 0 starts, yet every")
    print("     effect's coefficients are MEASURED to be uploaded at C-RAM base 0x00.")
    print("     An undecoded word (or the CALL itself) must rebase or bank the cursor.")
    print()
    print("  ESCAPE-FORMAT HAZARD (bit 11 set => class4 is not a class):")
    for nm, W in (("header", H), ("epilogue", S), ("bodies", allbody)):
        e = [w for w in W if is_escape(w)]
        ea = [w for w in e if D.class4(w) == 0xA]
        print("    %-9s escape=%4d  of which class4==A and so counted into the"
              " cursor = %d %s"
              % (nm, len(e), len(ea), [wstr(w) for w in ea]))

    # ------------------------------------------------------------------ 7
    rule("7. THE FRAME PATH, WORD BY WORD (scaffolding)")
    for nm, base, W in (("HEADER", 0, H), ("EPILOGUE", 60, S)):
        print("\n  --- %s ---" % nm)
        for k, w in enumerate(W):
            note = D.annotate(w) or ""
            print("   %s %3d  %010X  %s  hi12{%s}%s  body:w=%d,f=%d %s"
                  % ("DEC" if D.decoded(w) else "  ?", base + k, w, wstr(w),
                     D.hi12_text(D.hi12(w)),
                     " cur+" if D.cursor_fetch(w) else "     ",
                     bodyw.get(w, 0), bodyf.get(fam(w), 0),
                     ("[%s]" % note) if note else ""))
    print("\n  host-patched slots observed in the capture:")
    for a, w in patch:
        print("    I-RAM %2d  %010X  %s" % (a, w, wstr(w)))

    # ------------------------------------------------------------------ 8
    rule("8. UNDECODED FAMILIES ON THE FRAME PATH (frequency, for contrast only)")
    fc = collections.Counter(fam(w) for w in frame if not D.decoded(w))
    nund = sum(fc.values())
    cum = 0
    print("  %-18s %5s %7s  %8s %6s  annotation" % ("family", "frame", "cum%",
                                                    "corpus", "images"))
    imgof = collections.defaultdict(set)
    for i, a, W in imgs:
        for w in W:
            imgof[fam(w)].add(i)
    for f, n in fc.most_common(20):
        cum += n
        ex = next(w for w in frame if fam(w) == f)
        print("  %-18s %5d %6.1f%%  %8d %6d  %s"
              % (fstr(f), n, 100.0 * cum / nund, bodyf.get(f, 0),
                 len(imgof.get(f, ())), (D.annotate(ex) or "")[:34]))
    print("\n  NOTE: the top of this list is the reverb tank (9 diffusers x 6 words),")
    print("  which is the one algorithm already solved structurally.  Frequency does")
    print("  NOT rank by blocking -- see notes/dsp-critical-path-coverage.md sect. 5.")

    # ------------------------------------------------------------------ 9
    rule("9. BLOCKING-CANDIDATE DOSSIERS")

    def dossier(pred, name):
        print("\n  --- %s ---" % name)
        for base, W, rname in ((0, H, "header"), (60, S, "epilogue")):
            for k, w in enumerate(W):
                if pred(w):
                    print("    %-9s I-RAM %2d  %010X  %s"
                          % (rname, base + k, w, wstr(w)))
        hits = collections.Counter()
        pos = []
        for i, a, W in imgs:
            for k, w in enumerate(W):
                if pred(w):
                    hits[w] += 1
                    pos.append(k / max(1, len(W) - 1))
        if hits:
            print("    bodies: %d occurrences, %d distinct; top %s"
                  % (sum(hits.values()), len(hits),
                     {"%010X" % k: v for k, v in hits.most_common(6)}))
            print("    mean normalised position in body = %.3f" % (sum(pos) / len(pos)))
        else:
            print("    bodies: 0 occurrences   <-- SCAFFOLDING-ONLY")

    dossier(lambda w: D.class4(w) == 1 and D.addr8(w) in (0x0E, 0x0F),
            "B1  unit-tagged transfer (CALL / RETURN)")
    dossier(lambda w: D.hi12(w) == 0xC00, "B2  hi12 = 0xC00 (frame wait)")
    dossier(lambda w: D.class4(w) in (9, 0xC, 0xD), "B3/B4  classes 9 / C / D")
    dossier(lambda w: D.lo12(w) in (0x445, 0x446), "B4  host patch slots 445/446")
    dossier(lambda w: D.lo12(w) in (0x820, 0x822, 0x825, 0x827),
            "B6  pointer-load siblings 820/822/825/827")
    dossier(lambda w: fam(w) == (0x000, 2, 0x407), "B8  000.2.**.407")
    dossier(lambda w: fam(w) == (0x212, 2, 0x000), "B9  212.2.**.000 (plain store)")
    dossier(lambda w: D.hi12(w) == 0x880 and D.class4(w) == 1,
            "B11 external delay-DRAM bracket 880.1")
    dossier(lambda w: D.class4(w) == 8, "B12 class 8 post-sum step")


if __name__ == "__main__":
    main()
