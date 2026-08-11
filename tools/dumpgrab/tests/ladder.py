"""Ladder-guided geometry: score a candidate grid by the redundancy the screen
already prints, so no atlas and no oracle are needed."""
import sys, os, glob, time
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000dump.geometry import fit_rows, ink_map, texture_map, Grid, RowFit, _col_score, _interp_cumsum
from kn7000dump.imageutil import gray, resample_patch, shear_rows
from kn7000dump import layout as L
from PIL import Image

GH, GW = 16, 10

def cut(ink, rows, pitch, cols, cw, x0, oy=1.0, ox=1.0):
    """rows: list of yc.  Returns (nrow, ncol, GH, GW)."""
    out = np.empty((len(rows), len(cols), GH, GW), np.float32)
    hy = pitch*0.5*oy
    hx = cw*0.5*ox
    for i, yc in enumerate(rows):
        for j, c in enumerate(cols):
            cx = x0 + (c+0.5)*cw
            out[i, j] = resample_patch(ink, yc-hy, yc+hy, cx-hx, cx+hx, GH, GW)
    return out

def zn(P):
    X = P.reshape(P.shape[0], -1).astype(np.float32)
    X -= X.mean(1, keepdims=True)
    X /= np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-6)
    return X

def ladder_score(ink, rows, pitch, x0, cw, lay=L.DEFAULT):
    """Consistency of the 8-digit address block with 'row r shows base+0x10r'."""
    A = cut(ink, rows, pitch, lay.addr_idx, cw, x0)          # (16, 8, GH, GW)
    n = len(rows)
    T = zn(A[:, 6])                                          # ladder: row r == digit r
    sc = 0.0; detail = {}
    # 1. column 7 must be '0' == T[0]
    C7 = zn(A[:, 7])
    s7 = C7 @ T.T
    ok7 = int((s7.argmax(1) == 0).sum())
    # 2. columns 0..5 constant down the rows AND each equal to some single ladder digit
    okc = 0; prefix = []
    for c in range(6):
        Cc = zn(A[:, c])
        s = Cc @ T.T
        w = s.argmax(1)
        vals, cnt = np.unique(w, return_counts=True)
        best = vals[cnt.argmax()]
        okc += int(cnt.max())
        prefix.append(int(best))
    # 3. the ladder itself must be 16 MUTUALLY DISTINCT glyphs
    S = T @ T.T
    off = S[~np.eye(n, dtype=bool)]
    distinct = 1.0 - float(off.mean())
    total = (ok7 + okc) / float(n*7)
    return total*0.75 + distinct*0.25, ok7, okc, prefix, total

def fit_ladder(rgb, verbose=False):
    ink0 = ink_map(rgb)
    best = None
    for slope in (0.0,):
        ink = shear_rows(ink0, slope) if slope else ink0
        y0, pitch, _ = fit_rows(ink)
        ink = shear_rows(ink_map(rgb, ry=max(2,int(round(pitch*1.3))), rx=max(2,int(round(pitch*3.0)))), slope)
        y0, pitch, _ = fit_rows(ink)
        h, w = ink.shape
        # column shortlist from the classic matched filter, over a wide pitch range
        cands = []
        for cw in np.arange(max(3.0, w/110.0), w/40.0, 0.05):
            bands = []
            for r in range(16):
                yc = y0 + r*pitch
                a = max(int(yc-pitch*0.32), 0); b = min(int(yc+pitch*0.32), h)
                if b > a: bands.append(ink[a:b])
            prof = np.concatenate(bands, 0).sum(axis=0)
            x0s = np.arange(0, max(w - L.DEFAULT.hex_end*cw, 1), 0.5)
            if len(x0s) == 0: continue
            s = _col_score(prof, L.DEFAULT, x0s, float(cw), w)
            k = int(np.argmax(s))
            cands.append((float(s[k]), float(x0s[k]), float(cw)))
        cands.sort(key=lambda t: -t[0])
        shortlist = cands[:40]
        for _, x0, cw in shortlist:
            for dk in range(-3, 4):
                rows = [y0 + (r+dk)*pitch for r in range(16)]
                if rows[0] < pitch*0.5 or rows[-1] > h-pitch*0.5: continue
                for dx in (-0.5, 0.0, 0.5):
                    sc, ok7, okc, prefix, tot = ladder_score(ink, rows, pitch, x0+dx, cw)
                    if best is None or sc > best[0]:
                        best = (sc, x0+dx, cw, rows, pitch, ok7, okc, prefix, tot, ink)
    return best

D = "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab"
sys.path.insert(0, "/home/fsanches/.claude/jobs/d0e1b1c2/tmp")
from locate import crop_panel
HEXD = "0123456789ABCDEF"
files = [(os.path.join(D, "real-NTSC-48019000.png"), "NTSC-grab", "48019000"),
         (os.path.join(D, "real-PAL-48019000.png"), "PAL-grab", "48019000")]
files += [(p, os.path.basename(p)[-12:], None) for p in sorted(glob.glob("/home/fsanches/compartilhado/KN7000/photos/dump-via-debug/*.jpg"))[:6]]
for path, tag, expect in files:
    rgb = np.asarray(Image.open(path).convert("RGB"))
    crop, _ = crop_panel(rgb)
    t0 = time.time()
    b = fit_ladder(crop)
    sc, x0, cw, rows, pitch, ok7, okc, prefix, tot, ink = b
    pfx = "".join(HEXD[i] for i in prefix)
    print("%-13s score=%.3f cw=%.3f x0=%.1f pitch=%.2f  col7ok=%2d/16 prefixok=%2d/96  prefix=%s??  %s (%.0fs)"
          % (tag, sc, cw, x0, pitch, ok7, okc, pfx,
             ("expect " + expect[:6]) if expect else "", time.time()-t0))
