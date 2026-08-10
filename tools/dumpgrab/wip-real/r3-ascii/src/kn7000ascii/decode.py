"""Two independent channels over the same 256 bytes, and the rule that fuses
them.

Channel H (hex pane)    two 5x7 glyphs per byte, 16 classes each -> 8 bits.
Channel A (ASCII pane)  one 5x7 glyph per byte, but the byte -> glyph map is
                        MANY-TO-ONE: measured on the instrument, 256 values
                        collapse onto 154 distinct bitmaps, and one of those
                        classes has 62 members (0xC0..0xFF minus D7 and F7).
                        So A *constrains*, it does not determine.
Channel C (colour)      cell background: aqua/yellow/lime/fuchsia mark the four
                        legend bytes, and -- not previously noted -- the ASCII
                        pane cells are highlighted too, so C is available twice.

Everything is a log-posterior over the 256 byte values, so fusing is addition.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np

from .forward import CellRenderer, znorm_rows
from .geometry_ascii import ROW

HEXC = "0123456789ABCDEF"
NEG = -60.0            # log-prob floor for "this channel rules the value out"


# --------------------------------------------------------------------------- #
#  font bundle
# --------------------------------------------------------------------------- #
@dataclass
class Font:
    charmap: np.ndarray        # (256, 7, 5) uint8 -- ASCII-pane glyph per byte
    cls_of: np.ndarray         # (256,) int -- ASCII class index per byte
    proto: np.ndarray          # (ncls, 7, 5) uint8 -- one bitmap per class
    members: List[List[int]]   # class index -> byte values
    hex_labels: List[str]
    hex_bitmaps: np.ndarray    # (18, 7, 5)

    @classmethod
    def load(cls, path: str) -> "Font":
        z = np.load(path, allow_pickle=False)
        lens = z["member_lens"]; flat = z["member_flat"]
        members, k = [], 0
        for n in lens:
            members.append([int(x) for x in flat[k:k + int(n)]]); k += int(n)
        return cls(charmap=z["charmap"], cls_of=z["cls_of"], proto=z["proto"],
                   members=members,
                   hex_labels=[str(x) for x in z["hex_labels"]],
                   hex_bitmaps=z["hex_bitmaps"])

    @property
    def hexmap(self) -> Dict[str, np.ndarray]:
        return {c: self.hex_bitmaps[i].astype(np.float64)
                for i, c in enumerate(self.hex_labels)}

    def class_size(self) -> np.ndarray:
        return np.array([len(m) for m in self.members], np.int32)


# --------------------------------------------------------------------------- #
#  common machinery
# --------------------------------------------------------------------------- #
def _ncc_cell(img, ren, r, i, templates_native, ctx=None):
    """NCC of the observed cell window against each native template rendered in
    place.  `ctx` = (left, right, up, down) native bitmaps or None."""
    u0, u1, v0, v1, _, _ = ren.window(r, i)
    H, W = img.shape
    if u0 < 0 or v0 < 0 or u1 > W or v1 > H:
        return None
    obs = img[v0:v1, u0:u1][ren.core].ravel()
    Wx, Wy, _ = ren.weights(r, i)
    L, R, U, D = ctx if ctx is not None else (None, None, None, None)
    mods = np.stack([ren.render(Wx, Wy, ren.canvas(t, L, R, U, D))[ren.core].ravel()
                     for t in templates_native])
    O = znorm_rows(obs[None, :])
    M = znorm_rows(mods)
    return (M @ O[0]).astype(np.float64)


def _softmax(s, T):
    z = (s - s.max()) / max(T, 1e-6)
    e = np.exp(z)
    return e / e.sum()


def calibrate_temperature(scores: np.ndarray, truth: np.ndarray,
                          grid=np.geomspace(0.005, 1.0, 60)) -> float:
    """Pick the softmax temperature that maximises the log-likelihood of the
    labels we already know (the address ladder).  No oracle involved."""
    best = (grid[0], -1e18)
    for T in grid:
        ll = 0.0
        for s, t in zip(scores, truth):
            p = _softmax(s, T)
            ll += np.log(max(p[t], 1e-12))
        if ll > best[1]:
            best = (float(T), ll)
    return best[0]


# --------------------------------------------------------------------------- #
#  channel H -- the hex pane
# --------------------------------------------------------------------------- #
class HexChannel:
    def __init__(self, img, grid, font: Font, sigma_x, sigma_y, T=0.05):
        self.img, self.grid, self.font = img, grid, font
        self.ren = CellRenderer(grid, sigma_x, sigma_y)
        self.T = T
        self.digits = np.stack([font.hexmap[c] for c in HEXC])
        self.blank = np.zeros((7, 5))
        self.dash = font.hexmap["-"]

    def _neighbours(self, r, i, dig):
        """native bitmaps of the four neighbours of hex cell i, from the
        current digit estimate `dig` (dict cell->bitmap)."""
        return (dig.get((r, i - 1)), dig.get((r, i + 1)),
                dig.get((r - 1, i)), dig.get((r + 1, i)))

    def run(self, passes: int = 2):
        cells = []
        for r in range(16):
            for k, (hi, lo) in enumerate(ROW.byte_idx):
                cells.append((r, hi)); cells.append((r, lo))
        # static context: blanks and dashes are known
        est = {}
        for r in range(16):
            for i in ROW.gap1_idx + ROW.gap2_idx:
                est[(r, i)] = self.blank
            for i in ROW.sep_idx:
                est[(r, i)] = self.dash if i == ROW.hex_dash_idx else self.blank
            est[(r, ROW.ascii_sep_idx)] = self.dash
        post = {}
        raw = {}
        for p in range(passes):
            for (r, i) in cells:
                ctx = self._neighbours(r, i, est) if p > 0 else None
                s = _ncc_cell(self.img, self.ren, r, i, self.digits, ctx)
                if s is None:
                    continue
                raw[(r, i)] = s
                post[(r, i)] = _softmax(s, self.T)
            for (r, i), pr in post.items():
                est[(r, i)] = self.digits[int(np.argmax(pr))]
        return post, raw

    def address_scores(self):
        """NCC scores for the supervised address cells, for temperature
        calibration; returns (scores, truth_indices)."""
        S, Tr = [], []
        for r in range(16):
            for ci, lab in ((ROW.addr_idx[7], "0"), (ROW.addr_idx[6], HEXC[r])):
                s = _ncc_cell(self.img, self.ren, r, ci, self.digits)
                if s is None:
                    continue
                S.append(s); Tr.append(HEXC.index(lab))
        return np.stack(S), np.array(Tr)

    def address_digits(self):
        out = []
        for r in range(16):
            row = []
            for ci in ROW.addr_idx:
                s = _ncc_cell(self.img, self.ren, r, ci, self.digits)
                row.append(HEXC[int(np.argmax(s))] if s is not None else "?")
            out.append("".join(row))
        return out


# --------------------------------------------------------------------------- #
#  channel A -- the ASCII pane
# --------------------------------------------------------------------------- #
class AsciiChannel:
    def __init__(self, img, grid, font: Font, sigma_x, sigma_y, T=0.05):
        self.img, self.grid, self.font = img, grid, font
        self.ren = CellRenderer(grid, sigma_x, sigma_y)
        self.T = T
        self.proto = font.proto.astype(np.float64)
        self.dash = font.hexmap["-"]
        self.blank = np.zeros((7, 5))

    def run(self, passes: int = 2):
        cells = [(r, ROW.ascii_idx[j]) for r in range(16) for j in range(16)]
        est = {}
        for r in range(16):
            est[(r, ROW.ascii_sep_idx)] = self.dash
            for i in ROW.gap2_idx:
                est[(r, i)] = self.blank
        cls_post, raw = {}, {}
        for p in range(passes):
            for (r, i) in cells:
                ctx = ((est.get((r, i - 1)), est.get((r, i + 1)),
                        est.get((r - 1, i)), est.get((r + 1, i)))
                       if p > 0 else None)
                s = _ncc_cell(self.img, self.ren, r, i, self.proto, ctx)
                if s is None:
                    continue
                raw[(r, i)] = s
                cls_post[(r, i)] = _softmax(s, self.T)
            for (r, i), pr in cls_post.items():
                est[(r, i)] = self.proto[int(np.argmax(pr))]
        return cls_post, raw

    def byte_logpost(self, cls_post) -> np.ndarray:
        """(256,256) log-posterior over byte values, one row per screen byte.
        A class of size m spreads its mass over its m members -- this is the
        many-to-one penalty, and it is what stops ASCII from over-claiming."""
        out = np.full((256, 256), NEG, np.float64)
        sizes = self.font.class_size()
        for r in range(16):
            for j in range(16):
                i = ROW.ascii_idx[j]
                pr = cls_post.get((r, i))
                if pr is None:
                    out[r * 16 + j, :] = 0.0
                    continue
                lp = np.full(256, -1e9)
                for ci, members in enumerate(self.font.members):
                    v = np.log(max(pr[ci], 1e-12) / sizes[ci])
                    for b in members:
                        lp[b] = v
                out[r * 16 + j] = lp - _logsumexp(lp)
        return out


def _logsumexp(a):
    m = a.max()
    return m + np.log(np.exp(a - m).sum())


# --------------------------------------------------------------------------- #
#  channel C -- the highlight colours
# --------------------------------------------------------------------------- #
LEGEND_RGB = {"aqua": (0, 252, 252), "yellow": (252, 252, 0),
              "lime": (0, 252, 0), "fuchsia": (252, 0, 252)}
LEGEND_DEFAULT = {"aqua": 0xF0, "yellow": 0xF7, "lime": 0xFF}


def colour_hits(rgb: np.ndarray, grid, cells, tol=90):
    """Which of the given (r, cell) positions sit on a highlighted background."""
    out = {}
    for (r, i) in cells:
        x = grid.cell_x(r, i); y = grid.cell_y(r)
        u0 = int(round(x)); v0 = int(round(y))
        u1 = int(round(x + grid.px)); v1 = int(round(y + grid.py * 0.8))
        if u0 < 0 or v0 < 0 or v1 > rgb.shape[0] or u1 > rgb.shape[1]:
            continue
        blk = rgb[v0:v1, u0:u1].reshape(-1, 3).astype(np.float64)
        for name, ref in LEGEND_RGB.items():
            d = np.abs(blk - np.array(ref, np.float64)).max(axis=1)
            frac = float((d < tol).mean())
            if frac > 0.30:
                out[(r, i)] = (name, frac)
                break
    return out


# --------------------------------------------------------------------------- #
#  the fusion rule
# --------------------------------------------------------------------------- #
def hex_byte_logpost(hex_post) -> np.ndarray:
    out = np.zeros((256, 256), np.float64)
    for r in range(16):
        for k, (hi, lo) in enumerate(ROW.byte_idx):
            ph = hex_post.get((r, hi)); pl = hex_post.get((r, lo))
            if ph is None or pl is None:
                continue
            lp = (np.log(np.maximum(ph, 1e-12))[:, None]
                  + np.log(np.maximum(pl, 1e-12))[None, :]).ravel()
            out[r * 16 + k] = lp - _logsumexp(lp)
    return out


def fuse(log_hex: np.ndarray, log_asc: Optional[np.ndarray] = None,
         colour: Optional[Dict[int, int]] = None,
         w_hex: float = 1.0, w_asc: float = 1.0) -> np.ndarray:
    """Add the log-posteriors.  Weights let a channel be down-weighted when its
    own calibration says it is the blurrier one; 1.0/1.0 is the honest default
    because both channels are the same font at the same scale.

    `colour` maps byte index -> the value its highlight proves, which is hard
    evidence: it overrides both glyph channels.
    """
    L = w_hex * log_hex
    if log_asc is not None:
        L = L + w_asc * log_asc
    L = L - L.max(axis=1, keepdims=True)
    P = np.exp(L)
    P /= P.sum(axis=1, keepdims=True)
    if colour:
        for idx, val in colour.items():
            P[idx] = 0.0
            P[idx, val] = 1.0
    return P


def argmax_bytes(P: np.ndarray):
    b = P.argmax(axis=1).astype(np.uint8)
    conf = P.max(axis=1)
    return bytes(b), conf
