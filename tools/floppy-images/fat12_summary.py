#!/usr/bin/env python3
"""fat12_summary.py -- what is on a raw 1.44 MB floppy image, region by region?

Question it answers: how does a disk an instrument formatted (or a builder produced) lay out its
boot sector, FATs, root directory and data area? Prints the boot sector head, the 55 AA
signature, each region's first bytes and byte histogram, and every root-directory entry.
usage: python3 -I fat12_summary.py IMAGE.img
"""
import collections
import struct
import sys

d = open(sys.argv[1], "rb").read()
S = 512
print(f"size {len(d)}")
print("boot[0:62]  ", d[:62].hex(" "))
print("boot[510:512]", d[510:512].hex(), " nonzero bytes in boot[32:510]:", sum(1 for b in d[32:510] if b))
bps, spc, res, nf, rde, tot, med, spf = struct.unpack_from("<HBHBHHBH", d, 11)
root = res + nf * spf
data = root + rde * 32 // bps
for name, a, b in [("boot", 0, res), ("FAT1", res, res + spf), ("FAT2", res + spf, root),
                   ("root", root, data), ("data", data, tot)]:
    blk = d[a * S:b * S]
    c = collections.Counter(blk)
    print(f"{name:5s} sectors {a:4d}-{b - 1:4d}: first16 {blk[:16].hex(' ')}  histogram {dict(c.most_common(3))}")
for i in range(rde):
    e = d[root * S + 32 * i:root * S + 32 * i + 32]
    if e[0] == 0:
        break
    print(f"  entry {i}: {e.hex(' ')}  {e[:11]!r} attr {e[11]:02X}")
