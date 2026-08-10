"""Reading the characters, and knowing when not to believe them.

Two things happen here.  The first is ordinary template matching: 16 classes,
one per hex digit, matched by normalised cross-correlation.  The second is the
part that makes the result trustworthy, and it is worth stating plainly because
it is the difference between this and an OCR toy.

**The templates are trained on the operator's own capture chain, live.**  A
glyph atlas cut from the emulator's 640x240 framebuffer does not transfer: on
the real composite grabber frames it decodes 31 % of a page whose answer we
know, and on the phone photos it decodes noise.  That is not a tuning problem.
The capture chain applies a point spread that is specific to the lens, the
distance, the focus and the video path, and a template matched in the sharp
domain is simply the wrong filter for a blurred observation.  The fix is to
learn the templates *through* the same blur, from the screen itself.

**The screen labels its own training data.**  Row r of a page shows the address
base + 0x10*r, so on any page, of any machine, with no ROM dump to compare
against, the second-to-last address digit runs 0,1,2,...,F down the sixteen
rows and the last one never changes.  That is one free, correctly-labelled
sample of every one of the sixteen classes in every single frame -- which is
what makes this usable on Felipe's instrument, whose PROGRAM build 893 flash
exists nowhere else and has no oracle at all.  Thirty frames a second of that
converges quickly, and it re-converges by itself when the focus changes.

**And the same ladder is the check.**  Before any byte is believed, the sixteen
row addresses must ascend by exactly 0x10.  A registration that has slipped by
one character, a frame smeared by hand shake, a half-drawn repaint: all of them
break that arithmetic, and a frame that fails it contributes nothing.  The
check costs nothing, cannot be satisfied by accident, and is independent of the
pixels the templates were trained on.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import geom as G

HEXD = "0123456789ABCDEF"
GH, GW = 18, 12                    # patch size the templates live at

# How far outside its own cell a patch is cut, in cells.  Measured, and the
# asymmetry is not arbitrary: the font is 5 pixels wide on a 6-pixel pitch, so
# ANY horizontal over-cut drags in the neighbouring glyph and the template
# becomes a template of a digit pair.  Vertically the row gap is wider and a
# little over-cut helps, by catching the ink the capture blur has pushed out of
# the cell.  On the simulator, (0.20, 0.10) gave 13.2 of 16 rows and 217 of 256
# bytes committed; (0.00, 0.10) gave 15.0 rows, 240 bytes, and raised the worst
# template separation from 0.118 to 0.134.
OVER_X, OVER_Y = 0.00, 0.10


# --------------------------------------------------------------------------- #
def znorm_rows(X: np.ndarray) -> np.ndarray:
    X = X.astype(np.float32)
    X = X - X.mean(axis=1, keepdims=True)
    return X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-6)


class GlyphBank:
    """Sixteen running-average templates, trained online from the address ladder.

    Kept as a plain sum/count so that training is incremental and order does not
    matter, and so a session can be resumed with the templates it had learned.
    """

    def __init__(self, gh: int = GH, gw: int = GW, min_samples: int = 8):
        self.gh, self.gw = gh, gw
        self.min_samples = min_samples
        self.sum = np.zeros((16, gh, gw), np.float64)
        self.n = np.zeros(16, np.int64)
        self._T: Optional[np.ndarray] = None
        self._cent: Optional[np.ndarray] = None

    # -- training ---------------------------------------------------------- #
    def add(self, labels: Sequence[int], patches: np.ndarray, decay: float = 0.0) -> None:
        if len(labels) == 0:
            return
        X = znorm_rows(patches.reshape(len(patches), -1)).reshape(-1, self.gh, self.gw)
        if decay > 0.0:
            # Forget slowly, so the templates follow a focus or distance change
            # instead of averaging the old blur with the new one for ever.
            self.sum *= (1.0 - decay)
            self.n = np.maximum((self.n * (1.0 - decay)).astype(np.int64), 0)
        for lab, p in zip(labels, X):
            self.sum[lab] += p
            self.n[lab] += 1
        self._T = None
        self._cent = None

    @property
    def ready(self) -> bool:
        return bool((self.n >= self.min_samples).all())

    @property
    def coverage(self) -> int:
        return int((self.n >= self.min_samples).sum())

    # -- use ---------------------------------------------------------------- #
    @property
    def templates(self) -> np.ndarray:
        if self._T is None:
            m = self.sum / np.maximum(self.n, 1)[:, None, None]
            self._T = znorm_rows(m.reshape(16, -1))
        return self._T

    @property
    def centroids(self) -> np.ndarray:
        """Ink centroid of each template, so displacements are class-relative."""
        if self._cent is None:
            self._cent = G.patch_centroids(self.templates.reshape(16, self.gh, self.gw))
        return self._cent

    def classify(self, patches: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Returns (class index, best NCC, margin over the runner-up)."""
        if len(patches) == 0:
            z = np.zeros(0)
            return z.astype(np.int64), z.astype(np.float32), z.astype(np.float32)
        X = znorm_rows(patches.reshape(len(patches), -1))
        S = X @ self.templates.T
        order = np.argsort(-S, axis=1)
        i = np.arange(len(X))
        best = order[:, 0]
        b0 = S[i, order[:, 0]]
        b1 = S[i, order[:, 1]]
        return best, b0.astype(np.float32), (b0 - b1).astype(np.float32)

    def separation(self) -> float:
        """Worst-case template distinguishability -- the ceiling on accuracy.

        If two templates are nearly identical the classifier cannot tell those
        two digits apart no matter how many frames it sees, and the operator
        needs to be told that the picture, not the software, is the limit.
        """
        S = self.templates @ self.templates.T
        return float(1.0 - S[~np.eye(16, dtype=bool)].max())

    # -- persistence -------------------------------------------------------- #
    def save(self, path: str) -> None:
        tmp = path + ".tmp.npz"
        np.savez_compressed(tmp, sum=self.sum, n=self.n, gh=self.gh, gw=self.gw,
                            min_samples=self.min_samples)
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: str) -> "GlyphBank":
        z = np.load(path)
        b = cls(int(z["gh"]), int(z["gw"]), int(z["min_samples"]))
        b.sum = z["sum"]
        b.n = z["n"]
        return b


