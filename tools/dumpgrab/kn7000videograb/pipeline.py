"""The video pipeline: frames in, a sparse ROM image + coverage report out.

Streaming by construction -- one 3-frame ring buffer for the temporal tear detector and
one accumulator per *live* page.  A page is flushed as soon as the sweep has moved a
configurable distance past it, so memory does not grow with the length of the capture and
a four-hour sweep costs the same as a four-second one.

Stage order, and why:

  frame -> signature -> [identical? reuse cached extraction] -> extract
        -> tear detect -> route rows to page accumulators -> flush -> assemble

The signature gate is *before* extraction because extraction is the expensive stage.  But
note the distinction it draws: bit-identical frames carry no new information and are
reused, whereas merely *similar* frames are re-extracted, because on analog capture those
differ by noise and each one is a fresh, independent vote.  Collapsing them would throw
away exactly the redundancy that makes video worth using.
"""

from __future__ import annotations

import time
from collections import OrderedDict, deque
from statistics import median
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import numpy as np

from . import tearing
from .assembly import SparseImage, coverage_report
from .contract import PAGE_ROWS, PageObservation, normalize
from .voting import FrameSignature, PageAccumulator, VotedPage


@dataclass
class PipelineConfig:
    vote_mode: str = "bayes"           # bayes | weighted
    # DEFAULT IS "off", and that is a measured choice, not laziness.  Two reasons:
    # (1) on real analog capture no two frames are ever bit-identical, so the dedup gate
    #     would never fire anyway -- the default should match reality;
    # (2) measured on the 1501-frame clean sweep, "off" gave 133 pages / 255 wrong bytes
    #     where "identical" gave 123 pages / 696.  The reference extractor keeps state
    #     (a persistent template bank and a grid lock), so skipping calls perturbs its
    #     trajectory.  A stateless extractor would make this knob accuracy-neutral.
    dedup: str = "off"                 # identical | similar | off
    similar_threshold: float = 6.0
    tear_policy: str = "split"         # split | discard | discount | off
    discount_factor: float = 0.05
    use_ladder: bool = True
    use_confidence_tear: bool = True
    use_temporal_tear: bool = True
    strict_adjacent: bool = True
    cell_threshold: float = 0.35
    max_bad_cells: int = 6
    flush_after: int = 6               # flush a page once this many other pages went by
    max_votes_per_page: int = 0        # 0 = unlimited; >0 caps work per page (live mode)
    early_stop_margin: float = 0.0     # >0 enables decisive-vote early stop
    min_page_obs: int = 1
    min_posterior: float = 0.0    # cells below this are reported UNKNOWN, not guessed
    base_continuity: str = "reject"   # off | reject | repair
    continuity_window: int = 0x8000   # 128 pages either side of the sweep's context
    continuity_resync: int = 4        # consecutive agreeing outliers that redefine context
    fill: int = 0x00
    progress_every: int = 0            # print a progress line every N frames (0 = never)


@dataclass
class PipelineStats:
    frames_seen: int = 0
    frames_extracted: int = 0
    frames_reused: int = 0
    frames_skipped_budget: int = 0
    frames_not_a_page: int = 0
    frames_base_outlier: int = 0
    frames_base_repaired: int = 0
    frames_torn: int = 0
    frames_torn_salvaged: int = 0
    frames_torn_discarded: int = 0
    pages_seen: int = 0
    tear_kinds: Dict[str, int] = field(default_factory=dict)
    seconds: float = 0.0

    @property
    def fps(self) -> float:
        return self.frames_seen / self.seconds if self.seconds > 0 else 0.0

    def as_dict(self) -> dict:
        d = dict(self.__dict__)
        d["fps"] = self.fps
        return d


