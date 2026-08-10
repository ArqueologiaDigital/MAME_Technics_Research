"""Measure the capture chain's point-spread function from the frame itself.

THE CALIBRATION ASSET.  Every dump frame prints 16 row addresses.  Whatever the
page is, character cell 6 of row r is the hex digit r -- so one frame contains
each of the 16 hex glyphs exactly once, labelled, at a known position; cell 7 is
always '0'; cells 8 and 9 are always spaces; cells 33 and 67 are hyphens.  Cell
7's whole neighbourhood is therefore known, which is what makes a blind
deconvolution unnecessary: the PSF falls out of ordinary least squares against
known ink, on every frame, with no oracle.

The scene model is a GREY-LEVEL native image, not a binary ink mask:

    native(y, x) = panel_base(y, x) - 128 * ink(y, x)
    observed     = c0 + cy*y + cx*x + c1 * PSF{ native }

`panel_base` carries the panel's own chrome, including the black lines at
native x=88 and y=53 that run 2 px from cell 0 and 2 px above row 0.  Fitting
without them inflated the horizontal sigma from 0.70 to 1.50 native px, because
the fit had to explain their smear with blur.

Two stages: bootstrap() grid-searches Gaussian sigmas and the affine map;
refine() then fits non-parametric taps, because composite smear is not Gaussian
and the tails are what drive the inter-character bleed the row fitter needs.
"""
import numpy as np

from . import layout as L
from .model import (Geometry, gauss_taps, resample_matrix, taps_basis,
                    normalise_taps, S)


# --------------------------------------------------------------- helpers ----
def ink_bitmap(cells_by_row, font, nx0, nx1, ny0, ny1):
    """Render known cells into a native 0/1 ink mask over [ny0,ny1) x [nx0,nx1)."""
    I = np.zeros((ny1 - ny0, nx1 - nx0), dtype=np.float64)
    for (r, c), k in cells_by_row.items():
        gx, gy = L.cell_x(c), L.cell_y(r)
        gl = font[k]
        ty0, tx0 = gy - ny0, gx - nx0
        ys0, ys1 = max(0, -ty0), min(L.GH, I.shape[0] - ty0)
        xs0, xs1 = max(0, -tx0), min(L.GW, I.shape[1] - tx0)
        if ys1 > ys0 and xs1 > xs0:
            I[ty0 + ys0:ty0 + ys1, tx0 + xs0:tx0 + xs1] += gl[ys0:ys1, xs0:xs1]
    return I


def scene(cells_by_row, font, nx0, nx1, ny0, ny1):
    """The full native grey-level scene: panel chrome minus text ink."""
    return (L.panel_base(ny0, ny1, nx0, nx1)
            - L.INK_LEVEL * ink_bitmap(cells_by_row, font, nx0, nx1, ny0, ny1))


def _design_bg(ry0, ry1, rx0, rx1):
    yy = np.linspace(-1, 1, ry1 - ry0)[:, None] * np.ones((1, rx1 - rx0))
    xx = np.ones((ry1 - ry0, 1)) * np.linspace(-1, 1, rx1 - rx0)[None, :]
    return [np.ones_like(yy), yy, xx]


def solve_linear(O, M, ry0, ry1, rx0, rx1):
    """LSQ for [c0, cy, cx, c1] in  O ~ c0 + cy*y + cx*x + c1*M."""
    cols = _design_bg(ry0, ry1, rx0, rx1) + [M]
    A = np.stack([c.ravel() for c in cols], 1)
    b = O.ravel()
    coef, *_ = np.linalg.lstsq(A, b, rcond=None)
    res = b - A @ coef
    return coef, float(res @ res)


def compass_search(f, x0, steps, shrink=0.5, min_frac=1e-3, max_iter=400):
    """Derivative-free compass (pattern) search.

    Steps shrink only when a whole pass finds no improvement, so an initial
    estimate that is one or two pixels out is still reached -- a geometric
    schedule that shrinks every pass cannot travel further than step/(1-shrink)
    and silently converges to the wrong sub-pixel phase, which is exactly how
    an early version of this fitter reported sigma_x = 1.41 on synthetic data
    whose true sigma was 1.10.
    """
    names = list(x0)
    cur = dict(x0)
    st = dict(steps)
    best = f(**cur)
    n = 0
    while n < max_iter and any(st[k] > min_frac * abs(steps[k]) for k in names):
        improved = False
        for k in names:
            for d in (-st[k], st[k]):
                trial = dict(cur)
                trial[k] = cur[k] + d
                v = f(**trial)
                n += 1
                if v < best - 1e-12:
                    best, cur, improved = v, trial, True
                    break
        if not improved:
            for k in names:
                st[k] *= shrink
    return best, cur


