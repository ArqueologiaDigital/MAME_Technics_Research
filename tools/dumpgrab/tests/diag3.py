import sys, os
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000dump.geometry import fit_grid, texture_map, Grid, RowFit
from kn7000dump.imageutil import load_rgb
from kn7000dump.extract import _cut_patches, refine_grid_by_centroids
from kn7000dump.atlas import AtlasBuilder
from kn7000dump.oracle import Oracle

D = "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab"
truth = Oracle().page(0x48019000)
rgb = load_rgb(os.path.join(D, "real-NTSC-48019000.png"))
g0 = fit_grid(rgb); ink = g0.ink; tex = texture_map(ink)
g0 = refine_grid_by_centroids(ink, g0, tex=tex)
lay = g0.lay

cells, chars = [], []
for r in range(16):
    s = "%08X" % (0x48019000 + 16*r)
    for j, c in enumerate(lay.addr_idx):
        cells.append((r, c)); chars.append(s[j])
    for k, (hi, lo) in enumerate(lay.byte_idx):
        v = truth[r*16+k]
        cells.append((r, hi)); chars.append("%X" % (v >> 4))
        cells.append((r, lo)); chars.append("%X" % (v & 15))
chars = np.array(chars)

def trainacc(gg, recenter, out_x, out_y, gh=18, gw=12):
    P = _cut_patches(ink, gg, cells, gh, gw, out_x=out_x, out_y=out_y, recenter=recenter, tex=tex)
    b = AtlasBuilder(gh=gh, gw=gw); b.add_many(list(chars), P); at = b.finish()
    idx, ncc, mrg = at.classify(P, allowed=list(range(len(at.labels))))
    pred = np.array([at.labels[i] for i in idx])
    return float((pred == chars).mean()), float(ncc.mean()), float(mrg.mean())

def shifted(dx, dcw, dy):
    rows = [RowFit(r.yc + dy, r.x0 + dx, r.cw + dcw, r.score) for r in g0.rows]
    return Grid(g0.slope, g0.row_pitch, rows, lay, g0.score, g0.height, g0.width, ink)

print("baseline recenter=True  : %.1f%% ncc=%.3f mrg=%.4f" % tuple(100*v if i==0 else v for i,v in enumerate(trainacc(g0, True, 1.15, 0.85))))
print("baseline recenter=False : %.1f%% ncc=%.3f mrg=%.4f" % tuple(100*v if i==0 else v for i,v in enumerate(trainacc(g0, False, 1.15, 0.85))))
print()
print("--- x0 / cw sweep, recenter=False ---")
best = None
for dcw in (-0.06, -0.03, 0.0, 0.03, 0.06):
    row = []
    for dx in (-1.2, -0.8, -0.4, 0.0, 0.4, 0.8, 1.2):
        a, _, _ = trainacc(shifted(dx, dcw, 0.0), False, 1.15, 0.85)
        row.append(a)
        if best is None or a > best[0]: best = (a, dx, dcw)
    print("  dcw=%+.2f " % dcw + " ".join("%5.1f" % (100*v) for v in row))
print("  best %.1f%% at dx=%+.2f dcw=%+.3f" % (100*best[0], best[1], best[2]))
print()
print("--- patch aperture sweep at best geometry, recenter=False ---")
gb = shifted(best[1], best[2], 0.0)
for ox in (0.85, 1.0, 1.15, 1.3):
    for oy in (0.7, 0.85, 1.0):
        a, n, m = trainacc(gb, False, ox, oy)
        print("   out_x=%.2f out_y=%.2f -> %.1f%% ncc=%.3f mrg=%.4f" % (ox, oy, 100*a, n, m))
