#!/usr/bin/env python3
"""cmp_snapshot.py -- compare a CaptureLcd BMP (as PNG) with MAME's own screen snapshot of the same
screen: quantise both to RGB565 (MAME may fill the low bits differently) and find the vertical
shift s for which BMP row y == snapshot row y+s. Answers: does the capture show what MAME displays,
and is it shifted by a row?
Usage: python3 cmp_snapshot.py CAPTURE.png SNAPSHOT.png
"""
import sys
import numpy as np
from PIL import Image
a = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(np.int32)
b = np.asarray(Image.open(sys.argv[2]).convert('RGB')).astype(np.int32)
print("capture", a.shape, "snapshot", b.shape)
q = lambda x: np.stack([x[..., 0] >> 3, x[..., 1] >> 2, x[..., 2] >> 3], -1)
a, b = q(a), q(b)
h = min(a.shape[0], b.shape[0])
for s in (-2, -1, 0, 1, 2):
    rows = [y for y in range(h) if 0 <= y + s < b.shape[0]]
    eq = sum(1 for y in rows if np.array_equal(a[y], b[y + s]))
    px = sum(int((a[y] != b[y + s]).any(-1).sum()) for y in rows)
    print(f"shift {s:+d}: identical rows {eq}/{len(rows)}, differing pixels {px}")
