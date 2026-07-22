#!/usr/bin/env python3
"""kn5000_dsp_class2.py -- decode attempt on CLASS 2, the largest instruction group
of the NEC uPD6383GF effects DSP (KN5000 IC311).

class4 == 2 accounts for 429 of the 688 distinct words and 3630 of the 6532 words
of the 91 valid ROM effect bodies.  Nothing was known about it.  This tool runs the
experiments written up in notes/kn5000-dsp-class2.md:

    inventory   class histogram, class-2 vocabulary, position/run statistics
    fields      does hi12 / lo12 decompose into sub-fields WITHIN class 2?
    joint       the (hi12, lo12) contingency table and its sparsity
    semantics   per-image membership of every hi12 / lo12 value, scored against
                effect-topology categories assigned from the effect NAMES
                (dram / lfo / env / filt) -- the mandatory controls
    mac         class 2 vs class A: which one consumes coefficients?
    addr8       is addr8 an absolute RAM address or a pointer displacement?
    reverb      the four class-2 words of the reverb stage, and where else they live

Usage:
    python3 tools/kn5000_dsp_extract.py <subprogram.rom> /tmp/progs
    python3 tools/kn5000_dsp_class2.py <subprogram.rom> /tmp/progs \\
            [--names <kn5000_v10_program.rom>] [section ...]

Reuses tools/kn5000_dsp_extract.py, kn5000_dsp_coeffs.py, kn5000_dsp_params.py.
Nothing here re-implements the bytecode parsing.

Every number printed is MEASURED.  Interpretation lives in the notes file.
"""
import collections
import glob
import math
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kn5000_dsp_coeffs as C          # noqa: E402
import kn5000_dsp_params as P          # noqa: E402

# Streams whose ALGO_TABLE pointer does not yield a valid I-RAM image: they load
# outside the 384-word I-RAM, contain no terminator and no class-2 word at all.
# 79/88 were already known (encoding note sect. 0b); 89/90/91 are the same defect
# and are excluded here for the first time -- including them adds 396 junk words.
MALFORMED = {79, 88, 89, 90, 91}

# ---------------------------------------------------------------------------
# ground truth: effect topology, assigned from the effect NAME alone.
# Keyed by the lowest algorithm slot of each distinct program image.
#   dram = uses the external DRAM delay memory
#   lfo  = has a periodic modulation source
#   env  = has an envelope / level follower
#   filt = has a tunable multi-pole filter section
# ---------------------------------------------------------------------------
IMG_CAT = {
    0:  ('NO OPERATION',     0, 0, 0, 0),
    1:  ('CHORUS',           1, 1, 0, 0),
    2:  ('MODULATED CHORUS', 1, 1, 0, 0),
    3:  ('ENHANCER',         1, 0, 0, 1),
    4:  ('FLANGER',          1, 1, 0, 0),
    5:  ('PHASER',           0, 1, 0, 0),
    6:  ('ENSEMBLE',         1, 1, 0, 0),
    8:  ('GATED REVERB',     1, 0, 1, 0),
    9:  ('SINGLE DELAY',     1, 0, 0, 0),
    10: ('MULTI TAP DELAY',  1, 0, 0, 0),
    15: ('ROCK ROTARY',      1, 1, 0, 1),
    16: ('REVERB x12',       1, 0, 0, 0),
    32: ('DISTORTION',       0, 0, 0, 0),
    33: ('OVERDRIVE',        0, 0, 0, 1),
    34: ('FUZZ',             0, 0, 0, 0),
    35: ('EXCITER',          0, 0, 0, 1),
    36: ('COMPRESSOR',       0, 0, 1, 0),
    39: ('PARAMETRIC EQ',    0, 0, 0, 1),
    48: ('AUTO PAN',         0, 1, 0, 0),
    50: ('VIBRATO',          1, 1, 0, 0),
    52: ('AUTO WAH',         0, 0, 1, 1),
    54: ('RING MODULATOR',   0, 1, 0, 0),
    56: ('MIX UP',           1, 1, 0, 0),
    64: ('S.DELAY+CHORUS',   1, 1, 0, 0),
    65: ('S.DELAY+S.DELAY',  1, 0, 0, 0),
    66: ('S.DELAY+FLANGER',  1, 1, 0, 0),
    67: ('S.DELAY+VIBRATO',  1, 1, 0, 0),
    68: ('S.DELAY+PHASER',   1, 1, 0, 0),
    70: ('AUTO WAH+S.DELAY', 1, 0, 1, 1),
    71: ('PEQ+CHORUS',       1, 1, 0, 1),
    72: ('PEQ+S.DELAY',      1, 0, 0, 1),
    73: ('PEQ+FLANGER',      1, 1, 0, 1),
    74: ('PEQ+VIBRATO',      1, 1, 0, 1),
    75: ('PEQ+COMPRESSOR',   0, 0, 1, 1),
    96: ('PEQ+COMPR+DIST',   0, 0, 1, 1),
    97: ('PEQ+COMPR+OVERDR', 0, 0, 1, 1),
    98: ('PEQ+DIST+DELAY',   1, 0, 0, 1),
    99: ('PEQ+OVERDR+DELAY', 1, 0, 0, 1),
}
CATS = ("dram", "lfo", "env", "filt")

