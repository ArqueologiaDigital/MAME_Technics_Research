#!/usr/bin/env python3
"""Full pipeline on one frame: grid -> empirical PSF -> three channels -> fusion.

    run2.py FRAME.png --font F.npz [--native | --x0 .. --px .. --y0 .. --py ..]
            [--gt NAME=FILE ...] [--json OUT.json]

The only thing a reference file is ever used for is SCORING at the end.
"""
from __future__ import annotations

import argparse, json, sys
from copy import deepcopy

import numpy as np
from PIL import Image

from kn7000ascii.decode import Font, colour_hits, LEGEND_DEFAULT
from kn7000ascii.geometry_ascii import ROW, Grid
from kn7000ascii.gridfit import autofit
from kn7000ascii.page import Page, HEXC, _softmax
from kn7000ascii.psf_empirical import SeparablePSF
from kn7000ascii import channels as CH


def luma(a):
    return 0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]


def bootstrap_base(page: Page, verbose=True):
    """Read the page base off the screen: cell 6 must be hex(row) and cell 7
    must be '0' (that is how the viewer prints), so cells 0..5 are the only
    unknowns and they are CONSTANT down the column -- 16 votes each."""
    tm = np.stack([page.font.hexmap[c] for c in HEXC])
    est = page.static_context()
    for i in range(6):
        for r in range(16):
            est.setdefault((r, ROW.addr_idx[i]), tm.mean(axis=0))
    digits = []
    for _ in range(3):
        acc = np.zeros((6, 16))
        for i in range(6):
            for r in range(16):
                s = page.score_cell(r, ROW.addr_idx[i], tm,
                                    page.ctx_of(est, r, ROW.addr_idx[i]))
                if s is None:
                    continue
                acc[i] += np.log(np.maximum(_softmax(s, 0.02), 1e-12))
        digits = [HEXC[int(np.argmax(acc[i]))] for i in range(6)]
        for i in range(6):
            for r in range(16):
                est[(r, ROW.addr_idx[i])] = page.font.hexmap[digits[i]]
    base = int("".join(digits) + "00", 16)
    if verbose:
        print("bootstrapped base from the ladder: %08X" % base)
    return base


