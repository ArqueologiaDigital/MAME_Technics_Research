#!/usr/bin/env python3
"""code8fit.py -- how do the 8-bit samples' segment codes scale the samples?

QUESTION: an 8-bit sample's record gives every segment a 6-bit code (a, b) (bits 13:11 and
10:8 of the parameter word). The raw bytes stay near full scale through a decaying sound
while the codes rise, so the codes are gains. Which law makes the decoded signal continuous
across segment boundaries?

Method: at every boundary between two segments of every 8-bit sample of both pairs, the RMS
of the 32 raw samples before and after it (both above 4/127). 1) a free fit of one log2 gain
G per code, by least squares on G(after) - G(before) = log2(rms before / rms after);
2) the median boundary jump |log2| for laws 2**-(alpha*a + beta*b), against the same
statistic inside segments (no code change: the floor).
RUN: python3 code8fit.py
"""
from collections import Counter
import numpy as np
from wavedir import *


def boundaries(w=32):
    for tg in (0, 1):
        s = stream(tg)
        for k, e in entries_cache(tg).items():
            if not e['is8']:
                continue
            r = parse_record(record(s, e), e['L'])
            sg = r['segs']
            if len(sg) < 2:
                continue
            base = e['page'] * PAGE + e['B'] * 16
            n = sg[-1][1]
            raw = s[base: base + (n + 1) // 2].view(np.int8).astype(np.float64)
            for (a0, b0, A0, B0), (a1, b1, A1, B1) in zip(sg, sg[1:]):
                if b0 - a0 < w or b1 - a1 < w or b1 > len(raw):
                    continue
                r0 = np.sqrt((raw[b0 - w:b0] ** 2).mean()); r1 = np.sqrt((raw[a1:a1 + w] ** 2).mean())
                if r0 >= 4 and r1 >= 4:
                    yield (A0, B0), (A1, B1), r0, r1
            for a0, b0, A0, B0 in sg:     # the floor: a split point inside a segment
                m = (a0 + b0) // 2
                if b0 - a0 >= 2 * w and b0 <= len(raw):
                    r0 = np.sqrt((raw[m - w:m] ** 2).mean()); r1 = np.sqrt((raw[m:m + w] ** 2).mean())
                    if r0 >= 4 and r1 >= 4:
                        yield None, None, r0, r1


rows = list(boundaries())
bnd = [r for r in rows if r[0] is not None]
inside = np.array([abs(np.log2(r[3] / r[2])) for r in rows if r[0] is None])
print('boundaries %d, inside-segment windows %d (floor: median |log2 jump| %.3f)' % (len(bnd), len(inside), np.median(inside)))

codes = sorted(set([r[0] for r in bnd] + [r[1] for r in bnd]))
idx = {c: i for i, c in enumerate(codes)}
M = np.zeros((len(bnd) + 1, len(codes))); y = np.zeros(len(bnd) + 1)
for k, (c0, c1, r0, r1) in enumerate(bnd):
    M[k, idx[c1]] += 1; M[k, idx[c0]] -= 1; y[k] = np.log2(r0 / r1)
M[-1, idx[(0, 0)]] = 1
G = np.linalg.lstsq(M, y, rcond=None)[0]
cnt = Counter()
for c0, c1, r0, r1 in bnd:
    cnt[c0] += 1; cnt[c1] += 1
print('free fit, log2 gain per code (a,b) seen at >= 30 boundaries, anchored at (0,0) = 0:')
for c in codes:
    if cnt[c] >= 30:
        print('   (%d,%d)  n=%5d  G=%+.2f   -b/2=%+.2f' % (c[0], c[1], cnt[c], G[idx[c]], -c[1] / 2))

print('median |log2 jump| at the boundaries for gain 2^-(alpha*a + beta*b):')
for al, be in ((0, 0), (1, 0), (0, 1), (0, 0.5), (0, 0.625), (0, 0.75), (0.125, 0.75), (0.5, 0.5)):
    j = [abs(np.log2(r0 * 2 ** -(al * c0[0] + be * c0[1]) / (r1 * 2 ** -(al * c1[0] + be * c1[1])))) for c0, c1, r0, r1 in bnd]
    print('   alpha %.3f beta %.3f   %.3f' % (al, be, np.median(j)))
