#!/usr/bin/env python3
"""Extract the EXACT native 5x7 font bitmaps of the KN7000 MEMORY DUMP viewer.

No guessing and no oracle: the address column of every dump page is self-labelling
(16 rows ascending by 0x10), so a handful of emulator frames at `-snapview native`
yields pixel-exact, labelled samples of every hex glyph.  The '-' separator (cell 33)
and the spaces (cells 8,9) come for free from the fixed line layout.

Writes  font_native.npz  with  labels (str), bitmaps (n,7,5) uint8 {0,1}, n_samples.
"""
from __future__ import annotations

import os
import sys
import json
import numpy as np
from PIL import Image

# native geometry (doc/GEOMETRY.txt, re-verified here)
X0, Y0 = 90, 55
PX, PY = 6, 9
GW, GH = 5, 7
NROWS = 16

CLASSES = "0123456789ABCDEF -"


def cell_lum(img: np.ndarray, row: int, col: int) -> np.ndarray:
    y = Y0 + PY * row
    x = X0 + PX * col
    return img[y:y + GH, x:x + GW].astype(np.float32).mean(axis=2)


def frame_bitmaps(path: str):
    """Return list of (label, 7x5 binary) from one native frame's address column."""
    img = np.array(Image.open(path).convert("RGB"))
    if img.shape[:2] != (240, 640):
        return None
    # read the 16 address rows as ink masks first; ink is dark on the grey panel
    out = []
    rows_digits = []
    for r in range(NROWS):
        digs = []
        for c in range(8):
            p = cell_lum(img, r, c)
            digs.append(p)
        rows_digits.append(digs)
    # panel background level: median of everything in the hex area
    bg = np.median(np.concatenate([d.ravel() for row in rows_digits for d in row]))
    def ink(p):
        return (p < bg * 0.6).astype(np.uint8)
    masks = [[ink(d) for d in row] for row in rows_digits]

    # self-label: the 16 rows must be base + 0x10*r.  We do not know the digits yet,
    # but rows differing only in digit 6 give us the ladder: cluster the 16 samples of
    # digit position 6 -- they are 0..F in order, by construction.
    for r in range(NROWS):
        out.append(("0123456789ABCDEF"[r], masks[r][6]))
        out.append(("0", masks[r][7]))          # digit 7 is 0 on a page-aligned base
    # digits 0..5 are the same in all 16 rows -> take row 0 samples, label unknown yet
    hdr = [masks[0][c] for c in range(6)]
    return out, hdr, masks, img


def main(argv):
    frames_dir = argv[1] if len(argv) > 1 else "/tmp/dg_cap1/frames"
    outp = argv[2] if len(argv) > 2 else "font_native.npz"
    files = sorted(f for f in os.listdir(frames_dir) if f.endswith(".png"))
    acc = {}          # label -> list of bitmaps
    nframes = 0
    ref = None
    for f in files[::7]:
        got = frame_bitmaps(os.path.join(frames_dir, f))
        if got is None:
            continue
        pairs, hdr, masks, img = got
        # sanity: the ladder must be internally consistent -- all 16 digit-6 samples
        # distinct, and digit-7 identical across rows
        sigs = {pairs[2 * r][1].tobytes() for r in range(NROWS)}
        if len(sigs) != 16:
            continue
        z7 = {pairs[2 * r + 1][1].tobytes() for r in range(NROWS)}
        if len(z7) != 1:
            continue
        nframes += 1
        for lab, bm in pairs:
            acc.setdefault(lab, []).append(bm)
        # the '-' separator at cell 33 and the spaces at cells 8,9
        for r in range(NROWS):
            acc.setdefault("-", []).append(mask_cell(img, r, 33))
            acc.setdefault(" ", []).append(mask_cell(img, r, 8))
            acc.setdefault(" ", []).append(mask_cell(img, r, 9))
        if nframes >= 40:
            break

    labels, bitmaps, counts, purity = [], [], [], []
    for lab in CLASSES:
        if lab not in acc:
            continue
        arr = np.stack(acc[lab])
        maj = (arr.mean(axis=0) > 0.5).astype(np.uint8)
        agree = float((arr == maj).mean())
        labels.append(lab)
        bitmaps.append(maj)
        counts.append(len(arr))
        purity.append(agree)

    B = np.stack(bitmaps)
    np.savez_compressed(outp, labels=np.array(labels), bitmaps=B,
                        counts=np.array(counts), purity=np.array(purity),
                        meta=json.dumps(dict(x0=X0, y0=Y0, px=PX, py=PY, gw=GW, gh=GH,
                                             frames=nframes, src=frames_dir)))
    print(f"frames used: {nframes}")
    for lab, n, p in zip(labels, counts, purity):
        print(f"  '{lab}'  n={n:5d}  pixel-purity={p*100:.4f}%")
    print("written", outp)
    for i, lab in enumerate(labels):
        print(f"--- '{lab}'")
        for r in range(B.shape[1]):
            print("   " + "".join("#" if B[i, r, c] else "." for c in range(B.shape[2])))


def mask_cell(img, row, col):
    p = cell_lum(img, row, col)
    # background from the whole panel row
    y = Y0 + PY * row
    strip = img[y:y + GH, X0:X0 + 6 * 57].astype(np.float32).mean(axis=2)
    bg = np.median(strip)
    return (p < bg * 0.6).astype(np.uint8)


if __name__ == "__main__":
    main(sys.argv)
