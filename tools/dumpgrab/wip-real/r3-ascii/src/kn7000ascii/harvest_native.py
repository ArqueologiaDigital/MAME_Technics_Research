#!/usr/bin/env python3
"""Harvest the KN7000 MEMORY DUMP font at NATIVE resolution, fully labelled.

Two things come out of this and both are ground truth, not inference:

  * `charmap`  -- the byte -> ASCII-pane-glyph map, all 256 entries.  It is read
    off a frame whose contents we WROTE: `capture/ascii_alphabet.lua` fills the
    scratch RAM page 0x44000000 with 0x00..0xFF in order, so the glyph printed
    in ASCII column j of row r *is* the rendering of byte r*16+j.  A second page
    holds the same 256 values rotated by 0x37, which proves the glyph is a
    function of the VALUE and not of the column it lands in.

  * `hexfont`  -- the 18 hex-pane glyphs (0-9 A-F, space, '-'), taken from the
    same frames, where the hex pane's contents are equally known.

Native geometry is fixed and measured (doc/GEOMETRY.txt + this file's own
verification): origin (90,55), 6 px char pitch, 9 px row pitch, 5x7 glyph.

Usage:  harvest_native.py FRAMEDIR OUT.npz
"""
from __future__ import annotations

import sys
import numpy as np
from PIL import Image

from .geometry_ascii import ROW  # noqa: F401  (native row layout w/ ASCII pane)
from .geometry_ascii import NATIVE_X0, NATIVE_Y0, NATIVE_PX, NATIVE_PY

ROT = 0x37


def _ink(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    lum = a.mean(axis=2)
    return (lum < 64).astype(np.uint8), a


def _cell(ink, r, i):
    y = NATIVE_Y0 + NATIVE_PY * r
    x = NATIVE_X0 + NATIVE_PX * i
    return ink[y:y + 7, x:x + 5]


def harvest(frame_page0: str, frame_page1: str):
    """frame_page0 shows 00..FF in order; frame_page1 the same rotated by ROT."""
    ink0, _ = _ink(frame_page0)
    ink1, _ = _ink(frame_page1)

    bmp = np.zeros((256, 7, 5), np.uint8)
    agree = 0
    for r in range(16):
        for j in range(16):
            b0 = r * 16 + j
            g0 = _cell(ink0, r, ROW.ascii_idx[j])
            g1 = _cell(ink1, r, ROW.ascii_idx[j])
            b1 = (b0 + ROT) & 0xFF
            bmp[b0] = g0
            if np.array_equal(bmp[b1] if bmp[b1].any() else g1, g1):
                pass
            # cross-check page1 against page0 once page0 is complete
    for r in range(16):
        for j in range(16):
            b1 = ((r * 16 + j) + ROT) & 0xFF
            g1 = _cell(ink1, r, ROW.ascii_idx[j])
            if np.array_equal(bmp[b1], g1):
                agree += 1

    # hex font: the alphabet page's hex pane is equally known (byte r*16+j),
    # and every row's address supplies '0'-'F' plus the two blanks and the '-'.
    HEXC = "0123456789ABCDEF"
    acc = {c: [] for c in HEXC + " -"}
    for r in range(16):
        for j in range(16):
            b = r * 16 + j
            hi, lo = ROW.byte_idx[j]
            acc[HEXC[b >> 4]].append(_cell(ink0, r, hi))
            acc[HEXC[b & 15]].append(_cell(ink0, r, lo))
        acc["-"].append(_cell(ink0, r, ROW.sep_idx[7]))
        acc["-"].append(_cell(ink0, r, ROW.ascii_sep_idx))
        acc[" "].append(_cell(ink0, r, ROW.gap1_idx[0]))
        acc[" "].append(_cell(ink0, r, ROW.sep_idx[0]))
    labels = list(HEXC + " -")
    hexf = np.zeros((len(labels), 7, 5), np.uint8)
    for k, c in enumerate(labels):
        s = np.stack(acc[c]).mean(axis=0)
        hexf[k] = (s > 0.5).astype(np.uint8)
        pure = float(np.mean((s == 0) | (s == 1)))
        if pure < 1.0:
            print("  warn: hex glyph %r only %.3f pure over %d samples"
                  % (c, pure, len(acc[c])))
    return bmp, agree, labels, hexf


def classes_of(bmp: np.ndarray):
    """Group the 256 byte values by identical native bitmap."""
    keys = {}
    for b in range(256):
        keys.setdefault(bmp[b].tobytes(), []).append(b)
    members = list(keys.values())
    cls_of = np.zeros(256, np.int16)
    for ci, ms in enumerate(members):
        for b in ms:
            cls_of[b] = ci
    proto = np.stack([bmp[ms[0]] for ms in members])
    return cls_of, members, proto


def main(argv):
    d = argv[1]
    out = argv[2]
    bmp, agree, labels, hexf = harvest(d + "/0000.png", d + "/0003.png")
    cls_of, members, proto = classes_of(bmp)
    print("value-consistency across the two alphabet pages: %d/256" % agree)
    print("distinct ASCII glyphs: %d" % len(members))
    sizes = {}
    for m in members:
        sizes[len(m)] = sizes.get(len(m), 0) + 1
    print("class-size histogram:", dict(sorted(sizes.items())))
    np.savez_compressed(
        out,
        charmap=bmp,
        cls_of=cls_of,
        proto=proto,
        member_lens=np.array([len(m) for m in members], np.int32),
        member_flat=np.array([b for m in members for b in m], np.int32),
        hex_labels=np.array(labels),
        hex_bitmaps=hexf,
    )
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
