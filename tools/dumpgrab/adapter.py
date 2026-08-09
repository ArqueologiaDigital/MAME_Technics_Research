"""Adapter: the kn7000dump single-image extractor -> the kn7000videograb frame contract.

kn7000videograb (the voter/assembler) never imports the extractor directly; it is handed
a callable ``extract(rgb_uint8_HxWx3) -> result``.  kn7000dump.PageExtractor already
produces everything that contract asks for, under slightly different names
(``conf`` instead of ``confidence``), so this module is the whole of the glue.

Two things happen here that are NOT cosmetic:

* GATE ON THE GRID, NOT ON THE CONTENT.  A frame decoded on a MISPLACED grid produces
  CONFIDENT nonsense (measured: 26% of the bytes above confidence 0.9 were wrong on a
  badly framed corpus), so such a frame must not reach the voter at all.  The test is the
  frame's own printed addresses: every row votes for a page base of
  ``printed_address - 0x10*row``, and a frame is trusted only if at least
  ``MIN_LADDER_AGREE`` rows agree on one base.  A misplaced grid cannot fake that; a page
  flip mid-repaint fails it in a specific, recoverable way (two bases one page apart),
  which is why the *rows* are handed on untouched for the pipeline's tear detector to
  split rather than being suppressed here.

* ZERO MEANS ABSENT, AND ABSTENTION IS PER CELL.  Cells the extractor could not read
  arrive with confidence 0 and the voter treats them as "no vote", never as the byte
  value 0.  Deliberately NOT used here: kn7000dump's own ``PageResult.ok``, which
  additionally requires *every* one of the 256 cells to have nonzero confidence.  That is
  too strict for a voter — measured on a 555-frame sweep, it refused 192 frames and lost
  page 0x48400000 entirely (every frame of that page carries a handful of unreadable
  cells), where letting those cells abstain recovers the rest of the page and leaves a few
  one-byte holes at worst.  It IS the right test for "is this frame settled", and it is
  used that way below and in predict/degrade_shipped.py.

Usage (from the pipeline CLI):
    --extractor adapter:ShippedExtractor
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kn7000dump import PageExtractor  # noqa: E402

#: how many of the 16 rows must agree on one page base before the frame is trusted at all.
#: 12 is the same floor the pipeline's ladder detector uses to call something a page rather
#: than noise: it tolerates a few misread address digits and a mid-repaint page flip, and
#: it is far out of reach of a grid that is simply in the wrong place.
MIN_LADDER_AGREE = 12

#: A frame that is NOT fully settled -- rows from two pages, or more than a handful of
#: unreadable cells -- still carries real information, but its glyphs may be half drawn,
#: and a half-drawn glyph is read confidently as a DIFFERENT glyph ('8' mid-repaint reads
#: as 'B').  Those errors are systematic across the transition frames of one page, so they
#: agree with each other and can out-vote the settled frames.  Such a frame therefore
#: votes at this fraction of its stated confidence: enough to fill a hole no settled frame
#: covers, not enough to overturn settled frames that disagree with it.
#: (override for experiments with DUMPGRAB_UNSETTLED_DISCOUNT=... in the environment;
#: 0.5 is the measured choice -- see README)
UNSETTLED_DISCOUNT = float(os.environ.get("DUMPGRAB_UNSETTLED_DISCOUNT", "0.5"))
#: cells below this count as unreadable when deciding whether a frame is settled
#: (same threshold the pipeline's confidence tear detector uses)
CELL_THRESHOLD = 0.35
MAX_BAD_CELLS = 6


def _ladder_agreement(row_addresses):
    """How well the frame's own printed addresses hang together.

    Returns ``(n_usable, n_top)``.  ``n_top`` is the largest set of rows agreeing on one
    page base.  ``n_usable`` adds the second-largest set when the two bases are a whole
    number of 0x100 pages apart, because that is not disagreement -- it is a frame caught
    mid page-flip, and the pipeline files each row under the base it names.
    """
    votes = {}
    for r, a in enumerate(row_addresses or []):
        if a is None:
            continue
        votes.setdefault((int(a) - 0x10 * r) & 0xFFFFFFFF, []).append(r)
    if not votes:
        return 0, 0
    ranked = sorted(votes.items(), key=lambda kv: -len(kv[1]))
    n1 = len(ranked[0][1])
    if len(ranked) > 1:
        n2 = len(ranked[1][1])
        delta = (ranked[1][0] - ranked[0][0]) & 0xFFFFFFFF
        if n2 >= 3 and delta % 0x100 == 0:
            return n1 + n2, n1
    return n1, n1


class ShippedExtractor:
    """Callable wrapper around kn7000dump.PageExtractor with the voter's contract."""

    def __init__(self, atlas_path: str = None, min_ladder_agree: int = MIN_LADDER_AGREE,
                 unsettled_discount: float = UNSETTLED_DISCOUNT,
                 use_color: bool = True, read_legend: bool = True):
        self.ex = PageExtractor(atlas_path=atlas_path, use_color=use_color,
                                read_legend=read_legend)
        self.min_ladder_agree = min_ladder_agree
        self.unsettled_discount = float(unsettled_discount)

    def __call__(self, image):
        return self.extract(image)

    def extract(self, image) -> dict:
        rgb = np.asarray(image)
        try:
            res = self.ex.extract(rgb)
        except Exception as exc:                       # never kill a long sweep
            return {
                "base_address": None,
                "bytes": np.zeros((16, 16), np.uint8),
                "confidence": np.zeros((16, 16), np.float32),
                "ok": False,
                "reason": "extractor raised %s: %s" % (type(exc).__name__, exc),
            }

        conf = np.asarray(res.conf, dtype=np.float32).reshape(16, 16)
        data = np.frombuffer(bytes(res.data), dtype=np.uint8).reshape(16, 16)
        n_agree, n_top = _ladder_agreement(res.row_addresses)
        good = res.base_address is not None and n_agree >= self.min_ladder_agree
        settled = (bool(res.row_addr_ok) and all(res.row_addr_ok)
                   and int((conf < CELL_THRESHOLD).sum()) <= MAX_BAD_CELLS)
        if not good:
            conf = np.zeros_like(conf)                 # a bad grid votes for nothing
        elif not settled:
            conf = conf * self.unsettled_discount      # mid-repaint: nudge, never decide

        # per-row address confidence = the weakest of that row's eight address digits,
        # halved when the row does not sit on the ladder.
        addr_conf = np.asarray(res.addr_conf, dtype=np.float32).reshape(16, 8)
        rconf = addr_conf.min(axis=1)
        rconf = np.where(np.asarray(res.row_addr_ok, dtype=bool), rconf, rconf * 0.5)

        reason = ""
        if not good:
            reason = ("row-address self-check failed (only %d/16 rows agree on a page "
                      "base, %d counting an adjacent-page split)" % (n_top, n_agree))
        elif not settled:
            reason = "unsettled repaint: votes at %.2f weight" % self.unsettled_discount
        if res.flags:
            reason = (reason + " " + " ".join(res.flags)).strip()

        return {
            "base_address": res.base_address,
            "bytes": data,
            "confidence": conf,
            "row_addresses": list(res.row_addresses),
            "row_addr_confidence": rconf,
            "ok": bool(good),
            "reason": reason,
            # extras the voter ignores but the single-image mode reports
            "_result": res,
        }


#: module-level default instance, so ``--extractor adapter:extract`` also works
_DEFAULT = None


def extract(image):
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = ShippedExtractor()
    return _DEFAULT.extract(image)
