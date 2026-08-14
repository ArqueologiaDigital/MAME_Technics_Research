#!/usr/bin/env python3
"""LINE 2, final: true fundamental (not just the loudest bin) and the re-grade.

The loudest DFT bin can be a HARMONIC of a lower fundamental, which would make
"cycles per buffer" too large.  Here the fundamental is the SMALLEST bin f whose
harmonic comb (f, 2f, 3f ...) captures >= 95% of the chunk's AC energy -- the
standard definition -- and it is cross-checked against the circular
autocorrelation, which asks the independent question "does this buffer contain
an exact repeat at a lag shorter than its own length?".

Both must agree for a chunk to be graded, so a chunk whose spectrum is ambiguous
is reported as UNGRADED rather than silently counted.
"""
import sys, math
import numpy as np
from collections import Counter

sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools")
from kn5000_period_oracle import page_dir, detect_period, load_rom  # noqa: E402


def fundamental(x, floor_db=30.0, thresh=0.98):
    """Cycles per buffer = GCD of the bins that carry real energy.

    (The earlier "smallest f whose comb >= 95%" rule was degenerate: the comb at
    f = 1 is every bin, so it always returns 1.  The gcd rule asks the right
    question -- are the occupied bins all multiples of some f > 1? -- and is
    then verified by checking that comb(f) really holds >= `thresh` of the AC
    energy, so a chunk with scattered bins is reported UNGRADED, not f = 1.)
    """
    xz = x - x.mean()
    P = np.abs(np.fft.rfft(xz)) ** 2
    ac = P[1:]
    tot = ac.sum()
    if tot <= 0 or len(ac) < 2:
        return 0, 0.0
    cut = ac.max() * (10.0 ** (-floor_db / 10.0))
    bins = [i + 1 for i, v in enumerate(ac) if v >= cut]
    if not bins:
        return 0, 0.0
    f = bins[0]
    for b in bins[1:]:
        f = math.gcd(f, b)
    idx = np.arange(f, len(P), f)
    frac = float(P[idx].sum() / tot)
    return (f, frac) if frac >= thresh else (f, frac)


def circ_repeat(x, tol=0.98):
    """Smallest lag L < N with circular autocorrelation >= tol (exact repeat)."""
    xz = x - x.mean()
    n = len(xz)
    e = float((xz * xz).sum())
    if e <= 0:
        return n
    F = np.fft.rfft(xz, n)
    r = np.fft.irfft(F * np.conj(F), n)[:n] / e
    for L in range(1, n):
        if r[L] >= tol:
            return L
    return n


def main():
    rom = load_rom()
    pages = {p: page_dir(rom, p) for p in range(4)}
    d2 = pages[2]

    print("### Q. true fundamental of page-2 short chunks (95% harmonic-comb rule)")
    recs = []
    for i, (st, n) in enumerate(d2):
        if n > 256:
            continue
        x = np.frombuffer(rom, dtype="<i2", count=n, offset=st).astype(np.float64)
        f, frac = fundamental(x)
        L = circ_repeat(x)
        recs.append(dict(i=i, st=st, n=n, f=f, frac=frac, L=L))
    c = Counter(r["f"] for r in recs)
    print("  cycles-per-buffer histogram: " + ", ".join(f"{k}:{v}" for k, v in sorted(c.items())))
    ok = sum(1 for r in recs if r["f"] and abs(r["n"] / r["f"] - r["L"]) < 1e-9)
    cons = sum(1 for r in recs if r["f"] and r["L"] < r["n"])
    print(f"  spectral n/f == circular-autocorr repeat lag: {ok}/{len(recs)}")
    print(f"  chunks with an exact circular repeat shorter than the buffer: {cons}/{len(recs)}")

    print("\n### R. the re-grade of the 500 page-2 P=N fallbacks (fundamental rule)")
    correct = Counter(); wrong = Counter(); ungraded = 0
    for i, (st, n) in enumerate(d2):
        if n < 32:
            continue
        if detect_period(rom, st, n, gate=0.5) != (n << 16):
            continue
        x = np.frombuffer(rom, dtype="<i2", count=n, offset=st).astype(np.float64)
        f, frac = fundamental(x)
        L = circ_repeat(x)
        if f == 0 or frac < 0.98:
            ungraded += 1
            continue
        if f == 1 and L >= n:
            correct[(n, 1)] += 1
        elif f > 1:
            wrong[(n, f)] += 1
        else:
            ungraded += 1
    print(f"  CORRECT  (buffer is exactly ONE cycle -- P=N is the true period): "
          f"{sum(correct.values())}")
    print(f"  WRONG    (buffer holds f>1 exact cycles -- P=N is f x too long):  "
          f"{sum(wrong.values())}")
    print(f"  UNGRADED (spectrum not cleanly harmonic):                         {ungraded}")
    print("  wrong, by (buffer length, cycles f):")
    for (n, f), k in sorted(wrong.items(), key=lambda kv: -kv[1]):
        print(f"    len {n:5d}  f={f:3d}  {k:4d} chunks   true period {n/f:8.2f} "
              f"   playback error +{12*math.log2(f):5.1f} semitones")
    print("  correct, by (buffer length):")
    for (n, f), k in sorted(correct.items(), key=lambda kv: -kv[1]):
        print(f"    len {n:5d}  {k:4d} chunks")

    print("\n### S. NULL for the fundamental rule: matched-length excerpts of pages 0/1/3")
    rng = np.random.default_rng(20260814)
    lens = [r["n"] for r in recs]
    for pg in (0, 1, 3):
        src = [(st, n) for st, n in pages[pg] if n > 4096]
        f1 = 0; harm = 0; tot = 0
        for L0 in lens:
            st, N = src[rng.integers(len(src))]
            o = int(rng.integers(0, N - L0 - 1))
            x = np.frombuffer(rom, dtype="<i2", count=L0, offset=st + 2 * o).astype(np.float64)
            f, frac = fundamental(x)
            tot += 1
            if frac >= 0.98:
                harm += 1
                if f == 1:
                    f1 += 1
        print(f"  page {pg}: {harm}/{tot} ({100.0*harm/tot:.1f}%) excerpts are cleanly "
              f"harmonic (comb>=98%); of those {f1} have f=1")
    harm = sum(1 for r in recs if r["frac"] >= 0.9)
    f1 = sum(1 for r in recs if r["frac"] >= 0.9 and r["f"] == 1)
    print(f"  PAGE 2 short: {harm}/{len(recs)} ({100.0*harm/len(recs):.1f}%) cleanly "
          f"harmonic; of those {f1} have f=1")


if __name__ == "__main__":
    main()
