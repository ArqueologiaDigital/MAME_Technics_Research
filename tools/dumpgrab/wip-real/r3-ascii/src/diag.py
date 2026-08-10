#!/usr/bin/env python3
"""Diagnostics: where does the decode actually lose?  Uses a reference page to
LABEL cells, never to fit anything."""
from __future__ import annotations

import argparse, json
import numpy as np
from PIL import Image

from kn7000ascii.decode import Font, HexChannel, AsciiChannel, HEXC
from kn7000ascii.forward import CellRenderer
from kn7000ascii.geometry_ascii import ROW, Grid
from kn7000ascii.psf import Calibrator, _ncc


def luma(a):
    return 0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]


def load(frame, gridjson):
    rgb = np.asarray(Image.open(frame).convert("RGB")).astype(np.float64)
    img = 255.0 - luma(rgb)
    res = json.load(open(gridjson))
    gd = res["grid"]
    g = Grid(gd["x0"], gd["px"], gd["y0"], gd["py"], 5.0, 7.0,
             list(gd.get("row_x0") or []))
    return rgb, img, g, res["sigma_x"], res["sigma_y"]


def full_context(font, base, data):
    """native bitmap for every (row, cell) of the page -- the perfect context."""
    hx = font.hexmap
    est = {}
    for r in range(16):
        a = "%08X" % (base + 16 * r)
        for i, ch in enumerate(a):
            est[(r, ROW.addr_idx[i])] = hx[ch]
        for i in ROW.gap1_idx + ROW.gap2_idx:
            est[(r, i)] = np.zeros((7, 5))
        for i in ROW.sep_idx:
            est[(r, i)] = hx["-"] if i == ROW.hex_dash_idx else np.zeros((7, 5))
        est[(r, ROW.ascii_sep_idx)] = hx["-"]
        for k in range(16):
            b = data[r * 16 + k]
            hi, lo = ROW.byte_idx[k]
            est[(r, hi)] = hx[HEXC[b >> 4]]
            est[(r, lo)] = hx[HEXC[b & 15]]
            est[(r, ROW.ascii_idx[k])] = font.charmap[b].astype(np.float64)
    return est


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frame"); ap.add_argument("--font", required=True)
    ap.add_argument("--grid", required=True); ap.add_argument("--gt", required=True)
    ap.add_argument("--base", default="48000000")
    ap.add_argument("--shift-scan", action="store_true")
    a = ap.parse_args()

    font = Font.load(a.font)
    data = open(a.gt, "rb").read()[:256]
    rgb, img, g, sx, sy = load(a.frame, a.grid)
    base = int(a.base, 16)
    print("grid x0=%.3f px=%.4f y0=%.3f py=%.4f sigma=(%.3f,%.3f)"
          % (g.x0, g.px, g.y0, g.py, sx, sy))

    cal = Calibrator(img, g, font.hex_labels, font.hex_bitmaps)
    if a.shift_scan:
        print("cell-shift scan (supervised ncc):")
        from copy import deepcopy
        for k in (-2, -1, 0, 1, 2):
            gg = deepcopy(g)
            gg.row_x0 = [x + k * g.px for x in g.row_x0] if g.row_x0 else []
            gg.x0 = g.x0 + k * g.px
            print("   shift %+d cells -> %.4f" % (k, cal.score(sx, sy, gg)))

    est = full_context(font, base, data)
    ren = CellRenderer(g, sx, sy)
    digits = np.stack([font.hexmap[c] for c in HEXC])

    # --- address cells with perfect context: how separable is the font? ---
    def cellscore(r, i, tmpl):
        u0, u1, v0, v1, _, _ = ren.window(r, i)
        obs = img[v0:v1, u0:u1][ren.core]
        Wx, Wy, _ = ren.weights(r, i)
        ctx = (est.get((r, i - 1)), est.get((r, i + 1)),
               est.get((r - 1, i)), est.get((r + 1, i)))
        m = ren.render(Wx, Wy, ren.canvas(tmpl, *ctx))[ren.core]
        return _ncc(obs, m)

    for tag, cells in (("ADDR", [(r, ROW.addr_idx[i]) for r in range(16) for i in range(8)]),
                       ("HEX ", [(r, c) for r in range(16) for k in range(16)
                                 for c in ROW.byte_idx[k]])):
        ok = 0; tot = 0; margins = []
        for (r, i) in cells:
            truth = est[(r, i)]
            s = np.array([cellscore(r, i, d) for d in digits])
            ti = int(np.argmax([np.array_equal(d, truth) for d in digits]))
            tot += 1
            if int(np.argmax(s)) == ti:
                ok += 1
            srt = np.sort(s)[::-1]
            margins.append(srt[0] - srt[1])
        print("%s with PERFECT context: %d/%d top-1   median margin %.3f"
              % (tag, ok, tot, float(np.median(margins))))

    # --- ASCII cells with perfect context ---
    proto = font.proto.astype(np.float64)
    ok = 0
    for r in range(16):
        for k in range(16):
            i = ROW.ascii_idx[k]
            b = data[r * 16 + k]
            ci = int(font.cls_of[b])
            s = np.array([cellscore(r, i, t) for t in proto])
            if int(np.argmax(s)) == ci:
                ok += 1
    print("ASCII with PERFECT context: %d/256 top-1 class" % ok)


if __name__ == "__main__":
    main()
