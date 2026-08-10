"""Where the characters are: a four-corner registration of the dump panel.

The batch extractor fits the character grid blind, by matched filtering against
the known ink/space pattern of a dump row.  That works on the emulator's
640x240 framebuffer, where the panel fills the frame, and it does **not** work
on real captures -- measured, on both the composite grabber frames and the
phone photos, the blind fit lands off the text and every byte downstream is
noise.  The reason is structural rather than fixable: the hex area's
INK/INK/SPACE column pattern repeats every three characters, so the objective
is nearly degenerate under a three-character shift, and on a frame that also
contains the instrument's bodywork, glare and a reflection there is plenty of
other regularly-spaced dark structure to lock onto instead.

A live tool does not have to solve that problem, because it has an operator.
Here the panel is described by the four corners of the 16 x 57 character block
(address column through the last hex digit), the operator drags them onto the
text once, and the mapping is a homography -- which also absorbs the
perspective of an off-axis camera, something a shear cannot do.  From then on
the grid is *derived*, not searched, and the only automatic part is a sub-pixel
correction each frame so that a nudged camera or a drifting tripod is tracked.

`auto_seed` proposes a starting quad from the brightest large region so the
operator is nudging rather than drawing from scratch, but it is explicitly a
suggestion: nothing downstream trusts it, and the ladder check in recog.py is
what decides whether a registration is real.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np

# The self-checking part of a dump row: 8 address digits, 2 blanks, then
# 16 bytes as "HH" separated by single characters ('-' after byte 7).
# 8 + 2 + 16*2 + 15 = 57.  See kn7000dump/layout.py for the format string.
NROW = 16
NCOL_HEX = 57
ADDR_COLS = list(range(8))
BYTE_COLS = [(10 + 3 * k, 11 + 3 * k) for k in range(16)]
SEP_COLS = [12 + 3 * k for k in range(15)]
LADDER_COL = 6          # the 0x10s digit: counts 0..F down the rows
UNIT_COL = 7            # the 0x1s digit: constant down the rows


# --------------------------------------------------------------------------- #
# homography
# --------------------------------------------------------------------------- #
def homography_from_quad(dst: np.ndarray) -> np.ndarray:
    """3x3 mapping the unit square onto `dst` (TL, TR, BR, BL), by DLT.

    The unit square is character space: u spans the 57 columns, v the 16 rows.
    """
    src = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    A = np.zeros((8, 8), np.float64)
    b = np.zeros(8, np.float64)
    for i in range(4):
        u, v = src[i]
        x, y = dst[i]
        A[2 * i] = [u, v, 1, 0, 0, 0, -u * x, -v * x]
        A[2 * i + 1] = [0, 0, 0, u, v, 1, -u * y, -v * y]
        b[2 * i] = x
        b[2 * i + 1] = y
    h = np.linalg.solve(A, b)
    return np.array([[h[0], h[1], h[2]],
                     [h[3], h[4], h[5]],
                     [h[6], h[7], 1.0]], np.float64)


def apply_h(H: np.ndarray, u: np.ndarray, v: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Map character-space coordinates through the homography to image pixels."""
    den = H[2, 0] * u + H[2, 1] * v + H[2, 2]
    den = np.where(np.abs(den) < 1e-12, 1e-12, den)
    x = (H[0, 0] * u + H[0, 1] * v + H[0, 2]) / den
    y = (H[1, 0] * u + H[1, 1] * v + H[1, 2]) / den
    return x, y


