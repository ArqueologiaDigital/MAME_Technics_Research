#!/usr/bin/env python3
"""Row/column ink profiles of the real capture, and a first look at periodicity."""
import numpy as np
from PIL import Image
import sys

p = sys.argv[1] if len(sys.argv) > 1 else "/home/fsanches/compartilhado/KN7000/photos/1st-frame-grabbed.png"
im = np.array(Image.open(p).convert("RGB")).astype(np.float32)
lum = 0.299 * im[:, :, 0] + 0.587 * im[:, :, 1] + 0.114 * im[:, :, 2]

# panel interior guess from the earlier probe
y0, y1 = 118, 412
x0, x1 = 152, 892
sub = lum[y0:y1, x0:x1]

# local background = per-row 90th percentile (the panel body between glyphs)
bg = np.percentile(sub, 88, axis=1, keepdims=True)
ink = np.clip(1.0 - sub / np.maximum(bg, 1e-3), 0, 1)

rowprof = ink.sum(axis=1)
colprof = ink.sum(axis=0)

np.save("real_ink.npy", ink)
np.save("real_rowprof.npy", rowprof)
np.save("real_colprof.npy", colprof)
print("sub", sub.shape, "bg median", float(np.median(bg)))
print("rowprof peaks (y abs):")
for i in range(len(rowprof)):
    pass
# crude: print rowprof as text sparkline
def spark(a, n=None):
    a = np.asarray(a, float)
    lo, hi = a.min(), a.max()
    ch = " .:-=+*#%@"
    return "".join(ch[min(9, int((v - lo) / max(hi - lo, 1e-9) * 9.999))] for v in a)
print("ROW", spark(rowprof))
print("COL", spark(colprof))

# autocorrelation of colprof to find the 3-cell period
c = colprof - colprof.mean()
ac = np.correlate(c, c, "full")[len(c) - 1:]
ac /= ac[0]
best = [(k, ac[k]) for k in range(6, 80)]
best.sort(key=lambda t: -t[1])
print("colprof autocorr top lags:", [(k, round(v, 3)) for k, v in best[:10]])

r = rowprof - rowprof.mean()
ar = np.correlate(r, r, "full")[len(r) - 1:]
ar /= ar[0]
best = [(k, ar[k]) for k in range(6, 60)]
best.sort(key=lambda t: -t[1])
print("rowprof autocorr top lags:", [(k, round(v, 3)) for k, v in best[:10]])
