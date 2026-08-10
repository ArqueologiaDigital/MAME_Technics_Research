"""Row geometry of the MEMORY DUMP screen, INCLUDING the ASCII pane.

★ CORRECTION TO doc/GEOMETRY.txt AND kn7000dump/layout.py ★

Both currently describe the ASCII pane as *16 consecutive cells* and put the row
at 75 cells wide.  Measured on an emulator native frame whose bytes we wrote
(scratch page filled with 00..FF), the pane is **17 cells**: it carries the same
'-' separator after the 8th character that the hex pane carries after byte 7.

    AAAAAAAA__HH HH HH HH HH HH HH HH-HH HH HH HH HH HH HH HH__CCCCCCCC-CCCCCCCC
    ^0     ^7 ^8         ^10                       ^33            ^59  ^67   ^75

    cell index   content
    -----------  -------------------------------------------------------------
      0..7       8 hex digits of the row's CPU address
      8, 9       blank
     10 + 3i     high nibble of byte i (i = 0..7);  11 + 3i = low nibble
     12 + 3i     blank separator                    (i = 0..6)
     33          '-'  (the hex pane's mid separator)
     34 + 3j     high nibble of byte 8+j (j = 0..7); 35 + 3j = low nibble
     36 + 3j     blank separator                    (j = 0..6)
     56          low nibble of byte 15  -- last hex cell
     57, 58      blank
     59 + j      ASCII character of byte j          (j = 0..7)
     67          '-'  (the ASCII pane's mid separator)  ← was missing
     68 + j      ASCII character of byte 8+j        (j = 0..7)
     75          ASCII character of byte 15  -- last cell of the row
    -----------  -------------------------------------------------------------
    ncols = 76   (was 75)

Native pixels (MAME `-snapview native`, 640x240 LCD raster):
    grid origin (90, 55), char pitch 6, row pitch 9, glyph 5x7 in the cell's
    top-left.  Cell i spans x = 90 + 6*i .. +4; row r spans y = 55 + 9*r .. +6.
    Cell 75 therefore ends at x = 544, inside the panel's 84..548 body.

Verified against `alpha/frames/0000.png` (page = 00..FF in order): the ink-column
runs inside the panel are exactly {0..7, 10,11, 13,14, ..., 33, ..., 56,
59..75} and nothing else.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

INK = 1
SPACE = 0
FREE = -1

NATIVE_X0, NATIVE_Y0 = 90, 55
NATIVE_PX, NATIVE_PY = 6, 9
NATIVE_GW, NATIVE_GH = 5, 7
NROWS, NBYTES = 16, 16


@dataclass
class AsciiRowLayout:
    kind: List[int] = field(default_factory=list)
    addr_idx: List[int] = field(default_factory=list)
    gap1_idx: List[int] = field(default_factory=list)
    byte_idx: List[Tuple[int, int]] = field(default_factory=list)
    sep_idx: List[int] = field(default_factory=list)
    hex_dash_idx: int = 33
    gap2_idx: List[int] = field(default_factory=list)
    ascii_idx: List[int] = field(default_factory=list)
    ascii_sep_idx: int = 67
    ncols: int = 76

    @classmethod
    def build(cls, gap1: int = 2, gap2: int = 2, ascii_sep: bool = True):
        kind: List[int] = []
        addr_idx, gap1_idx, byte_idx, sep_idx, gap2_idx, ascii_idx = [], [], [], [], [], []
        for _ in range(8):
            addr_idx.append(len(kind)); kind.append(INK)
        for _ in range(gap1):
            gap1_idx.append(len(kind)); kind.append(SPACE)
        hex_dash = -1
        for k in range(16):
            hi = len(kind); kind.append(INK)
            lo = len(kind); kind.append(INK)
            byte_idx.append((hi, lo))
            if k != 15:
                sep_idx.append(len(kind))
                if k == 7:
                    hex_dash = len(kind)
                kind.append(INK if k == 7 else SPACE)
        for _ in range(gap2):
            gap2_idx.append(len(kind)); kind.append(SPACE)
        asc_sep = -1
        for j in range(16):
            if j == 8 and ascii_sep:
                asc_sep = len(kind); kind.append(INK)
            ascii_idx.append(len(kind)); kind.append(FREE)
        return cls(kind=kind, addr_idx=addr_idx, gap1_idx=gap1_idx,
                   byte_idx=byte_idx, sep_idx=sep_idx, hex_dash_idx=hex_dash,
                   gap2_idx=gap2_idx, ascii_idx=ascii_idx,
                   ascii_sep_idx=asc_sep, ncols=len(kind))

    @property
    def hex_end(self) -> int:
        return self.byte_idx[-1][1] + 1


ROW = AsciiRowLayout.build(2, 2, True)
ROW75 = AsciiRowLayout.build(2, 2, False)   # the old (wrong) 75-cell model


@dataclass
class Grid:
    """An affine cell grid over some image: cell (r,i) top-left is
    (x0 + px*i, y0 + py*r), glyph box gw x gh, optional per-row x offset."""
    x0: float
    px: float
    y0: float
    py: float
    gw: float
    gh: float
    row_x0: List[float] = field(default_factory=list)

    def cell_x(self, r: int, i: int) -> float:
        base = self.row_x0[r] if self.row_x0 else self.x0
        return base + self.px * i

    def cell_y(self, r: int) -> float:
        return self.y0 + self.py * r


def native_grid() -> Grid:
    return Grid(NATIVE_X0, NATIVE_PX, NATIVE_Y0, NATIVE_PY, NATIVE_GW, NATIVE_GH)
