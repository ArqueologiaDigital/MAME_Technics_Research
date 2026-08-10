#!/usr/bin/env python3
"""Sub-pixel geometry fit for a REAL (composite-captured) KN7000 MEMORY DUMP frame.

Nothing here assumes a scale factor.  Both axes are fitted by 1-D optimisation of a
normalised cross-correlation between the capture's ink profile and a *reference
profile measured from clean native emulator frames* -- so the template already carries
the true statistics of the layout (address digits, the two spaces, the 3-cell
nibble/nibble/gap comb, the '-' separator, the ASCII column) and nothing is guessed.

Outputs the affine char-grid map

    x_capture = XO + PX * cell        (cell = 0 .. 74)
    y_capture = YO + PY * row         (row  = 0 .. 15)

plus a per-row independent re-fit of XO, which is what exposes the accumulating-pitch
error class that killed the phone-photo path.
"""
from __future__ import annotations

import json
import os
import sys
import numpy as np
from PIL import Image

NATIVE = dict(x0=90, y0=55, px=6, py=9, gw=5, gh=7, nrows=16, ncols=75)


# --------------------------------------------------------------------------- #
# ink maps
# --------------------------------------------------------------------------- #
def luma(im: np.ndarray) -> np.ndarray:
    return 0.299 * im[:, :, 0] + 0.587 * im[:, :, 1] + 0.114 * im[:, :, 2]


def ink_map(lum: np.ndarray, pct: float = 88.0) -> np.ndarray:
    """Ink = how far below the local (per-row) panel background a pixel is, in [0,1]."""
    bg = np.percentile(lum, pct, axis=1, keepdims=True)
    return np.clip(1.0 - lum / np.maximum(bg, 1e-3), 0.0, 1.0)


