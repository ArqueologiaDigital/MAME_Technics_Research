#!/usr/bin/env python3
"""Decode one frame through both channels and score the fusion.

    run_frame.py FRAME.png --font FONT.npz [--x0 .. --px .. --y0 .. --py ..]
                 [--gt-photo F.bin] [--gt-rom F.bin] [--json OUT.json]

Every number it prints is a count against a file on disk; nothing is asserted.
"""
from __future__ import annotations

import argparse, json, sys
import numpy as np
from PIL import Image

from kn7000ascii.decode import (Font, HexChannel, AsciiChannel, hex_byte_logpost,
                                fuse, argmax_bytes, colour_hits, calibrate_temperature,
                                LEGEND_DEFAULT, HEXC)
from kn7000ascii.geometry_ascii import ROW
from kn7000ascii.gridfit import autofit
from kn7000ascii.psf import Calibrator


def luma(a):
    return 0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("frame")
    ap.add_argument("--font", required=True)
    ap.add_argument("--x0", type=float, default=None)
    ap.add_argument("--px", type=float, default=None)
    ap.add_argument("--y0", type=float, default=None)
    ap.add_argument("--py", type=float, default=None)
    ap.add_argument("--native", action="store_true",
                    help="frame is a 640x240 MAME native snapshot")
    ap.add_argument("--gt", action="append", default=[],
                    help="NAME=PATH of a 256-byte reference to score against")
    ap.add_argument("--json", default=None)
    ap.add_argument("--w-asc", type=float, default=1.0)
    ap.add_argument("--passes", type=int, default=2)
    a = ap.parse_args(argv)

    rgb = np.asarray(Image.open(a.frame).convert("RGB")).astype(np.float64)
    img = 255.0 - luma(rgb)          # higher = more ink
    font = Font.load(a.font)

    if a.native:
        x0, px, y0, py = 90.0, 6.0, 55.0, 9.0
    else:
        x0, px, y0, py = a.x0, a.px, a.y0, a.py
    print("start grid x0=%.3f px=%.4f y0=%.3f py=%.4f" % (x0, px, y0, py))
    grid, sx, sy, ncc = autofit(img, font, x0, px, y0, py)

    # temperature calibration on the address ladder (oracle free)
    hexch = HexChannel(img, grid, font, sx, sy)
    S, T = hexch.address_scores()
    Temp = calibrate_temperature(S, T)
    print("softmax temperature from the ladder: %.4f  (ladder top-1 %d/%d)"
          % (Temp, int((S.argmax(axis=1) == T).sum()), len(T)))
    hexch.T = Temp
    addr = hexch.address_digits()
    print("address column:", " ".join(addr[:4]), "...", addr[-1])
    ladder_ok = sum(1 for r, s in enumerate(addr)
                    if len(s) == 8 and s[6] == HEXC[r] and s[7] == "0")
    print("ladder self-check: %d/16 rows" % ladder_ok)

    hex_post, hex_raw = hexch.run(passes=a.passes)
    ascch = AsciiChannel(img, grid, font, sx, sy, T=Temp)
    cls_post, asc_raw = ascch.run(passes=a.passes)

    LH = hex_byte_logpost(hex_post)
    LA = ascch.byte_logpost(cls_post)

    # colour channel, measured on BOTH panes
    hexcells = [(r, ROW.byte_idx[k][0]) for r in range(16) for k in range(16)]
    asccells = [(r, ROW.ascii_idx[k]) for r in range(16) for k in range(16)]
    ch = colour_hits(rgb, grid, hexcells)
    ca = colour_hits(rgb, grid, asccells)
    colour = {}
    for (r, i), (name, frac) in list(ch.items()):
        k = [kk for kk in range(16) if ROW.byte_idx[kk][0] == i][0]
        if name in LEGEND_DEFAULT:
            colour[r * 16 + k] = LEGEND_DEFAULT[name]
    for (r, i), (name, frac) in list(ca.items()):
        k = ROW.ascii_idx.index(i)
        if name in LEGEND_DEFAULT:
            colour.setdefault(r * 16 + k, LEGEND_DEFAULT[name])
    print("colour hits: hex pane %d, ascii pane %d, union %d"
          % (len(ch), len(ca), len(colour)))

    P_hex = fuse(LH)
    P_asc = fuse(np.zeros_like(LH), LA)
    P_fus = fuse(LH, LA, w_asc=a.w_asc)
    P_all = fuse(LH, LA, colour=colour, w_asc=a.w_asc)

    out = {"frame": a.frame, "sigma_x": sx, "sigma_y": sy, "ncc": ncc,
           "temperature": Temp, "ladder_ok": ladder_ok,
           "grid": {"x0": grid.x0, "px": grid.px, "y0": grid.y0, "py": grid.py,
                    "row_x0": grid.row_x0},
           "colour_hits": {"hex": len(ch), "ascii": len(ca)},
           "scores": {}}

    refs = {}
    for spec in a.gt:
        name, path = spec.split("=", 1)
        refs[name] = open(path, "rb").read()[:256]

    bh, _ = argmax_bytes(P_hex)
    ba, _ = argmax_bytes(P_asc)
    bf, cf = argmax_bytes(P_fus)
    bc, _ = argmax_bytes(P_all)
    out["bytes"] = {"hex": bh.hex(), "fused": bf.hex(), "fused_colour": bc.hex()}

    for name, ref in refs.items():
        row = {}
        for tag, bb in (("hex_only", bh), ("fused", bf), ("fused_colour", bc)):
            row[tag] = int(sum(1 for i in range(256) if bb[i] == ref[i]))
        # what ASCII alone can say: is the true byte inside the decoded class?
        inclass = 0
        for i in range(256):
            if LA[i, ref[i]] > -50:
                inclass += 1
        row["ascii_class_contains_truth"] = inclass
        # nibble accuracy of hex
        row["hex_hi_nib"] = int(sum(1 for i in range(256) if (bh[i] >> 4) == (ref[i] >> 4)))
        row["hex_lo_nib"] = int(sum(1 for i in range(256) if (bh[i] & 15) == (ref[i] & 15)))
        out["scores"][name] = row
        print("vs %-8s hex %3d/256   fused %3d/256   +colour %3d/256   "
              "ascii-class-contains-truth %3d/256"
              % (name, row["hex_only"], row["fused"], row["fused_colour"], inclass))

    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
    return out


if __name__ == "__main__":
    main()
