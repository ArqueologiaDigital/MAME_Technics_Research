#!/usr/bin/env python3
"""Measure the capture chain's point-spread function from the real KN7000 frame.

Everything here is measured off /home/fsanches/compartilhado/KN7000/photos/1st-frame-grabbed.png
and expressed in NATIVE LCD PIXELS (the KN7000 LCD is 640x240), so the numbers are
independent of whatever the grabber and the preview window did to the scale.
"""
import sys, math
import numpy as np
from PIL import Image

FRAME = '/home/fsanches/compartilhado/KN7000/photos/1st-frame-grabbed.png'

# Geometry solved from the panel: the full 640x240 LCD maps to the content bbox.
X0, Y0 = 11.0, 14.0
SX, SY = (1039 - 11 + 1) / 640.0, (504 - 14 + 1) / 240.0


def load():
    a = np.asarray(Image.open(FRAME).convert('RGB')).astype(np.float64)
    y = 0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]
    # BT.601 colour-difference, the two chroma channels composite actually carries
    cb = -0.168736 * a[:, :, 0] - 0.331264 * a[:, :, 1] + 0.5 * a[:, :, 2]
    cr = 0.5 * a[:, :, 0] - 0.418688 * a[:, :, 1] - 0.081312 * a[:, :, 2]
    return a, y, cb, cr


def esf_sigma(prof, axis_scale, label, invert=False):
    """Fit a Gaussian-blurred step to a 1-D edge profile.

    Returns sigma in NATIVE LCD PIXELS and the 10-90% rise, also in native px.
    """
    p = np.asarray(prof, dtype=float)
    if invert:
        p = -p
    lo, hi = p[:3].mean(), p[-3:].mean()
    if hi - lo < 5:
        return None
    n = (p - lo) / (hi - lo)
    x = np.arange(len(p), dtype=float)
    # LSF = derivative; its RMS width is the PSF sigma
    d = np.gradient(n)
    d = np.clip(d, 0, None)
    if d.sum() <= 0:
        return None
    c = (d * x).sum() / d.sum()
    var = (d * (x - c) ** 2).sum() / d.sum()
    sig_px = math.sqrt(max(var, 0.0))
    # 10-90 rise by interpolation
    def cross(t):
        for i in range(len(n) - 1):
            if (n[i] - t) * (n[i + 1] - t) <= 0 and n[i + 1] != n[i]:
                return i + (t - n[i]) / (n[i + 1] - n[i])
        return None
    a10, a90 = cross(0.1), cross(0.9)
    rise = (a90 - a10) if (a10 is not None and a90 is not None) else float('nan')
    return dict(label=label, sigma_native=sig_px / axis_scale, rise1090_native=rise / axis_scale,
                sigma_capture=sig_px, rise_capture=rise, n=len(p))


