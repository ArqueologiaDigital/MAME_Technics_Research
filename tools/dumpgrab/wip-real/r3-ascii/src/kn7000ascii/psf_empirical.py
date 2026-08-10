"""EMPIRICAL point-spread, fitted from the address column -- no Gaussian assumed.

A composite chain is not a Gaussian.  It is a chroma notch, a band-limit, a
resample and whatever the grabber's scaler does, and the result rings.  Trying
to summarise that with one sigma costs most of the glyph separability: measured
on the real frame, a fitted Gaussian left the 16 hex templates a median NCC
margin of 0.017, i.e. indistinguishable.

So fit the kernel itself.  Model one native pixel as a delta at its capture-
domain centre and let a separable pair of free kernels carry everything else:

    obs(v,u)  =  SUM_m SUM_n  Ky(v + 0.5 - Yc(m)) * Kx(u + 0.5 - Xc(n)) * N(m,n)
    Xc(n) = x0 + sx*(n + 0.5)          sx = px / 6
    Yc(m) = y0 + sy*(m + 0.5)          sy = py / 9

Kx and Ky are piecewise-linear on a fixed knot grid, so the model is LINEAR in
the knot values and alternating least squares solves it exactly, one direction
at a time.  Second-difference regularisation keeps it from fitting noise.

TRAINING DATA IS FREE AND ORACLE-FREE: the 8 address cells of all 16 rows.
Their content follows from the page base, and the page base follows from the
ladder (cell 6 is hex(row), cell 7 is '0', cells 0..5 are constant down the
column) -- never from a ROM.  `bootstrap_base` does that vote.
"""
from __future__ import annotations

import numpy as np

from .geometry_ascii import ROW

HEXC = "0123456789ABCDEF"


def hat_design(offsets: np.ndarray, knots: np.ndarray) -> np.ndarray:
    """(N, K) piecewise-linear basis evaluated at `offsets`."""
    K = len(knots)
    h = knots[1] - knots[0]
    B = np.zeros((len(offsets), K))
    t = (offsets - knots[0]) / h
    i0 = np.floor(t).astype(int)
    f = t - i0
    ok = (i0 >= 0) & (i0 < K - 1)
    idx = np.nonzero(ok)[0]
    B[idx, i0[idx]] = 1 - f[idx]
    B[idx, i0[idx] + 1] = f[idx]
    edge = (i0 == K - 1) & (np.abs(f) < 1e-9)
    B[np.nonzero(edge)[0], K - 1] = 1.0
    return B


class SeparablePSF:
    def __init__(self, knots_x: np.ndarray, kx: np.ndarray,
                 knots_y: np.ndarray, ky: np.ndarray):
        self.knots_x, self.kx = knots_x, kx
        self.knots_y, self.ky = knots_y, ky

    def matrices(self, u: np.ndarray, Xc: np.ndarray,
                 v: np.ndarray, Yc: np.ndarray):
        Bx = hat_design((u[:, None] - Xc[None, :]).ravel(), self.knots_x)
        Mx = (Bx @ self.kx).reshape(len(u), len(Xc))
        By = hat_design((v[:, None] - Yc[None, :]).ravel(), self.knots_y)
        My = (By @ self.ky).reshape(len(v), len(Yc))
        return Mx, My

    def render(self, native: np.ndarray, x_off: float, sx: float,
               y_off: float, sy: float, u: np.ndarray, v: np.ndarray):
        """native (nh, nw); its pixel (m, n) centre sits at
        (y_off + sy*(m+0.5), x_off + sx*(n+0.5))."""
        Xc = x_off + sx * (np.arange(native.shape[1]) + 0.5)
        Yc = y_off + sy * (np.arange(native.shape[0]) + 0.5)
        Mx, My = self.matrices(u, Xc, v, Yc)
        return My @ native @ Mx.T

    def as_dict(self):
        return {"knots_x": self.knots_x.tolist(), "kx": self.kx.tolist(),
                "knots_y": self.knots_y.tolist(), "ky": self.ky.tolist()}

    @classmethod
    def from_dict(cls, d):
        return cls(np.array(d["knots_x"]), np.array(d["kx"]),
                   np.array(d["knots_y"]), np.array(d["ky"]))

    @classmethod
    def gaussian(cls, sigma_x, sigma_y, sx, sy, half_x=8.0, half_y=6.0, step=0.25):
        kx_t = np.arange(-half_x, half_x + step / 2, step)
        ky_t = np.arange(-half_y, half_y + step / 2, step)
        kx = np.exp(-0.5 * (kx_t / sigma_x) ** 2) * sx / (sigma_x * np.sqrt(2 * np.pi))
        ky = np.exp(-0.5 * (ky_t / sigma_y) ** 2) * sy / (sigma_y * np.sqrt(2 * np.pi))
        return cls(kx_t, kx, ky_t, ky)


