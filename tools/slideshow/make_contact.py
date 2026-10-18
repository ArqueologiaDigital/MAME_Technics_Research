#!/usr/bin/env python3
"""make_contact.py -- question it answers: what did the KN7000 LCD show at each logged
moment of a MAME run?  Takes 640x240 images (render_fb.py output) as they are, and crops the 640x240 LCD area from MAME snapshots (the kn7000 layout
puts the LCD's top-left at (180, 78) in a 1000x750 snapshot -- measured on these runs) and
stacks the crops with a caption into one PNG.
usage: python3 -I make_contact.py OUT.png COLS SNAP.png=caption [SNAP.png=caption ...]
"""
import sys
from PIL import Image, ImageDraw
out, cols = sys.argv[1], int(sys.argv[2])
items = [a.split("=", 1) for a in sys.argv[3:]]
W, H, CAP = 640, 240, 22
rows = (len(items) + cols - 1) // cols
sheet = Image.new("RGB", (cols * (W + 8) + 8, rows * (H + CAP + 8) + 8), (40, 40, 40))
d = ImageDraw.Draw(sheet)
for i, (p, cap) in enumerate(items):
    im = Image.open(p).convert("RGB")
    crop = im if im.size == (W, H) else im.crop((180, 78, 180 + W, 78 + H))   # 640x240 renders as is
    x = 8 + (i % cols) * (W + 8); y = 8 + (i // cols) * (H + CAP + 8)
    d.text((x + 4, y + 4), cap, fill=(255, 255, 255))
    sheet.paste(crop, (x, y + CAP))
sheet.save(out); print(out, sheet.size)
