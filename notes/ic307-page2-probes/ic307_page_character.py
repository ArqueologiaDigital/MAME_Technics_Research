#!/usr/bin/env python3
"""LINE 2: what does IC307 page 2 contain, acoustically?

Characterises every chunk of all four IC307 pages and compares page 2 against
pages 0/1/3 as controls.  Read-only: touches nothing but the ROM.

Hypothesis under test:
  H1  page 2 is one-shot / percussive / aperiodic material, so detect_period()'s
      "P = N" fallback is the CORRECT answer for it.
  H2  page 2 is ordinary pitched PCM and the detector is failing on it.
  H3  page 2 is not audio at all (table / compressed data / padding).

Discriminators computed per chunk: length, RMS, peak, DC, zero-crossing rate,
spectral centroid, spectral flatness, dominant DFT bin, wrap discontinuity,
normalised autocorrelation peak (same window rules as detect_period), byte
entropy, 0xFF/0x00 byte fractions.

NULL / control: the same statistics on RANDOM excerpts of matched length taken
from pages 0/1/3.  If page 2's short chunks are indistinguishable from random
excerpts of ordinary PCM, the "single-cycle wavetable" reading is refuted.

    python3 ic307_page_character.py            # full run
    python3 ic307_page_character.py --csv out.csv
"""
import argparse, math, os, struct, sys
import numpy as np

sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools")
from kn5000_period_oracle import page_dir, detect_period, load_rom  # noqa: E402

PAGE_SIZE = 0x100000


def chunk_samples(rom, start, n):
    return np.frombuffer(rom, dtype="<i2", count=n, offset=start).astype(np.float64)


def metrics(rom, start, n):
    x = chunk_samples(rom, start, n)
    b = np.frombuffer(rom, dtype=np.uint8, count=2 * n, offset=start)
    dc = float(x.mean())
    xz = x - dc
    rms = float(np.sqrt((xz * xz).mean()))
    peak = float(np.abs(x).max())
    zc = int(np.count_nonzero(np.diff(np.signbit(xz))))
    zcr = zc / max(1, n - 1)
    # wrap discontinuity: |x[0]-x[N-1]| against the chunk's own typical step
    d = np.abs(np.diff(x))
    mstep = float(np.median(d)) if n > 2 else 0.0
    wrap = abs(float(x[0] - x[-1]))
    wrap_ratio = wrap / mstep if mstep > 0 else float("inf")
    # spectrum on the whole chunk, rectangular window (single-cycle waves are
    # exactly periodic over the chunk, so no window: it would smear bin 1)
    X = np.abs(np.fft.rfft(xz))
    if len(X) > 1:
        f = np.arange(len(X)) / (2.0 * (len(X) - 1))   # fraction of Nyquist
        s = X.sum()
        cent = float((f * X).sum() / s) if s > 0 else 0.0
        Xp = X[1:]
        pos = Xp[Xp > 0]
        flat = float(np.exp(np.log(pos).mean()) / Xp.mean()) if len(pos) > 4 and Xp.mean() > 0 else float("nan")
        fbin = int(np.argmax(Xp)) + 1 if len(Xp) else 0
        fbin_frac = float(Xp.max() / Xp.sum()) if Xp.sum() > 0 else 0.0
    else:
        cent, flat, fbin, fbin_frac = 0.0, float("nan"), 0, 0.0
    # byte entropy
    h = np.bincount(b, minlength=256).astype(np.float64)
    p = h[h > 0] / h.sum()
    ent = float(-(p * np.log2(p)).sum())
    ff = float(h[255] / h.sum())
    z00 = float(h[0] / h.sum())
    # autocorrelation peak, same window rules as detect_period
    r_peak, r_lag = autocorr_peak(x, n)
    return dict(n=n, rms=rms, peak=peak, dc=dc, zcr=zcr, wrap=wrap,
                wrap_ratio=wrap_ratio, cent=cent, flat=flat, fbin=fbin,
                fbin_frac=fbin_frac, ent=ent, ff=ff, z00=z00,
                r_peak=r_peak, r_lag=r_lag)