@dataclass
class Quad:
    """The four image-space corners of the 16 x 57 character block."""
    corners: np.ndarray            # (4,2) float: TL, TR, BR, BL

    def __post_init__(self):
        self.corners = np.asarray(self.corners, dtype=np.float64).reshape(4, 2)

    @classmethod
    def from_bbox(cls, x0: float, y0: float, x1: float, y1: float) -> "Quad":
        return cls(np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], float))

    @property
    def H(self) -> np.ndarray:
        return homography_from_quad(self.corners)

    @property
    def centre(self) -> np.ndarray:
        return self.corners.mean(axis=0)

    def cell_pitch(self) -> Tuple[float, float]:
        """Approximate (char width, row height) in image pixels."""
        w = (np.linalg.norm(self.corners[1] - self.corners[0])
             + np.linalg.norm(self.corners[2] - self.corners[3])) * 0.5 / NCOL_HEX
        h = (np.linalg.norm(self.corners[3] - self.corners[0])
             + np.linalg.norm(self.corners[2] - self.corners[1])) * 0.5 / NROW
        return float(w), float(h)

    def bbox(self, margin: float = 0.04) -> Tuple[int, int, int, int]:
        """(x0, y0, x1, y1) integer bounds with a relative margin."""
        xs, ys = self.corners[:, 0], self.corners[:, 1]
        mx = (xs.max() - xs.min()) * margin
        my = (ys.max() - ys.min()) * margin
        return (int(np.floor(xs.min() - mx)), int(np.floor(ys.min() - my)),
                int(np.ceil(xs.max() + mx)), int(np.ceil(ys.max() + my)))

    def cell_polygon(self, r: int, c: int, ncols: int = NCOL_HEX) -> np.ndarray:
        """Image-space corners of one character cell, for the overlay."""
        H = self.H
        u0, u1 = c / ncols, (c + 1) / ncols
        v0, v1 = r / NROW, (r + 1) / NROW
        u = np.array([u0, u1, u1, u0])
        v = np.array([v0, v0, v1, v1])
        x, y = apply_h(H, u, v)
        return np.stack([x, y], axis=1)

    def translate(self, dx: float, dy: float) -> None:
        self.corners += np.array([dx, dy], float)

    def scale(self, fx: float, fy: float) -> None:
        c = self.centre
        self.corners = c + (self.corners - c) * np.array([fx, fy], float)

    def move_corner(self, i: int, dx: float, dy: float) -> None:
        self.corners[i] += np.array([dx, dy], float)

    def keystone(self, kx: float = 0.0, ky: float = 0.0) -> None:
        """Foreshorten one side relative to the other.

        These are the two degrees of freedom a translation-and-scale search
        cannot reach, and they are precisely the ones a handheld camera keeps
        changing: `kx` widens the top edge and narrows the bottom (the camera
        tipping up or down), `ky` does the same between left and right.
        """
        c = self.centre
        d = self.corners - c
        if kx:
            for i, sgn in ((0, +1), (1, +1), (2, -1), (3, -1)):
                d[i, 0] *= (1.0 + sgn * kx)
        if ky:
            for i, sgn in ((0, -1), (1, +1), (2, +1), (3, -1)):
                d[i, 1] *= (1.0 + sgn * ky)
        self.corners = c + d

    def nearest_corner(self, x: float, y: float) -> Tuple[int, float]:
        d = np.linalg.norm(self.corners - np.array([x, y], float), axis=1)
        i = int(np.argmin(d))
        return i, float(d[i])

    def to_json(self) -> list:
        return [[float(a), float(b)] for a, b in self.corners]

    @classmethod
    def from_json(cls, v) -> "Quad":
        return cls(np.array(v, float))


# --------------------------------------------------------------------------- #
# sampling
# --------------------------------------------------------------------------- #
def sample_bilinear(a: np.ndarray, ys: np.ndarray, xs: np.ndarray) -> np.ndarray:
    """Bilinear sample of a 2-D array at float coordinates."""
    h, w = a.shape
    ys = np.clip(ys, 0, h - 1.001)
    xs = np.clip(xs, 0, w - 1.001)
    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    fy = (ys - y0).astype(np.float32)
    fx = (xs - x0).astype(np.float32)
    y1 = np.minimum(y0 + 1, h - 1)
    x1 = np.minimum(x0 + 1, w - 1)
    return (a[y0, x0] * (1 - fy) * (1 - fx) + a[y1, x0] * fy * (1 - fx)
            + a[y0, x1] * (1 - fy) * fx + a[y1, x1] * fy * fx)


