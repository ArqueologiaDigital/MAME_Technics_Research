"""Reference single-frame extractor -- a STAND-IN for package c2.

c3's job is the video pipeline, not the extractor.  But a pipeline whose extractor is a
`pass` statement cannot be measured, and rule (2) of the brief is "measure, do not
assert".  So this module implements the c2 contract well enough to produce real numbers
end to end.  Swap it out: ``Pipeline(extractor=c2.extract)`` and nothing else changes.

The one idea here worth stealing for c2
---------------------------------------
The address column is a **self-labelling font sample**.  Row r of a clean page always
prints an address ending in ``r*0x10``, so character column 6 of the 16 rows spells
``0 1 2 3 4 5 6 7 8 9 A B C D E F`` top to bottom -- every glyph class, correctly
labelled, in every single frame, with no oracle and no training set.  Templates are
bootstrapped from that and then matched against the rest of the screen.  It self-
calibrates to whatever the capture chain does to the font.

Geometry (measured on MAME `-snapview native` frames, 640x240):
    text rows      y = 55 + 9*r, glyph height 7          (r = 0..15)
    char cells     x = 90 + 6*c, glyph width 5
    address        char cols 0..7
    byte b digits  char cols 10+3b, 11+3b   (b = 0..15; col 33 holds the '-' separator)
Frames of other sizes are rescaled to 640x240 first, then the grid phase is refined by
correlating the ink profile against combs of period 6 (x) and 9 (y), so modest scaling,
cropping and offset from a capture card are absorbed.

Dependencies: numpy, Pillow (Pillow only for rescaling).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from .contract import PAGE_COLS, PAGE_ROWS

NOMINAL_W, NOMINAL_H = 640, 240
ROW_Y0, ROW_PITCH, GLYPH_H = 55, 9, 7
COL_X0, COL_PITCH, GLYPH_W = 90, 6, 5
N_ROWS = 16
ADDR_COLS = list(range(8))
HEX_DIGITS = "0123456789ABCDEF"

# highlight background colours in the native palette; the legend at the bottom of the
# screen says what byte each one means.  A free redundant channel.
HILITE_RGB = {
    "aqua": (0, 252, 248),
    "yellow": (248, 252, 0),
    "lime": (0, 252, 0),
    "fuchsia": (248, 0, 248),
}
DEFAULT_HILITE_VALUE = {"aqua": 0xF0, "yellow": 0xF7, "lime": 0xFF}


def byte_char_cols(b: int) -> Tuple[int, int]:
    return 10 + 3 * b, 11 + 3 * b


@dataclass
class TemplateBank:
    """Glyph templates, learned from address columns and refined across frames.

    Persisting the bank across a video is itself a cross-frame win: a page whose own
    address column is damaged still gets classified with templates learned earlier.
    """

    shape: Tuple[int, int] = (GLYPH_H, GLYPH_W)
    sums: np.ndarray = field(default=None, repr=False)
    counts: np.ndarray = field(default=None, repr=False)

    def __post_init__(self):
        if self.sums is None:
            self.sums = np.zeros((16,) + self.shape, np.float64)
        if self.counts is None:
            self.counts = np.zeros(16, np.int64)

    @property
    def ready(self) -> bool:
        return bool((self.counts > 0).all())

    def learn(self, label: int, patch: np.ndarray) -> None:
        p = _norm_patch(patch)
        if p is None:
            return
        self.sums[label] += p
        self.counts[label] += 1

    def templates(self) -> Optional[np.ndarray]:
        if not self.ready:
            return None
        t = self.sums / self.counts[:, None, None]
        t = t - t.mean(axis=(1, 2), keepdims=True)
        n = np.sqrt((t * t).sum(axis=(1, 2), keepdims=True))
        n[n == 0] = 1.0
        return t / n


def _norm_patch(patch: np.ndarray) -> Optional[np.ndarray]:
    """Zero-mean, unit-norm a glyph patch.  Returns None for a featureless (blank) cell."""
    p = patch.astype(np.float64)
    p = p - p.mean()
    n = float(np.sqrt((p * p).sum()))
    if n < 1e-6:
        return None
    return p / n


def _resize_rgb(img: np.ndarray, w: int, h: int) -> np.ndarray:
    from PIL import Image
    if img.shape[1] == w and img.shape[0] == h:
        return img
    return np.asarray(Image.fromarray(img).resize((w, h), Image.BILINEAR), dtype=np.uint8)


def _bilinear(img: np.ndarray, yy: np.ndarray, xx: np.ndarray) -> np.ndarray:
    """Sample ``img`` at fractional (yy, xx).  Needed once the grid pitch is fractional."""
    h, w = img.shape[:2]
    y0 = np.floor(yy).astype(np.int32)
    x0 = np.floor(xx).astype(np.int32)
    fy = (yy - y0).astype(np.float32)
    fx = (xx - x0).astype(np.float32)
    y0 = np.clip(y0, 0, h - 1); y1 = np.clip(y0 + 1, 0, h - 1)
    x0 = np.clip(x0, 0, w - 1); x1 = np.clip(x0 + 1, 0, w - 1)
    return (img[y0, x0] * (1 - fy) * (1 - fx) + img[y1, x0] * fy * (1 - fx)
            + img[y0, x1] * (1 - fy) * fx + img[y1, x1] * fy * fx)


def _luma(rgb: np.ndarray) -> np.ndarray:
    f = rgb.astype(np.float32)
    return 0.299 * f[..., 0] + 0.587 * f[..., 1] + 0.114 * f[..., 2]


def _refine_phase_frac(profile: np.ndarray, extent: int, nom_off: float,
                       nom_pitch: float, glyph: float,
                       search_off: float, search_pitch: float,
                       n_off: int = 25, n_pitch: int = 25) -> Tuple[float, float]:
    """Fit BOTH the grid offset and the cell pitch, sub-pixel, from a 1-D ink profile.

    Why the pitch must be fitted and not assumed: a capture chain that resamples 640 px
    across 720 (or a TV that overscans) changes the effective character pitch by a
    fraction of a percent.  With a fixed pitch of 6.0 the error is invisible at the
    address column and over a pixel by character column 55 -- so the *right-hand* bytes
    decode from a window straddling two glyphs.  That produces a SYSTEMATIC misread (in
    the measured H.264 clip, '8' read as '3' in byte after byte), and systematic errors
    are exactly the kind cross-frame voting cannot remove: every frame makes the same
    mistake, so the majority is wrong.

    Scoring uses a cumulative sum so a candidate costs two interpolated lookups per cell.
    """
    cs = np.concatenate([[0.0], np.cumsum(profile)])
    xs = np.arange(len(cs), dtype=np.float64)

    def integ(a, b):
        return np.interp(b, xs, cs) - np.interp(a, xs, cs)

    k = np.arange(extent, dtype=np.float64)
    best = (nom_off, nom_pitch)
    best_score = -1e30
    for off in np.linspace(nom_off - search_off, nom_off + search_off, n_off):
        for pitch in np.linspace(nom_pitch - search_pitch, nom_pitch + search_pitch, n_pitch):
            starts = off + pitch * k
            inside = integ(starts, starts + glyph).sum()
            gap = integ(starts + glyph, starts + pitch).sum()
            score = inside / glyph - gap / max(pitch - glyph, 1e-3)
            if score > best_score:
                best, best_score = (float(off), float(pitch)), score
    return best


def _refine_phase(profile: np.ndarray, period: int, extent: int, nominal: int,
                  glyph: int, search: int) -> int:
    """Pick the grid offset that puts ink inside glyph slots and blank in the gaps.

    Brute force over ``nominal +- search`` -- at most 2*search+1 candidates, each a couple
    of vectorised sums.  A closed-form comb correlation was tried first and picked an
    offset three pixels out on clean frames (the ink profile is not sinusoidal), which is
    exactly the sort of clever-but-wrong that a measured check catches.
    """
    n = len(profile)
    best_off, best_score = nominal, -1e30
    for off in range(nominal - search, nominal + search + 1):
        idx = off + period * np.arange(extent)[:, None] + np.arange(period)[None, :]
        if idx.min() < 0 or idx.max() >= n:
            continue
        cells = profile[idx]
        inside = cells[:, :glyph].sum()
        gap = cells[:, glyph:].sum()
        # per-column normalisation so the score is a contrast, not a brightness
        score = inside / max(glyph, 1) - gap / max(period - glyph, 1)
        if score > best_score:
            best_off, best_score = off, score
    return best_off


class ReferenceExtractor:
    """Implements the c2 contract.  Call the instance, or use the module-level `extract`."""

    def __init__(self, bank: Optional[TemplateBank] = None, use_colour_check: bool = True,
                 refine_grid: bool = True, relock_every: int = 30,
                 freeze_after: int = 24):
        self.bank = bank if bank is not None else TemplateBank()
        self.shape_flat = (GLYPH_H, GLYPH_W)
        self.use_colour_check = use_colour_check
        self.refine_grid = refine_grid
        self.relock_every = relock_every
        # Freeze the templates once enough settled frames have contributed.  Without this
        # the extractor is not a pure function of its input -- the same frame decodes
        # slightly differently depending on how many frames preceded it -- and that made
        # the pipeline's own dedup setting change the ANSWER (measured on 1501 clean
        # frames: 255 wrong with --dedup identical, 978 with --dedup off, same pixels).
        # A stateful extractor turns a performance knob into an accuracy knob.
        self.freeze_after = freeze_after
        self._good_frames = 0
        self._last_samples: List = []
        self._locked: Optional[Tuple[float, float]] = None
        self._locked_pitch = (float(COL_PITCH), float(ROW_PITCH))
        self._lock_ttl = 0
        self.pitch_x = float(COL_PITCH)
        self.pitch_y = float(ROW_PITCH)
        self._x0, self._y0 = COL_X0, ROW_Y0

    # -- geometry ---------------------------------------------------------------------
    def _grid_score(self, lum: np.ndarray) -> float:
        """Label-free plausibility of a candidate grid, from the address column's structure.

        Within one page, address character columns 0..5 are the *same* glyph on every row
        and column 7 is always '0'; column 6 is the row index, so it is 16 *different*
        glyphs; column 33 is the '-' separator on every row; and the separator columns
        between bytes are spaces, so any ink in them means the grid is off.  No glyph
        labels and no oracle are involved.

        This also breaks the whole-row ambiguity that a pure ink-contrast phase search
        cannot see: a grid one text line low scores almost as well on ink contrast, and
        the first version of this search picked exactly that, decoding every byte from
        the wrong line.
        """
        cols = np.asarray(list(range(8)) + [33])
        patches = self._all_patches(lum, self._x0, self._y0, cols)
        norm, blank = self._normalise(patches)
        # blank cells contribute a ZERO vector rather than being omitted: omitting them
        # let the mean similarity RISE when the grid slid onto the legend bar.
        norm = np.where(blank[..., None, None], 0.0, norm)
        flat = norm.reshape(N_ROWS, len(cols), -1)

        def pairwise(ci):
            m = flat[:, ci, :]
            g = m @ m.T
            return float((g.sum() - np.trace(g)) / (N_ROWS * (N_ROWS - 1)))

        same = sum(pairwise(c) for c in (0, 1, 2, 3, 4, 5, 7)) / 7.0
        distinct = pairwise(6)
        hyphen = pairwise(8)  # column 33 is index 8 in `cols`

        blank_cols = np.asarray([8, 9] + [9 + 3 * b for b in range(1, PAGE_COLS) if b != 8])
        glyph_cols = np.asarray([10, 11, 13, 14])
        ink_blank = float(np.abs(self._all_patches(lum, self._x0, self._y0, blank_cols)
                                 - 255.0).sum()) / len(blank_cols)
        ink_glyph = float(np.abs(self._all_patches(lum, self._x0, self._y0, glyph_cols)
                                 - 255.0).sum()) / len(glyph_cols)
        clean = -(ink_blank / ink_glyph) if ink_glyph > 0 else 0.0
        return same - distinct + hyphen + clean

    def _locate(self, lum: np.ndarray) -> Tuple[int, int]:
        """Grid origin, with a lock.

        The capture geometry does not change from frame to frame, so re-solving it on
        every frame is pure waste.  Solve it, then reuse for ``relock_every`` frames.
        Set ``relock_every=1`` to disable the lock (e.g. if the source is a mixed pile of
        photographs rather than one video).
        """
        if not self.refine_grid:
            return COL_X0, ROW_Y0
        if self._locked is not None and self._lock_ttl > 0:
            self._lock_ttl -= 1
            self.pitch_x, self.pitch_y = self._locked_pitch
            return self._locked

        prev_lock, prev_pitch = self._locked, self._locked_pitch
        if prev_lock is not None:
            # Only re-solve the grid on a frame that already reads well.  A re-lock that
            # lands on a mid-repaint frame solves the geometry from garbage and holds it
            # for the next `relock_every` frames.  Measured cost of not doing this: the
            # SAME 1501 frames decoded differently depending on the pipeline's dedup
            # setting (255 vs 978 wrong bytes), because the two runs called the extractor
            # a different number of times and therefore re-locked on different frames.
            self._x0, self._y0 = prev_lock
            self.pitch_x, self.pitch_y = prev_pitch
            if self._legibility(lum) < 0.55:
                self._lock_ttl = 3          # try again shortly, on a calmer frame
                return prev_lock
        self._x0, self._y0 = COL_X0, ROW_Y0
        g = self._grid(255.0 - lum, lum)
        new_pitch = (self.pitch_x, self.pitch_y)

        if prev_lock is not None:
            # A re-lock that happens to land on a frame caught mid-repaint solves the grid
            # from garbage and then holds that garbage for the next `relock_every` frames.
            # Measured: with the lock refreshed unconditionally, running the SAME 1501
            # frames with dedup on vs off gave 255 vs 973 wrong bytes purely because the
            # two runs re-locked on different frames.  So a new grid has to EARN the lock
            # on the very frame that proposed it.
            self._x0, self._y0 = g
            self.pitch_x, self.pitch_y = new_pitch
            new_score = self._grid_score(lum) + 2.0 * self._legibility(lum)
            self._x0, self._y0 = prev_lock
            self.pitch_x, self.pitch_y = prev_pitch
            old_score = self._grid_score(lum) + 2.0 * self._legibility(lum)
            if old_score >= new_score:
                g, new_pitch = prev_lock, prev_pitch

        self._locked, self._lock_ttl = g, max(0, self.relock_every - 1)
        self._locked_pitch = new_pitch
        self.pitch_x, self.pitch_y = new_pitch
        return g

    def _grid(self, ink: np.ndarray, lum: np.ndarray) -> Tuple[int, int]:
        if not self.refine_grid:
            return COL_X0, ROW_Y0
        y_lo, y_hi = ROW_Y0 - ROW_PITCH, ROW_Y0 + ROW_PITCH * N_ROWS + ROW_PITCH
        x_lo, x_hi = COL_X0 - COL_PITCH, COL_X0 + COL_PITCH * 56 + COL_PITCH
        band = ink[max(0, y_lo):y_hi, max(0, x_lo):x_hi]
        if band.size == 0:
            return COL_X0, ROW_Y0
        colprof = np.zeros(ink.shape[1]); colprof[max(0, x_lo):x_hi] = band.sum(axis=0)
        rowprof = np.zeros(ink.shape[0]); rowprof[max(0, y_lo):y_hi] = band.sum(axis=1)
        # stage 1: sub-pixel offset AND pitch.  Searching only a whole period of offset
        # lets the row grid slide by exactly one text line and score just as well, so the
        # offset search stays inside half a period and stage 2 resolves the rest.
        x0, self.pitch_x = _refine_phase_frac(colprof, 56, COL_X0, COL_PITCH, GLYPH_W,
                                              COL_PITCH / 2.0, 0.12)
        y0, self.pitch_y = _refine_phase_frac(rowprof, N_ROWS, ROW_Y0, ROW_PITCH, GLYPH_H,
                                              ROW_PITCH / 2.0, 0.18)
        # stage 2: resolve the remaining whole-cell ambiguity by content structure
        best, best_s = (x0, y0), -1e30
        for dy in (-self.pitch_y, 0.0, self.pitch_y):
            for dx in (-self.pitch_x, 0.0, self.pitch_x):
                self._x0, self._y0 = x0 + dx, y0 + dy
                if (self._y0 < 0 or self._x0 < 0
                        or self._y0 + self.pitch_y * N_ROWS >= lum.shape[0]
                        or self._x0 + self.pitch_x * 56 >= lum.shape[1]):
                    continue
                s = self._grid_score(lum)
                if s > best_s:
                    best, best_s = (self._x0, self._y0), s
        # stage 3: sub-pixel polish with the CONTENT score.  Stage 1 works on an ink
        # profile and cannot tell a half-pixel shift from a slightly different blur; on
        # the H.264 clip it settled one pixel left of true, which clipped the right-hand
        # column off every glyph and turned '8' into 'B' or '3' in byte after byte -- a
        # systematic error, i.e. exactly the kind voting is powerless against.
        bx, by = best
        best_s = -1e30
        for dy in np.arange(-0.75, 0.76, 0.25):
            for dx in np.arange(-0.75, 0.76, 0.25):
                self._x0, self._y0 = bx + dx, by + dy
                if (self._y0 < 0 or self._x0 < 0
                        or self._y0 + self.pitch_y * N_ROWS >= lum.shape[0]
                        or self._x0 + self.pitch_x * 56 >= lum.shape[1]):
                    continue
                s = self._grid_score(lum) + 2.0 * self._legibility(lum)
                if s > best_s:
                    best, best_s = (self._x0, self._y0), s
        return best

    def _legibility(self, lum: np.ndarray) -> float:
        """Mean classification confidence over the DATA cells at a candidate grid.

        The structural score only inspects the address block, so it is blind to a shift
        that is harmless there and ruinous 300 pixels to the right.  Measured on the
        H.264 clip: structure alone chose x0=89.25 (5.69% byte error) where x0=89.00 gives
        3.18% -- and the per-cell confidence is exactly the signal that separates them.
        Uses a throwaway bank so the persistent one is never trained at a rejected grid.
        """
        tmp = TemplateBank()
        for r in range(N_ROWS):
            tmp.learn(r, self._cell(lum, self._x0, self._y0, r, 6))
            tmp.learn(0, self._cell(lum, self._x0, self._y0, r, 7))
        t = tmp.templates()
        if t is None:
            return 0.0
        cols = np.asarray([c for b in range(PAGE_COLS) for c in byte_char_cols(b)])
        _, conf = self._classify(self._all_patches(lum, self._x0, self._y0, cols), t)
        return float(conf.mean())

    def _cell(self, lum: np.ndarray, x0: float, y0: float, r: int, c: int) -> np.ndarray:
        return self._all_patches(lum, x0, y0, np.asarray([c]))[r, 0]

    # -- classification ---------------------------------------------------------------
    @staticmethod
    def _match(patch: np.ndarray, templates: np.ndarray) -> Tuple[int, float, float]:
        p = _norm_patch(patch)
        if p is None:
            return -1, -1.0, -1.0
        scores = (templates * p[None, :, :]).sum(axis=(1, 2))
        order = np.argsort(scores)
        return int(order[-1]), float(scores[order[-1]]), float(scores[order[-2]])

    def _bootstrap(self, lum: np.ndarray, x0: float, y0: float) -> TemplateBank:
        """Glyphs 0..F from address char col 6 (= the row index) and col 7 (= '0').

        Returns a THROWAWAY bank.  Whether these samples also go into the persistent bank
        is decided afterwards, once we know the frame was worth learning from -- see
        `_maybe_learn`.  Training on every frame indiscriminately meant that a run with
        `--dedup off` fed ~510 mid-repaint frames' worth of garbled glyphs into the
        templates, and the same 1501 frames then decoded to 973 wrong bytes instead of
        255 purely because of how often the extractor had been called.
        """
        tmp = TemplateBank()
        self._last_samples = []
        for r in range(N_ROWS):
            p6 = self._cell(lum, x0, y0, r, 6)
            p7 = self._cell(lum, x0, y0, r, 7)
            tmp.learn(r, p6); tmp.learn(0, p7)
            self._last_samples.append((r, p6))
            self._last_samples.append((0, p7))
        return tmp

    def _maybe_learn(self, row_addr, conf: np.ndarray) -> None:
        """Fold this frame's glyph samples into the persistent bank only if the frame
        looks like a settled, fully consistent page."""
        if any(a is None for a in row_addr):
            return
        if any(row_addr[r] != row_addr[0] + 0x10 * r for r in range(N_ROWS)):
            return
        if float(conf.mean()) < 0.6:
            return
        if self._good_frames >= self.freeze_after:
            return   # frozen: see below
        self._good_frames += 1
        for label, patch in self._last_samples:
            self.bank.learn(label, patch)

    # -- vectorised cell grab ---------------------------------------------------------
    def _all_patches(self, lum: np.ndarray, x0: int, y0: int,
                     cols: np.ndarray) -> np.ndarray:
        """(n_rows, n_cols, GLYPH_H, GLYPH_W) in one fancy-index, no Python loop.

        The per-cell Python loop this replaces ran the whole extractor at 5.4 frames/s,
        which is below any plausible capture rate and would have made the live-V4L2 path
        a fiction.
        """
        ys = y0 + self.pitch_y * np.arange(N_ROWS)
        xs = x0 + self.pitch_x * np.asarray(cols, dtype=np.float64)
        dy = np.arange(GLYPH_H, dtype=np.float64)
        dx = np.arange(GLYPH_W, dtype=np.float64)
        yy = ys[:, None, None, None] + dy[None, None, :, None]
        xx = xs[None, :, None, None] + dx[None, None, None, :]
        return _bilinear(lum, yy, xx)

    @staticmethod
    def _normalise(patches: np.ndarray):
        p = patches.astype(np.float64)
        p = p - p.mean(axis=(-2, -1), keepdims=True)
        n = np.sqrt((p * p).sum(axis=(-2, -1), keepdims=True))
        blank = n[..., 0, 0] < 1e-6
        n = np.where(n < 1e-6, 1.0, n)
        return p / n, blank

    def _classify(self, patches: np.ndarray, templates: np.ndarray):
        """-> (labels, confidence) with labels -1 where the cell is blank."""
        norm, blank = self._normalise(patches)
        flat = norm.reshape(norm.shape[0], norm.shape[1], -1)
        scores = flat @ templates.reshape(16, -1).T      # (rows, cols, 16)
        part = np.partition(scores, -2, axis=-1)
        s1 = part[..., -1]
        s2 = part[..., -2]
        labels = np.argmax(scores, axis=-1)
        conf = _conf_vec(s1, s2)
        labels = np.where(blank, -1, labels)
        conf = np.where(blank, 0.0, conf)
        return labels, conf

    # -- main -------------------------------------------------------------------------
    def __call__(self, image: np.ndarray) -> dict:
        return self.extract(image)

    def extract(self, image: np.ndarray) -> dict:
        img = np.asarray(image)
        if img.ndim == 2:
            img = np.repeat(img[:, :, None], 3, axis=2)
        img = _resize_rgb(img[:, :, :3].astype(np.uint8), NOMINAL_W, NOMINAL_H)
        lum = _luma(img)

        x0, y0 = self._locate(lum)
        self._x0, self._y0 = x0, y0

        # bootstrap templates from this frame's address column, then classify with the
        # accumulated bank (which may already hold better templates from earlier frames)
        tmp_bank = self._bootstrap(lum, x0, y0)
        templates = self.bank.templates()
        if templates is None:
            templates = tmp_bank.templates()
        if templates is None:
            return _empty("template bootstrap failed (not a dump screen?)")

        addr_p = self._all_patches(lum, x0, y0, np.asarray(ADDR_COLS))
        a_lab, a_conf = self._classify(addr_p, templates)

        hi_cols = np.asarray([byte_char_cols(b)[0] for b in range(PAGE_COLS)])
        lo_cols = np.asarray([byte_char_cols(b)[1] for b in range(PAGE_COLS)])
        h_lab, h_conf = self._classify(self._all_patches(lum, x0, y0, hi_cols), templates)
        l_lab, l_conf = self._classify(self._all_patches(lum, x0, y0, lo_cols), templates)

        bad = (h_lab < 0) | (l_lab < 0)
        data = ((np.where(h_lab < 0, 0, h_lab) << 4)
                | np.where(l_lab < 0, 0, l_lab)).astype(np.uint8)
        data = np.where(bad, 0, data).astype(np.uint8)
        # both nibbles must be right for the byte to be right
        conf = (h_conf * l_conf).astype(np.float32)
        conf = np.where(bad, 0.0, conf).astype(np.float32)

        row_addr: List[Optional[int]] = []
        row_conf = np.zeros(N_ROWS, np.float32)
        for r in range(N_ROWS):
            if (a_lab[r] < 0).any():
                row_addr.append(None)
                row_conf[r] = 0.0
                continue
            a = 0
            for n in a_lab[r]:
                a = (a << 4) | int(n)
            row_addr.append(a)
            row_conf[r] = float(a_conf[r].min())

        if self.use_colour_check:
            _apply_colour_check_vec(img, x0, y0, data, conf,
                                    self.pitch_x, self.pitch_y)

        self._maybe_learn(row_addr, conf)

        base = row_addr[0]
        ok = base is not None
        return {
            "base_address": base,
            "bytes": data,
            "confidence": conf,
            "row_addresses": row_addr,
            "row_addr_confidence": row_conf,
            "ok": ok,
            "reason": "" if ok else "row 0 address unreadable",
        }


def _conf_from_margin(s1: float, s2: float) -> float:
    """Map (best NCC, runner-up NCC) to a probability-like confidence.

    Calibration intent: a clean 1.0/0.4 match must land very close to 1, an ambiguous
    0.7/0.69 must land near chance.  The logistic below is deliberately conservative --
    over-confidence is far more damaging to voting than under-confidence, because it lets
    one bad frame outvote several good ones.
    """
    if s1 < 0:
        return 0.0
    margin = max(0.0, s1 - s2)
    quality = max(0.0, min(1.0, (s1 - 0.3) / 0.6))
    p = 1.0 / (1.0 + np.exp(-(margin * 18.0 - 2.0)))
    return float(np.clip(p * quality, 0.0, 0.999))


def _conf_vec(s1: np.ndarray, s2: np.ndarray) -> np.ndarray:
    """Vectorised twin of _conf_from_margin."""
    margin = np.maximum(0.0, s1 - s2)
    quality = np.clip((s1 - 0.3) / 0.6, 0.0, 1.0)
    p = 1.0 / (1.0 + np.exp(-(margin * 18.0 - 2.0)))
    return np.clip(p * quality, 0.0, 0.999)


_HILITE_ARR = np.array([HILITE_RGB[k] for k in ("aqua", "yellow", "lime", "fuchsia")],
                       dtype=np.int32)
_HILITE_NAMES = ("aqua", "yellow", "lime", "fuchsia")
_HILITE_VALUE = np.array([0xF0, 0xF7, 0xFF, -1], dtype=np.int32)


def _apply_colour_check_vec(img: np.ndarray, x0: float, y0: float,
                            data: np.ndarray, conf: np.ndarray,
                            pitch_x: float = COL_PITCH,
                            pitch_y: float = ROW_PITCH) -> None:
    """Use the highlight background colour as independent evidence about the byte.

    The screen paints a cell's background aqua / yellow / lime when the byte equals the
    legend's F0 / F7 / FF.  That is a different physical channel from the glyph shape --
    chroma rather than luma -- so agreement is real corroboration and disagreement is a
    real warning.  Fuchsia is skipped: its legend value is user-settable and prints as
    "XX" by default, so it cannot be pinned to a number without parsing the legend.
    """
    ys = y0 + pitch_y * np.arange(PAGE_ROWS)
    xs = x0 + pitch_x * np.asarray([10 + 3 * b for b in range(PAGE_COLS)])
    dy = np.arange(GLYPH_H, dtype=np.float64)
    dx = np.arange(GLYPH_W * 2 + 1, dtype=np.float64)
    yy = (ys[:, None, None, None] + dy[None, None, :, None]).astype(np.int32)
    xx = (xs[None, :, None, None] + dx[None, None, None, :]).astype(np.int32)
    if yy.max() >= img.shape[0] or xx.max() >= img.shape[1]:
        return
    cells = img[yy, xx].astype(np.int32)                      # (16,16,h,w,3)
    d = np.abs(cells[..., None, :] - _HILITE_ARR[None, None, None, None, :, :]).sum(-1)
    near = d < 60                                             # (16,16,h,w,4)
    frac = near.mean(axis=(2, 3))                             # (16,16,4)
    which = np.argmax(frac, axis=-1)
    strong = frac.max(axis=-1) > 0.45                         # background, not stray ink
    want = _HILITE_VALUE[which]
    checkable = strong & (want >= 0)
    agree = checkable & (data.astype(np.int32) == want)
    disagree = checkable & (data.astype(np.int32) != want)
    conf[agree] = np.minimum(0.999, 1.0 - (1.0 - conf[agree]) * 0.25)
    conf[disagree] = conf[disagree] * 0.25


def _empty(reason: str) -> dict:
    return {
        "base_address": None,
        "bytes": np.zeros((PAGE_ROWS, PAGE_COLS), np.uint8),
        "confidence": np.zeros((PAGE_ROWS, PAGE_COLS), np.float32),
        "row_addresses": [None] * N_ROWS,
        "row_addr_confidence": np.zeros(N_ROWS, np.float32),
        "ok": False,
        "reason": reason,
    }


_default = ReferenceExtractor()


def extract(image: np.ndarray) -> dict:
    """Module-level convenience matching the c2 contract signature."""
    return _default.extract(image)
