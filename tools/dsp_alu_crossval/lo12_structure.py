#!/usr/bin/env python3
"""lo12_structure.py -- find the SUB-FIELD boundaries inside lo12 before assigning
any meaning.  Scratchpad-only.
"""
import collections
import itertools
import sys

from dspcorpus import load, kernel_blob, distinct_images, fields, fmt
from dspcorpus import KERNEL_ADDR, EPILOGUE_ADDR

rom, names, imgs = load()
_c, ka, KW = kernel_blob(rom, KERNEL_ADDR)
_c, ea, EW = kernel_blob(rom, EPILOGUE_ADDR)

DIST = distinct_images(imgs)
BODY = []
for ws in DIST:
    BODY += list(ws)

ALL = list(KW) + list(EW) + BODY

print("=" * 78)
print("0.  POPULATIONS")
print("=" * 78)
print("kernel %d  epilogue %d  distinct-body %d  total %d"
      % (len(KW), len(EW), len(BODY), len(ALL)))

for label, pop in (("ALL", ALL), ("bodies only", BODY)):
    los = set(w & 0xFFF for w in pop)
    pairs = set(((w >> 20) & 0xF, w & 0xFFF) for w in pop)
    print("  %-12s  words %4d  distinct lo12 %3d  distinct (class4,lo12) %3d"
          % (label, len(pop), len(los), len(pairs)))

# The brief's numbers: 2788 words, 80 distinct lo12, 121 pairs.  Try to find the
# population that reproduces them.
print("\n  -- searching for the brief's population (2788 / 80 / 121):")
for name, pop in (("bodies", BODY), ("all", ALL)):
    for cls_filter, cname in ((None, "any class"),
                              ({2, 0xA}, "class 2/A"),
                              ({0, 2, 4, 6, 8, 0xA, 0xC, 0xE}, "even class")):
        sub = [w for w in pop
               if cls_filter is None or ((w >> 20) & 0xF) in cls_filter]
        los = set(w & 0xFFF for w in sub)
        prs = set(((w >> 20) & 0xF, w & 0xFFF) for w in sub)
        print("     %-8s %-10s words %4d lo12 %3d pairs %3d"
              % (name, cname, len(sub), len(los), len(prs)))

print()
print("=" * 78)
print("1.  BIT-LEVEL STRUCTURE OF lo12 (over distinct VALUES, not occurrences)")
print("=" * 78)

VALS = sorted(set(w & 0xFFF for w in ALL))
print("distinct lo12 values: %d" % len(VALS))

# per-bit: how often is each bit set, over distinct values and over occurrences
occ = collections.Counter(w & 0xFFF for w in ALL)
print("\n bit | set in distinct-values | set in occurrences")
for b in range(11, -1, -1):
    dv = sum(1 for v in VALS if v & (1 << b))
    oc = sum(n for v, n in occ.items() if v & (1 << b))
    print("  %2d |  %3d / %3d  (%5.1f%%)   | %5d / %5d (%5.1f%%)"
          % (b, dv, len(VALS), 100.0 * dv / len(VALS),
             oc, len(ALL), 100.0 * oc / len(ALL)))

print()
print("=" * 78)
print("2.  MUTUAL INFORMATION BETWEEN lo12 BIT PAIRS (occurrence-weighted)")
print("    high MI = the two bits belong to one field (or are redundant)")
print("=" * 78)
import math


def mi(pop, ba, bb):
    n = len(pop)
    cnt = collections.Counter(((w >> ba) & 1, (w >> bb) & 1) for w in pop)
    pa = collections.Counter((w >> ba) & 1 for w in pop)
    pb = collections.Counter((w >> bb) & 1 for w in pop)
    s = 0.0
    for (x, y), c in cnt.items():
        pxy = c / n
        px = pa[x] / n
        py = pb[y] / n
        s += pxy * math.log2(pxy / (px * py))
    return s


lo_pop = [w & 0xFFF for w in ALL]
print("      " + "".join("  b%-2d" % b for b in range(11, -1, -1)))
for a in range(11, -1, -1):
    row = "  b%-2d " % a
    for b in range(11, -1, -1):
        if a == b:
            row += "  .  "
        else:
            row += "%5.2f" % mi(lo_pop, a, b)
    print(row)

print()
print("=" * 78)
print("3.  CANDIDATE FIELD SPLITS -- which nibble/bit groups are 'small'?")
print("=" * 78)
for lo_bit, hi_bit in [(0, 2), (0, 3), (0, 4), (3, 5), (3, 7), (4, 7),
                       (8, 11), (7, 11), (6, 11), (0, 11)]:
    mask = ((1 << (hi_bit + 1)) - 1) ^ ((1 << lo_bit) - 1)
    vals = collections.Counter((w & mask) >> lo_bit for w in lo_pop)
    width = hi_bit - lo_bit + 1
    print("  bits[%2d:%2d] width %d  distinct %3d of %4d possible : %s"
          % (hi_bit, lo_bit, width, len(vals), 1 << width,
             " ".join("%X(%d)" % (v, n) for v, n in vals.most_common(12))))

print()
print("=" * 78)
print("4.  THE lo12 VALUES, SORTED, WITH THEIR CLASSES AND FREQUENCY")
print("=" * 78)
by_lo = collections.defaultdict(collections.Counter)
for w in ALL:
    by_lo[w & 0xFFF][(w >> 20) & 0xF] += 1
print(" lo12  bin           n     classes")
for v in VALS:
    tot = sum(by_lo[v].values())
    if tot < 3:
        continue
    print("  %03X  %012s  %4d   %s"
          % (v, format(v, "012b"), tot,
             " ".join("%X:%d" % (c, n) for c, n in sorted(by_lo[v].items()))))
