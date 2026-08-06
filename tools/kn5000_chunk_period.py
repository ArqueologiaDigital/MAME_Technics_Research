#!/usr/bin/env python3
"""KN5000: audit detect_period() against the recordings it is measuring.

Felipe reported (2026-08-06) that on "Jazz Flute" the six semitones Db..Gb sound one
octave high while the rest of the keyboard is right. A chromatic sweep localised that band
to ONE multisample zone -- wave selector 0x5004, i.e. bank 1 (IC307) / page 1 / chunk 4 --
and showed the emulator's registers are perfectly chromatic across it. The octave therefore
cannot come from the pitch registers; the only other term in

    pitch_step = f_wanted * pitch_period_q16 / 48000

is the period detect_period() measured for the chunk. If that period is wrong by a factor
k, the note renders k times too high, and NOTHING else about the voice looks wrong.

This tool reads the waveform ROM directly, rebuilds the page directory with the SAME rules
as kn5000_tonegen.cpp's scan_wave_directories(), reimplements detect_period() faithfully,
and compares its answer against a reference estimate that does not share its failure mode.

The reference is deliberately a DIFFERENT estimator, not a tuned version of the same one:
the cumulative-mean-normalised difference function (YIN's d'), which is designed to reject
the octave errors plain autocorrelation makes. Where the two agree, detect_period is fine;
where they disagree by a clean factor of 2 (or 3), the chunk is a period-detection failure
and the audible symptom is a pitch error of exactly that ratio.

usage: kn5000_chunk_period.py <rom.ic307> [--page N] [--chunks a,b,c] [--all]
"""
import argparse
import sys

import numpy as np

PAGE_SIZE = 0x100000