def obs_window(ax, bx, ay, by, nx, ny, guard=(6, 0, 6, 3)):
    """Real-pixel window for a scene window, inset by a guard in native px.

    The scene must extend past the observed window so that ink OUTSIDE the
    window still contributes its blur; conversely the observed window must stay
    away from scene edges, because beyond them the scene is unknown (the LCD
    behind the panel differs between firmware builds).  Tying the two together
    is what made the first fits chase unmodelled neighbours and inflate sigma.
    """
    gl, gr, gt, gb = guard
    nx0, nx1 = nx
    ny0, ny1 = ny
    return (int(np.ceil(ax + bx * (nx0 + gl))) + 1,
            int(np.floor(ax + bx * (nx1 - gr))) - 1,
            int(np.ceil(ay + by * (ny0 + gt))) + 1,
            int(np.floor(ay + by * (ny1 - gb))) - 1)


def calib_cells(addr_prefix=None, cmax=9):
    cells = {}
    for r in range(L.NROWS):
        for c, k in L.known_row_text(r, addr_prefix).items():
            if c <= cmax:
                cells[(r, c)] = k
    return cells


# ------------------------------------------------------------- bootstrap ----
def bootstrap(lum, g, addr_prefix=None, verbose=False):
    """Grid-search Gaussian sigmas and polish the affine map on cells 0..9.

    Without `addr_prefix` only cells 6..9 are known, so the window starts just
    right of cell 5; with it the whole address block is known ink.
    """
    font = L.load_font()
    if addr_prefix:
        nx0, nx1, guard = 80, L.cell_x(10) - 2, (6, 2, 6, 3)
    else:
        # only cells 6..9 are known; keep clear of cell 5 on the left and of
        # cell 10 on the right, both of which are unmodelled here
        nx0, nx1, guard = L.cell_x(6) - 4, L.cell_x(10) - 2, (7, 2, 6, 3)
    ny0, ny1 = L.cell_y(0) - 7, L.cell_y(L.NROWS - 1) + L.GH + 3
    cells = calib_cells(addr_prefix)
    if not addr_prefix:
        cells = {k: v for k, v in cells.items() if k[1] >= 6}
    V = scene(cells, font, nx0, nx1, ny0, ny1)

    def evaluate(ax, bx, ay, by, sx, sy):
        rx0, rx1, ry0, ry1 = obs_window(ax, bx, ay, by, (nx0, nx1), (ny0, ny1), guard)
        Cx = resample_matrix(nx1 - nx0, rx1 - rx0, ax + bx * nx0 - rx0, bx, gauss_taps(sx))
        Cy = resample_matrix(ny1 - ny0, ry1 - ry0, ay + by * ny0 - ry0, by, gauss_taps(sy))
        O = lum[ry0:ry1, rx0:rx1].astype(np.float64)
        coef, ss = solve_linear(O, Cy @ V @ Cx.T, ry0, ry1, rx0, rx1)
        return ss / O.size, coef

    def obj(ax, bx, ay, by, sx, sy):
        if not (0.05 <= sx <= 3.5 and 0.03 <= sy <= 2.5):
            return 1e18
        return evaluate(ax, bx, ay, by, sx, sy)[0]

    # coarse: translation and sigma together, on a grid that brackets the
    # 1-2 px error a bbox-based seed can have
    best = None
    for dax in np.arange(-3.0, 3.01, 0.5):
        for day in np.arange(-3.0, 3.01, 0.5):
            for sx in (0.5, 1.0, 1.5, 2.0):
                for sy in (0.3, 0.6, 0.9):
                    v = obj(g.ax + dax, g.bx, g.ay + day, g.by, sx, sy)
                    if best is None or v < best[0]:
                        best = (v, g.ax + dax, g.ay + day, sx, sy)
    _, ax0, ay0, sx0, sy0 = best
    v, cur = compass_search(
        obj, dict(ax=ax0, bx=g.bx, ay=ay0, by=g.by, sx=sx0, sy=sy0),
        dict(ax=0.5, bx=0.004, ay=0.5, by=0.004, sx=0.20, sy=0.20))
    g2 = Geometry(cur["ax"], cur["bx"], cur["ay"], cur["by"],
                  gauss_taps(cur["sx"]), gauss_taps(cur["sy"]))
    _, coef = evaluate(**cur)
    if verbose:
        print("bootstrap: ax=%.3f bx=%.5f ay=%.3f by=%.5f sigx=%.3f sigy=%.3f rms=%.2f c1=%.3f"
              % (cur["ax"], cur["bx"], cur["ay"], cur["by"], cur["sx"], cur["sy"],
                 np.sqrt(v), coef[3]))
    return g2, dict(sigma_x_native=float(cur["sx"]), sigma_y_native=float(cur["sy"]),
                    rms=float(np.sqrt(v)), coef=coef.tolist(),
                    amp=float(L.INK_LEVEL * coef[3]))


