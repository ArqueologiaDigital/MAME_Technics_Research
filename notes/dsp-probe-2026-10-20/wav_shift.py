#!/usr/bin/env python3
# wav_shift.py A.wav B.wav -- is B the same sound as A, only starting at another moment?
# For the gate's oracle captures (3 channels, 48 kHz, the audio on channels 0-1): prints each file's onset (the first
# sample above 1/8 of its peak, channel 0), then the shift of B against A that best lines up channel 0 over 0.5 s from
# A's onset (least squares, searched to +-50 ms), and how much of A's energy is left in the difference once aligned.
import sys
import wave
import array


def load(p):
    w = wave.open(p)
    a = array.array('h', w.readframes(w.getnframes()))
    return [a[i::w.getnchannels()] for i in range(w.getnchannels())], w.getframerate()


(a, rate), (b, _) = load(sys.argv[1]), load(sys.argv[2])
x, y = a[0], b[0]
peak = max(abs(v) for v in x)
on = lambda s: next(i for i, v in enumerate(s) if abs(v) > peak / 8)
oa, ob = on(x), on(y)
print(f'onset: A {oa / rate:.6f} s, B {ob / rate:.6f} s, B - A = {(ob - oa) / rate * 1000:.3f} ms ({ob - oa} samples)')
n = rate // 2
seg = x[oa:oa + n]
e = sum(v * v for v in seg)
best = None
for lag in range(-rate // 20, rate // 20 + 1):
    s = y[oa + lag:oa + lag + n]
    d = sum((p - q) ** 2 for p, q in zip(seg, s))
    if best is None or d < best[1]:
        best = (lag, d)
print(f'best alignment: B shifted by {best[0]} samples ({best[0] / rate * 1000:.3f} ms); residual energy {100 * best[1] / e:.2f}% '
      f'of A\'s over 0.5 s (without shifting: {100 * sum((p - q) ** 2 for p, q in zip(seg, y[oa:oa + n])) / e:.1f}%)')
