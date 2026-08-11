import sys, os, glob, time
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000dump.imageutil import gray, box_mean
from kn7000dump import PageExtractor
from PIL import Image

def largest_bright_component(g, frac=0.55, ds=4):
    """bbox of the largest bright blob, computed on a downsampled copy."""
    h, w = g.shape
    s = g[::ds, ::ds]
    thr = frac * float(np.percentile(s, 99.5))
    m = s > thr
    H, W = m.shape
    lab = np.zeros((H, W), np.int32); cur = 0; best = (0, None)
    idx = np.argwhere(m)
    seen = np.zeros((H, W), bool)
    for y0, x0 in idx:
        if seen[y0, x0]: continue
        cur += 1
        stack = [(y0, x0)]; seen[y0, x0] = True
        ys, xs = [], []
        while stack:
            y, x = stack.pop(); ys.append(y); xs.append(x)
            for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
                ny, nx = y+dy, x+dx
                if 0 <= ny < H and 0 <= nx < W and m[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True; stack.append((ny, nx))
        if len(ys) > best[0]:
            best = (len(ys), (min(ys), max(ys), min(xs), max(xs)))
    if best[1] is None: return None
    y0, y1, x0, x1 = best[1]
    return (y0*ds, min((y1+1)*ds, h), x0*ds, min((x1+1)*ds, w)), best[0]*ds*ds

def crop_panel(rgb, pad=0.02):
    g = gray(rgb)
    r = largest_bright_component(g)
    if r is None: return rgb, None
    (y0, y1, x0, x1), area = r
    ph, pw = y1-y0, x1-x0
    py, px = int(ph*pad), int(pw*pad)
    y0 = max(y0-py, 0); y1 = min(y1+py, rgb.shape[0])
    x0 = max(x0-px, 0); x1 = min(x1+px, rgb.shape[1])
    return rgb[y0:y1, x0:x1], (x0, y0, x1-x0, y1-y0, area)

D = "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab"
files = [(os.path.join(D, "real-NTSC-48019000.png"), "NTSC-grab")] + \
        [(p, os.path.basename(p)[-12:]) for p in sorted(glob.glob("/home/fsanches/compartilhado/KN7000/photos/dump-via-debug/*.jpg"))[:6]]
crops = []
for path, tag in files:
    rgb = np.asarray(Image.open(path).convert("RGB"))
    c, info = crop_panel(rgb)
    print("%-14s %sx%s -> panel at %s  crop %dx%d" % (tag, rgb.shape[1], rgb.shape[0],
          (info[0], info[1]) if info else None, c.shape[1], c.shape[0]))
    crops.append((tag, c))

t0=time.time()
at = PageExtractor.build_atlas_selfsupervised([c for _, c in crops[1:]], rounds=2)
print("selfsup atlas from %d cropped photos in %.0fs" % (len(crops)-1, time.time()-t0))
ex = PageExtractor(atlas=at)
for tag, c in crops:
    r = ex.extract(c, retry=False)
    print("  %-12s base=%-8s rows_ok=%2d lowconf=%3d | %s" % (
        tag, ("%08X"%r.base_address) if r.base_address is not None else "None",
        sum(r.row_addr_ok), r.n_low_conf, r.text[0][:44]))