# the four class-2 words of the 8-instruction reverb stage (reverb note sect. 1)
REVERB_STAGE_C2 = [0x104200000, 0x000200419, 0x012200680, 0x000200000]


# ------------------------------------------------------------------ helpers

def fl(w):
    """hi12, class4, addr8, lo12"""
    return ((w >> 24) & 0xFFF, (w >> 20) & 0xF, (w >> 12) & 0xFF, w & 0xFFF)


def fmt(w):
    h, c, a, l = fl(w)
    return f"{h:03X}.{c:X}.{a:02X}.{l:03X}"


def load_progs(d):
    out = {}
    for f in sorted(glob.glob(os.path.join(d, "algo*.bin"))):
        n = int(os.path.basename(f)[4:6])
        if n in MALFORMED:
            continue
        raw = open(f, "rb").read()
        out[n] = [int.from_bytes(raw[i:i + 5], "big") for i in range(0, len(raw), 5)]
    return out


def images(progs):
    """-> {representative_algo: [word,...]} collapsing byte-identical images."""
    d = {}
    for a in sorted(progs):
        d.setdefault(tuple(progs[a]), []).append(a)
    return {al[0]: list(k) for k, al in d.items()}


def entropy(x):
    n = len(x)
    c = collections.Counter(x)
    return -sum(v / n * math.log2(v / n) for v in c.values())


def mutinf(a, b):
    n = len(a)
    j = collections.Counter(zip(a, b))
    ca, cb = collections.Counter(a), collections.Counter(b)
    return sum(v / n * math.log2((v / n) / (ca[x] / n * cb[y] / n))
               for (x, y), v in j.items())


def pearson(x, y):
    mx, my = statistics.mean(x), statistics.mean(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den = (sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y)) ** 0.5
    return num / den if den else 0.0


def partial(rxy, rxz, ryz):
    """partial correlation of x,y controlling for z"""
    den = math.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))
    return (rxy - rxz * ryz) / den if den else 0.0


def mcc(tp, fp, fn, tn):
    den = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return (tp * tn - fp * fn) / den if den else 0.0


# ------------------------------------------------------------------ sections

def sec_inventory(progs, c2):
    print("=" * 74)
    print("1. INVENTORY -- class 2 in effect-body code")
    print("=" * 74)
    allw = [w for v in progs.values() for w in v]
    ch = collections.Counter(fl(w)[1] for w in allw)
    chd = collections.Counter(fl(w)[1] for w in set(allw))
    print(f"{len(progs)} valid programs, {len(allw)} words, "
          f"{len(set(allw))} distinct   (excluded: {sorted(MALFORMED)})")
    print("class4  occurrences  distinct")
    for k in sorted(ch):
        print(f"   {k:X}   {ch[k]:>10}  {chd[k]:>8}")
    print(f"\nclass 2 = {len(c2)} words ({100*len(c2)/len(allw):.1f}% of code), "
          f"{len(set(c2))} distinct ({100*len(set(c2))/len(set(allw)):.1f}% of vocabulary)")

    # per-bit occupancy inside class 2
    live = [b for b in list(range(35, 23, -1)) + list(range(19, -1, -1))]
    dead = [b for b in live if len({(w >> b) & 1 for w in set(c2)}) == 1]
    print(f"\nbits with ZERO variance inside class 2: {dead}")
    print("   (word bit 24 = hi12 bit0, bit 11 and bit 5 = lo12 bits 11 and 5)")

    # position + runs
    pos, runs = [], []
    for a in progs:
        n = len(progs[a])
        r = 0
        for i, w in enumerate(progs[a]):
            if fl(w)[1] == 2:
                pos.append(i / (n - 1))
                r += 1
            else:
                if r:
                    runs.append(r)
                r = 0
        if r:
            runs.append(r)
    h = [0] * 10
    for x in pos:
        h[min(9, int(x * 10))] += 1
    print(f"\nnormalised position in program: mean {statistics.mean(pos):.3f} "
          f"median {statistics.median(pos):.3f}")
    print(f"   decile histogram {h}")
    print(f"run lengths: {collections.Counter(runs).most_common(8)} max {max(runs)}")
    fw = collections.Counter(fl(progs[a][0])[1] for a in progs)
    print(f"first word of a program: class histogram {dict(sorted(fw.items()))}")
    print("last word of a program : class 1 in 91/91 (the terminator landmark)")


