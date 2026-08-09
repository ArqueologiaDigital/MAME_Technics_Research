"""Tearing detection, and the synthetic tears used to measure it.

What a torn frame actually looks like here
------------------------------------------
The brief expected MAME to be incapable of producing torn frames.  **It is not.**  The
firmware repaints the viewer over several video frames, so a frame grabbed during a page
flip really does mix two pages -- measured on run ``cap2`` (260 clean-capture frames,
one page per burst): frames 0069 and 0190 show row addresses alternating between two
pages, e.g. ``1300 1510 1320 1530 1340 1550 1360 ...``.

Two things about those real tears matter, and neither is the textbook "top half / bottom
half" split:

1. The mix is **interleaved by row**, not a single split point.  The repaint touches odd
   and even rows in separate passes.
2. Many damaged cells are **half-drawn glyphs** whose decoded byte matches *neither*
   page.  On frame 0068 the row-address ladder is perfectly consistent and 15 data bytes
   are still wrong.  A detector that only checks the address ladder therefore misses real
   damage, which is why ``confidence`` below is not optional garnish.

So three independent detectors, deliberately cheap, each catching what the others miss:

``ladder``
    Row addresses must ascend by exactly 0x10.  Catches page mixing outright and can
    often say *where*.  Needs ``row_addresses`` from the extractor.
``confidence``
    A repaint-damaged glyph is not a confident glyph.  Catches intra-row damage that the
    ladder cannot see.  Needs nothing but the contract's required fields.
``temporal``
    Over a 3-frame window, a clean frame's rows all resemble the same neighbour; a torn
    frame's rows split into "looks like the previous frame" and "looks like the next
    one".  Pixel-only, so it works even with a minimal extractor.

A detector that flags clean frames is worse than none, so every one of these is measured
for false positives on known-clean frames, not just for detection rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np

from .contract import PAGE_ROWS, ROW_STRIDE, PageObservation

PAGE_STEP = 0x100  # one screenful; also the page-advance button's step


@dataclass
class TearVerdict:
    torn: bool = False
    kind: str = "clean"   # clean | page-mix | ladder-unusable | low-confidence | temporal
    detectors: List[str] = field(default_factory=list)
    base: Optional[int] = None
    # (page_base, [row indices]) -- an arbitrary row set, not a contiguous split, because
    # the tears this instrument actually produces are INTERLEAVED by row
    segments: List[Tuple[int, List[int]]] = field(default_factory=list)
    suspect_rows: List[int] = field(default_factory=list)
    detail: str = ""

    @property
    def salvageable(self) -> bool:
        return bool(self.segments)


# ----------------------------------------------------------------------------------
# 1. address ladder
# ----------------------------------------------------------------------------------

def ladder_check(row_addresses: Optional[Sequence[Optional[int]]],
                 strict_adjacent: bool = True, min_agree: int = 12,
                 min_second: int = 3) -> TearVerdict:
    """Each row states its own address, so each row can be filed independently.

    Row r of the page based at B prints ``B + 0x10*r``.  Invert that: every row votes for
    a page base of ``printed_address - 0x10*r``.  Now:

    * all 16 rows voting the same base  -> clean page.
    * one dominant base, a few dissenters -> the *address glyphs* were misread on those
      rows, not a tear.  Keep the whole frame under the voted base and let the per-cell
      confidences deal with the noisy rows.  This case matters enormously on real capture:
      on the H.264 medium-degradation clip a strict ascend-by-0x10 test rejected 32 of 60
      frames, all of them for a single misread hex digit in an address.
    * two bases, each with real support, separated by a whole number of pages -> a genuine
      page mix.  File each row under the base *it* names; rows naming neither are dropped.
      This handles interleaved tears, which a single-split model cannot express at all.

    ``strict_adjacent`` requires the two bases of a claimed page mix to be EXACTLY ONE
    page apart -- the false-positive brake, and a tight one on purpose.  The button steps
    one page at a time and the repaint takes ~112 ms against a ~190 ms page period, so a
    frame caught mid flip can only ever mix two CONSECUTIVE pages.  Accepting any whole
    multiple of 0x100 is what let a handful of misread address digits file 196 bytes at
    0x48402B00, three pages past where the sweep ever went, on the integrator's own
    555-frame run: 185 of that run's 201 wrong bytes were that one fabricated page.
    Requiring |delta| == 0x100 drops those rows instead.
    """
    if row_addresses is None:
        return TearVerdict(False, "clean", [], detail="no row addresses supplied")

    ra = list(row_addresses)
    votes: dict = {}
    for r, a in enumerate(ra):
        if a is None:
            continue
        base = (a - ROW_STRIDE * r) & 0xFFFFFFFF
        votes.setdefault(base, []).append(r)
    if not votes:
        return TearVerdict(True, "ladder-unusable", ["ladder"],
                           detail="no row address could be read")

    ranked = sorted(votes.items(), key=lambda kv: -len(kv[1]))
    base, rows = ranked[0]
    n1 = len(rows)
    second = ranked[1] if len(ranked) > 1 else None
    n2 = len(second[1]) if second else 0

    if n1 == PAGE_ROWS:
        return TearVerdict(False, "clean", [], base=base,
                           segments=[(base, list(range(PAGE_ROWS)))])

    page_mix = False
    if second is not None and n2 >= min_second:
        delta = (second[0] - base) & 0xFFFFFFFF
        delta = delta if delta < 0x80000000 else delta - 0x100000000
        page_mix = (abs(delta) == PAGE_STEP) if strict_adjacent else (delta != 0)

    if page_mix:
        segs = [(b, sorted(rs)) for b, rs in ranked[:2] if len(rs) >= min_second]
        dropped = sorted(set(range(PAGE_ROWS)) - {r for _, rs in segs for r in rs})
        return TearVerdict(True, "page-mix", ["ladder"], base=base, segments=segs,
                           suspect_rows=dropped,
                           detail=f"{n1} rows at {base:08X}, {n2} rows at "
                                  f"{second[0]:08X}; {len(dropped)} rows dropped")

    if n1 >= min_agree:
        suspect = sorted(set(range(PAGE_ROWS)) - set(rows))
        return TearVerdict(False, "clean", [], base=base,
                           segments=[(base, list(range(PAGE_ROWS)))],
                           suspect_rows=suspect,
                           detail=f"{len(suspect)} rows with misread addresses "
                                  f"(kept: dominant base has {n1}/16 votes)")

    return TearVerdict(True, "ladder-unusable", ["ladder"], base=base,
                       detail=f"no dominant base ({n1}/16 top, {n2} second)")


# ----------------------------------------------------------------------------------
# 2. confidence
# ----------------------------------------------------------------------------------

def confidence_check(conf: np.ndarray, cell_threshold: float = 0.35,
                     max_bad_cells: int = 6, baseline: Optional[float] = None,
                     baseline_factor: float = 2.5,
                     baseline_margin: float = 8.0) -> TearVerdict:
    """Flag a frame whose glyphs are too often unreadable to be a settled repaint.

    Calibrated against the measured distribution on run cap2: on *correct* cells the
    confidence median is 0.89 and only 1.2% fall below 0.35, while on *wrong* cells the
    median is 0.042 and 94% fall below 0.35.  ``max_bad_cells`` is what keeps a couple of
    genuinely hard glyphs from condemning a good frame.
    """
    bad = int((conf < cell_threshold).sum())
    limit = float(max_bad_cells)
    if baseline is not None:
        # RELATIVE, not absolute.  An absolute limit tuned on pixel-exact emulator frames
        # condemned every frame of the H.264 medium-degradation clip, and cost 5.2% false
        # positives even on verified-clean frames.  What matters is whether THIS frame is
        # anomalously unreadable compared with how this capture normally looks.
        limit = max(limit, baseline * baseline_factor + baseline_margin)
    if bad > limit:
        return TearVerdict(True, "low-confidence", ["confidence"],
                           detail=f"{bad} cells below {cell_threshold} (limit {limit:.1f})")
    return TearVerdict(False, "clean", [])


# ----------------------------------------------------------------------------------
# 3. temporal
# ----------------------------------------------------------------------------------

def row_bands(frame: np.ndarray, y0: int = 55, pitch: int = 9, n: int = PAGE_ROWS,
              height: int = 7) -> np.ndarray:
    """Mean luma of each text row band -- cheap per-row fingerprints."""
    f = frame.astype(np.float32).mean(axis=2)
    h = f.shape[0]
    out = np.zeros((n, f.shape[1]), np.float32)
    for r in range(n):
        y = y0 + pitch * r
        if y + height <= h:
            out[r] = f[y:y + height].mean(axis=0)
    return out


def temporal_check(prev: Optional[np.ndarray], cur: np.ndarray,
                   nxt: Optional[np.ndarray], ratio: float = 2.0,
                   min_change: float = 1.5) -> TearVerdict:
    """A torn frame's rows disagree about which neighbour they resemble.

    For each text row: d_prev = |row(cur) - row(prev)|, d_next = |row(cur) - row(next)|.
    A settled frame has every row on the same side (all still equal to the previous page,
    or all already equal to the next).  A frame caught mid-repaint has some rows matching
    the old content and others matching the new -- a mixed sign pattern.
    """
    if prev is None or nxt is None:
        return TearVerdict(False, "clean", [], detail="window incomplete")
    bp = row_bands(prev)
    bc = row_bands(cur)
    bn = row_bands(nxt)
    d_prev = np.abs(bc - bp).mean(axis=1)
    d_next = np.abs(bc - bn).mean(axis=1)
    changed = (d_prev + d_next) > min_change
    if changed.sum() < 2:
        return TearVerdict(False, "clean", [])
    like_prev = (d_next > ratio * np.maximum(d_prev, 1e-6)) & changed
    like_next = (d_prev > ratio * np.maximum(d_next, 1e-6)) & changed
    if like_prev.any() and like_next.any():
        rows_p = list(np.nonzero(like_prev)[0])
        rows_n = list(np.nonzero(like_next)[0])
        return TearVerdict(True, "temporal", ["temporal"],
                           detail=f"rows {rows_p} match previous, {rows_n} match next")
    return TearVerdict(False, "clean", [])


# ----------------------------------------------------------------------------------
# combined
# ----------------------------------------------------------------------------------

def detect(obs: PageObservation, prev_frame=None, cur_frame=None, next_frame=None,
           use_ladder: bool = True, use_confidence: bool = True,
           use_temporal: bool = True, strict_adjacent: bool = True,
           cell_threshold: float = 0.35, max_bad_cells: int = 6,
           conf_baseline: Optional[float] = None) -> TearVerdict:
    verdicts: List[TearVerdict] = []
    if use_ladder and obs.has_row_addresses:
        verdicts.append(ladder_check(obs.row_addresses, strict_adjacent))
    if use_confidence:
        verdicts.append(confidence_check(obs.confidence, cell_threshold, max_bad_cells,
                                         baseline=conf_baseline))
    if use_temporal and cur_frame is not None:
        verdicts.append(temporal_check(prev_frame, cur_frame, next_frame))

    firing = [v for v in verdicts if v.torn]
    if not firing:
        clean = TearVerdict(False, "clean", [])
        for v in verdicts:
            if v.segments:
                clean.segments = v.segments
                clean.base = v.base
                clean.suspect_rows = v.suspect_rows
                clean.detail = v.detail
        return clean

    # prefer a verdict that can be salvaged, then the most specific
    firing.sort(key=lambda v: (0 if v.segments else 1, v.kind))
    best = firing[0]
    return TearVerdict(True, best.kind,
                       sorted({d for v in firing for d in v.detectors}),
                       best.base, best.segments, best.suspect_rows,
                       " | ".join(v.detail for v in firing if v.detail))


# ----------------------------------------------------------------------------------
# synthetic tears -- for measuring the detectors
# ----------------------------------------------------------------------------------

def splice_text_row(a: np.ndarray, b: np.ndarray, k: int, y0: int = 55,
                    pitch: int = 9) -> np.ndarray:
    """Text-row-aligned splice: rows [0,k) from page A, rows [k,16) from page B."""
    out = a.copy()
    ysplit = y0 + pitch * k - 1
    out[ysplit:] = b[ysplit:]
    return out


def splice_scanline(a: np.ndarray, b: np.ndarray, y: int) -> np.ndarray:
    """Raw scanline tear at an arbitrary y -- the classic video tear, which cuts a text
    row in half rather than between rows."""
    out = a.copy()
    out[y:] = b[y:]
    return out


def splice_interlace(a: np.ndarray, b: np.ndarray, parity: int = 0) -> np.ndarray:
    """Interlace-style splice: alternating scanlines from two different pages."""
    out = a.copy()
    out[parity::2] = b[parity::2]
    return out


def splice_interleaved_rows(a: np.ndarray, b: np.ndarray, parity: int = 1,
                            y0: int = 55, pitch: int = 9,
                            height: int = 7) -> np.ndarray:
    """Alternating *text rows* from two pages -- reproduces the tear MAME actually emits
    (measured on cap2 frame 0069)."""
    out = a.copy()
    for r in range(parity, PAGE_ROWS, 2):
        y = y0 + pitch * r
        out[y:y + height] = b[y:y + height]
    return out
