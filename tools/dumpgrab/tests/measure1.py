import sys, time, os
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000dump import PageExtractor, fit_grid
from kn7000dump.imageutil import load_rgb

# known page 0x48019000 -- oracle from the archived table ROM
from kn7000dump.oracle import Oracle
orc = Oracle()
truth = orc.page(0x48019000)
print("truth first 4 rows:")
for r in range(4):
    print("  %08X %s" % (0x48019000+16*r, " ".join("%02X"%b for b in truth[16*r:16*r+16])))
nz = [i for i in range(256) if truth[i] != 0x77]
print("non-0x77 cells: %d/256" % len(nz))

D = "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab"
for atlas in ("data/atlas_native.npz", "data/atlas_selfsup.npz"):
    ap = os.path.join(D, "kn7000dump", atlas)
    for f in ("real-NTSC-48019000.png", "real-PAL-48019000.png"):
        rgb = load_rgb(os.path.join(D, f))
        t0 = time.time()
        ex = PageExtractor(atlas_path=ap)
        res = ex.extract(rgb)
        dt = time.time()-t0
        good = sum(1 for i in range(256) if res.data[i] == truth[i])
        goodnz = sum(1 for i in nz if res.data[i] == truth[i])
        print("%-22s %-26s base=%s rows_ok=%2d  all=%5.1f%%  non77=%5.1f%%  lowconf=%3d  %.2fs  flags=%s"
              % (atlas, f, ("%08X"%res.base_address) if res.base_address is not None else "None",
                 sum(res.row_addr_ok), 100*good/256, 100*goodnz/len(nz), res.n_low_conf, dt,
                 ",".join(res.flags) or "-"))
