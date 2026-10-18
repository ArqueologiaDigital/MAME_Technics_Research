#!/usr/bin/env python3
"""identify_frames.py -- question it answers: which source picture is on the KN7000 LCD in a
MAME snapshot (or in a render_fb.py RAM render)?  Compares the 640x240 LCD crop (at (180,78)
of a 1000x750 snapshot, or the whole image if it is already 640x240) with every candidate
640x240 JPEG by mean absolute grey-level difference; prints the best and second-best match.
A clean frame scores well below ~20; a mixed/transitional frame has no clear winner.
usage: python3 -I identify_frames.py PICDIR SNAP.png [SNAP.png ...]
"""
import sys, os
from PIL import Image, ImageChops, ImageStat
picdir = sys.argv[1]
cands = {f: Image.open(os.path.join(picdir, f)).convert("L") for f in sorted(os.listdir(picdir)) if f.lower().endswith(".jpg")}
for p in sys.argv[2:]:
    im = Image.open(p).convert("L")
    if im.size != (640, 240): im = im.crop((180, 78, 820, 318))
    sc = sorted((ImageStat.Stat(ImageChops.difference(im, c)).mean[0], f) for f, c in cands.items() if c.size == (640, 240))
    print(f"{os.path.basename(os.path.dirname(os.path.dirname(p)))}/{os.path.basename(p)}: best {sc[0][1]} {sc[0][0]:.1f}  next {sc[1][1]} {sc[1][0]:.1f}")
