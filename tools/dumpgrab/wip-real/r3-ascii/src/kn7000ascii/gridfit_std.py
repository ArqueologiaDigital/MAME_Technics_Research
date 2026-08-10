"""Content-independent horizontal grid fit from the COLUMN VARIANCE profile.

Take the standard deviation of the panel down each capture column.  A column
that is blank for every one of the 16 rows has (almost) no variance; a column
that carries glyph strokes has a lot, because within a text row the ink
alternates with the 2-pixel inter-row gap.  The pattern of blank columns is
fixed by the format and does not depend on what the page contains:

    always blank:  col 5 of every cell, plus every column of cells
                   8, 9, 12, 15, 18, 21, 24, 27, 30, 36, 39, 42, 45, 48, 51,
                   54, 57, 58

That is 18 whole blank cells spread from cell 8 to cell 58, plus a blank column
every 6 native pixels the whole way across -- an anchor grid spanning the full
76-cell row, with no oracle and no dependence on the glyphs being legible.

Measured on the real capture this also CONFIRMS the geometry correction: the
variance stays high out to cell 75 and collapses at 76, and there is a
low-variance notch at cell 67 -- the ASCII pane's '-' separator, which the
shipped 75-cell layout does not have.
"""
from __future__ import annotations

import numpy as np

from .geometry_ascii import ROW, SPACE


def native_variance_template(nrows_blank_penalty: float = 1.0) -> np.ndarray:
    """(6*ncols,) 1.0 where a column can carry ink, 0.0 where it never does."""
    t = np.zeros(6 * ROW.ncols)
    for i in range(ROW.ncols):
        if ROW.kind[i] == SPACE:
            continue
        t[6 * i:6 * i + 5] = 1.0
    return t


def column_std(img: np.ndarray, y0: float, py: float, nrows: int = 16) -> np.ndarray:
    v0 = int(round(y0)); v1 = int(round(y0 + py * nrows))
    return img[v0:v1, :].std(axis=0)


def fit(colstd: np.ndarray, x0_range, px_range, n=41, rounds=5):
    """NCC of the measured std profile against the template."""
    ref = native_variance_template()
    nref = len(ref)
    x = np.arange(len(colstd), dtype=np.float64) + 0.5
    lo_o, hi_o = x0_range
    lo_p, hi_p = px_range
    best = (0.0, 0.0, -2.0)
    for _ in range(rounds):
        for x0 in np.linspace(lo_o, hi_o, n):
            for px in np.linspace(lo_p, hi_p, n):
                sx = px / 6.0
                u = (x - x0) / sx           # native column coordinate
                m = np.interp(u, np.arange(nref) + 0.5, ref, left=0.0, right=0.0)
                sel = (u > -2) & (u < nref + 2)
                a = colstd[sel] - colstd[sel].mean()
                b = m[sel] - m[sel].mean()
                d = np.sqrt((a * a).sum() * (b * b).sum())
                v = float((a * b).sum() / d) if d > 1e-9 else -1.0
                if v > best[2]:
                    best = (float(x0), float(px), v)
        do = (hi_o - lo_o) / n * 1.5
        dp = (hi_p - lo_p) / n * 1.5
        lo_o, hi_o = best[0] - do, best[0] + do
        lo_p, hi_p = best[1] - dp, best[1] + dp
        n = 21
    return best


def row_variance_template() -> np.ndarray:
    """(9*16,) 1.0 on the 7 glyph rows of each text row, 0 on the 2-row gap."""
    t = np.zeros(9 * 16)
    for r in range(16):
        t[9 * r:9 * r + 7] = 1.0
    return t


def row_std(img: np.ndarray, x0: float, px: float) -> np.ndarray:
    u0 = int(round(x0)); u1 = int(round(x0 + px * ROW.ncols))
    return img[:, u0:u1].std(axis=1)


def fit_rows(rowstd: np.ndarray, y0_range, py_range, n=41, rounds=5):
    ref = row_variance_template()
    nref = len(ref)
    y = np.arange(len(rowstd), dtype=np.float64) + 0.5
    lo_o, hi_o = y0_range
    lo_p, hi_p = py_range
    best = (0.0, 0.0, -2.0)
    for _ in range(rounds):
        for y0 in np.linspace(lo_o, hi_o, n):
            for py in np.linspace(lo_p, hi_p, n):
                sy = py / 9.0
                u = (y - y0) / sy
                m = np.interp(u, np.arange(nref) + 0.5, ref, left=0.0, right=0.0)
                sel = (u > -2) & (u < nref + 2)
                a = rowstd[sel] - rowstd[sel].mean()
                b = m[sel] - m[sel].mean()
                d = np.sqrt((a * a).sum() * (b * b).sum())
                v = float((a * b).sum() / d) if d > 1e-9 else -1.0
                if v > best[2]:
                    best = (float(y0), float(py), v)
        do = (hi_o - lo_o) / n * 1.5
        dp = (hi_p - lo_p) / n * 1.5
        lo_o, hi_o = best[0] - do, best[0] + do
        lo_p, hi_p = best[1] - dp, best[1] + dp
        n = 21
    return best