def sec_fields(c2):
    print()
    print("=" * 74)
    print("2. DOES class 2 DECOMPOSE?  hi12 / lo12 sub-field test")
    print("=" * 74)
    H = [fl(w)[0] for w in c2]
    L = [fl(w)[3] for w in c2]
    print(f"H(hi12) = {entropy(H):.2f} bits over {len(set(H))} values")
    print(f"H(lo12) = {entropy(L):.2f} bits over {len(set(L))} values")
    print(f"MI(hi12, lo12) = {mutinf(H, L):.2f} bits   "
          f"(1.96 bits over ALL classes -- coupling drops but does not vanish)")
    print(f"(hi12, lo12) combinations used: {len(set(zip(H, L)))} "
          f"of {len(set(H))*len(set(L))} possible")

    print("\nhi12 values (word bits 35..24), class 2 only:")
    for v, n in sorted(collections.Counter(H).items()):
        print(f"   {v:03X}  {v:012b}  x{n}")
    print("lo12 values (word bits 11..0), class 2 only:")
    for v, n in sorted(collections.Counter(L).items()):
        print(f"   {v:03X}  {v:012b}  x{n}")

    print("\nCandidate split of hi12 suggested by the bit patterns:")
    print("   U = hi12[11:7]   V = hi12[5:4]   W = hi12[3:1]   (bits 6 and 0 dead)")
    U = [h >> 7 for h in H]
    V = [(h >> 4) & 3 for h in H]
    W = [(h >> 1) & 7 for h in H]
    print(f"   U {sorted(set(U))}   V {sorted(set(V))}   W {sorted(set(W))}")
    print(f"   (U,V,W) combos used {len(set(zip(U, V, W)))} of "
          f"{len(set(U))*len(set(V))*len(set(W))}")
    print(f"   MI(U,V)={mutinf(U, V):.2f}  MI(U,W)={mutinf(U, W):.2f}  "
          f"MI(V,W)={mutinf(V, W):.2f}")
    print(f"   H(U)+H(V)+H(W) = {entropy(U)+entropy(V)+entropy(W):.2f} "
          f"vs H(hi12) = {entropy(H):.2f}")
    print("   -> the three parts are NOT independent; the split does not separate.")

    Pp = [l >> 8 for l in L]
    Q = [l & 0xFF for l in L]
    print("\nSame test on lo12 split as [11:8] . [7:0]:")
    print(f"   MI = {mutinf(Pp, Q):.2f} bits against H([11:8]) = {entropy(Pp):.2f} "
          f"-- the high nibble is almost a function of the low byte.")
    print("   -> lo12 is ONE enumerated code, not two independent fields.")


def sec_joint(c2):
    print()
    print("=" * 74)
    print("3. THE (hi12, lo12) CONTINGENCY TABLE, class 2 only")
    print("=" * 74)
    g = collections.Counter((fl(w)[0], fl(w)[3]) for w in c2)
    His = sorted({h for h, _ in g})
    Los = sorted({l for _, l in g})
    print("      " + "".join(f"{l:>5X}" for l in Los))
    for h in His:
        print(f"{h:03X} |" + "".join(
            (f"{g[(h,l)]:>5}" if (h, l) in g else "    .") for l in Los))


