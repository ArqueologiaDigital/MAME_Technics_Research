"""One captured page: geometry + empirical PSF + the three channels.

`Page` is the single object the rest of the tool talks to.  It owns

    img      2-D float, higher = more ink
    grid     the 76-cell affine cell grid (see geometry_ascii)
    psf      a SeparablePSF fitted on this frame's own address column
    font     the native 5x7 bitmaps, including the 256-entry ASCII charmap

and offers `logpost_hex()` / `logpost_ascii()` / `colour_evidence()`, all three
returning evidence about the same 256 bytes so that fusing is an addition.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from .geometry_ascii import ROW, Grid
from .psf_empirical import SeparablePSF, PSFFitter

HEXC = "0123456789ABCDEF"
BLANK = np.zeros((7, 5))
NEG = -60.0


def _ncc(a, b):
    a = a.ravel() - a.mean(); b = b.ravel() - b.mean()
    na = float(np.sqrt((a * a).sum())); nb = float(np.sqrt((b * b).sum()))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float((a * b).sum() / (na * nb))


def _softmax(s, T):
    z = (s - s.max()) / max(T, 1e-6)
    e = np.exp(z)
    return e / e.sum()


def _logsumexp(a):
    m = a.max()
    return m + np.log(np.exp(a - m).sum())


class Page:
    def __init__(self, img, grid: Grid, font, psf: SeparablePSF,
                 pad_cells=1, pad_rows=1, mx=0.30, my=0.10):
        self.img = img
        self.g = grid
        self.font = font
        self.psf = psf
        self.sx = grid.px / 6.0
        self.sy = grid.py / 9.0
        self.pad_cells, self.pad_rows = pad_cells, pad_rows
        self.mx, self.my = mx, my
        self._cache: Dict[Tuple[int, int], tuple] = {}

    # ---------------------------------------------------------------- #
    def rowx(self, r):
        return self.g.row_x0[r] if self.g.row_x0 else self.g.x0

    def geom(self, r, i):
        """(obs, x_off, y_off, u, v) for cell (r, i) -- obs is the CORE window,
        x_off/y_off place native pixel (0,0) of the padded canvas."""
        key = (r, i)
        if key in self._cache:
            return self._cache[key]
        cx = self.rowx(r) + self.g.px * i
        cy = self.g.y0 + self.g.py * r
        u0 = int(round(cx - self.mx * self.g.px))
        u1 = int(round(cx + (1 + self.mx) * self.g.px))
        v0 = int(round(cy - self.my * self.g.py))
        v1 = int(round(cy + (1 + self.my) * self.g.py))
        H, W = self.img.shape
        if u0 < 0 or v0 < 0 or u1 > W or v1 > H:
            self._cache[key] = None
            return None
        obs = self.img[v0:v1, u0:u1]
        u = np.arange(u0, u1, dtype=np.float64) + 0.5
        v = np.arange(v0, v1, dtype=np.float64) + 0.5
        x_off = cx - self.pad_cells * self.g.px
        y_off = cy - self.pad_rows * self.g.py
        val = (obs, x_off, y_off, u, v)
        self._cache[key] = val
        return val

    def canvas(self, centre, ctx=(None, None, None, None)):
        nh = 9 * (1 + 2 * self.pad_rows)
        nw = 6 * (1 + 2 * self.pad_cells)
        c = np.zeros((nh, nw))
        oy, ox = 9 * self.pad_rows, 6 * self.pad_cells
        c[oy:oy + 7, ox:ox + 5] = centre
        L, R, U, D = ctx
        if L is not None:
            c[oy:oy + 7, ox - 6:ox - 1] = L
        if R is not None:
            c[oy:oy + 7, ox + 6:ox + 11] = R
        if U is not None:
            c[oy - 9:oy - 2, ox:ox + 5] = U
        if D is not None:
            c[oy + 9:oy + 16, ox:ox + 5] = D
        return c

    def model(self, r, i, centre, ctx=(None, None, None, None)):
        gm = self.geom(r, i)
        if gm is None:
            return None
        _, x_off, y_off, u, v = gm
        can = self.canvas(centre, ctx)
        return self.psf.render(can, x_off, self.sx, y_off, self.sy, u, v)

    def score_cell(self, r, i, templates, ctx=(None, None, None, None)):
        gm = self.geom(r, i)
        if gm is None:
            return None
        obs = gm[0]
        return np.array([_ncc(obs, self.model(r, i, t, ctx)) for t in templates])

    # ---------------------------------------------------------------- #
    #  known-content maps
    # ---------------------------------------------------------------- #
    def static_context(self):
        hx = self.font.hexmap
        est = {}
        for r in range(16):
            for i in ROW.gap1_idx + ROW.gap2_idx:
                est[(r, i)] = BLANK
            for i in ROW.sep_idx:
                est[(r, i)] = hx["-"] if i == ROW.hex_dash_idx else BLANK
            est[(r, ROW.ascii_sep_idx)] = hx["-"]
            est[(r, ROW.addr_idx[7])] = hx["0"]
            est[(r, ROW.addr_idx[6])] = hx[HEXC[r]]
        return est

    def address_context(self, base):
        hx = self.font.hexmap
        est = self.static_context()
        for r in range(16):
            for i, ch in enumerate("%08X" % (base + 16 * r)):
                est[(r, ROW.addr_idx[i])] = hx[ch]
        return est

    def ctx_of(self, est, r, i):
        return (est.get((r, i - 1)), est.get((r, i + 1)),
                est.get((r - 1, i)), est.get((r + 1, i)))

    # ---------------------------------------------------------------- #
    #  PSF training on the address column
    # ---------------------------------------------------------------- #
    def psf_patches(self, est, cells):
        out = []
        for (r, i) in cells:
            gm = self.geom(r, i)
            if gm is None:
                continue
            obs, x_off, y_off, u, v = gm
            centre = est.get((r, i))
            if centre is None:
                continue
            can = self.canvas(centre, self.ctx_of(est, r, i))
            out.append((obs, can, x_off, self.sx, y_off, self.sy, u, v))
        return out

    def fit_psf(self, est, cells, iters=6, **kw):
        f = PSFFitter(**kw)
        self.psf = f.fit(self.psf_patches(est, cells), iters=iters, init=self.psf)
        self._cache.clear()
        return self.psf

    def psf_residual(self, est, cells):
        vals = []
        for (r, i) in cells:
            gm = self.geom(r, i)
            if gm is None:
                continue
            m = self.model(r, i, est[(r, i)], self.ctx_of(est, r, i))
            vals.append(_ncc(gm[0], m))
        return float(np.mean(vals)), len(vals)
