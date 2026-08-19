#!/usr/bin/env python3
"""Recover the per-recording ROOT PITCH of IC307 chunks from the PCM alone,
and test it against the firmware-derived constant C.

ROOT_units = NAT + C    where NAT = -3072*log2(P_samples)   (256 units/semitone)
If the chip needed no per-recording pitch datum, ROOT would be a single global
constant across every chunk.  Measure how constant it is, and what the residue is.
"""
import re, sys, math
import numpy as np

ROM = "/home/fsanches/compartilhado/kn5000_original_roms/kn5000/kn5000_waveform_rom.ic307"
HXX = "/home/fsanches/compartilhado/kn7000_mame/src/mame/matsushita/kn5000_pitch_trim.hxx"
PAGE = 0x100000

rom = open(ROM, "rb").read()

def u16(b, o): return b[o] | (b[o+1] << 8)

def scan_page(page):
    base = page * PAGE
    pg = rom[base:base+PAGE]
    p0 = u16(pg, 0)
    if p0 < 4 or p0 % 4: return None
    n = p0 // 4
    param, wave = [], []
    for i in range(n):
        param.append(u16(pg, i*4)); wave.append(u16(pg, i*4+2))
        if i and param[i] < param[i-1]: return None
        if param[i] < n*4: return None
        if wave[i]*16 >= PAGE: return None
        if u16(pg, param[i]) != wave[i]: return None
    srt = sorted(set(wave))
    out = []
    for i in range(n):
        j = np.searchsorted(srt, wave[i], side="right")
        end = PAGE if j >= len(srt) else srt[j]*16
        off = wave[i]*16
        out.append((base+off, (end-off)//2 if end > off else 0, param[i]))
    # record extents: param_ptr[i] .. next strictly greater param_ptr
    sp = sorted(set(param))
    rec = []
    for i in range(n):
        j = np.searchsorted(sp, param[i], side="right")
        rend = sp[j] if j < len(sp) else None
        rec.append((base+param[i], (rend - param[i]) if rend else 0))
    return out, rec

def yin_period(x, minlag=3, maxlag=3000, thresh=0.12):
    """FFT-accelerated YIN cumulative-mean-normalised difference function."""
    N = len(x)
    off = N // 3
    W = min(N - off, 8192)
    if W < 256:
        off, W = 0, min(N, 8192)
    w = x[off:off+W].astype(np.float64)
    w -= w.mean()
    e = (w*w).sum()
    if e < 1.0 or W < 128: return 0.0
    hi = min(maxlag, W//2 - 2)
    if hi < minlag + 2: return 0.0
    M = W - hi                      # fixed comparison length
    # d[lag] = sum_{i<M} (w[i]-w[i+lag])^2 = E0 + Elag - 2*corr[lag]
    nfft = 1 << int(math.ceil(math.log2(W + M)))
    F = np.fft.rfft(w, nfft)
    G = np.fft.rfft(w[:M], nfft)
    corr = np.fft.irfft(F * np.conj(G), nfft)[:hi+1]
    cs = np.concatenate(([0.0], np.cumsum(w*w)))
    E0 = cs[M]
    Elag = cs[np.arange(hi+1) + M] - cs[np.arange(hi+1)]
    d = E0 + Elag - 2*corr
    d[0] = 0.0
    run = np.cumsum(d)
    lags = np.arange(hi+1)
    with np.errstate(divide='ignore', invalid='ignore'):
        dp = np.where(run > 0, d * lags / run, 1.0)
    dp[0] = 1.0
    best = None
    for lag in range(minlag, hi):
        if dp[lag] < thresh and dp[lag] <= dp[lag+1]:
            best = lag; break
    if best is None:
        best = int(np.argmin(dp[minlag:hi]) + minlag)
    y0, y1, y2 = dp[best-1], dp[best], dp[best+1]
    den = y0 - 2*y1 + y2
    frac = 0.5*(y0-y2)/den if abs(den) > 1e-12 else 0.0
    frac = max(-0.5, min(0.5, frac))
    return best + frac, float(dp[best])

# ---- selectors -> C
rows = re.findall(r'\{\s*0x([0-9A-Fa-f]{4}),\s*(-?\d+),\s*(\d)\s*\}', open(HXX).read())
C = {int(a,16): (int(b), int(c)) for a,b,c in rows}

dirs, recs = {}, {}
for p in range(4):
    r = scan_page(p)
    dirs[p], recs[p] = r[0], r[1]
    print("# page %d: %d slots" % (p, len(r[0])))

per = {}
for p in range(4):
    for i,(start, ns, _) in enumerate(dirs[p]):
        if ns < 64: per[(p,i)] = None; continue
        x = np.frombuffer(rom[start:start+min(ns,24000)*2], dtype="<i2").astype(np.float64)
        r = yin_period(x)
        per[(p,i)] = r if r else None

np.save("/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/per.npy",
        np.array([[p,i,(per[(p,i)][0] if per[(p,i)] else 0),(per[(p,i)][1] if per[(p,i)] else 9)]
                  for p in range(4) for i in range(len(dirs[p]))]))
print("# periods done")
