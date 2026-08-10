#!/usr/bin/env python3
"""CEILING PROBE -- diagnostic only, uses the reference page as labels.

Question it answers: on this capture, is the limit the MODEL (fixable) or the
PHYSICS (not)?  It fits the empirical PSF on the whole page with every cell
labelled from a reference, then measures how separable the templates are.  If
top-1 is still poor with a perfectly-fitted PSF and perfect neighbour context,
the frame carries less than one glyph's worth of information per cell and no
decoder can read it.

Never use its output as an accuracy claim: it has seen the answer.
"""
from __future__ import annotations

import argparse, json
import numpy as np
from PIL import Image

from kn7000ascii.decode import Font
from kn7000ascii.geometry_ascii import ROW, Grid
from kn7000ascii.page import Page, HEXC, BLANK
from kn7000ascii.psf_empirical import SeparablePSF


def luma(a):
    return 0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]


def full_est(page, base, data):
    hx = page.font.hexmap
    est = page.address_context(base)
    for r in range(16):
        for k in range(16):
            b = data[r * 16 + k]
            hi, lo = ROW.byte_idx[k]
            est[(r, hi)] = hx[HEXC[b >> 4]]
            est[(r, lo)] = hx[HEXC[b & 15]]
            est[(r, ROW.ascii_idx[k])] = page.font.charmap[b].astype(np.float64)
    return est


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frame"); ap.add_argument("--font", required=True)
    ap.add_argument("--grid", required=True); ap.add_argument("--gt", required=True)
    ap.add_argument("--base", default="48000000")
    ap.add_argument("--iters", type=int, default=8)
    ap.add_argument("--out-psf", default=None)
    a = ap.parse_args()

    font = Font.load(a.font)
    data = open(a.gt, "rb").read()[:256]
    rgb = np.asarray(Image.open(a.frame).convert("RGB")).astype(np.float64)
    img = 255.0 - luma(rgb)
    res = json.load(open(a.grid))
    gd = res["grid"]
    g = Grid(gd["x0"], gd["px"], gd["y0"], gd["py"], 5.0, 7.0,
             list(gd.get("row_x0") or []))
    psf = (SeparablePSF.from_dict(res["psf"]) if "psf" in res
           else SeparablePSF.gaussian(res["sigma_x"], res["sigma_y"],
                                      g.px / 6.0, g.py / 9.0))
    page = Page(img, g, font, psf)
    base = int(a.base, 16)
    est = full_est(page, base, data)

    allcells = ([(r, ROW.addr_idx[i]) for r in range(16) for i in range(8)]
                + [(r, c) for r in range(16) for k in range(16) for c in ROW.byte_idx[k]]
                + [(r, ROW.ascii_idx[k]) for r in range(16) for k in range(16)])
    print("residual before refit: ncc %.4f over %d cells" % page.psf_residual(est, allcells))
    page.fit_psf(est, allcells, iters=a.iters)
    print("residual after  refit: ncc %.4f over %d cells" % page.psf_residual(est, allcells))

    digits = np.stack([font.hexmap[c] for c in HEXC])
    proto = font.proto.astype(np.float64)

    def probe(cells, tmpl, truth_of):
        ok1 = ok2 = 0; n = 0; marg = []
        for (r, i) in cells:
            s = page.score_cell(r, i, tmpl, page.ctx_of(est, r, i))
            if s is None:
                continue
            t = truth_of(r, i)
            o = np.argsort(-s)
            n += 1
            ok1 += int(o[0] == t); ok2 += int(t in o[:2])
            marg.append(s[o[0]] - s[o[1]])
        return ok1, ok2, n, float(np.median(marg))

    hexcells = [(r, c) for r in range(16) for k in range(16) for c in ROW.byte_idx[k]]

    def hex_truth(r, i):
        for k, (hi, lo) in enumerate(ROW.byte_idx):
            if i == hi:
                return data[r * 16 + k] >> 4
            if i == lo:
                return data[r * 16 + k] & 15
        raise KeyError

    o1, o2, n, m = probe(hexcells, digits, hex_truth)
    print("HEX  ceiling: top1 %d/%d (%.1f%%)  top2 %d/%d  median margin %.4f"
          % (o1, n, 100.0 * o1 / n, o2, n, m))

    asccells = [(r, ROW.ascii_idx[k]) for r in range(16) for k in range(16)]

    def asc_truth(r, i):
        k = ROW.ascii_idx.index(i)
        return int(font.cls_of[data[r * 16 + k]])

    o1, o2, n, m = probe(asccells, proto, asc_truth)
    print("ASCII ceiling: top1 %d/%d (%.1f%%)  top2 %d/%d  median margin %.4f"
          % (o1, n, 100.0 * o1 / n, o2, n, m))

    addr = [(r, ROW.addr_idx[i]) for r in range(16) for i in range(8)]
    o1, o2, n, m = probe(addr, digits, lambda r, i: HEXC.index(
        ("%08X" % (base + 16 * r))[ROW.addr_idx.index(i)]))
    print("ADDR ceiling: top1 %d/%d  top2 %d/%d  median margin %.4f" % (o1, n, o2, n, m))

    if a.out_psf:
        json.dump({"psf": page.psf.as_dict(), "grid": gd}, open(a.out_psf, "w"), indent=1)


if __name__ == "__main__":
    main()