# --------------------------------------------------------------------------- #
# reference profiles from clean native frames
# --------------------------------------------------------------------------- #
def native_profiles(frames_dir: str, nmax: int = 60):
    """Mean column and row ink profiles of the 16-row text block, in native px.

    Column profile spans cells 0..74 (450 px); row profile spans rows 0..15 (144 px).
    Both are indexed from the char-grid origin, so the returned arrays are directly
    the templates for the affine fit.
    """
    files = sorted(f for f in os.listdir(frames_dir) if f.endswith(".png"))
    step = max(1, len(files) // nmax)
    C = np.zeros(NATIVE["px"] * NATIVE["ncols"])
    R = np.zeros(NATIVE["py"] * NATIVE["nrows"])
    n = 0
    for f in files[::step][:nmax]:
        im = np.array(Image.open(os.path.join(frames_dir, f)).convert("RGB")).astype(np.float32)
        if im.shape[:2] != (240, 640):
            continue
        lum = luma(im)
        y0, x0 = NATIVE["y0"], NATIVE["x0"]
        blk = lum[y0:y0 + NATIVE["py"] * NATIVE["nrows"], x0:x0 + NATIVE["px"] * NATIVE["ncols"]]
        ink = np.clip(1.0 - blk / 128.0, 0, 1)
        C += ink.sum(axis=0)
        R += ink.sum(axis=1)
        n += 1
    return C / n, R / n, n


# --------------------------------------------------------------------------- #
# 1-D affine fit of a measured profile against a reference profile
# --------------------------------------------------------------------------- #
def _resample(ref: np.ndarray, org: float, scale: float, x: np.ndarray) -> np.ndarray:
    """ref is indexed in native px from the grid origin; return ref at capture x."""
    u = (x - org) / scale
    return np.interp(u, np.arange(len(ref)), ref, left=0.0, right=0.0)


def ncc(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean(); b = b - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 1e-12 else -1.0


def fit_axis(prof: np.ndarray, ref: np.ndarray, org_range, scale_range,
             n_org=400, n_scale=400, refine=3):
    """Grid + successive refinement over (origin, scale).  Returns (org, scale, ncc)."""
    x = np.arange(len(prof), dtype=np.float64)
    o_lo, o_hi = org_range
    s_lo, s_hi = scale_range
    best = (None, None, -2.0)
    for it in range(refine + 1):
        os_ = np.linspace(o_lo, o_hi, n_org)
        ss_ = np.linspace(s_lo, s_hi, n_scale if it == 0 else max(60, n_scale // 4))
        for s in ss_:
            # vectorise over origins for this scale
            for o in os_:
                m = _resample(ref, o, s, x)
                v = ncc(prof, m)
                if v > best[2]:
                    best = (o, s, v)
        o, s, _ = best
        do = (o_hi - o_lo) / n_org * 4
        ds = (s_hi - s_lo) / max(n_scale, 1) * 4
        o_lo, o_hi = o - do, o + do
        s_lo, s_hi = s - ds, s + ds
        n_org = 120
    return best


def fit_axis_fast(prof, ref, org_range, scale_range, n_scale=240, refine=4):
    """Same as fit_axis but the origin search is done by FFT cross-correlation."""
    x = np.arange(len(prof), dtype=np.float64)
    p = prof - prof.mean()
    pn = np.sqrt((p * p).sum())
    s_lo, s_hi = scale_range
    o_lo, o_hi = org_range
    best = (None, None, -2.0)
    for it in range(refine + 1):
        for s in np.linspace(s_lo, s_hi, n_scale if it == 0 else 60):
            # build the model at origin 0 then slide it by integer shifts via FFT
            L = len(prof)
            base = np.interp(x / s, np.arange(len(ref)), ref, left=0.0, right=0.0)
            b = base - base.mean()
            bn = np.sqrt((b * b).sum())
            if bn < 1e-9:
                continue
            cc = np.fft.irfft(np.fft.rfft(p, 2 * L) * np.conj(np.fft.rfft(b, 2 * L)), 2 * L)
            # shift k means model placed at origin k
            ks = np.arange(int(max(0, o_lo)), int(min(L - 1, o_hi)) + 1)
            if len(ks) == 0:
                continue
            v = cc[ks] / (pn * bn)
            k = ks[int(np.argmax(v))]
            # sub-pixel refine on origin by local quadratic on the true ncc
            for o in np.linspace(k - 1.5, k + 1.5, 25):
                m = _resample(ref, o, s, x)
                q = ncc(prof, m)
                if q > best[2]:
                    best = (float(o), float(s), q)
        o, s, _ = best
        ds = (s_hi - s_lo) / n_scale * 3
        s_lo, s_hi = s - ds, s + ds
        o_lo, o_hi = o - 3, o + 3
    return best


# --------------------------------------------------------------------------- #
def main(argv):
    real_path = argv[1] if len(argv) > 1 else \
        "/home/fsanches/compartilhado/KN7000/photos/1st-frame-grabbed.png"
    frames_dir = argv[2] if len(argv) > 2 else "/tmp/dg_cap1/frames"

    cache = "native_profiles.npz"
    if os.path.exists(cache):
        z = np.load(cache)
        Cref, Rref, nref = z["C"], z["R"], int(z["n"])
    else:
        Cref, Rref, nref = native_profiles(frames_dir)
        np.savez(cache, C=Cref, R=Rref, n=nref)
    print(f"native reference profiles from {nref} frames")

    im = np.array(Image.open(real_path).convert("RGB")).astype(np.float32)
    lum = luma(im)
    H, W = lum.shape

    # --- coarse panel window (generous), then ink map ----------------------- #
    ys, xs = np.nonzero((lum > 24))
    win = dict(x0=max(0, xs.min()), x1=min(W, xs.max() + 1),
               y0=max(0, ys.min()), y1=min(H, ys.max() + 1))
    # the panel is the dominant mid-grey blob; find it by greyness profile
    mx = im.max(axis=2); mn = im.min(axis=2)
    grey = ((mx - mn) < 45) & (lum > 80) & (lum < 210)
    cp = grey.sum(axis=0); rp = grey.sum(axis=1)
    xs_ = np.nonzero(cp > 0.25 * cp.max())[0]
    ys_ = np.nonzero(rp > 0.25 * rp.max())[0]
    px0, px1 = int(xs_.min()), int(xs_.max())
    py0, py1 = int(ys_.min()), int(ys_.max())
    print(f"panel (grey blob) x {px0}..{px1}  y {py0}..{py1}")

    # generous crop around the text block
    cx0, cx1 = max(0, px0 - 12), min(W, px1 + 12)
    cy0, cy1 = max(0, py0 - 12), min(H, py1 + 12)
    sub = lum[cy0:cy1, cx0:cx1]
    ink = ink_map(sub)

    # --- vertical fit ------------------------------------------------------- #
    rowprof = ink.sum(axis=1)
    sy_guess = (py1 - py0) / (NATIVE["py"] * NATIVE["nrows"])
    yo, sy, vy = fit_axis_fast(rowprof, Rref,
                               org_range=(0, len(rowprof) - 1),
                               scale_range=(sy_guess * 0.75, sy_guess * 1.35))
    PY = sy * NATIVE["py"]
    YO = cy0 + yo
    print(f"VERTICAL   origin y={YO:.3f}  scale={sy:.5f}  row pitch PY={PY:.4f} px  ncc={vy:.4f}")

    # --- horizontal fit (restricted to the fitted text rows) ---------------- #
    r0 = int(round(yo)); r1 = int(round(yo + PY * NATIVE["nrows"]))
    r0 = max(0, r0); r1 = min(ink.shape[0], r1)
    colprof = ink[r0:r1].sum(axis=0)
    sx_guess = (px1 - px0) / (NATIVE["px"] * NATIVE["ncols"] + 12)
    xo, sx, vx = fit_axis_fast(colprof, Cref,
                               org_range=(0, len(colprof) - 1),
                               scale_range=(sx_guess * 0.7, sx_guess * 1.4))
    PX = sx * NATIVE["px"]
    XO = cx0 + xo
    print(f"HORIZONTAL origin x={XO:.3f}  scale={sx:.5f}  char pitch PX={PX:.4f} px  ncc={vx:.4f}")

    # --- per-row independent horizontal origin (shear / drift detector) ----- #
    print("per-row horizontal origin (pitch held at the global fit):")
    offs = []
    for r in range(NATIVE["nrows"]):
        a = int(round(yo + PY * r)); b = int(round(yo + PY * r + PY))
        a = max(0, a); b = min(ink.shape[0], b)
        if b - a < 3:
            offs.append(np.nan); continue
        rp_ = ink[a:b].sum(axis=0)
        bestv, besto = -2, np.nan
        for o in np.linspace(xo - 6, xo + 6, 241):
            m = _resample(Cref, o, sx, np.arange(len(rp_), dtype=float))
            v = ncc(rp_, m)
            if v > bestv:
                bestv, besto = v, o
        offs.append(besto)
        print(f"   row {r:2d}  x0={cx0+besto:8.3f}  d={besto-xo:+6.3f}  ncc={bestv:.3f}")
    offs = np.array(offs, float)
    ok = np.isfinite(offs)
    if ok.sum() > 3:
        A = np.polyfit(np.arange(16)[ok], offs[ok], 1)
        print(f"   shear: dx/drow = {A[0]:+.4f} px  (total over 16 rows {A[0]*15:+.3f} px)")
        print(f"   residual std after removing shear: {np.std(offs[ok]-np.polyval(A,np.arange(16)[ok])):.3f} px")

    # --- per-row independent pitch (the drift class) ------------------------ #
    print("per-row independent (origin,pitch) fit:")
    pitches = []
    for r in range(NATIVE["nrows"]):
        a = int(round(yo + PY * r)); b = int(round(yo + PY * r + PY))
        a = max(0, a); b = min(ink.shape[0], b)
        rp_ = ink[a:b].sum(axis=0)
        o_, s_, v_ = fit_axis_fast(rp_, Cref, (xo - 8, xo + 8), (sx * 0.96, sx * 1.04),
                                   n_scale=120, refine=3)
        pitches.append(s_ * NATIVE["px"])
        print(f"   row {r:2d}  PX={s_*NATIVE['px']:.4f}  x0={cx0+o_:.3f}  ncc={v_:.3f}")
    pitches = np.array(pitches)
    print(f"   pitch mean {pitches.mean():.4f}  std {pitches.std():.4f}  "
          f"spread over a 75-char row {(pitches.max()-pitches.min())*74:.2f} px")

    res = dict(image=real_path, W=W, H=H,
               panel=[px0, px1, py0, py1],
               XO=XO, PX=PX, YO=YO, PY=PY,
               sx=sx, sy=sy, ncc_x=vx, ncc_y=vy,
               per_row_x0=[None if not np.isfinite(o) else cx0 + float(o) for o in offs],
               per_row_pitch=[float(v) for v in pitches],
               native=NATIVE)
    with open("geom_real.json", "w") as fh:
        json.dump(res, fh, indent=1)
    print("written geom_real.json")


if __name__ == "__main__":
    main(sys.argv)
