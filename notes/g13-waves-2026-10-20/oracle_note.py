#!/usr/bin/env python3
"""oracle_note.py WAV... -- the gate's audio-oracle capture (rigs/money.lua: key C4 held from
t=16 s to t=17 s, 22 s captured), described by numbers.

QUESTION: how loud is the held note, does it clip, what is its pitch, and what is left
after the release? Per capture: rms and peak over t=10-15.5 s (no stimulus), 16-18 s (the
note) and 18-21 s (the tail), clipped samples, and the fundamental of 16.25-17.0 s within
+-0.6 octave of C4 (261.63 Hz; harmonic-sum search on a 16x zero-padded spectrum), in cents.
The loudest channel is used. RUN: python3 oracle_note.py old.wav new.wav
"""
import sys
import wave
import numpy as np


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


for path in sys.argv[1:]:
    w = wave.open(path)
    fs, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
    a = np.frombuffer(w.readframes(n), dtype='<i2').reshape(-1, ch).astype(np.float64)
    c = int(np.argmax((a ** 2).sum(axis=0)))
    x = a[:, c]
    seg = lambda t0, t1: x[int(t0 * fs):int(t1 * fs)]
    out = [path, 'ch%d of %d, %d Hz, %.2f s' % (c, ch, fs, n / fs)]
    for name, t0, t1 in (('quiet 10-15.5', 10, 15.5), ('note 16-18', 16, 18), ('tail 18-21', 18, 21)):
        s = seg(t0, t1)
        out.append('%s: rms %.1f peak %.0f' % (name, np.sqrt((s ** 2).mean()), np.abs(s).max()))
    out.append('clipped samples %d' % int((np.abs(a) >= 32767).sum()))
    fe = 261.6255653
    f = f0(seg(16.25, 17.0), fs, fe)
    out.append('held note %.2f Hz = %+.1f cents from C4' % (f, 1200 * np.log2(f / fe)))
    print('\n   '.join(out))