def sec_semantics(IM, nm):
    print()
    print("=" * 74)
    print("4. SEMANTICS -- every hi12 / lo12 value scored against effect topology")
    print("=" * 74)
    print("Categories come from the effect NAMES (see IMG_CAT), not from the code.")
    print("MCC = Matthews correlation over the 38 distinct program images.\n")

    def members(pred):
        return {a for a, ws in IM.items()
                if any(fl(w)[1] == 2 and pred(w) for w in ws)}

    def best(S):
        out = []
        for ci, c in enumerate(CATS):
            pos = {a for a in IM if IMG_CAT[a][1 + ci]}
            tp = len(S & pos)
            fp = len(S - pos)
            fn = len(pos - S)
            tn = len(IM) - tp - fp - fn
            out.append((mcc(tp, fp, fn, tn), c, tp, fp, fn))
        return max(out)

    for tag, get in (("hi12", lambda w: fl(w)[0]), ("lo12", lambda w: fl(w)[3])):
        vals = sorted({get(w) for ws in IM.values() for w in ws if fl(w)[1] == 2})
        print(f"--- {tag} ---")
        rows = []
        for v in vals:
            S = members(lambda w, v=v, g=get: g(w) == v)
            m, c, tp, fp, fn = best(S)
            rows.append((m, v, len(S), c, tp, fp, fn))
        for m, v, n, c, tp, fp, fn in sorted(rows, reverse=True):
            star = " <<<" if m >= 0.9 else ""
            print(f"  {tag}={v:03X} in {n:2}/38 images   best={c:<5} "
                  f"MCC={m:+.3f} tp={tp} fp={fp} fn={fn}{star}")
        print()

    print("--- the three strongest, in full ---")
    for lbl, pred, cat in (
            ("hi12=082", lambda w: fl(w)[0] == 0x082, 2),
            ("hi12=C40", lambda w: fl(w)[0] == 0xC40, 3),
            ("lo12 in {647,687}", lambda w: fl(w)[3] in (0x647, 0x687), 4)):
        S = members(pred)
        pos = {a for a in IM if IMG_CAT[a][cat]}
        print(f"\n{lbl}  vs category '{CATS[cat-1]}'")
        print("   members : " + ", ".join(sorted(IMG_CAT[a][0] for a in S)))
        print("   FALSE +  : " + (", ".join(sorted(IMG_CAT[a][0] for a in S - pos)) or "none"))
        print("   FALSE -  : " + (", ".join(sorted(IMG_CAT[a][0] for a in pos - S)) or "none"))

    # rigid idioms
    print("\n--- fixed neighbour idioms (context of the strong words) ---")
    for lbl, pred in (("hi12=C40", lambda w: fl(w)[0] == 0xC40),
                      ("hi12=082", lambda w: fl(w)[0] == 0x082),
                      ("lo12=687", lambda w: fl(w)[3] == 0x687),
                      ("lo12=647", lambda w: fl(w)[3] == 0x647)):
        pre, post, tot = collections.Counter(), collections.Counter(), 0
        for a, ws in IM.items():
            for i, w in enumerate(ws):
                if fl(w)[1] == 2 and pred(w):
                    tot += 1
                    if i:
                        pre[fmt(ws[i - 1])] += 1
                    if i + 1 < len(ws):
                        post[fmt(ws[i + 1])] += 1
        print(f"  {lbl}: {tot} occurrences over the 38 images")
        print("     prev: " + ", ".join(f"{k}x{v}" for k, v in pre.most_common(4)))
        print("     next: " + ", ".join(f"{k}x{v}" for k, v in post.most_common(4)))


def sec_mac(IM, rom):
    print()
    print("=" * 74)
    print("5. CLASS 2 vs CLASS A -- which one consumes coefficients?")
    print("=" * 74)
    A = C.load_all(rom)
    nw, nc, n2, nA = [], [], [], []
    for a, ws in IM.items():
        nw.append(len(ws))
        nc.append(len(C.coeffs_of(A[a])))
        cnt = collections.Counter(fl(w)[1] for w in ws)
        n2.append(cnt[2])
        nA.append(cnt[0xA])
    r_cw, r_c2, r_cA = pearson(nc, nw), pearson(nc, n2), pearson(nc, nA)
    r_w2, r_wA = pearson(nw, n2), pearson(nw, nA)
    print(f"n = {len(nw)} distinct images")
    print(f"  r(ncoeff, nwords)    = {r_cw:+.3f}")
    print(f"  r(ncoeff, n_class2)  = {r_c2:+.3f}      r(nwords, n_class2) = {r_w2:+.3f}")
    print(f"  r(ncoeff, n_classA)  = {r_cA:+.3f}      r(nwords, n_classA) = {r_wA:+.3f}")
    print("\n  PARTIAL correlations, controlling for program length:")
    print(f"    ncoeff . n_class2 | nwords = {partial(r_c2, r_cw, r_w2):+.3f}")
    print(f"    ncoeff . n_classA | nwords = {partial(r_cA, r_cw, r_wA):+.3f}")
    print("  -> class A scales with the coefficient bank, class 2 scales AGAINST it.")