@dataclass
class Registration:
    """A quad plus the sub-pixel correction that tracking keeps updating.

    The correction is an affine map in character space, i.e. it says "the text
    actually starts a fifth of a character to the left of where the corners
    say, and the pitch is 0.3 % larger".  Keeping it separate from the corners
    means the operator's placement is never silently overwritten, and `bake()`
    folds it in when it has converged.
    """
    quad: Quad
    au: float = 1.0
    bu: float = 0.0
    av: float = 1.0
    bv: float = 0.0
    ncols: int = NCOL_HEX

    def cut(self, img: np.ndarray, cells: Sequence[Tuple[int, int]],
            gh: int, gw: int, ox: float = 0.0, oy: float = 0.0,
            origin: Tuple[float, float] = (0.0, 0.0)) -> np.ndarray:
        """Resample one gh x gw patch per (row, col) cell.  Vectorised.

        `ox`/`oy` widen the aperture beyond the nominal cell, in cells.

        This is the hot path -- the refinement search calls it tens of times a
        frame -- so the sample grid is built once, in float32, and the whole
        set of cells goes through a single bilinear gather.
        """
        n = len(cells)
        if n == 0:
            return np.zeros((0, gh, gw), np.float32)
        cells = np.asarray(cells, dtype=np.float32)
        r = cells[:, 0] - oy * 0.5
        c = cells[:, 1] - ox * 0.5
        jj = ((np.arange(gw, dtype=np.float32) + 0.5) / gw) * (1.0 + ox)
        ii = ((np.arange(gh, dtype=np.float32) + 0.5) / gh) * (1.0 + oy)
        u = (c[:, None, None] + jj[None, None, :]) * (self.au / self.ncols) + self.bu
        v = (r[:, None, None] + ii[None, :, None]) * (self.av / NROW) + self.bv
        H = self.quad.H
        den = H[2, 0] * u + H[2, 1] * v + H[2, 2]
        x = (H[0, 0] * u + H[0, 1] * v + H[0, 2]) / den - origin[0]
        y = (H[1, 0] * u + H[1, 1] * v + H[1, 2]) / den - origin[1]
        # `img` may be a crop of the frame (the ink map is only ever computed
        # around the panel, so a 4K camera costs no more than a webcam here).
        return sample_bilinear(img, np.broadcast_to(y, (n, gh, gw)),
                               np.broadcast_to(x, (n, gh, gw))).astype(np.float32)

    def bake(self) -> None:
        """Fold the affine correction into the corners and reset it."""
        if (self.au, self.bu, self.av, self.bv) == (1.0, 0.0, 1.0, 0.0):
            return
        H = self.quad.H
        u = np.array([0.0, 1.0, 1.0, 0.0])
        v = np.array([0.0, 0.0, 1.0, 1.0])
        x, y = apply_h(H, self.au * u + self.bu, self.av * v + self.bv)
        self.quad = Quad(np.stack([x, y], axis=1))
        self.au, self.bu, self.av, self.bv = 1.0, 0.0, 1.0, 0.0

    def to_json(self) -> dict:
        return {"quad": self.quad.to_json(), "au": self.au, "bu": self.bu,
                "av": self.av, "bv": self.bv, "ncols": self.ncols}

    @classmethod
    def from_json(cls, d: dict) -> "Registration":
        return cls(Quad.from_json(d["quad"]), d.get("au", 1.0), d.get("bu", 0.0),
                   d.get("av", 1.0), d.get("bv", 0.0), d.get("ncols", NCOL_HEX))


# --------------------------------------------------------------------------- #
# tracking
# --------------------------------------------------------------------------- #
def patch_centroids(P: np.ndarray) -> np.ndarray:
    """Ink-weighted centroid of each patch, in patch units (0.5 = centre).

    Returns (N, 2) as (cx, cy).  The weight is the part of the patch that is
    darker than the patch's own mean, which is what "the glyph" means once the
    background has been divided out by the ink map.
    """
    n, gh, gw = P.shape
    w = np.maximum(P - P.mean(axis=(1, 2), keepdims=True), 0.0)
    tot = w.sum(axis=(1, 2)) + 1e-9
    jx = (np.arange(gw) + 0.5) / gw
    iy = (np.arange(gh) + 0.5) / gh
    cx = (w.sum(axis=1) * jx).sum(axis=1) / tot
    cy = (w.sum(axis=2) * iy).sum(axis=1) / tot
    return np.stack([cx, cy, tot / (gh * gw)], axis=1)


