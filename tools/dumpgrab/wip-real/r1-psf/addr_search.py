#!/usr/bin/env python3
"""Read the address prefix with a GENERATIVE model rather than per-cell template
matching, and refit the geometry for each candidate.

Per-cell NCC treats a character cell as if its pixels belonged to it alone.  At
this blur they do not: a glyph bleeds two to three native pixels into both
neighbours, so the eight address digits are one joint measurement, not eight
independent ones.  This script therefore scores a WHOLE-BLOCK hypothesis --
"cells 0..5 and 7 are these constant glyphs, cell 6 is the ladder" -- by the
least-squares residual of the rendered block against the pixels, and searches
the hypothesis space by coordinate descent over the seven constant cells.

It also refits the affine for the best few hypotheses, because a wrong glyph and
a slightly wrong geometry can trade against each other.
"""
from __future__ import annotations

import argparse
import itertools
import sys

import numpy as np
from PIL import Image

import fitcore as FC
import fit_real as FR
import realgeom as RG
from realgeom import Affine, NativeGrid, load_font


def block_text(prefix, cells=None):
    """16x57 text with only the address block filled in."""
    txt = [[None] * RG.NHEXCOLS for _ in range(RG.NROWS)]
    for r in range(RG.NROWS):
        for c in range(8):
            if c == RG.LADDER_CELL:
                txt[r][c] = RG.HEXDIG[r]
            else:
                txt[r][c] = prefix[c]
    return txt


def residual_for(gray, grid, font, aff, sx, sy, txt, cells):
    ink = FC.raster_text(grid, font, txt)
    w = FC.cell_mask(grid, cells)
    warp = grid.warp(gray, aff)
    model = RG.sepconv(ink, RG.gauss1(sy, grid.S), RG.gauss1(sx, grid.S))
    return RG.fit_levels_residual(warp, model, w)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frame")
    ap.add_argument("--S", type=int, default=3)
    args = ap.parse_args()

    img = np.asarray(Image.open(args.frame).convert("RGB")).astype(np.float32)
    gray = img.mean(axis=2)
    font = load_font()
    grid = NativeGrid(S=args.S)

    ul, vt, ur, vb = FR.find_panel(img)
    ax0 = (ur - ul) / (RG.PANEL[2] - RG.PANEL[0])
    rp, ay0, by0, ng = FR.seed_rows(gray, ul, vt, ur, vb)
    seed = Affine(ax0, 0.0, ul - ax0 * RG.PANEL[0], ay0, 0.0, by0)
    print("seed  ax %.5f bx %.3f  ay %.5f by %.3f" % (seed.ax, seed.bx, seed.ay, seed.by))

    # score only the interior of the block so the unknown cell 8 does not leak in
    cells = [(r, c) for r in range(RG.NROWS) for c in range(0, 8)]

    prefix = list("00000000")
    aff, sx, sy = seed, 1.4, 0.5
    for sweep in range(4):
        for c in list(range(8)):
            if c == RG.LADDER_CELL:
                continue
            best = None
            for g in RG.HEXDIG:
                trial = list(prefix)
                trial[c] = g
                v = residual_for(gray, grid, font, aff, sx, sy, block_text(trial), cells)
                if best is None or v < best[0]:
                    best = (v, g)
            prefix[c] = best[1]
        txt = block_text(prefix)
        aff, sx, sy, val, npix = FC.fit(gray, grid, font, txt, aff, (sx, sy), cells=cells)
        print("sweep %d  prefix %s  rms %.4f  sigma_nat x %.3f y %.3f  "
              "char pitch %.4f row pitch %.4f"
              % (sweep, "".join(prefix), val, sx, sy,
                 aff.ax * RG.CELL_W, aff.ay * RG.CELL_H))

    # per-cell margin: how much worse is the runner-up glyph?
    print("\nper-cell evidence (whole-block LSQ residual, lower is better)")
    for c in range(8):
        if c == RG.LADDER_CELL:
            print("   cell %d  = row ladder 0..F" % c)
            continue
        scores = []
        for g in RG.HEXDIG:
            trial = list(prefix)
            trial[c] = g
            scores.append((residual_for(gray, grid, font, aff, sx, sy,
                                        block_text(trial), cells), g))
        scores.sort()
        print("   cell %d  best '%s' %.4f | next %s" %
              (c, scores[0][1], scores[0][0],
               "  ".join("'%s' %.4f" % (g, v) for v, g in scores[1:5])))

    base = "".join(prefix[:6]) + "00"
    print("\nBASE ADDRESS = 0x%s" % ("".join(prefix[:6]) + "00"))

    # ladder check with the refitted geometry
    tm = FC.cell_templates(font, sx, sy)
    ok = sum(1 for r in range(RG.NROWS)
             if FC.classify(FC.cut_cell(gray, aff, r, RG.LADDER_CELL), tm, RG.HEXDIG)[0]
             == RG.HEXDIG[r])
    print("ladder correct in %d/16 rows with the refitted geometry" % ok)
    return 0


if __name__ == "__main__":
    sys.exit(main())
