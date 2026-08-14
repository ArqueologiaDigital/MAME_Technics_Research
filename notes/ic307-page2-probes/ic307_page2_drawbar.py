#!/usr/bin/env python3
"""LINE 2, part 3: are page 2's short chunks organ drawbar footages?

Prediction (falsifiable): if page 2's short chunks are drawbar footage waves,
then each chunk is a near-pure sinusoid whose number of cycles per buffer is one
of the Hammond footage ratios {1,2,3,4,6,8,10,12,16} relative to the buffer, the
buffer is DC-free, and the residual after subtracting the best single sinusoid
is small.  If instead they are ordinary sampled instrument single cycles, the
residual will be large (many harmonics) and the cycle counts will be 1 only.

REFUTATION: cycle counts spread over arbitrary integers, or sinusoid residual
comparable to the signal, kills the drawbar reading.
"""
import sys, math
import numpy as np
from collections import Counter

sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools")
from kn5000_period_oracle import page_dir, load_rom  # noqa: E402


def harmonics(x):
    xz = x - x.mean()
    X = np.abs(np.fft.rfft(xz))
    P = X ** 2
    tot = P[1:].sum()
    if tot <= 0:
        return None
    ks = np.argsort(P[1:])[::-1] + 1
    return P, tot, ks


def main():
    rom = load_rom()
    d2 = page_dir(rom, 2)
    short = [(i, st, n) for i, (st, n) in enumerate(d2) if n <= 256]
    print(f"page 2: {len(d2)} chunks, {len(short)} of them <= 256 samples\n")

    print("### F. purity: energy in the single loudest bin, and sinusoid residual")
    rows = []
    for i, st, n in short:
        x = np.frombuffer(rom, dtype="<i2", count=n, offset=st).astype(np.float64)
        h = harmonics(x)
        if h is None:
            continue
        P, tot, ks = h
        k = int(ks[0])
        frac1 = P[k] / tot
        frac2 = (P[ks[0]] + P[ks[1]]) / tot if len(ks) > 1 else frac1
        # best-fit single sinusoid at bin k, residual RMS / signal RMS
        t = np.arange(n)
        c = np.cos(2 * np.pi * k * t / n)
        s = np.sin(2 * np.pi * k * t / n)
        xz = x - x.mean()
        a = 2 * (xz * c).sum() / n
        b = 2 * (xz * s).sum() / n
        res = xz - (a * c + b * s)
        rr = math.sqrt((res ** 2).mean()) / max(1e-9, math.sqrt((xz ** 2).mean()))
        rows.append(dict(i=i, n=n, k=k, frac1=frac1, frac2=frac2, resid=rr,
                         peak=float(np.abs(x).max())))

    for k in sorted({r["k"] for r in rows}):
        S = [r for r in rows if r["k"] == k]
        print(f"  cycles/buffer = {k:3d}: {len(S):4d} chunks   "
              f"med loudest-bin energy frac {np.median([r['frac1'] for r in S]):.4f}   "
              f"med sinusoid residual {np.median([r['resid'] for r in S]):.4f}   "
              f"lens {sorted(Counter(r['n'] for r in S).items())}")

    print("\n### G. cycles-per-buffer as a FOOTAGE ratio")
    HAMMOND = {1: "16'", 2: "8'", 3: "5 1/3'", 4: "4'", 6: "2 2/3'", 8: "2'",
               10: "1 3/5'", 12: "1 1/3'", 16: "1'"}
    c = Counter(r["k"] for r in rows)
    tot = sum(c.values())
    inh = sum(v for k, v in c.items() if k in HAMMOND)
    for k, v in sorted(c.items()):
        print(f"   k={k:3d}  {v:4d} chunks  {100.0*v/tot:5.1f}%   "
              f"{'HAMMOND ' + HAMMOND[k] if k in HAMMOND else '(not a drawbar ratio)'}")
    print(f"  -> {inh}/{tot} ({100.0*inh/tot:.1f}%) of short page-2 chunks have a "
          f"cycle count in the Hammond drawbar series")
    print("  NULL for that: the drawbar series covers 9 of the 1..128 integers = 7.0%; "
          "arbitrary excerpts would land there ~7% of the time")

    print("\n### H. layout: are the short chunks a contiguous region of page 2?")
    runs = []
    cur = None
    for i, (st, n) in enumerate(d2):
        sh = (n <= 256)
        if cur is None or cur[0] != sh:
            if cur:
                runs.append(cur)
            cur = [sh, i, i]
        else:
            cur[2] = i
    runs.append(cur)
    for sh, a, b in runs:
        st = d2[a][0]
        en = d2[b][0] + 2 * d2[b][1]
        print(f"  entries {a:4d}-{b:4d} ({b-a+1:4d})  "
              f"{'SHORT<=256' if sh else 'long >256 '}  rom 0x{st:06X}-0x{en:06X}")

    print("\n### I. shape of the first few short chunks (first 16 samples each)")
    for i, st, n in short[:6]:
        x = np.frombuffer(rom, dtype="<i2", count=n, offset=st)
        print(f"  entry {i:4d} n={n:3d} @0x{st:06X}: " +
              " ".join(f"{v:6d}" for v in x[:12]) + " ...")

    print("\n### J. page-2 chunk 0 (256 samples) vs a perfect sine, like page 0 chunk 0")
    for pg in (0, 2):
        st, n = page_dir(rom, pg)[0]
        x = np.frombuffer(rom, dtype="<i2", count=n, offset=st).astype(np.float64)
        ref = 32767.0 * np.sin(2 * np.pi * np.arange(n) / n)
        best = min(np.abs(np.roll(ref, k) - x).mean() for k in range(n))
        print(f"  page {pg} chunk 0: n={n} peak {np.abs(x).max():.0f} "
              f"mean-abs-err vs best-aligned full-scale sine = {best:.2f} LSB")

    print("\n### K. duplicate content among short chunks")
    seen = {}
    for i, st, n in short:
        b = bytes(rom[st:st + 2 * n])
        seen.setdefault(b, []).append(i)
    dups = {k: v for k, v in seen.items() if len(v) > 1}
    print(f"  {len(seen)} distinct byte-strings among {len(short)} short chunks; "
          f"{len(dups)} appear more than once "
          f"(largest group {max((len(v) for v in seen.values()), default=0)})")


if __name__ == "__main__":
    main()
