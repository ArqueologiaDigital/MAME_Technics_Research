#!/usr/bin/env python3
"""Validate the geometry + PSF machinery end to end on frames whose answer is
known exactly.

A fit that has no ground truth can only be checked for self-consistency, and
self-consistency is exactly what a bootstrapped fit is good at faking.  So: take
a pixel-exact emulator frame whose page contents the ROM already gives us, push
it through the SAME degradation the real capture applies (the affine and the
non-parametric PSF measured from the real frame, plus the measured pixel noise),
and run the whole pipeline on the result.  Everything is then checkable:

  * the recovered affine, against the one used to render -- reported as the
    worst-case character-cell position error in capture pixels, which is the
    number that actually matters for a decoder;
  * the recovered PSF width, against the one used;
  * the base address read off the screen;
  * all 256 bytes, against the ROM.

    python3 validate_synth.py --fit fit_real.json [--n 6]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np
from PIL import Image

import fitcore as FC
import fit_real as FR
import realgeom as RG
from realgeom import Affine, NativeGrid, load_font

ROMS = {
    0x48400000: "/home/fsanches/compartilhado/kn7000-emulator/roms/kn7000/kn7000_program.rom",
    0x48000000: "/home/fsanches/compartilhado/kn7000-emulator/roms/kn7000/kn7000_table.rom",
}


def rom_page(addr):
    for base, path in ROMS.items():
        if base <= addr < base + os.path.getsize(path):
            with open(path, "rb") as f:
                f.seek(addr - base)
                return f.read(256)
    return None


def page_text(addr, page):
    out = []
    for r in range(16):
        t = "%08X" % (addr + 16 * r) + "  "
        for k in range(16):
            t += "%02X" % page[16 * r + k]
            if k != 15:
                t += "-" if k == 7 else " "
        out.append(t[:RG.NHEXCOLS])
    return out


def degrade(native_rgb, aff, K, F, out_shape, noise_sd, rng):
    """Render a native RGB frame into a capture-sized frame through (aff, K)."""
    H, W = out_shape
    uu = (np.arange(W * F) + 0.5) / F
    vv = (np.arange(H * F) + 0.5) / F
    U, V = np.meshgrid(uu, vv)
    X, Y = aff.inverse(U, V)
    inside = (X >= 0) & (X < RG.NAT_W) & (Y >= 0) & (Y < RG.NAT_H)
    xi = np.clip(np.floor(X).astype(np.int32), 0, RG.NAT_W - 1)
    yi = np.clip(np.floor(Y).astype(np.int32), 0, RG.NAT_H - 1)
    r0, r1 = (K.shape[0] - 1) // 2, (K.shape[1] - 1) // 2
    out = np.zeros((H, W, 3), np.float64)
    for ch in range(3):
        fine = native_rgb[:, :, ch][yi, xi].astype(np.float64)
        fine[~inside] = 0.0
        pad = np.pad(fine, ((r0, r0), (r1, r1)), mode="edge")
        acc = np.zeros_like(fine)
        for i in range(K.shape[0]):
            for j in range(K.shape[1]):
                k = K[i, j]
                if k != 0.0:
                    acc += k * pad[i:i + fine.shape[0], j:j + fine.shape[1]]
        out[:, :, ch] = acc.reshape(H, F, W, F).mean(axis=(1, 3))
    out += rng.normal(0.0, noise_sd, out.shape)
    return np.clip(out, 0, 255).astype(np.float32)


def cell_error(a_true, a_est):
    """Worst-case character-cell corner error, in capture px, over the hex area."""
    worst = 0.0
    for r in (0, RG.NROWS):
        for c in (0, RG.NHEXCOLS):
            X = RG.CELL_X0 + RG.CELL_W * c
            Y = RG.CELL_Y0 + RG.CELL_H * r
            u1, v1 = a_true.forward(X, Y)
            u2, v2 = a_est.forward(X, Y)
            worst = max(worst, float(np.hypot(u1 - u2, v1 - v2)))
    return worst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", default="fit_real.json")
    ap.add_argument("--frames", default="/tmp/dg_cap1/frames/*.png")
    ap.add_argument("--manifest", default="/tmp/dg_cap1/manifest.json")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--noise", type=float, default=None)
    ap.add_argument("--out", default="validate_synth.json")
    ap.add_argument("--save", default=None)
    args = ap.parse_args()

    fit = json.load(open(args.fit))
    aff_t = Affine(**fit["affine_native_to_capture"])
    K = np.array(fit["kernel"], float)
    F = fit["psf"]["taps_per_capture_px"]
    noise = args.noise if args.noise is not None else fit.get("noise_sd_grey", 2.0)
    font = load_font()
    shape = (533, 1055)
    print("degrading with the affine and PSF measured on the REAL frame:")
    print("  char pitch %.4f px  row pitch %.4f px  sigma_nat x %.3f y %.3f  noise sd %.2f"
          % (fit["char_pitch_capture_px"], fit["row_pitch_capture_px"],
             fit["psf"]["sigma_x_native_px"], fit["psf"]["sigma_y_native_px"], noise))

    man = json.load(open(args.manifest))
    fa = {}
    for p in man["pages"]:
        for s in p["snaps"]:
            fa[s] = int(p["addr"], 16)
    frames = sorted(glob.glob(args.frames))
    rng = np.random.default_rng(12345)

    picked, results = [], []
    for fp in frames:
        if len(picked) >= args.n:
            break
        idx = int(os.path.basename(fp)[:4])
        addr = fa.get(idx)
        if addr is None:
            continue
        page = rom_page(addr)
        if page is None:
            continue
        nat = np.asarray(Image.open(fp).convert("RGB")).astype(np.float32)
        # only use fully settled frames: check the native decode is exact first
        want = page_text(addr, page)
        g = nat.astype(np.int32).sum(axis=2)
        ok = True
        for r in range(16):
            for c in range(RG.NHEXCOLS):
                pt = g[RG.CELL_Y0 + 9 * r:RG.CELL_Y0 + 9 * r + 7,
                       RG.CELL_X0 + 6 * c:RG.CELL_X0 + 6 * c + 5]
                bm = (pt < 100).astype(np.uint8)
                exp = font[want[r][c]]
                if not np.array_equal(bm, exp.astype(np.uint8)):
                    ok = False
                    break
            if not ok:
                break
        if not ok:
            continue
        if picked and addr in [p[1] for p in picked]:
            continue
        picked.append((fp, addr, page))

    print("\nusing %d settled emulator frames" % len(picked))
    for fp, addr, page in picked:
        nat = np.asarray(Image.open(fp).convert("RGB")).astype(np.float32)
        cap = degrade(nat, aff_t, K, F, shape, noise, rng)
        if args.save:
            Image.fromarray(cap.astype(np.uint8)).save(
                "%s_%08X.png" % (args.save, addr))
        gray = cap.mean(axis=2)
        ul, vt, ur, vb = FR.find_panel(cap)
        ax0 = (ur - ul) / (RG.PANEL[2] - RG.PANEL[0])
        rp, ay0, by0, ng = FR.seed_rows(gray, ul, vt, ur, vb)
        seed = Affine(ax0, 0.0, ul - ax0 * RG.PANEL[0], ay0, 0.0, by0)
        seed_err = cell_error(aff_t, seed)
        prefix, aff, sx, sy, evid = FR.read_prefix(gray, font, seed, verbose=False)
        base = prefix[:6] + "00"
        grid = NativeGrid(S=3)
        prev = None
        for it in range(3):
            text, ncc, marg = FC.decode_page(gray, aff, font, sx, sy, use_context=False)
            for r in range(16):
                for c, ch in enumerate("%08X" % (int(base, 16) + 16 * r)):
                    text[r][c] = ch
            flat = "".join("".join(x or "?" for x in row) for row in text)
            aff, sx, sy, val, npix = FC.fit(gray, grid, font, text, aff, (sx, sy),
                                            maxiter=400)
            if prev == flat:
                break
            prev = flat
        text, ncc, marg = FC.decode_page(gray, aff, font, sx, sy, use_context=False)
        for r in range(16):
            for c, ch in enumerate("%08X" % (int(base, 16) + 16 * r)):
                text[r][c] = ch
        got = FC.text_to_bytes(text)
        good = sum(1 for i in range(256) if got[i] == page[i])
        err = cell_error(aff_t, aff)
        res = {"addr": "0x%08X" % addr, "base_read": "0x" + base,
               "base_ok": int(base, 16) == addr,
               "seed_cell_error_px": seed_err, "final_cell_error_px": err,
               "sigma_x_native": sx, "sigma_y_native": sy,
               "bytes_correct": good, "byte_accuracy_pct": 100.0 * good / 256.0}
        results.append(res)
        print("  page 0x%08X  base read 0x%s %s | cell err seed %.2f -> %.2f px "
              "| sigma_nat %.2f/%.2f | bytes %3d/256 = %6.2f %%"
              % (addr, base, "OK " if res["base_ok"] else "BAD",
                 seed_err, err, sx, sy, good, res["byte_accuracy_pct"]))

    if results:
        tot = sum(r["bytes_correct"] for r in results)
        n = 256 * len(results)
        print("\nTOTAL  %d/%d bytes = %.4f %%   base address correct on %d/%d pages"
              % (tot, n, 100.0 * tot / n,
                 sum(1 for r in results if r["base_ok"]), len(results)))
        print("worst final cell-position error: %.2f capture px"
              % max(r["final_cell_error_px"] for r in results))
    json.dump({"noise_sd": noise, "results": results}, open(args.out, "w"), indent=1)
    print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
