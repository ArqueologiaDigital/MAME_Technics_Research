"""Per-frame point-spread and grid calibration -- ORACLE FREE.

Every frame carries its own labelled training set, for nothing:

  * cell 7 of every row is '0'   -- the viewer prints base + 0x10*r, and the
    dial only ever leaves the base on a 0x100 boundary, so the last address
    digit is '0' in all 16 rows;
  * cell 6 of row r is hex(r)    -- the ladder digit, 16 distinct labels;
  * cells 0..5 are the same six digits in all 16 rows -- unknown, but their
    CONSTANCY across rows is a check no wrong PSF can fake;
  * cell 33 and cell 67 are '-'  -- the hex pane's and the ASCII pane's mid
    separators (see geometry_ascii.py for the second one, which the shipped
    layout does not know about);
  * cells 8, 9 and the 14 blank byte separators are paper.

`Calibrator.fit()` maximises the mean normalised cross-correlation of the
supervised cells (6, 7, 33, 67 -- 64 glyphs per frame) against templates
rendered by the forward model, over (sigma_x, sigma_y).  `refine_grid()` then
takes a per-row sub-pixel x offset.  Nothing here ever looks at a ROM, which is
the point: the target chip has no oracle.

Comparison happens on the CORE of each cell window only.  The window is padded
by one cell in each direction so that a *known* neighbour's ink is modelled, but
scoring is restricted to the centre so an *unknown* neighbour cannot poison the
fit.
"""
from __future__ import annotations

import numpy as np
from copy import deepcopy

from .forward import CellRenderer
from .geometry_ascii import ROW

HEXC = "0123456789ABCDEF"
BLANK = np.zeros((7, 5))


def _ncc(a: np.ndarray, b: np.ndarray) -> float:
    a = a.ravel() - a.mean(); b = b.ravel() - b.mean()
    na = float(np.sqrt((a * a).sum())); nb = float(np.sqrt((b * b).sum()))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float((a * b).sum() / (na * nb))


class Calibrator:
    def __init__(self, img: np.ndarray, grid, hex_labels, hex_bitmaps):
        """img: 2-D float, HIGHER = MORE INK (invert luma before calling)."""
        self.img = img.astype(np.float64)
        self.grid = grid
        self.labels = list(hex_labels)
        self.bmp = {c: hex_bitmaps[i].astype(np.float64)
                    for i, c in enumerate(self.labels)}

    # ------------------------------------------------------------------ #
    def supervised(self, r: int):
        """[(cell, centre_bitmap, (left, right, up, down))] for row r.

        Only neighbours whose content follows from the ladder are supplied;
        everything else is left None (rendered blank, and mostly outside the
        scored core anyway)."""
        B, hx = self.bmp, self.bmp
        d0 = B["0"]; dr = B[HEXC[r]]; dash = B["-"]
        up6 = B[HEXC[r - 1]] if r > 0 else None
        dn6 = B[HEXC[r + 1]] if r < 15 else None
        return [
            (ROW.addr_idx[7], d0, (dr, BLANK, d0 if r > 0 else None,
                                   d0 if r < 15 else None)),
            (ROW.addr_idx[6], dr, (None, d0, up6, dn6)),
            (ROW.hex_dash_idx, dash, (None, None, dash if r > 0 else None,
                                      dash if r < 15 else None)),
            (ROW.ascii_sep_idx, dash, (None, None, dash if r > 0 else None,
                                       dash if r < 15 else None)),
        ]

    def _cell_score(self, ren, r, ci, centre, ctx):
        u0, u1, v0, v1, _, _ = ren.window(r, ci)
        H, W = self.img.shape
        if u0 < 0 or v0 < 0 or u1 > W or v1 > H:
            return None
        obs = self.img[v0:v1, u0:u1]
        Wx, Wy, _ = ren.weights(r, ci)
        mod = ren.render(Wx, Wy, ren.canvas(centre, *ctx))
        return _ncc(obs[ren.core], mod[ren.core])

    def score(self, sigma_x, sigma_y, grid=None, rows=range(16)):
        g = grid if grid is not None else self.grid
        ren = CellRenderer(g, sigma_x, sigma_y)
        vals = []
        for r in rows:
            for ci, centre, ctx in self.supervised(r):
                s = self._cell_score(ren, r, ci, centre, ctx)
                if s is not None:
                    vals.append(s)
        return float(np.mean(vals)) if vals else -1.0

    def fit(self, sx_range=(0.10, 4.0), sy_range=(0.10, 3.0), n=13, rounds=4):
        best = (1.0, 1.0, -2.0)
        lo_x, hi_x = sx_range
        lo_y, hi_y = sy_range
        for _ in range(rounds):
            for sxv in np.linspace(lo_x, hi_x, n):
                for syv in np.linspace(lo_y, hi_y, n):
                    s = self.score(max(sxv, 0.05), max(syv, 0.05))
                    if s > best[2]:
                        best = (float(max(sxv, 0.05)), float(max(syv, 0.05)), s)
            dx = (hi_x - lo_x) / n * 1.5
            dy = (hi_y - lo_y) / n * 1.5
            lo_x, hi_x = max(best[0] - dx, 0.05), best[0] + dx
            lo_y, hi_y = max(best[1] - dy, 0.05), best[1] + dy
            n = 9
        return best

    def refine_grid(self, sigma_x, sigma_y, span=1.2, n=25):
        """Per-row sub-pixel x offset plus a global y offset."""
        g = deepcopy(self.grid)
        best = (0.0, -2.0)
        for dy in np.linspace(-span, span, n):
            gg = deepcopy(g); gg.y0 = g.y0 + dy
            s = self.score(sigma_x, sigma_y, gg)
            if s > best[1]:
                best = (float(dy), s)
        g.y0 += best[0]
        rowx = []
        for r in range(16):
            base = g.row_x0[r] if g.row_x0 else g.x0
            bb = (0.0, -2.0)
            for dx in np.linspace(-span, span, n):
                gg = deepcopy(g)
                gg.row_x0 = list(g.row_x0) if g.row_x0 else [g.x0] * 16
                gg.row_x0[r] = base + dx
                s = self.score(sigma_x, sigma_y, gg, rows=[r])
                if s > bb[1]:
                    bb = (float(dx), s)
            rowx.append(base + bb[0])
        g.row_x0 = rowx
        return g
