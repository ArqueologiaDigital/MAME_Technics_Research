#!/usr/bin/env python3
"""gaps.py SEQ.txt... -- from sc1all.lua's "time TX/RX byte" lines: the gaps between consecutive TX writes
closer than 1 ms (one command sequence), as a histogram, and the largest."""
import sys
for f in sys.argv[1:]:
    ev = [l.split() for l in open(f)]
    tx = [float(e[0]) for e in ev if e[1] == 'TX']
    g = sorted((b - a) * 1e6 for a, b in zip(tx, tx[1:]) if b - a < 1e-3)
    buckets = {}
    for x in g:
        k = int(x // 25) * 25
        buckets[k] = buckets.get(k, 0) + 1
    print(f, f'{len(g)} gaps < 1 ms; max {g[-1]:.0f} us;', ' '.join(f'{k}-{k+25}us:{n}' for k, n in sorted(buckets.items())))