def _d2(K):
    D = np.zeros((K - 2, K))
    for i in range(K - 2):
        D[i, i] = 1.0; D[i, i + 1] = -2.0; D[i, i + 2] = 1.0
    return D


class PSFFitter:
    """Alternating least squares for (Kx, Ky) on a set of labelled patches."""

    def __init__(self, half_x=9.0, half_y=6.0, step=0.5, lam=2e-3):
        self.knots_x = np.arange(-half_x, half_x + step / 2, step)
        self.knots_y = np.arange(-half_y, half_y + step / 2, step)
        self.lam = lam

    def fit(self, patches, iters=6, init: SeparablePSF = None):
        """patches: list of (obs2d, native2d, x_off, sx, y_off, sy, u, v)."""
        kx = (init.kx.copy() if init is not None and len(init.kx) == len(self.knots_x)
              else np.exp(-0.5 * (self.knots_x / 1.5) ** 2))
        ky = (init.ky.copy() if init is not None and len(init.ky) == len(self.knots_y)
              else np.exp(-0.5 * (self.knots_y / 1.0) ** 2))
        Dx, Dy = _d2(len(kx)), _d2(len(ky))
        pre = []
        for (obs, N, xo, sx, yo, sy, u, v) in patches:
            Xc = xo + sx * (np.arange(N.shape[1]) + 0.5)
            Yc = yo + sy * (np.arange(N.shape[0]) + 0.5)
            Bx = hat_design((u[:, None] - Xc[None, :]).ravel(), self.knots_x
                            ).reshape(len(u), len(Xc), len(self.knots_x))
            By = hat_design((v[:, None] - Yc[None, :]).ravel(), self.knots_y
                            ).reshape(len(v), len(Yc), len(self.knots_y))
            pre.append((obs, N, Bx, By))
        for it in range(iters):
            # --- solve Kx given Ky ---
            A = []; b = []
            for (obs, N, Bx, By) in pre:
                My = By @ ky                       # (nv, nm)
                G = My @ N                         # (nv, nn)
                # design[v,u,k] = sum_n G[v,n] * Bx[u,n,k]
                D = np.einsum("vn,unk->vuk", G, Bx).reshape(-1, len(kx))
                o = obs.ravel()
                D = D - D.mean(axis=0, keepdims=True)
                o = o - o.mean()
                A.append(D); b.append(o)
            A = np.concatenate(A); b = np.concatenate(b)
            R = self.lam * (np.abs(A).mean() + 1e-9) * len(A) ** 0.5 * Dx
            kx = np.linalg.lstsq(np.vstack([A, R]),
                                 np.concatenate([b, np.zeros(R.shape[0])]),
                                 rcond=None)[0]
            # --- solve Ky given Kx ---
            A = []; b = []
            for (obs, N, Bx, By) in pre:
                Mx = Bx @ kx                       # (nu, nn)
                G = N @ Mx.T                       # (nm, nu)
                D = np.einsum("mu,vmk->vuk", G, By).reshape(-1, len(ky))
                o = obs.ravel()
                D = D - D.mean(axis=0, keepdims=True)
                o = o - o.mean()
                A.append(D); b.append(o)
            A = np.concatenate(A); b = np.concatenate(b)
            R = self.lam * (np.abs(A).mean() + 1e-9) * len(A) ** 0.5 * Dy
            ky = np.linalg.lstsq(np.vstack([A, R]),
                                 np.concatenate([b, np.zeros(R.shape[0])]),
                                 rcond=None)[0]
            # fix the scale ambiguity
            s = np.abs(ky).sum()
            if s > 1e-9:
                ky = ky / s; kx = kx * s
        return SeparablePSF(self.knots_x, kx, self.knots_y, ky)
