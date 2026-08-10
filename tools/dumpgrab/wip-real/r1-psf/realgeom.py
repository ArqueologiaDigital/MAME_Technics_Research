#!/usr/bin/env python3
"""Sub-pixel geometry + point-spread-function model for a REAL composite capture
of the KN7000 MEMORY DUMP screen.  numpy + Pillow only (no scipy, no OpenCV).

Why this exists
---------------
`kn7000dump.geometry` fits a row comb and a column matched filter independently
and then re-centres each character cell on its own ink.  On a pixel-exact
emulator frame that is enough.  On analog video it is not, for two reasons that
were both measured before this file was written:

  * the character pitch is estimated from a 1-D profile whose peaks have been
    smeared into each other, so a small pitch error is invisible locally and
    accumulates across a 75-character row (the phone-photo failure: pitch 8 %
    low, 47 px of drift by the right end of the row);
  * per-cell ink re-centring is *actively harmful* once neighbouring glyphs
    overlap, because a cell's ink centroid is pulled by its neighbours.

So instead of estimating a pitch, this module fits ONE GLOBAL AFFINE MAP from
the native 640x240 raster to the capture, jointly with the blur, by
forward-modelling the screen and minimising the residual against the pixels.  A
single global map cannot drift, and every known character constrains it.

What is "known" without an oracle
---------------------------------
Everything the fit needs is printed on the screen in every frame:

  * the panel rectangle -- a hard bright-on-black edge on all four sides;
  * cells 8, 9, 12+3i, 36+3j are SPACES and cell 33 is '-' in all 16 rows
    (240 cells whose content is fixed by the layout, spread across the full
    row width -- this is what pins the pitch);
  * the row address is base + 0x10*r, so address cell 6 spells 0,1,...,F down
    the page while cells 0..5 and 7 are the same glyph in every row.  Sixteen
    labelled samples spanning all sixteen hex classes, free, in every frame,
    with no oracle.

Model
-----
    u = ax*X + shx*Y + bx          (X,Y) native pixel coords, (u,v) capture px
    v = ay*Y + shy*X + by

Fitting is done in NATIVE space for speed: the capture is warped back onto a
supersampled native grid (S samples per native pixel), where the model is just
the sharp glyph raster convolved with the PSF expressed in native pixels.  The
final PSF is then re-measured in the forward direction, in capture space, with
a non-parametric kernel, so nothing rests on the warp.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# --------------------------------------------------------------------------- #
# the screen, in native pixels (doc/GEOMETRY.txt, re-verified in this package)
# --------------------------------------------------------------------------- #
NAT_W, NAT_H = 640, 240
CELL_X0, CELL_Y0 = 90, 55        # top-left of character cell (row 0, col 0)
CELL_W, CELL_H = 6, 9            # character pitch / row pitch
GLYPH_W, GLYPH_H = 5, 7
NROWS = 16
NHEXCOLS = 57                    # cells 0..56 = address + hex area
ASCII_C0, ASCII_N = 58, 16       # the ASCII column
# Edges of the panel's UNSATURATED bright body, in native pixels: left/top/right
# are the panel rectangle, the bottom is the top of the legend colour band (the
# band itself is fully saturated, so it is not part of the mask find_panel uses).
PANEL = (84.0, 49.0, 550.0, 199.0)

HEX_HI = [10 + 3 * i for i in range(8)] + [34 + 3 * j for j in range(8)]
SPACE_CELLS = [8, 9] + [12 + 3 * i for i in range(7)] + [36 + 3 * j for j in range(7)]
DASH_CELL = 33
HEXDIG = "0123456789ABCDEF"
# The row address printed on line r is base + 0x10*r, so of the eight address
# digits it is cell 6 that runs 0,1,...,F down the page and cell 7 that is always
# '0'.  Cells 0..5 and 7 are the same glyph in every row.
LADDER_CELL = 6
CONST_CELLS = [0, 1, 2, 3, 4, 5, 7]

FONT_PATH = "font_native.json"


def load_font(path: str = FONT_PATH) -> Dict[str, np.ndarray]:
    raw = json.load(open(path))
    return {ch: np.array([[1.0 if c == "#" else 0.0 for c in r] for r in rows],
                         dtype=np.float32)
            for ch, rows in raw.items()}


# --------------------------------------------------------------------------- #
@dataclass
class Affine:
    ax: float
    shx: float
    bx: float
    ay: float
    shy: float
    by: float

    def to_vec(self):
        return np.array([self.ax, self.shx, self.bx, self.ay, self.shy, self.by])

    def forward(self, X, Y):
        return (self.ax * X + self.shx * Y + self.bx,
                self.ay * Y + self.shy * X + self.by)

    def inverse(self, u, v):
        det = self.ax * self.ay - self.shx * self.shy
        du, dv = u - self.bx, v - self.by
        return ((self.ay * du - self.shx * dv) / det,
                (-self.shy * du + self.ax * dv) / det)


def bilinear(img: np.ndarray, U: np.ndarray, V: np.ndarray) -> np.ndarray:
    h, w = img.shape
    u0 = np.clip(np.floor(U - 0.5).astype(np.int32), 0, w - 2)
    v0 = np.clip(np.floor(V - 0.5).astype(np.int32), 0, h - 2)
    fu = np.clip(U - 0.5 - u0, 0.0, 1.0)
    fv = np.clip(V - 0.5 - v0, 0.0, 1.0)
    return (img[v0, u0] * (1 - fu) * (1 - fv) + img[v0, u0 + 1] * fu * (1 - fv) +
            img[v0 + 1, u0] * (1 - fu) * fv + img[v0 + 1, u0 + 1] * fu * fv)


# --------------------------------------------------------------------------- #
# native-space analysis grid
# --------------------------------------------------------------------------- #
class NativeGrid:
    """A supersampled native-coordinate grid covering the hex text area.

    S samples per native pixel.  Warping the capture onto this grid makes the
    forward model trivial (sharp raster * PSF) and 20x cheaper than rendering
    the native raster into capture space at every optimiser step.
    """

    def __init__(self, S: int = 3, pad: int = 2, c0: int = 0, c1: int = NHEXCOLS):
        # c0..c1 restricts the grid to a range of character columns.  Fitting on
        # the 8-cell address block alone is 5.7x cheaper than warping the whole
        # 57-cell row, and the early rounds only score the address block.
        self.S = S
        self.c0, self.c1 = c0, c1
        self.x0 = CELL_X0 + CELL_W * c0 - pad
        self.y0 = CELL_Y0 - pad
        self.w = CELL_W * (c1 - c0) + 2 * pad
        self.h = CELL_H * NROWS + 2 * pad
        xs = self.x0 + (np.arange(self.w * S) + 0.5) / S
        ys = self.y0 + (np.arange(self.h * S) + 0.5) / S
        self.X, self.Y = np.meshgrid(xs, ys)
        self.shape = self.X.shape

    def warp(self, img: np.ndarray, aff: Affine) -> np.ndarray:
        U, V = aff.forward(self.X, self.Y)
        return bilinear(img, U, V)

    def raster(self, font, text) -> Tuple[np.ndarray, np.ndarray]:
        """(ink, known) rasters on the grid.  `text[r][c]` may be None."""
        S = self.S
        ink = np.zeros(self.shape, np.float32)
        known = np.zeros(self.shape, np.float32)
        for r, row in enumerate(text):
            for c, ch in enumerate(row):
                if ch is None:
                    continue
                gy = (CELL_Y0 + CELL_H * r - self.y0) * S
                gx = (CELL_X0 + CELL_W * c - self.x0) * S
                g = np.kron(font[ch], np.ones((S, S), np.float32))
                ink[gy:gy + GLYPH_H * S, gx:gx + GLYPH_W * S] = g
                known[gy:gy + CELL_H * S, gx:gx + CELL_W * S] = 1.0
        return ink, known


def known_text(base: Optional[str] = None) -> List[List[Optional[str]]]:
    txt: List[List[Optional[str]]] = [[None] * NHEXCOLS for _ in range(NROWS)]
    for r in range(NROWS):
        if base is not None:
            for c, ch in enumerate("%08X" % (int(base, 16) + 16 * r)):
                txt[r][c] = ch
        else:
            txt[r][LADDER_CELL] = HEXDIG[r]
        for c in SPACE_CELLS:
            txt[r][c] = " "
        txt[r][DASH_CELL] = "-"
    return txt


# --------------------------------------------------------------------------- #
def gauss1(sigma: float, S: int) -> np.ndarray:
    s = max(sigma, 1e-3) * S
    rad = max(int(np.ceil(3.5 * s)), 1)
    x = np.arange(-rad, rad + 1, dtype=np.float64)
    k = np.exp(-0.5 * (x / s) ** 2)
    return (k / k.sum()).astype(np.float32)


def sepconv(img: np.ndarray, ky: np.ndarray, kx: np.ndarray) -> np.ndarray:
    def conv1(a, k, axis):
        r = (len(k) - 1) // 2
        if r == 0:
            return a
        pad = [(0, 0), (0, 0)]
        pad[axis] = (r, r)
        b = np.pad(a, pad, mode="edge")
        out = np.zeros_like(a)
        n = a.shape[axis]
        for i, w in enumerate(k):
            if w == 0.0:
                continue
            sl = [slice(None), slice(None)]
            sl[axis] = slice(i, i + n)
            out += w * b[tuple(sl)]
        return out
    return conv1(conv1(img, ky, 0), kx, 1)


def conv2(img: np.ndarray, K: np.ndarray) -> np.ndarray:
    r0 = (K.shape[0] - 1) // 2
    r1 = (K.shape[1] - 1) // 2
    b = np.pad(img, ((r0, r0), (r1, r1)), mode="edge")
    out = np.zeros_like(img)
    h, w = img.shape
    for i in range(K.shape[0]):
        for j in range(K.shape[1]):
            k = K[i, j]
            if k != 0.0:
                out += k * b[i:i + h, j:j + w]
    return out


def fit_levels_residual(obs: np.ndarray, model: np.ndarray, w: np.ndarray):
    """Solve obs ~ p + q*model on the weighted support; return (rms, p, q)."""
    sel = w.ravel() > 0
    o = obs.ravel()[sel].astype(np.float64)
    m = model.ravel()[sel].astype(np.float64)
    n = len(o)
    if n < 50:
        return 1e9, 0.0, 0.0
    A = np.stack([np.ones(n), m], axis=1)
    sol, *_ = np.linalg.lstsq(A, o, rcond=None)
    r = o - (sol[0] + sol[1] * m)
    return float(np.sqrt((r * r).mean())), float(sol[0]), float(sol[1])


# --------------------------------------------------------------------------- #
def nelder_mead(f, x0, step, maxiter=800, tol=1e-10):
    n = len(x0)
    sim = [np.asarray(x0, float)]
    for i in range(n):
        p = np.asarray(x0, float).copy()
        p[i] += step[i]
        sim.append(p)
    sim = np.array(sim)
    val = np.array([f(p) for p in sim])
    for _ in range(maxiter):
        o = np.argsort(val)
        sim, val = sim[o], val[o]
        if abs(val[-1] - val[0]) <= tol * (abs(val[0]) + abs(val[-1]) + 1e-12):
            break
        cen = sim[:-1].mean(axis=0)
        xr = cen + (cen - sim[-1]); fr = f(xr)
        if fr < val[0]:
            xe = cen + 2.0 * (cen - sim[-1]); fe = f(xe)
            sim[-1], val[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < val[-2]:
            sim[-1], val[-1] = xr, fr
        else:
            xc = cen + 0.5 * (sim[-1] - cen); fc = f(xc)
            if fc < val[-1]:
                sim[-1], val[-1] = xc, fc
            else:
                sim[1:] = sim[0] + 0.5 * (sim[1:] - sim[0])
                for i in range(1, n + 1):
                    val[i] = f(sim[i])
    o = np.argsort(val)
    return sim[o][0], float(val[o][0])
