#!/usr/bin/env python3
"""LINE 2 follow-up: is page 2 synthetic single-cycle wavetable data, and is the
P=N fallback the correct answer for it?

Adds the discriminators the first pass showed were needed:
  * spectral FLATNESS and harmonic-comb energy fraction, with a matched-length
    NULL cut from pages 0/1/3 (the first pass showed "dominant bin == 1" alone
    does NOT discriminate: the null hits 23-31%).
  * exact-zero DC count (a recorded sample essentially never has mean exactly 0)
  * cross-tab of the P=N fallback against chunk length and dominant bin, which
    is what decides "correct answer" vs "detector defect".
"""
import math, os, sys
import numpy as np
from collections import Counter

sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools")
from kn5000_period_oracle import page_dir, detect_period, load_rom  # noqa: E402


def spec(x):
    xz = x - x.mean()
    X = np.abs(np.fft.rfft(xz))
    Xp = X[1:]
    if Xp.sum() <= 0 or len(Xp) < 4:
        return dict(flat=float("nan"), fbin=0, comb=float("nan"), top=float("nan"))
    pos = Xp[Xp > 0]
    flat = float(np.exp(np.log(pos).mean()) / Xp.mean()) if len(pos) > 3 else float("nan")
    fbin = int(np.argmax(Xp)) + 1
    P = Xp ** 2
    idx = np.arange(fbin, len(Xp) + 1, fbin) - 1
    comb = float(P[idx].sum() / P.sum())
    return dict(flat=flat, fbin=fbin, comb=comb, top=float(P.max() / P.sum()))


def main():
    rom = load_rom()
    pages = {p: page_dir(rom, p) for p in range(4)}
    rows = []
    for pg, lst in pages.items():
        for i, (st, ns) in enumerate(lst):
            if ns <= 0:
                continue
            x = np.frombuffer(rom, dtype="<i2", count=ns, offset=st).astype(np.float64)
            r = dict(page=pg, idx=i, start=st, n=ns, mean=float(x.mean()),
                     rms=float(np.sqrt(((x - x.mean()) ** 2).mean())))
            r.update(spec(x))
            if ns >= 32:
                p = detect_period(rom, st, ns, gate=0.5)
                r["fallback"] = int(p == (ns << 16))
                r["period"] = p / 65536.0
            else:
                r["fallback"] = -1
                r["period"] = float(ns)
            rows.append(r)

    P2 = [r for r in rows if r["page"] == 2]
    short = [r for r in P2 if r["n"] <= 256]
    long_ = [r for r in P2 if r["n"] > 256]

    print("### A. exact-zero DC mean (a recorded 16-bit sample basically never has mean == 0)")
    for pg in range(4):
        R = [r for r in rows if r["page"] == pg]
        z = sum(1 for r in R if r["mean"] == 0.0)
        print(f"  page {pg}: {z:4d}/{len(R):4d} chunks have mean EXACTLY 0.0 "
              f"({100.0*z/len(R):.1f}%)")
    z = sum(1 for r in short if r["mean"] == 0.0)
    print(f"  page 2 short(<=256): {z}/{len(short)} ({100.0*z/len(short):.1f}%);  "
          f"page 2 long(>256): {sum(1 for r in long_ if r['mean']==0.0)}/{len(long_)}")

    print("\n### B. spectral flatness + harmonic-comb fraction, with matched-length NULL")
    rng = np.random.default_rng(20260814)
    lens = [r["n"] for r in short]
    def summarise(lab, S):
        fl = np.array([r["flat"] for r in S if not math.isnan(r["flat"])])
        cb = np.array([r["comb"] for r in S if not math.isnan(r["comb"])])
        tp = np.array([r["top"] for r in S if not math.isnan(r["top"])])
        print(f"  {lab:28s} n={len(fl):4d}  med flatness {np.median(fl):.5f}  "
              f"med comb-frac {np.median(cb):.4f}  med top-bin-frac {np.median(tp):.4f}  "
              f"flatness<0.01: {100.0*np.mean(fl<0.01):.1f}%")
    summarise("PAGE 2 short (<=256)", short)
    summarise("PAGE 2 long  (>256)", long_)
    for pg in (0, 1, 3):
        src = [(r["start"], r["n"]) for r in rows if r["page"] == pg and r["n"] > 4096]
        got = []
        for L in lens:
            st, N = src[rng.integers(len(src))]
            o = int(rng.integers(0, N - L - 1))
            x = np.frombuffer(rom, dtype="<i2", count=L, offset=st + 2 * o).astype(np.float64)
            got.append(spec(x))
        summarise(f"NULL: page {pg} excerpts", got)
        c = Counter(r["fbin"] for r in got)
        print(f"      dominant-bin histogram (top 8): " +
              ", ".join(f"{k}:{v}" for k, v in c.most_common(8)))
    c = Counter(r["fbin"] for r in short)
    print("      PAGE 2 short dominant-bin histogram: " +
          ", ".join(f"{k}:{v}" for k, v in c.most_common(12)))

    print("\n### C. cross-tab: P=N fallback vs length and vs cycles-per-chunk (dominant bin)")
    tab = {}
    for r in P2:
        if r["fallback"] < 0:
            continue
        key = (r["n"], r["fbin"])
        t = tab.setdefault(key, [0, 0])
        t[0] += 1
        t[1] += r["fallback"]
    print("   len  bin  chunks  fallback   implied period = len/bin   detector maxlag")
    for (L, b), (n, f) in sorted(tab.items()):
        if n < 3:
            continue
        off = L // 3
        W = min(L - off, 4096)
        if W < 64:
            W = min(L, 4096)
        maxlag = min(W // 2, 2048)
        print(f"  {L:5d} {b:4d} {n:7d} {f:9d}   {L/b:10.1f}   {maxlag:6d}"
              + ("   <-- period UNREACHABLE (>maxlag)" if L / b > maxlag else ""))

    print("\n### D. is the fallback value RIGHT? compare P=N against len/dominant-bin")
    ok = bad = 0
    for r in P2:
        if r["fallback"] != 1 or r["fbin"] == 0:
            continue
        implied = r["n"] / r["fbin"]
        if abs(implied - r["n"]) < 0.02 * r["n"]:
            ok += 1
        else:
            bad += 1
    print(f"  page 2 fallbacks whose spectrum says the chunk IS one cycle: {ok}")
    print(f"  page 2 fallbacks whose spectrum says it holds >1 cycle:      {bad}")

    print("\n### E. the same question for pages 0/1 fallbacks (the control)")
    for pg in (0, 1):
        R = [r for r in rows if r["page"] == pg and r["fallback"] == 1]
        ok = sum(1 for r in R if r["fbin"] and abs(r["n"] / r["fbin"] - r["n"]) < 0.02 * r["n"])
        print(f"  page {pg}: {len(R)} fallbacks, {ok} of them are single-cycle by spectrum, "
              f"median len {np.median([r['n'] for r in R]):.0f}")


if __name__ == "__main__":
    main()
