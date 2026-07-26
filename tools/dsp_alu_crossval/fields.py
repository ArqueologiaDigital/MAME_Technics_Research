#!/usr/bin/env python3
"""fields.py -- is lo12 a horizontal microword (like hi12), and does hi12's f31
field carry the ALU op?  Scratchpad-only.
"""
import collections
import itertools
import math
import random

from dspcorpus import (load, kernel_blob, distinct_images, fields, fmt,
                       KERNEL_ADDR, EPILOGUE_ADDR)

rom, names, imgs = load()
_c, ka, KW = kernel_blob(rom, KERNEL_ADDR)
_c, ea, EW = kernel_blob(rom, EPILOGUE_ADDR)
DIST = distinct_images(imgs)
BODY = []
for ws in DIST:
    BODY += list(ws)
ALL = list(KW) + list(EW) + BODY

LO = [w & 0xFFF for w in ALL]
HI = [(w >> 24) & 0xFFF for w in ALL]
VALS = sorted(set(LO))
HVALS = sorted(set(HI))

print("=" * 78)
print("A.  IS lo12 A HORIZONTAL MICROWORD?  (the hi12 test, re-run on lo12)")
print("=" * 78)
print("The hi12 test (instruction-set.md): count Hamming-distance-1 pairs among")
print("the observed values, against a popcount-matched null.")


def hd1_pairs(vs, width):
    s = set(vs)
    n = 0
    for v in s:
        for b in range(width):
            if (v ^ (1 << b)) in s and (v ^ (1 << b)) > v:
                n += 1
    return n


def null(vs, width, trials=2000, seed=1):
    """Popcount-matched null: resample the same multiset of popcounts."""
    rng = random.Random(seed)
    pcs = [bin(v).count("1") for v in vs]
    out = []
    for _ in range(trials):
        s = set()
        for pc in pcs:
            bits = rng.sample(range(width), pc)
            x = 0
            for b in bits:
                x |= 1 << b
            s.add(x)
        out.append(hd1_pairs(s, width))
    m = sum(out) / len(out)
    sd = (sum((x - m) ** 2 for x in out) / len(out)) ** 0.5
    return m, sd


for label, vs, width in (("hi12 (control -- known microword)", HVALS, 12),
                         ("lo12 (all 167 values)", VALS, 12),
                         ("lo12 (values with n>=3)", sorted(
                             v for v, n in collections.Counter(LO).items() if n >= 3), 12)):
    obs = hd1_pairs(vs, width)
    m, sd = null(vs, width)
    z = (obs - m) / sd if sd else 0.0
    print("  %-34s  %3d values  HD1 obs %3d  null %5.1f +- %4.1f  z = %+5.1f"
          % (label, len(vs), obs, m, sd, z))

print()
print("=" * 78)
print("B.  hi12 f31 (bits 3:1) AS AN ALU-OP SELECTOR -- does lo12 stay fixed")
print("    while f31 varies?  (the LFO pair 092/094 . A . 00 . 200 says yes)")
print("=" * 78)


def f31(h):
    return (h >> 1) & 7


def f98(h):
    return (h >> 8) & 3


by_lo_hi = collections.defaultdict(collections.Counter)
for w in ALL:
    hi, cl, ad, lo = fields(w)
    by_lo_hi[lo][hi] += 1

print("lo12 values that appear with MORE THAN ONE f31 value (n>=8 total):")
print(" lo12  n     f31 spread                         hi12 values")
multi = []
for lo in VALS:
    tot = sum(by_lo_hi[lo].values())
    if tot < 8:
        continue
    fs = collections.Counter()
    for hi, n in by_lo_hi[lo].items():
        fs[f31(hi)] += n
    if len(fs) > 1:
        multi.append((tot, lo, fs))
for tot, lo, fs in sorted(multi, reverse=True):
    print("  %03X %4d  %-34s %s"
          % (lo, tot, " ".join("f31=%d:%d" % kv for kv in sorted(fs.items())),
             " ".join("%03X" % h for h in sorted(by_lo_hi[lo]))))

print()
print("Conversely: hi12 values that appear with many lo12 values")
by_hi_lo = collections.defaultdict(collections.Counter)
for w in ALL:
    hi, cl, ad, lo = fields(w)
    by_hi_lo[hi][lo] += 1
for hi in sorted(by_hi_lo, key=lambda h: -sum(by_hi_lo[h].values()))[:14]:
    c = by_hi_lo[hi]
    print("  %03X (f98=%d f31=%d bit4=%d) n=%4d  %2d lo12 : %s"
          % (hi, f98(hi), f31(hi), (hi >> 4) & 1, sum(c.values()), len(c),
             " ".join("%03X(%d)" % kv for kv in c.most_common(8))))

print()
print("=" * 78)
print("C.  CONTINGENCY: is (f31, lo12) independent?  If f31 were the ALU op and")
print("    lo12 the route, both would range fairly freely.  If lo12 already")
print("    contained the op, f31 would be a FUNCTION of lo12.")
print("=" * 78)
tab = collections.Counter()
for w in ALL:
    hi, cl, ad, lo = fields(w)
    tab[(f31(hi), lo)] += 1
n_lo = len(VALS)
n_f31 = len(set(f31(h) for h in HI))
# how many lo12 values determine f31 uniquely?
det = sum(1 for lo in VALS if len(set(f31(h) for h in by_lo_hi[lo])) == 1)
occ_det = sum(sum(by_lo_hi[lo].values()) for lo in VALS
              if len(set(f31(h) for h in by_lo_hi[lo])) == 1)
print("  distinct lo12 %d ; distinct f31 %d" % (n_lo, n_f31))
print("  lo12 values with a UNIQUE f31: %d / %d  (%.1f%% of values, %.1f%% of words)"
      % (det, n_lo, 100.0 * det / n_lo, 100.0 * occ_det / len(ALL)))
# the same, for f98 and for hi12-bit4
for name, fn in (("f98", f98), ("bit4(store)", lambda h: (h >> 4) & 1),
                 ("bit11(ESC)", lambda h: (h >> 11) & 1)):
    d = sum(1 for lo in VALS if len(set(fn(h) for h in by_lo_hi[lo])) == 1)
    o = sum(sum(by_lo_hi[lo].values()) for lo in VALS
            if len(set(fn(h) for h in by_lo_hi[lo])) == 1)
    print("  lo12 values with a UNIQUE %-11s : %3d / %d  (%.1f%% of words)"
          % (name, d, n_lo, 100.0 * o / len(ALL)))