# ---------------------------------------------------------------- refine ----
def _smooth_penalty(n):
    D = np.zeros((n - 2, n))
    for i in range(n - 2):
        D[i, i], D[i, i + 1], D[i, i + 2] = 1.0, -2.0, 1.0
    return D


def fit_prefix(lum, g, prefix=None, passes=3, cmax=9, verbose=False):
    """Read the six constant leading address characters by residual descent.

    They are the same on all 16 rows, so a single 16-row fit decides them; the
    objective is the same least-squares residual the PSF fit uses, which makes
    this a measurement of the page's base address rather than an assumption
    (the 0/4 pair the eye confuses at this blur is separated by ~10x in the
    residual -- see out/prefix_scores.txt).
    """
    font = L.load_font()
    nx0, nx1 = 80, L.cell_x(10) - 2
    ny0, ny1 = L.cell_y(0) - 7, L.cell_y(L.NROWS - 1) + L.GH + 3
    rx0, rx1, ry0, ry1 = obs_window(g.ax, g.bx, g.ay, g.by, (nx0, nx1), (ny0, ny1),
                                    (6, 2, 6, 3))
    Cx = resample_matrix(nx1 - nx0, rx1 - rx0, g.ax + g.bx * nx0 - rx0, g.bx, g.hx)
    Cy = resample_matrix(ny1 - ny0, ry1 - ry0, g.ay + g.by * ny0 - ry0, g.by, g.hy)
    O = lum[ry0:ry1, rx0:rx1].astype(np.float64)
    cur = list(prefix or "000000")
    scores = {}

    def resid(pref):
        V = scene(calib_cells("".join(pref)), font, nx0, nx1, ny0, ny1)
        _, ss = solve_linear(O, Cy @ V @ Cx.T, ry0, ry1, rx0, rx1)
        return ss / O.size

    for p in range(passes):
        changed = False
        for c in range(5, -1, -1):
            vals = []
            for k in range(16):
                trial = list(cur)
                trial[c] = L.HEXCHARS[k]
                vals.append((resid(trial), L.HEXCHARS[k]))
            vals.sort()
            scores[c] = vals
            if vals[0][1] != cur[c]:
                cur[c] = vals[0][1]
                changed = True
        if not changed:
            break
    if verbose:
        for c in range(6):
            top = scores.get(c, [])[:3]
            print("  prefix[%d] = %s   %s" % (c, cur[c],
                  "  ".join("%s:%.2f" % (ch, np.sqrt(v)) for v, ch in top)))
    return "".join(cur), scores


