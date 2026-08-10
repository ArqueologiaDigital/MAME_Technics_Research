"""Character layout of the KN7000 MEMORY DUMP screen, and the hex font.

All geometry here is in NATIVE LCD pixels (the 640x240 raster the firmware
draws).  Measured, not inferred -- see dumpgrab/doc/GEOMETRY.txt; the column
occupancy below was re-measured on /tmp/dg_cap1/frames/0300.png, which showed
the doc's "ASCII at 58..73" to be off by one and missing the second hyphen.
"""
import os
import numpy as np

# ---------------------------------------------------------------- raster ----
NAT_W, NAT_H = 640, 240
X0, Y0 = 90, 55           # first character cell, native pixels
PX, PY = 6, 9             # character pitch
GW, GH = 5, 7             # glyph bitmap inside the cell
NROWS = 16
NCOLS = 76                # 0..75 inclusive

# ------------------------------------------------------------ line layout ---
ADDR_CELLS = list(range(8))                    # 8 hex digits of the row address
HEX_CELLS = ([10 + 3 * i for i in range(8)] +  # high nibble of bytes 0..7
             [34 + 3 * j for j in range(8)])   # high nibble of bytes 8..15
# byte i occupies HEX_CELLS[i] and HEX_CELLS[i]+1
ASCII_CELLS = [59 + i for i in range(8)] + [68 + j for j in range(8)]
HYPHEN_CELLS = [33, 67]
BLANK_CELLS = ([8, 9] + [12 + 3 * i for i in range(8)][:-1] + [33 - 0] * 0 +
               [36 + 3 * j for j in range(7)] + [57, 58])
# rebuild BLANK_CELLS explicitly (clearer than the arithmetic above)
BLANK_CELLS = sorted(set(
    [8, 9] +
    [12 + 3 * i for i in range(7)] +      # 12,15,18,21,24,27,30  (33 is '-')
    [36 + 3 * j for j in range(7)] +      # 36,39,42,45,48,51,54
    [57, 58]))

# every cell that carries a hex digit
HEXDIGIT_CELLS = sorted(ADDR_CELLS + [c for h in HEX_CELLS for c in (h, h + 1)])

HEXCHARS = "0123456789ABCDEF"
CLASSES = list(HEXCHARS) + [" ", "-"]     # 18 template classes
CLS_SPACE = 16
CLS_HYPHEN = 17
NCLS = 18

_FONT_PATH = os.path.join(os.path.dirname(__file__), "font57.npy")


def load_font():
    """(18,7,5) uint8 glyph bitmaps, order = CLASSES.

    Harvested from clean emulator frames by averaging every instance of each
    glyph over 30 frames; every class came out unambiguous (no pixel disagreed
    between instances), so these are the firmware's exact bitmaps.
    """
    return np.load(_FONT_PATH).astype(np.float32)


_BASE_PATH = os.path.join(os.path.dirname(__file__), "panel_base.npy")
BASE_ORIGIN = (40, 75)      # native (y, x) of panel_base[0,0]
_BASE = None


def panel_base(ny0, ny1, nx0, nx1):
    """Native grey levels of the dump panel WITHOUT any text, over a window.

    The panel is not a flat 128 field: it has a raised border at native x=85 /
    y=50 (grey 200) and a SUNKEN BLACK LINE at native x=88 and y=53.  Those two
    black lines sit 2 px from character cell 0 and 2 px above text row 0, so a
    model that assumes a flat background mis-attributes their smear to the PSF
    -- which is exactly what inflated the first horizontal sigma estimate here
    from ~0.7 to 1.5 native px.  Harvested from 12 emulator frames with every
    character cell masked out; the 12 frames agreed to 0.0 everywhere.
    """
    global _BASE
    if _BASE is None:
        _BASE = np.load(_BASE_PATH)
    oy, ox = BASE_ORIGIN
    out = np.zeros((ny1 - ny0, nx1 - nx0), dtype=np.float64)
    sy0, sx0 = ny0 - oy, nx0 - ox
    sy1, sx1 = ny1 - oy, nx1 - ox
    ty0, tx0 = max(0, -sy0), max(0, -sx0)
    sy0c, sx0c = max(0, sy0), max(0, sx0)
    sy1c = min(_BASE.shape[0], sy1)
    sx1c = min(_BASE.shape[1], sx1)
    if sy1c > sy0c and sx1c > sx0c:
        out[ty0:ty0 + (sy1c - sy0c), tx0:tx0 + (sx1c - sx0c)] = _BASE[sy0c:sy1c, sx0c:sx1c]
    return out


INK_LEVEL = 128.0     # a glyph pixel pulls the 128 body down to 0


def cell_x(c):
    """native x of the left edge of character cell c."""
    return X0 + PX * c


def cell_y(r):
    """native y of the top edge of text row r."""
    return Y0 + PY * r


def known_row_text(row, addr_prefix=None):
    """The characters of row `row` that are KNOWN without decoding anything.

    Returns a dict {cell_index: class_index}.  This is the calibration asset:
      * cell 6  == the row index as a hex digit -- across the 16 rows this is
        every one of the 16 hex glyphs, exactly once, labelled, for free;
      * cell 7  == '0'  (a page is 0x100 aligned, so the low nibble is 0);
      * cells 8,9 and the inter-byte gaps are spaces;
      * cells 33 and 67 are hyphens.
    Cells 0..5 are the same six characters on every row but their identity is
    not known a priori -- pass `addr_prefix` (a 6-char string) to add them.
    """
    known = {6: HEXCHARS.index("0123456789ABCDEF"[row]), 7: 0}
    for c in BLANK_CELLS:
        known[c] = CLS_SPACE
    for c in HYPHEN_CELLS:
        known[c] = CLS_HYPHEN
    if addr_prefix:
        for i, ch in enumerate(addr_prefix[:6]):
            known[i] = CLASSES.index(ch)
    return known
