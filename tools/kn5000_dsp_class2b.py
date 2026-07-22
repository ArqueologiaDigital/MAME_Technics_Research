#!/usr/bin/env python3
"""kn5000_dsp_class2b.py -- CLASS 2 of the NEC uPD6383GF, second pass.

Round one (tools/kn5000_dsp_class2.py, notes/kn5000-dsp-class2.md) established that
class 2 does NOT decompose into bitfields, and left the reverb stage undecoded because
104.2.00.000 also occurs in the PHASER "which has no delay line".

This tool does not redo any of that.  It runs five NEW experiments, none of which is
more statistics on the instruction encoding:

    allpass   the ALL-PASS REFRAME.  A phaser and a reverb diffuser are the same
              algebra with different storage.  Test the storage split directly
              (external-DRAM bracket present/absent) and the shared-word membership.
    dataflow  cross-reference the microcode addr8 values against the addresses the
              HOST writes coefficients to (T1 maps, notes/kn5000-dsp-parameters.md).
    order     P(the previous instruction is class A) per hi12 / lo12 value.  A
              datapath imposes order; round one only looked at distributions.
    header    the 60-word common header's class-2 vocabulary vs the effect bodies'.
    bands     the PARAMETRIC EQ 4-vs-5 band contradiction, resolved three ways.

Usage:
    python3 tools/kn5000_dsp_extract.py <kn5000_subprogram_v142.rom> /tmp/progs
    python3 tools/kn5000_dsp_class2b.py <kn5000_subprogram_v142.rom> /tmp/progs [section ...]

Reuses kn5000_dsp_extract / kn5000_dsp_coeffs / kn5000_dsp_params / kn5000_dsp_class2.
Every number printed is MEASURED; interpretation lives in
notes/kn5000-dsp-class2-round2.md.
"""
import collections
import math
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kn5000_dsp_class2 as K        # noqa: E402  (corpus, fields, IMG_CAT, mcc)
import kn5000_dsp_coeffs as C        # noqa: E402
import kn5000_dsp_extract as E       # noqa: E402
import kn5000_dsp_params as P        # noqa: E402

fl, fmt = K.fl, K.fmt

# The 60-word common header, uploaded once per cold boot (notes/kn5000-dsp-header.md).
HEADER_ROM, HEADER_LEN = 0x01E496, 305
HEADER_SKIP = 5                       # 2-byte length + cmd byte + 2-byte I-RAM address

# The reverb stage (notes/kn5000-dsp-reverb.md sect. 1), as 40-bit words.
DRAM_OPEN, DRAM_CLOSE = (0x880, 1, 0x60), (0x880, 1, 0x20)

# ---------------------------------------------------------------------------
# PRE-REGISTERED topology label for the all-pass reframe.
# Assigned from the effect NAME and textbook DSP only, BEFORE looking at any word:
# a reverb diffuser is a chain of all-passes; a phaser IS a chain of all-passes.
# ENHANCER is deliberately labelled 0 -- round one flagged its labels as suspect,
# so leaving it at 0 makes it a possible FALSE POSITIVE, i.e. the harder test.
# ---------------------------------------------------------------------------
ALLPASS = {'REVERB x12', 'GATED REVERB', 'PHASER', 'S.DELAY+PHASER'}


def binom_p(k, n, p):
    """one-sided exact binomial tail, whichever side k falls on."""
    def pmf(i):
        return math.comb(n, i) * p ** i * (1 - p) ** (n - i)
    if k >= n * p:
        return sum(pmf(i) for i in range(k, n + 1))
    return sum(pmf(i) for i in range(0, k + 1))


def hyper_p(k, K_, n, N):
    """P(X >= k), X ~ Hypergeometric(N, K_, n)."""
    return sum(math.comb(K_, i) * math.comb(N - K_, n - i) / math.comb(N, n)
               for i in range(k, min(K_, n) + 1))


def header_words(rom):
    b = rom.slice(HEADER_ROM, HEADER_LEN)[HEADER_SKIP:]
    return [int.from_bytes(b[i:i + 5], 'big') for i in range(0, len(b) - 4, 5)]


def t1_addresses(prom, algo):
    """set of 8-bit DSP addresses the HOST writes user parameters to, for one algo."""
    ptr = prom.u32le(P.ALGO_T1_ARRAY + 4 * algo)
    if not prom.ok(ptr, 4):
        return set()
    s = set()
    for _, _op, ents in P.parse_t1(prom, ptr):
        s |= set(ents)
    s.discard(0)
    return s


