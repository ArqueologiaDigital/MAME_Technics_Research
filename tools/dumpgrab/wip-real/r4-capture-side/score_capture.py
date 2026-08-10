#!/usr/bin/env python3
"""score_capture.py -- put a number on a KN7000 MEMORY DUMP capture.

The point of this tool is that every capture-side change (PAL vs NTSC, 720x480 vs
640x480, YUYV vs MJPEG, sharpening on/off, a different grabber, a phone photo) becomes
an A/B you can *measure* in ten seconds instead of an opinion.  It never decodes bytes;
it measures how much of the screen's own structure survived the path.

    ./score_capture.py FRAME.png [FRAME.png ...]        one or more stills
    ./score_capture.py --dir DIR/                       every image in a directory
    ./score_capture.py --video FILE.mkv --frames 60     pull frames with ffmpeg first

What it reports, all in units of NATIVE LCD PIXELS so two captures at different
resolutions are directly comparable (the KN7000 LCD is 640x240; the dump panel is
465x161 native px; the character cell is 6x9 with a 5x7 glyph -- doc/GEOMETRY.txt):

  sampling      capture px per native px, horizontal and vertical.  Below 1.0 you are
                under-sampling the screen and no software can undo it.
  edge rise     10-90 % rise of a hard screen edge, in native px.  1.0 means the path
                resolves individual LCD pixels; 2.0 means neighbouring pixels merge.
  MTF           surviving contrast at the 6 / 4 / 3 / 2.5 / 2 native-px periods,
                normalised to the 6 px character pitch.  The 2 px figure is the one
                that decides whether adjacent glyph strokes can ever be separated.
  chroma        whether the four highlight colours are still distinguishable, and
                whether the legend text on top of them survived.
  interlace     even/odd scanline parity structure -- tells you if the device is
                weaving, bobbing or blending fields.
  temporal      frame-to-frame noise and sub-pixel drift (>= 2 frames).  Noise sets
                how far frame averaging can take you; drift says whether averaging can
                also buy resolution.

Dependencies: python3, numpy, Pillow.  ffmpeg only for --video.  No OpenCV.
"""

from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

# ---- the screen, in its own native pixels (kn7000_mame/tools/dumpgrab/doc/GEOMETRY.txt)
LCD_W, LCD_H = 640, 240
PANEL = (84, 49, 548, 209)          # x0, y0, x1, y1 of the grey dump panel
CELL_X0, CELL_Y0 = 90, 55           # first character cell
CPX, RPY = 6, 9                     # character pitch, row pitch
GLYPH_W, GLYPH_H = 5, 7
NROWS = 16
ADDR_COLS = 8                       # the address ladder: 8 hex digits, all 16 rows


# ------------------------------------------------------------------ image helpers
def load_luma(path):
    a = np.asarray(Image.open(path).convert('RGB')).astype(np.float64)
    y = 0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]
    cb = -0.168736 * a[:, :, 0] - 0.331264 * a[:, :, 1] + 0.5 * a[:, :, 2]
    cr = 0.5 * a[:, :, 0] - 0.418688 * a[:, :, 1] - 0.081312 * a[:, :, 2]
    return y, cb, cr


def _longest_run(mask, gap):
    idx = np.where(mask)[0]
    if len(idx) == 0:
        return 0, len(mask)
    best = (idx[0], idx[0])
    s = prev = idx[0]
    for i in idx[1:]:
        if i - prev > gap:
            if prev - s > best[1] - best[0]:
                best = (s, prev)
            s = i
        prev = i
    if prev - s > best[1] - best[0]:
        best = (s, prev)
    return best[0], best[1] + 1


