#!/usr/bin/env python3
"""Does the COLOUR highlight channel survive the composite path?

The viewer paints the cell background of any byte equal to F0 / F7 / FF / XX in
aqua / yellow / lime / fuchsia.  Chroma is carried separately in composite and is
band-limited far harder than luma -- but a highlight is 3 character cells (18 native
px) wide, so it may survive where the 1-px glyph strokes do not.  Ground truth for
which cells are highlighted comes from the committed photo transcription of the SAME
page 0x48000000.
"""
import json
import numpy as np
from PIL import Image

FRAME = '/home/fsanches/compartilhado/KN7000/photos/1st-frame-grabbed.png'
TRANS = ('/home/fsanches/compartilhado/kn7000_disassembly/dumps/'
         'build893-photo-transcription/screens.json')

rgb = np.asarray(Image.open(FRAME).convert('RGB')).astype(np.float64)
Y  = 0.299*rgb[:,:,0] + 0.587*rgb[:,:,1] + 0.114*rgb[:,:,2]
CB = -0.168736*rgb[:,:,0] - 0.331264*rgb[:,:,1] + 0.5*rgb[:,:,2]
CR = 0.5*rgb[:,:,0] - 0.418688*rgb[:,:,1] - 0.081312*rgb[:,:,2]

X0, Y0, SX, SY = 11.0, 14.0, 1029/640.0, 491/240.0
CELL_X0, CELL_Y0, CPX, RPY = 90, 55, 6, 9          # native px, from doc/GEOMETRY.txt

def cell_box(col, row):
    x = X0 + (CELL_X0 + CPX*col)*SX
    y = Y0 + (CELL_Y0 + RPY*row)*SY
    return slice(int(round(y)), int(round(y + 7*SY))), slice(int(round(x)), int(round(x + 6*SX)))

pages = {p['base_address']: p for p in json.load(open(TRANS))}
page = pages['48000000']
data = [[int(b, 16) for b in r['bytes']] for r in page['rows']]

# the four legend values on this page: the defaults F0 / F7 / FF, plus XX (unknown,
# user-settable).  Read the legend strip's own colours off the screen instead of
# assuming them -- that is what the extractor does.
legend_row_y = Y0 + (CELL_Y0 + RPY*16)*SY
lr = slice(int(legend_row_y), int(legend_row_y + 7*SY))
print(f'legend strip rows {lr.start}..{lr.stop}')
for name, xs in (('aqua', 160), ('yellow', 330), ('lime', 500), ('fuchsia', 660)):
    b = slice(xs, xs+60)
    print(f'  {name:<8s} Y={Y[lr,b].mean():6.1f}  Cb={CB[lr,b].mean():+7.1f}  Cr={CR[lr,b].mean():+7.1f}')
print()

# classify every hex cell pair by its background chroma
hits = {'F0': [], 'F7': [], 'FF': [], 'other': []}
rows_out = []
for r in range(16):
    for i in range(16):
        col = (10 + 3*i) if i < 8 else (34 + 3*(i-8))
        v = data[r][i]
        # sample the CELL BACKGROUND: the 1-px gap column between the two nibbles'
        # cells is background-only, and so is the row above/below the 5x7 glyph
        ys, xs = cell_box(col, r)
        # widen to the whole two-character cell and take the top gap row
        xs = slice(xs.start, xs.start + int(round(12*SX)))
        gap = slice(ys.stop - int(round(2*SY)), ys.stop)
        cb, cr = CB[gap, xs].mean(), CR[gap, xs].mean()
        key = f'{v:02X}' if f'{v:02X}' in hits else 'other'
        hits[key].append((cb, cr))

print('cell-background chroma, grouped by the byte value from the photo transcription')
print('  value      n    mean Cb    mean Cr    (a highlighted cell should sit far from "other")')
for k in ('F0', 'F7', 'FF', 'other'):
    v = np.array(hits[k])
    if len(v) == 0:
        print(f'  {k:<8s}  0    --')
        continue
    print(f'  {k:<8s} {len(v):3d}   {v[:,0].mean():+8.2f}   {v[:,1].mean():+8.2f}'
          f'   (sd {v[:,0].std():5.2f}, {v[:,1].std():5.2f})')

# separability: how far is each highlighted cell from the "other" cloud, in sigmas?
oth = np.array(hits['other'])
mu, sd = oth.mean(axis=0), oth.std(axis=0) + 1e-6
print()
for k in ('F0', 'F7', 'FF'):
    v = np.array(hits[k])
    if len(v) == 0: continue
    dist = np.sqrt((((v - mu)/sd)**2).sum(axis=1))
    print(f'  {k}: {len(v)} cell(s), Mahalanobis distance from the unhighlighted cloud '
          f'= {dist.min():.1f}..{dist.max():.1f} sigma')
