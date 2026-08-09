"""Find the MEMORY DUMP text grid in an arbitrary image.

Nothing here is tied to a capture resolution: the row pitch, the character
pitch, the panel origin and a small skew are all estimated from the image by
matched filtering against the *known character layout* of a dump row
(layout.py).  The only assumptions are that the text is dark-on-light and that
the 16 rows are the dominant regularly-spaced dark structure in the frame.

Pipeline
    1. ink map          = (local background - pixel) / local background
    2. skew estimate    = vertical shear that maximises the 16-row comb response
    3. row comb fit     = (y0, row_pitch) from the horizontal-gradient profile
    4. column fit       = (x0, char_pitch) matched against layout.kind, then the
                          pitch re-estimated from the phase-folded profile
    5. row/column alternation: which 16 consecutive rows are the DUMP rows is
                          decided on the column signature (the colour legend line
                          under the table is text at the same pitch and must not
                          be mistaken for a data row)
    6. per-row refinement so keystone is absorbed row-wise, then a robust
                          polynomial through the 16 rows removes per-row noise
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from . import layout as L
from .imageutil import as_rgb, box_mean, gray, local_max, shear_rows


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _interp_cumsum(p: np.ndarray) -> np.ndarray:
    """C[i] = sum(p[:i]); used with np.interp for fractional-range sums."""
    c = np.zeros(len(p) + 1, dtype=np.float64)
    c[1:] = np.cumsum(p)
    return c


def _range_sum(cum: np.ndarray, a, b):
    """Sum of p over the fractional interval [a, b) (a, b may be arrays)."""
    n = len(cum) - 1
    x = np.arange(n + 1, dtype=np.float64)
    return np.interp(np.clip(b, 0, n), x, cum) - np.interp(np.clip(a, 0, n), x, cum)


def ink_map(rgb: np.ndarray, ry: int = None, rx: int = None,
            bg_frac: float = 20.0, mode: str = "mean") -> np.ndarray:
    """Ink strength in [0,1]: how much darker a pixel is than its local background,
    expressed as a *ratio* so that neither the LCD backlight gradient of a phone
    photo nor the black area around the panel produces spurious ink.
    """
    g = gray(rgb)
    h, w = g.shape
    if ry is None:
        ry = max(2, int(round(h / bg_frac)))
    if rx is None:
        rx = max(2, int(round(w / bg_frac)))
    if mode == "max":
        # Alternative "paper" estimate.  Sharper near the panel edge, but it also
        # changes the ink values inside the panel; on native frames it is worse
        # (99.83% -> 99.02%), so it is only used as the RETRY variant when a frame
        # fails its own address self-check.
        bg = box_mean(local_max(g, max(ry // 3, 1), max(rx // 3, 1)),
                      max(ry // 4, 1), max(rx // 4, 1))
    else:
        bg = box_mean(g, ry, rx)
    bright = float(np.percentile(bg, 90))
    floor = 0.25 * bright
    den = np.maximum(bg, max(floor, 1.0))
    ink = np.clip((bg - g) / den, 0.0, 1.0)
    # Kill the halo.  The dump panel is a bright rectangle on black, so the box
    # mean bleeds panel brightness tens of pixels out into the surround and the
    # surround turns into saturated fake ink.  That fake ink is not harmless: the
    # hex area's INK/INK/SPACE column pattern repeats every 3 characters, so the
    # column matched filter is degenerate under a 3-character shift and is pinned
    # down only by the address block at the left -- a band of fake ink to the LEFT
    # of the panel therefore lets a 9-character-shifted alignment outscore the
    # truth (measured on a 720x480 resample: the fit landed 9 cells left of the
    # panel and the page decoded to noise).  Requiring the local background to be
    # genuinely light removes it without touching anything inside the panel.
    # (A local-maximum "paper" estimate was tried instead and is worse: it also
    # changes the ink values inside the panel, and native-frame accuracy fell
    # from 99.97% to 99.02%.)
    ink = np.where(bg >= 0.35 * bright, ink, 0.0)
    return ink.astype(np.float32)


# --------------------------------------------------------------------------- #
# fits
# --------------------------------------------------------------------------- #
@dataclass
class RowFit:
    yc: float          # row centre in sheared coordinates
    x0: float          # left edge of character cell 0
    cw: float          # character pitch
    score: float


@dataclass
class Grid:
    slope: float
    row_pitch: float
    rows: List[RowFit]
    lay: L.RowLayout
    score: float
    height: int
    width: int
    # the (sheared) ink map the fit was computed on, kept so the extractor does
    # not have to recompute it; None if the Grid was built by hand
    ink: Optional[np.ndarray] = None

    def cell_box(self, r: int, c: int, pad_x: float = 0.0, pad_y: float = 0.0):
        """(y0, y1, x0, x1) of character cell (row r, char c) in sheared coords."""
        rf = self.rows[r]
        x0 = rf.x0 + c * rf.cw - pad_x * rf.cw
        x1 = rf.x0 + (c + 1) * rf.cw + pad_x * rf.cw
        hh = self.row_pitch * (0.5 + pad_y)
        return rf.yc - hh, rf.yc + hh, x0, x1


def texture_map(ink: np.ndarray) -> np.ndarray:
    """Horizontal-gradient magnitude of the ink map.

    This is what separates a row of TEXT from the panel's own horizontal
    borders: a border is a solid dark line, so it has plenty of ink but no
    horizontal structure, whereas a row of glyphs is nothing but vertical
    strokes.  Combing the rows on ink alone locks onto the border and comes out
    one row high -- measured, and the reason this map exists.
    """
    d = np.zeros_like(ink)
    d[:, 1:-1] = np.abs(ink[:, 2:] - ink[:, :-2]) * 0.5
    return d


def _row_profile(ink: np.ndarray) -> np.ndarray:
    return ink.sum(axis=1)


def _comb_score(prof: np.ndarray, pitch: float, phases: np.ndarray,
                nrows: int, band: float) -> np.ndarray:
    """Matched filter: ink inside nrows bands minus ink in the gaps between."""
    cum = _interp_cumsum(prof)
    hb = band * pitch * 0.5
    k = np.arange(nrows)[None, :]
    c = phases[:, None] + pitch * k
    inb = _range_sum(cum, c - hb, c + hb).sum(axis=1)
    gap = _range_sum(cum, c + hb, c + pitch - hb).sum(axis=1)
    ins_len = 2 * hb * nrows
    gap_len = max((pitch - 2 * hb) * nrows, 1e-6)
    return inb / ins_len - gap / gap_len


def fit_rows(ink: np.ndarray, nrows: int = L.NROWS,
             pitch_lo: float = 5.0, pitch_hi: Optional[float] = None,
             band: float = 0.70, pre: bool = False,
             pitch_step: float = 0.05) -> Tuple[float, float, float]:
    """Return (y0_centre_of_row0, row_pitch, score).

    `pre=True` means `ink` is already a texture map; otherwise one is derived.
    """
    h = ink.shape[0]
    prof = _row_profile(ink if pre else texture_map(ink))
    if pitch_hi is None:
        pitch_hi = h / (nrows - 0.2)
    best = (-1e18, 0.0, 0.0)
    pitches = np.arange(pitch_lo, pitch_hi, pitch_step)
    for pitch in pitches:
        span = pitch * (nrows - 1)
        if span >= h:
            continue
        phases = np.arange(pitch * 0.25, h - span, max(pitch / 12.0, 0.25))
        if len(phases) == 0:
            continue
        sc = _comb_score(prof, pitch, phases, nrows, band)
        i = int(np.argmax(sc))
        if sc[i] > best[0]:
            best = (float(sc[i]), float(phases[i]), float(pitch))
    return best[1], best[2], best[0]


def estimate_skew(ink: np.ndarray, nrows: int = L.NROWS,
                  max_slope: float = 0.05, pitch_hint: Optional[float] = None) -> float:
    """Pick the vertical shear that makes the 16-row comb sharpest (coarse->fine)."""
    tex = texture_map(ink)

    def score(s: float, step: float) -> float:
        sh = shear_rows(tex, float(s))
        lo, hi = 5.0, None
        if pitch_hint is not None:
            lo, hi = pitch_hint * 0.92, pitch_hint * 1.08
        return fit_rows(sh, nrows, pitch_lo=lo, pitch_hi=hi, pre=True, pitch_step=step)[2]

    best_s, best_v = 0.0, -1e18
    coarse = np.linspace(-max_slope, max_slope, 9)
    for s in coarse:
        v = score(s, 0.25)
        if v > best_v:
            best_v, best_s = v, float(s)
    span = float(coarse[1] - coarse[0])
    best_v = -1e18
    for s in np.linspace(best_s - span, best_s + span, 9):
        v = score(s, 0.15)
        if v > best_v:
            best_v, best_s = v, float(s)
    return best_s


def _col_score(colprof: np.ndarray, lay: L.RowLayout, x0s: np.ndarray,
               cw: float, width: int) -> np.ndarray:
    """Score a (x0, cw) hypothesis against the known ink/space character pattern."""
    cum = _interp_cumsum(colprof)
    kind = np.asarray(lay.kind)
    idx_ink = np.nonzero(kind == L.INK)[0]
    idx_sp = np.nonzero(kind == L.SPACE)[0]

    def cellmeans(idx):
        a = x0s[:, None] + idx[None, :] * cw
        b = a + cw
        inside = (a >= 0) & (b <= width)
        s = _range_sum(cum, a, b) / cw
        s = np.where(inside, s, np.nan)
        return s

    mi = cellmeans(idx_ink)
    ms = cellmeans(idx_sp)
    with np.errstate(invalid="ignore"):
        vi = np.nanmean(mi, axis=1)
        vs = np.nanmean(ms, axis=1)
    n_ok = np.sum(~np.isnan(mi), axis=1)
    ok = n_ok >= int(0.7 * len(idx_ink))
    out = np.where(ok, vi - vs, -1e18)
    return np.nan_to_num(out, nan=-1e18)


def fit_columns(ink_row: np.ndarray, lay: L.RowLayout,
                cw_lo: float = 3.0, cw_hi: Optional[float] = None,
                cw_hint: Optional[float] = None,
                x0_hint: Optional[float] = None) -> Tuple[float, float, float]:
    """Fit (x0, char pitch) for one text row.  ink_row is a 2-D band of the ink map.

    Coarse sweep first, then a local sub-pixel refinement -- the refinement
    matters: an 0.02 px pitch error accumulates to more than half a character
    over the 57 characters of the self-checking part of a row.
    """
    w = ink_row.shape[1]
    colprof = ink_row.sum(axis=0)
    if cw_hi is None:
        cw_hi = w / (lay.hex_end - 0.5)
    if cw_hint is not None:
        cw_lo = max(cw_lo, cw_hint * 0.88)
        cw_hi = min(cw_hi, cw_hint * 1.14)
    if cw_hi <= cw_lo:
        cw_hi = cw_lo + 0.5

    def sweep(cws, x0s_fn):
        best = (-1e18, 0.0, 0.0)
        for cw in cws:
            x0s = x0s_fn(cw)
            if len(x0s) == 0:
                continue
            sc = _col_score(colprof, lay, x0s, float(cw), w)
            i = int(np.argmax(sc))
            if sc[i] > best[0]:
                best = (float(sc[i]), float(x0s[i]), float(cw))
        return best

    if x0_hint is None:
        def coarse_x0(cw):
            return np.arange(-2.0 * cw, w - lay.hex_end * cw + 2.0 * cw, max(cw / 10.0, 0.15))
    else:
        def coarse_x0(cw):
            return np.arange(x0_hint - 1.5 * cw, x0_hint + 1.5 * cw, max(cw / 10.0, 0.15))

    s, x0, cw = sweep(np.arange(cw_lo, cw_hi, 0.08), coarse_x0)
    # local refinement
    s2, x02, cw2 = sweep(np.arange(max(cw - 0.14, 0.5), cw + 0.14, 0.005),
                         lambda c: np.arange(x0 - 0.9, x0 + 0.9, 0.03))
    if s2 >= s:
        s, x0, cw = s2, x02, cw2

    # The matched filter is biased low in the pitch: the glyph is narrower than
    # its cell, so shrinking the cell raises the ink-cell mean.  Take the pitch
    # from the periodicity of the glyph comb instead (unbiased), then re-seat x0.
    cw_dft = _pitch_by_dft(colprof, x0, x0 + lay.hex_end * cw, cw)
    if cw_dft is not None:
        s3, x03, _ = sweep([cw_dft], lambda c: np.arange(x0 - 0.9, x0 + 0.9, 0.02))
        x0, cw, s = x03, cw_dft, s3
    return x0, cw, s


def _pitch_by_dft(colprof: np.ndarray, xa: float, xb: float, cw0: float,
                  rel: float = 0.05, n: int = 401, bins: int = 24) -> Optional[float]:
    """Character pitch by maximising the sharpness of the PHASE-FOLDED profile.

    Folding the column profile modulo a trial pitch and measuring how much
    structure survives is an unbiased pitch estimator: only the true pitch keeps
    the 5-on/1-off glyph comb from smearing.  (The obvious alternatives are
    biased -- a matched filter on cell means always prefers a pitch slightly
    smaller than the truth, because a narrower cell excludes the blank column
    and so raises the mean; measured at -0.02 px/char on native frames, which is
    a whole character of drift across a row.)
    """
    a = int(max(round(xa), 0)); b = int(min(round(xb), len(colprof)))
    if b - a < 8 * cw0:
        return None
    p = colprof[a:b].astype(np.float64)
    if not np.any(p > 1e-9):
        return None
    x = np.arange(a, b, dtype=np.float64) - a
    best_cw, best_v = None, -1.0
    for cw in np.linspace(cw0 * (1 - rel), cw0 * (1 + rel), n):
        idx = np.floor(((x / cw) % 1.0) * bins).astype(np.int64)
        idx = np.clip(idx, 0, bins - 1)
        s = np.bincount(idx, weights=p, minlength=bins)
        c = np.bincount(idx, minlength=bins).astype(np.float64)
        f = s / np.maximum(c, 1e-9)
        v = float(f.var())
        if v > best_v:
            best_v, best_cw = v, float(cw)
    return best_cw


def row_layout_score(ink: np.ndarray, yc: float, pitch: float, lay: L.RowLayout,
                     x0: float, cw: float) -> float:
    """How much this single image row looks like a DUMP row (not a legend line)."""
    h = ink.shape[0]
    a = int(round(yc - pitch * 0.5)); b = int(round(yc + pitch * 0.5))
    a = max(a, 0); b = min(b, h)
    if b - a < 2:
        return -1e18
    prof = ink[a:b].sum(axis=0) / float(b - a)
    return float(_col_score(prof, lay, np.array([x0], dtype=float), cw, ink.shape[1])[0])


def _choose_row_block(ink: np.ndarray, y0: float, pitch: float, lay: L.RowLayout,
                      x0: float, cw: float, span: int = 3) -> float:
    """Slide the 16-row window by whole rows and keep the best-scoring position."""
    h = ink.shape[0]
    scores = {}
    for k in range(-span, L.NROWS + span):
        yc = y0 + k * pitch
        if yc < -pitch or yc > h + pitch:
            scores[k] = -1e18
        else:
            scores[k] = row_layout_score(ink, yc, pitch, lay, x0, cw)
    best_k, best_v = 0, -1e18
    for k0 in range(-span, span + 1):
        v = sum(scores.get(k0 + i, -1e18) for i in range(L.NROWS))
        if v > best_v:
            best_v, best_k = v, k0
    return y0 + best_k * pitch


def fit_grid(rgb, layouts: Optional[List[L.RowLayout]] = None,
             skew: Optional[float] = None, refine: bool = True,
             search_skew: bool = True, prior: Optional[Grid] = None,
             ink_mode: str = "mean") -> Grid:
    """Locate the 16x(address+16 byte) character grid.  Returns a Grid.

    `prior` (a Grid from a previous frame of the same capture) turns the whole
    thing into a cheap local refinement, which is what a video decoder wants.
    """
    rgb = as_rgb(rgb)
    h, w = rgb.shape[:2]

    if prior is not None:
        ink = shear_rows(ink_map(rgb, ry=max(2, int(round(prior.row_pitch * 1.3))),
                                 rx=max(2, int(round(prior.row_pitch * 3.0)))), prior.slope)
        g = Grid(slope=prior.slope, row_pitch=prior.row_pitch,
                 rows=[RowFit(r.yc, r.x0, r.cw, r.score) for r in prior.rows],
                 lay=prior.lay, score=prior.score, height=h, width=w)
        g = refine_rows(ink, g, y_search=0.30)
        g.ink = ink
        return g

    ink0 = ink_map(rgb, mode=ink_mode)
    if skew is None:
        skew = estimate_skew(ink0) if search_skew else 0.0
    ink = shear_rows(ink0, skew)

    y0, pitch, rscore = fit_rows(ink)
    # second pass: now that the row pitch is known, re-derive the ink map with a
    # background window matched to it (sharper, and it stops the black surround
    # around the panel from bleeding in)
    ink0 = ink_map(rgb, ry=max(2, int(round(pitch * 1.3))), rx=max(2, int(round(pitch * 3.0))), mode=ink_mode)
    ink = shear_rows(ink0, skew)
    y0, pitch, rscore = fit_rows(ink)

    if layouts is None:
        layouts = [L.DEFAULT]

    # Fit the columns on the whole block (all 16 rows stacked -- far more signal
    # than any single row), then decide which 16 consecutive rows are the dump
    # rows.  (Alternating the two to convergence, and re-fitting the row pitch
    # against the column signature, were both tried: they rescue a 720x480
    # resample whose column fit lands off the panel, but they cost accuracy on
    # native frames -- 99.97% -> 99.02% -- so they are not in the shipped path.)
    def _stack(y0v):
        bands = []
        for r in range(L.NROWS):
            yc = y0v + r * pitch
            a = int(round(yc - pitch * 0.5)); b = int(round(yc + pitch * 0.5))
            a = max(a, 0); b = min(b, h)
            if b > a:
                bands.append(ink[a:b])
        return np.concatenate(bands, axis=0) if bands else ink

    best = None
    for cand in layouts:
        x0, cw, sc = fit_columns(_stack(y0), cand)
        if best is None or sc > best[0]:
            best = (sc, x0, cw, cand)
    cscore, x0g, cwg, lay = best

    # Which 16 consecutive rows are the DUMP rows?  The comb alone cannot tell:
    # the colour legend under the table is one more line of text at the same
    # pitch, so the fit can slide by a whole row.  Resolve it on CONTENT -- only
    # a dump row has the "8 hex digits, 2 blanks, then hex-hex-blank triplets"
    # column signature, and the legend row does not.
    y0 = _choose_row_block(ink, y0, pitch, lay, x0g, cwg)

    rows: List[RowFit] = []
    for r in range(L.NROWS):
        yc = y0 + r * pitch
        rows.append(RowFit(yc=yc, x0=x0g, cw=cwg, score=cscore))

    grid = Grid(slope=skew, row_pitch=pitch, rows=rows, lay=lay,
                score=min(rscore, cscore), height=h, width=w)

    if refine:
        grid = refine_rows(ink, grid)
    grid.ink = ink
    return grid


def refine_rows(ink: np.ndarray, grid: Grid, y_search: float = 0.35) -> Grid:
    """Per-row y centring and (x0, cw) re-fit -- absorbs keystone/perspective."""
    h, w = ink.shape
    pitch = grid.row_pitch
    tex = texture_map(ink)
    x0_ref = float(np.median([r.x0 for r in grid.rows]))
    cw_ref = float(np.median([r.cw for r in grid.rows]))
    # Only the character block itself may vote on where a row sits: anything
    # else on the screen (logos, widgets, the ASCII pane) drags the centring.
    xa = max(int(round(x0_ref)), 0)
    xb = min(int(round(x0_ref + grid.lay.hex_end * cw_ref)), w)
    prof_cum = _interp_cumsum(tex[:, xa:max(xb, xa + 1)].sum(axis=1))
    for r, rf in enumerate(grid.rows):
        # y: maximise glyph texture inside a 0.62*pitch band around the centre.
        # The response is a plateau (the band is taller than the glyph), so take
        # the MIDDLE of the plateau, not its first sample -- that is worth a
        # pixel of registration, which template matching feels.
        offs = np.arange(-y_search * pitch, y_search * pitch + 1e-9, 0.05)
        cs = rf.yc + offs
        hb = 0.31 * pitch
        v = _range_sum(prof_cum, cs - hb, cs + hb)
        top = v >= v.max() - 1e-9 - 0.005 * abs(v.max())
        rf.yc = float(cs[top].mean())
        a = int(round(rf.yc - pitch * 0.55)); b = int(round(rf.yc + pitch * 0.55))
        a = max(a, 0); b = min(b, h)
        if b - a < 2:
            continue
        x0, cw, s = fit_columns(ink[a:b], grid.lay, cw_hint=cw_ref, x0_hint=x0_ref)
        # keep the block-wide fit if this single row's fit wandered off
        if abs(cw - cw_ref) < 0.15 * cw_ref and abs(x0 - x0_ref) < 1.5 * cw_ref:
            rf.x0, rf.cw, rf.score = x0, cw, s
    return regularise_rows(grid)


def _robust_poly(y: np.ndarray, deg: int, tol: float, rounds: int = 2) -> np.ndarray:
    """Least-squares poly in the row index with outlier rejection; returns fitted y."""
    r = np.arange(len(y), dtype=float)
    keep = np.ones(len(y), bool)
    coef = np.polyfit(r, y, deg)
    for _ in range(rounds):
        res = np.abs(y - np.polyval(coef, r))
        nk = res <= tol
        if nk.sum() < deg + 2:
            break
        keep = nk
        coef = np.polyfit(r[keep], y[keep], deg)
    return np.polyval(coef, r)


def regularise_rows(grid: Grid, deg: int = 1) -> Grid:
    """Rows on a real screen are evenly spaced; force that back onto the fit.

    A per-row fit is what absorbs perspective, but it also lets a single noisy
    row wander by a pixel.  Fitting a low-order polynomial through the 16
    per-row estimates keeps the perspective and throws away the noise.
    """
    ycs = np.array([r.yc for r in grid.rows], float)
    x0s = np.array([r.x0 for r in grid.rows], float)
    cws = np.array([r.cw for r in grid.rows], float)
    p = grid.row_pitch
    ycs_f = _robust_poly(ycs, deg, 0.30 * p)
    x0s_f = _robust_poly(x0s, deg, 0.40 * float(np.median(cws)))
    cws_f = _robust_poly(cws, deg, 0.06 * float(np.median(cws)))
    for i, rf in enumerate(grid.rows):
        rf.yc, rf.x0, rf.cw = float(ycs_f[i]), float(x0s_f[i]), float(cws_f[i])
    if len(grid.rows) > 1:
        grid.row_pitch = float(np.mean(np.diff(ycs_f)))
    return grid
