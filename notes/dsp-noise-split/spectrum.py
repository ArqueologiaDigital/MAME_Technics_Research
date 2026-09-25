#!/usr/bin/env python3
"""Spectral check: is the instrument output noisy, and does the DSP make it so?

The zero-crossing proxy in analyse_audio.py is crude. This takes the loudest
one-second window and reports where the energy actually sits, by band.

That band table is the whole answer. A first version of this script also printed a
"non-harmonic residue" against the strongest peak -- that figure is meaningless on
the chord this stimulus plays, because the other two notes' partials are not
harmonics of the first and were being counted as noise. It read 65% for an output
with no measurable energy above 1 kHz. It is gone; do not reintroduce it without a
monophonic stimulus.

Usage: spectrum.py a.wav [b.wav ...]
"""
import struct
import sys
import wave

import numpy as np


def instrument(path):
    w = wave.open(path)
    n, ch, sr = w.getnframes(), w.getnchannels(), w.getframerate()
    s = np.frombuffer(w.readframes(n), dtype="<i2").reshape(-1, ch)
    return s[:, 0].astype(float), sr


def main(paths):
    for p in paths:
        x, sr = instrument(p)
        # loudest one-second window: that is where the notes are
        step = sr // 4
        best = max(range(0, len(x) - sr, step), key=lambda i: np.abs(x[i:i + sr]).mean())
        seg = x[best:best + sr] * np.hanning(sr)
        mag = np.abs(np.fft.rfft(seg))
        freq = np.fft.rfftfreq(sr, 1.0 / sr)
        tot = (mag ** 2).sum()
        f0 = freq[1 + int(np.argmax(mag[1:]))]
        hf = (mag[freq >= 1000] ** 2).sum() / tot
        bands = [(0, 200), (200, 1000), (1000, 4000), (4000, 12000), (12000, 24000)]
        frac = ["%s-%sHz %4.1f%%" % (lo, hi,
                100 * (mag[(freq >= lo) & (freq < hi)] ** 2).sum() / tot) for lo, hi in bands]
        print("%-16s window@%5.1fs  strongest %6.1f Hz  energy above 1 kHz %5.2f%%"
              % (p.split("/")[-1], best / sr, f0, 100 * hf))
        print("                 " + "  ".join(frac))


if __name__ == "__main__":
    main(sys.argv[1:])
