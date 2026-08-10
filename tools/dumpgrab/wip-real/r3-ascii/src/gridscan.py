#!/usr/bin/env python3
"""Diagnostic: how does model fidelity vary with the grid?  Labels come from a
reference page, so this measures the CEILING, not an achievable accuracy."""
from __future__ import annotations

import argparse, json
import numpy as np
from PIL import Image
from copy import deepcopy

from kn7000ascii.decode import Font
from kn7000ascii.geometry_ascii import ROW, Grid
from kn7000ascii.page import Page
from kn7000ascii.psf_empirical import SeparablePSF
from ceiling import full_est, luma


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frame"); ap.add_argument("--font", required=True)
    ap.add_argument("--grid", required=True); ap.add_argument("--gt", required=True)
    ap.add_argument("--psf", default=None); ap.add_argument("--base", default="48000000")
    ap.add_argument("--refit", type=int, default=0)
    a = ap.parse_args()

    font = Font.load(a.font)
    data = open(a.gt, "rb").read()[:256]
    rgb = np.asarray(Image.open(a.frame).convert("RGB")).astype(np.float64)
    img = 255.0 - luma(rgb)
    res = json.load(open(a.grid)); gd = res["grid"]
    pj = json.load(open(a.psf))["psf"] if a.psf else res["psf"]
    base = int(a.base, 16)

    allc = ([(r, ROW.addr_idx[i]) for r in range(16) for i in range(8)]
            + [(r, c) for r in range(16) for k in range(16) for c in ROW.byte_idx[k]]
            + [(r, ROW.ascii_idx[k]) for r in range(16) for k in range(16)])

    def make(x0, px, y0, py, rowx=None):
        g = Grid(x0, px, y0, py, 5.0, 7.0, list(rowx or []))
        p = Page(img, g, font, SeparablePSF.from_dict(pj))
        return p

    print("scan x0 / px  (mean cell NCC with true labels)")
    best = None
    for px in np.arange(9.58, 9.72, 0.01):
        row = []
        for x0 in np.arange(155.0, 159.6, 0.4):
            p = make(x0, px, gd["y0"], gd["py"])
            est = full_est(p, base, data)
            if a.refit:
                p.fit_psf(est, allc, iters=a.refit)
            s, _ = p.psf_residual(est, allc)
            row.append(s)
            if best is None or s > best[0]:
                best = (s, x0, px)
        print("  px=%.3f " % px + " ".join("%.3f" % v for v in row))
    print("best ncc %.4f at x0=%.2f px=%.3f" % best)

    s0, x0, px = best
    print("scan y0 / py")
    best2 = None
    for py in np.arange(18.28, 18.48, 0.02):
        row = []
        for y0 in np.arange(124.0, 127.2, 0.3):
            p = make(x0, px, y0, py)
            est = full_est(p, base, data)
            s, _ = p.psf_residual(est, allc)
            row.append(s)
            if best2 is None or s > best2[0]:
                best2 = (s, y0, py)
        print("  py=%.3f " % py + " ".join("%.3f" % v for v in row))
    print("best ncc %.4f at y0=%.2f py=%.3f" % best2)


if __name__ == "__main__":
    main()
