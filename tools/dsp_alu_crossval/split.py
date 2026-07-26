#!/usr/bin/env python3
"""split.py -- the lo12 field boundaries, measured.  Scratchpad-only."""
import collections
import math

from dspcorpus import (load, kernel_blob, distinct_images, fields, fmt,
                       KERNEL_ADDR, EPILOGUE_ADDR)

rom, names, imgs = load()
_c, _ka, KW = kernel_blob(rom, KERNEL_ADDR)
_c, _ea, EW = kernel_blob(rom, EPILOGUE_ADDR)
DIST = distinct_images(imgs)
BODY = []
for ws in DIST:
    BODY += list(ws)
ALL = list(KW) + list(EW) + BODY
LO = [w & 0xFFF for w in ALL]

print("=" * 78)
print("D.  THE '+SUFFIX' RECURRENCE:  lo12 = UPPER<<5 | LOWER ?")
print("=" * 78)
print("    Observed by hand: 0x1D5 = 0x1C0+0x15, 0x655 = 0x640+0x15,")
print("    0x415 = 0x400+0x15, 0x2D5 = 0x2C0+0x15 ...  Test it globally.")


def split_stats(lo_bit):
    """Split lo12 at lo_bit: UPPER = lo12>>lo_bit, LOWER = lo12 & mask."""
    up = collections.Counter(v >> lo_bit for v in LO)
    dn = collections.Counter(v & ((1 << lo_bit) - 1) for v in LO)
    pairs = collections.Counter((v >> lo_bit, v & ((1 << lo_bit) - 1)) for v in LO)
    # mutual information between the two halves (occurrence-weighted)
    n = len(LO)
    mi = 0.0
    for (a, b), c in pairs.items():
        p = c / n
        mi += p * math.log2(p / ((up[a] / n) * (dn[b] / n)))
    # H of each half
    def H(cnt):
        return -sum((c / n) * math.log2(c / n) for c in cnt.values())
    return up, dn, pairs, mi, H(up), H(dn)


print("\n  split  |UP| |DN| |pairs| (|UP|*|DN|)  MI(UP;DN)  H(UP)  H(DN)  H(lo12)")
Hlo = -sum((c / len(LO)) * math.log2(c / len(LO))
           for c in collections.Counter(LO).values())
for b in range(2, 11):
    up, dn, pr, mi, hu, hd = split_stats(b)
    print("  bits[%2d:0] %3d %3d  %4d   (%5d)     %5.3f   %5.3f  %5.3f  %5.3f"
          % (b - 1, len(up), len(dn), len(pr), len(up) * len(dn), mi, hu, hd, Hlo))
print("\n  (a clean two-field encoding = LOW MI between the halves and")
print("   |pairs| << |UP|*|DN| only because the corpus is small)")

print()
print("=" * 78)
print("E.  THE FIVE-BIT LOWER FIELD  lo12[4:0]  -- values and where they appear")
print("=" * 78)
low = collections.Counter(v & 0x1F for v in LO)
upp = collections.Counter(v >> 5 for v in LO)
print("  lo12[4:0]:  %d of 32 values" % len(low))
byl = collections.defaultdict(set)
for v in set(LO):
    byl[v & 0x1F].add(v >> 5)
for k in sorted(low, key=lambda x: -low[x]):
    print("    %02X (%05s)  n=%4d  seen with %2d uppers: %s"
          % (k, format(k, "05b"), low[k], len(byl[k]),
             " ".join("%02X" % u for u in sorted(byl[k]))))

print("\n  lo12[11:5]: %d values" % len(upp))
byu = collections.defaultdict(set)
for v in set(LO):
    byu[v >> 5].add(v & 0x1F)
for k in sorted(upp, key=lambda x: -upp[x]):
    print("    %02X (%07s)  n=%4d  seen with %2d lowers: %s"
          % (k, format(k, "07b"), upp[k], len(byu[k]),
             " ".join("%02X" % u for u in sorted(byu[k]))))

print()
print("=" * 78)
print("F.  lo12[8:6] AS A 3-BIT FIELD  (the high-MI triple from the MI matrix)")
print("=" * 78)
f3 = collections.Counter((v >> 6) & 7 for v in LO)
for k in sorted(f3):
    vs = sorted(set(v for v in LO if ((v >> 6) & 7) == k))
    print("   f3=%d (%03s)  n=%4d  lo12 values: %s"
          % (k, format(k, "03b"), f3[k], " ".join("%03X" % v for v in vs[:24])))

print()
print("   the four single-bit flags:")
for b, nm in ((11, "bit11"), (10, "bit10"), (9, "bit9"), (5, "bit5")):
    n = sum(1 for v in LO if v & (1 << b))
    vs = sorted(set(v for v in LO if v & (1 << b)))
    print("   %s set in %4d/%d words, %d distinct values%s"
          % (nm, n, len(LO), len(vs),
             (": " + " ".join("%03X" % v for v in vs[:20])) if len(vs) <= 20 else ""))
