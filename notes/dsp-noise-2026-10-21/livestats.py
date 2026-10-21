#!/usr/bin/env python3
# livestats.py WAV... -- how broken up is each recording? For a live capture (pw-record of what MAME played) against
# the -wavwrite of the same session (README.md here, "Live against computed").
#
# QUESTION IT ANSWERS: does what the listener hears carry gaps and clicks that the computed stream does not?
# For each WAV, over its active span (first to last 10 ms block above -60 dBFS, instrument channels only):
#   span      seconds from the first note to the end of the last tail (a live capture of a slow session is longer:
#             the passage plays stretched, at the emulation's speed)
#   dropouts  10 ms blocks whose level is more than 20 dB under the median of the 210 ms around them, per second
#             of span (a held or decaying note has none; an audio buffer underrun cuts a hole)
#   clicks    samples whose second difference exceeds 8x the span's RMS second difference, per second of span
#   zeros     the share of samples inside the span that are exactly 0 on both channels (a starved output pads with 0)
# Needs numpy only.
import sys, wave
import numpy as np

print(f'{"wav":48} {"sr":>6} {"span s":>7} {"dropouts/s":>10} {"clicks/s":>9} {"zeros %":>8}')
for p in sys.argv[1:]:
    w = wave.open(p)
    sr, n = w.getframerate(), w.getnchannels()
    x = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').reshape(-1, n)[:, :2].astype(np.float64) / 32768
    blk = sr // 100
    m = len(x) // blk
    e = np.sqrt((x[:m * blk] ** 2).mean(axis=1).reshape(m, blk).mean(axis=1))
    act = np.flatnonzero(e > 10 ** (-60 / 20))
    a, b = act[0], act[-1] + 1
    ee = e[a:b]
    drop = 0
    for i in range(len(ee)):
        nb = ee[max(0, i - 10):i + 11]
        med = np.median(nb)
        if med > 10 ** (-60 / 20) and ee[i] < med * 0.1:
            drop += 1
    s = x[a * blk:b * blk]
    d2 = np.diff(s, 2, axis=0)
    thr = 8 * np.sqrt((d2 ** 2).mean(axis=0))
    clicks = int((np.abs(d2) > thr).any(axis=1).sum())
    zeros = float(((s[:, 0] == 0) & (s[:, 1] == 0)).mean()) * 100
    span = (b - a) / 100
    print(f'{p[-48:]:48} {sr:6d} {span:7.2f} {drop / span:10.2f} {clicks / span:9.1f} {zeros:8.2f}')
