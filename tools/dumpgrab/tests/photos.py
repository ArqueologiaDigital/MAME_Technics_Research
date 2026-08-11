import sys, os, glob, time
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000dump import PageExtractor
from kn7000dump.imageutil import load_rgb
from PIL import Image

P = sorted(glob.glob("/home/fsanches/compartilhado/KN7000/photos/dump-via-debug/*.jpg"))[:6]
imgs = []
for p in P:
    im = Image.open(p).convert("RGB")
    imgs.append((os.path.basename(p), np.asarray(im), im.size))
t0=time.time()
at = PageExtractor.build_atlas_selfsupervised([a for _, a, _ in imgs], rounds=2)
print("selfsup atlas from %d photos in %.0fs: counts=%s" % (len(imgs), time.time()-t0, list(at.counts)))
ex = PageExtractor(atlas=at)
for name, arr, size in imgs:
    r = ex.extract(arr, retry=False)
    print("  %-40s %sx%s base=%-8s rows_ok=%2d lowconf=%3d" % (
        name, size[0], size[1], ("%08X"%r.base_address) if r.base_address is not None else "None",
        sum(r.row_addr_ok), r.n_low_conf))
    print("      " + r.text[0])
    print("      " + r.text[1])
