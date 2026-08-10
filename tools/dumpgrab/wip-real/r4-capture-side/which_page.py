#!/usr/bin/env python3
"""Which page is the real frame showing?  Scored by template match, not by OCR.

For each candidate page we know what glyph belongs in each of the 512 hex character
cells.  Cut that cell out of the frame, z-score it, and dot it with the atlas template
for the glyph the candidate predicts.  The candidate that is actually on screen wins by
a wide margin even when no individual character is legible, because 512 weak votes add.
"""
import json
import numpy as np
from PIL import Image

ATLAS = ('/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab/'
         'kn7000dump/data/atlas_native.npz')
FRAME = '/home/fsanches/compartilhado/KN7000/photos/1st-frame-grabbed.png'
TRANS = ('/home/fsanches/compartilhado/kn7000_disassembly/dumps/'
         'build893-photo-transcription/screens.json')
TABLE = '/home/fsanches/compartilhado/kn7000-emulator/roms/kn7000/kn7000_table.rom'
PROG  = '/home/fsanches/compartilhado/kn7000-emulator/roms/kn7000/kn7000_program.rom'

d = np.load(ATLAS, allow_pickle=True)
labels = list(d['labels']); T = d['templates']; GH, GW = int(d['gh']), int(d['gw'])
tmpl = {c: T[i] for i, c in enumerate(labels)}

X0, Y0, SX, SY = 11.0, 14.0, 1029/640.0, 491/240.0
rgb = np.asarray(Image.open(FRAME).convert('RGB')).astype(np.float64)
Y = 0.299*rgb[:,:,0] + 0.587*rgb[:,:,1] + 0.114*rgb[:,:,2]
im = Image.fromarray(Y.astype(np.float32), mode='F')

def cut(col, row):
    x = X0 + (90 + 6*col)*SX
    y = Y0 + (55 + 9*row)*SY
    p = im.resize((GW, GH), Image.BILINEAR, box=(x, y, x + 6*SX, y + 9*SY))
    a = np.asarray(p, dtype=np.float64)
    a -= a.mean()
    n = np.linalg.norm(a)
    return a/n if n > 0 else a

CELLS = [[cut(c, r) for c in range(58)] for r in range(16)]

def hexcols(i):
    base = (10 + 3*i) if i < 8 else (34 + 3*(i-8))
    return base, base + 1

def score(page, polarity):
    s = 0.0
    for r in range(16):
        for i in range(16):
            hi, lo = f'{page[r*16+i]:02X}'
            a, b = hexcols(i)
            s += float((CELLS[r][a]*tmpl[hi]).sum())
            s += float((CELLS[r][b]*tmpl[lo]).sum())
    return polarity*s/512.0

tr = {p['base_address']: p for p in json.load(open(TRANS))}
tab = open(TABLE, 'rb').read(); prg = open(PROG, 'rb').read()

cands = {'PHOTO TRANSCRIPTION 0x48000000':
         bytes(int(b, 16) for row in tr['48000000']['rows'] for b in row['bytes']),
         'table.rom   0x48000000': tab[0:256],
         'program.rom 0x48400000': prg[0:256]}
for off in (0x19000, 0x39000, 0x49000, 0x159000, 0x100, 0x200):
    cands[f'table.rom   0x{0x48000000+off:08X}'] = tab[off:off+256]
for off in (0x100, 0x1000, 0x10000, 0x100000, 0x200000):
    cands[f'program.rom 0x{0x48400000+off:08X}'] = prg[off:off+256]
rng = np.random.default_rng(0)
cands['RANDOM BYTES (null)'] = bytes(rng.integers(0, 256, 256).tolist())
cands['ALL ZERO (null)'] = bytes(256)

# polarity: whichever sign makes the ADDRESS COLUMN score positive.  The address
# column is known ground truth in every frame: row r prints base + 0x10*r.
def addr_score(base, polarity):
    s = 0.0
    for r in range(16):
        txt = f'{base + 0x10*r:08X}'
        for c in range(8):
            s += float((CELLS[r][c]*tmpl[txt[c]]).sum())
    return polarity*s/128.0

pol = 1.0 if addr_score(0x48000000, 1.0) > 0 else -1.0
print(f'polarity chosen from the address ladder: {pol:+.0f}')
print()
print('ADDRESS-COLUMN check (the calibration asset -- 128 known characters):')
for base in (0x48000000, 0x48400000, 0x48040000, 0x40000000, 0x48000100):
    print(f'   base 0x{base:08X}   mean template match = {addr_score(base, pol):+.4f}')
print()
print('DATA-AREA check (512 characters per candidate):')
for name, page in sorted(cands.items(), key=lambda kv: -score(kv[1], pol)):
    print(f'   {name:<34s} {score(page, pol):+.4f}')
