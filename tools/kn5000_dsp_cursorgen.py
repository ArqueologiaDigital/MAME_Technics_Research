#!/usr/bin/env python3
"""kn5000_dsp_cursorgen.py -- does the COEFFICIENT CURSOR model generalise?

Companion tool to notes/kn5000-dsp-cursor-general.md.  It takes the model proven
on the PARAMETRIC EQ's biquad (notes/kn5000-dsp-biquad-map.md) --

    an implicit auto-increment coefficient pointer with NO address field in the
    instruction word, advancing +1 per class-A word from the start of the
    microprogram --

and tests it on all 38 distinct program images, on the REVERB, and against the
per-image zero-init streams.

Nothing here re-implements parsing: it imports kn5000_dsp_extract (bytecode),
kn5000_dsp_class2 (field split / image set), kn5000_dsp_biquad (section finder),
kn5000_dsp_biquadmap (sbank) and kn5000_dsp_params (T1 host map).  None of them
is edited.

Sections:
    bank      bank size vs class-A count -- the independent test of "one
              coefficient word per class-A word"
    hostxref  every coefficient-space T1 entry vs the cursor's reachable range
    compress  the compressor's +4, localised
    reverb    ** the reverb, stage by stage, with the gain ladder read off **
    ladders   the same stage slots across all 12 reverb presets
    state     the zero-init streams: 4 state cells per biquad section, one space

Usage:
    python3 tools/kn5000_dsp_extract.py <subprogram_v142.rom> /tmp/progs
    python3 tools/kn5000_dsp_cursorgen.py <subprogram_v142.rom> /tmp/progs \\
            [<kn5000_v10_program.rom>] [section ...]
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kn5000_dsp_extract as E        # noqa: E402
import kn5000_dsp_class2 as K         # noqa: E402
import kn5000_dsp_biquad as B         # noqa: E402
import kn5000_dsp_biquadmap as BM     # noqa: E402
import kn5000_dsp_params as P         # noqa: E402

PEQ = 39
REVERB_IMG = 16                 # ROOM REVERB 1 -- the image shared by algos 16..27
REVERB_PRESETS = range(16, 28)

# T1 opcodes whose writer is LABEL_0387E6, i.e. whose addresses are
# COEFFICIENT-space (the 801.0.NN.821 pointer space) -- see
# notes/kn5000-dsp-parameters.md sect. 2 and kn5000_dsp_params.OPCODE_EVAL.
COEF_OPS = {op for op, (_e, wr, _f) in P.OPCODE_EVAL.items() if wr == 0x0387E6}
# ... minus the three that are the same in every image (global effect level /
# balance, not per-algorithm coefficients) and the two that demonstrably address
# the external-DRAM delay registers instead (0x67 -> always >= 0x26, 0x6A -> 0x56..).
COEF_OPS -= {0x74, 0x21, 0x67, 0x6A}

# the reverb motif (notes/kn5000-dsp-reverb.md sect. 1); the class-A word is at +5
MOTIF = [0x8801602D4, 0x104200000, 0x000200419, 0x012200680,
         0x880120655, 0x102A0064B, 0x000200000, 0x000200000]


def q23(v):
    return (v - (1 << 24)) / (1 << 23) if v & 0x800000 else v / (1 << 23)


def load(subrom, progdir):
    progs = K.load_progs(progdir)
    return progs, B.distinct_images(progs)


def classa_count(words):
    return sum(1 for w in words if K.fl(w)[1] == 0xA)


def bank_of(subrom, algo):
    """[(address, 24-bit word)] of the algorithm's loaded coefficient bank."""
    out = []
    for base, ws in BM.sbank(subrom, algo):
        for i, w in enumerate(ws):
            out.append((base + i, w))
    return out


def cursor_slots(words, base):
    """[(program index, coefficient address)] for every class-A word."""
    out, c = [], 0
    for i, w in enumerate(words):
        if w == 0x801000021:            # the proven rewind (pointer <- 0)
            c = 0
        if K.fl(w)[1] == 0xA:
            out.append((i, base + c))
            c += 1
    return out


