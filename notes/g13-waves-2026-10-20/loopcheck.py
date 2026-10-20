#!/usr/bin/env python3
"""loopcheck.py -- does the record grammar in wavedir.py put the loop where the data has one?

QUESTION: for every directory entry of both pairs, is the decoded loop [ls, le) inside the
sample, and do the samples just before ls equal the samples just before le (the authored
"pre-roll" a seamless loop carries)? Also: where do explicit-end loops (flag 0x80) end
relative to the region end (the next entry's start), and when that gap is 32 samples, are
those 32 samples a copy of the loop's first 32 (a run-out for the interpolator)?
("loop past region": entries whose sample runs on through the next entry's data -- an
attack version and a later-starting version of one recording share it.)

Prints counts per record kind. Exact equality is tested on the raw 16-bit words / bytes
(no gain), 16 samples before each loop point; all-zero windows are counted separately.
RUN: python3 loopcheck.py
"""
from collections import Counter
import numpy as np
from wavedir import *

for tg in (1, 0):
    s = stream(tg)
    c = Counter(); tail = Counter(); runout = Counter()
    for (p, j), e in entries_cache(tg).items():
        if e['end'] is None:
            c['last entry of page (region end unknown)'] += 1
            continue
        ps = record(s, e)
        r = parse_record(ps, e['L'])
        explicit = any((v >> 14) == 2 and (v & 0xFF) >= 0x80 for v in ps)
        kind = ('8-bit ' if e['is8'] else '16-bit ') + ('explicit end' if explicit else 'one-granule loop')
        base = e['page'] * PAGE + e['B'] * 16
        n = (e['end'] - e['B']) * 16 * (2 if e['is8'] else 1)
        if r['le'] > n:
            c[kind + ': loop past region'] += 1
            continue
        raw = s[base: base + n // (2 if e['is8'] else 1)]
        raw = raw.view(np.int8) if e['is8'] else raw.view('<i2')
        ls, le = r['ls'], r['le']
        if ls < 16:
            c[kind + ': loop from the start'] += 1
            continue
        a, b = raw[ls - 16:ls], raw[le - 16:le]
        if not np.any(a) and not np.any(b):
            c[kind + ': silent at the loop'] += 1
        elif np.array_equal(a, b):
            c[kind + ': pre-roll exact'] += 1
        else:
            c[kind + ': pre-roll differs'] += 1
        if explicit:
            tail[n - le] += 1
            if n - le == 32:
                runout['copy' if np.array_equal(raw[le:le + 32], raw[ls:ls + 32]) else 'differs'] += 1
    print(PAIR_NAME[tg])
    for k, v in sorted(c.items()):
        print('   %-48s %5d' % (k, v))
    print('   explicit-end loops: region end - loop end (samples) ->', tail.most_common(5))
    print('   ...of those 32 short: the 32 samples after the loop end vs the loop\'s first 32 ->', dict(runout))
