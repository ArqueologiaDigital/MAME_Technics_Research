#!/usr/bin/env python3
"""wavshift.py OLD.wav NEW.wav -- is NEW the same audio as OLD, shifted in time?

On channel 1 (the KN5000's channel 0 is always silent): the first sample above 1000 in each, the shift
that best aligns them (searched +-50 ms around the onset difference, by the residual of 5 s of audio), and
then, at that shift, the residual RMS and the bit-identical fraction over the overlap.
"""
import struct
import sys
import wave


def load(p):
    w = wave.open(p)
    n, ch = w.getnframes(), w.getnchannels()
    s = struct.unpack('<%dh' % (n * ch), w.readframes(n))
    return s[1::ch], w.getframerate()


a, ra = load(sys.argv[1])
b, rb = load(sys.argv[2])
assert ra == rb
onset = lambda x: next(i for i, v in enumerate(x) if abs(v) > 1000)
oa, ob = onset(a), onset(b)
print(f'onset: old {oa / ra:.4f} s, new {ob / rb:.4f} s, difference {(ob - oa) / ra * 1000:+.2f} ms')
seg = range(oa, min(oa + 5 * ra, len(a)))
def resid(d):
    return sum((a[i] - b[i + d]) ** 2 for i in seg if 0 <= i + d < len(b)) / len(seg)
base = ob - oa
best = min(range(base - ra // 20, base + ra // 20 + 1, 1 if ra < 1000 else max(1, ra // 2000)), key=resid)
best = min(range(best - 30, best + 31), key=resid)
n = min(len(a), len(b) - best) if best >= 0 else min(len(a) + best, len(b))
pairs = [(a[i], b[i + best]) for i in range(max(0, -best), n)]
rms = (sum((x - y) ** 2 for x, y in pairs) / len(pairs)) ** 0.5
sig = (sum(x * x for x, _ in pairs) / len(pairs)) ** 0.5
same = sum(1 for x, y in pairs if x == y) / len(pairs)
print(f'best shift {best} samples ({best / ra * 1000:+.2f} ms); over {len(pairs) / ra:.1f} s: residual rms {rms:.1f} '
      f'against signal rms {sig:.1f}; identical samples {same * 100:.2f}%')
