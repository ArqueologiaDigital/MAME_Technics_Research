#!/usr/bin/env python3
"""photofit.py -- EXPERIMENTAL character-pitch search for hand-held PHOTOGRAPHS.

STATUS: this does not work well enough to use, and it is shipped because the
measurement it produces is the useful part.  On a real photo of the KN7000 LCD it
recovers about half the bytes of a page; the tool's own self-check correctly refuses
that, so `dumpgrab.py image` on a photo still emits nothing.  Read the numbers at the
bottom of this docstring before spending time here.

WHY PHOTOS FAIL WHILE EMULATOR FRAMES DO NOT
    The grid fitter estimates the character pitch from the periodicity of the ink.  On a
    hand-held photo of a curved, glare-lit LCD the estimate lands a few percent low, and
    a few percent compounds: at 20 px per character and 75 characters per row, 4% is
    three whole characters of drift by the right-hand end of a row.  The row-address
    ladder cannot see this, because the eight address characters sit at the LEFT of the
    row where the drift has not accumulated yet -- so a photo can pass the ladder check
    and still decode the right-hand half of every row as noise.

WHAT THIS SCRIPT DOES ABOUT IT
    It re-decodes the frame over a grid of (pitch scale, x offset) candidates and keeps
    the one that maximises the MEAN GLYPH CONFIDENCE over the data cells -- i.e. it scores
    the geometry on the thing the geometry is for, instead of on a structural ink score
    that is blind to the failure.  ~50 decodes, about 80 s per photo.

MEASURED (2026-08-09, photo_5170298038159870967_y.jpg, whose page 0x48400D00 is inside
kn7000_program.rom so it can be scored):
    plain fit               : mean conf 0.078, 11/16 rows on the ladder, base misread,
                              0 bytes usable
    best of the search      : scale 1.04, dx -0.30 cell -> mean conf 0.509,
                              13/16 rows on the ladder, base 0x48400CD0 (WRONG: the true
                              first row is 0x48400D00), 130/256 bytes correct = 50.8%
    conclusion              : the mean-confidence score does find a far better grid
                              (0.078 -> 0.509 and 0 -> 130 correct bytes), so the search
                              direction is right, but a single global scale cannot absorb
                              the perspective of a hand-held shot.  The missing piece is a
                              four-corner homography on the panel, not a better 1-D search.

    photo_..870968 (page 0x48400C00, a squarer and better-lit shot) is NOT rescued: the
    plain fit already scores mean confidence 0.463 with only 1 of 16 rows on the ladder --
    confident nonsense -- and no candidate in the search beats it.  Two lessons: the
    mean-confidence score is a good tie-breaker but NOT a validity test on its own, and the
    ladder gate is what keeps that frame from emitting 256 bytes of garbage.

The composite-video path does not have this problem: a grabber samples a flat raster on a
fixed axis, and the resampling that costs a photo everything measured harmless there.
"""

from __future__ import annotations

import argparse
import copy
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kn7000dump import PageExtractor, fit_grid  # noqa: E402

DEFAULT_SCALES = [0.94, 0.96, 0.98, 1.00, 1.02, 1.04, 1.06, 1.08, 1.10, 1.12]
DEFAULT_OFFSETS = [-0.6, -0.3, 0.0, 0.3, 0.6]


def rescale(grid, scale: float, dx: float):
    """Scale the character pitch of every row and shift the row origin by dx cells."""
    g = copy.deepcopy(grid)
    for rf in g.rows:
        cw = rf.cw * scale
        rf.x0 = rf.x0 + dx * cw
        rf.cw = cw
    return g


def search(rgb, ex: PageExtractor = None, scales=None, offsets=None, log=None):
    """Return (best_result, best_scale, best_dx, rows) -- rows is the whole score table."""
    ex = ex or PageExtractor()
    g0 = fit_grid(np.asarray(rgb))
    rows = []
    best = None
    for s in (scales or DEFAULT_SCALES):
        for dx in (offsets or DEFAULT_OFFSETS):
            res = ex.extract(rgb, grid=rescale(g0, s, dx))
            score = float(res.conf.mean())
            rec = {"scale": s, "dx": dx, "mean_conf": score,
                   "ladder": int(sum(res.row_addr_ok)),
                   "base": res.base_address}
            rows.append(rec)
            if log:
                log(rec)
            if best is None or score > best[0]:
                best = (score, s, dx, res)
    return best[3], best[1], best[2], rows


def main(argv=None):
    ap = argparse.ArgumentParser("photofit", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photos", nargs="+")
    ap.add_argument("--oracle", action="append", default=[],
                    help="ROM to score the winning grid against (base inferred from the "
                         "file name, as in dumpgrab.py)")
    ap.add_argument("--verbose", action="store_true", help="print every candidate")
    args = ap.parse_args(argv)

    from PIL import Image
    import dumpgrab

    oracles = []
    for base, path in dumpgrab.oracle_specs(args.oracle):
        oracles.append((base, open(path, "rb").read()))

    ex = PageExtractor()
    for path in args.photos:
        rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8)
        t0 = time.time()
        plain = ex.extract(rgb)
        res, s, dx, rows = search(
            rgb, ex, log=(lambda r: print("   scale %.2f dx %+.2f  conf %.3f  ladder %2d"
                                          % (r["scale"], r["dx"], r["mean_conf"],
                                             r["ladder"]))) if args.verbose else None)
        print("== %s   (%d candidates, %.0f s)"
              % (os.path.basename(path), len(rows), time.time() - t0))
        for tag, r in (("plain fit", plain), ("best of search", res)):
            base = r.base_address
            line = ("   %-15s conf %.3f  ladder %2d/16  base %s"
                    % (tag, float(r.conf.mean()), sum(r.row_addr_ok),
                       "None" if base is None else "0x%08X" % base))
            if oracles and base is not None:
                for obase, blob in oracles:
                    off = base - obase
                    if 0 <= off and off + 256 <= len(blob):
                        truth = blob[off:off + 256]
                        ok = sum(1 for i in range(256) if r.data[i] == truth[i])
                        line += "  bytes %d/256 = %.1f%%" % (ok, 100.0 * ok / 256)
                        break
                else:
                    line += "  (base outside every oracle)"
            print(line)
        print("   winning grid: pitch scale %.2f, origin %+0.2f cell" % (s, dx))
        print("   NOTE the tool still refuses this frame: the shipped gate needs 15/16 "
              "rows on the ladder before any byte is emitted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
