"""Joint whole-row decoding in the blurred domain.

A per-cell matcher throws away the fact that neighbouring characters bleed into
each other; at the horizontal blur measured on the real capture (sigma 1.41
native px against a 6 px pitch) that bleed carries a large fraction of every
cell's energy, and it is *informative* -- the smear from cell c-1 is evidence
about cell c-1, so predicting and removing it sharpens cell c.

The row is modelled as one linear superposition

    observed = BG - amp * sum_c  T[c][k_c]

with T[c][k] the exact 5x7 glyph k placed at cell c and pushed through the
measured PSF, and BG the panel's own chrome (border and the black lines at
native x=88 / y=53) through the same PSF.  Minimising the squared residual over
the whole class sequence expands into unary terms plus pairwise overlap terms
that die out beyond lag 2, i.e. a Markov chain: Viterbi solves it exactly and
forward-backward gives a per-nibble posterior over the 16 classes.
"""
import numpy as np

from . import layout as L
from .model import resample_matrix


class RowRenderer:
    """Pre-rendered blurred glyph templates and chrome for one text row."""

    def __init__(self, g, row, ncols=57, margin_x=5, margin_y=4,
                 scene_x0=80, scene_x1=None, guard_x=(6, 2), guard_y=(1, 1)):
        self.g, self.row, self.ncols = g, row, ncols
        font = L.load_font()
        if scene_x1 is None:
            scene_x1 = L.cell_x(ncols) + L.PX      # first unmodelled cell
        self.nx0, self.nx1 = scene_x0, scene_x1
        self.ny0 = L.cell_y(row) - margin_y
        self.ny1 = L.cell_y(row) + L.GH + margin_y

        self.rx0 = int(np.ceil(g.real_x(self.nx0 + guard_x[0]))) + 1
        self.rx1 = int(np.floor(g.real_x(self.nx1 - guard_x[1]))) - 1
        self.ry0 = int(np.ceil(g.real_y(self.ny0 + guard_y[0]))) + 1
        self.ry1 = int(np.floor(g.real_y(self.ny1 - guard_y[1]))) - 1
        self.W = self.rx1 - self.rx0
        self.H = self.ry1 - self.ry0

        self.Cy = resample_matrix(self.ny1 - self.ny0, self.H,
                                  g.ay + g.by * self.ny0 - self.ry0, g.by, g.hy)
        base = L.panel_base(self.ny0, self.ny1, self.nx0, self.nx1)
        Cxfull = resample_matrix(self.nx1 - self.nx0, self.W,
                                 g.ax + g.bx * self.nx0 - self.rx0, g.bx, g.hx)
        self.chrome = self.Cy @ base @ Cxfull.T      # blurred panel background

        gy = margin_y
        self.win, self.T = [], []
        for c in range(ncols):
            nx0 = L.cell_x(c) - margin_x
            nx1 = L.cell_x(c) + L.GW + margin_x
            a = max(int(np.floor(g.real_x(nx0))) - self.rx0, 0)
            b = min(int(np.ceil(g.real_x(nx1))) - self.rx0, self.W)
            Cx = resample_matrix(nx1 - nx0, b - a,
                                 g.ax + g.bx * nx0 - (self.rx0 + a), g.bx, g.hx)
            Ts = np.empty((L.NCLS, self.H, b - a))
            for k in range(L.NCLS):
                I = np.zeros((self.ny1 - self.ny0, nx1 - nx0))
                I[gy:gy + L.GH, margin_x:margin_x + L.GW] = font[k]
                Ts[k] = self.Cy @ I @ Cx.T
            self.win.append((a, b))
            self.T.append(Ts)
        self._gram = {}

    # --------------------------------------------------------------------
    def gram(self, c1, c2):
        key = (c1, c2)
        if key not in self._gram:
            a1, b1 = self.win[c1]
            a2, b2 = self.win[c2]
            lo, hi = max(a1, a2), min(b1, b2)
            if hi <= lo:
                G = np.zeros((L.NCLS, L.NCLS))
            else:
                A = self.T[c1][:, :, lo - a1:hi - a1].reshape(L.NCLS, -1)
                B = self.T[c2][:, :, lo - a2:hi - a2].reshape(L.NCLS, -1)
                G = A @ B.T
            self._gram[key] = G
        return self._gram[key]

    def observed(self, lum):
        return lum[self.ry0:self.ry1, self.rx0:self.rx1].astype(np.float64)

    def ink_of(self, classes):
        out = np.zeros((self.H, self.W))
        for c, k in enumerate(classes):
            if k is None:
                continue
            a, b = self.win[c]
            out[:, a:b] += self.T[c][k]
        return out

    def bg_basis(self):
        yy = np.linspace(-1, 1, self.H)[:, None] * np.ones((1, self.W))
        xx = np.ones((self.H, 1)) * np.linspace(-1, 1, self.W)[None, :]
        return [np.ones_like(yy), yy, xx]

    def fit_levels(self, lum, classes):
        """LSQ for [c0, cy, cx, c1] with a decoded class sequence."""
        O = self.observed(lum)
        M = self.chrome - L.INK_LEVEL * self.ink_of(classes)
        A = np.stack([c.ravel() for c in self.bg_basis()] + [M.ravel()], 1)
        coef, *_ = np.linalg.lstsq(A, O.ravel(), rcond=None)
        res = O.ravel() - A @ coef
        return coef, float(np.sqrt((res ** 2).mean()))

    def bg_and_amp(self, coef):
        b = self.bg_basis()
        bg = coef[0] * b[0] + coef[1] * b[1] + coef[2] * b[2] + coef[3] * self.chrome
        return bg, L.INK_LEVEL * coef[3]


