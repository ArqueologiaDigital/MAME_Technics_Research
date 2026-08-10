"""Geometry fit: find the affine native->real map from the frame's own structure.

Nothing here needs to know what the page says.  Stage 1 locates the 16 text
rows from the vertical ink comb; stage 2 locates the character grid from the
KNOWN pattern of blank cells (18 of the 76 columns are always spaces), which is
a matched filter that cannot be fooled by content.  Stage 3 refines all four
parameters against the rendered model once a PSF exists (psf.refine_geometry).
"""
import numpy as np
from PIL import Image

from . import layout as L
from .model import Geometry


def load_frame(path):
    """(H,W,3) float32 RGB, and its luma."""
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    return rgb, lum


def content_bbox(lum, thresh=16.0):
    """Bounding box of non-black content -- the LCD raster inside the capture."""
    m = lum > thresh
    ys = np.nonzero(m.any(1))[0]
    xs = np.nonzero(m.any(0))[0]
    return int(xs[0]), int(xs[-1]), int(ys[0]), int(ys[-1])


def coarse_from_bbox(lum):
    """Affine map from the raster bounding box alone.

    The firmware fills the whole 640x240 LCD, so the visible content box IS the
    raster.  This is a good enough seed (sub-pixel refinement follows) and it is
    completely independent of the text.
    """
    x0, x1, y0, y1 = content_bbox(lum)
    bx = (x1 - x0 + 1) / L.NAT_W
    by = (y1 - y0 + 1) / L.NAT_H
    return Geometry(x0, bx, y0, by)


def row_comb(lum, g, pad=2):
    """Ink profile over the text block, and the 16 row centres it implies."""
    ry0 = int(np.floor(g.real_y(L.Y0 - 2)))
    ry1 = int(np.ceil(g.real_y(L.cell_y(L.NROWS - 1) + L.GH + 2)))
    rx0 = int(np.floor(g.real_x(L.cell_x(0))))
    rx1 = int(np.ceil(g.real_x(L.cell_x(L.NCOLS - 1) + L.GW)))
    band = lum[ry0:ry1, rx0:rx1]
    bg = np.percentile(band, 85)
    ink = np.clip(bg - band, 0, None).mean(1)
    return ry0, ink


def fit_rows(lum, g):
    """Least-squares fit of (ay, by) to the measured row comb.

    Model: the ink profile is periodic with period 9*by; its minima sit at the
    two-pixel inter-row gaps.  Rather than peak-picking, correlate against a
    rendered comb over a small (ay, by) grid -- robust to a row of all-zero
    bytes, which has less ink but the same geometry.
    """
    ry0, ink = row_comb(lum, g)
    n = len(ink)
    yy = np.arange(n) + ry0

    def score(ay, by):
        # expected ink template: 1 inside the 7 glyph rows, 0 in the 2-row gap
        ny = (yy - ay) / by
        phase = np.mod(ny - L.Y0, L.PY)
        t = ((phase >= 0.0) & (phase < L.GH)).astype(float)
        t -= t.mean()
        v = ink - ink.mean()
        d = np.linalg.norm(t) * np.linalg.norm(v)
        return float(t @ v / d) if d > 0 else -1.0

    best = None
    for by in np.arange(g.by - 0.06, g.by + 0.06, 0.002):
        for ay in np.arange(g.ay - 4.0, g.ay + 4.0, 0.1):
            s = score(ay, by)
            if best is None or s > best[0]:
                best = (s, ay, by)
    s, ay, by = best
    # local polish
    for _ in range(3):
        step_a, step_b = 0.02, 0.0004
        for da in (-step_a, 0, step_a):
            for db in (-step_b, 0, step_b):
                v = score(ay + da, by + db)
                if v > s:
                    s, ay, by = v, ay + da, by + db
    return ay, by, s


def fit_cols(lum, g):
    """Fit (ax, bx) with a matched filter on the 18 always-blank cells."""
    ry0 = int(np.floor(g.real_y(L.Y0)))
    ry1 = int(np.ceil(g.real_y(L.cell_y(L.NROWS - 1) + L.GH)))
    band = lum[ry0:ry1, :]
    bg = np.percentile(band, 85)
    ink = np.clip(bg - band, 0, None).mean(0)
    xx = np.arange(len(ink))

    blank = np.zeros(L.NCOLS, bool)
    blank[L.BLANK_CELLS] = True

    def score(ax, bx):
        nx = (xx - ax) / bx
        c = np.floor((nx - L.X0) / L.PX)
        inside = (c >= 0) & (c < L.NCOLS)
        cc = np.clip(c, 0, L.NCOLS - 1).astype(int)
        t = np.where(inside & ~blank[cc], 1.0, 0.0)
        t = np.where(inside, t, 0.0)
        sel = inside
        tv = t[sel] - t[sel].mean()
        iv = ink[sel] - ink[sel].mean()
        d = np.linalg.norm(tv) * np.linalg.norm(iv)
        return float(tv @ iv / d) if d > 0 else -1.0

    best = None
    for bx in np.arange(g.bx - 0.05, g.bx + 0.05, 0.001):
        for ax in np.arange(g.ax - 5.0, g.ax + 5.0, 0.1):
            s = score(ax, bx)
            if best is None or s > best[0]:
                best = (s, ax, bx)
    s, ax, bx = best
    for _ in range(4):
        for da in (-0.02, 0, 0.02):
            for db in (-0.0002, 0, 0.0002):
                v = score(ax + da, bx + db)
                if v > s:
                    s, ax, bx = v, ax + da, bx + db
    return ax, bx, s


def fit(lum, seed=None, verbose=False):
    g = seed or coarse_from_bbox(lum)
    ay, by, sy = fit_rows(lum, g)
    g = Geometry(g.ax, g.bx, ay, by, g.hx, g.hy)
    ax, bx, sx = fit_cols(lum, g)
    g = Geometry(ax, bx, ay, by, g.hx, g.hy)
    if verbose:
        print("geom: ax=%.3f bx=%.5f (ncc %.3f)  ay=%.3f by=%.5f (ncc %.3f)"
              % (ax, bx, sx, ay, by, sy))
    return g, dict(ncc_cols=sx, ncc_rows=sy)
