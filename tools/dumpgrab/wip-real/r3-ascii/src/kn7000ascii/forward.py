"""Forward model: native 5x7 bitmap -> what the capture chain actually shows.

The chain is: the LCD raster is a piecewise-constant image (one value per native
pixel); it is scanned out as analog composite, which band-limits it; the grabber
samples that on its own pixel grid.  So the honest model of a captured pixel is

    captured(u,v) = SUM_over_native_pixels  w_y(v,m) * w_x(u,n) * native(m,n)

with w a *separable, exact* box-into-Gaussian weight:

    w_x(u,n) = Phi((X0 + sx*(n+1) - u)/sigma_x) - Phi((X0 + sx*n - u)/sigma_x)

i.e. the Gaussian point-spread integrated over the capture-domain extent of one
native pixel.  No resampling approximation, no "blur then scale" ordering
mistake, and sub-pixel grid offsets fall out for free because X0 is a float.

Two parameters carry all the damage: sigma_x and sigma_y in CAPTURE pixels.
They are fitted per frame in `psf.py` against cells whose content is known
without any oracle.
"""
from __future__ import annotations

import math
import numpy as np

SQRT2 = math.sqrt(2.0)


def _phi(z):
    from scipy.special import erf  # noqa
    return 0.5 * (1.0 + erf(z / SQRT2))


def _phi_np(z):
    # normal CDF without scipy (not installed everywhere): math.erf is scalar,
    # so use the vectorised Abramowitz-Stegun-free route via np.vectorize-free
    # tanh approximation?  No -- accuracy matters.  numpy has no erf, but the
    # error function is available through np.math? It is not.  Use a high
    # accuracy rational approximation (Cody), max abs error < 1.2e-7.
    z = np.asarray(z, dtype=np.float64)
    t = 1.0 / (1.0 + 0.2316419 * np.abs(z) / SQRT2)
    d = (0.3989422804014327) * np.exp(-(z * z) / 2.0)
    p = d * t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 +
                 t * (-1.821255978 + t * 1.330274429))))
    return np.where(z >= 0, 1.0 - p, p)


try:
    from scipy.special import erf as _erf  # type: ignore

    def phi(z):
        return 0.5 * (1.0 + _erf(np.asarray(z, dtype=np.float64) / SQRT2))
except Exception:      # pragma: no cover - scipy is optional
    phi = _phi_np


def box_weights(n_native: int, origin: float, scale: float,
                sigma: float, u: np.ndarray) -> np.ndarray:
    """(len(u), n_native) weight matrix.  Column n is the native pixel whose
    capture-domain extent is [origin + scale*n, origin + scale*(n+1))."""
    edges = origin + scale * np.arange(n_native + 1, dtype=np.float64)
    z = (edges[None, :] - u[:, None]) / max(sigma, 1e-3)
    c = phi(z)
    return c[:, 1:] - c[:, :-1]


class CellRenderer:
    """Renders a native glyph, in place inside its native neighbourhood, onto
    the capture pixel grid of one cell window."""

    def __init__(self, grid, sigma_x: float, sigma_y: float,
                 pad_cells: int = 1, pad_rows: int = 1,
                 nat_px: int = 6, nat_py: int = 9,
                 nat_gw: int = 5, nat_gh: int = 7,
                 core_mx: float = 0.12, core_my: float = 0.05):
        self.g = grid
        self.sx = grid.px / nat_px          # capture px per native px, horizontal
        self.sy = grid.py / nat_py
        self.sigma_x = max(float(sigma_x), 0.05)
        self.sigma_y = max(float(sigma_y), 0.05)
        self.pad_cells = pad_cells
        self.pad_rows = pad_rows
        self.npx, self.npy, self.ngw, self.ngh = nat_px, nat_py, nat_gw, nat_gh
        self.nw = nat_px * (1 + 2 * pad_cells)
        self.nh = nat_py * (1 + 2 * pad_rows)
        # fixed patch size so every cell yields the same shape
        self.NU = int(math.ceil(self.nw * self.sx)) + 2
        self.NV = int(math.ceil(self.nh * self.sy)) + 2
        # the sub-rectangle actually compared: the centre cell plus a small
        # margin.  Outside it the model would need neighbours we may not know.
        cu = int(round(pad_cells * grid.px))
        cv = int(round(pad_rows * grid.py))
        mu = int(round(core_mx * grid.px))
        mv = int(round(core_my * grid.py))
        self.core = (slice(max(cv - mv, 0), min(cv + int(round(grid.py)) + mv, self.NV)),
                     slice(max(cu - mu, 0), min(cu + int(round(grid.px)) + mu, self.NU)))

    # -- capture-pixel window for cell (r, i) ------------------------------ #
    def window(self, r: int, i: int):
        cx = self.g.cell_x(r, i)
        cy = self.g.cell_y(r)
        x_lo = cx - self.pad_cells * self.g.px
        y_lo = cy - self.pad_rows * self.g.py
        u0 = int(math.floor(x_lo))
        v0 = int(math.floor(y_lo))
        return u0, u0 + self.NU, v0, v0 + self.NV, x_lo, y_lo

    def weights(self, r: int, i: int):
        u0, u1, v0, v1, x_lo, y_lo = self.window(r, i)
        u = np.arange(u0, u1, dtype=np.float64) + 0.5
        v = np.arange(v0, v1, dtype=np.float64) + 0.5
        Wx = box_weights(self.nw, x_lo, self.sx, self.sigma_x, u)
        Wy = box_weights(self.nh, y_lo, self.sy, self.sigma_y, v)
        return Wx, Wy, (u0, u1, v0, v1)

    def render(self, Wx, Wy, native_canvas):
        """native_canvas (nh, nw) float -> (nv, nu) capture patch."""
        return Wy @ native_canvas @ Wx.T

    def canvas(self, centre_bmp, left_bmp=None, right_bmp=None,
               up_bmp=None, down_bmp=None):
        """Assemble the native neighbourhood.  Missing neighbours are blank."""
        c = np.zeros((self.nh, self.nw), np.float64)
        oy = self.pad_rows * self.npy
        ox = self.pad_cells * self.npx
        c[oy:oy + self.ngh, ox:ox + self.ngw] = centre_bmp
        if left_bmp is not None and self.pad_cells:
            c[oy:oy + self.ngh, ox - self.npx:ox - self.npx + self.ngw] = left_bmp
        if right_bmp is not None and self.pad_cells:
            c[oy:oy + self.ngh, ox + self.npx:ox + self.npx + self.ngw] = right_bmp
        if up_bmp is not None and self.pad_rows:
            c[oy - self.npy:oy - self.npy + self.ngh, ox:ox + self.ngw] = up_bmp
        if down_bmp is not None and self.pad_rows:
            c[oy + self.npy:oy + self.npy + self.ngh, ox:ox + self.ngw] = down_bmp
        return c


def znorm_rows(X: np.ndarray) -> np.ndarray:
    X = X.astype(np.float64)
    X = X - X.mean(axis=1, keepdims=True)
    n = np.sqrt((X * X).sum(axis=1, keepdims=True))
    return X / np.maximum(n, 1e-12)