def refine(lum, g, cells=None, addr_prefix=None, nx=None, ny=None,
           guard=(6, 2, 6, 3), lam=2e-2, iters=4, verbose=False,
           half_x=None, half_y=None, fit_geometry=True, nonneg=False):
    """Non-parametric PSF taps + affine polish against known/hypothesised ink.

    `cells` is {(row, cell): class}; with `addr_prefix` instead, the address
    block (cells 0..9) is used.  Passing the full decoded page as `cells` turns
    this into the M-step of an EM loop over the whole screen.
    """
    font = L.load_font()
    if cells is None:
        cells = calib_cells(addr_prefix)
    if nx is None:
        nx = (80, L.cell_x(10) - 2)
    if ny is None:
        ny = (L.cell_y(0) - 7, L.cell_y(L.NROWS - 1) + L.GH + 3)
    nx0, nx1 = nx
    ny0, ny1 = ny
    V = scene(cells, font, nx0, nx1, ny0, ny1)

    hx, hy = np.array(g.hx, float), np.array(g.hy, float)
    if half_x is None:
        half_x = min((len(hx) - 1) // 2, 4 * S)
    if half_y is None:
        half_y = min((len(hy) - 1) // 2, 3 * S)
    nhx, nhy = 2 * half_x + 1, 2 * half_y + 1
    hx = gauss_taps(max(psf_width(hx) - 0.29, 0.15), half=half_x)
    hy = gauss_taps(max(psf_width(hy) - 0.29, 0.10), half=half_y)

    state = dict(ax=g.ax, bx=g.bx, ay=g.ay, by=g.by)

    def window(st):
        return obs_window(st["ax"], st["bx"], st["ay"], st["by"],
                          (nx0, nx1), (ny0, ny1), guard)

    def residual(st, hx, hy):
        rx0, rx1, ry0, ry1 = window(st)
        Cx = resample_matrix(nx1 - nx0, rx1 - rx0, st["ax"] + st["bx"] * nx0 - rx0, st["bx"], hx)
        Cy = resample_matrix(ny1 - ny0, ry1 - ry0, st["ay"] + st["by"] * ny0 - ry0, st["by"], hy)
        O = lum[ry0:ry1, rx0:rx1].astype(np.float64)
        coef, ss = solve_linear(O, Cy @ V @ Cx.T, ry0, ry1, rx0, rx1)
        return ss / O.size, coef

    v, _ = residual(state, hx, hy)

    def fit_taps(axis, hx, hy):
        rx0, rx1, ry0, ry1 = window(state)
        O = lum[ry0:ry1, rx0:rx1].astype(np.float64)
        bgcols = _design_bg(ry0, ry1, rx0, rx1)
        if axis == "x":
            Cy = resample_matrix(ny1 - ny0, ry1 - ry0,
                                 state["ay"] + state["by"] * ny0 - ry0, state["by"], hy)
            B = taps_basis(nx1 - nx0, rx1 - rx0,
                           state["ax"] + state["bx"] * nx0 - rx0, state["bx"], nhx)
            CV = Cy @ V
            mods = [(CV @ B[t].T) for t in range(nhx)]
            n = nhx
        else:
            Cx = resample_matrix(nx1 - nx0, rx1 - rx0,
                                 state["ax"] + state["bx"] * nx0 - rx0, state["bx"], hx)
            B = taps_basis(ny1 - ny0, ry1 - ry0,
                           state["ay"] + state["by"] * ny0 - ry0, state["by"], nhy)
            VC = V @ Cx.T
            mods = [(B[t] @ VC) for t in range(nhy)]
            n = nhy
        A = np.stack([c.ravel() for c in bgcols] + [m.ravel() for m in mods], 1)
        D = _smooth_penalty(n)
        Areg = np.zeros((D.shape[0], A.shape[1]))
        w = lam * np.linalg.norm(A, axis=0).mean() / max(np.abs(D).max(), 1e-9)
        Areg[:, 3:] = D * w
        sol, *_ = np.linalg.lstsq(np.vstack([A, Areg]),
                                  np.concatenate([O.ravel(), np.zeros(D.shape[0])]),
                                  rcond=None)
        u = np.clip(sol[3:], 0, None) if nonneg else sol[3:]
        return normalise_taps(u) if u.sum() > 1e-9 else None

    for it in range(iters):
        t = fit_taps("x", hx, hy)
        if t is not None:
            cand = t
            vv, _ = residual(state, cand, hy)
            if vv < v:
                hx, v = cand, vv
        t = fit_taps("y", hx, hy)
        if t is not None:
            cand = t
            vv, _ = residual(state, hx, cand)
            if vv < v:
                hy, v = cand, vv
        if fit_geometry:
            v, state = compass_search(
                lambda **kw: residual(kw, hx, hy)[0], state,
                dict(ax=0.25, bx=0.002, ay=0.25, by=0.002))
        if verbose:
            print("  refine it%d rms=%.3f  ax=%.3f bx=%.5f ay=%.3f by=%.5f  wx=%.3f wy=%.3f"
                  % (it, np.sqrt(v), state["ax"], state["bx"], state["ay"], state["by"],
                     psf_width(hx), psf_width(hy)))

    g2 = Geometry(state["ax"], state["bx"], state["ay"], state["by"], hx, hy)
    _, coef = residual(state, hx, hy)
    return g2, dict(rms=float(np.sqrt(v)), coef=coef.tolist(),
                    amp=float(L.INK_LEVEL * coef[3]),
                    width_x_native=psf_width(hx), width_y_native=psf_width(hy))


def psf_width(taps, S=S):
    """Std deviation of a tap vector in native pixels (native box included)."""
    t = np.asarray(taps, float)
    x = (np.arange(len(t)) - (len(t) - 1) / 2) / S
    w = t / t.sum()
    m = (w * x).sum()
    return float(np.sqrt((w * (x - m) ** 2).sum()))
