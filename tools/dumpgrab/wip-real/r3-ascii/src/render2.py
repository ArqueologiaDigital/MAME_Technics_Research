#!/usr/bin/env python3
"""Stack observation against the empirical-PSF model of a KNOWN page."""
from __future__ import annotations

import argparse, json
import numpy as np
from PIL import Image

from kn7000ascii.decode import Font
from kn7000ascii.geometry_ascii import ROW, Grid
from kn7000ascii.page import Page, HEXC
from kn7000ascii.psf_empirical import SeparablePSF
from ceiling import full_est, luma


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frame"); ap.add_argument("--font", required=True)
    ap.add_argument("--grid", required=True); ap.add_argument("--gt", required=True)
    ap.add_argument("--psf", default=None)
    ap.add_argument("--base", default="48000000")
    ap.add_argument("--out", required=True)
    ap.add_argument("--rows", default="0-15")
    ap.add_argument("--cells", default="0-40")
    ap.add_argument("--zoom", type=int, default=3)
    a = ap.parse_args()

    font = Font.load(a.font)
    data = open(a.gt, "rb").read()[:256]
    rgb = np.asarray(Image.open(a.frame).convert("RGB")).astype(np.float64)
    img = 255.0 - luma(rgb)
    res = json.load(open(a.grid))
    gd = res["grid"]
    g = Grid(gd["x0"], gd["px"], gd["y0"], gd["py"], 5.0, 7.0,
             list(gd.get("row_x0") or []))
    pj = json.load(open(a.psf))["psf"] if a.psf else res["psf"]
    page = Page(img, g, font, SeparablePSF.from_dict(pj), mx=0.0, my=0.0)
    est = full_est(page, int(a.base, 16), data)

    r0, r1 = [int(t) for t in a.rows.split("-")]
    c0, c1 = [int(t) for t in a.cells.split("-")]
    tiles_o, tiles_m = [], []
    for r in range(r0, r1 + 1):
        ro, rm = [], []
        for i in range(c0, c1 + 1):
            gm = page.geom(r, i)
            if gm is None:
                continue
            o = gm[0]
            m = page.model(r, i, est.get((r, i), np.zeros((7, 5))),
                           page.ctx_of(est, r, i))
            ro.append(o); rm.append(m)
        w = min(x.shape[1] for x in ro); h = min(x.shape[0] for x in ro)
        tiles_o.append(np.concatenate([x[:h, :w] for x in ro], axis=1))
        tiles_m.append(np.concatenate([x[:h, :w] for x in rm], axis=1))
    W = min(t.shape[1] for t in tiles_o)
    O = np.concatenate([t[:, :W] for t in tiles_o], axis=0)
    M = np.concatenate([t[:, :W] for t in tiles_m], axis=0)
    print("per-pixel correlation over the shown area: %.4f"
          % float(np.corrcoef(O.ravel(), M.ravel())[0, 1]))

    def nz(x):
        return (x - x.min()) / max(float(np.ptp(x)), 1e-6)
    st = np.concatenate([nz(O), np.ones((3, W)), nz(M)], axis=0)
    Image.fromarray((st * 255).astype(np.uint8)).resize(
        (W * a.zoom, st.shape[0] * a.zoom), Image.NEAREST).save(a.out)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