def track_homography(reg: Registration, cells: np.ndarray, resid: np.ndarray,
                     weight: np.ndarray, gain: float = 0.6,
                     max_cell_shift: float = 0.45,
                     ridge: float = 4.0) -> Optional[float]:
    """Re-solve the full 8-dof homography from per-cell displacements.

    The camera is handheld, so between one frame and the next the panel
    translates, rotates, changes scale *and* changes its perspective foreshortening.
    Correcting only a translation and a character pitch -- which is all a
    character-space affine can express -- cannot follow that: an affine
    correction composed with the existing homography stays inside a 6-dof
    subgroup, so the two projective degrees of freedom would never update and
    the far end of the block would walk off the text while the near end still
    looked fitted.

    So the correction is a full re-solve.  Every cell contributes one
    correspondence -- "character-space point (u, v) is really at image point
    q" -- and the 8 homography parameters come from a weighted least-squares
    DLT over all of them, which is heavily over-determined (900-odd equations)
    and therefore stable even when a third of the cells are illegible.  Two
    reweighting rounds drop the cells whose displacement disagrees with the
    consensus, so a glare blob or a half-drawn row does not drag the fit.

    `resid` is the per-cell displacement in CELL units, `weight` the confidence
    to give each.  The update is damped by `gain` because an undamped re-solve
    chasing a hand tremor oscillates.  Returns the median absolute displacement
    in cells (a motion measure the caller can gate voting on), or None if too
    few cells were usable.
    """
    ok = (weight > 0) & (np.abs(resid[:, 0]) < max_cell_shift) & (np.abs(resid[:, 1]) < max_cell_shift)
    if ok.sum() < 24:
        return None
    cells = cells[ok]; resid = resid[ok]; w = weight[ok]

    H = reg.quad.H
    u = reg.au * ((cells[:, 1] + 0.5) / reg.ncols) + reg.bu
    v = reg.av * ((cells[:, 0] + 0.5) / NROW) + reg.bv
    # Where the glyph actually is, in image space.
    qx, qy = apply_h(H, u + resid[:, 0] * reg.au / reg.ncols,
                     v + resid[:, 1] * reg.av / NROW)
    # Fit H' with H'(u, v) = q.  Damp by moving only `gain` of the way.
    qx = (1 - gain) * apply_h(H, u, v)[0] + gain * qx
    qy = (1 - gain) * apply_h(H, u, v)[1] + gain * qy

    un = (u - reg.bu) / max(reg.au, 1e-9)
    vn = (v - reg.bv) / max(reg.av, 1e-9)

    # Hartley normalisation.  Without it the DLT is hopeless here: the two
    # projective columns carry entries of order |q| (a thousand, in pixels)
    # while every other column is of order one, so the least-squares solution
    # is dominated by rounding in the projective part and the "correction"
    # walks the quad off the text within a dozen frames.  Measured: tracking
    # ON made a perfectly-placed grid diverge by 22 px, while tracking OFF held
    # 13/16 rows indefinitely.  Conditioning was the whole difference.
    tx, ty = float(qx.mean()), float(qy.mean())
    d = float(np.mean(np.hypot(qx - tx, qy - ty)))
    s = (np.sqrt(2.0) / d) if d > 1e-9 else 1.0
    nqx, nqy = (qx - tx) * s, (qy - ty) * s

    # Pull the solution towards the homography we already have.  Eight free
    # parameters is more than a few hundred noisy sub-pixel displacements can
    # determine: the two projective ones in particular are barely observable
    # over a block this shallow, so left unregularised they soak up noise and
    # the far corners of the quad wander even while the near ones stay put --
    # which the ladder, being entirely in the left eighth of the block, cannot
    # see.  A ridge towards the current fit costs nothing and makes the update
    # behave like a similarity when the data cannot support more.
    T = np.array([[s, 0.0, -s * tx], [0.0, s, -s * ty], [0.0, 0.0, 1.0]])
    Hc = T @ H
    Hc = Hc / Hc[2, 2]
    p0 = np.array([Hc[0, 0], Hc[0, 1], Hc[0, 2], Hc[1, 0], Hc[1, 1], Hc[1, 2],
                   Hc[2, 0], Hc[2, 1]], np.float64)

    Hn = None
    for _ in range(2):
        n = len(un)
        A = np.zeros((2 * n, 8), np.float64)
        b = np.zeros(2 * n, np.float64)
        A[0::2, 0] = un; A[0::2, 1] = vn; A[0::2, 2] = 1
        A[0::2, 6] = -un * nqx; A[0::2, 7] = -vn * nqx
        A[1::2, 3] = un; A[1::2, 4] = vn; A[1::2, 5] = 1
        A[1::2, 6] = -un * nqy; A[1::2, 7] = -vn * nqy
        b[0::2] = nqx; b[1::2] = nqy
        sw = np.repeat(np.sqrt(w), 2)[:, None]
        A = np.vstack([A * sw, ridge * np.eye(8)])
        bb = np.concatenate([b * sw.ravel(), ridge * p0])
        coef, *_ = np.linalg.lstsq(A, bb, rcond=None)
        Hnorm = np.array([[coef[0], coef[1], coef[2]],
                          [coef[3], coef[4], coef[5]],
                          [coef[6], coef[7], 1.0]])
        Tinv = np.array([[1.0 / s, 0.0, tx], [0.0, 1.0 / s, ty], [0.0, 0.0, 1.0]])
        Hn = Tinv @ Hnorm
        px, py = apply_h(Hn, un, vn)
        err = np.hypot(px - qx, py - qy)
        keep = err <= max(np.percentile(err, 80), 1e-6)
        if keep.sum() < 24:
            break
        un, vn, qx, qy, nqx, nqy, w = (un[keep], vn[keep], qx[keep], qy[keep],
                                       nqx[keep], nqy[keep], w[keep])

    corners_u = np.array([0.0, 1.0, 1.0, 0.0])
    corners_v = np.array([0.0, 0.0, 1.0, 1.0])
    cx, cy = apply_h(Hn, corners_u, corners_v)
    new = np.stack([cx, cy], axis=1)
    if not np.all(np.isfinite(new)):
        return None
    # A correction bigger than this is not a hand moving between two frames
    # 33 ms apart; it is the fit coming loose.  Clamp rather than follow, and
    # let the ladder check decide whether the frame is usable.
    cw, ch = reg.quad.cell_pitch()
    lim = max(0.8 * max(cw, ch), 12.0)
    step = new - reg.quad.corners
    d = np.hypot(step[:, 0], step[:, 1]).max()
    if d > lim:
        new = reg.quad.corners + step * (lim / d)
    reg.quad = Quad(new)
    reg.au, reg.bu, reg.av, reg.bv = 1.0, 0.0, 1.0, 0.0
    return float(np.median(np.hypot(resid[:, 0], resid[:, 1])))