class Pipeline:
    def __init__(self, extractor: Callable, config: Optional[PipelineConfig] = None):
        self.extract = extractor
        self.cfg = config or PipelineConfig()
        self.image = SparseImage(fill=self.cfg.fill)
        self.stats = PipelineStats()
        self.pages: "OrderedDict[int, PageAccumulator]" = OrderedDict()
        self._sig = FrameSignature(change_threshold=self.cfg.similar_threshold)
        self._cache: Optional[PageObservation] = None
        self._window: deque = deque(maxlen=3)      # (frame_index, frame, obs)
        self._page_order: List[int] = []
        self.tear_log: List[dict] = []
        self.frame_log: List[dict] = []
        # rolling record of how unreadable this capture normally is, so the
        # confidence detector can flag OUTLIERS rather than a fixed quality bar
        self._badcells: deque = deque(maxlen=90)
        # where the sweep currently is, used to reject fabricated page addresses
        self._recent_bases: deque = deque(maxlen=15)
        self._outlier_run: List[int] = []
        self.quarantined: List[dict] = []

    # -- main entry -------------------------------------------------------------------
    def run(self, frames: Iterable[Tuple[int, np.ndarray]]) -> "Pipeline":
        t0 = time.time()
        for idx, frame in frames:
            self._push(idx, frame)
        # drain the 3-frame window
        while self._window:
            self._drain_one()
        self._flush_all()
        self.stats.seconds = time.time() - t0
        return self

    # -- per frame --------------------------------------------------------------------
    def _push(self, idx: int, frame: np.ndarray) -> None:
        self.stats.frames_seen += 1
        obs = self._observe(idx, frame)
        self._window.append((idx, frame, obs))
        if len(self._window) == 3:
            self._drain_one()
        if self.cfg.progress_every and self.stats.frames_seen % self.cfg.progress_every == 0:
            print(f"  [{self.stats.frames_seen} frames, {len(self.image.pages)} pages, "
                  f"{self.stats.fps if self.stats.seconds else 0:.1f} fps]", flush=True)

    def _observe(self, idx: int, frame: np.ndarray) -> Optional[PageObservation]:
        cfg = self.cfg
        if cfg.dedup != "off":
            kind, _dist = self._sig.classify(frame)
            if kind == "identical" and self._cache is not None:
                self.stats.frames_reused += 1
                cached = PageObservation(**{**self._cache.__dict__})
                cached.frame_index = idx
                return cached
            if cfg.dedup == "similar" and kind == "same" and self._cache is not None:
                self.stats.frames_reused += 1
                cached = PageObservation(**{**self._cache.__dict__})
                cached.frame_index = idx
                return cached
        obs = normalize(self.extract(frame), frame_index=idx)
        self.stats.frames_extracted += 1
        self._cache = obs
        return obs

    def _drain_one(self) -> None:
        idx, frame, obs = self._window.popleft()
        prev = self._window_prev(idx)
        nxt = self._window[0][1] if self._window else None
        self._consume(idx, frame, obs, prev, nxt)

    def _window_prev(self, idx: int) -> Optional[np.ndarray]:
        return getattr(self, "_last_frame", None)

    def _consume(self, idx: int, frame: np.ndarray, obs: Optional[PageObservation],
                 prev: Optional[np.ndarray], nxt: Optional[np.ndarray]) -> None:
        cfg = self.cfg
        self._last_frame = frame
        if obs is None or not obs.ok or obs.base_address is None:
            self.stats.frames_not_a_page += 1
            self.frame_log.append({"frame": idx, "status": "not-a-page"})
            return

        bad_now = int((obs.confidence < cfg.cell_threshold).sum())
        baseline = median(self._badcells) if len(self._badcells) >= 12 else None
        verdict = tearing.TearVerdict()
        if cfg.tear_policy != "off":
            verdict = tearing.detect(
                obs, prev_frame=prev, cur_frame=frame, next_frame=nxt,
                use_ladder=cfg.use_ladder, use_confidence=cfg.use_confidence_tear,
                use_temporal=cfg.use_temporal_tear, strict_adjacent=cfg.strict_adjacent,
                cell_threshold=cfg.cell_threshold, max_bad_cells=cfg.max_bad_cells,
                conf_baseline=baseline)
        self._badcells.append(bad_now)
        obs.tear = None if not verdict.torn else verdict.kind

        if verdict.torn:
            self.stats.frames_torn += 1
            self.stats.tear_kinds[verdict.kind] = self.stats.tear_kinds.get(verdict.kind, 0) + 1
            self.tear_log.append({"frame": idx, "kind": verdict.kind,
                                  "detectors": verdict.detectors,
                                  "detail": verdict.detail})

        segments: List[Tuple[int, List[int]]]
        weight = 1.0
        if not verdict.torn:
            # the ladder's voted base outranks row 0's printed address: row 0 can be the
            # misread one
            base = verdict.base if verdict.base is not None else obs.base_address
            segments = verdict.segments or [(base, list(range(PAGE_ROWS)))]
        elif cfg.tear_policy == "split" and verdict.salvageable:
            segments = verdict.segments
            self.stats.frames_torn_salvaged += 1
        elif cfg.tear_policy == "discount":
            base = verdict.base if verdict.base is not None else obs.base_address
            segments = [(base, list(range(PAGE_ROWS)))]
            weight = cfg.discount_factor
        else:
            self.stats.frames_torn_discarded += 1
            self.frame_log.append({"frame": idx, "status": "torn-discarded",
                                   "kind": verdict.kind})
            return

        # continuity is checked per SEGMENT, not just the primary one: a page-mix frame
        # contributes a second base, and it was exactly those second bases that produced
        # the fabricated pages 0x40432000 / 0x43430000 in the H.264 measurement.
        kept = []
        for seg_base, rows in segments:
            ok_base, fixed = self._continuity(seg_base, idx)
            if not ok_base:
                self.stats.frames_base_outlier += 1
                self.tear_log.append({"frame": idx, "kind": "base-outlier",
                                      "detectors": ["continuity"],
                                      "detail": f"0x{seg_base:08X} is not where the "
                                                f"sweep is"})
                continue
            kept.append((fixed, rows))
        if not kept:
            self.frame_log.append({"frame": idx, "status": "base-outlier",
                                   "base": f"0x{segments[0][0]:08X}"})
            return
        segments = kept
        self._recent_bases.append(segments[0][0])
        for base, rows in segments:
            self._add_rows(base, obs, rows, weight)
        self.frame_log.append({
            "frame": idx, "status": "used",
            "base": f"0x{(verdict.base if verdict.base is not None else obs.base_address):08X}",
            "tear": verdict.kind if verdict.torn else "clean",
            "mean_conf": round(obs.mean_confidence(), 4),
        })
        self._maybe_flush(segments[0][0] if segments else obs.base_address)

    def _add_rows(self, base: int, obs: PageObservation, rows, weight: float) -> None:
        cfg = self.cfg
        acc = self.pages.get(base)
        if acc is None:
            acc = PageAccumulator(base_address=base, mode=cfg.vote_mode)
            self.pages[base] = acc
            self._page_order.append(base)
            self.stats.pages_seen += 1
        if cfg.max_votes_per_page and acc.n_obs >= cfg.max_votes_per_page:
            self.stats.frames_skipped_budget += 1
            return
        if cfg.early_stop_margin > 0 and acc.decisive(min_margin=cfg.early_stop_margin):
            self.stats.frames_skipped_budget += 1
            return
        if weight != 1.0:
            scaled = PageObservation(**{**obs.__dict__})
            scaled.confidence = (obs.confidence * weight).astype(np.float32)
            obs = scaled
        acc.add(obs, rows=rows)

    # -- sweep continuity -------------------------------------------------------------
    def _continuity(self, base: int, idx: int) -> Tuple[bool, int]:
        """Reject (or repair) a page address that the sweep cannot plausibly be at.

        This is the safeguard that matters most, and it exists because of a measured
        failure: on the H.264 medium clip the extractor misread the leading '8' of the
        address and the pipeline happily filed whole pages at 0x40432000, 0x43430000 and
        0x48432F00 -- addresses the sweep never visited.  Those pages are internally
        consistent, so every frame agreed, so the voted posterior was HIGH and the
        posterior gate did not remove a single one of them.  668 wrong bytes survived a
        0.99999 gate.

        The fix is information that only a *video* has: a sweep moves one page at a time,
        so the address of frame N is bounded by where the sweep was at frame N-1.  A
        fabricated address is one that jumps out of that neighbourhood.

        A deliberate jump (the operator re-dials the address) is handled by resync: once
        ``continuity_resync`` consecutive rejects agree with each other, they become the
        new context.
        """
        cfg = self.cfg
        if cfg.base_continuity == "off" or len(self._recent_bases) < 3:
            self._outlier_run.clear()
            return True, base
        ctx = int(sorted(self._recent_bases)[len(self._recent_bases) // 2])
        if abs(base - ctx) <= cfg.continuity_window:
            self._outlier_run.clear()
            return True, base
        if cfg.base_continuity == "repair":
            # keep the low 16 bits (which the sweep is actually changing) and take the
            # high half from the context
            cand = (ctx & ~0xFFFF) | (base & 0xFFFF)
            if abs(cand - ctx) <= cfg.continuity_window:
                self.stats.frames_base_repaired += 1
                self._outlier_run.clear()
                return True, cand
        self._outlier_run.append(base)
        if len(self._outlier_run) >= cfg.continuity_resync:
            run = self._outlier_run[-cfg.continuity_resync:]
            if max(run) - min(run) <= cfg.continuity_window:
                self._recent_bases.clear()
                self._recent_bases.extend(run)
                self._outlier_run.clear()
                return True, base
        return False, base

    # -- flushing ---------------------------------------------------------------------
    def _maybe_flush(self, current_base: int) -> None:
        keep = self.cfg.flush_after
        if len(self.pages) <= keep:
            return
        for base in list(self.pages.keys())[:-keep]:
            if base == current_base:
                continue
            self._flush(base)

    def _flush(self, base: int) -> None:
        acc = self.pages.pop(base, None)
        if acc is None:
            return
        if acc.n_obs < self.cfg.min_page_obs:
            return
        page = acc.result()
        if self.cfg.min_posterior > 0.0:
            # An uncertain byte must become a HOLE, never a guess: a hole costs another
            # sweep, a guess costs the credibility of the whole dump.
            page.known = page.known & (page.posterior >= self.cfg.min_posterior)
        self.image.add_page(page)

    def _flush_all(self) -> None:
        for base in list(self.pages.keys()):
            self._flush(base)
        self._quarantine_outliers()

    def _quarantine_outliers(self) -> None:
        """Post-hoc: a sweep is one contiguous excursion, so a page sitting megabytes away
        from every other page it was captured alongside is a misread address, not a
        discovery.

        The streaming continuity check cannot catch these during the first few frames --
        there is no context yet -- which is precisely when one of them got in during the
        H.264 measurement (0x43430000, from frame 2).  Quarantined pages are reported, not
        deleted, so nothing disappears silently.
        """
        if self.cfg.base_continuity == "off" or len(self.image.pages) < 5:
            return
        bases = sorted(self.image.pages)
        med = bases[len(bases) // 2]
        window = self.cfg.continuity_window * 4
        for b in bases:
            if abs(b - med) > window:
                data, known, post = self.image.pages.pop(b)
                self.quarantined.append({
                    "address": f"0x{b:08X}",
                    "known_bytes": int(known.sum()),
                    "reason": f"more than 0x{window:X} from the sweep median "
                              f"0x{med:08X}",
                })

    # -- reporting --------------------------------------------------------------------
    def report(self, expected: Optional[List[Tuple[int, int]]] = None) -> str:
        s = self.stats
        head = [
            "== throughput ==",
            f"frames seen      : {s.frames_seen}",
            f"frames extracted : {s.frames_extracted}",
            f"frames reused    : {s.frames_reused} (identical to previous)",
            f"frames budget-cut: {s.frames_skipped_budget}",
            f"not a dump page  : {s.frames_not_a_page}",
            f"base outliers    : {s.frames_base_outlier} (address not where the sweep is)",
            f"base repaired    : {s.frames_base_repaired}",
            f"elapsed          : {s.seconds:.2f} s",
            f"throughput       : {s.fps:.1f} frames/s",
            "",
            "== tearing ==",
            f"frames flagged   : {s.frames_torn}",
            f"  salvaged (split): {s.frames_torn_salvaged}",
            f"  discarded       : {s.frames_torn_discarded}",
            f"  by kind         : {dict(sorted(s.tear_kinds.items()))}",
            "",
            "== coverage ==",
        ]
        if self.quarantined:
            head[-1:-1] = [f"QUARANTINED pages: {len(self.quarantined)} "
                           f"(address implausible for this sweep; NOT in the output)"]
            head[-1:-1] = [f"  {q['address']}  {q['known_bytes']} bytes  {q['reason']}"
                           for q in self.quarantined]
        return "\n".join(head) + "\n" + coverage_report(self.image, expected)
