#!/usr/bin/env python3
# Render kn7000.lay to a schematic PNG in the "Compact" view coordinate system (2000x1500),
# which matches the user's mockup. Draws button/LED boxes + text labels at their exact positions
# so the layout can be pixel-compared/overlaid against the mockup for positioning fine-tuning.
#   usage: python3 tools/render_lay.py [out.png]
# Group->view offsets (Compact view): screen_block(0,0) left_block(0,997) right_block(1000,997).
import re, sys
from PIL import Image, ImageDraw, ImageFont

LAY = 'src/mame/layout/kn7000.lay'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'layrender.png'
GOFF = {'screen_block': (0, 0), 'left_block': (0, 997), 'right_block': (1000, 997)}

lay = open(LAY).read()
tmap = {m.group(1): m.group(2).replace('&amp;', '&')
        for m in re.finditer(r'<element name="(t\d+)"><text string="([^"]*)"', lay)}
img = Image.new('RGB', (2000, 1500), (88, 88, 90))
d = ImageDraw.Draw(img)
font = ImageFont.load_default()
for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
    try: font = ImageFont.truetype(f, 11); break
    except Exception: pass

inst = re.compile(r'<element ref="([^"]+)"[^>]*>(?:<orientation[^>]*/>)?'
                  r'<bounds x="(-?\d+)" y="(-?\d+)" width="(\d+)" height="(\d+)"')
scr = re.compile(r'<screen index="0"><bounds x="(-?\d+)" y="(-?\d+)" width="(\d+)" height="(\d+)"')
cur, ox, oy = None, 0, 0
for line in lay.splitlines():
    gm = re.search(r'<group name="([^"]+)"', line)
    if gm and gm.group(1) in GOFF:
        cur, (ox, oy) = gm.group(1), GOFF[gm.group(1)]; continue
    sm = scr.search(line)
    if sm and cur:
        x, y = int(sm.group(1)) + ox, int(sm.group(2)) + oy
        d.rectangle([x, y, x + int(sm.group(3)), y + int(sm.group(4))], fill=(20, 20, 24)); continue
    im = inst.search(line)
    if not im or cur is None: continue
    ref, x, y, w, h = im.group(1), int(im.group(2)) + ox, int(im.group(3)) + oy, int(im.group(4)), int(im.group(5))
    if ref in tmap:
        d.text((x, y - 2), tmap[ref], fill=(235, 235, 235), font=font)
    elif 'led' in ref:
        d.ellipse([x, y, x + w, y + h], outline=(40, 200, 40))
    elif ref.startswith(('bg_', 'screen_frame', 'panel_bg')):
        pass
    else:
        d.rectangle([x, y, x + w, y + h], outline=(170, 170, 175))
d.line([0, 997, 2000, 997], fill=(50, 50, 50)); d.line([1000, 997, 1000, 1500], fill=(50, 50, 50))
img.save(OUT)
print("wrote", OUT)