# ------------------------------------------------------------------ DP ------
def default_candidates(ncols=57, addr_prefix=None, row=None):
    cand = []
    hexset = list(range(16))
    for c in range(ncols):
        if c in L.BLANK_CELLS:
            cand.append([L.CLS_SPACE])
        elif c in L.HYPHEN_CELLS:
            cand.append([L.CLS_HYPHEN])
        elif addr_prefix is not None and c < 6:
            cand.append([L.CLASSES.index(addr_prefix[c])])
        elif addr_prefix is not None and c == 6 and row is not None:
            cand.append([row])
        elif addr_prefix is not None and c == 7:
            cand.append([0])
        else:
            cand.append(hexset)
    return cand


NEG = -1e30


def _potentials(rr, ink, cand, scale, max_lag=2):
    ncols = rr.ncols
    unary = []
    for c in range(ncols):
        a, b = rr.win[c]
        e = ink[:, a:b].ravel()
        Tc = rr.T[c].reshape(L.NCLS, -1)
        u = (Tc * Tc).sum(1) - 2.0 * Tc @ e
        p = np.full(L.NCLS, NEG)
        p[cand[c]] = -scale * u[cand[c]]
        unary.append(p)
    pair1 = [-scale * 2.0 * rr.gram(c, c + 1) for c in range(ncols - 1)]
    pair2 = ([-scale * 2.0 * rr.gram(c, c + 2) for c in range(ncols - 2)]
             if max_lag >= 2 else [])
    return unary, pair1, pair2


def _trans(unary, pair1, pair2, c):
    t = unary[c][None, None, :] + pair1[c - 1][None, :, :]
    if c >= 2 and pair2:
        t = t + pair2[c - 2][:, None, :]
    return t


def _lse(M, axis):
    mx = np.max(M, axis=axis, keepdims=True)
    mx = np.where(np.isfinite(mx), mx, 0.0)
    return (mx + np.log(np.exp(np.clip(M - mx, -700, 0)).sum(axis=axis,
                                                            keepdims=True)
                        + 1e-300)).squeeze(axis)


