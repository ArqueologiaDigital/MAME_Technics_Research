#!/usr/bin/env python3
"""Which page is the frame showing?  Calibrated on the frame's OWN address column.

Character 6 of the address ladder is the digit 0..F, one clean sample of every hex
glyph, printed in the same font at the same size in the same frame.  Its mean luma is
therefore a per-glyph "ink" calibration that needs no oracle.  Apply it to predict the
mean luma of all 256 data cells for each candidate page and correlate.  Mean luma per
cell is a very low-frequency statistic, so it survives the composite blur that destroys
the glyph shapes.
"""
import json
import numpy as np
from PIL import Image

FRAME = '/home/fsanches/compartilhado/KN7000/photos/1st-frame-grabbed.png'
TRANS = ('/home/fsanches/compartilhado/kn7000_disassembly/dumps/'
         'build893-photo-transcription/screens.json')
TABLE = '/home/fsanches/compartilhado/kn7000-emulator/roms/kn7000/kn7000_table.rom'
PROG  = '/home/fsanches/compartilhado/kn7000-emulator/roms/kn7000/kn7000_program.rom'

X0, Y0, SX, SY = 11.0, 14.0, 1029/640.0, 491/240.0
rgb = np.asarray(Image.open(FRAME).convert('RGB')).astype(np.float64)
Y = 0.299*rgb[:,:,0] + 0.587*rgb[:,:,1] + 0.114*rgb[:,:,2]

def cellmean(col, row):
    x = X0 + (90 + 6*col)*SX
    y = Y0 + (55 + 9*row)*SY
    return Y[int(round(y)):int(round(y + 7*SY)), int(round(x)):int(round(x + 5*SX))].mean()

# --- calibrate: address char 6 is the row index digit 0..F
ink = {f'{r:X}': cellmean(6, r) for r in range(16)}
paper = np.mean([cellmean(8, r) for r in range(16)])   # cell 8 is always a space
print('per-glyph mean luma, calibrated on THIS frame\'s address ladder (paper = %.1f):' % paper)
for k in '0123456789ABCDEF':
    print(f'   {k}: {ink[k]:6.1f}   (ink depth {paper-ink[k]:+5.1f})')
spread = max(ink.values()) - min(ink.values())
print(f'   spread across the 16 glyphs: {spread:.1f} LSB   '
      f'(vs paper-to-darkest {paper-min(ink.values()):.1f})')
print()

meas = np.zeros(256)
for r in range(16):
    for i in range(16):
        base = (10 + 3*i) if i < 8 else (34 + 3*(i-8))
        meas[r*16+i] = 0.5*(cellmean(base, r) + cellmean(base+1, r))
m = (meas - meas.mean())/meas.std()

def corr(page):
    p = np.array([0.5*(ink[f'{b:02X}'[0]] + ink[f'{b:02X}'[1]]) for b in page])
    if p.std() == 0: return float('nan')
    p = (p - p.mean())/p.std()
    return float((m*p).mean())

tr = {p['base_address']: p for p in json.load(open(TRANS))}
tab = open(TABLE, 'rb').read(); prg = open(PROG, 'rb').read()
cands = {'PHOTO TRANSCRIPTION 0x48000000':
         bytes(int(b, 16) for row in tr['48000000']['rows'] for b in row['bytes']),
         'table.rom   0x48000000': tab[0:256],
         'program.rom 0x48400000': prg[0:256]}
for name, blob, base in (('table.rom', tab, 0x48000000), ('program.rom', prg, 0x48400000)):
    for off in (0x100, 0x1000, 0x19000, 0x39000, 0x49000, 0x100000, 0x159000):
        if off + 256 <= len(blob):
            cands[f'{name:<11s} 0x{base+off:08X}'] = blob[off:off+256]
rng = np.random.default_rng(0)
for k in range(3):
    cands[f'RANDOM null #{k}'] = bytes(rng.integers(0, 256, 256).tolist())

print('correlation of predicted vs measured per-cell mean luma (256 cells):')
for name, page in sorted(cands.items(), key=lambda kv: -(corr(kv[1]) if corr(kv[1]) == corr(kv[1]) else -9)):
    print(f'   {name:<34s} r = {corr(page):+.3f}')
