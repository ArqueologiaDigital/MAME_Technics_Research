#!/usr/bin/env python3
"""wavpitch.py TRACE WAV -- do the notes the rig played come out at the right pitch?

QUESTION: in a -wavwrite capture of a tg_trace.lua run, what is the fundamental of each
held note, compared with the key that was pressed (C4 = 261.63 Hz, equal temperament,
A4 = 440)? Also the level and clipping of each note.

For each "ON <group> <key>" .. "OFF" window of the trace, the capture from ON+0.25 s to OFF
is analysed: the fundamental is the period with the highest harmonic sum (8 harmonics)
within +-0.6 octave of the key's frequency, on a 16x zero-padded spectrum. The error is in
cents. Octave-shifted sounds (bass and organ footages) show as +-1200.
Channels: the loudest one is used. RUN: python3 wavpitch.py trace.txt o.wav
"""
import sys
import wave
import numpy as np

NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def key_midi(k):
    name, octave = k[:-1], int(k[-1])
    return 12 * (octave + 1) + NAMES.index(name)


def f0(x, fs, fexp, span=0.6):
    x = (x - x.mean()) * np.hanning(len(x))
    N = 1 << int(np.ceil(np.log2(len(x) * 16)))
    X = np.abs(np.fft.rfft(x, N))
    best = None
    for f in np.exp(np.linspace(np.log(fexp) - span * np.log(2), np.log(fexp) + span * np.log(2), 2400)):
        idx = (np.arange(1, 9) * f * N / fs).round().astype(int)
        idx = idx[idx < len(X)]
        sc = np.log(X[idx] + 1e-6).mean()
        if best is None or sc > best[0]:
            best = (sc, f)
    return best[1]


def main(trace, wav):
    w = wave.open(wav)
    fs, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
    a = np.frombuffer(w.readframes(n), dtype='<i2').reshape(-1, ch).astype(np.float64)
    c = int(np.argmax((a ** 2).sum(axis=0)))
    x = a[:, c]
    on = None
    rows = []
    for line in open(trace):
        p = line.split()
        if p and p[0] == '#' and len(p) >= 5 and p[2] in ('ON', 'OFF'):
            t = float(p[1])
            if p[2] == 'ON':
                on = (t, p[3], p[4])
            elif on:
                t0, g, k = on
                seg = x[int((t0 + 0.25) * fs): int(t * fs)]
                if len(seg) > 1000:
                    fe = 440.0 * 2 ** ((key_midi(k) - 69) / 12)
                    if np.sqrt((seg ** 2).mean()) < 30:
                        rows.append((g, k, None, 0, 0, 0))
                    else:
                        f = f0(seg, fs, fe)
                        rows.append((g, k, 1200 * np.log2(f / fe), np.sqrt((seg ** 2).mean()),
                                     np.abs(seg).max(), int((np.abs(seg) >= 32767).sum())))
                on = None
    for g, k, cents, rms, peak, clip in rows:
        if cents is None:
            print('%-9s %-4s  silent' % (g, k))
        else:
            print('%-9s %-4s  %+7.1f cents   rms %6.0f  peak %5.0f  clipped %d' % (g, k, cents, rms, peak, clip))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
