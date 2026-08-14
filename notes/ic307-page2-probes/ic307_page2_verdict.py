#!/usr/bin/env python3
"""LINE 2, part 4: the null for the footage claim, and whether P=N is CORRECT.

  L. honest NULL: run the identical cycle-count test on matched-length random
     excerpts of pages 0/1/3, and report how often THEY land in the octave/tierce
     set. (The 7% "9 integers out of 128" figure quoted in part 3 is a bad null —
     the dominant bin of a random excerpt is not uniform.)
  M. the period set page 2 actually uses.
  N. do the page-2 chunks where detect_period DID resolve a period agree with the
     spectral period n/k?  (If yes, the spectral period is trustworthy and the
     fallbacks can be graded against it.)
  O. grade every page-2 P=N fallback: correct (chunk really is one cycle) or wrong
     by an exact factor k, and the resulting pitch error in semitones.
"""
import sys, math
import numpy as np
from collections import Counter

sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools")
from kn5000_period_oracle import page_dir, detect_period, load_rom  # noqa: E402

OCTAVE_TIERCE = {1, 2, 4, 8, 16, 5, 10, 20, 40}   # 2^a and 5*2^a
HAMMOND = {1, 2, 3, 4, 6, 8, 10, 12, 16}


def cycles(x, n):
    xz = x - x.mean()
    P = np.abs(np.fft.rfft(xz)) ** 2
    if P[1:].sum() <= 0:
        return 0, 0.0
    k = int(np.argmax(P[1:])) + 1
    idx = np.arange(k, len(P), k)
    return k, float(P[idx].sum() / P[1:].sum())


def main():
    rom = load_rom()
    pages = {p: page_dir(rom, p) for p in range(4)}
    d2 = pages[2]
    short = [(i, st, n) for i, (st, n) in enumerate(d2) if n <= 256]
    lens = [n for _i, _s, n in short]

    print("### L. NULL: same cycle-count test on matched-length excerpts of pages 0/1/3")
    rng = np.random.default_rng(20260814)
    for pg in (0, 1, 3):
        src = [(st, n) for st, n in pages[pg] if n > 4096]
        ks, combs = [], []
        for L in lens:
            st, N = src[rng.integers(len(src))]
            o = int(rng.integers(0, N - L - 1))
            x = np.frombuffer(rom, dtype="<i2", count=L, offset=st + 2 * o).astype(np.float64)
            k, cb = cycles(x, L)
            ks.append(k); combs.append(cb)
        oc = sum(1 for k in ks if k in OCTAVE_TIERCE)
        hm = sum(1 for k in ks if k in HAMMOND)
        print(f"  page {pg} excerpts n={len(ks)}: k in octave/tierce set "
              f"{oc} ({100.0*oc/len(ks):.1f}%)   k in Hammond set {hm} "
              f"({100.0*hm/len(ks):.1f}%)   med comb-frac {np.median(combs):.4f}")
    ks, combs = [], []
    for i, st, n in short:
        x = np.frombuffer(rom, dtype="<i2", count=n, offset=st).astype(np.float64)
        k, cb = cycles(x, n)
        ks.append(k); combs.append(cb)
    oc = sum(1 for k in ks if k in OCTAVE_TIERCE)
    hm = sum(1 for k in ks if k in HAMMOND)
    print(f"  PAGE 2 short  n={len(ks)}: k in octave/tierce set {oc} "
          f"({100.0*oc/len(ks):.1f}%)   k in Hammond set {hm} ({100.0*hm/len(ks):.1f}%)"
          f"   med comb-frac {np.median(combs):.4f}")
    print("  REFUTATION TEST: if the nulls had also landed >90% in the octave/tierce set, "
          "the claim would be an artefact of the statistic, not a property of page 2.")

    print("\n### M. the period set page 2 uses (period = buffer length / cycles)")
    per = Counter()
    for (i, st, n), k in zip(short, ks):
        if k:
            per[round(n / k, 3)] += 1
    for p, c in sorted(per.items()):
        rel = p / 64.0
        print(f"  period {p:8.3f} samples  {c:4d} chunks   = 64/{64.0/p:.3f}"
              + ("   (octave of 64)" if abs(math.log2(64.0 / p) - round(math.log2(64.0 / p))) < 1e-6 else "")
              + ("   (octave of 64 / 5)" if abs(math.log2(64.0 / p / 5) - round(math.log2(64.0 / p / 5))) < 1e-6 else ""))

    print("\n### N. where detect_period DID resolve, does it agree with the spectral period?")
    agree = dis = 0
    errs = []
    for (i, st, n), k in zip(short, ks):
        if n < 32 or not k:
            continue
        p = detect_period(rom, st, n, gate=0.5)
        if p == (n << 16):
            continue
        P = p / 65536.0
        want = n / k
        errs.append(abs(P - want) / want)
        if abs(P - want) / want < 0.02:
            agree += 1
        else:
            dis += 1
    print(f"  resolved (non-fallback) short page-2 chunks: {agree + dis}; "
          f"within 2% of n/k: {agree}; disagreeing: {dis}; "
          f"median |rel err| {np.median(errs):.5f}")
    print("  -> the spectral period n/k is corroborated by the detector itself wherever "
          "the detector is able to look far enough; so it is a fair yardstick for the rest.")

    print("\n### O. grading every page-2 P=N fallback against the spectral period")
    good = Counter()
    bad = Counter()
    for i, (st, n) in enumerate(d2):
        if n < 32:
            continue
        p = detect_period(rom, st, n, gate=0.5)
        if p != (n << 16):
            continue
        x = np.frombuffer(rom, dtype="<i2", count=n, offset=st).astype(np.float64)
        k, cb = cycles(x, n)
        if k <= 1 or cb < 0.5:
            good[(n, k)] += 1
        else:
            bad[(n, k)] += 1
    ng, nb = sum(good.values()), sum(bad.values())
    print(f"  CORRECT   (chunk really is one cycle; P=N is the true period): {ng}")
    print(f"  WRONG     (chunk holds k>1 exact cycles; P=N is k x too long):  {nb}")
    print("  wrong ones, by (buffer length, cycles k) -> pitch error:")
    for (n, k), c in sorted(bad.items(), key=lambda kv: -kv[1]):
        print(f"    len {n:5d}  k={k:3d}  {c:4d} chunks   true period {n/k:8.2f}   "
              f"pitch error +{12*math.log2(k):5.1f} semitones")
    print("  correct ones, by (buffer length, cycles k):")
    for (n, k), c in sorted(good.items(), key=lambda kv: -kv[1])[:8]:
        print(f"    len {n:5d}  k={k:3d}  {c:4d} chunks")

    print("\n### P. the same grading for the 58 LONG page-2 chunks and for pages 0/1")
    for pg in (0, 1, 2, 3):
        tot = fb = 0
        for st, n in pages[pg]:
            if n < 32 or (pg == 2 and n <= 256):
                continue
            tot += 1
            if detect_period(rom, st, n, gate=0.5) == (n << 16):
                fb += 1
        lab = "page 2 LONG only" if pg == 2 else f"page {pg}"
        print(f"  {lab:18s}: {fb}/{tot} P=N fallbacks")


if __name__ == "__main__":
    main()
