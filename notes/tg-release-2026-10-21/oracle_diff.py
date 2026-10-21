#!/usr/bin/env python3
# oracle_diff.py A.wav B.wav -- where two captures of the gate's audio oracle (oracle_ab.sh) differ (README.md here):
# the first differing sample frame, the count of differing frames, and each second's RMS (dBFS, channels 0 and 1) in both.
import sys
import wave

import numpy as np


def load(p):
    with wave.open(p, "rb") as w:
        return w.getframerate(), np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, w.getnchannels())


R, a = load(sys.argv[1])
_, b = load(sys.argv[2])
n = min(len(a), len(b))
d = np.any(a[:n] != b[:n], axis=1)
idx = np.flatnonzero(d)
print("frames %d / %d; differing %d; first at %s" % (len(a), len(b), len(idx), "%.4f s" % (idx[0] / R) if len(idx) else "none"))


def db(x):
    x = x[:, :2].astype(np.float64) / 32768.0
    return 10 * np.log10(max((x ** 2).mean(), 1e-24))


for s in range(int(n / R)):
    sa, sb = a[s * R:(s + 1) * R], b[s * R:(s + 1) * R]
    if np.any(sa != sb):
        print("second %2d: A %7.1f dBFS  B %7.1f dBFS" % (s, db(sa), db(sb)))
