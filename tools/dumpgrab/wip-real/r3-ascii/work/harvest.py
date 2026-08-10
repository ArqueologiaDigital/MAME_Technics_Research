#!/usr/bin/env python3
"""Harvest labelled ASCII-pane glyph samples from emulator frames.

Labels come from the emulator's own program ROM (the oracle) at the page base
address that the frame prints for itself.  Only frames whose 16-row address
ladder is fully self-consistent are used, so a mis-framed grid cannot mislabel
a glyph.
"""
import os, sys, glob, json
import numpy as np
from PIL import Image

sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
from kn7000dump import PageExtractor, layout as L
from kn7000dump.extract import _cut_patches
from kn7000dump.geometry import texture_map, ink_map
from kn7000dump.imageutil import as_rgb, shear_rows

ORACLE = "/home/fsanches/compartilhado/kn7000-emulator/roms/kn7000/kn7000_program.rom"
ROM_BASE = 0x48400000

rom = open(ORACLE, "rb").read()


def oracle_page(base):
    off = base - ROM_BASE
    if off < 0 or off + 256 > len(rom):
        return None
    return rom[off:off + 256]


def main():
    frames = sorted(glob.glob(sys.argv[1]))
    if len(sys.argv) > 2:
        frames = frames[::int(sys.argv[2])]
    ex = PageExtractor()
    # widen the layout so the ASCII pane is definitely covered: try gap2 in 1..4
    samples = {}     # byte value -> list of patches
    seen_pages = set()
    nframes = 0
    GH, GW = 24, 16          # bigger patches than the hex atlas: richer glyphs
    for fp in frames:
        rgb = as_rgb(Image.open(fp))
        res = ex.extract(rgb)
        if res.base_address is None or sum(res.row_addr_ok) != 16:
            continue
        page = oracle_page(res.base_address)
        if page is None:
            continue
        if res.base_address in seen_pages and len(seen_pages) > 4:
            # keep a couple of repeats for variance, then stop hoarding
            pass
        seen_pages.add(res.base_address)
        # verify hex decode matches oracle -- guarantees the grid is right
        if bytes(res.data) != page:
            continue
        nframes += 1
        grid = res.grid
        ink = getattr(grid, "ink", None)
        if ink is None:
            ink = shear_rows(ink_map(rgb, ry=max(2, int(round(grid.row_pitch * 1.3))),
                                     rx=max(2, int(round(grid.row_pitch * 3.0)))), grid.slope)
        tex = texture_map(ink)
        lay = grid.lay
        cells = [(r, c) for r in range(16) for c in lay.ascii_idx]
        p = _cut_patches(ink, grid, cells, GH, GW, tex=tex, recenter=False)
        for i, (r, c) in enumerate(cells):
            k = lay.ascii_idx.index(c)
            b = page[r * 16 + k]
            samples.setdefault(b, []).append(p[i])
        if nframes >= int(os.environ.get("MAXF", "60")):
            break
    print("frames used %d  pages %d  distinct byte values %d"
          % (nframes, len(seen_pages), len(samples)))
    np.savez_compressed(sys.argv[3] if len(sys.argv) > 3 else "ascii_samples.npz",
                        **{"b%02X" % k: np.stack(v) for k, v in samples.items()})
    print("counts:", {("%02X" % k): len(v) for k, v in sorted(samples.items())})


if __name__ == "__main__":
    main()
