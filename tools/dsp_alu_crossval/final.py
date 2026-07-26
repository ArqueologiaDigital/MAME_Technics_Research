#!/usr/bin/env python3
"""final.py -- per-hi12 breakdown of the DR-consumer statistic, and the seven
non-reverb 0x680 sites.  Scratchpad."""
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


def is_read(w):
    return (hi(w) & 0xF00) == 0x800 and cls(w) == 1 and ((w >> 12) & 0xFF) == 0x60


def dist_read(s, i, k=6):
    for d in range(1, k + 1):
        if i - d >= 0 and is_read(s[i - d]):
            return d
    return None


print("=" * 78)
print("F1.  0x655 and 0x419 SPLIT BY hi12 -- distance back to the DRAM READ")
print("=" * 78)
for target in (0x655, 0x419, 0x64B, 0x695, 0x2D9, 0x2DA):
    tab = collections.defaultdict(collections.Counter)
    for nm, s in STREAMS:
        for i, w in enumerate(s):
            if (w & 0xFFF) != target:
                continue
            tab[(hi(w), cls(w))][dist_read(s, i)] += 1
    print("\n  lo12 = 0x%03X" % target)
    for k in sorted(tab, key=lambda k: -sum(tab[k].values())):
        c = tab[k]
        n = sum(c.values())
        hit = n - c[None]
        print("    %03X.%X.**.%03X  n=%-3d  after-a-READ %d/%d  distances %s"
              % (k[0], k[1], target, n, hit, n,
                 " ".join("d%s:%d" % (d, m) for d, m in sorted(
                     c.items(), key=lambda x: (x[0] is None, x[0])))))

print()
print("=" * 78)
print("F2.  EVERY 0x680 SITE  (the reading my control killed)")
print("=" * 78)
for nm, s in STREAMS:
    for i, w in enumerate(s):
        if (w & 0xFFF) != 0x680:
            continue
        d = dist_read(s, i)
        ctx = " | ".join(fmt(s[j]) for j in range(max(0, i - 3), min(len(s), i + 2)))
        print("   %-24s w%-3d %-14s readdist=%-4s  [%s]"
              % (nm[:24], i, fmt(w), d, ctx))

print()
print("=" * 78)
print("F3.  THE RECURRING DELAY-TAP IDIOM  (read | classA.655 | .. | .419 | write)")
print("=" * 78)
n_idiom = 0
for nm, s in STREAMS:
    for i in range(len(s) - 4):
        if not is_read(s[i]):
            continue
        if (s[i + 1] & 0xFFF) not in (0x655, 0x695):
            continue
        if cls(s[i + 1]) != 0xA:
            continue
        n_idiom += 1
        if n_idiom <= 12:
            print("   %-24s w%-3d : %s"
                  % (nm[:24], i, " | ".join(fmt(s[i + k]) for k in range(5))))
print("   ... %d sites of `880.1.60.* | *.A.*.655/695`" % n_idiom)

print()
print("=" * 78)
print("F4.  hi12 f31 ACROSS THE THREE CONTEXTS  (the candidate ALU-op field)")
print("=" * 78)
f31c = collections.Counter()
for nm, s in STREAMS:
    for w in s:
        f31c[(hi(w) >> 1) & 7] += 1
print("  f31 histogram over %d words: %s"
      % (sum(f31c.values()), sorted(f31c.items())))
print("\n  the LFO minimal pair and its third sibling:")
print("    092.A.dd.200  f31=1  hi12 bits {1,4,7}   n=29   phase accumulate")
print("    094.A.dd.200  f31=2  hi12 bits {2,4,7}   n=29   wrap on 0x7FFFFF")
print("    09A.A.00.200  f31=5  hi12 bits {1,3,4,7} n=9    COMPRESSOR/kernel, SOLO")
print("    412.A.00.200  f31=1  hi12 bits {1,4,10}  n=1    kernel iw33")
