"""Assembly: merge voted pages into a sparse image + a KNOWN mask, and report coverage.

The hard rule here is that a hole is never quietly filled.  A dump with an invented byte
in it is worse than a dump with a documented gap, because the gap can be re-swept in
thirty seconds and the invention cannot be found again.  So:

* every byte carries a ``known`` bit,
* the fill byte for unknown positions is caller-chosen and recorded in the manifest,
* the coverage report lists contiguous runs AND holes, with addresses and sizes,
* and if the same address is seen twice with different values, the conflict is recorded
  rather than resolved by whoever wrote last.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from .contract import PAGE_SIZE
from .voting import VotedPage


@dataclass
class Region:
    start: int
    data: bytearray
    known: bytearray

    @property
    def end(self) -> int:
        return self.start + len(self.data)


class SparseImage:
    """Address-keyed sparse byte store with a per-byte known mask."""

    def __init__(self, fill: int = 0x00):
        self.fill = fill & 0xFF
        self.pages: Dict[int, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        self.conflicts: List[dict] = []

    def add_page(self, page: VotedPage) -> None:
        base = page.base_address
        data, known = page.flat()
        post = page.posterior.reshape(-1)
        if base in self.pages:
            old_d, old_k, old_p = self.pages[base]
            both = old_k & known
            diff = both & (old_d != data)
            if diff.any():
                for i in np.nonzero(diff)[0]:
                    self.conflicts.append({
                        "address": f"0x{base + int(i):08X}",
                        "kept": int(old_d[i]) if old_p[i] >= post[i] else int(data[i]),
                        "other": int(data[i]) if old_p[i] >= post[i] else int(old_d[i]),
                        "posterior_kept": float(max(old_p[i], post[i])),
                        "posterior_other": float(min(old_p[i], post[i])),
                    })
            take = (~old_k & known) | (both & (post > old_p))
            new_d = np.where(take, data, old_d)
            new_k = old_k | known
            new_p = np.maximum(old_p, post)
            self.pages[base] = (new_d.astype(np.uint8), new_k, new_p.astype(np.float32))
        else:
            self.pages[base] = (data.copy(), known.copy(), post.copy())

    # -- queries ---------------------------------------------------------------------
    def known_byte_count(self) -> int:
        return int(sum(k.sum() for _, k, _ in self.pages.values()))

    def address_span(self) -> Optional[Tuple[int, int]]:
        if not self.pages:
            return None
        lo = min(self.pages)
        hi = max(self.pages) + PAGE_SIZE
        return lo, hi

    def regions(self, max_gap: int = 0) -> List[Region]:
        """Contiguous runs of *known* bytes.  ``max_gap`` lets small holes be bridged in
        the output file (they stay unknown in the mask)."""
        if not self.pages:
            return []
        items = []
        for base in sorted(self.pages):
            d, k, _ = self.pages[base]
            items.append((base, d, k))
        regions: List[Region] = []
        cur: Optional[Region] = None
        for base, d, k in items:
            for i in range(PAGE_SIZE):
                addr = base + i
                if not k[i]:
                    continue
                if cur is not None and addr - cur.end <= max_gap and addr >= cur.end:
                    pad = addr - cur.end
                    if pad:
                        cur.data.extend(bytes([self.fill]) * pad)
                        cur.known.extend(b"\x00" * pad)
                    cur.data.append(int(d[i]))
                    cur.known.append(1)
                else:
                    if cur is not None:
                        regions.append(cur)
                    cur = Region(addr, bytearray([int(d[i])]), bytearray([1]))
        if cur is not None:
            regions.append(cur)
        return regions

    def holes(self) -> List[Tuple[int, int]]:
        """Gaps between the first and last known byte: [(start, length), ...]."""
        regs = self.regions()
        out = []
        for a, b in zip(regs, regs[1:]):
            out.append((a.end, b.start - a.end))
        return out

    # -- output ----------------------------------------------------------------------
    def write(self, outdir: str, prefix: str = "dump", max_gap: int = 0) -> dict:
        os.makedirs(outdir, exist_ok=True)
        regs = self.regions(max_gap=max_gap)
        manifest = {
            "fill_byte_for_unknown": f"0x{self.fill:02X}",
            "known_bytes": self.known_byte_count(),
            "pages": len(self.pages),
            "conflicts": self.conflicts,
            "regions": [],
            "holes": [{"start": f"0x{s:08X}", "length": n} for s, n in self.holes()],
        }
        for r in regs:
            name = f"{prefix}_{r.start:08X}_{len(r.data):06X}"
            binp = os.path.join(outdir, name + ".bin")
            mskp = os.path.join(outdir, name + ".mask")
            with open(binp, "wb") as fh:
                fh.write(bytes(r.data))
            with open(mskp, "wb") as fh:
                fh.write(bytes(r.known))
            manifest["regions"].append({
                "start": f"0x{r.start:08X}",
                "end": f"0x{r.end:08X}",
                "length": len(r.data),
                "known": int(sum(r.known)),
                "bin": os.path.basename(binp),
                "mask": os.path.basename(mskp),
            })
        with open(os.path.join(outdir, prefix + "_manifest.json"), "w") as fh:
            json.dump(manifest, fh, indent=2)
        return manifest


def coverage_report(img: SparseImage, expected: Optional[List[Tuple[int, int]]] = None) -> str:
    """Human-readable coverage: runs, holes, and (if given) progress against target ranges."""
    lines = []
    regs = img.regions()
    lines.append(f"pages assembled : {len(img.pages)}")
    lines.append(f"known bytes     : {img.known_byte_count()}")
    lines.append(f"contiguous runs : {len(regs)}")
    for r in regs:
        lines.append(f"  RUN  0x{r.start:08X}-0x{r.end - 1:08X}  {len(r.data):8d} bytes"
                     f"  known {int(sum(r.known))}")
    hs = img.holes()
    lines.append(f"holes           : {len(hs)}")
    for s, n in hs:
        lines.append(f"  HOLE 0x{s:08X}-0x{s + n - 1:08X}  {n:8d} bytes")
    if img.conflicts:
        lines.append(f"CONFLICTS       : {len(img.conflicts)} (same address, two values)")
        for c in img.conflicts[:20]:
            lines.append(f"  {c['address']}  kept 0x{c['kept']:02X} over 0x{c['other']:02X}"
                         f"  (posterior {c['posterior_kept']:.3f} vs"
                         f" {c['posterior_other']:.3f})")
    if expected:
        for start, length in expected:
            have = 0
            for base in img.pages:
                if start <= base < start + length:
                    have += int(img.pages[base][1].sum())
            pct = 100.0 * have / length if length else 0.0
            lines.append(f"target 0x{start:08X}+0x{length:X}: {have}/{length} bytes"
                         f" ({pct:.4f}%)")
    return "\n".join(lines)
