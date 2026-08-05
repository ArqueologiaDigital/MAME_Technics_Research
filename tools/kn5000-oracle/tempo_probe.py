#!/usr/bin/env python3
"""Model-free tempo probe: autocorrelation of the broadband onset function."""
import sys
import numpy as np
from analyse_capture import rise

HOP, SR = 256, 48000
d = np.load(sys.argv[1])
lo, hi = float(sys.argv[2]), float(sys.argv[3])
mag, times = d['mag'], d['times']
sel = (times >= lo) & (times <= hi)
R = rise(mag)[:, sel]
o = R.sum(axis=0)
o = o - o.mean()
n = len(o)
ac = np.correlate(o, o, 'full')[n - 1:]
ac /= ac[0]
lagt = np.arange(len(ac)) * HOP / SR
m = (lagt > 0.15) & (lagt < 1.6)
idx = np.argsort(-ac[m])[:40]
print(f'window {lo}-{hi}s, onset-function frames {n}')
print('top autocorrelation lags (s, corr, implied bpm):')
seen = []
for i in idx:
    t, c = lagt[m][i], ac[m][i]
    if any(abs(t - s) < 0.05 for s in seen):
        continue
    seen.append(t)
    print(f'   lag={t:.4f}s corr={c:+.3f}  {60/t:7.2f} bpm  (x2 {120/t:7.2f}, /2 {30/t:7.2f})')
    if len(seen) >= 12:
        break
