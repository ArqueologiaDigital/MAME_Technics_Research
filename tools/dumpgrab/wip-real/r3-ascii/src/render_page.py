#!/usr/bin/env python3
"""Render a whole page through the forward model and stack it against the real
capture.  This is the model-adequacy check: if the synthetic panel does not
look like the captured panel, no classifier built on the model can work.

    render_page.py FRAME.png --font F.npz --bytes GT.bin --grid RES.json --out X.png
"""
from __future__ import annotations

import argparse, json
import numpy as np
from PIL import Image

from kn7000ascii.decode import Font
from kn7000ascii.forward import box_weights
from kn7000ascii.geometry_ascii import ROW, Grid

HEXC = "0123456789ABCDEF"


def page_native(font: Font, base: int, data: bytes) -> np.ndarray:
    """Native-resolution ink canvas of the 16x76 text block (144 x 456)."""
    H, W = 9 * 16, 6 * ROW.ncols
    c = np.zeros((H, W), np.float64)

    def put(r, i, bmp):
        y = 9 * r; x = 6 * i
        c[y:y + 7, x:x + 5] = bmp

    hx = font.hexmap
    for r in range(16):
        a = "%08X" % (base + 16 * r)
        for i, ch in enumerate(a):
            put(r, ROW.addr_idx[i], hx[ch])
        for k in range(16):
            b = data[r * 16 + k]
            hi, lo = ROW.byte_idx[k]
            put(r, hi, hx[HEXC[b >> 4]]); put(r, lo, hx[HEXC[b & 15]])
            put(r, ROW.ascii_idx[k], font.charmap[b].astype(np.float64))
        put(r, ROW.hex_dash_idx, hx["-"])
        put(r, ROW.ascii_sep_idx, hx["-"])
    return c


def render(canvas, grid: Grid, sigma_x, sigma_y, W, H):
    sx = grid.px / 6.0
    sy = grid.py / 9.0
    u = np.arange(W, dtype=np.float64) + 0.5
    v = np.arange(H, dtype=np.float64) + 0.5
    Wx = box_weights(canvas.shape[1], grid.x0, sx, sigma_x, u)
    Wy = box_weights(canvas.shape[0], grid.y0, sy, sigma_y, v)
    return Wy @ canvas @ Wx.T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frame"); ap.add_argument("--font", required=True)
    ap.add_argument("--bytes", required=True); ap.add_argument("--grid", required=True)
    ap.add_argument("--base", default="48000000")
    ap.add_argument("--out", required=True)
    ap.add_argument("--crop", default=None, help="x0,x1,y0,y1")
    a = ap.parse_args()

    font = Font.load(a.font)
    data = open(a.bytes, "rb").read()[:256]
    res = json.load(open(a.grid))
    gd = res["grid"]
    g = Grid(gd["x0"], gd["px"], gd["y0"], gd["py"], 5.0, 7.0)
    sx, sy = res["sigma_x"], res["sigma_y"]

    rgb = np.asarray(Image.open(a.frame).convert("RGB")).astype(np.float64)
    lum = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    obs = 255.0 - lum
    H, W = obs.shape

    can = page_native(font, int(a.base, 16), data)
    mod = render(can, g, sx, sy, W, H)

    if a.crop:
        x0, x1, y0, y1 = [int(t) for t in a.crop.split(",")]
    else:
        x0 = int(g.x0) - 8; x1 = int(g.x0 + g.px * ROW.ncols) + 8
        y0 = int(g.y0) - 6; y1 = int(g.y0 + g.py * 16) + 6
    O = obs[y0:y1, x0:x1]; M = mod[y0:y1, x0:x1]
    O = (O - O.min()) / max(float(np.ptp(O)), 1e-6)
    M = (M - M.min()) / max(float(np.ptp(M)), 1e-6)
    stack = np.concatenate([O, np.ones((4, O.shape[1])) * 0.5, M], axis=0)
    Image.fromarray((stack * 255).astype(np.uint8)).resize(
        (stack.shape[1] * 2, stack.shape[0] * 2), Image.NEAREST).save(a.out)
    print("wrote", a.out, "obs on top, model below")
    # correlation over the text block
    print("whole-block NCC obs vs model: %.4f"
          % float(np.corrcoef(O.ravel(), M.ravel())[0, 1]))


if __name__ == "__main__":
    main()