def main():
    a, y, cb, cr = load()
    print(f'frame {a.shape[1]}x{a.shape[0]}   LCD 640x240 -> content {SX:.4f} px/native-col, '
          f'{SY:.4f} px/native-line')
    print()

    rows = []

    # --- horizontal luma edge: the dump panel's LEFT edge (dark blue -> light grey),
    #     sampled on rows that are inside the panel body.
    #     panel native x0 = 84 -> capture x = 11 + 84*1.6078 = 146.1
    seg = y[130:430, 132:164]          # 300 rows x 32 cols across the edge
    rows.append(esf_sigma(seg.mean(axis=0), SX, 'H luma: panel LEFT edge (blue->grey)'))

    # --- horizontal luma edge: the dump panel's RIGHT edge (grey -> dark blue)
    seg = y[130:430, 880:912]
    rows.append(esf_sigma(seg.mean(axis=0)[::-1], SX, 'H luma: panel RIGHT edge (grey->blue)'))

    # --- horizontal luma edge: the LCD's own left border (black -> blue) at x~11
    seg = y[60:100, 0:32]
    rows.append(esf_sigma(seg.mean(axis=0), SX, 'H luma: screen LEFT border (black->blue)'))

    # --- vertical luma edge: the dump panel's TOP edge, away from text
    seg = y[100:132, 300:800]
    rows.append(esf_sigma(seg.mean(axis=1), SY, 'V luma: panel TOP edge (blue->grey)'))

    # --- vertical luma edge: the title bar bottom (blue title -> dark background)
    seg = y[60:100, 300:800]
    rows.append(esf_sigma(seg.mean(axis=1)[::-1], SY, 'V luma: title-bar BOTTOM edge'))

    for r in rows:
        if r is None:
            continue
        print(f"{r['label']:<46s} sigma = {r['sigma_native']:5.2f} native px   "
              f"10-90% rise = {r['rise1090_native']:5.2f} native px   "
              f"(capture px: sigma {r['sigma_capture']:.2f}, rise {r['rise_capture']:.2f})")
    print()

    # --- chroma vs luma: the legend colour strip has hard colour edges at constant luma-ish.
    #     Find it: the row band where saturation is extreme.
    sat = np.abs(cb) + np.abs(cr)
    band = sat[:, 160:880].mean(axis=1)
    ymax = int(np.argmax(band))
    print(f'most saturated row band at y={ymax} (legend strip), mean |Cb|+|Cr| = {band[ymax]:.1f}')
    strip = slice(max(ymax - 6, 0), ymax + 7)
    # locate the aqua->yellow transition: Cb goes strongly + (aqua) to - (yellow)
    cbline = cb[strip, :].mean(axis=0)
    crline = cr[strip, :].mean(axis=0)
    yline = y[strip, :].mean(axis=0)
    d = np.abs(np.gradient(cbline))
    # strongest chroma edge inside the panel
    xs = 160 + int(np.argmax(d[160:880]))
    print(f'strongest chroma edge in the legend strip at x={xs}')
    w = 26
    r = esf_sigma(cbline[xs - w:xs + w] * np.sign(cbline[xs + w - 1] - cbline[xs - w]), SX,
                  'H CHROMA: legend colour edge (Cb)')
    if r:
        print(f"{r['label']:<46s} sigma = {r['sigma_native']:5.2f} native px   "
              f"10-90% rise = {r['rise1090_native']:5.2f} native px")
    r = esf_sigma(yline[xs - w:xs + w] * np.sign(yline[xs + w - 1] - yline[xs - w]), SX,
                  'H luma at the SAME edge (for comparison)')
    if r:
        print(f"{r['label']:<46s} sigma = {r['sigma_native']:5.2f} native px   "
              f"10-90% rise = {r['rise1090_native']:5.2f} native px")
    print()

    # --- noise: spatial std in a flat grey area of the panel that has no text
    #     (between the last hex row and the legend strip)
    flat = y[400:412, 200:860]
    hp = flat - np.array([np.convolve(r, np.ones(9) / 9, 'same') for r in flat])
    print(f'flat-field spatial noise (high-passed) std = {hp[:, 6:-6].std():.2f} LSB of 255')

    # --- interlace: for a static picture, line-doubling means row pairs should match.
    #     Which parity pairs?  Measure mean |row_i - row_{i+1}| split by parity of i.
    reg = y[120:430, 160:880]
    dif = np.abs(np.diff(reg, axis=0)).mean(axis=1)
    print(f'row-to-row |diff| : even-index pairs {dif[0::2].mean():.2f}, '
          f'odd-index pairs {dif[1::2].mean():.2f}')
    # compare with the difference between rows two apart
    d2 = np.abs(reg[2:] - reg[:-2]).mean()
    print(f'rows two apart |diff| = {d2:.2f}')

    # --- horizontal frequency response: energy vs spatial frequency in the hex area,
    #     expressed in cycles per native LCD pixel and in MHz on the composite line.
    #     NTSC active line = 52.66 us carrying 640 native columns.
    hex_band = y[120:430, 160:880]
    hp = hex_band - hex_band.mean(axis=1, keepdims=True)
    win = np.hanning(hp.shape[1])
    spec = np.abs(np.fft.rfft(hp * win, axis=1)).mean(axis=0)
    f_cap = np.fft.rfftfreq(hp.shape[1])            # cycles / capture px
    f_nat = f_cap * SX                              # cycles / native px
    mhz = f_nat * 640 / 52.66e-6 / 1e6              # MHz on an NTSC active line
    print()
    print('horizontal spectrum of the hex area (mean magnitude):')
    print('  MHz   cyc/native-px   magnitude')
    for target in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.43, 5.0, 6.0]:
        i = int(np.argmin(np.abs(mhz - target)))
        print(f'  {mhz[i]:4.2f}      {f_nat[i]:.4f}       {spec[i]:8.1f}')


if __name__ == '__main__':
    main()