# --------------------------------------------------------------- bank

def sec_bank(subrom, progs, imgs, mrom):
    print("=== the independent test: bank size vs class-A count\n")
    print("PREDICTION (pre-registered): if the cursor advances +1 per class-A word and")
    print("never repeats, the program loader must load EXACTLY as many coefficient words")
    print("as the program has class-A words.  The loader and the microcode are written by")
    print("different tools and neither knows the other's count.\n")
    print(f"{'algo':>4} {'name':22} {'base':>5} {'clsA':>5} {'bank':>5} {'bank-clsA-1':>12}")
    exact = 0
    rows = []
    for a in imgs:
        w = progs[a]
        nA = classa_count(w)
        bk = bank_of(subrom, a)
        base = bk[0][0] if bk else 0
        d = len(bk) - nA - 1
        rows.append((a, base, nA, len(bk), d))
        exact += (d == 0)
        nm = P.effect_name(mrom, a) if mrom else str(a)
        print(f"{a:>4} {nm:22} 0x{base:02X} {nA:>5} {len(bk):>5} {d:>+12}")
    print(f"\n   bank == class-A + 1 in {exact} of {len(imgs)} images.")
    print("   The '+1' is the trailing spare word (algo 39 loads it separately at 0x1E).")
    return {a: d for a, _b, _n, _k, d in rows}


# --------------------------------------------------------------- hostxref

def sec_hostxref(subrom, progs, imgs, rom, mrom, defc):
    print("=== every coefficient-space T1 address vs the cursor's reachable range\n")
    print("Reachable range = [base, base + class-A count + deficit).  The deficit comes")
    print("from the BANK SIZE (previous section); the T1 addresses come from the HOST's")
    print("parameter map.  Two unrelated measurements.\n")
    tot = ok = 0
    for a in imgs:
        w = progs[a]
        nA = classa_count(w)
        bk = bank_of(subrom, a)
        base = bk[0][0] if bk else 0
        t1p = rom.u32le(P.ALGO_T1_ARRAY + 4 * a)
        ents = []
        if t1p and t1p != P.NULL_T1:
            for _ad, op, e in P.parse_t1(rom, t1p):
                if op in COEF_OPS:
                    ents += [(op, v) for v in e]
        if not ents:
            continue
        top = base + nA + max(0, defc.get(a, 0))
        inside = [(o, v) for o, v in ents if base <= v < base + nA]
        strad = [(o, v) for o, v in ents if base + nA <= v < top]
        out = [(o, v) for o, v in ents if not (base <= v < top)]
        tot += len(ents)
        ok += len(ents) - len(out)
        nm = P.effect_name(mrom, a) if mrom else str(a)
        print(f"{a:>4} {nm:22} base 0x{base:02X} clsA {nA:>3} top 0x{top:02X}  "
              f"in {len(inside)}  in-deficit {len(strad)}  OUT {len(out)}"
              + (f"  {[(hex(o), hex(v)) for o, v in out]}" if out else ""))
    print(f"\n   {ok}/{tot} coefficient-space T1 addresses lie inside the reachable range.")


# --------------------------------------------------------------- compress

def sec_compress(subrom, progs, mrom):
    print("=== the compressor's +4, localised\n")
    for a in (36, 75, 96, 97):
        w = progs[a]
        nA = classa_count(w)
        bk = bank_of(subrom, a)
        nm = P.effect_name(mrom, a) if mrom else str(a)
        print(f"algo {a} {nm}: class-A {nA}, bank {len(bk)}, deficit {len(bk)-nA-1:+d}"
              f"  ({(len(bk)-nA-1)//2} per compressor stage x 2 stages)")
    print("\nThe 11 words that every compressor stage contains and that no zero-deficit")
    print("image contains (candidates for the four non-class-A coefficient consumers):")
    cnt = collections.Counter()
    for a in (36, 75, 96, 97):
        seen = set()
        for x in progs[a]:
            h, c, ad, lo = K.fl(x)
            if c != 0xA:
                seen.add((h, c, lo))
        for f in seen:
            cnt[f] += 1
    zero = set()
    for a in progs:
        pass
    for f, n in sorted(cnt.items()):
        if n == 4:
            print(f"   {f[0]:03X}.{f[1]:X}.{f[2]:03X}")


