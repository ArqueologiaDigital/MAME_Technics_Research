import sys, os
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000dump.geometry import fit_grid, texture_map, ink_map
from kn7000dump.imageutil import load_rgb, gray

D = "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab"
for f in ("real-NTSC-48019000.png", "real-PAL-48019000.png"):
    rgb = load_rgb(os.path.join(D, f)); h, w = rgb.shape[:2]
    g = gray(rgb)
    print("=== %s  %dx%d ===" % (f, w, h))
    # 1. where is the bright panel?  (the viewer is light-on-... let's just look at luma)
    colmax = g.max(axis=0); rowmax = g.max(axis=1)
    bright = g > (g.max()*0.5)
    cs = np.nonzero(bright.sum(axis=0) > 0.02*h)[0]
    rs = np.nonzero(bright.sum(axis=1) > 0.02*w)[0]
    print("  bright bbox: x %d..%d (w=%d)   y %d..%d (h=%d)" % (cs[0], cs[-1], cs[-1]-cs[0]+1, rs[0], rs[-1], rs[-1]-rs[0]+1))
    ink = ink_map(rgb)
    grid = fit_grid(rgb)
    y0 = grid.rows[0].yc - grid.row_pitch*0.5; y1 = grid.rows[-1].yc + grid.row_pitch*0.5
    band = ink[int(y0):int(y1)]
    prof = band.sum(axis=0)
    thr = 0.12*prof.max()
    on = np.nonzero(prof > thr)[0]
    print("  text-row band y %d..%d ; inked columns %d..%d (span %d)" % (int(y0), int(y1), on[0], on[-1], on[-1]-on[0]+1))
    # 2. pitch by phase folding over the WHOLE inked span
    a, b = on[0], on[-1]+1
    p = prof[a:b].astype(float); x = np.arange(b-a, dtype=float)
    best=(None,-1)
    for cw in np.arange(4.0, 12.0, 0.002):
        idx = np.clip(np.floor(((x/cw) % 1.0)*24).astype(int), 0, 23)
        s = np.bincount(idx, weights=p, minlength=24); c = np.bincount(idx, minlength=24)
        v = float((s/np.maximum(c,1e-9)).var())
        if v > best[1]: best = (cw, v)
    cw = best[0]
    print("  pitch by phase-fold over full span: %.4f px/char  -> %.1f chars in span" % (cw, (b-a)/cw))
    # 3. interlace check: horizontal energy of even vs odd lines, and their mutual offset
    ev, od = band[0::2], band[1::2]
    print("  field ink: even=%.4f odd=%.4f   rowsum std even=%.4f odd=%.4f" % (ev.mean(), od.mean(), ev.sum(1).std(), od.sum(1).std()))
    pe, po = ev.sum(0), od.sum(0)
    pe = pe - pe.mean(); po = po - po.mean()
    cc = np.correlate(pe, po, mode="full"); lag = int(np.argmax(cc)) - (len(po)-1)
    print("  even/odd field horizontal lag: %d px (0 = not field-shifted)" % lag)
    # 4. how many text lines does the panel have in total?
    tex = texture_map(ink)
    rp = tex.sum(axis=1)
    print("  row-texture peaks (top 24 y):", sorted(np.argsort(rp)[-24:].tolist())[:24])
