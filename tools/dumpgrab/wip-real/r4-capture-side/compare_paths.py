#!/usr/bin/env python3
"""Apples-to-apples: how much detail does each capture path deliver, per NATIVE LCD pixel?

Both sources show the SAME screen (page 0x48000000 of the same instrument), so the
only thing that differs is the path:  LCD -> composite -> grabber -> preview -> screenshot
versus                                LCD -> phone camera -> JPEG.

Scale is established from the screen's own geometry (character pitch 6 native px,
row pitch 9 native px), so no assumption about the capture resolution is needed.
"""
import numpy as np
from PIL import Image

def luma(path):
    a = np.asarray(Image.open(path).convert('RGB')).astype(np.float64)
    return 0.299*a[:,:,0] + 0.587*a[:,:,1] + 0.114*a[:,:,2]

def pitch(prof, lo, hi):
    """dominant period of a 1-D profile, by FFT, searched in [lo,hi] samples"""
    p = np.asarray(prof, float); p = p - p.mean()
    F = np.abs(np.fft.rfft(p*np.hanning(len(p))))
    f = np.fft.rfftfreq(len(p))
    ok = (f > 1/hi) & (f < 1/lo)
    i = np.argmax(np.where(ok, F, 0))
    # parabolic refine
    if 0 < i < len(F)-1:
        y0,y1,y2 = F[i-1],F[i],F[i+1]
        d = 0.5*(y0-y2)/(y0-2*y1+y2+1e-12)
        fi = f[i] + d*(f[1]-f[0])
    else:
        fi = f[i]
    return 1.0/fi

def rise1090(prof):
    p = np.asarray(prof, float)
    lo, hi = p[:2].mean(), p[-2:].mean()
    if hi < lo: p = -p; lo, hi = -lo, -hi
    n = (p-lo)/(hi-lo)
    def cross(t):
        for i in range(len(n)-1):
            if (n[i]-t)*(n[i+1]-t) <= 0 and n[i+1]!=n[i]:
                return i + (t-n[i])/(n[i+1]-n[i])
        return None
    a,b = cross(0.1), cross(0.9)
    return (b-a) if (a is not None and b is not None) else float('nan')

def modulation(prof):
    """Michelson contrast of a periodic profile -- how much of the pattern survived"""
    p = np.asarray(prof, float)
    return (p.max()-p.min())/(p.max()+p.min()+1e-9)

print('=' * 78)
print('A. COMPOSITE  (photos/1st-frame-grabbed.png, gnome-screenshot of a preview)')
print('=' * 78)
y = luma('/home/fsanches/compartilhado/KN7000/photos/1st-frame-grabbed.png')
# character pitch from the hex area (16 rows of 75 cells, cell pitch = 6 native px)
hexband = y[120:430, 250:880]
cp = pitch(np.abs(np.diff(hexband, axis=1)).mean(axis=0), 5, 20)
# row pitch from the address column
addr = y[112:420, 155:250]
rp = pitch(addr.mean(axis=1), 8, 40)
print(f'  character pitch {cp:6.2f} px  -> {cp/6:5.3f} capture px per NATIVE px (horizontal)')
print(f'  row       pitch {rp:6.2f} px  -> {rp/9:5.3f} capture px per NATIVE px (vertical)')
sxc, syc = cp/6, rp/9
r_h = rise1090(y[130:430, 138:160].mean(axis=0))          # panel left edge
r_v = rise1090(y[104:126, 300:800].mean(axis=1))          # panel top edge
print(f'  10-90% edge rise  horizontal {r_h:5.2f} px = {r_h/sxc:5.2f} NATIVE px')
print(f'  10-90% edge rise  vertical   {r_v:5.2f} px = {r_v/syc:5.2f} NATIVE px')
print()

print('=' * 78)
print('B. PHONE PHOTO  (photos/dump-via-debug/photo_5170298038159870981_y.jpg,')
print('   the SAME page 0x48000000 -- this is the source of the ground-truth transcription)')
print('=' * 78)
p = luma('/home/fsanches/compartilhado/KN7000/photos/dump-via-debug/photo_5170298038159870981_y.jpg')
hexband_p = p[160:640, 280:1150]
cpp = pitch(np.abs(np.diff(hexband_p, axis=1)).mean(axis=0), 8, 40)
addr_p = p[155:645, 75:210]
rpp = pitch(addr_p.mean(axis=1), 15, 60)
print(f'  character pitch {cpp:6.2f} px  -> {cpp/6:5.3f} photo px per NATIVE px (horizontal)')
print(f'  row       pitch {rpp:6.2f} px  -> {rpp/9:5.3f} photo px per NATIVE px (vertical)')
sxp, syp = cpp/6, rpp/9
r_hp = rise1090(p[200:620, 48:78].mean(axis=0))      # panel left border, dark -> light
r_vp = rise1090(p[130:165, 300:1100].mean(axis=1))   # panel top border
print(f'  10-90% edge rise  horizontal {r_hp:5.2f} px = {r_hp/sxp:5.2f} NATIVE px')
print(f'  10-90% edge rise  vertical   {r_vp:5.2f} px = {r_vp/syp:5.2f} NATIVE px')
print()

print('=' * 78)
print('C. THE NUMBER THAT MATTERS: modulation of the 6-native-px character comb')
print('   (how much of the per-character structure is left after the path)')
print('=' * 78)
for name, band, sx in (('composite', hexband, sxc), ('phone photo', hexband_p, sxp)):
    prof = np.abs(np.diff(band, axis=1)).mean(axis=0)
    # fold on the measured character pitch
    per = sx*6
    idx = np.arange(len(prof))
    ph = ((idx % per) / per * 24).astype(int) % 24
    folded = np.array([prof[ph == k].mean() for k in range(24)])
    print(f'  {name:<12s} character-comb modulation {modulation(folded)*100:5.1f} %')
    # and the 3-native-px (half-character) comb, the one that separates glyph strokes
    per3 = sx*3
    ph3 = ((idx % per3)/per3*12).astype(int) % 12
    f3 = np.array([prof[ph3 == k].mean() for k in range(12)])
    print(f'  {name:<12s} 3-native-px comb modulation {modulation(f3)*100:5.1f} %')