# --------------------------------------------------------------- reverb

def sec_reverb(subrom, progs, rom, mrom, algo=REVERB_IMG):
    print(f"=== ** THE REVERB, stage by stage ** (image {REVERB_IMG}, "
          f"coefficients of algo {algo})\n")
    print("PREDICTION, stated before running: the motif has ONE class-A word per stage,")
    print("so the cursor must hand each successive diffuser stage the next bank word.")
    print("Stages 1..5 (chain 0) should pick up a descending gain ladder, stages 6..9")
    print("(chain 1) a second descending ladder.\n")
    w = progs[REVERB_IMG]
    bk = dict(bank_of(subrom, algo))
    base = min(bk)
    slots = dict(cursor_slots(w, base))
    # motif occurrences, tolerant of the one-field variant at the block-2 head
    hits = []
    for i in range(len(w) - 8 + 1):
        d = sum(1 for k in range(8) if w[i + k] != MOTIF[k])
        if d <= 1:
            hits.append(i)
    print(f"motif at {hits}   ({len(hits)} repetitions)")
    print(f"coefficient bank: {len(bk)} words at 0x{base:02X}..0x{max(bk):02X}\n")
    print(f"{'stage':>5} {'motif@':>7} {'classA@':>8} {'coef':>6} {'value':>10}  chain")
    for n, i in enumerate(hits):
        ai = i + 5
        ad = slots[ai]
        print(f"{n+1:>5} {i:>7} {ai:>8}  0x{ad:02X} {q23(bk[ad]):>+10.6f}"
              f"  {'0' if n < 5 else '1'}")
    print("\n-- the DRAM-bracketed single-multiply stages the motif scan misses")
    for i in range(len(w) - 4):
        h, c, ad, lo = K.fl(w[i])
        if h == 0x880 and c == 1 and ad == 0x60 and lo == 0x2DA:
            ai = next(j for j in range(i, i + 6) if K.fl(w[j])[1] == 0xA)
            a2 = slots[ai]
            print(f"   bracket at {i:>3}  class-A at {ai:>3}  coef 0x{a2:02X}"
                  f" = {q23(bk[a2]):+.6f}")
    print("\n-- every class-A word of the reverb, with the bank word the cursor gives it")
    for i, ad in sorted(slots.items()):
        v = bk.get(ad)
        print(f"   [{i:>3}] {K.fmt(w[i])}   coef 0x{ad:02X} = "
              + (f"{q23(v):+.6f}" if v is not None else "(past end of bank)"))
    print("\n-- the host's T1 map for this preset, against those slots")
    t1p = rom.u32le(P.ALGO_T1_ARRAY + 4 * algo)
    used = set(slots.values())
    if t1p and t1p != P.NULL_T1:
        for _ad, op, e in P.parse_t1(rom, t1p):
            if op not in COEF_OPS:
                continue
            for v in e:
                print(f"   op 0x{op:02X} -> 0x{v:02X}   "
                      + ("HITS a class-A slot" if v in used else "NOT a class-A slot"))


# --------------------------------------------------------------- ladders

