#!/usr/bin/env python3
"""First-pass measurement of the real capture: panel extent, scale, legend bar."""
import numpy as np
from PIL import Image
import sys

p = sys.argv[1] if len(sys.argv) > 1 else "/home/fsanches/compartilhado/KN7000/photos/1st-frame-grabbed.png"
im = np.array(Image.open(p).convert("RGB")).astype(np.float32)
H, W, _ = im.shape
print("frame", W, "x", H)

lum = im.mean(axis=2)

# 1. non-black content bbox
mask = lum > 24
ys, xs = np.nonzero(mask)
print("content bbox x", xs.min(), xs.max(), " y", ys.min(), ys.max())

# 2. the dump panel is a big mid-grey region.  Score each pixel by "greyness"
mx = im.max(axis=2); mn = im.min(axis=2)
grey = (mx - mn < 40) & (lum > 90) & (lum < 200)
colprof = grey.sum(axis=0)
rowprof = grey.sum(axis=1)
def runs(prof, thr):
    on = prof > thr
    out = []
    i = 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and on[j]:
                j += 1
            out.append((i, j - 1, j - i))
            i = j
        else:
            i += 1
    return out
print("grey col runs:", [r for r in runs(colprof, 40) if r[2] > 20])
print("grey row runs:", [r for r in runs(rowprof, 100) if r[2] > 20])

# 3. legend bar: saturated aqua/yellow/lime/fuchsia
def colmask(rgb, tol=70):
    return (np.abs(im - np.array(rgb, np.float32)).max(axis=2) < tol)
for name, rgb in [("aqua", (0, 252, 252)), ("yellow", (252, 252, 0)),
                  ("lime", (0, 252, 0)), ("fuchsia", (252, 0, 252)),
                  ("red", (252, 0, 0))]:
    m = colmask(rgb)
    if m.sum() < 50:
        print(f"{name}: {m.sum()} px")
        continue
    ys, xs = np.nonzero(m)
    print(f"{name}: {m.sum():6d} px  x {xs.min()}..{xs.max()}  y {ys.min()}..{ys.max()}")
