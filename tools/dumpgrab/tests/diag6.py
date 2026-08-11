import sys, os
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000dump.geometry import fit_grid, ink_map
from kn7000dump.imageutil import load_rgb

D = "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab"
for f in ("real-NTSC-48019000.png", "real-PAL-48019000.png"):
    rgb = load_rgb(os.path.join(D, f))
    ink = ink_map(rgb)
    grid = fit_grid(rgb)
    P = []
    for r in grid.rows:
        a = int(round(r.yc - grid.row_pitch*0.32)); b = int(round(r.yc + grid.row_pitch*0.32))
        P.append(ink[a:b].sum(axis=0))
    P = np.array(P)                       # (16, W)
    mean = P.mean(0); std = P.std(0)
    m = mean/max(mean.max(),1e-9); s = std/max(std.max(),1e-9)
    print("=== %s ===  (M=mean ink across rows, S=std across rows; 0-9)" % f)
    for lo in range(80, 640, 140):
        hi = min(lo+140, 720)
        print("  x=%3d M %s" % (lo, "".join(str(min(9,int(m[x]*10))) for x in range(lo,hi))))
        print("        S %s" % ("".join(str(min(9,int(s[x]*10))) for x in range(lo,hi))))
    # first x where std becomes large = start of the varying address digit / hex area
    thr = 0.25*std.max()
    idx = np.nonzero(std > thr)[0]
    print("  columns with high across-row variance: %d..%d" % (idx[0], idx[-1]))
    onm = np.nonzero(mean > 0.12*mean.max())[0]
    print("  columns with ink at all: %d..%d" % (onm[0], onm[-1]))
