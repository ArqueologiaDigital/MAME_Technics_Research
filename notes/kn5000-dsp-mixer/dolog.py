#!/usr/bin/env python3
"""dolog.py run.log -- the DO1 the harness logged (UPD6383TEST lines, `L 1' for every frame): its range and its
strongest frequencies at the 44.1 kHz frame rate. Separates what the DSP presents from what the tone generator
then does with it."""
import sys
import numpy as np

d = [l.split() for l in open(sys.argv[1]) if l.startswith('UPD6383TEST frame')]
fr = np.array([int(x[2]) for x in d])
i = [x.index('DO1') for x in d]
do = np.array([int(x[k + 1]) for x, k in zip(d, i)])
print('%d frames %d..%d, DO1 %d..%d' % (len(d), fr[0], fr[-1], do.min(), do.max()))
print('first:', ' '.join(str(v) for v in do[:12]))
n = 1 << int(np.log2(len(do)))
f = np.abs(np.fft.rfft(do[:n] * np.hanning(n)))
hz = np.fft.rfftfreq(n, 1 / 44100)
for k in sorted(np.argsort(f)[-8:]):
    print('  %8.1f Hz  %.3g' % (hz[k], f[k]))
p = f ** 2
keep = np.zeros(len(p), bool)
for t in (220, 330, 440, 660):
    k = int(round(t * n / 44100))
    keep[k - 4:k + 5] = True
print('  energy outside 220/330/440/660 Hz (+-4 bins): %.1f dB of the total' % (10 * np.log10(p[~keep].sum() / p.sum())))
