"""Glyph atlas for the MEMORY DUMP font.

The viewer draws only 18 distinct glyphs in the part we care about: the 16 hex
digits, the space and the '-' separator.  That is small enough that template
matching beats general OCR outright -- provided the templates are the *actual*
glyphs of the *actual* capture chain rather than a rendering of some other font.

The templates are therefore cut from captures whose contents we already know:
the ROM file is the oracle, so every character in every cell of a frame at a
known address is labelled with zero manual work.  `build_atlas` does exactly
that.  The result is a tiny .npz that also travels with the tool.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

CLASSES = "0123456789ABCDEF"          # the 16 classes the byte/address decoder uses
EXTRA = " -"                          # useful for grid self-checks
ALL_CLASSES = CLASSES + EXTRA

GH, GW = 18, 12                       # glyph patches are resampled to this size


def znorm(p: np.ndarray) -> np.ndarray:
    """Zero-mean, unit-norm -- makes matching invariant to gain and offset."""
    p = p.astype(np.float32)
    p = p - p.mean()
    n = float(np.sqrt((p * p).sum()))
    return p / n if n > 1e-6 else p


@dataclass
class Atlas:
    labels: List[str]
    templates: np.ndarray            # (nclass, GH, GW) float32, z-normalised
    counts: np.ndarray               # (nclass,) how many samples each average used
    gh: int = GH
    gw: int = GW
    meta: Optional[dict] = None

    # -- persistence -------------------------------------------------------- #
    def save(self, path: str) -> None:
        np.savez_compressed(
            path,
            labels=np.array(self.labels),
            templates=self.templates.astype(np.float32),
            counts=self.counts.astype(np.int64),
            gh=self.gh, gw=self.gw,
            meta=json.dumps(self.meta or {}),
        )

    @classmethod
    def load(cls, path: str) -> "Atlas":
        z = np.load(path, allow_pickle=False)
        meta = {}
        if "meta" in z:
            try:
                meta = json.loads(str(z["meta"]))
            except Exception:
                meta = {}
        return cls(labels=[str(x) for x in z["labels"]],
                   templates=z["templates"].astype(np.float32),
                   counts=z["counts"], gh=int(z["gh"]), gw=int(z["gw"]), meta=meta)

    # -- use ---------------------------------------------------------------- #
    @property
    def flat(self) -> np.ndarray:
        return self.templates.reshape(len(self.labels), -1)

    def classify(self, patches: np.ndarray,
                 allowed: Optional[Sequence[int]] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """patches: (N, GH, GW).  Returns (index, best_ncc, margin)."""
        n = patches.shape[0]
        X = patches.reshape(n, -1).astype(np.float32)
        X = X - X.mean(axis=1, keepdims=True)
        nrm = np.sqrt((X * X).sum(axis=1, keepdims=True))
        X = X / np.maximum(nrm, 1e-6)
        T = self.flat
        if allowed is not None:
            sel = np.asarray(allowed, dtype=np.int64)
            S = X @ T[sel].T
            order = np.argsort(-S, axis=1)
            best = sel[order[:, 0]]
            b0 = S[np.arange(n), order[:, 0]]
            b1 = S[np.arange(n), order[:, 1]] if S.shape[1] > 1 else b0 - 1.0
        else:
            S = X @ T.T
            order = np.argsort(-S, axis=1)
            best = order[:, 0]
            b0 = S[np.arange(n), order[:, 0]]
            b1 = S[np.arange(n), order[:, 1]]
        return best, b0.astype(np.float32), (b0 - b1).astype(np.float32)


class AtlasBuilder:
    """Accumulates labelled glyph patches and averages them into templates."""

    def __init__(self, labels: str = ALL_CLASSES, gh: int = GH, gw: int = GW):
        self.labels = list(labels)
        self.gh, self.gw = gh, gw
        self._sum: Dict[str, np.ndarray] = {c: np.zeros((gh, gw), np.float64) for c in self.labels}
        self._n: Dict[str, int] = {c: 0 for c in self.labels}

    def add(self, ch: str, patch: np.ndarray) -> None:
        if ch not in self._sum:
            return
        self._sum[ch] += znorm(patch)
        self._n[ch] += 1

    def add_many(self, chars: Sequence[str], patches: np.ndarray) -> None:
        for ch, p in zip(chars, patches):
            self.add(ch, p)

    @property
    def counts(self) -> Dict[str, int]:
        return dict(self._n)

    def finish(self, meta: Optional[dict] = None, min_samples: int = 1) -> Atlas:
        keep = [c for c in self.labels if self._n[c] >= min_samples]
        missing = [c for c in self.labels if self._n[c] < min_samples]
        if missing:
            (meta := dict(meta or {})).setdefault("missing_classes", missing)
        T = np.stack([znorm(self._sum[c] / max(self._n[c], 1)) for c in keep])
        counts = np.array([self._n[c] for c in keep], dtype=np.int64)
        return Atlas(labels=keep, templates=T.astype(np.float32), counts=counts,
                     gh=self.gh, gw=self.gw, meta=meta or {})