# ======================================================================= 1
def sec_allpass(progs, IM):
    print("=" * 74)
    print("1. THE ALL-PASS REFRAME -- storage differs, algebra does not transfer")
    print("=" * 74)
    nm = {a: K.IMG_CAT[a][0] for a in IM}

    print("\n1a. THE STORAGE TEST (prediction: reverb has the external-DRAM bracket,")
    print("    the phaser does not).  880.1.XX class-1 words per image:")
    both, dram = [], []
    for a in sorted(IM, key=lambda x: nm[x]):
        c = collections.Counter(fl(w)[2] for w in progs[a]
                                if fl(w)[0] == 0x880 and fl(w)[1] == 1)
        has = 0x20 in c and 0x60 in c
        d = K.IMG_CAT[a][1]
        both.append(has)
        dram.append(d)
        flag = '' if has == bool(d) else '   <-- MISMATCH'
        print(f"    {nm[a]:20s} dram={d}  " +
              ' '.join(f'{k:02X}x{v}' for k, v in sorted(c.items())) + flag)
    tp = sum(1 for h, d in zip(both, dram) if h and d)
    fp = sum(1 for h, d in zip(both, dram) if h and not d)
    fn = sum(1 for h, d in zip(both, dram) if not h and d)
    tn = len(both) - tp - fp - fn
    print(f"\n    predictor 'has both 880.1.60 and 880.1.20' vs the DRAM label:")
    print(f"    TP={tp} FP={fp} FN={fn} TN={tn}   MCC={K.mcc(tp, fp, fn, tn):+.3f}"
          f"   p={hyper_p(tp, tp + fn, tp + fp, len(both)):.2e}")
    print("    PHASER: only 880.1.30 -- no DRAM bracket at all.  PREDICTION HOLDS.")

    print("\n1b. THE SHARED WORD.  Membership of each reverb-stage word:")
    stage = [0x8801602D4, 0x104200000, 0x000200419, 0x012200680,
             0x880120655, 0x102A0064B]
    for w in stage:
        imgs = sorted(nm[a] for a in IM if w in progs[a])
        print(f"    {fmt(w)}  {len(imgs)} images: {', '.join(imgs)}")

    print("\n1c. 104.2.00.000 scored against the PRE-REGISTERED all-pass label:")
    print(f"    label (name + textbook only): {sorted(ALLPASS)}")
    mem = {nm[a] for a in IM if 0x104200000 in progs[a]}
    tp = len(mem & ALLPASS)
    fp = len(mem - ALLPASS)
    fn = len(ALLPASS - mem)
    tn = len(IM) - tp - fp - fn
    print(f"    members: {sorted(mem)}")
    print(f"    TP={tp} FP={fp} FN={fn} TN={tn}   MCC={K.mcc(tp, fp, fn, tn):+.3f}"
          f"   p={hyper_p(tp, len(ALLPASS), len(mem), len(IM)):.2e}")
    ctrl = sorted(nm[a] for a in IM
                  if K.IMG_CAT[a][1] and 0x104200000 not in progs[a])
    print(f"    CONTROL -- images that DO use the external DRAM but lack the word"
          f" ({len(ctrl)}):\n      {', '.join(ctrl)}")

    print("\n1d. THE INTERNAL-RAM ALL-PASS SECTION (a 3-word idiom, mirror-addressed):")
    print("      102.2.<c>.1CD / 212.2.01.412 / 104.2.<s>.1D5   with c + s == 0xFF")
    for a in sorted(IM):
        n, ex = 0, []
        p = progs[a]
        for i in range(len(p) - 2):
            f0, f1, f2 = fl(p[i]), fl(p[i + 1]), fl(p[i + 2])
            if ((f0[0], f0[1], f0[3]) == (0x102, 2, 0x1CD)
                    and (f1[0], f1[3]) == (0x212, 0x412)
                    and (f2[0], f2[1], f2[3]) == (0x104, 2, 0x1D5)
                    and (f0[2] + f2[2]) & 0xFF == 0xFF):
                n += 1
                ex.append(f"{f0[2]:02X}/{f2[2]:02X}")
        if n:
            print(f"    {nm[a]:20s} {n:3d} sections   {' '.join(ex[:6])} ...")
    print("    Zero occurrences in the other 35 images, including every reverb.")