# --------------------------------------------------------------------------- #
@dataclass
class RowReading:
    row: int
    address: Optional[int]
    addr_margin: float
    accepted: bool
    reason: str = ""


@dataclass
class FrameReading:
    """Everything one frame yielded, and everything needed to judge it."""
    rows: List[RowReading]
    base: Optional[int]
    n_rows_ok: int
    values: Dict[int, Tuple[int, float]] = field(default_factory=dict)   # addr -> (byte, weight)
    ladder_ok: bool = False
    motion: Optional[float] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    cells: Optional[np.ndarray] = None          # (N,2) cells that were cut
    cell_class: Optional[np.ndarray] = None
    cell_margin: Optional[np.ndarray] = None
    torn: bool = False
    # per-cell displacement from the matched template, for the homography tracker
    track_resid: Optional[np.ndarray] = None
    track_weight: Optional[np.ndarray] = None

    @property
    def usable(self) -> bool:
        return self.ladder_ok and self.n_rows_ok >= 3


# --------------------------------------------------------------------------- #
# Columns kept in the cut on every frame regardless of what is already locked,
# purely so the homography fit has landmarks spread across the whole width.
# Without them a page that is nearly finished would be tracked from its address
# column alone, and a fit from a 14 %-wide strip cannot see perspective.
TRACK_COLS = [10, 16, 22, 28, 34, 40, 46, 52, 55, 56]


