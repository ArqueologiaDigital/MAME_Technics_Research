import sys, os
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000dump.geometry import fit_grid, ink_map, texture_map
from kn7000dump.imageutil import load_rgb, shear_rows
from kn7000dump.extract import _cut_patches, refine_grid_by_centroids
from kn7000dump import layout as L

D = "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab"
for f in ("real-NTSC-48019000.png", "real-PAL-48019000.png"):
    rgb = load_rgb(os.path.join(D, f))
    h, w = rgb.shape[:2]
    g = fit_grid(rgb)
    ink = g.ink; tex = texture_map(ink)
    g = refine_grid_by_centroids(ink, g, tex=tex)
    r0, r15 = g.rows[0], g.rows[-1]
    print("%s  %dx%d" % (f, w, h))
    print("   slope=%+.5f row_pitch=%.3f  x0=%.2f cw=%.4f  hex_end_x=%.1f  score=%.4f"
          % (g.slope, g.row_pitch, r0.x0, r0.cw, r0.x0 + g.lay.hex_end*r0.cw, g.score))
    print("   rows y: %.1f .. %.1f  (span %.1f)" % (r0.yc, r15.yc, r15.yc-r0.yc))
    # atlas-free legibility probe on the address column
    lastc  = g.lay.addr_idx[7]
    pen    = g.lay.addr_idx[6]
    for name, c in (("addr[7] (all '0')", lastc), ("addr[6] (0..F)", pen)):
        P = _cut_patches(ink, g, [(r, c) for r in range(16)], 18, 12, tex=tex)
        X = P.reshape(16, -1)
        X = X - X.mean(1, keepdims=True)
        X /= np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-6)
        S = X @ X.T
        off = S[~np.eye(16, dtype=bool)]
        print("   %-18s  self-similarity mean=%.3f min=%.3f  (same glyph -> high; distinct -> low)"
              % (name, off.mean(), off.min()))
    print("   ink stats: mean=%.4f p99=%.4f  tex p99=%.4f" % (ink.mean(), np.percentile(ink,99), np.percentile(tex,99)))