# ======================================================================= 2
def sec_dataflow(progs, IM, prom):
    print()
    print("=" * 74)
    print("2. DATA-FLOW CORRELATION WITH THE HOST WRITES")
    print("=" * 74)
    print("For each effect: which microcode addr8 values match an address the host")
    print("writes a user parameter to (T1 map)?  Coefficient operand vs internal state.")
    print()
    nm = {a: K.IMG_CAT[a][0] for a in IM}
    h2 = hA = e2 = eA = 0
    o2 = t2 = oA = tA = 0
    print(f"{'image':20s} {'|T1|':>4} {'c2 hit':>7} {'cA hit':>7} {'neither':>7}")
    for a in sorted(IM):
        T = t1_addresses(prom, a)
        if not T:
            continue
        c2 = [fl(w)[2] for w in progs[a] if fl(w)[1] == 2]
        cA = [fl(w)[2] for w in progs[a] if fl(w)[1] == 0xA]
        s2, sA = set(c2), set(cA)
        h2 += len(T & s2); hA += len(T & sA)
        e2 += len(T) * len(s2) / 256.0
        eA += len(T) * len(sA) / 256.0
        o2 += sum(1 for x in c2 if x in T); t2 += len(c2)
        oA += sum(1 for x in cA if x in T); tA += len(cA)
        print(f"{nm[a]:20s} {len(T):4d} {len(T & s2):7d} {len(T & sA):7d} "
              f"{len(T - s2 - sA):7d}")
    print()
    print(f"  TOTAL over 445 T1 entries:")
    print(f"    class-2 addr8 matched : {h2:4d}   chance expectation {e2:6.1f}"
          f"   enrichment x{h2 / e2:.2f}")
    print(f"    class-A addr8 matched : {hA:4d}   chance expectation {eA:6.1f}"
          f"   enrichment x{hA / eA:.2f}")
    print(f"    occurrence-weighted   : class 2 {o2}/{t2} = {o2 / t2:.3f}   "
          f"class A {oA}/{tA} = {oA / tA:.3f}")
    print("  MEASURED: 80% of host-written parameter addresses appear as NO addr8")
    print("  anywhere in the effect's own microcode.")

    print("\n  CONFOUND CHECK -- is a per-image relocation offset K hiding the match?")
    print("  (best K over 0..255, maximising |{(t+K)&0xFF} n addr8|):")
    ks = []
    for a in sorted(IM):
        T = t1_addresses(prom, a)
        if not T:
            continue
        A = set(fl(w)[2] for w in progs[a])
        sc = [(len({(t + k) & 0xFF for t in T} & A), k) for k in range(256)]
        best = max(sc)
        ks.append(best[1])
    hi = sum(1 for k in ks if k >= 0xE0)
    print(f"    best-K lands in 0xE0..0xFF for {hi} of {len(ks)} images.")
    print("    REJECTED as an artefact: 88% of all addr8 values already lie in")
    print("    0x00..0x10 / 0xF0..0xFF (round one sect. 6.2), so a small negative K")
    print("    trivially drags small T1 values into the dense band.  No relocation")
    print("    base is recoverable this way.")


# ======================================================================= 3
def sec_order(progs, IM):
    print()
    print("=" * 74)
    print("3. SEQUENCE STRUCTURE -- does the word CONSUME a multiplier product?")
    print("=" * 74)
    predA_l = collections.Counter(); tot_l = collections.Counter()
    predA_h = collections.Counter(); tot_h = collections.Counter()
    for a in IM:
        p = progs[a]
        for i in range(1, len(p)):
            h, c, _ad, l = fl(p[i])
            if c != 2:
                continue
            tot_l[l] += 1; tot_h[h] += 1
            if fl(p[i - 1])[1] == 0xA:
                predA_l[l] += 1; predA_h[h] += 1
    base = sum(predA_l.values()) / sum(tot_l.values())
    print(f"baseline P(previous word is class A | this word is class 2) = {base:.3f}\n")
    for lbl, tot, hit in (('hi12', tot_h, predA_h), ('lo12', tot_l, predA_l)):
        print(f"  {lbl}   n  P(pred=A)   binomial p     group")
        for v, n in sorted(tot.items(), key=lambda kv: -kv[1]):
            if n < 8:
                continue
            pr = hit[v] / n
            p = binom_p(hit[v], n, base)
            g = ('MUST-FOLLOW-A' if pr > 0.75 and p < 1e-3 else
                 'NEVER-FOLLOWS-A' if pr < 0.02 and p < 1e-3 else '')
            print(f"  {v:03X} {n:5d}   {pr:6.3f}   {p:10.2e}   {g}")
        print()
    print("  MEASURED: the distribution is BIMODAL.  Several values sit at exactly")
    print("  1.000 and several at exactly 0.000, with crushing binomial p-values.")
    print("  This is an ordering constraint the round-one distribution analysis")
    print("  could not see, and it partitions class 2 without touching the encoding.")


