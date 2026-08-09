#!/usr/bin/env python3
"""verify_alignment.py -- prove that manifest relframe N == movie frame N == frames/NNNN.png.

The manifest is only useful as ground truth if the integrator knows which movie frame each row
refers to. This measures that instead of assuming it: it hashes every PNG and every AVI frame
and reports the constant offset (and whether it is in fact constant over the whole capture).

Deps: numpy, pillow.

    python3 verify_alignment.py --dir runs/fast
"""
import argparse
import csv
import hashlib
import os
import sys

import numpy as np
from PIL import Image

from avi_frames import AviReader


def sha(a):
    return hashlib.sha1(np.ascontiguousarray(a).tobytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    a = ap.parse_args()

    rows = []
    with open(os.path.join(a.dir, "manifest.csv")) as fh:
        for r in csv.DictReader(fh):
            rows.append((int(r["relframe"]), int(r["snap"]), int(r["addr"], 16)))

    avi = os.path.join(a.dir, "movie.avi")
    if not os.path.exists(avi):
        print(f"no {avi} -- run the capture with --movie avi", file=sys.stderr)
        return 2
    r = AviReader(avi)
    print(f"movie      : {r.width}x{r.height} {r.bitcount}bpp, {len(r)} frames, "
          f"fps={r.fps:.4f}, {os.path.getsize(avi)} bytes "
          f"({os.path.getsize(avi) / max(len(r), 1):.0f} B/frame)")
    print(f"manifest   : {len(rows)} rows, "
          f"{sum(1 for _, s, _ in rows if s >= 0)} of them with a PNG")

    avihash = [sha(r[i]) for i in range(len(r))]
    pnghash = {}
    for rel, snap, _ in rows:
        if snap < 0:
            continue
        p = os.path.join(a.dir, "frames", f"{snap:04d}.png")
        if os.path.exists(p):
            pnghash[rel] = sha(np.asarray(Image.open(p).convert("RGB")))

    # find the offset that maximises agreement
    best, bestoff = -1, None
    for off in range(-8, 9):
        hits = sum(1 for rel, h in pnghash.items()
                   if 0 <= rel + off < len(avihash) and avihash[rel + off] == h)
        if hits > best:
            best, bestoff = hits, off
    print(f"alignment  : movie_index = relframe + {bestoff}  "
          f"({best}/{len(pnghash)} PNGs match that movie frame exactly "
          f"= {100.0 * best / max(len(pnghash), 1):.2f} %)")
    if best < len(pnghash):
        bad = [rel for rel, h in pnghash.items()
               if not (0 <= rel + bestoff < len(avihash) and avihash[rel + bestoff] == h)]
        print(f"             mismatching relframes: {bad[:20]}{' ...' if len(bad) > 20 else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
