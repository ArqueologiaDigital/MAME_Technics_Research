#!/usr/bin/env python3
"""kn6xxx_font_placeholder.py -- build a PLACEHOLDER table/font ROM for the KN6000 or KN6500
that holds nothing but the KN7000's bitmap fonts, laid out where the KN6xxx firmware looks.

WHY. The KN6000/KN6500 table/font mask ROMs (IC13/IC14) have never been dumped, and without
them the firmware draws no text at all: its font-table initialiser copies five pointers out
of the table-ROM header (offset 0x200..0x213) and the text drawer follows the fourth one, the
font-descriptor table (notes/kn6000-kn6500-boot.md). The KN6000/KN6500/KN7000 text drawers are
the same code, so the KN7000's fonts -- whose table ROM IS dumped -- can stand in. This is
GUESSWORK: the real KN6xxx glyphs may differ. The image exists only so the menus can be read
while exploring the driver, until IC13/IC14 are read. Everything it renders is the KN7000's
font, and must never be cited as KN6xxx data (the driver loads it as BAD_DUMP).

WHAT IT CONTAINS, at the KN6xxx table-ROM offsets (everything else is 0xFF, as blank flash):
  0x000..0x1FF  0xFF. The KN7000's own identity header here makes the KN6000 boot derail
                to a black screen (measured, notes/kn6000-kn6500-boot.md), so it is left out.
  0x200..0x213  the five header pointers: bitmap table, frame table, icon table, font table, 0.
  FONT_OFF..    the KN7000 font-descriptor table (0x14-byte records) and every glyph and kern
                table it points to, copied byte for byte from the KN7000 table ROM at the same
                offsets, with every pointer relocated to the target model's table-ROM base.
  EMPTY_OFF..   (default) an all-zero block that the bitmap, frame and icon pointers share:
                every bitmap/frame/icon descriptor reads as {0, 0, NULL}, so those draw nothing
                instead of drawing the KN7000's artwork at the KN6xxx's indices.

The table ROM sits at a different CPU address on the two models -- 0x48000000 on the KN6000,
0x40010000 on the KN6500, whose otherwise identical font initialiser (0x48420433) reads its
header from 0x40010200 -- so the pointers differ and each model gets its own image (--model).

Font descriptor (KN7000 DrawString_Impl, annotations/gfx_draw.ann in kn7000_disassembly):
  +0 u16 width (0 = proportional), +2 u16 height, +4 s16 descent, +6 u16 byte columns per glyph,
  +8 u32 glyphs, +0xC u32 kern table (0 = fixed width; else 224 x {u8 width, u8, u16 offset}),
  +0x10 u32 double-byte (Shift-JIS) table (0 = none). Glyphs cover characters 0x20..0xFF, 1 bpp,
  column-major. The table ends with an all-zero record.

usage:
  kn6xxx_font_placeholder.py --model kn6000 --table kn7000_table.rom --out kn6000_table_fontph.rom
  kn6xxx_font_placeholder.py --model kn6500 --even kn7000_table_even.rom --odd kn7000_table_odd.rom \\
                             --out kn6500_table_fontph.rom
options: --size BYTES (default 0x40000), --report (print the font table and exit codes only)
"""
import argparse
import hashlib
import struct
import sys
import zlib

KN7000_BASE = 0x48000000
MODEL_BASE = {"kn6000": 0x48000000, "kn6500": 0x40010000}
HEADER_OFF = 0x200
NCHARS = 0xE0                      # characters 0x20..0xFF
EMPTY_OFF = 0x1000                 # the shared all-zero bitmap/frame/icon table
EMPTY_LEN = 0x10000                # 8192 eight-byte descriptors


def interleave(even, odd):
    """ROM_LOAD32_WORD pair -> linear image: each dword is even[2] then odd[2]."""
    assert len(even) == len(odd)
    out = bytearray(len(even) * 2)
    for i in range(0, len(even), 2):
        out[2 * i:2 * i + 2] = even[i:i + 2]
        out[2 * i + 2:2 * i + 4] = odd[i:i + 2]
    return bytes(out)


