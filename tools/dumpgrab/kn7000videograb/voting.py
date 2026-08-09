"""Cross-frame voting: the reason video beats stills.

The same 256-byte page is shown for many consecutive frames.  Each frame is an
*independent* noisy measurement of the same 256 bytes, so the per-cell error rate falls
roughly geometrically with the number of frames -- provided the errors are independent,
which for analog capture noise they largely are, and provided we combine them with the
extractor's own confidence rather than a flat majority.

Two combiners are implemented and both are measured:

``bayes`` (default)
    Treat the extractor's confidence ``c`` as P(the reported value is the true one).
    Then for a candidate true value ``t``::

        P(observed v | t) = c            if v == t
                          = (1 - c)/255  otherwise

    Accumulate log-likelihood over frames and take the argmax.  This is the right thing:
    a 0.55-confidence vote nudges, a 0.999-confidence vote decides, and three agreeing
    weak votes beat one strong wrong one -- which flat majority cannot express.

``weighted``
    Plain confidence-weighted majority (sum of confidences per candidate value).
    Kept because it is what most people mean by "weighted majority", and because it is a
    fair baseline to measure ``bayes`` against.

Zero-confidence cells are *abstentions*: they add nothing and never create a value.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from .contract import PAGE_COLS, PAGE_ROWS, PAGE_SIZE, PageObservation

# clamp so log() never explodes and so a "certain" extractor cannot become unfalsifiable
_C_MIN = 1.0 / 256.0
_C_MAX = 1.0 - 1e-6


@dataclass
class PageAccumulator:
    """Log-likelihood (or weight) accumulator for one 256-byte page."""

    base_address: int
    mode: str = "bayes"
    # (16,16,256) is 64 K floats per page.  Pages are flushed as soon as the sweep
    # leaves them, so only a handful are ever live at once.
    acc: np.ndarray = field(default=None, repr=False)
    n_obs: int = 0
    n_cell_votes: np.ndarray = field(default=None, repr=False)
    frame_indices: List[int] = field(default_factory=list)

    def __post_init__(self):
        if self.acc is None:
            self.acc = np.zeros((PAGE_ROWS, PAGE_COLS, 256), np.float64)
        if self.n_cell_votes is None:
            self.n_cell_votes = np.zeros((PAGE_ROWS, PAGE_COLS), np.int32)

    def add(self, obs: PageObservation, rows: Optional[Iterable[int]] = None) -> None:
        """Fold one observation in.  ``rows`` restricts to a subset (used when a torn
        frame is split and only part of it belongs to this page)."""
        rows = list(range(PAGE_ROWS)) if rows is None else list(rows)
        if not rows:
            return
        r_idx = np.asarray(rows, dtype=np.intp)
        vals = obs.data[r_idx].astype(np.intp)
        conf = np.clip(obs.confidence[r_idx].astype(np.float64), 0.0, _C_MAX)

        voted = conf > 0.0
        if not voted.any():
            self.n_obs += 1
            self.frame_indices.append(obs.frame_index)
            return

        c = np.clip(conf, _C_MIN, _C_MAX)
        if self.mode == "bayes":
            # baseline for every candidate: log((1-c)/255); then bump the observed value
            base = np.log((1.0 - c) / 255.0)
            bump = np.log(c) - base
            sub = self.acc[r_idx]
            sub += np.where(voted, base, 0.0)[:, :, None]
            rr, cc = np.nonzero(voted)
            sub[rr, cc, vals[rr, cc]] += bump[rr, cc]
            self.acc[r_idx] = sub
        else:  # weighted majority
            sub = self.acc[r_idx]
            rr, cc = np.nonzero(voted)
            sub[rr, cc, vals[rr, cc]] += c[rr, cc]
            self.acc[r_idx] = sub

        self.n_cell_votes[r_idx] += voted.astype(np.int32)
        self.n_obs += 1
        self.frame_indices.append(obs.frame_index)

    def result(self) -> "VotedPage":
        acc = self.acc
        order = np.argsort(acc, axis=2)
        best = order[:, :, -1].astype(np.uint8)
        second = order[:, :, -2]
        rows = np.arange(PAGE_ROWS)[:, None]
        cols = np.arange(PAGE_COLS)[None, :]
        top = acc[rows, cols, best.astype(np.intp)]
        nxt = acc[rows, cols, second]
        margin = top - nxt

        if self.mode == "bayes":
            # posterior of the winner under a uniform prior; margin is in log units
            m = acc - acc.max(axis=2, keepdims=True)
            p = np.exp(m)
            p /= p.sum(axis=2, keepdims=True)
            posterior = p.max(axis=2)
        else:
            tot = acc.sum(axis=2)
            posterior = np.divide(top, tot, out=np.zeros_like(top), where=tot > 0)

        known = self.n_cell_votes > 0
        best = np.where(known, best, 0).astype(np.uint8)
        posterior = np.where(known, posterior, 0.0)
        return VotedPage(
            base_address=self.base_address,
            data=best,
            known=known,
            posterior=posterior.astype(np.float32),
            margin=margin.astype(np.float32),
            n_obs=self.n_obs,
            n_cell_votes=self.n_cell_votes.copy(),
            frame_indices=list(self.frame_indices),
        )

    def decisive(self, min_obs: int = 3, min_margin: float = 12.0) -> bool:
        """True when every cell's winner is far enough ahead that more frames cannot
        realistically change it.  Used for early-stop under a live-throughput budget.
        ``min_margin`` is in log-likelihood units for ``bayes`` (12 nats ~ 1e-5 odds)."""
        if self.n_obs < min_obs:
            return False
        if (self.n_cell_votes == 0).any():
            return False
        part = np.partition(self.acc, -2, axis=2)
        return bool((part[:, :, -1] - part[:, :, -2] >= min_margin).all())


@dataclass
class VotedPage:
    base_address: int
    data: np.ndarray  # (16,16) uint8
    known: np.ndarray  # (16,16) bool
    posterior: np.ndarray  # (16,16) float32
    margin: np.ndarray  # (16,16) float32
    n_obs: int
    n_cell_votes: np.ndarray
    frame_indices: List[int] = field(default_factory=list)

    def flat(self) -> Tuple[np.ndarray, np.ndarray]:
        return self.data.reshape(-1), self.known.reshape(-1)


# --------------------------------------------------------------------------------------
# cheap frame signatures -- the "should I even run the extractor?" gate
# --------------------------------------------------------------------------------------

class FrameSignature:
    """Cheap page-change detector.

    Two levels, because they answer different questions:

    * ``digest``  -- md5 of the raw frame bytes.  Bit-identical frames (the emulator, and
      a perfectly stable digital capture) carry *zero* extra information, so the cached
      extraction is reused verbatim.  This is a pure speed win with no accuracy cost.
    * ``thumb``   -- a 32x24 grayscale thumbnail of the region of interest.  Mean absolute
      difference against the previous frame's thumbnail says "same page, different noise"
      (re-extract: a genuinely new vote) versus "different page" (flush and start a new
      accumulator).

    The ROI defaults to the whole frame; pass ``roi`` (x0,y0,x1,y1) to hash only the
    address column, which is the cheapest reliable page-change signal.
    """

    def __init__(self, roi: Optional[Tuple[int, int, int, int]] = None,
                 change_threshold: float = 6.0, thumb: Tuple[int, int] = (32, 24)):
        self.roi = roi
        self.change_threshold = change_threshold
        self.tw, self.th = thumb
        self.prev_digest: Optional[str] = None
        self.prev_thumb: Optional[np.ndarray] = None

    def _crop(self, frame: np.ndarray) -> np.ndarray:
        if self.roi is None:
            return frame
        x0, y0, x1, y1 = self.roi
        return frame[y0:y1, x0:x1]

    def compute(self, frame: np.ndarray) -> Tuple[str, np.ndarray]:
        sub = self._crop(frame)
        digest = hashlib.md5(np.ascontiguousarray(sub)).hexdigest()
        g = sub.astype(np.float32).mean(axis=2)
        h, w = g.shape
        ys = (np.linspace(0, h, self.th + 1)).astype(int)
        xs = (np.linspace(0, w, self.tw + 1)).astype(int)
        # box-average downsample without scipy
        rows = np.add.reduceat(g, ys[:-1], axis=0) / np.maximum(np.diff(ys), 1)[:, None]
        thumb = np.add.reduceat(rows, xs[:-1], axis=1) / np.maximum(np.diff(xs), 1)[None, :]
        return digest, thumb.astype(np.float32)

    def classify(self, frame: np.ndarray) -> Tuple[str, float]:
        """Return ('identical' | 'same' | 'changed', distance)."""
        digest, thumb = self.compute(frame)
        if self.prev_digest is None:
            self.prev_digest, self.prev_thumb = digest, thumb
            return "changed", float("inf")
        if digest == self.prev_digest:
            return "identical", 0.0
        d = float(np.abs(thumb - self.prev_thumb).mean())
        self.prev_digest, self.prev_thumb = digest, thumb
        return ("changed" if d >= self.change_threshold else "same"), d