def autocorr_peak(x, n):
    """Max normalised autocorrelation after the first negative crossing.

    Same window selection, DC removal and normalisation as detect_period, so
    r_peak is exactly the quantity the 0.5 gate is applied to.
    """
    if n < 32:
        return float("nan"), 0
    off = n // 3
    W = min(n - off, 4096)
    if W < 64:
        off, W = 0, min(n, 4096)
    minlag, maxlag = 4, min(W // 2, 2048)
    if maxlag <= minlag:
        return float("nan"), 0
    w = x[off:off + W].copy()
    m = len(w)
    if m <= minlag * 2 + 4:
        return float("nan"), 0
    w -= w.mean()
    if (w * w).sum() < 1.0:
        return float("nan"), 0
    hi = min(maxlag, m - 1)
    sq = np.concatenate(([0.0], np.cumsum(w * w)))
    r = np.full(hi + 1, -2.0)
    for lag in range(minlag, hi + 1):
        k = m - lag
        c = float(np.dot(w[:k], w[lag:lag + k]))
        e0 = sq[k] - sq[0]
        e1 = sq[lag + k] - sq[lag]
        den = math.sqrt(e0 * e1)
        r[lag] = (c / den) if den > 1.0 else -2.0
    cross = 0
    for lag in range(minlag, hi + 1):
        if r[lag] < 0.0:
            cross = lag
            break
    if cross == 0:
        return float("nan"), 0
    seg = r[cross:hi + 1]
    return float(seg.max()), int(np.argmax(seg)) + cross


def q(vals, name, fmt="{:.3f}"):
    v = np.asarray([x for x in vals if not (isinstance(x, float) and math.isnan(x))], dtype=float)
    if not len(v):
        return f"{name:14s} n=0"
    p = np.percentile(v, [10, 25, 50, 75, 90])
    return (f"{name:14s} n={len(v):4d}  med " + fmt.format(p[2]) +
            "  [p10 " + fmt.format(p[0]) + " p25 " + fmt.format(p[1]) +
            " p75 " + fmt.format(p[3]) + " p90 " + fmt.format(p[4]) + "]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="")
    ap.add_argument("--seed", type=int, default=20260814)
    args = ap.parse_args()
    rom = load_rom()
    pages = {p: page_dir(rom, p) for p in range(4)}
    print("IC307 page directories: " + ", ".join(f"p{p}={len(v)}" for p, v in pages.items()))

    rows = []
    for pg, lst in pages.items():
        for i, (st, ns) in enumerate(lst):
            if ns <= 0 or st + 2 * ns > len(rom):
                continue
            m = metrics(rom, st, ns)
            m.update(page=pg, idx=i, start=st)
            if ns >= 32:
                pc = detect_period(rom, st, ns, gate=0.5)
                m["period"] = pc
                m["fallback"] = int(pc == (ns << 16))
                m["nozero"] = int(pc == 0)
            else:
                m["period"] = ns << 16
                m["fallback"] = -1
                m["nozero"] = 0
            rows.append(m)

    if args.csv:
        import csv
        keys = list(rows[0].keys())
        with open(args.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            for r in rows:
                w.writerow(r)
        print(f"wrote {args.csv} ({len(rows)} rows)")

    # ---------------- per-page distributions -------------------------------
    for pg in range(4):
        R = [r for r in rows if r["page"] == pg]
        print(f"\n=== PAGE {pg}: {len(R)} chunks, {sum(r['n'] for r in R)} samples ===")
        print("  " + q([r["n"] for r in R], "len(samples)", "{:.0f}"))
        print("  " + q([r["rms"] for r in R], "rms", "{:.0f}"))
        print("  " + q([r["peak"] for r in R], "peak", "{:.0f}"))
        print("  " + q([r["dc"] for r in R], "dc", "{:.0f}"))
        print("  " + q([r["zcr"] for r in R], "zcr", "{:.4f}"))
        print("  " + q([r["cent"] for r in R], "centroid/Nyq", "{:.4f}"))
        print("  " + q([r["flat"] for r in R], "flatness", "{:.4f}"))
        print("  " + q([r["ent"] for r in R], "byte entropy", "{:.3f}"))
        print("  " + q([r["r_peak"] for r in R], "autocorr pk", "{:.3f}"))
        print("  " + q([r["wrap_ratio"] for r in R], "wrapratio", "{:.2f}"))
        sil = sum(1 for r in R if r["peak"] < 256)
        allff = sum(1 for r in R if r["ff"] > 0.99)
        fb = sum(1 for r in R if r["fallback"] == 1)
        nz = sum(1 for r in R if r["nozero"] == 1)
        b1 = sum(1 for r in R if r["fbin"] == 1)
        gate = sum(1 for r in R if not math.isnan(r["r_peak"]) and r["r_peak"] >= 0.5)
        print(f"  near-silent(peak<256) {sil}   all-0xFF {allff}   "
              f"P=N fallback {fb}   period=0 {nz}   autocorr>=0.5 {gate}   dominant bin==1 {b1}")

    # -------- page 2 split into short (<=256) and long populations ---------
    P2 = [r for r in rows if r["page"] == 2]
    short = [r for r in P2 if r["n"] <= 256]
    long_ = [r for r in P2 if r["n"] > 256]
    print(f"\n=== PAGE 2 BIMODALITY: {len(short)} chunks <=256 samples "
          f"({sum(r['n'] for r in short)} samples), {len(long_)} chunks >256 "
          f"({sum(r['n'] for r in long_)} samples) ===")
    for lab, S in (("short<=256", short), ("long >256", long_)):
        fb = sum(1 for r in S if r["fallback"] == 1)
        b1 = sum(1 for r in S if r["fbin"] == 1)
        print(f"  {lab}: P=N fallback {fb}/{len(S)}  dominant-bin==1 {b1}/{len(S)}  "
              f"med rms {np.median([r['rms'] for r in S]):.0f}  "
              f"med zcr {np.median([r['zcr'] for r in S]):.4f}  "
              f"med autocorr pk {np.nanmedian([r['r_peak'] for r in S]):.3f}  "
              f"med wrapratio {np.median([r['wrap_ratio'] for r in S]):.2f}")

    # -------- THE NULL: random excerpts of matched length from p0/p1/p3 ----
    rng = np.random.default_rng(args.seed)
    lens = [r["n"] for r in short]
    print("\n=== NULL CONTROL: random excerpts of the SAME lengths cut from pages 0/1/3 ===")
    print("  (if page-2 short chunks are just PCM cut at arbitrary points, these match)")
    for pg in (0, 1, 3):
        src = [(r["start"], r["n"]) for r in rows if r["page"] == pg and r["n"] > 4096]
        got = []
        for L in lens:
            st, N = src[rng.integers(len(src))]
            o = int(rng.integers(0, N - L - 1))
            got.append(metrics(rom, st + 2 * o, L))
        b1 = sum(1 for r in got if r["fbin"] == 1)
        print(f"  page {pg} excerpts n={len(got)}: dominant-bin==1 {b1} "
              f"({100.0*b1/len(got):.1f}%)  med wrapratio "
              f"{np.median([r['wrap_ratio'] for r in got]):.2f}  "
              f"med zcr {np.median([r['zcr'] for r in got]):.4f}  "
              f"med rms {np.median([r['rms'] for r in got]):.0f}")
    b1 = sum(1 for r in short if r["fbin"] == 1)
    print(f"  PAGE 2 short chunks n={len(short)}: dominant-bin==1 {b1} "
          f"({100.0*b1/len(short):.1f}%)  med wrapratio "
          f"{np.median([r['wrap_ratio'] for r in short]):.2f}  "
          f"med zcr {np.median([r['zcr'] for r in short]):.4f}  "
          f"med rms {np.median([r['rms'] for r in short]):.0f}")

    # -------- dominant-bin histogram for page-2 short chunks ---------------
    from collections import Counter
    c = Counter(r["fbin"] for r in short)
    print("  page-2 short dominant-bin histogram (top 10): " +
          ", ".join(f"bin{k}:{v}" for k, v in c.most_common(10)))


if __name__ == "__main__":
    main()
