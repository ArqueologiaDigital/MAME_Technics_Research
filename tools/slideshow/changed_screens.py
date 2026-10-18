# changed_screens.py SNAPDIR OUT COLS -- the LCD of every snapshot in SNAPDIR that differs from the one before,
# on one contact sheet (KN6000 snapshot layout: LCD at (370,70)-(1030,325); labels assume the
# kn6000_pres_insert.lua cadence, insert at t=24 then one snapshot every 5 s). Answers: did the slides advance?
import sys, glob, hashlib
from PIL import Image, ImageDraw
d, out, cols = sys.argv[1], sys.argv[2], int(sys.argv[3])
tiles, prev = [], None
for i, f in enumerate(sorted(glob.glob(d + "/*.png"))):
    h = hashlib.md5(open(f, "rb").read()).hexdigest()
    if h == prev: continue
    prev = h
    im = Image.open(f).convert("RGB").crop((370, 70, 1030, 325)).resize((330, 128))
    ImageDraw.Draw(im).text((3, 2), "t=%d" % (24 + 5 * i - 5 if i else 24), fill=(255, 255, 0))
    tiles.append(im)
w, h = tiles[0].size; rows = (len(tiles) + cols - 1) // cols
sheet = Image.new("RGB", (w * cols, h * rows))
for k, t in enumerate(tiles): sheet.paste(t, ((k % cols) * w, (k // cols) * h))
sheet.save(out); print(out, len(tiles), "screens")
