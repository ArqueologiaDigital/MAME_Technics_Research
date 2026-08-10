#!/usr/bin/env python3
"""Stage-A/B/C geometry fit, done cleanly.

A  locate the text block from horizontal-gradient energy (text-only structure)
B  vertical: fit (y0, py) against the native row profile
C  horizontal: fit (x0, px) against the native column profile
D  per-row re-fit -> shear and pitch-drift diagnostics
"""
from __future__ import annotations
import json, os, sys
import numpy as np
from PIL import Image

NROWS, NCOLS = 16, 75
NPX, NPY = 6, 9            # native char / row pitch
NX0, NY0 = 90, 55          # native grid origin


def luma(im):
    return 0.299 * im[:, :, 0] + 0.587 * im[:, :, 1] + 0.114 * im[:, :, 2]


def native_profiles(frames_dir, nmax=60, cache="native_profiles2.npz"):
    if os.path.exists(cache):
        z = np.load(cache)
        return z["C"], z["R"], int(z["n"])
    files = sorted(f for f in os.listdir(frames_dir) if f.endswith(".png"))
    step = max(1, len(files) // nmax)
    C = np.zeros(NPX * NCOLS); R = np.zeros(NPY * NROWS); n = 0
    for f in files[::step][:nmax]:
        im = np.array(Image.open(os.path.join(frames_dir, f)).convert("RGB")).astype(np.float32)
        if im.shape[:2] != (240, 640):
            continue
        L = luma(im)
        blk = L[NY0:NY0 + NPY * NROWS, NX0:NX0 + NPX * NCOLS]
        ink = np.clip(1.0 - blk / 128.0, 0, 1)
        C += ink.sum(axis=0); R += ink.sum(axis=1); n += 1
    C /= n; R /= n
    np.savez(cache, C=C, R=R, n=n)
    return C, R, n


def ncc_many(prof, models):
    """prof (L,), models (K,L) -> (K,) normalised cross correlation."""
    p = prof - prof.mean()
    pn = np.sqrt((p * p).sum())
    M = models - models.mean(axis=1, keepdims=True)
    mn = np.sqrt((M * M).sum(axis=1))
    return (M @ p) / np.maximum(mn * pn, 1e-12)


def fit1d(prof, ref, o_lo, o_hi, s_lo, s_hi, no=241, ns=241, rounds=4):
    """Exhaustive (origin, scale) NCC search with successive refinement."""
    x = np.arange(len(prof), dtype=np.float64)
    ru = np.arange(len(ref), dtype=np.float64)
    best = (0.0, 1.0, -2.0)
    for it in range(rounds):
        os_ = np.linspace(o_lo, o_hi, no)
        ss_ = np.linspace(s_lo, s_hi, ns)
        for s in ss_:
            U = (x[None, :] - os_[:, None]) / s
            M = np.interp(U, ru, ref, left=0.0, right=0.0)
            v = ncc_many(prof, M)
            k = int(np.argmax(v))
            if v[k] > best[2]:
                best = (float(os_[k]), float(s), float(v[k]))
        o, s, _ = best
        do = (o_hi - o_lo) / no * 3
        ds = (s_hi - s_lo) / ns * 3
        o_lo, o_hi, s_lo, s_hi = o - do, o + do, s - ds, s + ds
        no, ns = 81, 81
    return best


def main(argv):
    real = argv[1] if len(argv) > 1 else \
        "/home/fsanches/compartilhado/KN7000/photos/1st-frame-grabbed.png"
    frames_dir = argv[2] if len(argv) > 2 else "/tmp/dg_cap1/frames"
    tag = argv[3] if len(argv) > 3 else "real"

    C, R, n = native_profiles(frames_dir)
    im = np.array(Image.open(real).convert("RGB")).astype(np.float32)
    L = luma(im); H, W = L.shape

    # ---- A. panel from the ACHROMATIC mask -------------------------------- #
    # The dump panel and its text are grey/black; everything around it on this screen
    # is blue (LCD background, title bar) or saturated (legend bar, panel buttons).
    Rc, Gc, Bc = im[:, :, 0], im[:, :, 1], im[:, :, 2]
    ach = (np.abs(Rc - Gc) < 38) & (np.abs(Gc - Bc) < 38) & (L > 35)

    def longest_run(p, frac=0.35):
        on = p > frac * p.max()
        best, i = (0, 0), 0
        while i < len(on):
            if on[i]:
                j = i
                while j < len(on) and on[j]:
                    j += 1
                if j - i > best[1] - best[0]:
                    best = (i, j)
                i = j
            else:
                i += 1
        return best

    ry0, ry1 = longest_run(ach.sum(axis=1))
    rx0, rx1 = longest_run(ach[ry0:ry1].sum(axis=0))
    print(f"[A] panel  x {rx0}..{rx1}  y {ry0}..{ry1}   ({rx1-rx0} x {ry1-ry0})")
    # the char grid sits inside the panel body: native panel 84..548 x 49..~199,
    # grid origin 90,55 -> use the panel only to bound the search, never as the grid.

    pad = 8
    cx0, cx1 = max(0, rx0 - pad), min(W, rx1 + pad)
    cy0, cy1 = max(0, ry0 - pad), min(H, ry1 + pad)
    sub = L[cy0:cy1, cx0:cx1]
    bg = np.percentile(sub, 88, axis=1, keepdims=True)
    ink = np.clip(1.0 - sub / np.maximum(bg, 1e-3), 0, 1)

    # ---- B. vertical ------------------------------------------------------ #
    rowprof = ink.sum(axis=1)
    sy0 = (ry1 - ry0) / (NPY * NROWS)
    yo, sy, vy = fit1d(rowprof, R, 0, 2 * pad + 24, sy0 * 0.78, sy0 * 1.28)
    PY = sy * NPY; YO = cy0 + yo
    print(f"[B] vertical    y0={YO:.3f}  row pitch PY={PY:.4f}  (scale {sy:.5f})  ncc={vy:.4f}")

    # ---- C. horizontal ---------------------------------------------------- #
    r0 = int(round(yo)); r1 = int(round(yo + PY * NROWS))
    colprof = ink[max(0, r0):min(ink.shape[0], r1)].sum(axis=0)
    sx0 = (rx1 - rx0) / (NPX * NCOLS)
    xo, sx, vx = fit1d(colprof, C, 0, 2 * pad + 24, sx0 * 0.78, sx0 * 1.28)
    PX = sx * NPX; XO = cx0 + xo
    print(f"[C] horizontal  x0={XO:.3f}  char pitch PX={PX:.4f}  (scale {sx:.5f})  ncc={vx:.4f}")

    # ---- D. per-row ------------------------------------------------------- #
    rows = []
    for r in range(NROWS):
        a = int(np.floor(yo + PY * r)); b = int(np.ceil(yo + PY * r + PY * 7.0 / 9.0))
        a = max(0, a); b = min(ink.shape[0], b)
        rp = ink[a:b].sum(axis=0)
        o_, s_, v_ = fit1d(rp, C, xo - 6, xo + 6, sx * 0.93, sx * 1.07, no=121, ns=121)
        rows.append(dict(row=r, x0=cx0 + o_, px=s_ * NPX, ncc=v_))
        print(f"    row {r:2d}  x0={cx0+o_:8.3f} ({o_-xo:+6.3f})  PX={s_*NPX:.4f} "
              f"({(s_-sx)/sx*100:+5.2f}%)  ncc={v_:.3f}")
    dx = np.array([q["x0"] for q in rows]) - XO
    pp = np.array([q["px"] for q in rows])
    A = np.polyfit(np.arange(NROWS), dx, 1)
    print(f"[D] shear dx/drow = {A[0]:+.4f} px/row (total {A[0]*15:+.3f} px over the block)")
    print(f"    x0 residual std after shear = {np.std(dx - np.polyval(A, np.arange(NROWS))):.3f} px")
    print(f"    per-row pitch mean {pp.mean():.4f} std {pp.std():.4f}  "
          f"-> worst-case end-of-row drift {(pp.max()-pp.min())*74:.2f} px")

    out = dict(image=real, W=W, H=H, block=[int(rx0), int(rx1), int(ry0), int(ry1)],
               XO=XO, PX=PX, YO=YO, PY=PY, sx=sx, sy=sy, ncc_x=vx, ncc_y=vy,
               rows=rows, native=dict(x0=NX0, y0=NY0, px=NPX, py=NPY, nrows=NROWS, ncols=NCOLS))
    with open(f"geom_{tag}.json", "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"written geom_{tag}.json")


if __name__ == "__main__":
    main(sys.argv)