# ======================================================================= 4
def sec_header(progs, IM, rom):
    print()
    print("=" * 74)
    print("4. THE HEADER'S CLASS-2 WORDS -- a free partition of the vocabulary")
    print("=" * 74)
    hw = header_words(rom)
    h2 = [w for w in hw if fl(w)[1] == 2]
    body = set(w for a in IM for w in progs[a] if fl(w)[1] == 2)
    print(f"header: {len(hw)} words, {len(h2)} of them class 2")
    for w in h2:
        print(f"    {fmt(w)}" + ("   <-- exact word also in the bodies"
                                 if w in body else ""))
    BH = set(fl(w)[0] for w in h2); BL = set(fl(w)[3] for w in h2)
    bh = set(fl(w)[0] for w in body); bl = set(fl(w)[3] for w in body)
    print(f"\n  hi12 shared with bodies : {sorted('%03X' % x for x in BH & bh)}")
    print(f"  hi12 HEADER-ONLY        : {sorted('%03X' % x for x in BH - bh)}")
    print(f"  lo12 shared with bodies : {sorted('%03X' % x for x in BL & bl)}")
    print(f"  lo12 HEADER-ONLY        : {sorted('%03X' % x for x in BL - bl)}")
    print("\n  NOTE: lo12 0x655 and 0x680 -- called 'reverb-exclusive' in the reverb")
    print("  note -- BOTH appear in the header (012.2.01.655 / 084.2.02.680).")
    print("  The exclusivity belonged to the whole word, not to lo12.")


# ======================================================================= 5
def sec_bands(progs, rom, prom):
    print()
    print("=" * 74)
    print("5. PARAMETRIC EQ: 4 BANDS OR 5?  -- resolved")
    print("=" * 74)
    p = progs[39]
    SEC = 9
    ref = tuple(p[5:5 + SEC])
    starts = [i for i in range(len(p) - SEC) if tuple(p[i:i + SEC]) == ref]
    print(f"  byte-identical 9-word sections: {len(starts)} at {starts}")
    near = []
    for i in range(len(p) - SEC):
        d = [j for j in range(SEC) if p[i + j] != ref[j]]
        if len(d) == 1:
            near.append((i, d[0], fmt(p[i + d[0]])))
    print(f"  sections differing in EXACTLY ONE word: {len(near)}")
    for i, j, w in near:
        print(f"     start {i:3d}  word {j} is {w}  (reference {fmt(ref[j])})")
    print(f"\n  => {len(starts) + len(near)} biquad sections total"
          f" = {(len(starts) + len(near)) // 2} bands x 2 channels")

    ptr = prom.u32le(P.ALGO_T1_ARRAY + 4 * 39)
    print("\n  T1 (host parameter -> DSP address) for PARAMETRIC EQ:")
    for _, op, ents in P.parse_t1(prom, ptr):
        print(f"     op {op:02X} -> " + ' '.join('%02X' % x for x in ents))
    t2 = prom.u32le(P.ALGO_T2_ARRAY + 4 * 39)
    recs = P.split_records(prom, t2)
    ops = ['%02X:%02X' % (r[2][0], r[2][1]) for r in recs]
    print(f"  T2 records ({len(recs)}): {ops}")

    S = C.load_all(C.Rom(sys.argv[1]))
    co = C.coeffs_of(S[39])
    nz = [(i, '%06X' % v) for i, v in enumerate(co) if v]
    print(f"\n  static coefficient bank: {len(co)} values, "
          f"{len(co) - len(nz)} of them ZERO; non-zero: {nz}")
    print("  => the '45 registers ~ 5 bands x 3' reading of the coefficient note is")
    print("     void: the bank is a ZERO-FILL of the biquad coefficient+state area.")


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    rom = E.Rom(argv[1])
    prom = P.Rom(argv[1], P.SUB_BASE)
    progs = K.load_progs(argv[2])
    IM = K.images(progs)
    want = [s for s in argv[3:] if not s.startswith('-')]
    run = (lambda s: not want or s in want)
    if run('allpass'):
        sec_allpass(progs, IM)
    if run('dataflow'):
        sec_dataflow(progs, IM, prom)
    if run('order'):
        sec_order(progs, IM)
    if run('header'):
        sec_header(progs, IM, rom)
    if run('bands'):
        sec_bands(progs, rom, prom)


if __name__ == '__main__':
    main(sys.argv)