def ladder_check(page: Page, base):
    """Independent verification: decode all 8 address cells per row freely and
    count the rows that come out equal to base + 0x10*r."""
    tm = np.stack([page.font.hexmap[c] for c in HEXC])
    est = page.address_context(base)
    ok = 0
    got = []
    for r in range(16):
        s = ""
        for i in range(8):
            ci = ROW.addr_idx[i]
            sc = page.score_cell(r, ci, tm, page.ctx_of(est, r, ci))
            s += HEXC[int(np.argmax(sc))] if sc is not None else "?"
        got.append(s)
        if s == "%08X" % (base + 16 * r):
            ok += 1
    return ok, got


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("frame")
    ap.add_argument("--font", required=True)
    ap.add_argument("--native", action="store_true")
    ap.add_argument("--x0", type=float); ap.add_argument("--px", type=float)
    ap.add_argument("--y0", type=float); ap.add_argument("--py", type=float)
    ap.add_argument("--gt", action="append", default=[])
    ap.add_argument("--json", default=None)
    ap.add_argument("--passes", type=int, default=3)
    ap.add_argument("--temp", type=float, default=0.02)
    ap.add_argument("--w-asc", type=float, default=1.0)
    ap.add_argument("--psf-iters", type=int, default=6)
    a = ap.parse_args(argv)

    rgb = np.asarray(Image.open(a.frame).convert("RGB")).astype(np.float64)
    img = 255.0 - luma(rgb)
    font = Font.load(a.font)

    if a.native:
        x0, px, y0, py = 90.0, 6.0, 55.0, 9.0
    else:
        x0, px, y0, py = a.x0, a.px, a.y0, a.py
    grid, sgx, sgy, ncc = autofit(img, font, x0, px, y0, py)
    print("gaussian prefit: sigma=(%.3f, %.3f) ncc=%.4f" % (sgx, sgy, ncc))

    psf0 = SeparablePSF.gaussian(sgx, sgy, grid.px / 6.0, grid.py / 9.0)
    page = Page(img, grid, font, psf0)

    # --- stage 1: PSF from cell 7 only (fully known 3x3 neighbourhood) ----
    est = page.static_context()
    cells7 = [(r, ROW.addr_idx[7]) for r in range(16)]
    r0, n0 = page.psf_residual(est, cells7)
    page.fit_psf(est, cells7, iters=a.psf_iters)
    r1, _ = page.psf_residual(est, cells7)
    print("PSF stage 1 on %d cells: ncc %.4f -> %.4f" % (n0, r0, r1))

    # --- stage 2: base, then refit on the whole address column ------------
    base = bootstrap_base(page)
    est = page.address_context(base)
    addr_cells = [(r, ROW.addr_idx[i]) for r in range(16) for i in range(8)]
    page.fit_psf(est, addr_cells, iters=a.psf_iters)
    r2, n2 = page.psf_residual(est, addr_cells)
    print("PSF stage 2 on %d cells: ncc %.4f" % (n2, r2))
    base2 = bootstrap_base(page, verbose=False)
    if base2 != base:
        print("  base changed after refit: %08X -> %08X" % (base, base2))
        base = base2
        est = page.address_context(base)
    lok, got = ladder_check(page, base)
    print("ladder self-check: %d/16 rows  (row0 %s, row15 %s)" % (lok, got[0], got[15]))

    # --- channels ----------------------------------------------------------
    hpost, hraw, _ = CH.hex_channel(page, base, T=a.temp, passes=a.passes)
    apost, araw, _ = CH.ascii_channel(page, base, T=a.temp, passes=a.passes)
    LH = CH.hex_byte_logpost(hpost)
    LA = CH.ascii_byte_logpost(font, apost)

    # --- colour ------------------------------------------------------------
    hexc = [(r, ROW.byte_idx[k][0]) for r in range(16) for k in range(16)]
    ascc = [(r, ROW.ascii_idx[k]) for r in range(16) for k in range(16)]
    ch_hits = colour_hits(rgb, page.g, hexc)
    ca_hits = colour_hits(rgb, page.g, ascc)
    colour = {}
    for (r, i), (name, _f) in ch_hits.items():
        k = [kk for kk in range(16) if ROW.byte_idx[kk][0] == i][0]
        if name in LEGEND_DEFAULT:
            colour[r * 16 + k] = LEGEND_DEFAULT[name]
    for (r, i), (name, _f) in ca_hits.items():
        k = ROW.ascii_idx.index(i)
        if name in LEGEND_DEFAULT:
            colour.setdefault(r * 16 + k, LEGEND_DEFAULT[name])
    print("colour hits: hex %d  ascii %d  union %d"
          % (len(ch_hits), len(ca_hits), len(colour)))

    def norm(L):
        L = L - L.max(axis=1, keepdims=True)
        P = np.exp(L); P /= P.sum(axis=1, keepdims=True)
        return P

    P_hex = norm(LH)
    P_asc = norm(LA)
    P_fus = norm(LH + a.w_asc * LA)
    P_col = P_fus.copy()
    for idx, val in colour.items():
        P_col[idx] = 0.0; P_col[idx, val] = 1.0

    bh = bytes(P_hex.argmax(axis=1).astype(np.uint8))
    bf = bytes(P_fus.argmax(axis=1).astype(np.uint8))
    bc = bytes(P_col.argmax(axis=1).astype(np.uint8))

    out = {"frame": a.frame, "base": "%08X" % base, "ladder_ok": lok,
           "grid": {"x0": page.g.x0, "px": page.g.px, "y0": page.g.y0,
                    "py": page.g.py, "row_x0": page.g.row_x0},
           "psf": page.psf.as_dict(),
           "gauss_prefit": {"sigma_x": sgx, "sigma_y": sgy, "ncc": ncc},
           "psf_ncc_addr": r2,
           "colour": {"hex": len(ch_hits), "ascii": len(ca_hits)},
           "bytes": {"hex": bh.hex(), "fused": bf.hex(), "fused_colour": bc.hex()},
           "scores": {}}

    for spec in a.gt:
        name, path = spec.split("=", 1)
        ref = open(path, "rb").read()[:256]
        row = {}
        for tag, bb in (("hex_only", bh), ("fused", bf), ("fused_colour", bc)):
            row[tag] = int(sum(1 for i in range(256) if bb[i] == ref[i]))
        # ASCII channel measured on the thing it actually estimates: the CLASS
        cls_top1 = cls_top2 = 0
        for r in range(16):
            for j in range(16):
                pr = apost.get((r, ROW.ascii_idx[j]))
                if pr is None:
                    continue
                tc = int(font.cls_of[ref[r * 16 + j]])
                order = np.argsort(-pr)
                cls_top1 += int(order[0] == tc)
                cls_top2 += int(tc in order[:2])
        row["ascii_class_top1"] = cls_top1
        row["ascii_class_top2"] = cls_top2
        # how much of the byte posterior the ASCII channel alone puts on truth
        row["ascii_mass_on_truth"] = float(np.mean([P_asc[i, ref[i]] for i in range(256)]))
        row["hex_mass_on_truth"] = float(np.mean([P_hex[i, ref[i]] for i in range(256)]))
        row["fused_mass_on_truth"] = float(np.mean([P_fus[i, ref[i]] for i in range(256)]))
        rk = [int(np.sum(P_fus[i] > P_fus[i, ref[i]])) for i in range(256)]
        row["fused_rank_median"] = float(np.median(rk))
        row["fused_top4"] = int(sum(1 for x in rk if x < 4))
        row["hex_hi"] = int(sum(1 for i in range(256) if (bh[i] >> 4) == (ref[i] >> 4)))
        row["hex_lo"] = int(sum(1 for i in range(256) if (bh[i] & 15) == (ref[i] & 15)))
        out["scores"][name] = row
        print("vs %-6s hex %3d  fused %3d  +colour %3d | ascii class top1 %3d "
              "top2 %3d | hex nib hi/lo %3d/%3d | mass hex %.3f asc %.3f fus %.3f"
              % (name, row["hex_only"], row["fused"], row["fused_colour"],
                 row["ascii_class_top1"], row["ascii_class_top2"],
                 row["hex_hi"], row["hex_lo"], row["hex_mass_on_truth"],
                 row["ascii_mass_on_truth"], row["fused_mass_on_truth"]))

    if a.json:
        np.savez_compressed(a.json.replace(".json", "_post.npz"),
                            LH=LH, LA=LA, P_hex=P_hex, P_asc=P_asc, P_fus=P_fus)
        json.dump(out, open(a.json, "w"), indent=1)
    return out


if __name__ == "__main__":
    main()