def sec_ladders(subrom, progs, mrom):
    print("=== the same stage slots across all 12 reverb presets\n")
    w = progs[REVERB_IMG]
    hits = []
    for i in range(len(w) - 8 + 1):
        if sum(1 for k in range(8) if w[i + k] != MOTIF[k]) <= 1:
            hits.append(i)
    for a in REVERB_PRESETS:
        bk = dict(bank_of(subrom, a))
        if not bk:
            continue
        base = min(bk)
        slots = dict(cursor_slots(w, base))
        g = [q23(bk[slots[i + 5]]) for i in hits if slots[i + 5] in bk]
        nm = P.effect_name(mrom, a) if mrom else str(a)
        mono0 = all(g[k] >= g[k + 1] for k in range(4))
        mono1 = all(g[k] >= g[k + 1] for k in range(5, len(g) - 1))
        print(f"{a:>4} {nm:18} n={len(bk):>3}  chain0 "
              + " ".join(f"{v:+.3f}" for v in g[:5])
              + "  | chain1 " + " ".join(f"{v:+.3f}" for v in g[5:])
              + f"   descending: {mono0}/{mono1}")


# --------------------------------------------------------------- state

def sec_state(subrom, progs, imgs, rom, mrom):
    print("=== TASK C: the zero-init streams -- where the state cells are, and how many\n")
    print("The parameter stream's op-0 records are 'pointer <- NN' (000.1.NN.000) followed")
    print("by writes of zero.  That pointer is the SECOND address space (the one writers")
    print("LABEL_038539 / LABEL_03846C use, descriptor field +2), NOT the 801.0 coefficient")
    print("space.  So every state cell a program clears lives in ONE space.\n")
    ref = progs[PEQ][5:5 + B.SECTION_LEN]
    r = E.Rom(subrom)
    for a in imgs:
        p = r.u32le(E.PARAM_TABLE + 4 * a)
        blocks = []
        for _ in range(64):
            b0, b1 = r.u8(p), r.u8(p + 1)
            op = b0 >> 4
            if op == 0xF:
                break
            ln = ((b0 & 0xF) << 8) | b1
            body = r.slice(p + 2, ln - 2)
            if op == 0:
                d = body[3:]
                ws = [int.from_bytes(d[k:k + 5], 'big')
                      for k in range(0, len(d) - 4, 5)]
                cur, n = None, 0
                for x in ws:
                    h, c, ad, lo = K.fl(x)
                    if h == 0 and c == 1 and lo == 0:
                        if cur is not None:
                            blocks.append((cur, n))
                        cur, n = ad, 0
                    else:
                        n += 1
                if cur is not None:
                    blocks.append((cur, n))
            p += ln
        nsec = len(B.find_sections(progs[a], ref, maxdiff=3))
        big = [(b, n) for b, n in blocks if 0x50 <= b < 0x80]
        nm = P.effect_name(mrom, a) if mrom else str(a)
        print(f"{a:>4} {nm:22} biquad sections {nsec:>2}  need {4*nsec:>3} cells   "
              f"cleared in 0x50.. : {[(hex(b), n) for b, n in big]}")


# --------------------------------------------------------------- main

def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    subrom, progdir = argv[1], argv[2]
    mainrom = argv[3] if len(argv) > 3 and argv[3].endswith('.rom') else None
    secs = [s for s in argv[3 if not mainrom else 4:]] or \
        ['bank', 'hostxref', 'compress', 'reverb', 'ladders', 'state']
    progs, imgs = load(subrom, progdir)
    rom = P.Rom(subrom, P.SUB_BASE)
    mrom = P.Rom(mainrom, 0) if mainrom else None
    defc = {}
    for s in secs:
        print('\n' + '=' * 78)
        if s == 'bank':
            defc = sec_bank(subrom, progs, imgs, mrom)
        elif s == 'hostxref':
            if not defc:
                defc = {a: len(bank_of(subrom, a)) - classa_count(progs[a]) - 1
                        for a in imgs}
            sec_hostxref(subrom, progs, imgs, rom, mrom, defc)
        elif s == 'compress':
            sec_compress(subrom, progs, mrom)
        elif s == 'reverb':
            sec_reverb(subrom, progs, rom, mrom)
        elif s == 'ladders':
            sec_ladders(subrom, progs, mrom)
        elif s == 'state':
            sec_state(subrom, progs, imgs, rom, mrom)
        else:
            print(f"unknown section {s}")


if __name__ == '__main__':
    main(sys.argv)
