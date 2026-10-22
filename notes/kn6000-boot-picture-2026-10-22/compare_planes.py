#!/usr/bin/env python3
"""compare_planes.py RUN_DIR -- is the KN6000 boot screen the table ROM's first 640x240 bytes?

Reads index.bin, companion.bin, table.bin and clut.bin written by planes.lua, prints the
shift at which the index plane matches the table ROM, how many bytes match, the table's
runs of 0xFF / 0x00 as screen rows (640 bytes per row), and CLUT entries 0x00 and 0xFF.
"""
import struct
import sys

r = sys.argv[1]
d = open(f'{r}/index.bin', 'rb').read()
c = open(f'{r}/companion.bin', 'rb').read()
t = open(f'{r}/table.bin', 'rb').read()

def score(s):
    return sum(d[i] == t[i + s] for i in range(2048, 150000, 7) if 0 <= i + s < len(t))

best = max(range(-1024, 1025), key=score)
n = sum(d[i] == t[i + best] for i in range(len(d)) if 0 <= i + best < len(t))
print(f'best shift {best}: index plane matches the table ROM in {n} of {len(d)} bytes')
print(f'index plane == companion plane in {sum(a == b for a, b in zip(d, c))} bytes')

runs, s = [], 0
for i in range(1, 0x25800 + 1):
    if i == 0x25800 or (t[i] == 0xff) != (t[s] == 0xff) or (t[i] == 0) != (t[s] == 0):
        if i - s >= 640:
            runs.append((s, i, t[s]))
        s = i
for a, b, v in runs:
    print(f'table bytes {a:#07x}-{b - 1:#07x}  rows {a // 640:3d}-{(b - 1) // 640:3d}  value {v:#04x}')

cl = open(f'{r}/clut.bin', 'rb').read()
for k in (0x00, 0xff):
    v = struct.unpack_from('<H', cl, 2 * k)[0]
    print(f'CLUT[{k:#04x}] = {v:#06x} = RGB555 ({(v >> 10 & 31) << 3}, {(v >> 5 & 31) << 3}, {(v & 31) << 3})')
