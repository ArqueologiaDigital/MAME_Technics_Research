import sys, os
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000dump.geometry import fit_grid, ink_map, texture_map
from kn7000dump.imageutil import load_rgb

D = "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab"
for f in ("real-NTSC-48019000.png",):
    rgb = load_rgb(os.path.join(D, f))
    ink = ink_map(rgb)
    grid = fit_grid(rgb)
    # use ONLY the 16 text rows, each restricted to a 0.6*pitch band around its centre
    bands = []
    for r in grid.rows:
        a = int(round(r.yc - grid.row_pitch*0.30)); b = int(round(r.yc + grid.row_pitch*0.30))
        bands.append(ink[a:b])
    band = np.concatenate(bands, 0)
    prof = band.sum(axis=0); prof = prof/prof.max()
    print("column profile (x=100..620, one char per 2px, level 0-9):")
    for lo in range(100, 620, 130):
        s = "".join(str(min(9,int(prof[x]*10))) for x in range(lo, min(lo+130, 720)))
        print("  x=%3d %s" % (lo, s))
    # autocorrelation of the mean-removed profile over the inked region
    on = np.nonzero(prof > 0.10)[0]
    a, b = on[0], on[-1]+1
    p = prof[a:b] - prof[a:b].mean()
    ac = np.correlate(p, p, mode="full")[len(p)-1:]
    ac = ac/ac[0]
    peaks = [(l, ac[l]) for l in range(3, 60) if ac[l] > ac[l-1] and ac[l] >= ac[l+1] and ac[l] > 0.1]
    print("  inked x %d..%d (span %d)" % (a, b-1, b-a))
    print("  autocorr peaks (lag, val):", [(l, round(float(v),3)) for l, v in peaks][:14])
