#!/usr/bin/env python3
"""control.py -- the 'after a DRAM read' statistic must survive removing the
reverb motif, or it is a scheduling artefact.  Scratchpad."""
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

REVERBISH = ("algo16", "algo8")     # the 133-word reverb image and GATED REVERB


def hi(w):
    return (w >> 24) & 0xFFF


def cls(w):
    return (w >> 20) & 0xF


def is_read(w):
    return (hi(w) & 0xF00) == 0x800 and cls(w) == 1 and ((w >> 12) & 0xFF) == 0x60


def prev_read(s, i, k=5):
    return any(i - d >= 0 and is_read(s[i - d]) for d in range(1, k + 1))


print("=" * 78)
print("C1.  'preceded within 5 words by an 880.1.60 DRAM READ', with the")
print("     reverb images (algo16 image + GATED REVERB) HELD OUT.")
print("=" * 78)
for label, keep in (("ALL images", lambda n: True),
                    ("reverb images REMOVED",
                     lambda n: not n.startswith(REVERBISH))):
    rd = collections.defaultdict(lambda: [0, 0])
    tot = [0, 0]
    for nm, s in STREAMS:
        if not keep(nm):
            continue
        for i, w in enumerate(s):
            r = prev_read(s, i)
            rd[w & 0xFFF][0] += 1
            rd[w & 0xFFF][1] += r
            tot[0] += 1
            tot[1] += r
    print("\n  %-26s  base rate %d/%d = %.1f%%"
          % (label, tot[1], tot[0], 100.0 * tot[1] / tot[0]))
    print("    lo12  UP LOW    n   after-a-READ")
    for lo in (0x419, 0x64B, 0x655, 0x680, 0x000, 0x407, 0x1D5, 0x415,
               0x1CD, 0x1CE, 0x647, 0x687, 0x2C7, 0x40E, 0x412, 0x447):
        n, p = rd[lo]
        if n == 0:
            print("     %03X  %02X %02X     0      --" % (lo, lo >> 5, lo & 0x1F))
            continue
        print("     %03X  %02X %02X %5d   %5.1f%%  (%d)"
              % (lo, lo >> 5, lo & 0x1F, n, 100.0 * p / n, p))

print()
print("=" * 78)
print("C2.  WHERE the non-reverb 0x419 / 0x64B / 0x655 / 0x680 words live")
print("=" * 78)
for target in (0x419, 0x64B, 0x655, 0x680):
    print("\n  lo12 = 0x%03X" % target)
    for nm, s in STREAMS:
        for i, w in enumerate(s):
            if (w & 0xFFF) != target:
                continue
            ctx = " | ".join(fmt(s[j]) for j in range(max(0, i - 5), i))
            print("    %-26s w%-3d %-14s  <= [%s]"
                  % (nm[:26], i, fmt(w), ctx))

print()
print("=" * 78)
print("C3.  NEGATIVE CONTROL -- 'preceded within 5 by a class-A MULTIPLY'")
print("     (a statistic that should NOT track the DRAM one)")
print("=" * 78)
mm = collections.defaultdict(lambda: [0, 0])
tot = [0, 0]
for nm, s in STREAMS:
    for i, w in enumerate(s):
        r = any(i - d >= 0 and cls(s[i - d]) == 0xA for d in range(1, 6))
        mm[w & 0xFFF][0] += 1
        mm[w & 0xFFF][1] += r
        tot[0] += 1
        tot[1] += r
print("  base rate %d/%d = %.1f%%" % (tot[1], tot[0], 100.0 * tot[1] / tot[0]))
for lo in (0x419, 0x64B, 0x655, 0x680, 0x1D5, 0x415, 0x407, 0x1C0, 0x200):
    n, p = mm[lo]
    print("     %03X  %5d   %5.1f%%" % (lo, n, 100.0 * p / n))
