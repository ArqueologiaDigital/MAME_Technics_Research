"""Forward model: native 640x240 bitmap -> observed (blurred, upscaled) pixels.

The capture chain is modelled as

    observed(x, y) = bg(x, y) - amp * (I * P)( (x-ax)/bx, (y-ay)/by )

i.e. an affine map from native LCD pixels to captured pixels, with a separable
point-spread function P applied in NATIVE units.  Everything is linear in the
native bitmap I, which is what lets a whole row be fitted jointly as a sum of
overlapping glyphs (see rowdp).

The operator is materialised as two resampling matrices

    Cx : (n_real_x, n_native_x)
    Cy : (n_real_y, n_native_y)          model = Cy @ I @ Cx.T

built by supersampling the native grid by S, convolving with the PSF taps on
that fine grid, and sampling at the fine coordinate of each real pixel.  Both
matrices are linear in their PSF tap vector, so the taps can be fitted by
ordinary least squares (psf.py) rather than assumed Gaussian -- which matters,
because composite horizontal smear is not Gaussian: it has a one-sided tail.
"""
import numpy as np

S = 8   # supersampling factor for the native grid


def normalise_taps(k, S=S):
    """Scale taps so the native-grid partition of unity holds (sum == S).

    A native pixel is a box of width 1, so the effective kernel is box1 * PSF,
    which integrates to 1 and tiles the line; on a grid of spacing 1/S that
    means the taps must sum to S.  Without this the operator loses DC and the
    fitted amplitude silently absorbs a scale error.
    """
    k = np.asarray(k, dtype=np.float64)
    return k * (S / k.sum())


def gauss_taps(sigma, half=None, S=S):
    """box1 (X) Gaussian(sigma) sampled on the fine grid, native units."""
    if half is None:
        half = int(np.ceil(4.0 * sigma * S)) + S
    t = np.arange(-half, half + 1, dtype=np.float64) / S
    k = np.exp(-0.5 * (t / max(sigma, 1e-6)) ** 2)
    box = np.ones(S)
    k = np.convolve(k, box, mode="same")
    return normalise_taps(k, S)


def resample_matrix(n_native, n_real, a, b, taps, S=S):
    """Matrix C with model_real = C @ native_signal.

    a, b   : real = a + b * native
    taps   : PSF taps on the fine grid (spacing 1/S native px), centred
    """
    taps = np.asarray(taps, dtype=np.float64)
    half = (len(taps) - 1) // 2
    real_idx = np.arange(n_real, dtype=np.float64)
    # fine-grid coordinate of each real pixel centre
    fine = (real_idx - a) / b * S
    f0 = np.floor(fine).astype(np.int64)
    w1 = fine - f0
    w0 = 1.0 - w1
    # fine index of native sample j is j*S; a tap at offset d contributes to
    # fine index j*S + d.  So contribution of native j to fine index p is
    # taps[p - j*S + half]  (when in range).
    C = np.zeros((n_real, n_native), dtype=np.float64)
    for p, w in ((f0, w0), (f0 + 1, w1)):
        # native j such that |p - j*S| <= half  ->  j in [(p-half)/S, (p+half)/S]
        jlo = np.ceil((p - half) / S).astype(np.int64)
        jhi = np.floor((p + half) / S).astype(np.int64)
        span = int((jhi - jlo).max()) + 1 if len(p) else 0
        for k in range(span):
            j = jlo + k
            ok = (j >= 0) & (j < n_native) & (j <= jhi)
            if not ok.any():
                continue
            d = p[ok] - j[ok] * S + half
            good = (d >= 0) & (d < len(taps))
            rows = np.nonzero(ok)[0][good]
            C[rows, j[ok][good]] += w[ok][good] * taps[d[good]]
    return C


def taps_basis(n_native, n_real, a, b, ntaps, S=S):
    """Per-tap resampling matrices: B[t] = dC/d(taps[t]).

    Lets C = sum_t taps[t] * B[t], so any least-squares problem that is linear
    in C is linear in the taps.  Shape (ntaps, n_real, n_native).
    """
    B = np.zeros((ntaps, n_real, n_native), dtype=np.float64)
    for t in range(ntaps):
        e = np.zeros(ntaps)
        e[t] = 1.0
        B[t] = resample_matrix(n_native, n_real, a, b, e, S=S)
    return B


class Geometry:
    """Affine native->real map plus the two PSF tap vectors."""

    def __init__(self, ax, bx, ay, by, hx=None, hy=None):
        self.ax, self.bx, self.ay, self.by = float(ax), float(bx), float(ay), float(by)
        self.hx = np.asarray(hx if hx is not None else gauss_taps(1.0))
        self.hy = np.asarray(hy if hy is not None else gauss_taps(0.35))

    def to_dict(self):
        return dict(ax=self.ax, bx=self.bx, ay=self.ay, by=self.by,
                    hx=self.hx.tolist(), hy=self.hy.tolist(), S=S)

    @staticmethod
    def from_dict(d):
        return Geometry(d["ax"], d["bx"], d["ay"], d["by"],
                        np.array(d["hx"]), np.array(d["hy"]))

    def real_x(self, nx):
        return self.ax + self.bx * np.asarray(nx, dtype=float)

    def real_y(self, ny):
        return self.ay + self.by * np.asarray(ny, dtype=float)

    def Cx(self, nx0, nx1, rx0, rx1):
        """Columns operator for native columns [nx0,nx1) -> real columns [rx0,rx1)."""
        return resample_matrix(nx1 - nx0, rx1 - rx0,
                               self.ax + self.bx * nx0 - rx0, self.bx, self.hx)

    def Cy(self, ny0, ny1, ry0, ry1):
        return resample_matrix(ny1 - ny0, ry1 - ry0,
                               self.ay + self.by * ny0 - ry0, self.by, self.hy)
