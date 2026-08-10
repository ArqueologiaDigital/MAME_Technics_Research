#!/usr/bin/env python3
"""Bootstrapped geometry + PSF fit for a real composite capture.  Shared core.

The bootstrap exists because of a subtlety that is easy to get wrong: a cell can
only be scored if EVERY pixel that lands in it is explained by the model, and at
this blur a glyph bleeds well into its neighbours.  Scoring the layout's blank
separator cells while their neighbours are unknown therefore biases the fit --
the model says "paper" where the observation has a neighbour's ink.

So the fit is grown outwards from what is certain:

  round 0   cell 7 only: the row-index ladder 0..F, the one block of 16 labelled
            glyphs that needs no oracle.  Neighbours (cells 6 and 8) are unknown,
            so only the interior of the cell is scored.
  round 1   read cells 0..6 by 16-row consensus -> the whole address block is
            known and mutually adjacent; refit on all 128 glyphs.
  round 2+  decode the hex area with the current geometry, declare the decoded
            text "known", refit on all 16x57 cells, re-decode.  Iterate until the
            decoded text stops changing.

Round 2 is a self-consistency loop, not evidence: it can converge on a wrong
page.  What makes the result checkable is that the ladder, the separators and
(for this frame) an oracle are all scored *after* convergence.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

import realgeom as RG
from realgeom import (Affine, NativeGrid, bilinear, fit_levels_residual, gauss1,
                      load_font, nelder_mead, sepconv)


# --------------------------------------------------------------------------- #
def cell_mask(grid: NativeGrid, cells: List[Tuple[int, int]],
              shrink_left=0.0, shrink_right=0.0, shrink_top=0.0, shrink_bot=0.0):
    """Boolean weight over the native grid for a set of character cells."""
    S = grid.S
    m = np.zeros(grid.shape, bool)
    for (r, c) in cells:
        if not (grid.c0 <= c < grid.c1):
            continue
        y = (RG.CELL_Y0 + RG.CELL_H * r - grid.y0) * S
        x = (RG.CELL_X0 + RG.CELL_W * c - grid.x0) * S
        m[int(y + shrink_top * S):int(y + (RG.CELL_H - shrink_bot) * S),
          int(x + shrink_left * S):int(x + (RG.CELL_W - shrink_right) * S)] = True
    return m


def raster_text(grid: NativeGrid, font, text) -> np.ndarray:
    S = grid.S
    ink = np.zeros(grid.shape, np.float32)
    for r, row in enumerate(text):
        for c, ch in enumerate(row):
            # neighbours just outside the grid still bleed in, so render one cell
            # of margin either side rather than clipping hard at the grid edge
            if ch is None or not (grid.c0 - 1 <= c <= grid.c1):
                continue
            gy = (RG.CELL_Y0 + RG.CELL_H * r - grid.y0) * S
            gx = (RG.CELL_X0 + RG.CELL_W * c - grid.x0) * S
            g = np.kron(font[ch], np.ones((S, S), np.float32))
            y1 = min(gy + RG.GLYPH_H * S, ink.shape[0])
            x1 = min(gx + RG.GLYPH_W * S, ink.shape[1])
            y0s = max(gy, 0); x0s = max(gx, 0)
            if y1 <= y0s or x1 <= x0s:
                continue
            ink[y0s:y1, x0s:x1] = g[y0s - gy:y1 - gy, x0s - gx:x1 - gx]
    return ink


def mean_glyph(font):
    """The average of the 16 hex bitmaps.

    Used as the model for a cell whose character is not yet known.  Rendering an
    unknown cell as BLANK is the tempting alternative and it is biased: the model
    then says "paper" where the observation has a neighbour's ink, which pulls
    the fit.  The mean glyph is the unbiased prior -- it has the right DC and
    roughly the right column structure -- and it lets the layout's 105 blank
    separator cells, which span the FULL row width, contribute to the pitch.
    """
    return np.mean([font[c] for c in RG.HEXDIG], axis=0).astype(np.float32)


def scored_cells(text) -> List[Tuple[int, int]]:
    """Cells that are known AND whose horizontal neighbours are known too."""
    out = []
    R, C = len(text), len(text[0])
    for r in range(R):
        for c in range(C):
            if text[r][c] is None:
                continue
            if c > 0 and text[r][c - 1] is None:
                continue
            if c + 1 < C and text[r][c + 1] is None:
                continue
            out.append((r, c))
    return out


def fit(gray, grid, font, text, seed, sig0, maxiter=500, edge_shrink=None,
        cells=None, free=(1, 1, 1, 1, 1, 1, 1, 1)):
    """Nelder-Mead over (ax, shx, bx, ay, shy, by, sigma_x, sigma_y).

    `free` zeroes the step of a parameter to hold it fixed.  Holding ax while
    fitting on the 8-cell address block matters: that block spans 48 native px,
    so it constrains the pitch ten times less well than the panel edges do, and
    letting it move the pitch cost 0.6 % -- a third of a character cell of drift
    by the right-hand end of the row.
    """
    ink = raster_text(grid, font, text)
    if cells is None:
        cells = scored_cells(text)
    if edge_shrink is None:
        edge_shrink = (0.0, 0.0)
    w = cell_mask(grid, cells, shrink_left=edge_shrink[0], shrink_right=edge_shrink[1])
    S = grid.S

    def obj(p):
        aff = Affine(*p[:6])
        sx, sy = abs(p[6]), abs(p[7])
        if not (0.8 < aff.ax < 4.0 and 0.8 < aff.ay < 6.0):
            return 1e9
        if sx > 4 or sy > 4:
            return 1e9
        warp = grid.warp(gray, aff)
        model = sepconv(ink, gauss1(sy, S), gauss1(sx, S))
        return fit_levels_residual(warp, model, w)[0]

    x = list(np.asarray(seed.to_vec(), float)) + [sig0[0], sig0[1]]
    for st in ([0.006, 0.006, 0.9, 0.006, 0.006, 0.9, 0.25, 0.25],
               [0.0015, 0.0015, 0.25, 0.0015, 0.0015, 0.25, 0.08, 0.08],
               [0.0004, 0.0004, 0.06, 0.0004, 0.0004, 0.06, 0.02, 0.02]):
        st = [s * f for s, f in zip(st, free)]
        sub = [i for i, f in enumerate(free) if f]
        base = list(x)

        def obj_sub(v):
            p = list(base)
            for i, k in enumerate(sub):
                p[k] = v[i]
            return obj(p)
        v, val = nelder_mead(obj_sub, [x[k] for k in sub],
                             [st[k] for k in sub], maxiter=maxiter)
        for i, k in enumerate(sub):
            x[k] = v[i]
    return Affine(*x[:6]), abs(x[6]), abs(x[7]), float(val), int(w.sum())


# --------------------------------------------------------------------------- #
def cut_cell(gray, aff, r, c, S=4, ypad=0.0, xpad=0.0):
    ys = (np.arange(int(round((RG.CELL_H + 2 * ypad) * S))) + 0.5) / S - ypad
    xs = (np.arange(int(round((RG.CELL_W + 2 * xpad) * S))) + 0.5) / S - xpad
    X, Y = np.meshgrid(RG.CELL_X0 + RG.CELL_W * c + xs, RG.CELL_Y0 + RG.CELL_H * r + ys)
    U, V = aff.forward(X, Y)
    return bilinear(gray, U, V)


def cell_templates(font, sig_x, sig_y, S=4, classes="0123456789ABCDEF -",
                   ypad=0.0, xpad=0.0, context=None):
    """Blurred glyph templates on the same grid `cut_cell` produces.

    `context` (left_char, right_char) renders the horizontal neighbours too, so
    the template carries the same bleed the observation does.  With no context
    the neighbours are rendered as blank, which is what a naive matcher assumes
    and is measurably worse at this blur.
    """
    out = {}
    pad = 8
    H = (RG.CELL_H + 2 * pad) * S
    W = (RG.CELL_W + 2 * pad) * S
    for ch in classes:
        canvas = np.zeros((H, W), np.float32)
        def put(cc, dx):
            if cc is None or cc == " ":
                return
            g = np.kron(font[cc], np.ones((S, S), np.float32))
            y = pad * S
            x = (pad + dx) * S
            canvas[y:y + RG.GLYPH_H * S, x:x + RG.GLYPH_W * S] = g
        put(ch, 0)
        if context:
            put(context[0], -RG.CELL_W)
            put(context[1], RG.CELL_W)
        b = sepconv(canvas, gauss1(sig_y, S), gauss1(sig_x, S))
        y0 = int(round((pad - ypad) * S)); x0 = int(round((pad - xpad) * S))
        hh = int(round((RG.CELL_H + 2 * ypad) * S)); ww = int(round((RG.CELL_W + 2 * xpad) * S))
        out[ch] = b[y0:y0 + hh, x0:x0 + ww]
    return out


def znorm(p):
    p = np.asarray(p, np.float64).ravel()
    p = p - p.mean()
    n = np.sqrt((p * p).sum())
    return p / n if n > 1e-9 else p


def classify(patch, tmpl, allowed):
    # The observation is DARK ink on BRIGHT paper; the templates are ink=1 on 0.
    # Negating the patch puts both in the same polarity -- without this every NCC
    # comes out negative and argmax picks the WORST match (measured: the address
    # column decoded to all-'7' before this line existed).
    p = znorm(-np.asarray(patch, np.float64))
    keys = list(allowed)
    sc = np.array([p @ znorm(tmpl[k]) for k in keys])
    o = np.argsort(-sc)
    return keys[o[0]], float(sc[o[0]]), float(sc[o[0]] - sc[o[1]]), \
        {keys[i]: float(sc[i]) for i in o}


def decode_page(gray, aff, font, sig_x, sig_y, S=4, use_context=True,
                text_hint=None):
    """Classify all 16x57 cells.  Returns (text, ncc, margin)."""
    text = [[None] * RG.NHEXCOLS for _ in range(RG.NROWS)]
    ncc = np.zeros((RG.NROWS, RG.NHEXCOLS))
    marg = np.zeros((RG.NROWS, RG.NHEXCOLS))
    plain = cell_templates(font, sig_x, sig_y, S=S)
    for r in range(RG.NROWS):
        for c in range(RG.NHEXCOLS):
            allowed = RG.HEXDIG
            if c in RG.SPACE_CELLS:
                text[r][c] = " "; ncc[r, c] = 1.0; marg[r, c] = 1.0; continue
            if c == RG.DASH_CELL:
                text[r][c] = "-"; ncc[r, c] = 1.0; marg[r, c] = 1.0; continue
            tm = plain
            if use_context and text_hint is not None:
                lc = text_hint[r][c - 1] if c > 0 else None
                rc = text_hint[r][c + 1] if c + 1 < RG.NHEXCOLS else None
                tm = cell_templates(font, sig_x, sig_y, S=S, context=(lc, rc))
            patch = cut_cell(gray, aff, r, c, S=S)
            ch, s, m, _ = classify(patch, tm, allowed)
            text[r][c] = ch; ncc[r, c] = s; marg[r, c] = m
    return text, ncc, marg


def text_to_bytes(text):
    out = []
    for r in range(RG.NROWS):
        for i in range(16):
            c = RG.HEX_HI[i]
            hi, lo = text[r][c], text[r][c + 1]
            out.append(int(hi + lo, 16))
    return bytes(out)


# --------------------------------------------------------------------------- #
# round 0: align on the address block, with no oracle and no prefix
# --------------------------------------------------------------------------- #
def address_block_score(gray, aff, font, sig_x, sig_y, S=4, tmpl=None):
    """A geometry score computed only from what the address block MUST look like.

    Two oracle-free terms:
      ladder   -- the row address is base + 0x10*r, so cell 6 spells 0,1,...,F
                  down the 16 rows (cell 7, the low nibble, is always '0').  Its
                  NCC against the corresponding template is a direct alignment
                  score.  NB cell 6, not cell 7: getting that wrong shifts the
                  whole read by one digit and was worth a debugging session.
      constant -- cells 0..5 and cell 7 hold the SAME (unknown) glyph in every
                  row, so the mean NCC of each against its own column average
                  measures alignment without knowing which glyph it is.

    Both are maximised only when the grid is on the characters; a whole-cell
    shift destroys the ladder term, and a sub-cell shift destroys both.
    """
    if tmpl is None:
        tmpl = cell_templates(font, sig_x, sig_y, S=S)
    lad = 0.0
    for r in range(RG.NROWS):
        p = znorm(-cut_cell(gray, aff, r, RG.LADDER_CELL, S=S))
        lad += float(p @ znorm(tmpl[RG.HEXDIG[r]]))
    lad /= RG.NROWS
    const = 0.0
    for c in RG.CONST_CELLS:
        ps = np.stack([znorm(-cut_cell(gray, aff, r, c, S=S)) for r in range(RG.NROWS)])
        mu = znorm(ps.mean(axis=0))
        const += float((ps @ mu).mean())
    const /= len(RG.CONST_CELLS)
    return lad, const


def fit_address_block(gray, font, seed, sig0=(0.9, 0.45), S=4, verbose=False):
    def obj(p):
        aff = Affine(p[0], p[1], p[2], p[3], p[4], p[5])
        sx, sy = abs(p[6]), abs(p[7])
        if not (0.8 < aff.ax < 4.0 and 0.8 < aff.ay < 6.0) or sx > 4 or sy > 4:
            return 1e9
        tmpl = cell_templates(font, sx, sy, S=S)
        lad, const = address_block_score(gray, aff, font, sx, sy, S=S, tmpl=tmpl)
        return -(lad + const)

    best, bestv = None, 1e18
    # coarse scan over the horizontal phase: the hex area's ink pattern repeats
    # every 3 cells, so a purely local search can lock one whole byte to the left
    for dbx in np.arange(-2.0, 2.01, 0.5):
        p = list(seed.to_vec()) + [sig0[0], sig0[1]]
        p[2] += dbx * seed.ax * RG.CELL_W / 2.0
        v = obj(p)
        if v < bestv:
            best, bestv = p, v
    x = best
    for st in ([0.004, 0.003, 0.7, 0.004, 0.003, 0.7, 0.2, 0.2],
               [0.001, 0.001, 0.2, 0.001, 0.001, 0.2, 0.06, 0.06],
               [0.0003, 0.0003, 0.05, 0.0003, 0.0003, 0.05, 0.02, 0.02]):
        x, v = nelder_mead(obj, list(x), st, maxiter=700)
    aff = Affine(*x[:6])
    sx, sy = abs(x[6]), abs(x[7])
    lad, const = address_block_score(gray, aff, font, sx, sy, S=S)
    return aff, sx, sy, lad, const
