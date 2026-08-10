#!/usr/bin/env python3
"""Extract the EXACT native 5x7 font bitmaps of the KN7000 MEMORY DUMP viewer.

Answers r1-psf item (d) with a measurement, not an assertion.  The templates the
PSF study and any future decoder use are not a guess at "some 5x7 font": they are
the instrument's own glyphs, cut out of pixel-exact emulator frames.

Method (deliberately UNSUPERVISED, then verified against the ROM):
  1. cut every 5x7 character cell of the hex area out of N clean emulator frames,
     keeping only cells whose pixels are exclusively black ink or panel grey;
  2. histogram the distinct bitmaps.  A mid-repaint frame tears *inside* a glyph,
     so hundreds of hybrid bitmaps appear -- but they are rare.  The 18 clean
     glyph classes dominate by two orders of magnitude and separate cleanly.
  3. label the 18 by rendering them, then VERIFY: re-decode complete settled
     frames with the resulting font and require 100% agreement with the ROM.

Native geometry (doc/GEOMETRY.txt, re-verified here):
    first char cell (x, y) = (90, 55); char pitch 6; row pitch 9; glyph 5x7 at
    the top-left of the cell; ink is pure black on a 128-grey panel.

Output: font_native.json  {glyph: [7 strings of 5 chars, '#'/'.']}
"""
import glob
import json
import os
import sys
from collections import Counter

import numpy as np
from PIL import Image

X0, Y0, CW, RP, GW, GH = 90, 55, 6, 9, 5, 7
NROWS, NCOLS = 16, 57

FRAMES = "/tmp/dg_cap1/frames/*.png"
MANIFEST = "/tmp/dg_cap1/manifest.json"
ROMS = {
    0x48400000: "/home/fsanches/compartilhado/kn7000-emulator/roms/kn7000/kn7000_program.rom",
    0x48000000: "/home/fsanches/compartilhado/kn7000-emulator/roms/kn7000/kn7000_table.rom",
}

# The 18 glyphs, written out as read off the histogram in step 2.  Every one of
# these strings is reproduced bit-for-bit by the extraction below; the script
# fails loudly if the image ever disagrees.
EXPECTED = {
    "0": ".###.|#...#|#..##|#.#.#|##..#|#...#|.###.",   # slashed zero
    "1": "..#..|.##..|..#..|..#..|..#..|..#..|.###.",
    "2": ".###.|#...#|....#|...#.|..#..|.#...|#####",
    "3": ".###.|#...#|....#|.###.|....#|#...#|.###.",
    "4": "...#.|..##.|.#.#.|#..#.|#####|...#.|...#.",
    "5": "#####|#....|####.|....#|....#|#...#|.###.",
    "6": ".###.|#....|####.|#...#|#...#|#...#|.###.",
    "7": "#####|....#|....#|...#.|..#..|..#..|..#..",
    "8": ".###.|#...#|#...#|.###.|#...#|#...#|.###.",
    "9": ".###.|#...#|#...#|#...#|.####|....#|.###.",
    "A": ".###.|#...#|#...#|#####|#...#|#...#|#...#",
    "B": "####.|#...#|#...#|####.|#...#|#...#|####.",
    "C": ".###.|#...#|#....|#....|#....|#...#|.###.",
    "D": "####.|#...#|#...#|#...#|#...#|#...#|####.",
    "E": "#####|#....|#....|####.|#....|#....|#####",
    "F": "#####|#....|#....|####.|#....|#....|#....",
    " ": ".....|.....|.....|.....|.....|.....|.....",
    "-": ".....|.....|.....|#####|.....|.....|.....",
}


def bm_str(bm):
    return "|".join("".join("#" if v else "." for v in row) for row in bm)


def rom_page(addr):
    for base, path in ROMS.items():
        if base <= addr < base + os.path.getsize(path):
            with open(path, "rb") as f:
                f.seek(addr - base)
                return f.read(256)
    return None


def page_text(addr, page):
    """The 16x57 characters the viewer prints for this page (hex area only)."""
    out = []
    for r in range(NROWS):
        t = "%08X" % (addr + 16 * r) + "  "
        for k in range(16):
            t += "%02X" % page[16 * r + k]
            if k != 15:
                t += "-" if k == 7 else " "
        out.append(t[:NCOLS])
    return out


