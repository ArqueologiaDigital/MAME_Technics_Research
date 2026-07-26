#!/usr/bin/env python3
"""fix.py -- re-run the DR-consumer statistic with the CORRECTED read detector
(880.1.60.* AND 900.1.60.* AND 800.1.60.*).  Scratchpad."""
import collections

from dspcorpus import (load, kernel_blob, distinct_images, fields, fmt,
                       KERNEL_ADDR, EPILOGUE_ADDR)

rom, names, imgs = load()
_c, _ka, KW = kernel_blob(rom, KERNEL_ADDR)
_c, _ea, EW = kernel_blob(rom, EPILOGUE_ADDR)
DIST = distinct_images(imgs)
STREAMS = [("kernel", list(KW)), ("epilogue", list(EW))]
for ws, algos in DIST.items():
    STREAMS.append(("algo%d:%s" % (algos[0], names.get(algos[0], "?")), list(ws)))


def hi(w):
    return (w >> 24) & 0xFFF


def cls(w):
    return (w >> 20) & 0xF


def a8(w):
    return (w >> 12) & 0xFF


ESC = 0x800


def is_read(w):
    return (hi(w) & ESC) and cls(w) == 1 and a8(w) == 0x60


def is_write(w):
    return (hi(w) & ESC) and cls(w) == 1 and a8(w) == 0x20


print("=" * 78)
print("X0.  THE DRAM WORD FAMILY -- every hi12 that carries class-1 addr8 0x60/0x20")
print("=" * 78)
fam = collections.Counter()
for nm, s in STREAMS:
    for w in s:
        if (hi(w) & ESC) and cls(w) == 1 and a8(w) in (0x20, 0x30, 0x60):
            fam[(hi(w), a8(w))] += 1
for k, n in fam.most_common():
    print("   %03X . 1 . %02X . ***   n=%d" % (k[0], k[1], n))

print()
print("=" * 78)
print("X1.  CORRECTED 'preceded within 5 by a DRAM READ' statistic")
print("=" * 78)


def dist_read(s, i, k=5):
    for d in range(1, k + 1):
        if i - d >= 0 and is_read(s[i - d]):
            return d
    return None


rd = collections.defaultdict(lambda: [0, 0])
tot = [0, 0]
for nm, s in STREAMS:
    for i, w in enumerate(s):
        r = dist_read(s, i) is not None
        rd[w & 0xFFF][0] += 1
        rd[w & 0xFFF][1] += r
        tot[0] += 1
        tot[1] += r
print("  BASE RATE %d/%d = %.1f%%" % (tot[1], tot[0], 100.0 * tot[1] / tot[0]))
print("\n  lo12  UP LOW    n   after-a-READ")
rows = [(lo, v[0], v[1]) for lo, v in rd.items() if v[0] >= 10]
for lo, n, p in sorted(rows, key=lambda r: -r[2] / r[1])[:26]:
    print("   %03X  %02X %02X %5d      %5.1f%%   (%d)"
          % (lo, lo >> 5, lo & 0x1F, n, 100.0 * p / n, p))

print()
print("=" * 78)
print("X2.  SPLIT BY hi12, corrected -- the UPPER-0x32 family")
print("=" * 78)
for target in (0x655, 0x64B, 0x647, 0x419, 0x680, 0x695, 0x64D):
    tab = collections.defaultdict(collections.Counter)
    for nm, s in STREAMS:
        for i, w in enumerate(s):
            if (w & 0xFFF) != target:
                continue
            tab[(hi(w), cls(w))][dist_read(s, i)] += 1
    print("\n  lo12 = 0x%03X  (UP=%02X LOW=%02X)" % (target, target >> 5, target & 0x1F))
    for k in sorted(tab, key=lambda k: -sum(tab[k].values())):
        c = tab[k]
        n = sum(c.values())
        print("    %03X.%X.**.%03X  n=%-3d  after-READ %d/%d   distances %s"
              % (k[0], k[1], target, n, n - c[None], n,
                 " ".join("d%s:%d" % (d, m) for d, m in sorted(
                     c.items(), key=lambda x: (x[0] is None, x[0])))))

print()
print("=" * 78)
print("X3.  CONTROL: negative lo12 values must stay near the base rate")
print("=" * 78)
for lo in (0x1D5, 0x415, 0x407, 0x1CD, 0x1CE, 0x000, 0x412, 0x40E, 0x200, 0x1C0,
           0x447, 0x4C8, 0x4CD, 0xC63, 0x700, 0x687):
    n, p = rd[lo]
    print("   %03X  UP=%02X LOW=%02X  %5d   %5.1f%%" % (lo, lo >> 5, lo & 0x1F, n,
                                                        100.0 * p / n))
