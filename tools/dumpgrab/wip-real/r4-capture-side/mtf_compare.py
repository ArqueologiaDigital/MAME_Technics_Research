#!/usr/bin/env python3
"""Relative MTF of the two capture paths, measured on the SAME printed text.

The address column prints "480000" in all 16 rows of page 0x48000000, in the screen's
own 5x7 font on a 6-px cell.  That is the same signal in both images, so the ratio of
their horizontal spectra is the ratio of the two paths' MTFs.  Frequency is expressed
in cycles per NATIVE LCD pixel using each image's own measured character pitch, so no
registration and no assumption about capture resolution is needed.
"""
import numpy as np
from PIL import Image

def luma(p):
    a = np.asarray(Image.open(p).convert('RGB')).astype(np.float64)
    return 0.299*a[:,:,0] + 0.587*a[:,:,1] + 0.114*a[:,:,2]

def peak_period(prof, lo, hi):
    p = np.asarray(prof, float); p = p - p.mean()
    F = np.abs(np.fft.rfft(p*np.hanning(len(p)), n=8192))
    f = np.fft.rfftfreq(8192)
    ok = (f > 1/hi) & (f < 1/lo)
    i = int(np.argmax(np.where(ok, F, 0)))
    return 1.0/f[i]

def band_spectrum(rows, px_per_native, fmax=0.55):
    """mean |FFT| over the rows, on a cycles-per-native-pixel axis"""
    b = np.asarray(rows, float)
    b = b - b.mean(axis=1, keepdims=True)
    n = 8192
    F = np.abs(np.fft.rfft(b*np.hanning(b.shape[1]), n=n, axis=1)).mean(axis=0)
    f = np.fft.rfftfreq(n) * px_per_native          # cycles per NATIVE px
    m = f <= fmax
    return f[m], F[m]

# ---------- A. composite ----------
yc = luma('/home/fsanches/compartilhado/KN7000/photos/1st-frame-grabbed.png')
SXc = 1029/640.0; SYc = 491/240.0; X0, Y0 = 11.0, 14.0
# sanity: the character pitch must come out at 6 native px
prof = np.abs(np.diff(yc[130:420, 250:880], axis=1)).mean(axis=0)
pc = peak_period(prof, 8, 12)
print(f'composite  : measured character pitch {pc:.3f} capture px  '
      f'= {pc/SXc:.3f} native px  (expected 6.000)')
rows_c = []
for r in range(16):
    t = Y0 + (55 + 9*r)*SYc
    rows_c.append(yc[int(round(t)):int(round(t+7*SYc)), int(X0+88*SXc):int(X0+140*SXc)].mean(axis=0))
L = min(len(r) for r in rows_c); rows_c = [r[:L] for r in rows_c]
fc, Fc = band_spectrum(rows_c, SXc)

# ---------- B. phone photo ----------
yp = luma('/home/fsanches/compartilhado/KN7000/photos/dump-via-debug/photo_5170298038159870981_y.jpg')
# character pitch measured on the ADDRESS COLUMN itself (avoids perspective drift)
pp = peak_period(np.abs(np.diff(yp[165:640, 70:215], axis=1)).mean(axis=0), 14, 30)
SXp = pp/6.0
rowprof = yp[150:650, 70:215].mean(axis=1)
rpp = peak_period(rowprof, 20, 45)
SYp = rpp/9.0
print(f'phone photo: measured character pitch {pp:.3f} photo px  = 6.000 native px by construction')
print(f'             row pitch {rpp:.2f} photo px  -> {SXp:.3f} px/native-col, {SYp:.3f} px/native-line')
# find the first row top by matched filter on the row profile
best, bestv = 0, -1e18
for off in np.arange(0, rpp, 0.25):
    idx = (np.arange(15)*rpp + off + 3.5*SYp).astype(int)
    idx = idx[(idx >= 0) & (idx < len(rowprof))]
    v = -rowprof[idx].mean()          # row centres are DARK (ink)
    if v > bestv: bestv, best = v, off
rows_p = []
for r in range(15):
    t = 150 + best + rpp*r
    rows_p.append(yp[int(round(t)):int(round(t+7*SYp)), 70:215].mean(axis=0))
L = min(len(r) for r in rows_p); rows_p = [r[:L] for r in rows_p]
fp, Fp = band_spectrum(rows_p, SXp)
print()

def at(f, F, t):
    i = int(np.argmin(np.abs(f-t))); return F[i], f[i]

nc = at(fc, Fc, 1/6.)[0]; npv = at(fp, Fp, 1/6.)[0]
print('  MTF normalised to 1.0 at the character fundamental (1/6 cyc per native px)')
print('  cyc/native px   period      composite    phone photo   photo/composite')
for t in (1/12., 1/6., 0.25, 1/3., 0.40, 0.45, 0.50):
    a, fa = at(fc, Fc, t); b, fb = at(fp, Fp, t)
    print(f'      {t:5.3f}       {1/t:5.2f} px    {a/nc:8.3f}     {b/npv:8.3f}      {b/npv/(a/nc):7.2f}x')
print()
print('  Nyquist of each path, in native px:  composite '
      f'{1/(2/SXc):.2f} native px period   photo {1/(2/SXp):.2f} native px period')
