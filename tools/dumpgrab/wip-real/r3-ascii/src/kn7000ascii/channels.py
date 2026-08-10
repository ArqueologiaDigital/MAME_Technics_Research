"""The three evidence channels, run over a `Page`.

Neighbour bleed is not a nuisance here, it is most of the signal budget: at the
measured smear a glyph's ink reaches well into the cells either side, so a
template matcher that renders its candidate on a blank background is comparing
against an image that does not exist.  Both glyph channels therefore run a
MEAN-FIELD loop: every cell's neighbours are rendered as the posterior-weighted
average of their own candidate bitmaps, which starts at the uniform mean and
sharpens as the passes go.  Cells whose content is fixed by the format (the
blanks, the two '-' separators, the address ladder) are pinned from the start.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np

from .geometry_ascii import ROW
from .page import Page, HEXC, BLANK, _softmax, _logsumexp, NEG


class GlyphChannel:
    """Common mean-field template matcher."""

    def __init__(self, page: Page, cells, templates, T=0.02, passes=3):
        self.p = page
        self.cells = cells
        self.T = T
        self.passes = passes
        self.templates = np.asarray(templates, dtype=np.float64)
        self.mean_tmpl = self.templates.mean(axis=0)

    def run(self, pinned: Dict[Tuple[int, int], np.ndarray]):
        est = dict(pinned)
        for (r, i) in self.cells:
            est.setdefault((r, i), self.mean_tmpl)
        post = {}
        raw = {}
        for p in range(self.passes):
            newpost = {}
            for (r, i) in self.cells:
                s = self.p.score_cell(r, i, self.templates, self.p.ctx_of(est, r, i))
                if s is None:
                    continue
                raw[(r, i)] = s
                newpost[(r, i)] = _softmax(s, self.T)
            post = newpost
            for (r, i), pr in post.items():
                est[(r, i)] = np.tensordot(pr, self.templates, axes=(0, 0))
        return post, raw, est


def hex_cells():
    return [(r, c) for r in range(16) for k in range(16) for c in ROW.byte_idx[k]]


def ascii_cells():
    return [(r, ROW.ascii_idx[k]) for r in range(16) for k in range(16)]


def hex_channel(page: Page, base: Optional[int], T=0.02, passes=3):
    tm = np.stack([page.font.hexmap[c] for c in HEXC])
    pinned = page.address_context(base) if base is not None else page.static_context()
    ch = GlyphChannel(page, hex_cells(), tm, T=T, passes=passes)
    return ch.run(pinned)


def ascii_channel(page: Page, base: Optional[int], T=0.02, passes=3):
    tm = page.font.proto.astype(np.float64)
    pinned = page.address_context(base) if base is not None else page.static_context()
    ch = GlyphChannel(page, ascii_cells(), tm, T=T, passes=passes)
    return ch.run(pinned)


# --------------------------------------------------------------------------- #
def hex_byte_logpost(post) -> np.ndarray:
    out = np.zeros((256, 256))
    for r in range(16):
        for k, (hi, lo) in enumerate(ROW.byte_idx):
            ph, pl = post.get((r, hi)), post.get((r, lo))
            if ph is None or pl is None:
                continue
            lp = (np.log(np.maximum(ph, 1e-12))[:, None]
                  + np.log(np.maximum(pl, 1e-12))[None, :]).ravel()
            out[r * 16 + k] = lp - _logsumexp(lp)
    return out


def ascii_byte_logpost(font, post) -> np.ndarray:
    """The many-to-one penalty lives here: a class of size m divides its
    posterior mass by m before it is handed to the fusion."""
    sizes = font.class_size()
    out = np.zeros((256, 256))
    for r in range(16):
        for j in range(16):
            pr = post.get((r, ROW.ascii_idx[j]))
            if pr is None:
                continue
            lp = np.full(256, -1e9)
            for ci, members in enumerate(font.members):
                v = np.log(max(float(pr[ci]), 1e-12) / sizes[ci])
                for b in members:
                    lp[b] = v
            out[r * 16 + j] = lp - _logsumexp(lp)
    return out


def ascii_nibble_marginal(font, post) -> np.ndarray:
    """(256, 16) posterior over the HIGH nibble implied by the ASCII pane.
    This is what the channel is actually good for -- see the class table."""
    out = np.zeros((256, 16))
    sizes = font.class_size()
    for r in range(16):
        for j in range(16):
            pr = post.get((r, ROW.ascii_idx[j]))
            if pr is None:
                out[r * 16 + j] = 1.0 / 16
                continue
            m = np.zeros(16)
            for ci, members in enumerate(font.members):
                w = float(pr[ci]) / sizes[ci]
                for b in members:
                    m[b >> 4] += w
            s = m.sum()
            out[r * 16 + j] = m / s if s > 0 else 1.0 / 16
    return out
