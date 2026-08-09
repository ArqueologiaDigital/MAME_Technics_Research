"""Contract between the single-frame extractor (package c2) and the video pipeline (c3).

c3 never imports c2 directly.  It is handed a *callable* with this signature::

    extract(image: np.ndarray) -> result

``image``
    ``uint8`` array of shape ``(H, W, 3)``, channel order **RGB**, one whole captured
    video frame (or one whole still).  The extractor is responsible for locating the
    debug screen inside the frame -- c3 does no cropping, deskewing or colour work.

``result``
    Either a ``dict`` or any object carrying the attributes below.  c3 normalises both,
    so c2 may pick whichever it prefers.

    REQUIRED
      ``base_address``  : int | None -- CPU address shown on the FIRST row, or None if
                          the frame could not be read at all.
      ``bytes``         : anything accepted by ``np.asarray(...)`` with shape (16, 16),
                          dtype coercible to uint8.  Value at [row][col].
      ``confidence``    : shape (16, 16) float in [0, 1].  0 = "I am guessing",
                          1 = "certain".  Used as the voting weight, so it must be
                          comparable *across frames*; a hard 0/1 flag works but wastes
                          most of the benefit.

    OPTIONAL -- supply these and c3 gets strictly better
      ``row_addresses`` : list of 16 ``int | None`` -- the address printed on each row.
                          This is what makes the *strong* tearing detector possible
                          (rows of a clean page ascend by exactly 0x10).  Without it c3
                          falls back to a weaker temporal detector, and a torn frame can
                          only be dropped, never split-and-salvaged.
      ``row_addr_confidence`` : 16 floats in [0, 1].
      ``ok``            : bool -- False means "this frame is not a dump screen".
                          Absent is treated as ``base_address is not None``.
      ``reason``        : str -- free-form diagnostic, carried into the report.

Conventions that matter for correctness
---------------------------------------
* A cell the extractor could not read at all should be reported with
  ``confidence == 0``.  c3 treats zero-confidence cells as *absent*, not as the value 0.
  Never invent a byte with nonzero confidence.
* ``base_address`` is the address of ``bytes[0][0]``.  Row r, column c holds the byte at
  ``base_address + 16*r + c``.
* Addresses are full 32-bit MN10300 CPU addresses (program flash 0x48400000.., table
  flash 0x48000000..).  c3 keeps them as CPU addresses end to end and only converts to
  file offsets when an oracle is supplied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence

import numpy as np

PAGE_ROWS = 16
PAGE_COLS = 16
PAGE_SIZE = PAGE_ROWS * PAGE_COLS
ROW_STRIDE = 0x10


@dataclass
class PageObservation:
    """One frame's worth of extracted page, normalised."""

    base_address: Optional[int]
    data: np.ndarray  # (16,16) uint8
    confidence: np.ndarray  # (16,16) float32 in [0,1]
    row_addresses: Optional[list] = None  # 16 x (int|None), or None if not provided
    row_addr_confidence: Optional[np.ndarray] = None  # (16,) float32
    ok: bool = True
    reason: str = ""
    # filled in by the pipeline, not the extractor
    frame_index: int = -1
    source: str = ""
    tear: Optional[str] = None  # None = clean; otherwise a short tag

    @property
    def has_row_addresses(self) -> bool:
        return self.row_addresses is not None

    def mean_confidence(self) -> float:
        return float(self.confidence.mean()) if self.confidence.size else 0.0


def _get(obj: Any, name: str, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def normalize(result: Any, frame_index: int = -1, source: str = "") -> PageObservation:
    """Accept a dict or an object from any extractor and return a PageObservation.

    Raises ValueError only for shapes that cannot possibly be a page; a *failed* read
    should come back as ``ok=False`` / ``base_address=None``, not as an exception.
    """
    if result is None:
        return PageObservation(
            base_address=None,
            data=np.zeros((PAGE_ROWS, PAGE_COLS), np.uint8),
            confidence=np.zeros((PAGE_ROWS, PAGE_COLS), np.float32),
            ok=False,
            reason="extractor returned None",
            frame_index=frame_index,
            source=source,
        )

    base = _get(result, "base_address", None)
    if base is not None:
        base = int(base) & 0xFFFFFFFF

    raw = _get(result, "bytes", None)
    if raw is None:
        raw = _get(result, "data", None)
    if raw is None:
        data = np.zeros((PAGE_ROWS, PAGE_COLS), np.uint8)
    else:
        data = np.asarray(raw)
        if data.shape != (PAGE_ROWS, PAGE_COLS):
            data = data.reshape(PAGE_ROWS, PAGE_COLS)
        data = data.astype(np.uint8, copy=False)

    conf_raw = _get(result, "confidence", None)
    if conf_raw is None:
        # An extractor that reports no confidence is taken at its word, uniformly.
        conf = np.ones((PAGE_ROWS, PAGE_COLS), np.float32)
    else:
        conf = np.asarray(conf_raw, dtype=np.float32).reshape(PAGE_ROWS, PAGE_COLS)
        conf = np.clip(conf, 0.0, 1.0)

    rows = _get(result, "row_addresses", None)
    if rows is not None:
        rows = [None if r is None else (int(r) & 0xFFFFFFFF) for r in rows]
        if len(rows) != PAGE_ROWS:
            rows = (rows + [None] * PAGE_ROWS)[:PAGE_ROWS]

    rconf = _get(result, "row_addr_confidence", None)
    if rconf is not None:
        rconf = np.clip(np.asarray(rconf, dtype=np.float32).reshape(PAGE_ROWS), 0.0, 1.0)

    ok = _get(result, "ok", None)
    if ok is None:
        ok = base is not None

    return PageObservation(
        base_address=base,
        data=data,
        confidence=conf,
        row_addresses=rows,
        row_addr_confidence=rconf,
        ok=bool(ok),
        reason=str(_get(result, "reason", "") or ""),
        frame_index=frame_index,
        source=source,
    )


ExtractorFn = Callable[[np.ndarray], Any]
