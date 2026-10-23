#!/usr/bin/env python3
"""tones.py OUT.wav [T0] -- does the capture carry the mixer test's four sines? Prints, from T0 seconds (default
8: after the test program is applied), the RMS and the level of the strongest FFT bins with their frequencies,
and the level at 220/330/440/660 Hz against the median bin (dB). Reads the last channel: MAME's -wavwrite on the
KN5000 writes three, of which the first is silent and the last two are the left and right speakers."""
import sys
import wave
import numpy as np

w = wave.open(sys.argv[1])
sr, ch = w.getframerate(), w.getnchannels()
x = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').reshape(-1, ch).astype(float)
t0 = float(sys.argv[2]) if len(sys.argv) > 2 else 8.0
x = x[int(t0 * sr):, ch - 1]
print('%.2f s from %.1f s, rms %.1f, peak %d' % (len(x) / sr, t0, np.sqrt((x ** 2).mean()), np.abs(x).max()))
n = 1 << int(np.log2(len(x)))
f = np.abs(np.fft.rfft(x[:n] * np.hanning(n)))
hz = np.fft.rfftfreq(n, 1 / sr)
med = np.median(f) + 1e-9
for k in sorted(np.argsort(f)[-8:]):
    print('  peak %8.1f Hz  %6.1f dB' % (hz[k], 20 * np.log10(f[k] / med)))
for t in (220, 330, 440, 660):
    k = int(round(t * n / sr))
    print('  %d Hz  %6.1f dB' % (t, 20 * np.log10(f[k - 2:k + 3].max() / med)))
p = f ** 2
keep = np.zeros(len(p), bool)
for t in (220, 330, 440, 660):
    k = int(round(t * n / sr))
    keep[k - 4:k + 5] = True
print('  energy outside the four tones (+-4 bins): %.1f dB of the total' % (10 * np.log10(p[~keep].sum() / p.sum())))