def effective_noise(R, half_y=6, half_x=12):
    """Per-pixel residual sigma inflated by its own correlation area.

    The residual of a blurred image is NOT white: one PSF-sized blob covers
    many pixels, so treating each pixel as an independent sample makes the
    posterior absurdly sharp (every byte came out at confidence 1.000, errors
    included).  The integrated normalised autocovariance A is the number of
    pixels per independent sample; sigma_eff = rms * sqrt(A) restores a
    posterior whose confidence means something.  A == 1 for white noise.
    """
    R = R - R.mean()
    n = R.size
    F = np.fft.rfft2(R)
    ac = np.fft.irfft2(F * np.conj(F), s=R.shape).real / n
    if ac[0, 0] <= 0:
        return float(np.sqrt((R ** 2).mean())), 1.0
    rho = ac / ac[0, 0]
    ys = np.concatenate([np.arange(0, min(half_y, R.shape[0] // 2) + 1),
                         np.arange(R.shape[0] - min(half_y, R.shape[0] // 2), R.shape[0])])
    xs = np.concatenate([np.arange(0, min(half_x, R.shape[1] // 2) + 1),
                         np.arange(R.shape[1] - min(half_x, R.shape[1] // 2), R.shape[1])])
    A = float(np.abs(rho[np.ix_(np.unique(ys), np.unique(xs))]).sum())
    rms = float(np.sqrt((R ** 2).mean()))
    return rms * np.sqrt(max(A, 1.0)), A


def decode_row(rr, lum, coef, cand=None, noise=None, max_lag=2, posterior=True,
               classes_for_noise=None):
    """Viterbi + forward-backward over one text row.  Returns (seq, post)."""
    O = rr.observed(lum)
    bg, amp = rr.bg_and_amp(coef)
    ink = (bg - O) / amp
    if cand is None:
        cand = default_candidates(rr.ncols)
    if noise is None:
        ref = classes_for_noise
        if ref is None:
            ref = [int(np.argmax(-((rr.T[c] - ink[:, rr.win[c][0]:rr.win[c][1]])
                                   ** 2).sum((1, 2)))) for c in range(rr.ncols)]
        noise, _ = effective_noise(bg - amp * rr.ink_of(ref) - O)
    scale = 1.0 / (2.0 * (noise / amp) ** 2)
    unary, pair1, pair2 = _potentials(rr, ink, cand, scale, max_lag)

    K, ncols = L.NCLS, rr.ncols
    V = np.full((K, K), NEG)
    V[0, :] = unary[0]
    back = np.zeros((ncols, K, K), np.int16)
    for c in range(1, ncols):
        M = V[:, :, None] + _trans(unary, pair1, pair2, c)
        idx = np.argmax(M, axis=0)
        V = np.take_along_axis(M, idx[None], 0)[0]
        back[c] = idx
    kp2, kp1 = np.unravel_index(np.argmax(V), V.shape)
    seq = [0] * ncols
    seq[ncols - 1] = int(kp1)
    if ncols >= 2:
        seq[ncols - 2] = int(kp2)
    for c in range(ncols - 1, 1, -1):
        kk = int(back[c][kp2, kp1])
        seq[c - 2] = kk
        kp2, kp1 = kk, kp2
    if not posterior:
        return seq, None

    F = [None] * ncols
    f = np.full((K, K), NEG)
    f[0, :] = unary[0]
    F[0] = f
    for c in range(1, ncols):
        F[c] = _lse(F[c - 1][:, :, None] + _trans(unary, pair1, pair2, c), 0)
    B = [None] * ncols
    B[ncols - 1] = np.zeros((K, K))
    for c in range(ncols - 1, 0, -1):
        B[c - 1] = _lse(_trans(unary, pair1, pair2, c) + B[c][None, :, :], 2)
    post = []
    for c in range(ncols):
        Lc = F[c] + B[c]
        Lc = np.where(np.isfinite(Lc), Lc, NEG)
        mx = Lc.max()
        w = np.exp(np.clip(Lc - mx, -700, 0)).sum(axis=0)
        s = w.sum()
        post.append(w / s if s > 0 else np.full(K, 1.0 / K))
    return seq, post
