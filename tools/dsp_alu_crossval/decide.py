#!/usr/bin/env python3
"""decide.py -- which lo12 SUB-FIELD carries R1's write-source split, and the
exact counts behind the 'lo12 is not the ALU op' falsification.  Scratchpad."""
import collections

from dspcorpus import (load, kernel_blob, distinct_images, fields, fmt,
                       KERNEL_ADDR, EPILOGUE_ADDR)

rom, names, imgs = load()
_c, _ka, KW = kernel_blob(rom, KERNEL_ADDR)
_c, _ea, EW = kernel_blob(rom, EPILOGUE_ADDR)
DIST = distinct_images(imgs)
STREAMS = [list(KW), list(EW)] + [list(ws) for ws in DIST]
ALL = [w for s in STREAMS for w in s]


def UP(w):
    return (w & 0xFFF) >> 5


def LOW(w):
    return w & 0x1F


def hi(w):
    return (w >> 24) & 0xFFF


def cls(w):
    return (w >> 20) & 0xF


def store(w):
    return (hi(w) >> 4) & 1


print("=" * 78)
print("M1.  WHICH SUB-FIELD carries R1's 44/44-vs-0/56 write-source split?")
print("     Held-out design: fix LOWER, vary UPPER; then fix UPPER, vary LOWER.")
print("=" * 78)
pre = collections.defaultdict(lambda: [0, 0])
for s in STREAMS:
    for i, w in enumerate(s):
        if i == 0:
            continue
        pre[w & 0xFFF][0] += 1
        pre[w & 0xFFF][1] += store(s[i - 1])


def rate(lo):
    n, p = pre[lo]
    return (p, n, 100.0 * p / n if n else float("nan"))


print("\n  (a) SAME LOWER, DIFFERENT UPPER  -- does the rate move?")
for low in (0x15, 0x0B, 0x07, 0x00, 0x0E, 0x0D):
    row = []
    for up in sorted(set(UP(w) for w in ALL)):
        lo = (up << 5) | low
        if pre[lo][0] >= 3:
            p, n, r = rate(lo)
            row.append("u=%02X:%5.1f%%(%d/%d)" % (up, r, p, n))
    if len(row) > 1:
        print("   LOWER %02X : %s" % (low, "  ".join(row)))

print("\n  (b) SAME UPPER, DIFFERENT LOWER -- does the rate move?")
for up in (0x32, 0x16, 0x20, 0x0E, 0x22, 0x34, 0x10, 0x26, 0x00):
    row = []
    for low in range(32):
        lo = (up << 5) | low
        if pre[lo][0] >= 3:
            p, n, r = rate(lo)
            row.append("l=%02X:%5.1f%%(%d/%d)" % (low, r, p, n))
    if len(row) > 1:
        print("   UPPER %02X : %s" % (up, "  ".join(row)))

print("\n  (c) R1's own six 880.1.20.* forms, resolved into (UPPER, LOWER):")
w880 = collections.defaultdict(lambda: [0, 0])
for s in STREAMS:
    for i, w in enumerate(s):
        if hi(w) == 0x880 and cls(w) == 1 and ((w >> 12) & 0xFF) == 0x20:
            w880[w & 0xFFF][0] += 1
            if i:
                w880[w & 0xFFF][1] += store(s[i - 1])
for lo in sorted(w880, key=lambda x: -w880[x][0]):
    n, p = w880[lo]
    print("     880.1.20.%03X  UP=%02X LOW=%02X   %2d sites  %2d preceded by store  %5.1f%%"
          % (lo, lo >> 5, lo & 0x1F, n, p, 100.0 * p / n))
print("     880.1.60.%03X  UP=%02X LOW=%02X   (the READ)"
      % (0x2D4, 0x2D4 >> 5, 0x2D4 & 0x1F))
print("\n  => the split is EXACTLY UPPER==0x32 vs UPPER in {0x16,0x20}.")
print("     Two minimal pairs across the split share their LOWER:")
print("       0x655(u32,l15) 16/16   vs 0x2D5(u16,l15) %d/%d" % (w880[0x2D5][1], w880[0x2D5][0]))
print("       0x64B(u32,l0B) 28/28   vs 0x40B(u20,l0B) %d/%d" % (w880[0x40B][1], w880[0x40B][0]))

print()
print("=" * 78)
print("M2.  'operand = the external-DRAM read register' -- test UPPER 0x32")
print("     rate of being preceded WITHIN 1..5 words by an 880.1.60.* READ")
print("=" * 78)


def prev_read(s, i, k=5):
    for d in range(1, k + 1):
        if i - d < 0:
            return False
        w = s[i - d]
        if (hi(w) & 0xF00) == 0x800 and cls(w) == 1 and ((w >> 12) & 0xFF) == 0x60:
            return True
    return False


rd = collections.defaultdict(lambda: [0, 0])
tot = [0, 0]
for s in STREAMS:
    for i, w in enumerate(s):
        r = prev_read(s, i)
        rd[w & 0xFFF][0] += 1
        rd[w & 0xFFF][1] += r
        tot[0] += 1
        tot[1] += r
print("  BASE RATE %d/%d = %.1f%%" % (tot[1], tot[0], 100.0 * tot[1] / tot[0]))
print("\n  lo12  UP LOW    n   after-a-DRAM-READ")
rows = [(lo, v[0], v[1]) for lo, v in rd.items() if v[0] >= 12]
for lo, n, p in sorted(rows, key=lambda r: -r[2] / r[1])[:22]:
    print("   %03X  %02X %02X %5d      %5.1f%%   (%d)"
          % (lo, lo >> 5, lo & 0x1F, n, 100.0 * p / n, p))

print()
print("=" * 78)
print("M3.  THE FALSIFICATION COUNTS -- one lo12, several operations")
print("=" * 78)
for lo in (0x64B, 0x407, 0x200, 0x000, 0x655, 0x419, 0x1D5):
    c = collections.Counter((hi(w), cls(w)) for w in ALL if (w & 0xFFF) == lo)
    print("\n  lo12 = 0x%03X : %d words, %d distinct (hi12,class4)"
          % (lo, sum(c.values()), len(c)))
    for (h, k), n in c.most_common(9):
        print("      %03X.%X.**.%03X  x%-4d  f31=%d f98=%d ST=%d ESC=%d"
              % (h, k, lo, n, (h >> 1) & 7, (h >> 8) & 3, (h >> 4) & 1, (h >> 11) & 1))

print()
print("=" * 78)
print("M4.  INPUT-STAGE cell X+4 -- read twice, written once, three coefficients")
print("=" * 78)
for i in (5, 6, 7):
    w = KW[i]
    print("   iw%-2d %-14s cursor +%d" % (i, fmt(w), i - 5))
print("   iw5 and iw6 READ X+4 (no store bit), iw7 WRITES X+4 (bit 4 set)")
print("   iw4 reads the input latch X+2 immediately before")
print("   => a first-order recursive section whose three coefficients are the")
print("      header-bank cells cur+0, cur+1, cur+2, which K6 measured as NOT")
print("      present anywhere in the cold-boot capture.")
