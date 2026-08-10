#!/usr/bin/env python3
"""Recover the TRUE capture sampling grid, and the noise level, from the screenshot."""
import numpy as np
from PIL import Image

FRAME = '/home/fsanches/compartilhado/KN7000/photos/1st-frame-grabbed.png'
rgb = np.asarray(Image.open(FRAME).convert('RGB')).astype(np.float64)
y = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]

FLATS = {
    'navy background (flat)':      (slice(92, 104),  slice(250, 850)),
    'navy background right side':  (slice(200, 400), slice(950, 1030)),
    'panel grey below last row':   (slice(402, 412), slice(200, 860)),
    'blue title bar':              (slice(30, 55),   slice(300, 850)),
}

def hp1(block, axis, k=15):
    ker = np.ones(k) / k
    sm = np.apply_along_axis(lambda v: np.convolve(v, ker, 'same'), axis, block)
    d = block - sm
    m = k // 2
    return d[:, m:-m] if axis == 1 else d[m:-m, :]

def acorr(d, axis, nlag=7):
    d = d - d.mean()
    out = []
    for L in range(nlag):
        x = (d[:, :d.shape[1]-L] * d[:, L:]) if axis == 1 else (d[:d.shape[0]-L, :] * d[L:, :])
        out.append(x.mean())
    out = np.array(out)
    return out / out[0]

print('%-30s %8s %8s   %s' % ('region', 'std', 'hp-std', 'horizontal noise acorr lags 0..6'))
for name, (rs, cs) in FLATS.items():
    b = y[rs, cs]
    dh = hp1(b, 1)
    ah = acorr(dh, 1)
    print('%-30s %8.2f %8.2f   %s' % (name, b.std(), dh.std(),
          ' '.join(f'{v:+.3f}' for v in ah)))
    if b.shape[0] >= 33:
        dv = hp1(b, 0)
        av = acorr(dv, 0)
        print('%-30s %8s %8s   %s' % ('', '', '(vert)', ' '.join(f'{v:+.3f}' for v in av)))

print()
print('8x8 JPEG BLOCKING TEST (MJPEG capture leaves a period-8 grid on the SOURCE raster)')
# blockiness metric: mean |second difference| across columns, folded modulo a candidate period
band = y[120:430, 150:900]
d2 = np.abs(band[:, 2:] - 2*band[:, 1:-1] + band[:, :-2]).mean(axis=0)
for period_src in (8,):
    for scale, srcname in ((1029/702.0, '720-wide source'), (1029/640.0, '640-wide source')):
        p = period_src * scale
        idx = np.arange(len(d2))
        phase = (idx % p).astype(int)
        prof = np.array([d2[phase == k].mean() for k in range(int(p))])
        contrast = (prof.max() - prof.min()) / prof.mean()
        print(f'  period {p:5.2f} screenshot px ({srcname}): '
              f'phase contrast {contrast*100:5.1f}%   profile ' +
              ' '.join(f'{v:.2f}' for v in prof))
# control: a period that has no physical meaning
for p in (7.0, 9.0, 11.0, 13.0):
    idx = np.arange(len(d2)); phase = (idx % p).astype(int)
    prof = np.array([d2[phase == k].mean() for k in range(int(p))])
    print(f'  control period {p:4.1f}: phase contrast {(prof.max()-prof.min())/prof.mean()*100:5.1f}%')
