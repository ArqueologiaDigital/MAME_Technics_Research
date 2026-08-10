"""The loop: track, read, vote, lock, draw.

`Engine` is the whole decoder and has no display in it, so the same code path
that runs behind the live window also runs headless in `selftest` -- which is
how any change to it gets a number rather than an impression.

`LiveApp` is the window around it.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from . import geom as G
from . import recog as R
from .store import DumpStore, WINDOWS


@dataclass
class EngineStats:
    frames: int = 0
    read: int = 0
    voted: int = 0
    skipped_motion: int = 0
    skipped_ladder: int = 0
    locked: int = 0
    conflicts: int = 0
    torn: int = 0
    reacquires: int = 0
    track_rejected: int = 0
    fps: float = 0.0
    ms: float = 0.0
    motion: float = 0.0
    last_reason: str = ""


class Engine:
    def __init__(self, store: DumpStore, reg: G.Registration,
                 bank: Optional[R.GlyphBank] = None,
                 seed_base: Optional[int] = None,
                 motion_gate: float = 0.22,
                 audit_period: int = 90,
                 decay: float = 0.0,
                 assume_aligned: bool = True,
                 restrict_windows: bool = True,
                 prealign: bool = True,
                 refine_budget: int = 44,
                 warmup: int = 4,
                 audit_rows: int = 4,
                 right_margin_min: float = 0.05):
        self.store = store
        self.reg = reg
        self.bank = bank or R.GlyphBank()
        self.reader = R.PageReader(
            self.bank, assume_aligned=assume_aligned,
            address_windows=[(lo, hi) for lo, hi, _ in WINDOWS] if restrict_windows else None)
        self.seed_base = seed_base
        self.motion_gate = motion_gate
        self.audit_period = audit_period
        self.decay = decay
        self.prealign = prealign
        self.refine_budget = refine_budget
        self.warmup = warmup
        self.audit_rows = audit_rows
        self.right_margin_min = right_margin_min
        self.stats = EngineStats()
        self.last: Optional[R.FrameReading] = None
        self.row_addr: Dict[int, int] = {}
        self._bad_streak = 0
        self._settle = 0
        self._vel = None
        self._best_ladder = 0.0
        self.panel = None
        self._audit_row = 0
        self._t_last = time.time()
        self._recent_locks: List[int] = []

    # -- helpers ------------------------------------------------------------ #
    def _quad_is_lost(self, panel) -> bool:
        """True when the registration is not plausibly on the detected screen."""
        px0, py0, px1, py1 = panel
        c = self.reg.quad.centre
        if not (px0 <= c[0] <= px1 and py0 <= c[1] <= py1):
            return True
        qw = float(np.ptp(self.reg.quad.corners[:, 0]))
        pw = max(px1 - px0, 1)
        return not (0.35 * pw <= qw <= 1.25 * pw)

    def _ink(self, frame: np.ndarray):
        x0, y0, x1, y1 = self.reg.quad.bbox(0.06)
        h, w = frame.shape[:2]
        x0 = max(0, min(x0, w - 2)); x1 = max(x0 + 2, min(x1, w))
        y0 = max(0, min(y0, h - 2)); y1 = max(y0 + 2, min(y1, h))
        cw, ch = self.reg.quad.cell_pitch()
        ry = max(2, int(round(ch * 1.3)))
        rx = max(2, int(round(cw * 3.0)))
        crop = frame[y0:y1, x0:x1]
        return G.ink_map(crop, ry, rx), (float(x0), float(y0)), crop

    def _wanted(self):
        """Which byte cells are still worth reading, per row.

        This is the "lock in and move on" rule made concrete: a cell already
        committed to the store is not cut, not matched and not voted on again,
        so a page that is 90 % done costs a tenth of what it did when it was
        blank.  One row per pass is exempted and re-read in full -- see the
        audit note in store.py -- because a locked byte that is wrong must have
        some way of being caught.
        """
        if not self.row_addr:
            return None, None
        # One row per frame is re-read in full, round-robin.  It does double
        # duty: it is the audit that can catch a locked byte that was wrong,
        # and its committed values are the balanced training set the templates
        # need (see the note in recog.read).
        # Audit several rows per frame, not one.  With one row the round trip is
        # sixteen frames, so over a normal dwell a given row is re-read about
        # three times -- and overturning a committed byte needs four frames of
        # agreement, so the audit could never actually correct anything it
        # found.  An audit that cannot overturn a wrong byte is decoration.
        audit = {(self._audit_row + k) % G.NROW for k in range(self.audit_rows)}
        self._audit_row = (self._audit_row + self.audit_rows) % G.NROW
        out: Dict[int, List[int]] = {}
        known: Dict[int, Tuple[int, Dict[int, int]]] = {}
        for r in range(G.NROW):
            a = self.row_addr.get(r)
            if a is None:
                out[r] = list(range(16))
                continue
            if r in audit:
                out[r] = list(range(16))
                vals = {}
                for k in range(16):
                    v = self.store.get((a + k) & 0xFFFFFFFF)
                    if v is not None:
                        vals[k] = v
                if vals:
                    known[r] = (a, vals)
                continue
            out[r] = [k for k in range(16) if not self.store.is_locked((a + k) & 0xFFFFFFFF)]
        return out, known

    def _referee(self, quad: G.Quad, ink, origin) -> float:
        """What a candidate geometry is judged on.

        Dominated by the number of rows whose eight-digit address reads
        cleanly AND agrees with its neighbours' -- sixteen rows ascending by
        exactly 0x10 is not something a misplaced grid stumbles into.  The
        match strength across a spread of far-right columns breaks ties, and is
        there for the one thing the ladder is blind to: the ladder lives in the
        left eighth of the block, so on its own it cannot see the far end
        sliding off, which with a handheld camera is exactly how a fit dies.
        """
        saved = self.reg
        self.reg = G.Registration(quad, ncols=saved.ncols)
        try:
            if self.bank.ready:
                return self.reader.score_geometry(self.reg, ink, origin)
            # Before there are any templates the ladder is still a usable
            # objective, and a continuous one: it falls off smoothly as the grid
            # slides, so the same search works. Without this the cold start had
            # no refinement at all -- bootstrap simply refused until the corners
            # happened to be within about a pixel, and a pixel and a half of
            # placement error was the difference between 223 committed bytes
            # and none.
            sc, ok, _, _ = self.reader.ladder_geometry(self.reg, ink, origin)
            return sc + (1.0 if ok else 0.0)
        finally:
            self.reg = saved

    def _refine(self, ink, origin, rd: Optional[R.FrameReading]) -> Optional[float]:
        """Follow the camera, and never make the fit worse than it already is.

        A handheld camera moves the panel every frame, and it changes the
        perspective as well as the position, so something has to re-solve the
        geometry continuously.  Two things do it here, and the second is what
        makes the first safe:

          1. an analytic proposal -- re-solve the homography from where each
             glyph actually sits relative to its matched template;
          2. acceptance only on a STRICT IMPROVEMENT of the referee, with a few
             small translations tried as alternatives.

        The proposal on its own is not trustworthy: eight parameters fitted to
        a few hundred sub-pixel displacements is over-determined in the two
        projective directions, and unguarded it walked a perfectly-placed grid
        11 px off the text in seven frames while every internal number still
        looked healthy.  Requiring a strict improvement makes the whole step
        monotone, so the worst a bad proposal can do is nothing at all.
        """
        base_c = self.reg.quad.corners.copy()
        best_q = G.Quad(base_c.copy())
        best = self._referee(best_q, ink, origin)
        moved, budget = None, self.refine_budget

        def try_quad(q):
            nonlocal best, best_q, moved, budget
            if budget <= 0:
                return False
            budget -= 1
            s = self._referee(q, ink, origin)
            if s > best + 1e-9:
                best, best_q = s, q
                return True
            return False

        # Predict, then correct.  A hand drifts smoothly, so where the panel
        # was going last frame is a good guess for where it is now; without
        # this the search is always one frame behind and, worse, its per-frame
        # step when it believes itself healthy is deliberately small -- so it
        # can lag a slow drift indefinitely while every candidate it tries is
        # an improvement on the last. Measured: the fit sat 3-6 px off the text
        # for as long as the drift continued, and never committed a byte.
        if self._vel is not None and np.abs(self._vel).max() > 1e-3:
            # Per CORNER, not per centre.  A hand changes its distance and its
            # angle as well as its position, so the four corners move at four
            # different velocities, and predicting a single translation leaves
            # the scale and perspective drift uncorrected -- with which the
            # tracker lags by 0.2 to 0.5 of a cell and the read never reaches
            # the quality the commit gate demands.  Measured, this is the
            # difference between committing nothing under hand movement and
            # committing 150-180 bytes a page.
            for k in (1.0, 0.5):
                try_quad(G.Quad(base_c + k * self._vel))

        if self.bank.ready and rd is not None and rd.track_resid is not None:
            for gain in (0.7, 0.3):
                trial = G.Registration(G.Quad(best_q.corners.copy()), ncols=self.reg.ncols)
                d = G.track_homography(trial, rd.cells, rd.track_resid, rd.track_weight, gain=gain)
                if d is not None and try_quad(trial.quad):
                    moved = d

        # Coarse to fine.  The scales matter: with only a coarse step the search
        # cannot settle -- a placement error of one pixel in twelve was enough
        # to stall it below the acceptance threshold indefinitely, because every
        # move it could make overshot.  With only a fine step it cannot keep up
        # with a hand.  Scale and keystone are in the set because a camera held
        # by hand changes its distance and its angle, not just its position.
        # Spend the budget where it is needed.  When the fit is already reading
        # every row there is nothing coarse to look for and the search only has
        # to hold sub-pixel station, which costs a handful of evaluations; when
        # rows are being lost, the camera has moved and the coarse steps earn
        # their cost.  Without this the search burned its whole budget on every
        # frame even when perfectly locked, and the frame rate -- which is the
        # operator's feedback loop -- paid for nothing.
        cw, ch = best_q.cell_pitch()
        # Judge "healthy" on the previous frame's FULL read, not on this
        # candidate's coarse score -- the coarse scorer is deliberately
        # approximate and reading it as an absolute would keep the search on
        # the expensive path for ever.
        levels = (0.4, 0.15, 0.06, 0.02) if (self._settle > 0 and self.bank.ready) \
            else (1.0, 0.4, 0.15, 0.06, 0.02)
        for f in levels:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = G.Quad(best_q.corners.copy())
                q.translate(dx * 0.30 * f * cw, dy * 0.30 * f * ch)
                if try_quad(q):
                    moved = max(moved or 0.0, 0.30 * f)
            if f < 0.3:
                continue      # shape only needs correcting at the coarse scales
            for sc in (1 + 0.006 * f, 1 - 0.006 * f):
                q = G.Quad(best_q.corners.copy()); q.scale(sc, sc); try_quad(q)
                q = G.Quad(best_q.corners.copy()); q.scale(sc, 1.0); try_quad(q)
            for k in (0.006 * f, -0.006 * f):
                q = G.Quad(best_q.corners.copy()); q.keystone(kx=k); try_quad(q)
                q = G.Quad(best_q.corners.copy()); q.keystone(ky=k); try_quad(q)
        if moved is None:
            self.stats.track_rejected += 1
        step = best_q.corners - base_c
        self._vel = (0.55 * self._vel + 0.45 * step) if self._vel is not None else step
        self.reg = G.Registration(best_q, ncols=self.reg.ncols)
        return moved

    # -- one frame ---------------------------------------------------------- #
    def process(self, frame: np.ndarray, vote: bool = True) -> R.FrameReading:
        t0 = time.time()
        self.stats.frames += 1

        # Before anything expensive: is the camera even looking at the screen?
        # It will not be for the first few seconds -- the operator has to pick it
        # up and aim it -- and the registration search is meaningless until it
        # is.  Skipping it here is what keeps those seconds responsive.
        if not self.bank.ready or self.lost:
            self.panel = G.screen_candidate(frame)
            if self.panel is None:
                self.stats.last_reason = "point the camera at the screen"
                self.last = None
                self._finish_timing(t0)
                return R.FrameReading(rows=[], base=None, n_rows_ok=0)
            # Aim the quad at the screen we just found, if it is nowhere near
            # it.  Without this, a quad seeded from a frame taken before the
            # camera was raised stays parked on a piece of the room for ever.
            if self._quad_is_lost(self.panel):
                self.reg = G.Registration(G.auto_seed_from(self.panel), ncols=self.reg.ncols)
                self.stats.last_reason = "found the screen -- aiming"

        ink, origin, crop = self._ink(frame)

        # Templates learned through a registration that turned out to be wrong
        # are not merely useless, they are unrecoverable: they classify
        # confidently and consistently, so nothing downstream ever complains.
        # If a supposedly-trained bank has produced no readable row for this
        # long, the templates are the suspect and the only fix is to bin them.
        if self.bank.ready and self._bad_streak > 120:
            self.bank = R.GlyphBank(self.bank.gh, self.bank.gw, self.bank.min_samples)
            self.reader.bank = self.bank
            self._bad_streak = 0
            self.stats.last_reason = "templates were not working -- relearning"

        # Refine first, always -- including before the templates exist, where
        # the referee falls back to the ladder.
        motion = self._refine(ink, origin, self.last)

        if not self.bank.ready:
            # ⚠ The cold start is the fragile part of this tool, and the reason
            # the corners are draggable and the picture can be frozen.  Bootstrap
            # has no templates to check itself against, so if the camera drifts
            # while it is still learning, it trains on a slipping grid, declares
            # itself ready, and is then confidently wrong with no way back --
            # measured, rows read 15 or 16 of 16 for six frames and then
            # collapsed to zero by frame twenty.  Freezing the picture to place
            # the corners avoids all of it, which is why the live view keeps
            # decoding (without committing) while paused.
            ok, why = self.reader.bootstrap(self.reg, ink, self.seed_base, origin)
            if not ok:
                # Nothing can be tracked yet -- tracking needs templates and
                # templates need a registration -- so the only way out of the
                # deadlock is to search for the registration directly, against
                # the one criterion that works with no templates at all.
                if self.reacquire(frame):
                    ink, origin, crop = self._ink(frame)
                    ok, why = self.reader.bootstrap(self.reg, ink, self.seed_base, origin)
            self.stats.last_reason = why if not ok else "training (%d/16 classes)" % self.bank.coverage
            if not ok:
                self._bad_streak += 1
                self.last = None
                self._finish_timing(t0)
                return R.FrameReading(rows=[], base=None, n_rows_ok=0)

        # While the templates are young they were trained through a registration
        # that was still converging, so forget quickly at first: otherwise the
        # blur of the first, worst-aligned frames is averaged into the templates
        # for ever and caps the match margin from then on.
        young = int(self.bank.n.sum()) < 2500
        wanted, known = self._wanted()
        rd = self.reader.read(self.reg, ink, wanted, train=True,
                              decay=max(self.decay, 0.03) if young else self.decay,
                              origin=origin, known=known, rgb=crop)
        self.stats.read += 1
        self.last = rd

        rd.motion = motion
        # `moved is None` means no candidate geometry beat the one we had, i.e.
        # the fit is already at a local optimum -- that is zero motion, not
        # unknown motion, and leaving the HUD showing the last non-zero value
        # would read as "still moving" when the camera has in fact settled.
        self.stats.motion = motion if motion is not None else 0.0

        # Warm-up.  Nothing is committed until the geometry has been stable and
        # complete for a few consecutive frames.  This is not caution for its
        # own sake: multi-frame agreement defends against NOISE, and the reads
        # taken while the registration is still converging are not noisy, they
        # are consistently wrong -- so they agree with each other and sail
        # through the vote.  Measured, that alone put four wrong bytes into a
        # store of 247, every one of them committed in the first few frames.
        # "Settled" means the READING is complete and the templates cover every
        # class -- deliberately NOT "the camera has stopped moving".  A handheld
        # camera never stops, so gating on stillness would mean never
        # committing anything; what matters is that the grid is on the text and
        # the classifier has something to classify with.
        # Gate on the ladder passing, not on a perfect 16 of 16.  Demanding
        # perfection here was tried, and under any hand movement the row count
        # flickers between 14 and 16, so the counter never reached the warm-up
        # and nothing was ever committed.  What made the strict gate necessary
        # -- confident wrong reads from a slightly-off grid -- is now caught per
        # byte by the jitter check in recog.read, which is a better place for
        # it: it rejects the individual bytes that are unsafe instead of
        # throwing away the whole frame.
        # Every one of these is load-bearing and each was established by a
        # measurement, not by taste:
        #   * 15 of 16 rows, not merely "the ladder passed" (14).  Relaxing this
        #     was tried twice, with the jitter check and the right-margin gate
        #     both in place, and both times it put wrong bytes into the store
        #     (2 of 242 in one run, 9 of 178 in another).  A frame one row short
        #     of perfect has a slightly-wrong geometry, and a slightly-wrong
        #     geometry does not produce noise -- it produces the same wrong
        #     answer every time, confidently.
        #   * the far-right columns must match well too, because the ladder only
        #     proves the left-hand end of each row.
        #   * every glyph class must have been seen, or the classifier is
        #     guessing on the ones it has not.
        # The consequence is that a badly-tracked session commits NOTHING rather
        # than committing something plausible.  That is the intended trade.
        settled = (rd.n_rows_ok >= G.NROW - 1
                   and rd.metrics.get("right_margin", 0.0) >= self.right_margin_min
                   and int(self.bank.n.min()) >= 8)
        self._settle = (self._settle + 1) if settled else 0

        if not rd.ladder_ok:
            self._bad_streak += 1
            self.stats.skipped_ladder += 1
            self.stats.last_reason = "ladder %d/16 rows" % rd.n_rows_ok
        else:
            self._bad_streak = 0
            self.row_addr = {rr.row: rr.address for rr in rd.rows if rr.accepted}
            if rd.torn:
                self.stats.torn += 1
            if motion is not None and motion > self.motion_gate:
                self.stats.skipped_motion += 1
                self.stats.last_reason = "moving (%.2f cell)" % motion
            elif self._settle < self.warmup:
                self.stats.last_reason = "settling (%d/%d)" % (self._settle, self.warmup)
            elif vote:
                self._vote(rd)
                self.stats.last_reason = ""

        self._finish_timing(t0)
        return rd

    def _vote(self, rd: R.FrameReading) -> None:
        self.stats.voted += 1
        fid = self.stats.frames
        locked: List[int] = []
        for addr, (val, margin) in rd.values.items():
            w = float(np.clip((margin - self.reader.byte_margin_min) / 0.06, 0.05, 1.0))
            what = self.store.observe(addr, val, w, fid)
            if what == "lock":
                locked.append(addr)
                self.stats.locked += 1
            elif what == "conflict":
                self.stats.conflicts += 1
        if locked:
            locked.sort()
            run = [locked[0]]
            for a in locked[1:]:
                if a == run[-1] + 1:
                    run.append(a)
                else:
                    self._journal_run(run); run = [a]
            self._journal_run(run)
            self._recent_locks = locked[-64:]
        self.store.snapshot()

    def _journal_run(self, run: List[int]) -> None:
        vals = [self.store.get(a) for a in run]
        if any(v is None for v in vals):
            return
        ev = [self.store.last_evidence.get(a, (0.0, 0)) for a in run]
        self.store.commit_row(run[0], vals, ev)

    def _finish_timing(self, t0: float) -> None:
        now = time.time()
        self.stats.ms = (now - t0) * 1000.0
        dt = now - self._t_last
        self._t_last = now
        if dt > 0:
            self.stats.fps = 0.85 * self.stats.fps + 0.15 * (1.0 / dt) if self.stats.fps else 1.0 / dt

    # -- recovery ----------------------------------------------------------- #
    def _ink_over(self, frame: np.ndarray, quad: G.Quad, pad: float):
        """Ink map over a padded box around `quad`, computed once."""
        x0, y0, x1, y1 = quad.bbox(pad)
        h, w = frame.shape[:2]
        x0 = max(0, min(x0, w - 2)); x1 = max(x0 + 2, min(x1, w))
        y0 = max(0, min(y0, h - 2)); y1 = max(y0 + 2, min(y1, h))
        cw, ch = quad.cell_pitch()
        return (G.ink_map(frame[y0:y1, x0:x1], max(2, int(round(ch * 1.3))),
                          max(2, int(round(cw * 3.0)))), (float(x0), float(y0)))

    def _score_quad(self, q: G.Quad, ink, origin) -> float:
        reg = G.Registration(q, ncols=self.reg.ncols)
        if self.bank.ready:
            rd = self.reader.read(reg, ink, wanted={}, train=False, origin=origin)
            return 2.0 + rd.n_rows_ok / 16.0
        s, ok, _, _ = self.reader.ladder_geometry(reg, ink, origin)
        return s + (1.0 if ok else 0.0)

    def reacquire(self, frame: np.ndarray, span: float = 1.5, steps: int = 5,
                  min_interval: float = 0.5) -> bool:
        """Local search for the registration when tracking has nothing to hold.

        Coarse then fine over translation and a uniform scale, around the
        current quad.  This is for "the operator's hands drifted and the lock
        let go", and for the cold start where there are no templates yet and so
        nothing to track with -- not for finding the panel from nothing.  It is
        scored by the ladder, the one criterion here that a wrong answer cannot
        satisfy, and rate-limited because a full search costs more than a frame.
        """
        now = time.time()
        if now - getattr(self, "_last_reacq", 0.0) < min_interval:
            return False
        self._last_reacq = now
        self.stats.reacquires += 1
        # ONE ink map for the whole search.  Recomputing it per candidate -- the
        # obvious way to write this, and how it was written -- made a single
        # re-acquire cost about 750 ms, because the ink map is the expensive
        # part and the search tries dozens of candidates.  They all live inside
        # one padded box, so one map serves all of them.
        ink, origin = self._ink_over(frame, self.reg.quad, 0.6)
        cw, ch = self.reg.quad.cell_pitch()
        best = (-1e9, G.Quad(self.reg.quad.corners.copy()))
        # One scale before the templates exist.  A cold-start search is the
        # single most expensive thing this tool does, it runs on frames where
        # the operator is still aiming, and every candidate it tries costs a
        # full ladder evaluation -- three scales by seven by seven was 172 of
        # them per call, which is where the first seconds went.
        scales = (1.0,) if not self.bank.ready else (0.96, 1.0, 1.04)
        for sx in scales:
            for dx in np.linspace(-span * cw, span * cw, steps):
                for dy in np.linspace(-span * ch, span * ch, steps):
                    q = G.Quad(self.reg.quad.corners.copy())
                    q.scale(sx, sx)
                    q.translate(dx, dy)
                    s = self._score_quad(q, ink, origin)
                    if s > best[0]:
                        best = (s, q)
        for dx in np.linspace(-0.25 * cw, 0.25 * cw, 3):
            for dy in np.linspace(-0.25 * ch, 0.25 * ch, 3):
                q = G.Quad(best[1].corners.copy())
                q.translate(dx, dy)
                s = self._score_quad(q, ink, origin)
                if s > best[0]:
                    best = (s, q)
        # Monotone, like the per-frame refinement: a search that is allowed to
        # settle for something worse than what it started with turns a fit that
        # was merely struggling into one that is lost.
        if best[0] > self._score_quad(self.reg.quad, ink, origin) + 1e-9:
            self.reg = G.Registration(best[1], ncols=self.reg.ncols)
            self._bad_streak = 0
            return True
        return False

    @property
    def lost(self) -> bool:
        return self._bad_streak > 45


# --------------------------------------------------------------------------- #
HELP = [
    ("mouse drag", "move a corner (or the whole quad from inside it)"),
    ("1 2 3 4", "select corner TL TR BR BL;  0 = whole quad"),
    ("arrows", "nudge selection by 1 px  (shift: 0.2 px, ctrl: 10 px)"),
    ("+ / -", "scale the quad about its centre"),
    ("[ / ]", "narrow / widen (horizontal scale only)"),
    ("SPACE", "freeze the picture (place the corners on a still)"),
    ("a", "auto-seed the quad from the brightest region"),
    ("r", "re-acquire: local search for the grid"),
    ("t", "reset the trained templates and start learning again"),
    ("x", "forget everything read for the page on screen"),
    ("s", "snapshot the store to disk now"),
    ("g", "cycle overlay: cells -> quad only -> off"),
    ("h", "this help"),
    ("q / ESC", "quit (the store is flushed first)"),
]


class LiveApp:
    def __init__(self, engine: Engine, source, calib_path: Optional[str] = None,
                 win: Tuple[int, int] = (1500, 860), decode_hz: float = 12.0):
        from .overlay import Renderer
        self.e = engine
        self.src = source
        self.calib_path = calib_path
        self.decode_period = 1.0 / max(decode_hz, 0.5)
        self.rnd = Renderer(win[0], win[1])
        self.selected: Optional[int] = None
        self.paused = False
        self.show = 0
        self.show_help = False
        self.frame: Optional[np.ndarray] = None
        self.drag: Optional[Tuple[int, float, float]] = None
        self._vs = (1.0, (0, 0))
        self._msg = ""
        self._msg_t = 0.0

    # -- state -------------------------------------------------------------- #
    def _page(self):
        base = None
        if self.e.last is not None and self.e.last.base is not None:
            base = self.e.last.base
        elif self.e.row_addr.get(0) is not None:
            base = self.e.row_addr[0]
        if base is None:
            return None, bytes(256), bytes(256), {}, set()
        pbase = self.e.store.page_of(base)
        data, mask = self.e.store.page_state(pbase)
        votes = {}
        pv = self.e.store._votes.get(pbase, {})
        for i, vt in pv.items():
            _, w, _, _ = vt.best()
            votes[i] = w
        conf = {int(c["a"], 16) - pbase for c in self.e.store.conflicts[-256:]
                if pbase <= int(c["a"], 16) < pbase + 256}
        return base, bytes(data), bytes(mask), votes, conf

    def _hud(self):
        s = self.e.stats
        rd = self.e.last
        cov = self.e.store.coverage()
        base, data, mask, votes, conf = self._page()
        nl = sum(mask)
        from .overlay import (COL_TEXT, COL_DIM, COL_LOCKED, COL_WARN,
                              COL_UNKNOWN, COL_CONFLICT, COL_PARTIAL)

        def c(ok, warn=False):
            return COL_LOCKED if ok else (COL_WARN if warn else COL_UNKNOWN)

        rows_ok = rd.n_rows_ok if rd else 0
        sep = self.e.bank.separation() if self.e.bank.ready else 0.0
        mg = (rd.metrics.get("addr_margin", 0.0) if rd else 0.0)
        rmarg = (rd.metrics.get("right_margin", 0.0) if rd else 0.0)
        lines = [
            ("source", "%s  %dx%d" % (self.src.name, self.src.size[0], self.src.size[1]), COL_DIM),
            ("fps / decode", "%.1f   %.0f ms" % (s.fps, s.ms), COL_TEXT),
            ("", "", COL_TEXT),
            ("TEMPLATES", "%d/16 classes%s" % (self.e.bank.coverage,
                                               "" if self.e.bank.ready else "  LEARNING"),
             c(self.e.bank.ready)),
            ("separation", "%.3f" % sep, c(sep > 0.10, sep > 0.05)),
            ("match margin", "%.3f" % mg, c(mg > 0.06, mg > 0.03)),
            ("", "", COL_TEXT),
            ("ADDRESS LADDER", "%d/16 rows" % rows_ok, c(rows_ok >= 15, rows_ok >= 8)),
            ("far-right match", "%.3f" % rmarg,
             c(rmarg >= self.e.right_margin_min, rmarg >= self.e.right_margin_min * 0.6)),
            ("motion", "%.2f cell%s" % (s.motion, "  HELD" if s.motion > self.e.motion_gate else ""),
             c(s.motion <= self.e.motion_gate, s.motion < self.e.motion_gate * 2)),
            ("torn frames", "%d" % s.torn, COL_DIM),
            ("status", s.last_reason or "reading", COL_WARN if s.last_reason else COL_LOCKED),
            ("", "", COL_TEXT),
            ("THIS PAGE", "%d/256 locked" % nl, c(nl == 256, nl > 0)),
            ("conflicts", "%d" % len(self.e.store.conflicts),
             COL_CONFLICT if self.e.store.conflicts else COL_DIM),
            ("frames voted", "%d of %d" % (s.voted, s.frames), COL_DIM),
            ("", "", COL_TEXT),
        ]
        for name, got, size in cov:
            pct = (100.0 * got / size) if size else 0.0
            lines.append((name.split(" (")[0], "%s  %.3f%%" % ("{:,}".format(got), pct), COL_TEXT))
        return lines, nl

    # -- events ------------------------------------------------------------- #
    def _note(self, txt):
        self._msg = txt
        self._msg_t = time.time()

    def _handle(self, ev) -> bool:
        import pygame
        if ev.type == pygame.QUIT:
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            fx, fy = self.rnd.to_frame(ev.pos[0], ev.pos[1], *self._vs)
            i, d = self.e.reg.quad.nearest_corner(fx, fy)
            cw, ch = self.e.reg.quad.cell_pitch()
            if d < max(6 * cw, 20):
                self.selected = i
                self.drag = (i, fx, fy)
            else:
                self.drag = (-1, fx, fy)
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self.drag = None
        elif ev.type == pygame.MOUSEMOTION and self.drag is not None:
            fx, fy = self.rnd.to_frame(ev.pos[0], ev.pos[1], *self._vs)
            i, px, py = self.drag
            if i >= 0:
                self.e.reg.quad.move_corner(i, fx - px, fy - py)
            else:
                self.e.reg.quad.translate(fx - px, fy - py)
            self.e.reg.bake()
            self.drag = (i, fx, fy)
        elif ev.type == pygame.KEYDOWN:
            k = ev.key
            mods = pygame.key.get_mods()
            step = 0.2 if mods & pygame.KMOD_SHIFT else (10.0 if mods & pygame.KMOD_CTRL else 1.0)
            if k in (pygame.K_q, pygame.K_ESCAPE):
                return False
            elif k == pygame.K_SPACE:
                self.paused = not self.paused
                if not self.paused and self.frame is not None:
                    # The camera did not hold still while the picture was
                    # frozen, so on resuming, the panel is no longer where the
                    # operator just placed the corners.  Re-acquire immediately
                    # rather than waiting for the lost-fit timeout, which is
                    # long by design and would spend it hunting.
                    self.e.reacquire(self.frame, min_interval=0.0)
                self._note("frozen -- place the corners" if self.paused else "running")
            elif k in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                self.selected = k - pygame.K_1
            elif k == pygame.K_0:
                self.selected = None
            elif k in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                dx = (-step if k == pygame.K_LEFT else step if k == pygame.K_RIGHT else 0.0)
                dy = (-step if k == pygame.K_UP else step if k == pygame.K_DOWN else 0.0)
                if self.selected is None:
                    self.e.reg.quad.translate(dx, dy)
                else:
                    self.e.reg.quad.move_corner(self.selected, dx, dy)
                self.e.reg.bake()
            elif k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self.e.reg.quad.scale(1.004, 1.004); self.e.reg.bake()
            elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.e.reg.quad.scale(0.996, 0.996); self.e.reg.bake()
            elif k == pygame.K_LEFTBRACKET:
                self.e.reg.quad.scale(0.996, 1.0); self.e.reg.bake()
            elif k == pygame.K_RIGHTBRACKET:
                self.e.reg.quad.scale(1.004, 1.0); self.e.reg.bake()
            elif k == pygame.K_a and self.frame is not None:
                self.e.reg = G.Registration(G.auto_seed(self.frame), ncols=self.e.reg.ncols)
                self._note("auto-seeded")
            elif k == pygame.K_r and self.frame is not None:
                self._note("re-acquired" if self.e.reacquire(self.frame) else "re-acquire failed")
            elif k == pygame.K_t:
                self.e.bank = R.GlyphBank(self.e.bank.gh, self.e.bank.gw, self.e.bank.min_samples)
                self.e.reader.bank = self.e.bank
                self._note("templates cleared")
            elif k == pygame.K_x:
                base, *_ = self._page()
                if base is not None:
                    n = self.e.store.forget_page(self.e.store.page_of(base))
                    self._note("forgot %d bytes of %08X" % (n, self.e.store.page_of(base)))
            elif k == pygame.K_s:
                self.e.store.snapshot(force=True)
                self._save_calib()
                self._note("saved")
            elif k == pygame.K_g:
                self.show = (self.show + 1) % 3
            elif k == pygame.K_h:
                self.show_help = not self.show_help
        return True

    def _save_calib(self):
        if not self.calib_path:
            return
        with open(self.calib_path, "w") as fh:
            json.dump(self.e.reg.to_json(), fh, indent=1)

    # -- main --------------------------------------------------------------- #
    def run(self) -> int:
        import pygame
        clock = pygame.time.Clock()
        running = True
        last_bank_save = time.time()
        last_decode = 0.0
        while running:
            for ev in pygame.event.get():
                if not self._handle(ev):
                    running = False
            f = self.src.read()
            if f is not None:
                self.frame = f
            if self.frame is None:
                if not getattr(self.src, "alive", True):
                    err = getattr(self.src, "error", "")
                    print("capture ended. ffmpeg said:\n%s" % (err or "(nothing)"))
                    break
                clock.tick(30)
                continue
            # Decode on its own clock, draw on every pass.  A decode costs tens
            # of milliseconds and the picture must not wait for it: while the
            # operator is aiming the camera, a smooth view is the whole product,
            # and a window that redraws at the decoder's rate is unusable for
            # pointing something by hand.
            #
            # Decoding while FROZEN but never committing is what makes placing
            # the corners possible at all: the operator drags a handle and
            # watches ADDRESS LADDER climb, instead of guessing and unfreezing
            # to find out.  It is also the right moment for the templates to be
            # learned -- on a still image, at a registration just perfected --
            # which is exactly the cold start the automatic path is worst at.
            now = time.time()
            if now - last_decode >= self.decode_period:
                last_decode = now
                self.e.process(self.frame, vote=not self.paused)
                if self.e.lost and not self.paused:
                    self.e.reacquire(self.frame)

            self._draw()
            if time.time() - last_bank_save > 30 and self.e.bank.ready:
                self.e.bank.save(os.path.join(self.e.store.path, "bank.npz"))
                self._save_calib()
                last_bank_save = time.time()
            clock.tick(60)

        self.e.store.close()
        if self.e.bank.ready:
            self.e.bank.save(os.path.join(self.e.store.path, "bank.npz"))
        self._save_calib()
        pygame.quit()
        return 0

    def _draw(self):
        import pygame
        from .overlay import COL_BG, COL_TEXT, COL_DIM, COL_LOCKED, COL_WARN
        sc = self.rnd.screen
        W, H = sc.get_size()
        panel_w = 470
        sc.fill(COL_BG)
        vid = (0, 0, W - panel_w, H)
        scale, origin = self.rnd.blit_frame(self.frame, vid)
        self._vs = (scale, origin)

        base, data, mask, votes, conf = self._page()
        if self.show < 2:
            self.rnd.draw_grid(self.e.reg, mask, votes, conf, scale, origin,
                               self.selected, show_cells=(self.show == 0))

        lines, nl = self._hud()
        self.rnd.draw_hud((W - panel_w, 0, panel_w, 430), lines)
        self.rnd.bar((W - panel_w + 8, 434, panel_w - 16, 10), nl / 256.0,
                     COL_LOCKED if nl == 256 else COL_WARN)
        self.rnd.draw_page((W - panel_w, 450, panel_w, H - 450), base, data, mask, votes, conf)

        if self.paused:
            sc.blit(self.rnd.f_big.render("FROZEN -- place the corners, SPACE to resume",
                                          True, COL_WARN), (12, 10))
        if self._msg and time.time() - self._msg_t < 3:
            sc.blit(self.rnd.f_big.render(self._msg, True, COL_TEXT), (12, H - 34))
        if self.show_help:
            y = 40
            box = pygame.Surface((560, 24 * len(HELP) + 20))
            box.set_alpha(235); box.fill((10, 10, 14))
            sc.blit(box, (12, y - 10))
            for kk, vv in HELP:
                sc.blit(self.rnd.f_small.render(kk, True, COL_WARN), (24, y))
                sc.blit(self.rnd.f_small.render(vv, True, COL_TEXT), (140, y))
                y += 24
        else:
            sc.blit(self.rnd.f_small.render("h = help", True, COL_DIM), (12, H - 58))
        pygame.display.flip()