def find_panel(y):
    """Locate the light dump panel inside the dark UI.

    The panel is the largest bright block on the screen and it is the only bright thing
    that is bright across nearly its whole width for many consecutive rows.  Returns
    (x0, x1, y0, y1) in capture pixels.
    """
    def smooth(v, k):
        k = max(3, int(k) | 1)
        return np.convolve(v, np.ones(k) / k, 'same')

    # The panel BACKGROUND is light everywhere inside the panel, whatever the text
    # density, so use a high per-line percentile rather than a mean: it tracks the
    # paper, not the ink.
    thr = 0.42 * np.percentile(y, 99.5)
    ro = smooth((np.percentile(y, 75, axis=1) > thr).astype(float), y.shape[0] * 0.04)
    gap = max(3, y.shape[0] // 60)
    ry0, ry1 = _longest_run(ro > 0.5, gap)
    band = y[ry0:ry1]
    co = smooth((np.percentile(band, 75, axis=0) > thr).astype(float), y.shape[1] * 0.01)
    rx0, rx1 = _longest_run(co > 0.5, max(3, y.shape[1] // 60))

    # refine each border to the steepest gradient nearby -- the coarse pass can sit a
    # few pixels inside, and every scale below is derived from these four numbers
    def refine(prof, pos, halfwin, sign):
        a = max(0, int(pos - halfwin)); b = min(len(prof), int(pos + halfwin) + 1)
        if b - a < 5:
            return pos
        d = sign * np.gradient(prof[a:b])
        return a + int(np.argmax(d))

    sx_guess = (rx1 - rx0) / float(PANEL[2] - PANEL[0])
    sy_guess = (ry1 - ry0) / float(PANEL[3] - PANEL[1])
    colprof = np.percentile(y[ry0:ry1], 75, axis=0)
    rowprof = np.percentile(y[:, rx0:rx1], 75, axis=1)
    rx0 = refine(colprof, rx0, 14 * sx_guess, +1)
    rx1 = refine(colprof, rx1, 14 * sx_guess, -1)
    ry0 = refine(rowprof, ry0, 14 * sy_guess, +1)
    ry1 = refine(rowprof, ry1, 14 * sy_guess, -1)
    return rx0, rx1, ry0, ry1


def peak_period(prof, lo, hi):
    p = np.asarray(prof, float)
    p = p - p.mean()
    n = 8192
    F = np.abs(np.fft.rfft(p * np.hanning(len(p)), n=n))
    f = np.fft.rfftfreq(n)
    ok = (f > 1.0 / hi) & (f < 1.0 / lo)
    if not ok.any():
        return float('nan')
    i = int(np.argmax(np.where(ok, F, 0)))
    return 1.0 / f[i] if f[i] > 0 else float('nan')


def rise_1090(prof):
    p = np.asarray(prof, float)
    if len(p) < 5:
        return float('nan')
    lo, hi = p[:2].mean(), p[-2:].mean()
    if hi < lo:
        p, lo, hi = -p, -lo, -hi
    if hi - lo < 4:
        return float('nan')
    n = (p - lo) / (hi - lo)

    def cross(t):
        for i in range(len(n) - 1):
            if (n[i] - t) * (n[i + 1] - t) <= 0 and n[i + 1] != n[i]:
                return i + (t - n[i]) / (n[i + 1] - n[i])
        return None

    a, b = cross(0.1), cross(0.9)
    return (b - a) if (a is not None and b is not None) else float('nan')


# ------------------------------------------------------------------ the measurements
def geometry(y):
    px0, px1, py0, py1 = find_panel(y)
    sx = (px1 - px0) / float(PANEL[2] - PANEL[0])
    sy = (py1 - py0) / float(PANEL[3] - PANEL[1])
    # origin of the LCD in capture coordinates
    ox = px0 - PANEL[0] * sx
    oy = py0 - PANEL[1] * sy
    return dict(sx=sx, sy=sy, ox=ox, oy=oy, panel=(px0, px1, py0, py1))


def check_pitch(y, g):
    """The character pitch must come out at 6 native px; if it does not, the panel fit
    is wrong and every number below is meaningless."""
    px0, px1, py0, py1 = g['panel']
    band = y[py0 + int(3 * g['sy']):py1 - int(12 * g['sy']),
             px0 + int(60 * g['sx']):px1 - int(20 * g['sx'])]
    if band.size == 0 or band.shape[1] < 40:
        return float('nan')
    prof = np.abs(np.diff(band, axis=1)).mean(axis=0)
    p = peak_period(prof, 0.75 * CPX * g['sx'], 1.35 * CPX * g['sx'])
    return p / g['sx']


def edge_rises(y, g):
    px0, px1, py0, py1 = g['panel']
    w = max(6, int(round(12 * g["sx"])))
    hh = max(6, int(round(10 * g["sy"])))
    ys = slice(py0 + int(10 * g['sy']), py1 - int(20 * g['sy']))
    left = y[ys, max(px0 - w, 0):px0 + w].mean(axis=0)
    right = y[ys, max(px1 - w, 0):min(px1 + w, y.shape[1])].mean(axis=0)[::-1]
    xs = slice(px0 + int(60 * g['sx']), px1 - int(60 * g['sx']))
    top = y[max(py0 - hh, 0):py0 + hh, xs].mean(axis=1)
    rh = np.nanmean([rise_1090(left), rise_1090(right)]) / g['sx']
    rv = rise_1090(top) / g['sy']
    return rh, rv


def address_band(y, g):
    """The 16 rows of the address ladder -- the same 8 characters, known a priori."""
    rows = []
    x0 = g['ox'] + (CELL_X0 - 2) * g['sx']
    x1 = g['ox'] + (CELL_X0 + ADDR_COLS * CPX + 2) * g['sx']
    for r in range(NROWS):
        t = g['oy'] + (CELL_Y0 + RPY * r) * g['sy']
        seg = y[int(round(t)):int(round(t + GLYPH_H * g['sy'])),
                int(round(x0)):int(round(x1))]
        if seg.size:
            rows.append(seg.mean(axis=0))
    if not rows:
        return None
    L = min(len(r) for r in rows)
    return np.array([r[:L] for r in rows])


def mtf(y, g):
    band = address_band(y, g)
    if band is None or band.shape[1] < 16:
        return {}
    b = band - band.mean(axis=1, keepdims=True)
    n = 8192
    F = np.abs(np.fft.rfft(b * np.hanning(b.shape[1]), n=n, axis=1)).mean(axis=0)
    f = np.fft.rfftfreq(n) * g['sx']           # cycles per NATIVE px
    nyq = 0.5 * g['sx']                        # sampling Nyquist, cycles per native px

    def at(t):
        if t > nyq:
            return float('nan')
        return float(F[int(np.argmin(np.abs(f - t)))])

    ref = at(1.0 / CPX)
    out = {}
    for period in (6.0, 4.0, 3.0, 2.5, 2.0):
        v = at(1.0 / period)
        out[period] = (v / ref) if (ref > 0 and v == v) else float('nan')
    out['nyquist_period_native_px'] = 1.0 / nyq if nyq > 0 else float('inf')
    # Noise floor: the same spectrum measured on the text-free strip of panel background
    # between the panel's top border and the first text row (native y 50..54).
    t0 = int(round(g['oy'] + 50 * g['sy']))
    t1 = int(round(g['oy'] + 54.5 * g['sy']))
    x0 = int(round(g['ox'] + (CELL_X0 - 2) * g['sx']))
    x1 = x0 + band.shape[1]
    flat = y[t0:t1, x0:x1]
    if flat.shape[0] >= 2 and flat.shape[1] == band.shape[1]:
        Ff = np.abs(np.fft.rfft((flat - flat.mean(axis=1, keepdims=True)) *
                                np.hanning(flat.shape[1]), n=n, axis=1)).mean(axis=0)
        lo = min(1.0 / 3.0, nyq * 0.9)
        hi = (f >= lo) & (f <= nyq)
        out['noise_floor'] = float(Ff[hi].mean() / ref) if ref > 0 and hi.any() else float('nan')
    return out


def chroma(y, cb, cr, g):
    """The four highlight colours and the legend row that names them."""
    t = g['oy'] + (CELL_Y0 + RPY * NROWS) * g['sy']
    ys = slice(int(round(t)), int(round(t + GLYPH_H * g['sy'])))
    px0, px1, _, _ = g['panel']
    xs = slice(px0 + 4, px1 - 4)
    if ys.stop > y.shape[0]:
        return {}
    sat = np.sqrt(cb[ys, xs] ** 2 + cr[ys, xs] ** 2)
    # cluster the legend strip's columns into colour blocks and report their separation
    col_cb, col_cr = cb[ys, xs].mean(axis=0), cr[ys, xs].mean(axis=0)
    pts = np.stack([col_cb, col_cr], axis=1)
    strong = pts[np.sqrt((pts ** 2).sum(axis=1)) > 20]
    # legend TEXT legibility: high-frequency luma contrast on the strip, relative to
    # the same measure over the grey hex area (where the text is definitely legible)
    def hf(block):
        if block.shape[1] < 8:
            return float('nan')
        d = np.abs(np.diff(block, axis=1))
        return float(d.mean())
    leg_hf = hf(y[ys, xs])
    t2 = g['oy'] + (CELL_Y0 + RPY * 3) * g['sy']
    hex_hf = hf(y[int(t2):int(t2 + GLYPH_H * g['sy']), xs])
    return dict(max_sat=float(sat.max()), mean_sat=float(sat.mean()),
                n_saturated_cols=int(len(strong)),
                legend_text_hf=leg_hf, hex_text_hf=hex_hf,
                legend_over_hex=(leg_hf / hex_hf) if hex_hf else float('nan'))


def interlace(y, g):
    px0, px1, py0, py1 = g['panel']
    reg = y[py0 + 4:py1 - 4, px0 + 4:px1 - 4]
    if reg.shape[0] < 8:
        return {}
    d1 = np.abs(np.diff(reg, axis=0)).mean(axis=1)
    d2 = float(np.abs(reg[2:] - reg[:-2]).mean())
    even, odd = float(d1[0::2].mean()), float(d1[1::2].mean())
    return dict(adjacent_even=even, adjacent_odd=odd, two_apart=d2,
                parity_asymmetry=abs(even - odd) / max(even, odd, 1e-9),
                adjacent_over_two_apart=(0.5 * (even + odd)) / max(d2, 1e-9))


def temporal(frames, g):
    """Frame-to-frame noise and sub-pixel drift, over frames of the SAME page."""
    if len(frames) < 2:
        return {}
    px0, px1, py0, py1 = g['panel']
    stack = np.array([f[py0 + 4:py1 - 4, px0 + 4:px1 - 4] for f in frames])
    # keep only frames that look like the same, settled page (reject repaint tears)
    ref = stack[0]
    keep = [0]
    for i in range(1, len(stack)):
        if np.abs(stack[i] - ref).mean() < 3 * np.abs(np.diff(ref, axis=1)).mean():
            keep.append(i)
    s = stack[keep]
    noise = float(s.std(axis=0).mean())
    # sub-pixel horizontal drift, by parabolic fit of the cross-correlation peak
    def shift(a, b):
        a = a.mean(axis=0) - a.mean()
        b = b.mean(axis=0) - b.mean()
        c = np.correlate(a, b, 'full')
        i = int(np.argmax(c))
        if 0 < i < len(c) - 1:
            y0, y1, y2 = c[i - 1], c[i], c[i + 1]
            d = 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2 + 1e-12)
        else:
            d = 0.0
        return (i + d) - (len(a) - 1)

    drifts = [shift(s[0], s[i]) for i in range(1, len(s))]
    return dict(n_frames=len(frames), n_same_page=len(s), temporal_noise_lsb=noise,
                drift_px_rms=float(np.sqrt(np.mean(np.square(drifts)))) if drifts else 0.0,
                drift_native_rms=(float(np.sqrt(np.mean(np.square(drifts)))) / g['sx'])
                if drifts else 0.0)


# ------------------------------------------------------------------ reporting
def report(paths, label):
    y0, cb0, cr0 = load_luma(paths[0])
    g = geometry(y0)
    pitch = check_pitch(y0, g)
    print('=' * 76)
    print(f'{label}   ({len(paths)} frame(s), first = {os.path.basename(paths[0])},'
          f' {y0.shape[1]}x{y0.shape[0]})')
    print('=' * 76)
    print(f'  panel found at x {g["panel"][0]}..{g["panel"][1]}, '
          f'y {g["panel"][2]}..{g["panel"][3]}')
    print(f'  SAMPLING     {g["sx"]:6.3f} capture px per native px horizontally, '
          f'{g["sy"]:6.3f} vertically')
    print(f'               character pitch measures {pitch:5.3f} native px '
          f'(must be 6.000 +/- 0.05, else the fit is wrong)')
    if not (5.7 < pitch < 6.3):
        print('               *** GEOMETRY FIT FAILED -- numbers below are not trustworthy')
    rh, rv = edge_rises(y0, g)
    print(f'  EDGE RISE    horizontal {rh:5.2f} native px, vertical {rv:5.2f} native px'
          f'   (1.0 = individual LCD pixels resolved)')
    m = mtf(y0, g)
    if m:
        print(f'  MTF          6px {m[6.0]:6.3f} (ref)   4px {m[4.0]:6.3f}   '
              f'3px {m[3.0]:6.3f}   2.5px {m[2.5]:6.3f}   2px {m[2.0]:6.3f}')
        if 'noise_floor' in m:
            print(f'               noise floor {m["noise_floor"]:6.3f}   '
                  f'-> an MTF at or below this is NO information')
        print(f'               sampling Nyquist = {m["nyquist_period_native_px"]:.2f}'
              f' native px period')
    c = chroma(y0, cb0, cr0, g)
    if c:
        print(f'  CHROMA       legend strip max saturation {c["max_sat"]:6.1f}, '
              f'{c["n_saturated_cols"]} strongly coloured columns')
        print(f'               legend text detail / hex text detail = '
              f'{c["legend_over_hex"]:5.2f}   (<0.5 = text on colour is destroyed)')
    it = interlace(y0, g)
    if it:
        print(f'  INTERLACE    adjacent-row diff even {it["adjacent_even"]:5.2f} / '
              f'odd {it["adjacent_odd"]:5.2f} (asymmetry {it["parity_asymmetry"]*100:4.1f}%)'
              f', adjacent/two-apart {it["adjacent_over_two_apart"]:4.2f}')
        print('               asymmetry >20% = fields differ (interlaced source or shear);'
              ' ratio ~0.5 = smooth upscale')
    if len(paths) > 1:
        frames = [load_luma(p)[0] for p in paths]
        t = temporal(frames, g)
        if t:
            print(f'  TEMPORAL     {t["n_same_page"]}/{t["n_frames"]} frames on the same '
                  f'settled page; noise {t["temporal_noise_lsb"]:5.2f} LSB')
            print(f'               sub-pixel drift {t["drift_native_rms"]:.3f} native px RMS'
                  f'   (>0.15 = frame averaging can also buy resolution)')
            if t['temporal_noise_lsb'] > 0.5:
                n = t['n_same_page']
                print(f'               averaging {n} frames would cut noise to '
                      f'{t["temporal_noise_lsb"]/np.sqrt(max(n,1)):.2f} LSB')
    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('images', nargs='*')
    ap.add_argument('--dir', action='append', default=[])
    ap.add_argument('--video')
    ap.add_argument('--frames', type=int, default=40)
    ap.add_argument('--label', default=None)
    a = ap.parse_args()

    paths = list(a.images)
    for d in a.dir:
        for ext in ('png', 'ppm', 'bmp', 'jpg', 'jpeg', 'tif', 'tiff'):
            paths += sorted(glob.glob(os.path.join(d, '*.' + ext)))
    tmp = None
    if a.video:
        tmp = tempfile.mkdtemp(prefix='score_capture_')
        subprocess.run(['ffmpeg', '-v', 'error', '-i', a.video, '-frames:v',
                        str(a.frames), '-f', 'image2',
                        os.path.join(tmp, 'f%05d.png')], check=True)
        paths += sorted(glob.glob(os.path.join(tmp, '*.png')))
    if not paths:
        ap.error('no images')
    report(paths, a.label or (a.video or a.dir[0] if a.dir else paths[0]))


if __name__ == '__main__':
    main()
