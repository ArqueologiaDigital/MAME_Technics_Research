import sys, os, time
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000dump import PageExtractor
from kn7000dump.imageutil import load_rgb
from kn7000dump.oracle import Oracle

D = "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab"
truth = Oracle().page(0x48019000)
nz = [i for i in range(256) if truth[i] != 0x77]

def score(res, tag):
    good = sum(1 for i in range(256) if res.data[i] == truth[i])
    gnz = sum(1 for i in nz if res.data[i] == truth[i])
    print("   %-28s base=%-8s rows_ok=%2d  all=%5.1f%%  non77=%5.1f%%  lowconf=%3d flags=%s"
          % (tag, ("%08X"%res.base_address) if res.base_address is not None else "None",
             sum(res.row_addr_ok), 100*good/256, 100*gnz/len(nz), res.n_low_conf,
             ",".join(res.flags) or "-"))

for f in ("real-NTSC-48019000.png", "real-PAL-48019000.png"):
    rgb = load_rgb(os.path.join(D, f))
    print(f)
    for rounds in (1, 2, 3):
        t0 = time.time()
        at = PageExtractor.build_atlas_selfsupervised([rgb], rounds=rounds)
        ex = PageExtractor(atlas=at)
        res = ex.extract(rgb, retry=False)
        score(res, "selfsup rounds=%d (%.1fs)" % (rounds, time.time()-t0))
    # and a two-frame atlas using both real frames
at = PageExtractor.build_atlas_selfsupervised(
        [load_rgb(os.path.join(D, x)) for x in ("real-NTSC-48019000.png", "real-PAL-48019000.png")],
        rounds=2)
print("joint atlas (both frames), classes=%s counts=%s" % ("".join(at.labels), list(at.counts)))
for f in ("real-NTSC-48019000.png", "real-PAL-48019000.png"):
    res = PageExtractor(atlas=at).extract(load_rgb(os.path.join(D, f)), retry=False)
    score(res, "joint " + f[:9])