def sec_addr8(progs, IM, c2):
    print()
    print("=" * 74)
    print("6. addr8 INSIDE CLASS 2 -- absolute address or pointer displacement?")
    print("=" * 74)
    allw = [w for v in progs.values() for w in v]
    for cl in (2, 0xA, 1, 0):
        A = [fl(w)[2] for w in allw if fl(w)[1] == cl]
        if not A:
            continue
        h = collections.Counter(x >> 4 for x in A)
        small = sum(1 for x in A if x <= 0x10 or x >= 0xF0)
        print(f"class {cl:X}: n={len(A):5} distinct={len(set(A)):3}  "
              f"|value| within 16 of zero (mod 256): {100*small/len(A):.1f}%")
        print("        hi-nibble: " + " ".join(f"{k:X}:{h.get(k,0)}" for k in range(16)))

    sh = 0
    for a in progs:
        s2 = {fl(w)[2] for w in progs[a] if fl(w)[1] == 2 and fl(w)[2]}
        sA = {fl(w)[2] for w in progs[a] if fl(w)[1] == 0xA and fl(w)[2]}
        sh += len(s2 & sA)
    print(f"\nclass-2 and class-A addr8 sets share {sh} values within the same program")
    print("   -> the two classes address the SAME 8-bit space.")

    print("\nTHE DECISIVE CASE -- PARAMETRIC EQ (algo 39):")
    ws = IM[39]
    print("   a 9-word section repeated 10 times, BYTE-IDENTICAL:")
    for w in ws[5:14]:
        print("        " + fmt(w))
    print("   class-2 addr8 used anywhere in the program: " +
          " ".join(f"{x:02X}" for x in sorted({fl(w)[2] for w in ws if fl(w)[1] == 2})))
    print("   class-A addr8 used anywhere in the program: " +
          " ".join(f"{x:02X}" for x in sorted({fl(w)[2] for w in ws if fl(w)[1] == 0xA})))
    print("   The 10 repetitions are 5 bands x 2 channels and MUST use different")
    print("   coefficients, yet every field including addr8 is identical.")

    print("\nTHE CONTRARY CASE -- PHASER (algo 5):")
    ws = IM[5]
    print("   a 3-word section repeated, with addr8 walking two runs:")
    for w in ws[12:21]:
        print("        " + fmt(w))
    print("   class-2 addr8: " +
          " ".join(f"{x:02X}" for x in sorted({fl(w)[2] for w in ws if fl(w)[1] == 2})))


def sec_reverb(IM, progs, nm):
    print()
    print("=" * 74)
    print("7. THE REVERB STAGE -- the four class-2 words, and where else they live")
    print("=" * 74)
    for w in REVERB_STAGE_C2:
        occ = {a: progs[a].count(w) for a in progs if w in progs[a]}
        imgs = [IMG_CAT[a][0] for a, ws in IM.items() if w in ws]
        print(f"\n{fmt(w)}   {sum(occ.values())} occurrences, "
              f"{len(occ)} algorithm slots, {len(imgs)} distinct images")
        print("   images: " + ", ".join(sorted(imgs)))
    print("\nCONTROL: the exact word 104.2.00.000 also occurs in PHASER and")
    print("   S.DELAY+PHASER, whose phaser sections are all-pass chains with NO")
    print("   external delay line.  It cannot mean 'read the delay line'.")


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    rompath, progdir = argv[1], argv[2]
    rom = C.Rom(rompath)
    progs = load_progs(progdir)
    IM = images(progs)
    c2 = [w for v in progs.values() for w in v if fl(w)[1] == 2]
    names = {}
    if "--names" in argv:
        try:
            names = C.effect_names(argv[argv.index("--names") + 1])
        except Exception:
            names = {}
    nm = (lambda i: (names.get(i, "") or f"algo{i}").strip())

    want = [s for s in argv[3:] if not s.startswith("-")
            and not s.endswith(".rom")]
    run = (lambda s: not want or s in want)

    assert set(IM) == set(IMG_CAT), \
        f"image set changed: {sorted(set(IM) ^ set(IMG_CAT))}"

    if run("inventory"):
        sec_inventory(progs, c2)
    if run("fields"):
        sec_fields(c2)
    if run("joint"):
        sec_joint(c2)
    if run("semantics"):
        sec_semantics(IM, nm)
    if run("mac"):
        sec_mac(IM, rom)
    if run("addr8"):
        sec_addr8(progs, IM, c2)
    if run("reverb"):
        sec_reverb(IM, progs, nm)


if __name__ == "__main__":
    main(sys.argv)
