#!/usr/bin/env python3
"""r1-psf item (c): how much information about a hex glyph actually survives the
measured capture chain?

This is the CEILING calculation.  It is deliberately independent of any decoder:
it asks, given (i) the exact native 5x7 glyph bitmaps, (ii) the point-spread
function measured from this frame's own address column, (iii) the capture's
sampling grid and sub-pixel phase, and (iv) the pixel noise measured in this
frame, how far apart the 16 classes are.

Metric.  Two glyphs that produce observed patches b_i, b_j in additive Gaussian
noise of standard deviation s are separated by

        d_ij = || b_i - b_j || / s          (a discriminability, in noise units)

and an ideal observer choosing between just those two errs with probability
Q(d_ij / 2).  d < 2 means worse than 16 % error on that pair alone; d > 8 means
the pair is, for practical purposes, never confused.  Because the character
pitch is not an integer number of capture pixels, the sub-pixel phase of a cell
varies across a row, so every distance is evaluated over a grid of phases and
reported as the WORST case (that is the one that bites) alongside the mean.

Noise s is measured, not assumed: see measure_noise().
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np
from PIL import Image

import realgeom as RG
from realgeom import Affine, load_font


# --------------------------------------------------------------------------- #
def measure_noise(gray, aff, halfwin=6):
    """Pixel noise sd of the capture, measured on GUARANTEED-BLANK panel paper.

    Between the dump panel's inner border and the first character cell there is
    a 4-px native margin, and there are 2 blank native rows between every pair of
    text rows.  Those areas contain no ink by construction, so anything that
    varies there is noise plus whatever slow shading the capture chain adds.  A
    local median is subtracted first so shading is not counted as noise.
    """
    samples = []
    # left margin (native x 86..89) and right margin (x .. panel edge) over the
    # full height of the text block
    for x0, x1 in ((86.5, 89.5), (RG.CELL_X0 + RG.CELL_W * 74 + 1.5,
                                  RG.CELL_X0 + RG.CELL_W * 75 + 3.5)):
        xs = np.arange(x0, x1, 0.5)
        ys = np.arange(RG.CELL_Y0, RG.CELL_Y0 + RG.CELL_H * RG.NROWS, 0.5)
        X, Y = np.meshgrid(xs, ys)
        U, V = aff.forward(X, Y)
        samples.append(RG.bilinear(gray, U, V))
    # the 2 blank native rows under every text row
    for r in range(RG.NROWS):
        ys = np.arange(RG.CELL_Y0 + RG.CELL_H * r + 7.3, RG.CELL_Y0 + RG.CELL_H * r + 8.8, 0.5)
        xs = np.arange(RG.CELL_X0, RG.CELL_X0 + RG.CELL_W * RG.NHEXCOLS, 0.5)
        X, Y = np.meshgrid(xs, ys)
        U, V = aff.forward(X, Y)
        samples.append(RG.bilinear(gray, U, V))
    sds = []
    for s in samples:
        # remove slow shading with a 1-D moving median along the long axis
        a = s.astype(np.float64)
        k = 9
        pad = np.pad(a, ((0, 0), (k // 2, k // 2)), mode="edge")
        med = np.stack([np.median(pad[:, i:i + k], axis=1) for i in range(a.shape[1])], axis=1)
        sds.append(float(np.std(a - med)))
    # robust: take the median of the per-region sds
    return float(np.median(sds)), [float(v) for v in sds]


# --------------------------------------------------------------------------- #
def observed_patch(font, ch, aff, K, F, phase=(0.0, 0.0), win=(2, 2), context=None):
    """The capture pixels a glyph produces, at a given sub-pixel phase.

    Everything happens in capture space so the sampling grid is the real one:
    the sharp native raster is supersampled at F per capture pixel, convolved
    with the measured kernel, box-downsampled, and a window around the cell is
    returned.
    """
    ax, ay = aff.ax, aff.ay
    cw, chh = RG.CELL_W * ax, RG.CELL_H * ay          # cell size in capture px
    padx, pady = win
    W = int(np.ceil(cw)) + 2 * padx
    H = int(np.ceil(chh)) + 2 * pady
    # sharp glyph on the fine capture grid; native pixel k spans [k, k+1)*a
    uu = (np.arange(W * F) + 0.5) / F - padx + phase[0]
    vv = (np.arange(H * F) + 0.5) / F - pady + phase[1]
    U, V = np.meshgrid(uu, vv)
    Xn = U / ax                     # native x within the cell
    Yn = V / ay
    sharp = np.zeros_like(U, dtype=np.float32)

    def stamp(cc, dx_cells):
        if cc is None or cc == " ":
            return
        g = font[cc]
        xi = np.floor(Xn - dx_cells * RG.CELL_W).astype(np.int32)
        yi = np.floor(Yn).astype(np.int32)
        ok = (xi >= 0) & (xi < RG.GLYPH_W) & (yi >= 0) & (yi < RG.GLYPH_H)
        vals = np.zeros_like(sharp)
        vals[ok] = g[yi[ok], xi[ok]]
        np.maximum(sharp, vals, out=sharp)

    stamp(ch, 0)
    if context:
        stamp(context[0], -1)
        stamp(context[1], 1)
    r0, r1 = (K.shape[0] - 1) // 2, (K.shape[1] - 1) // 2
    pad = np.pad(sharp, ((r0, r0), (r1, r1)), mode="edge")
    out = np.zeros_like(sharp)
    for i in range(K.shape[0]):
        for j in range(K.shape[1]):
            k = K[i, j]
            if k != 0.0:
                out += k * pad[i:i + sharp.shape[0], j:j + sharp.shape[1]]
    return out.reshape(H, F, W, F).mean(axis=(1, 3))


def qfunc(x):
    """Upper tail of the standard normal, via erfc (numpy has no scipy here)."""
    return 0.5 * np.vectorize(np.math.erfc)(x / np.sqrt(2.0)) if False else \
        0.5 * _erfc_vec(x / np.sqrt(2.0))


def _erfc_vec(x):
    x = np.asarray(x, float)
    # Abramowitz & Stegun 7.1.26-style rational approximation, |eps| < 1.5e-7
    z = np.abs(x)
    t = 1.0 / (1.0 + 0.5 * z)
    y = t * np.exp(-z * z - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (
        0.09678418 + t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (
            1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))))
    return np.where(x >= 0, y, 2.0 - y)


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", default="fit_real.json")
    ap.add_argument("--frame", default="/home/fsanches/compartilhado/KN7000/photos/1st-frame-grabbed.png")
    ap.add_argument("--font", default=RG.FONT_PATH)
    ap.add_argument("--nphase", type=int, default=4)
    ap.add_argument("--json", default="confusion.json")
    ap.add_argument("--context", action="store_true",
                    help="also report distances with random hex neighbours present")
    args = ap.parse_args()

    fit = json.load(open(args.fit))
    aff = Affine(**fit["affine_native_to_capture"])
    K = np.array(fit["kernel"], float)
    F = fit["psf"]["taps_per_capture_px"]
    font = load_font(args.font)
    gray = np.asarray(Image.open(args.frame).convert("RGB")).astype(np.float32).mean(axis=2)

    noise, per_region = measure_noise(gray, aff)
    print("MEASURED PIXEL NOISE")
    print("  blank-paper sd per region : %s" % " ".join("%.2f" % v for v in per_region))
    print("  adopted noise sd          : %.3f grey levels" % noise)
    print("  kernel-fit residual rms   : %.3f grey levels  (noise + PSF model error)"
          % fit["kernel_fit"]["rms"])

    # ink/paper contrast on this frame, from the fitted levels
    ink_contrast = fit.get("contrast", None)
    if ink_contrast is None:
        # recover it: paper is the panel median, ink is the darkest glyph core
        pass

    cls = RG.HEXDIG
    phases = [(i / args.nphase, j / args.nphase)
              for i in range(args.nphase) for j in range(args.nphase)]

    # contrast scale: the model patches are in 0..1 ink units; multiply by the
    # measured ink-to-paper amplitude to get grey levels
    amp = fit.get("ink_amplitude_grey", None)
    if amp is None:
        amp = estimate_amplitude(gray, aff, font, fit)
    print("  ink->paper amplitude      : %.2f grey levels" % amp)
    print("  => contrast-to-noise      : %.1f" % (amp / noise))

    D = np.zeros((16, 16, len(phases)))
    for pi, ph in enumerate(phases):
        pats = np.stack([observed_patch(font, c, aff, K, F, phase=ph).ravel() for c in cls])
        pats *= amp
        for i in range(16):
            for j in range(16):
                D[i, j, pi] = np.linalg.norm(pats[i] - pats[j])
    Dmin = D.min(axis=2) / noise
    Dmean = D.mean(axis=2) / noise
    np.fill_diagonal(Dmin, np.inf)
    np.fill_diagonal(Dmean, np.inf)

    print("\nPAIRWISE DISCRIMINABILITY d = ||b_i - b_j|| / noise_sd   (WORST sub-pixel phase)")
    print("      " + "".join("%6s" % c for c in cls))
    for i, c in enumerate(cls):
        print("   %s " % c + "".join("%6.1f" % (Dmin[i, j] if np.isfinite(Dmin[i, j]) else 0)
                                     for j in range(16)))

    pairs = [(Dmin[i, j], cls[i], cls[j]) for i in range(16) for j in range(i + 1, 16)]
    pairs.sort()
    print("\nTIGHTEST 12 PAIRS  (worst phase; P(err) is an ideal 2-way observer)")
    for d, a, b in pairs[:12]:
        print("   %s/%s   d = %6.2f   P(confuse) = %.2e" % (a, b, d, qfunc(d / 2.0)))
    print("WIDEST 3 PAIRS")
    for d, a, b in pairs[-3:]:
        print("   %s/%s   d = %6.2f" % (a, b, d))

    # per-class error, union bound over the 15 alternatives
    perr = np.array([float(qfunc(Dmin[i][np.isfinite(Dmin[i])] / 2.0).sum()) for i in range(16)])
    perr = np.clip(perr, 0, 1)
    print("\nPREDICTED IDEAL-OBSERVER ERROR (union bound over 15 alternatives, worst phase)")
    for i, c in enumerate(cls):
        print("   '%s'  P(err) = %.3e" % (c, perr[i]))
    pg = float(perr.mean())
    print("   mean per-glyph error   %.4e" % pg)
    print("   -> per-byte accuracy   %.6f %%" % (100.0 * (1 - pg) ** 2))
    print("   -> expected wrong bytes in a 256-byte page: %.3f" % (256 * (1 - (1 - pg) ** 2)))

    indist = [(a, b, d) for d, a, b in pairs if d < 2.0]
    print("\nTHEORETICALLY INDISTINGUISHABLE PAIRS (d < 2, i.e. >15.9%% error): %s"
          % (indist or "NONE"))
    marg = [(a, b, d) for d, a, b in pairs if 2.0 <= d < 6.0]
    print("MARGINAL PAIRS (2 <= d < 6, i.e. 0.1%%..16%% error)          : %s"
          % (marg or "NONE"))

    out = {
        "noise_sd_grey": noise, "noise_per_region": per_region,
        "ink_amplitude_grey": amp, "contrast_to_noise": amp / noise,
        "classes": list(cls),
        "d_worst_phase": Dmin.tolist(),
        "d_mean_phase": Dmean.tolist(),
        "tightest_pairs": [[a, b, float(d)] for d, a, b in pairs[:12]],
        "per_class_perr": perr.tolist(),
        "mean_glyph_perr": pg,
        "predicted_byte_accuracy_pct": 100.0 * (1 - pg) ** 2,
        "indistinguishable_d_lt_2": [[a, b, float(d)] for a, b, d in indist],
        "marginal_2_to_6": [[a, b, float(d)] for a, b, d in marg],
    }
    json.dump(out, open(args.json, "w"), indent=1)
    print("\nwrote %s" % args.json)
    return 0


def estimate_amplitude(gray, aff, font, fit):
    """paper - ink, in grey levels, from the frame itself.

    Uses the address block, whose characters are known: the model's fully-inked
    and fully-blank fine samples are compared with the observation.
    """
    base = fit["base_address"]
    S = 3
    grid = RG.NativeGrid(S=S)
    text = [[None] * RG.NHEXCOLS for _ in range(RG.NROWS)]
    for r in range(RG.NROWS):
        for c, ch in enumerate("%08X" % (int(base, 16) + 16 * r)):
            text[r][c] = ch
    ink = np.zeros(grid.shape, np.float32)
    kn = np.zeros(grid.shape, bool)
    for r, row in enumerate(text):
        for c, ch in enumerate(row):
            if ch is None:
                continue
            gy = (RG.CELL_Y0 + RG.CELL_H * r - grid.y0) * S
            gx = (RG.CELL_X0 + RG.CELL_W * c - grid.x0) * S
            ink[gy:gy + RG.GLYPH_H * S, gx:gx + RG.GLYPH_W * S] = \
                np.kron(font[ch], np.ones((S, S), np.float32))
            kn[gy:gy + RG.CELL_H * S, gx:gx + RG.CELL_W * S] = True
    sx = fit["gaussian_psf_native_px"]["sigma_x"]
    sy = fit["gaussian_psf_native_px"]["sigma_y"]
    model = RG.sepconv(ink, RG.gauss1(sy, S), RG.gauss1(sx, S))
    warp = grid.warp(gray, aff)
    rms, p, q = RG.fit_levels_residual(warp, model, kn)
    return abs(q)


if __name__ == "__main__":
    sys.exit(main())
