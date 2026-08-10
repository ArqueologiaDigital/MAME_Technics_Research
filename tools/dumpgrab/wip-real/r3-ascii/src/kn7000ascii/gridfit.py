"""Fit the 76-cell row grid to a capture, using only self-evident anchors.

The anchors are the four supervised cells of `psf._supervised_cells`: the two
right-hand address digits (labels known from the ladder alone) and the two mid
separators -- cell 33 in the hex pane and **cell 67 in the ASCII pane**.  Cell 6
and cell 67 are 61 cells apart, which is the longest labelled baseline on the
screen and therefore the best pitch estimate available without an oracle.

This matters: the shipped extractor fits a 75-cell model.  One cell of model
error over a 76-cell row is 1.3 % of pitch, i.e. a whole character of drift by
the right-hand end -- which is exactly where the shipped tool's residual
systematic errors were reported to live.
"""
from __future__ import annotations

import numpy as np
from copy import deepcopy

from .geometry_ascii import Grid
from .psf import Calibrator


def fit_horizontal(cal: Calibrator, x0_range, px_range, sigma_x, sigma_y,
                   n=21, rounds=4):
    lo_o, hi_o = x0_range
    lo_p, hi_p = px_range
    best = (cal.grid.x0, cal.grid.px, -2.0)
    for _ in range(rounds):
        for o in np.linspace(lo_o, hi_o, n):
            for p in np.linspace(lo_p, hi_p, n):
                g = deepcopy(cal.grid); g.x0 = float(o); g.px = float(p)
                g.row_x0 = []
                s = cal.score(sigma_x, sigma_y, g)
                if s > best[2]:
                    best = (float(o), float(p), s)
        do = (hi_o - lo_o) / n * 1.5
        dp = (hi_p - lo_p) / n * 1.5
        lo_o, hi_o = best[0] - do, best[0] + do
        lo_p, hi_p = best[1] - dp, best[1] + dp
        n = 11
    return best


def fit_vertical(cal: Calibrator, y0_range, py_range, sigma_x, sigma_y,
                 n=21, rounds=3):
    lo_o, hi_o = y0_range
    lo_p, hi_p = py_range
    best = (cal.grid.y0, cal.grid.py, -2.0)
    for _ in range(rounds):
        for o in np.linspace(lo_o, hi_o, n):
            for p in np.linspace(lo_p, hi_p, n):
                g = deepcopy(cal.grid); g.y0 = float(o); g.py = float(p)
                s = cal.score(sigma_x, sigma_y, g)
                if s > best[2]:
                    best = (float(o), float(p), s)
        do = (hi_o - lo_o) / n * 1.5
        dp = (hi_p - lo_p) / n * 1.5
        lo_o, hi_o = best[0] - do, best[0] + do
        lo_p, hi_p = best[1] - dp, best[1] + dp
        n = 11
    return best


def autofit(img, font, x0, px, y0, py, verbose=True):
    """Alternate (grid, psf) a few times from a rough start."""
    g = Grid(x0, px, y0, py, 5.0, 7.0)
    cal = Calibrator(img, g, font.hex_labels, font.hex_bitmaps)
    sx, sy = 1.5, 1.0
    spans = [(6.0, 0.40, 4.0, 0.40), (2.0, 0.10, 1.5, 0.10), (1.0, 0.04, 0.8, 0.04)]
    for it in range(3):
        sx, sy, s = cal.fit()
        if verbose:
            print("  psf   sigma_x=%.3f sigma_y=%.3f  ncc=%.4f" % (sx, sy, s))
        dx, dpx, dy, dpy = spans[it]
        ox, opx, s = fit_horizontal(cal, (g.x0 - dx, g.x0 + dx),
                                    (g.px - dpx, g.px + dpx), sx, sy)
        g.x0, g.px = ox, opx
        cal.grid = g
        oy, opy, s = fit_vertical(cal, (g.y0 - dy, g.y0 + dy),
                                  (g.py - dpy, g.py + dpy), sx, sy)
        g.y0, g.py = oy, opy
        cal.grid = g
        if verbose:
            print("  grid  x0=%.3f px=%.4f y0=%.3f py=%.4f  ncc=%.4f"
                  % (g.x0, g.px, g.y0, g.py, s))
    g = cal.refine_grid(sx, sy)
    cal.grid = g
    final = cal.score(sx, sy)
    if verbose:
        print("  rowfit ncc=%.4f" % final)
    return g, sx, sy, final