class PageReader:
    """Turns one frame into per-address byte observations, or into nothing."""

    def __init__(self, bank: GlyphBank,
                 addr_margin_min: float = 0.03,
                 byte_margin_min: float = 0.02,
                 ncc_min: float = 0.25,
                 min_cluster: int = 3,
                 address_windows: Optional[List[Tuple[int, int]]] = None,
                 assume_aligned: bool = True):
        self.bank = bank
        self.addr_margin_min = addr_margin_min
        self.byte_margin_min = byte_margin_min
        self.ncc_min = ncc_min
        self.min_cluster = min_cluster
        self.address_windows = address_windows
        self.assume_aligned = assume_aligned

    # -- bootstrap ---------------------------------------------------------- #
    def ladder_geometry(self, reg: G.Registration, ink: np.ndarray,
                        origin: Tuple[float, float] = (0.0, 0.0)):
        """How much does this registration look like it is on the address block?

        Uses only the redundancy the screen prints, so it works before there is
        any template to classify with -- which is the whole difficulty of
        starting up.  Two facts, both true of every page of every machine:

            the 0x10s digit counts 0..F down the rows  -> sixteen glyphs that
                                                          must be MUTUALLY UNLIKE
            the 0x1s digit never changes              -> sixteen glyphs that
                                                          must be near IDENTICAL

        A registration sitting half a character off, or a row out, or on the
        instrument's bodywork, fails both at once.  Returned as a continuous
        score so a search can be run over it, plus the pass/fail verdict.
        """
        cells = np.array([(r, c) for r in range(G.NROW) for c in G.ADDR_COLS])
        P = reg.cut(ink, cells, self.bank.gh, self.bank.gw, OVER_X, OVER_Y, origin)
        A = P.reshape(G.NROW, 8, self.bank.gh, self.bank.gw)

        lad = znorm_rows(A[:, G.LADDER_COL].reshape(G.NROW, -1))
        off = (lad @ lad.T)[~np.eye(G.NROW, dtype=bool)]
        uni = znorm_rows(A[:, G.UNIT_COL].reshape(G.NROW, -1))
        offu = (uni @ uni.T)[~np.eye(G.NROW, dtype=bool)]

        # Judged on robust statistics, not on the extremes.  A single row can be
        # ruined by a glare spot or a half-drawn repaint without the
        # registration being wrong at all, and an acceptance test that a lone
        # outlier can veto rejects usable frames for ever -- measured: at a
        # placement error of two pixels in twelve the worst pair of "identical"
        # glyphs still only correlates at 0.44 while the typical pair is fine.
        p95 = float(np.percentile(off, 95))
        p20u = float(np.percentile(offu, 20))
        score = float((1.0 - off.mean()) + offu.mean())
        ok, why = True, "ok"
        if p95 > 0.97 or off.mean() > 0.90:
            ok, why = False, "ladder not distinct (p95 %.3f mean %.3f)" % (p95, off.mean())
        elif p20u < 0.45:
            ok, why = False, "0x1s column not constant (p20 %.3f)" % p20u
        return score, ok, why, P

    def fit_quality(self, reg: G.Registration, ink: np.ndarray,
                    origin: Tuple[float, float] = (0.0, 0.0)) -> float:
        """How well the grid explains the text, ACROSS THE WHOLE BLOCK.

        The ladder check is the stronger test but it lives entirely in the left
        eighth of the panel, so it cannot see the right-hand end of the grid
        sliding off -- and with a handheld camera that is exactly how a fit
        comes apart.  This samples the address block and a spread of columns to
        the far right and reports the median match strength, which collapses as
        soon as cells stop containing whole glyphs.
        """
        if not self.bank.ready:
            return 0.0
        cells = np.array([(r, c) for r in range(G.NROW) for c in (G.ADDR_COLS + TRACK_COLS)])
        P = reg.cut(ink, cells, self.bank.gh, self.bank.gw, OVER_X, OVER_Y, origin)
        _, ncc, margin = self.bank.classify(P)
        return float(np.median(ncc) + np.median(margin))

    def bootstrap(self, reg: G.Registration, ink: np.ndarray,
                  seed_base: Optional[int] = None,
                  origin: Tuple[float, float] = (0.0, 0.0)) -> Tuple[bool, str]:
        """Train the bank from one frame's address block, if it is trustworthy."""
        _, ok, why, P = self.ladder_geometry(reg, ink, origin)
        if not ok:
            return False, why
        A = P.reshape(G.NROW, 8, self.bank.gh, self.bank.gw)

        labels, patches = [], []
        if seed_base is not None:
            for r in range(G.NROW):
                s = "%08X" % ((seed_base + 0x10 * r) & 0xFFFFFFFF)
                for j in range(8):
                    labels.append(HEXD.index(s[j]))
                    patches.append(A[r, j])
        elif self.assume_aligned:
            for r in range(G.NROW):
                labels.append(r); patches.append(A[r, G.LADDER_COL])
                labels.append(0); patches.append(A[r, G.UNIT_COL])
        else:
            return False, "no seed address and --any-address set"
        self.bank.add(labels, np.array(patches))
        return True, "ok"

    # -- reading ------------------------------------------------------------ #
    def read(self, reg: G.Registration, ink: np.ndarray,
             wanted: Optional[Dict[int, List[int]]] = None,
             train: bool = True, decay: float = 0.0,
             origin: Tuple[float, float] = (0.0, 0.0),
             known: Optional[Dict[int, Tuple[int, Dict[int, int]]]] = None) -> FrameReading:
        """Decode one frame.

        `wanted` maps a row index to the byte indices still worth reading, so a
        page that is nearly finished costs almost nothing: locked cells are not
        cut, not matched and not voted on.  Passing None reads every byte.
        """
        gh, gw = self.bank.gh, self.bank.gw
        addr_cells = [(r, c) for r in range(G.NROW) for c in G.ADDR_COLS]
        byte_cells: List[Tuple[int, int]] = []
        byte_of: List[Tuple[int, int, int]] = []      # (row, byte index, nibble)
        for r in range(G.NROW):
            want = range(16) if wanted is None else wanted.get(r, [])
            for k in want:
                hi, lo = G.BYTE_COLS[k]
                byte_cells.append((r, hi)); byte_of.append((r, k, 1))
                byte_cells.append((r, lo)); byte_of.append((r, k, 0))
        track_cells = [(r, c) for r in range(G.NROW) for c in TRACK_COLS]

        cells = np.array(addr_cells + byte_cells + track_cells, dtype=np.int64)
        P = reg.cut(ink, cells, gh, gw, OVER_X, OVER_Y, origin)
        idx, ncc, margin = self.bank.classify(P)

        # ---- displacements, for the tracker ------------------------------- #
        obs = G.patch_centroids(P)
        tpl = self.bank.centroids[idx]
        resid = np.stack([(obs[:, 0] - tpl[:, 0]) * (1.0 + OVER_X),
                          (obs[:, 1] - tpl[:, 1]) * (1.0 + OVER_Y)], axis=1)
        # Only confidently-matched cells may steer the geometry.  A displacement
        # is "how far this glyph sits from where its template says it should" --
        # which is meaningless if the glyph was matched to the wrong template,
        # and a wrong match is not rare early on, before the templates have
        # settled.  Measured on a perfectly-placed grid, letting every cell vote
        # produced a systematic -0.14 cell bias and walked the fit off the text
        # in eight frames.
        tw = (np.clip((margin - 0.05) / 0.10, 0, 1)
              * np.clip((ncc - 0.35) / 0.25, 0, 1)
              * (obs[:, 2] > 0.01))

        # ---- addresses ----------------------------------------------------- #
        na = len(addr_cells)
        ach = np.array([HEXD[i] for i in idx[:na]]).reshape(G.NROW, 8)
        amg = margin[:na].reshape(G.NROW, 8)
        ancc = ncc[:na].reshape(G.NROW, 8)

        rows: List[RowReading] = []
        for r in range(G.NROW):
            m = float(amg[r].min())
            try:
                a = int("".join(ach[r]), 16)
            except ValueError:
                a = None
            ok = a is not None and m >= self.addr_margin_min and float(ancc[r].min()) >= self.ncc_min
            rows.append(RowReading(r, a, m, ok,
                                   "" if ok else ("low margin %.3f" % m if a is not None else "unreadable")))

        # Cluster the rows on the base address each of them implies.  A torn
        # repaint puts two pages on the screen at once -- 29 % of frames during
        # a sweep, measured -- and both halves are perfectly good data as long
        # as each row is filed under the address it states.
        votes: Dict[int, List[int]] = {}
        for rr in rows:
            if rr.accepted and rr.address is not None:
                b = (rr.address - 0x10 * rr.row) & 0xFFFFFFFF
                votes.setdefault(b, []).append(rr.row)
        clusters = {b: rs for b, rs in votes.items() if len(rs) >= self.min_cluster}
        if self.address_windows:
            clusters = {b: rs for b, rs in clusters.items()
                        if any(lo <= b < hi for lo, hi in self.address_windows)}
        for rr in rows:
            if rr.accepted:
                b = (rr.address - 0x10 * rr.row) & 0xFFFFFFFF
                if b not in clusters:
                    rr.accepted = False
                    rr.reason = "address %08X not corroborated" % (rr.address or 0)
        base = max(clusters.items(), key=lambda kv: len(kv[1]))[0] if clusters else None
        n_ok = sum(1 for rr in rows if rr.accepted)
        torn = len(clusters) > 1

        # ---- bytes ---------------------------------------------------------- #
        values: Dict[int, Tuple[int, float]] = {}
        acc = {rr.row: rr.address for rr in rows if rr.accepted}
        if byte_of:
            nib = np.full((G.NROW, 16, 2), -1, np.int64)
            nw = np.zeros((G.NROW, 16, 2), np.float32)
            for t, (r, k, half) in enumerate(byte_of):
                j = na + t
                nib[r, k, half] = idx[j]
                nw[r, k, half] = (margin[j] if ncc[j] >= self.ncc_min else 0.0)
            for r, a in acc.items():
                want = range(16) if wanted is None else wanted.get(r, [])
                for k in want:
                    hi, lo = nib[r, k, 1], nib[r, k, 0]
                    if hi < 0 or lo < 0:
                        continue
                    m = float(min(nw[r, k, 1], nw[r, k, 0]))
                    if m < self.byte_margin_min:
                        continue
                    values[(a + k) & 0xFFFFFFFF] = (int(hi) * 16 + int(lo), m)

        # ---- training ------------------------------------------------------- #
        ladder_ok = n_ok >= G.NROW - 2 or (torn and n_ok >= G.NROW - 3)
        if train and ladder_ok and base is not None:
            labels, patches = [], []
            for rr in rows:
                if not rr.accepted:
                    continue
                s = "%08X" % rr.address
                for j in range(8):
                    labels.append(HEXD.index(s[j]))
                    patches.append(P[rr.row * 8 + j])
            # Also train on bytes the store has already COMMITTED.  The address
            # column alone is a badly unbalanced teacher -- a page's addresses
            # contain the same five or six digits over and over, so 'B', 'E' and
            # 'F' arrive once per frame against '0' six hundred times, their
            # templates stay noisy, and rows get rejected for low margin on a
            # digit that was in fact read correctly (measured: 657 samples of
            # '0' against 7 of 'F', and two rows per frame lost to it).
            # Committed bytes are balanced, plentiful, and already carry four
            # frames of agreement behind them, so this is training on what has
            # been verified rather than on what has merely been guessed.
            if known:
                pos = {(r, c): na + t for t, (r, k, half) in enumerate(byte_of)
                       for c in [G.BYTE_COLS[k][half]]}
                for r, (want_addr, vals) in known.items():
                    rr = rows[r]
                    if not rr.accepted or rr.address != want_addr:
                        continue        # the page moved under us; labels are stale
                    for k, v in vals.items():
                        hi, lo = G.BYTE_COLS[k]
                        for c, lab in ((hi, v >> 4), (lo, v & 15)):
                            j = pos.get((r, c))
                            if j is not None:
                                labels.append(lab)
                                patches.append(P[j])
            if labels:
                self.bank.add(labels, np.array(patches), decay=decay)

        metrics = {
            "addr_margin": float(np.median(amg)) if len(amg) else 0.0,
            "addr_ncc": float(np.median(ancc)) if len(ancc) else 0.0,
            "byte_margin": float(np.median(margin[na:na + len(byte_of)])) if byte_of else float("nan"),
            "ink": float(np.percentile(P, 98)) if P.size else 0.0,
            "separation": self.bank.separation() if self.bank.ready else 0.0,
        }
        return FrameReading(rows=rows, base=base, n_rows_ok=n_ok, values=values,
                            ladder_ok=ladder_ok, metrics=metrics, cells=cells,
                            cell_class=idx, cell_margin=margin, torn=torn,
                            track_resid=resid, track_weight=tw)