def read_fonts(t):
    """-> (font table offset, [descriptor tuples], end offset of the whole font block)."""
    bmp, frm, icn, fnt, fifth = struct.unpack_from("<5I", t, HEADER_OFF)
    off = fnt - KN7000_BASE
    fonts, end = [], off
    while True:
        rec = struct.unpack_from("<HHhHIII", t, off + 0x14 * len(fonts))
        w, h, desc, cols, glyphs, kern, sjis = rec
        if w == 0 and h == 0 and glyphs == 0:
            break
        if sjis:
            sys.exit("font %d has a double-byte table; this generator does not copy those" % len(fonts))
        if kern:                   # proportional: glyph data runs up to its kern table
            end = max(end, kern - KN7000_BASE + 4 * NCHARS)
        else:
            end = max(end, glyphs - KN7000_BASE + NCHARS * cols * h)
        fonts.append(rec)
    end = max(end, off + 0x14 * (len(fonts) + 1))
    return (bmp, frm, icn, fnt, fifth), off, fonts, end


def build(t, model, size):
    base = MODEL_BASE[model]
    reloc = lambda p: p - KN7000_BASE + base if p else 0
    hdr, off, fonts, end = read_fonts(t)
    if end > size:
        sys.exit("font block ends at 0x%X, past the 0x%X-byte image" % (end, size))
    if EMPTY_OFF + EMPTY_LEN > off:
        sys.exit("empty table would overlap the font block at 0x%X" % off)
    img = bytearray(b"\xff" * size)
    img[off:end] = t[off:end]                              # descriptors, glyphs, kern tables
    for i, (w, h, desc, cols, glyphs, kern, sjis) in enumerate(fonts):
        struct.pack_into("<HHhHIII", img, off + 0x14 * i, w, h, desc, cols,
                         reloc(glyphs), reloc(kern), reloc(sjis))
    img[EMPTY_OFF:EMPTY_OFF + EMPTY_LEN] = bytes(EMPTY_LEN)
    empty = base + EMPTY_OFF
    struct.pack_into("<5I", img, HEADER_OFF, empty, empty, empty, base + off, 0)
    return bytes(img), hdr, off, fonts, end


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", choices=sorted(MODEL_BASE), required=True)
    ap.add_argument("--table", help="linear KN7000 table ROM (kn7000_table.rom)")
    ap.add_argument("--even", help="kn7000_table_even.rom (with --odd, instead of --table)")
    ap.add_argument("--odd")
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=lambda s: int(s, 0), default=0x40000)
    a = ap.parse_args()
    if a.table:
        t = open(a.table, "rb").read()
    elif a.even and a.odd:
        t = interleave(open(a.even, "rb").read(), open(a.odd, "rb").read())
    else:
        ap.error("give --table, or --even and --odd")
    img, hdr, off, fonts, end = build(t, a.model, a.size)
    open(a.out, "wb").write(img)
    base = MODEL_BASE[a.model]
    print("KN7000 header @0x200: " + " ".join("%08X" % x for x in hdr))
    print("%s: %d fonts, block 0x%X..0x%X copied, base 0x%08X" % (a.model, len(fonts), off, end, base))
    for i, (w, h, desc, cols, glyphs, kern, _s) in enumerate(fonts):
        print("  font %2d: %s %2dx%-2d descent %d, %d column(s), glyphs 0x%08X%s"
              % (i, "prop " if kern else "fixed", w, h, desc, cols, glyphs - KN7000_BASE + base,
                 ", kern 0x%08X" % (kern - KN7000_BASE + base) if kern else ""))
    print("%s: 0x%X bytes, CRC32 %08x, SHA1 %s" % (a.out, len(img), zlib.crc32(img) & 0xFFFFFFFF,
                                                hashlib.sha1(img).hexdigest()))


if __name__ == "__main__":
    main()