# --------------------------------------------------------------------------- #
# ink
# --------------------------------------------------------------------------- #
def to_gray(rgb: np.ndarray) -> np.ndarray:
    return (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1]
            + 0.114 * rgb[:, :, 2]).astype(np.float32)


def _box_mean(a: np.ndarray, ry: int, rx: int) -> np.ndarray:
    h, w = a.shape
    ii = np.zeros((h + 1, w + 1), np.float64)
    ii[1:, 1:] = a.cumsum(0).cumsum(1)
    ys, xs = np.arange(h), np.arange(w)
    y0 = np.clip(ys - ry, 0, h); y1 = np.clip(ys + ry + 1, 0, h)
    x0 = np.clip(xs - rx, 0, w); x1 = np.clip(xs + rx + 1, 0, w)
    s = ii[y1][:, x1] - ii[y0][:, x1] - ii[y1][:, x0] + ii[y0][:, x0]
    n = (y1 - y0)[:, None] * (x1 - x0)[None, :]
    return (s / np.maximum(n, 1)).astype(np.float32)


def ink_map(rgb: np.ndarray, ry: int, rx: int, inset: float = 0.15) -> np.ndarray:
    """Ink strength in [0,1]: how much darker a pixel is than its surroundings.

    Expressed as a ratio to the local background so that neither a camera's
    exposure gradient nor a bright reflection off the instrument's bezel
    produces spurious ink.  The window radii come from the measured row pitch,
    so this adapts to how close the camera is.

    `bright` -- the reference paper level -- is taken from the CENTRE of the
    image only.  This matters much more than it looks: the caller passes a crop
    of the frame around the panel, and if the reference is taken over the whole
    crop then it depends on how much dark surround the crop happens to include.
    Measured, widening that margin from 6 % to 10 % took the tool from 242
    committed bytes to none at all.  A decoder whose behaviour hinges on a crop
    margin is a decoder that will behave differently every time the operator
    reframes, so the reference is measured where the panel certainly is.
    """
    g = to_gray(rgb)
    bg = _box_mean(g, ry, rx)
    h, w = bg.shape
    iy, ix = int(h * inset), int(w * inset)
    core = bg[iy:h - iy, ix:w - ix] if (h - 2 * iy) > 4 and (w - 2 * ix) > 4 else bg
    bright = float(np.percentile(core, 90))
    den = np.maximum(bg, max(0.25 * bright, 1.0))
    ink = np.clip((bg - g) / den, 0.0, 1.0)
    return np.where(bg >= 0.35 * bright, ink, 0.0).astype(np.float32)