def scan_page(rom, page):
    """Rebuild one page's directory exactly as scan_wave_directories() does."""
    base = page * PAGE_SIZE
    pg = rom[base:base + PAGE_SIZE]
    if len(pg) < PAGE_SIZE:
        return None

    def u16(o):
        return int(pg[o]) | (int(pg[o + 1]) << 8)

    p0 = u16(0)
    if p0 < 4 or p0 % 4:
        return None
    n = p0 // 4
    if n * 4 > PAGE_SIZE - 4:
        return None
    param, wave = [], []
    for i in range(n):
        param.append(u16(i * 4))
        wave.append(u16(i * 4 + 2))
        if i and param[i] < param[i - 1]:
            return None
        if param[i] < n * 4:
            return None
        if wave[i] * 16 >= PAGE_SIZE:
            return None
        if u16(param[i]) != wave[i]:
            return None
    srt = sorted(set(wave))
    out = []
    for i in range(n):
        j = np.searchsorted(srt, wave[i], side="right")
        end = PAGE_SIZE if j >= len(srt) else srt[j] * 16
        off = wave[i] * 16
        out.append((base + off, (end - off) // 2 if end > off else 0))
    return out


def pcm(rom, start, samples):
    return np.frombuffer(rom[start:start + samples * 2], dtype="<i2").astype(np.float64)


def detect_period(x):
    """Faithful reimplementation of kn5000_tonegen.cpp detect_period()."""
    samples = len(x)
    if samples < 32:
        return samples * 65536, None
    off = samples // 3
    W = min(samples - off, 4096)
    if W < 64:
        off, W = 0, min(samples, 4096)
    minlag, maxlag = 4, min(W // 2, 2048)
    if maxlag <= minlag:
        return samples * 65536, None
    w = x[off:off + W].copy()
    n = len(w)
    if n <= minlag * 2 + 4:
        return samples * 65536, None
    w -= w.mean()
    if (w * w).sum() < 1.0:
        return samples * 65536, None
    hi = min(maxlag, n - 1)
    r = np.full(hi + 1, -2.0)
    for lag in range(minlag, hi + 1):
        a, b = w[:n - lag], w[lag:]
        den = np.sqrt((a * a).sum() * (b * b).sum())
        r[lag] = (a * b).sum() / den if den > 1.0 else -2.0
    cross = 0
    for lag in range(minlag, hi + 1):
        if r[lag] < 0.0:
            cross = lag
            break
    if cross == 0:
        return (samples * 65536 if samples <= 2048 else 0), r
    peak = r[cross:hi + 1].max()

    def refine(lag):
        frac = 0.0
        if minlag < lag <= hi - 1:
            y0, y1, y2 = r[lag - 1], r[lag], r[lag + 1]
            den = y0 - 2 * y1 + y2
            if abs(den) > 1e-12:
                frac = 0.5 * (y0 - y2) / den
            frac = max(-0.5, min(0.5, frac))
        return int(max(1.0, lag + frac) * 65536 + 0.5)

    if peak >= 0.5:
        for lag in range(cross + 1, hi):
            if r[lag] >= 0.92 * peak and r[lag] >= r[lag - 1] and r[lag] >= r[lag + 1]:
                return refine(lag), r
        for lag in range(cross, hi + 1):
            if r[lag] >= 0.92 * peak:
                return refine(lag), r
    return (samples * 65536 if samples <= 2048 else 0), r


def yin_period(x, minlag=4, maxlag=2048, thresh=0.15):
    """Reference estimator: YIN's cumulative-mean-normalised difference function.

    Chosen because its whole purpose is to NOT make the octave error that a plain
    normalised autocorrelation makes, so agreement between the two is meaningful and
    disagreement localises the failure to the autocorrelation."""
    off = len(x) // 3
    W = min(len(x) - off, 4096)
    if W < 128:
        off, W = 0, min(len(x), 4096)
    w = x[off:off + W].astype(np.float64)
    w -= w.mean()
    if (w * w).sum() < 1.0:
        return 0.0
    hi = min(maxlag, W // 2 - 1)
    d = np.zeros(hi + 1)
    for lag in range(1, hi + 1):
        diff = w[:W - hi] - w[lag:lag + W - hi]
        d[lag] = (diff * diff).sum()
    dp = np.ones(hi + 1)
    run = 0.0
    for lag in range(1, hi + 1):
        run += d[lag]
        dp[lag] = d[lag] * lag / run if run > 0 else 1.0
    best = None
    for lag in range(minlag, hi):
        if dp[lag] < thresh and dp[lag] <= dp[lag + 1]:
            best = lag
            break
    if best is None:
        best = int(np.argmin(dp[minlag:hi]) + minlag)
    y0, y1, y2 = dp[best - 1], dp[best], dp[best + 1]
    den = y0 - 2 * y1 + y2
    frac = 0.5 * (y0 - y2) / den if abs(den) > 1e-12 else 0.0
    return best + max(-0.5, min(0.5, frac))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--chunks", default="")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()

    rom = open(a.rom, "rb").read()
    d = scan_page(rom, a.page)
    if d is None:
        sys.exit("page %d has no valid directory" % a.page)
    print("# %s page %d: %d chunks" % (a.rom, a.page, len(d)))
    if a.chunks:
        idx = [int(s) for s in a.chunks.split(",")]
    elif a.all:
        idx = range(len(d))
    else:
        idx = range(min(16, len(d)))

    print("%6s %10s %8s %10s %10s %8s  %s"
          % ("chunk", "start", "samples", "detect_P", "yin_P", "ratio", "verdict"))
    bad = 0
    for i in idx:
        start, ns = d[i]
        if ns < 32:
            continue
        x = pcm(rom, start, min(ns, 8192))
        pq, _ = detect_period(x)
        dp = pq / 65536.0
        yp = yin_period(x)
        if yp <= 0 or dp <= 0:
            v, ratio = "-", 0.0
        else:
            ratio = dp / yp
            if abs(ratio - 1.0) < 0.06:
                v = "agree"
            elif abs(ratio - 2.0) < 0.12:
                v = "*** detect = 2x yin (octave HIGH when played)"
            elif abs(ratio - 3.0) < 0.18:
                v = "*** detect = 3x yin"
            elif abs(ratio - 0.5) < 0.03:
                v = "*** detect = yin/2 (octave LOW)"
            else:
                v = "*** disagree %.2fx" % ratio
            if v != "agree":
                bad += 1
        print("%6d 0x%08X %8d %10.3f %10.3f %8.3f  %s" % (i, start, ns, dp, yp, ratio, v))
    print("# %d of %d disagree" % (bad, len(list(idx))))


if __name__ == "__main__":
    main()
