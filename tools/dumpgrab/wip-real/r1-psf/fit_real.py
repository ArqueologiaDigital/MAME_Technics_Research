#!/usr/bin/env python3
"""r1-psf items (a) and (b): locate the MEMORY DUMP grid in a REAL composite
capture at sub-pixel precision, and MEASURE the point-spread function of the
capture chain from the address column.

    python3 fit_real.py FRAME.png [--json fit.json]

No oracle is used anywhere in the fit.

Stages
  0  panel rectangle (sub-pixel), then the row pitch from the 15 inter-row
     GUTTERS -- the most reliable measurement in the frame, because vertical
     resolution is set by the scanline count while horizontal resolution is set
     by luma bandwidth;
  1  the address prefix, by coordinate descent on a WHOLE-BLOCK least-squares
     residual (not per-cell template matching: at this blur a glyph bleeds two
     to three native pixels into both neighbours, so the eight address digits
     are one joint measurement), alternating with an affine refit;
  2+ decode the hex area, declare the decode "known", refit the affine on all
     16x57 cells, re-decode, until the text stops changing;
  3  non-parametric PSF, solved in the forward direction in capture space.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import numpy as np
from PIL import Image

import fitcore as FC
import realgeom as RG
from realgeom import Affine, NativeGrid, load_font


# --------------------------------------------------------------------------- #
# stage 0
# --------------------------------------------------------------------------- #
def _half_crossing(prof, lo, hi, rising):
    seg = prof[lo:hi].astype(np.float64)
    k = max(len(seg) // 5, 2)
    dark, brt = (np.median(seg[:k]), np.median(seg[-k:])) if rising else \
                (np.median(seg[-k:]), np.median(seg[:k]))
    half = 0.5 * (dark + brt)
    idx = np.arange(lo, hi)
    rng = range(1, len(seg)) if rising else range(len(seg) - 1, 0, -1)
    for i in rng:
        a, b = seg[i - 1], seg[i]
        if (a < half <= b) if rising else (b < half <= a):
            return float(idx[i - 1] + (half - a) / (b - a))
    return float("nan")


def _longest_run(mask):
    best, s, out = 0, None, (0, 0)
    for i, v in enumerate(list(mask) + [False]):
        if v and s is None:
            s = i
        elif not v and s is not None:
            if i - s > best:
                best, out = i - s, (s, i - 1)
            s = None
    return out


def find_panel(rgb):
    """(left, top, right, bottom) capture-space edges of the bright dump panel.

    The dump panel is the only large LOW-SATURATION bright rectangle on the LCD:
    the title bar is blue, the button strip dark blue, the legend band fully
    saturated aqua/yellow/lime/fuchsia.  The brightness threshold is derived
    from the frame's own dark/bright percentiles -- the real capture's paper
    sits at grey 103 and its glyph cores at 41, so an absolute threshold tuned
    on the emulator's 128/0 does not survive.  Each edge is then refined to
    sub-pixel on the half-amplitude crossing of a profile averaged along it,
    which averages the glyph ink away.

    The bottom edge returned is the TOP OF THE LEGEND COLOUR BAND (native
    y = 199), not the bottom of the panel: the band is saturated, so the mask
    stops there, and in luma there is no falling edge at the panel bottom at all
    because aqua/yellow/lime are bright.  RG.PANEL uses the same convention.
    """
    g = rgb.mean(axis=2)
    sat = rgb.max(axis=2) - rgb.min(axis=2)
    dark = float(np.percentile(g, 5))
    brt = float(np.percentile(g, 99.5))
    m = (sat < 0.20 * (brt - dark) + 8) & (g > dark + 0.25 * (brt - dark))
    rf = m.mean(axis=1)
    t0, b0 = _longest_run(rf > 0.5 * rf.max())
    cf = m[t0:b0 + 1].mean(axis=0)
    l0, r0 = _longest_run(cf > 0.5 * cf.max())
    h, w = g.shape
    band_v = g[t0 + int(0.05 * (b0 - t0)):t0 + int(0.60 * (b0 - t0)), :].mean(axis=0)
    band_h = g[:, l0 + int(0.05 * (r0 - l0)):l0 + int(0.95 * (r0 - l0))].mean(axis=1)
    return (_half_crossing(band_v, max(l0 - 14, 0), l0 + 14, True),
            _half_crossing(band_h, max(t0 - 14, 0), t0 + 14, True),
            _half_crossing(band_v, r0 - 14, min(r0 + 14, w), False),
            float(b0 + 1))


def seed_rows(gray, ul, vt, ur, vb):
    """(row_pitch, ay, by, n_gutters_used), measured on the INTER-ROW GUTTERS.

    Each text row is 9 native px of which the last 2 are blank, so the vertical
    profile of horizontal-gradient energy has 15 sharp MINIMA between the 16
    rows.  An impulse comb finds them, each is refined to sub-pixel by a
    parabola, and a robust line through them gives the pitch.

    An inside-band/gap comb was tried first and is BIASED: at this blur the ink
    band is wider than 7/9 of the pitch and the fit came out 2 % low (17.95 px
    instead of 18.33), i.e. 2.3 px of accumulated error by row 15.  Impulses at
    the minima have no such bias.
    """
    y0i = int(vt) + 1
    sub = gray[y0i:int(vb) - 1, int(ul) + 6:int(ur) - 6]
    prof = np.abs(sub[:, 2:] - sub[:, :-2]).sum(axis=1).astype(np.float64)
    n = len(prof)
    xs = np.arange(n, dtype=np.float64)
    NG = 15
    best = None
    for pitch in np.arange(n / 17.5, n / 15.0, 0.005):
        phs = np.arange(0.0, pitch, 0.1)
        pos = phs[:, None] + pitch * np.arange(NG)[None, :]
        ok = pos[:, -1] < n - 1
        pos, ph = pos[ok], phs[ok]
        if len(ph) == 0:
            continue
        v = np.interp(pos, xs, prof).sum(axis=1)
        i = int(np.argmin(v))
        if best is None or v[i] < best[0]:
            best = (float(v[i]), float(pitch), float(ph[i]))
    _, pitch, ph = best
    pts = []
    for r in range(NG):
        i = int(round(ph + pitch * r))
        if i < 3 or i >= n - 3:
            continue
        j = i - 2 + int(np.argmin(prof[i - 2:i + 3]))
        if j < 1 or j >= n - 1:
            continue
        a, b, c = prof[j - 1], prof[j], prof[j + 1]
        den = a - 2 * b + c
        d = (a - c) / (2 * den) if den != 0 else 0.0
        pts.append((r, j + max(min(d, 1.0), -1.0)))
    rs = np.array([p[0] for p in pts], float)
    ys = np.array([p[1] for p in pts], float)
    for _ in range(3):
        A = np.stack([np.ones_like(rs), rs], axis=1)
        sol, *_ = np.linalg.lstsq(A, ys, rcond=None)
        res = ys - A @ sol
        keep = np.abs(res) <= max(3.0 * np.std(res), 0.6)
        if keep.all():
            break
        rs, ys = rs[keep], ys[keep]
    pitch = float(sol[1])
    y_first = float(sol[0]) + y0i
    ay = pitch / RG.CELL_H
    g0 = int(round((((y_first - (vt - ay * 49.0)) / ay) - 63.0) / 9.0))
    by = y_first - ay * (63.0 + 9.0 * g0)
    return pitch, ay, by, len(rs)


# --------------------------------------------------------------------------- #
# stage 1: the address prefix, by whole-block least squares
# --------------------------------------------------------------------------- #
def block_text(prefix):
    txt = [[None] * RG.NHEXCOLS for _ in range(RG.NROWS)]
    for r in range(RG.NROWS):
        for c in range(8):
            txt[r][c] = RG.HEXDIG[r] if c == RG.LADDER_CELL else prefix[c]
    return txt


def read_prefix(gray, font, seed, S=3, sweeps=3, verbose=True):
    grid = NativeGrid(S=S, c0=0, c1=9)
    cells = [(r, c) for r in range(RG.NROWS) for c in range(8)]
    w = FC.cell_mask(grid, cells)
    prefix = list("00000000")
    aff, sx, sy = seed, 1.4, 0.5
    for sweep in range(sweeps):
        warp = grid.warp(gray, aff)          # geometry fixed within a sweep
        ky, kx = RG.gauss1(sy, S), RG.gauss1(sx, S)
        for c in range(8):
            if c == RG.LADDER_CELL:
                continue
            best = None
            for g in RG.HEXDIG:
                trial = list(prefix)
                trial[c] = g
                ink = FC.raster_text(grid, font, block_text(trial))
                v = RG.fit_levels_residual(warp, RG.sepconv(ink, ky, kx), w)[0]
                if best is None or v < best[0]:
                    best = (v, g)
            prefix[c] = best[1]
        # ax is held: 8 cells cannot set the pitch as well as the panel edges can
        aff, sx, sy, val, npix = FC.fit(gray, grid, font, block_text(prefix), aff,
                                        (sx, sy), cells=cells, maxiter=350,
                                        free=(0, 0, 1, 1, 1, 1, 1, 1))
        if verbose:
            print("   sweep %d  prefix %s  rms %.4f  sigma_nat x %.3f y %.3f  "
                  "pitch %.4f/%.4f" % (sweep, "".join(prefix), val, sx, sy,
                                       aff.ax * RG.CELL_W, aff.ay * RG.CELL_H))
    # per-cell evidence at the final geometry
    warp = grid.warp(gray, aff)
    ky, kx = RG.gauss1(sy, S), RG.gauss1(sx, S)
    evidence = []
    for c in range(8):
        if c == RG.LADDER_CELL:
            evidence.append(None)
            continue
        sc = []
        for g in RG.HEXDIG:
            trial = list(prefix)
            trial[c] = g
            ink = FC.raster_text(grid, font, block_text(trial))
            sc.append((RG.fit_levels_residual(warp, RG.sepconv(ink, ky, kx), w)[0], g))
        sc.sort()
        evidence.append(sc)
    return "".join(prefix), aff, sx, sy, evidence


# --------------------------------------------------------------------------- #
# stage 3: non-parametric PSF
# --------------------------------------------------------------------------- #
def fit_kernel(gray, aff, font, text, kh=13, kw=21, F=3, lam=2e-3):
    """Least squares for the PSF on the capture grid.

    The sharp native raster is supersampled onto a capture-space fine grid at F
    samples per capture pixel -- so the native pixel footprint is exact rather
    than assumed -- and the kernel K on that fine grid is solved so that
    box_downsample(K ** sharp) * q + p best matches the observed pixels, over
    cells whose characters AND whose neighbours are known.  `lam` is a Laplacian
    smoothness penalty.
    """
    xs = [RG.CELL_X0, RG.CELL_X0 + RG.CELL_W * RG.NHEXCOLS]
    ys = [RG.CELL_Y0, RG.CELL_Y0 + RG.CELL_H * RG.NROWS]
    corn = [aff.forward(x, y) for x in xs for y in ys]
    u0 = int(np.floor(min(c[0] for c in corn))) - 5
    u1 = int(np.ceil(max(c[0] for c in corn))) + 5
    v0 = int(np.floor(min(c[1] for c in corn))) - 5
    v1 = int(np.ceil(max(c[1] for c in corn))) + 5
    H, W = v1 - v0, u1 - u0

    nat = np.zeros((RG.NAT_H, RG.NAT_W), np.float32)
    kn = np.zeros((RG.NAT_H, RG.NAT_W), np.float32)
    keep = set(FC.scored_cells(text))
    for r, row in enumerate(text):
        for c, ch in enumerate(row):
            if ch is None:
                continue
            y = RG.CELL_Y0 + RG.CELL_H * r
            x = RG.CELL_X0 + RG.CELL_W * c
            nat[y:y + RG.GLYPH_H, x:x + RG.GLYPH_W] = font[ch]
            if (r, c) in keep:
                kn[y:y + RG.CELL_H, x:x + RG.CELL_W] = 1.0

    uu = u0 + (np.arange(W * F) + 0.5) / F
    vv = v0 + (np.arange(H * F) + 0.5) / F
    U, V = np.meshgrid(uu, vv)
    X, Y = aff.inverse(U, V)
    xi = np.clip(np.floor(X).astype(np.int32), 0, RG.NAT_W - 1)
    yi = np.clip(np.floor(Y).astype(np.int32), 0, RG.NAT_H - 1)
    sharp = nat[yi, xi]
    kmask = kn[yi, xi]

    def down(a):
        return a.reshape(H, F, W, F).mean(axis=(1, 3))

    sel = (down(kmask) > 0.999).ravel()
    obs = gray[v0:v1, u0:u1]
    r0, r1 = (kh - 1) // 2, (kw - 1) // 2
    pad = np.pad(sharp, ((r0, r0), (r1, r1)), mode="edge")
    cols = [down(pad[i:i + H * F, j:j + W * F]).ravel()[sel]
            for i in range(kh) for j in range(kw)]
    A = np.stack(cols + [np.ones(int(sel.sum()))], axis=1)
    b = obs.ravel()[sel].astype(np.float64)
    n = A.shape[1]
    L = np.zeros((kh * kw, n))
    for i in range(kh):
        for j in range(kw):
            k = i * kw + j
            L[k, k] = 4.0
            for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                ii, jj = i + di, j + dj
                if 0 <= ii < kh and 0 <= jj < kw:
                    L[k, ii * kw + jj] = -1.0
    scale = np.sqrt((A * A).sum()) / max(np.sqrt((L * L).sum()), 1e-9)
    sol, *_ = np.linalg.lstsq(np.vstack([A, lam * scale * L]),
                              np.concatenate([b, np.zeros(kh * kw)]), rcond=None)
    K = sol[:kh * kw].reshape(kh, kw)
    pred = A @ sol
    rms = float(np.sqrt(((b - pred) ** 2).mean()))
    sd = float(np.sqrt(((b - b.mean()) ** 2).mean()))
    return K, F, rms, sd, int(sel.sum()), float(sol[kh * kw])


def _fwhm(p, t):
    p = np.asarray(p, float)
    p = p / p.max()
    idx = np.where(p >= 0.5)[0]
    if len(idx) == 0:
        return 0.0
    lo, hi = idx[0], idx[-1]
    a = (t[lo] if lo == 0 else
         t[lo - 1] + (0.5 - p[lo - 1]) * (t[lo] - t[lo - 1]) / (p[lo] - p[lo - 1] + 1e-12))
    c = (t[hi] if hi == len(p) - 1 else
         t[hi] + (p[hi] - 0.5) * (t[hi + 1] - t[hi]) / (p[hi] - p[hi + 1] + 1e-12))
    return float(c - a)


def kernel_stats(K, F, ax, ay):
    Kn = K / K.sum()
    kh, kw = Kn.shape
    yy = (np.arange(kh) - (kh - 1) / 2.0) / F
    xx = (np.arange(kw) - (kw - 1) / 2.0) / F
    px, py = Kn.sum(axis=0), Kn.sum(axis=1)
    mx = float((px * xx).sum()); my = float((py * yy).sum())
    sx = float(np.sqrt(max((px * (xx - mx) ** 2).sum(), 0.0)))
    sy = float(np.sqrt(max((py * (yy - my) ** 2).sum(), 0.0)))
    return {
        "sigma_x_capture_px": sx, "sigma_y_capture_px": sy,
        "fwhm_x_capture_px": _fwhm(px, xx), "fwhm_y_capture_px": _fwhm(py, yy),
        "sigma_x_native_px": sx / ax, "sigma_y_native_px": sy / ay,
        "fwhm_x_native_px": _fwhm(px, xx) / ax, "fwhm_y_native_px": _fwhm(py, yy) / ay,
        "anisotropy_sigma_native": (sx / ax) / max(sy / ay, 1e-9),
        "centroid_x_capture_px": mx, "centroid_y_capture_px": my,
        "profile_x": [float(v) for v in px], "profile_y": [float(v) for v in py],
        "taps_per_capture_px": F,
    }


# --------------------------------------------------------------------------- #
def report(tag, aff, sx, sy, val, npix):
    print("   %-9s ax %.6f shx %+.5f bx %8.3f | ay %.6f shy %+.5f by %8.3f"
          % (tag, aff.ax, aff.shx, aff.bx, aff.ay, aff.shy, aff.by))
    print("             char pitch %.4f px  row pitch %.4f px  sigma_nat x %.3f y %.3f"
          "  rms %.3f  (%d px)" % (aff.ax * RG.CELL_W, aff.ay * RG.CELL_H, sx, sy,
                                   val, npix))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frame")
    ap.add_argument("--font", default=RG.FONT_PATH)
    ap.add_argument("--json", default="fit_real.json")
    ap.add_argument("--S", type=int, default=3)
    ap.add_argument("--rounds", type=int, default=3)
    args = ap.parse_args()
    t0 = time.time()

    img = np.asarray(Image.open(args.frame).convert("RGB")).astype(np.float32)
    gray = img.mean(axis=2)
    font = load_font(args.font)

    ul, vt, ur, vb = find_panel(img)
    ax0 = (ur - ul) / (RG.PANEL[2] - RG.PANEL[0])
    rp, ay0, by0, ngut = seed_rows(gray, ul, vt, ur, vb)
    seed = Affine(ax0, 0.0, ul - ax0 * RG.PANEL[0], ay0, 0.0, by0)
    print("frame %s  %dx%d" % (args.frame, gray.shape[1], gray.shape[0]))
    print("STAGE 0  panel edges  L %.2f  T %.2f  R %.2f  B %.2f  (capture px)"
          % (ul, vt, ur, vb))
    print("         gutter comb: row pitch %.4f px from %d gutters" % (rp, ngut))
    print("         seed char pitch %.4f px  row pitch %.4f px  bx %.3f by %.3f"
          % (seed.ax * 6, seed.ay * 9, seed.bx, seed.by))

    print("STAGE 1  address prefix by whole-block least squares (no oracle)")
    prefix, aff, sx, sy, evid = read_prefix(gray, font, seed, S=args.S)
    base = prefix[:6] + "00"
    for c in range(8):
        if evid[c] is None:
            print("         cell %d = the row ladder 0..F" % c)
        else:
            b = evid[c]
            print("         cell %d -> '%s' rms %.4f | runners-up %s"
                  % (c, b[0][1], b[0][0],
                     " ".join("'%s' %.4f" % (g, v) for v, g in b[1:4])))
    tm = FC.cell_templates(font, sx, sy)
    ladder_ok = sum(1 for r in range(RG.NROWS)
                    if FC.classify(FC.cut_cell(gray, aff, r, RG.LADDER_CELL),
                                   tm, RG.HEXDIG)[0] == RG.HEXDIG[r])
    print("         BASE ADDRESS 0x%s      ladder correct in %d/16 rows"
          % (base, ladder_ok))
    report("addrblk", aff, sx, sy, float("nan"), 0)

    # ---- stage 1b: full-row structure fit ---------------------------------- #
    # The layout's 105 blank separator cells and the '-' at cell 33 span the WHOLE
    # row, which is the only leverage in the frame that can pin the character
    # pitch to better than a tenth of a pixel.  Data cells are modelled by the
    # mean glyph so their bleed into the separators is not mistaken for paper.
    grid = NativeGrid(S=args.S)
    fill = FC.mean_glyph(font)
    font_q = dict(font); font_q["?"] = fill
    txt_q = [[None] * RG.NHEXCOLS for _ in range(RG.NROWS)]
    for r in range(RG.NROWS):
        for c in range(RG.NHEXCOLS):
            txt_q[r][c] = "?"
        for c, ch in enumerate("%08X" % (int(base, 16) + 16 * r)):
            txt_q[r][c] = ch
        for c in RG.SPACE_CELLS:
            txt_q[r][c] = " "
        txt_q[r][RG.DASH_CELL] = "-"
    aff, sx, sy, val, npix = FC.fit(gray, grid, font_q, txt_q, aff, (sx, sy),
                                    maxiter=500)
    print("STAGE 1b  full-row structure fit (separators + address, data = mean glyph)")
    report("struct", aff, sx, sy, val, npix)

    prev, hist = None, []
    for it in range(args.rounds):
        text, ncc, marg = FC.decode_page(gray, aff, font, sx, sy, use_context=False)
        for r in range(RG.NROWS):
            for c, ch in enumerate("%08X" % (int(base, 16) + 16 * r)):
                text[r][c] = ch
        flat = "".join("".join(x or "?" for x in row) for row in text)
        changed = -1 if prev is None else sum(1 for a, b in zip(flat, prev) if a != b)
        aff, sx, sy, val, npix = FC.fit(gray, grid, font, text, aff, (sx, sy), maxiter=400)
        print("STAGE 2.%d  full-page self-consistent refit (%d cells changed)"
              % (it, changed))
        report("full", aff, sx, sy, val, npix)
        hist.append({"changed": changed, "rms": val,
                     "char_pitch": aff.ax * RG.CELL_W, "row_pitch": aff.ay * RG.CELL_H,
                     "sigma_x_native": sx, "sigma_y_native": sy})
        prev = flat
        if changed == 0:
            break

    text, ncc, marg = FC.decode_page(gray, aff, font, sx, sy, use_context=False)
    for r in range(RG.NROWS):
        for c, ch in enumerate("%08X" % (int(base, 16) + 16 * r)):
            text[r][c] = ch
    data = FC.text_to_bytes(text)
    hexcells = RG.HEX_HI + [c + 1 for c in RG.HEX_HI]

    print("\nDECODED PAGE (plain per-cell template match; no ASCII, no colour)")
    for r in range(RG.NROWS):
        print("   %08X  %s" % (int(base, 16) + 16 * r,
                               " ".join("%02X" % data[16 * r + i] for i in range(16))))
    print("   hex-glyph NCC: mean %.4f  min %.4f   margin: mean %.4f  min %.4f"
          % (ncc[:, hexcells].mean(), ncc[:, hexcells].min(),
             marg[:, hexcells].mean(), marg[:, hexcells].min()))

    K, F, rms, sd, npx, off = fit_kernel(gray, aff, font, text)
    st = kernel_stats(K, F, aff.ax, aff.ay)
    print("\nSTAGE 3  NON-PARAMETRIC PSF (13x21 taps at %d samples/capture px)" % F)
    print("   fitted on %d capture px; residual rms %.3f of signal sd %.3f"
          " -> %.1f%% unexplained" % (npx, rms, sd, 100.0 * rms / sd))
    print("   sigma x %.3f y %.3f capture px  |  x %.3f y %.3f NATIVE px"
          % (st["sigma_x_capture_px"], st["sigma_y_capture_px"],
             st["sigma_x_native_px"], st["sigma_y_native_px"]))
    print("   FWHM  x %.3f y %.3f capture px  |  x %.3f y %.3f NATIVE px"
          % (st["fwhm_x_capture_px"], st["fwhm_y_capture_px"],
             st["fwhm_x_native_px"], st["fwhm_y_native_px"]))
    print("   anisotropy sigma_x/sigma_y in native px: %.2f" % st["anisotropy_sigma_native"])
    print("   horizontal marginal: %s" % " ".join("%.4f" % v for v in st["profile_x"]))
    print("   vertical   marginal: %s" % " ".join("%.4f" % v for v in st["profile_y"]))

    out = {
        "frame": args.frame,
        "panel_edges_capture_px": [ul, vt, ur, vb],
        "affine_native_to_capture": dict(zip("ax shx bx ay shy by".split(),
                                             [float(v) for v in aff.to_vec()])),
        "char_pitch_capture_px": aff.ax * RG.CELL_W,
        "row_pitch_capture_px": aff.ay * RG.CELL_H,
        "gaussian_psf_native_px": {"sigma_x": sx, "sigma_y": sy},
        "base_address": base,
        "address_prefix_evidence": [None if e is None else
                                    [[g, v] for v, g in e[:5]] for e in evid],
        "ladder_ok_rows": ladder_ok,
        "rounds": hist,
        "decoded_hex": [" ".join("%02X" % data[16 * r + i] for i in range(16))
                        for r in range(16)],
        "decoded_bytes_hex": data.hex(),
        "ncc_mean": float(ncc[:, hexcells].mean()),
        "ncc_min": float(ncc[:, hexcells].min()),
        "margin_mean": float(marg[:, hexcells].mean()),
        "kernel": [[float(v) for v in row] for row in K],
        "psf": st,
        "kernel_fit": {"rms": rms, "signal_sd": sd, "pixels": npx},
        "seconds": time.time() - t0,
    }
    json.dump(out, open(args.json, "w"), indent=1)
    print("\nwrote %s   (%.0f s)" % (args.json, time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