# --------------------------------------------------------------------------- #
# seeding
# --------------------------------------------------------------------------- #
def largest_bright_bbox(g: np.ndarray, frac: float = 0.55, ds: int = 6):
    """Bounding box of the largest bright blob, found on a downsampled copy.

    Deliberately crude.  On a photo of the instrument this finds the lit screen
    because the screen is the brightest large thing in the picture; when it
    finds something else instead, the operator drags the corners, which is why
    the whole tool is built around the corners being editable.
    """
    s = g[::ds, ::ds]
    thr = frac * float(np.percentile(s, 99.5))
    m = s > thr
    if not m.any():
        return None
    H, W = m.shape
    seen = np.zeros((H, W), bool)
    best = (0, None)
    for y0, x0 in np.argwhere(m):
        if seen[y0, x0]:
            continue
        stack = [(int(y0), int(x0))]
        seen[y0, x0] = True
        ys, xs = [], []
        while stack:
            y, x = stack.pop()
            ys.append(y); xs.append(x)
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < H and 0 <= nx < W and m[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if len(ys) > best[0]:
            best = (len(ys), (min(ys), max(ys), min(xs), max(xs)))
    if best[1] is None:
        return None
    y0, y1, x0, x1 = best[1]
    return (x0 * ds, y0 * ds, (x1 + 1) * ds, (y1 + 1) * ds)


def auto_seed(rgb: np.ndarray) -> Quad:
    """A first guess at the character block: the text area of the lit screen.

    The dump viewer fills essentially the whole 640x240 screen with the table
    (75 characters of a possible 80, 16 data rows plus a legend line), so
    insetting the detected screen slightly is a usable starting point.  It is
    only a starting point -- see the module docstring.
    """
    g = to_gray(rgb)
    bb = largest_bright_bbox(g)
    if bb is None:
        h, w = g.shape
        bb = (int(w * 0.1), int(h * 0.1), int(w * 0.9), int(h * 0.9))
    x0, y0, x1, y1 = bb
    w, h = x1 - x0, y1 - y0
    # The 57 hex columns are the left ~76 % of the 75-character line, and the
    # 16 data rows sit above the legend line.
    return Quad.from_bbox(x0 + 0.03 * w, y0 + 0.10 * h,
                          x0 + 0.79 * w, y0 + 0.88 * h)
