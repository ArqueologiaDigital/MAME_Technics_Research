"""Character layout of one KN7000 MEMORY DUMP row.

The viewer prints (DbMemoryDumpProc @ 0x484878AC):

    AAAAAAAA<gap1>HH HH HH HH HH HH HH HH-HH HH HH HH HH HH HH HH<gap2>CCCCCCCCCCCCCCCC

i.e. an 8 hex-digit address, 16 bytes as %02X separated by single spaces with a
'-' instead of a space after byte 7, then a 16-character ASCII pane ('.' for
bytes < 0x20).  Everything is one fixed-pitch bitmap font, so a row is a fixed
sequence of character cells and the whole geometry problem reduces to finding
the left edge and the character pitch.

gap1/gap2 are left as parameters because they are the only part of the format
string we cannot read off the disassembly summary with certainty; the grid
fitter tries the plausible values and keeps the best-scoring one.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

INK = 1      # a character cell that always contains ink
SPACE = 0    # a character cell that is always blank
FREE = -1    # unknown content (ASCII pane) -- ignored when fitting


@dataclass
class RowLayout:
    gap1: int = 2
    gap2: int = 2
    kind: List[int] = field(default_factory=list)
    addr_idx: List[int] = field(default_factory=list)      # 8 char indices
    byte_idx: List[tuple] = field(default_factory=list)    # 16 (hi, lo) pairs
    sep_idx: List[int] = field(default_factory=list)       # 15 separator cells
    ascii_idx: List[int] = field(default_factory=list)     # 16 char indices
    ncols: int = 0

    @classmethod
    def build(cls, gap1: int = 2, gap2: int = 2) -> "RowLayout":
        kind: List[int] = []
        addr_idx = []
        for _ in range(8):
            addr_idx.append(len(kind)); kind.append(INK)
        for _ in range(gap1):
            kind.append(SPACE)
        byte_idx = []
        sep_idx = []
        for k in range(16):
            hi = len(kind); kind.append(INK)
            lo = len(kind); kind.append(INK)
            byte_idx.append((hi, lo))
            if k != 15:
                sep_idx.append(len(kind))
                # the '-' after byte 7 has ink; the other separators are blank
                kind.append(INK if k == 7 else SPACE)
        for _ in range(gap2):
            kind.append(SPACE)
        ascii_idx = []
        for _ in range(16):
            ascii_idx.append(len(kind)); kind.append(FREE)
        return cls(gap1=gap1, gap2=gap2, kind=kind, addr_idx=addr_idx,
                   byte_idx=byte_idx, sep_idx=sep_idx, ascii_idx=ascii_idx,
                   ncols=len(kind))

    @property
    def hex_end(self) -> int:
        """Char index one past the last hex digit (end of the self-checking part)."""
        return self.byte_idx[-1][1] + 1


DEFAULT = RowLayout.build(2, 2)
NROWS = 16
NBYTES = 16