def cells(a):
    """(16,57,7,5) uint8 ink masks, plus a (16,57) bool 'plain cell' mask."""
    s = a.astype(np.int32).sum(axis=2)
    ink = np.zeros((NROWS, NCOLS, GH, GW), np.uint8)
    plain = np.zeros((NROWS, NCOLS), bool)
    for r in range(NROWS):
        for c in range(NCOLS):
            pt = s[Y0 + RP * r:Y0 + RP * r + GH, X0 + CW * c:X0 + CW * c + GW]
            i = pt < 100
            plain[r, c] = bool(np.all(i | (pt == 384)))
            ink[r, c] = i
    return ink, plain


def main():
    frames = sorted(glob.glob(FRAMES))
    if not frames:
        print("no frames at %s" % FRAMES)
        return 2

    # ---- step 1+2: unsupervised histogram --------------------------------- #
    hist = Counter()
    for fp in frames[:120]:
        a = np.asarray(Image.open(fp).convert("RGB"))
        ink, plain = cells(a)
        for r in range(NROWS):
            for c in range(NCOLS):
                if plain[r, c]:
                    hist[ink[r, c].tobytes()] += 1
    top = hist.most_common(18)
    tail = sum(v for _, v in hist.most_common()[18:])
    print("distinct 5x7 bitmaps seen : %d   (the tail is mid-repaint tearing)" % len(hist))
    print("top-18 share of all cells : %.4f%%   tail %d cells"
          % (100.0 * sum(v for _, v in top) / sum(hist.values()), tail))
    print("count gap 18th vs 19th    : %d vs %d  (%.1fx)"
          % (top[-1][1], hist.most_common()[18][1],
             top[-1][1] / max(hist.most_common()[18][1], 1)))

    seen = {bm_str(np.frombuffer(k, np.uint8).reshape(GH, GW)) for k, _ in top}
    exp = set(EXPECTED.values())
    if seen != exp:
        print("MISMATCH: histogram top-18 is not the expected glyph set")
        for s in sorted(seen - exp):
            print("  unexpected: %s" % s)
        for s in sorted(exp - seen):
            print("  missing   : %s" % s)
        return 1
    print("top-18 == the 18 labelled glyphs : YES")

    font = {ch: s.split("|") for ch, s in EXPECTED.items()}
    lut = {s: ch for ch, s in EXPECTED.items()}

    # ---- step 3: verify by decoding settled frames against the ROM -------- #
    man = json.load(open(MANIFEST))
    fa = {}
    for p in man["pages"]:
        for s in p["snaps"]:
            fa[s] = int(p["addr"], 16)
    tested = ok_cells = bad_cells = settled = 0
    for fp in frames:
        idx = int(os.path.basename(fp)[:4])
        addr = fa.get(idx)
        if addr is None:
            continue
        a = np.asarray(Image.open(fp).convert("RGB"))
        ink, plain = cells(a)
        # a settled frame: every plain cell is one of the 18 glyphs
        txt = [["?"] * NCOLS for _ in range(NROWS)]
        clean = True
        for r in range(NROWS):
            for c in range(NCOLS):
                if not plain[r, c]:
                    txt[r][c] = None
                    continue
                ch = lut.get(bm_str(ink[r, c]))
                if ch is None:
                    clean = False
                txt[r][c] = ch
        if not clean:
            continue
        # its own address ladder must be self-consistent
        addrs = ["".join(txt[r][0:8]) for r in range(NROWS)]
        try:
            base = int(addrs[0], 16)
        except ValueError:
            continue
        if any(int(addrs[r], 16) != base + 16 * r for r in range(NROWS)):
            continue
        settled += 1
        page = rom_page(base)
        if page is None:
            continue
        want = page_text(base, page)
        tested += 1
        for r in range(NROWS):
            for c in range(NCOLS):
                if txt[r][c] is None:
                    continue
                if txt[r][c] == want[r][c]:
                    ok_cells += 1
                else:
                    bad_cells += 1
        if tested >= 120:
            break

    print("settled frames decoded    : %d   (ROM-covered: %d)" % (settled, tested))
    print("character cells verified  : %d   wrong: %d   accuracy %.6f%%"
          % (ok_cells + bad_cells, bad_cells,
             100.0 * ok_cells / max(ok_cells + bad_cells, 1)))

    json.dump(font, open("font_native.json", "w"), indent=1, sort_keys=True)
    print("wrote font_native.json")
    for ch in "0123456789ABCDEF -":
        print("  '%s'  %s" % (ch, EXPECTED[ch]))
    return 0 if bad_cells == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
