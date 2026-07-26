#!/usr/bin/env python3
"""tests.py -- falsifiable tests of the UPPER=source / LOWER=adder-B reading.
Scratchpad-only."""
import collections

from dspcorpus import (load, kernel_blob, distinct_images, fields, fmt,
                       KERNEL_ADDR, EPILOGUE_ADDR)

rom, names, imgs = load()
_c, _ka, KW = kernel_blob(rom, KERNEL_ADDR)
_c, _ea, EW = kernel_blob(rom, EPILOGUE_ADDR)
DIST = distinct_images(imgs)

# "streams" = ordered word sequences we may look at adjacency inside
STREAMS = [list(KW), list(EW)] + [list(ws) for ws in DIST]
ALL = [w for s in STREAMS for w in s]


def UP(w):
    return (w & 0xFFF) >> 5


def LOW(w):
    return w & 0x1F


def cls(w):
    return (w >> 20) & 0xF


def hi(w):
    return (w >> 24) & 0xFFF


def store(w):
    return (hi(w) >> 4) & 1


def cursor(w):
    return (cls(w) >> 3) & 1


def f31(w):
    return (hi(w) >> 1) & 7


print("=" * 78)
print("T1.  lo12 = 0x200 -- ALWAYS class-A + store?  (the LFO form)")
print("=" * 78)
w200 = [w for w in ALL if (w & 0xFFF) == 0x200]
print("  n = %d ; class-A %d ; store-bit set %d ; cursor-fetch %d"
      % (len(w200), sum(1 for w in w200 if cls(w) == 0xA),
         sum(1 for w in w200 if store(w)), sum(1 for w in w200 if cursor(w))))
print("  hi12 values: %s" % collections.Counter(hi(w) for w in w200).most_common())
print("  BASE RATES over the whole corpus: class-A %.1f%%  store %.1f%%  cursor %.1f%%"
      % (100.0 * sum(1 for w in ALL if cls(w) == 0xA) / len(ALL),
         100.0 * sum(1 for w in ALL if store(w)) / len(ALL),
         100.0 * sum(1 for w in ALL if cursor(w)) / len(ALL)))

print()
print("=" * 78)
print("T2.  UPPER = lo12[11:5] -- per-family profile")
print("=" * 78)
print(" UP   n    cursor%%  store%%  classes                       lowers")
byu = collections.defaultdict(list)
for w in ALL:
    byu[UP(w)].append(w)
for u in sorted(byu, key=lambda x: -len(byu[x]))[:20]:
    ws = byu[u]
    cc = collections.Counter(cls(w) for w in ws)
    ll = collections.Counter(LOW(w) for w in ws)
    print("  %02X %4d  %5.1f  %5.1f   %-28s %s"
          % (u, len(ws), 100.0 * sum(1 for w in ws if cursor(w)) / len(ws),
             100.0 * sum(1 for w in ws if store(w)) / len(ws),
             " ".join("%X:%d" % kv for kv in sorted(cc.items())),
             " ".join("%02X:%d" % kv for kv in ll.most_common(7))))

print()
print("=" * 78)
print("T3.  LOWER = lo12[4:0] = 'adder B source'?")
print("    PREDICTION: LOWER = 0x15 means 'acc += P' (mac).  A word that")
print("    consumes P must be PRECEDED BY A MULTIPLY (a class-A word, which is")
print("    the only P producer).  LOWER = 0x00 (nop, 0x1C0, 0x200, 0x680)")
print("    should NOT be.  Measure distance to the nearest preceding class-A.")
print("=" * 78)


def dist_to_prev_classA(stream, i):
    for d in range(1, 9):
        if i - d < 0:
            return None
        if cls(stream[i - d]) == 0xA:
            return d
    return None


stats = collections.defaultdict(lambda: [0, 0, 0])   # lower -> [n, prev1, prev<=2]
for s in STREAMS:
    for i, w in enumerate(s):
        d = dist_to_prev_classA(s, i)
        st = stats[LOW(w)]
        st[0] += 1
        if d == 1:
            st[1] += 1
        if d is not None and d <= 2:
            st[2] += 1
tot = [0, 0, 0]
for s in STREAMS:
    for i, w in enumerate(s):
        d = dist_to_prev_classA(s, i)
        tot[0] += 1
        if d == 1:
            tot[1] += 1
        if d is not None and d <= 2:
            tot[2] += 1
print("  BASE RATE: prev word is class-A %.1f%% ; within 2 %.1f%%  (n=%d)"
      % (100.0 * tot[1] / tot[0], 100.0 * tot[2] / tot[0], tot[0]))
print("\n  LOWER   n    prev-is-classA%%   within-2%%")
for lo in sorted(stats, key=lambda x: -stats[x][0]):
    n, p1, p2 = stats[lo]
    if n < 20:
        continue
    print("   %02X  %5d      %6.1f          %6.1f"
          % (lo, n, 100.0 * p1 / n, 100.0 * p2 / n))

print()
print("=" * 78)
print("T4.  R1's store->write test, generalised to EVERY lo12")
print("    'is the immediately preceding word a bit-4 STORE?'")
print("=" * 78)
st2 = collections.defaultdict(lambda: [0, 0])
base = [0, 0]
for s in STREAMS:
    for i, w in enumerate(s):
        if i == 0:
            continue
        prev = store(s[i - 1])
        st2[w & 0xFFF][0] += 1
        st2[w & 0xFFF][1] += prev
        base[0] += 1
        base[1] += prev
print("  BASE RATE %d/%d = %.1f%%" % (base[1], base[0], 100.0 * base[1] / base[0]))
print("\n  lo12  UP LOW    n   preceded-by-store")
rows = [(lo, v[0], v[1]) for lo, v in st2.items() if v[0] >= 12]
for lo, n, p in sorted(rows, key=lambda r: -r[2] / r[1]):
    print("   %03X  %02X %02X %5d      %5.1f%%   (%d)"
          % (lo, lo >> 5, lo & 0x1F, n, 100.0 * p / n, p))

print()
print("=" * 78)
print("T5.  Does UPPER 0x32 really mean 'operand = mem[ptr]'?")
print("    Every u=0x32 word, with its class and its predecessor.")
print("=" * 78)
for s in STREAMS:
    for i, w in enumerate(s):
        if UP(w) != 0x32:
            continue
        prev = fmt(s[i - 1]) if i else "-"
        nxt = fmt(s[i + 1]) if i + 1 < len(s) else "-"
        print("   %-14s prev %-14s next %-14s ST(prev)=%d"
              % (fmt(w), prev, nxt, store(s[i - 1]) if i else -1))
        break   # one example per stream is enough
u32 = [w for w in ALL if UP(w) == 0x32]
print("  u=0x32 total %d ; lo12 %s ; classes %s"
      % (len(u32), collections.Counter(w & 0xFFF for w in u32).most_common(),
         collections.Counter(cls(w) for w in u32).most_common()))
