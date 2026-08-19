#!/usr/bin/env python3
"""Standalone runtime-shaped walker: table_data ROM bytes -> selector->C table.
No tsv, no firmware-derived checked-in data. Mirrors what a C++ device_start()
would do against memregion("table_data")->base().
"""
import collections, os, re, sys
D = os.path.expanduser('~/compartilhado/kn7000-emulator/roms/kn5000')
ev = open(os.path.join(D, 'kn5000_table_data_rom_even.ic3'), 'rb').read()
od = open(os.path.join(D, 'kn5000_table_data_rom_odd.ic1'), 'rb').read()
img = bytearray(0x200000)
for i in range(0, len(ev), 2):                 # ROM_LOAD32_WORD interleave
    j = (i // 2) * 4
    img[j:j+2] = ev[i:i+2]; img[j+2:j+4] = od[i:i+2]

ROOT = 0x30000                                 # main 0x830000; the ONLY magic constant
u16 = lambda o: img[o] | img[o+1] << 8
u32 = lambda o: u16(o) | u16(o+2) << 16
s16 = lambda v: v - 0x10000 if v >= 0x8000 else v
rel = lambda r: ROOT + r                       # rel32 is relative to the root struct

set_base   = rel(u32(ROOT + 0x30))             # root+0x30/+0x34/+0x38 all equal
set_stride = u16(ROOT + 0xEC)                  # = 15
a2_tables  = [rel(u32(ROOT + o)) for o in (0x24, 0x28, 0x2C)]
n_sets     = (min(a2_tables) - set_base) // set_stride

W = collections.defaultdict(collections.Counter)
for i in range(n_sets):
    d      = set_base + set_stride * i
    flags  = img[d]
    stride = 6 if (flags & 0x80) else 4
    ptrA   = rel(u32(d + 1))
    ptrB   = rel(u32(d + 5))
    ptrC   = rel(u32(ptrA))
    root   = img[d + 0x0B]
    base   = u16(d + 0x0C)
    pivot  = (root << 8) + 0x80
    for key in range(128):
        E   = img[ptrA + 4 + img[ptrC + key]]
        rec = ptrB + stride * E
        sel = u16(rec)
        trim = s16(u16(rec + 4)) if stride == 6 else 0
        W[sel][(base - pivot) + trim] += 1

mine = {sel: (c.most_common(1)[0][0], 1 if len(c) > 1 else 0) for sel, c in W.items()}
print("walker: n_sets=%d  selectors=%d  ambiguous=%d"
      % (n_sets, len(mine), sum(a for _, a in mine.values())))

HXX = os.path.expanduser('~/compartilhado/kn7000_mame/src/mame/matsushita/kn5000_pitch_trim.hxx')
ship = {}
for m in re.finditer(r'\{\s*0x([0-9A-F]{4}),\s*(-?\d+),\s*(\d)\s*\}', open(HXX).read()):
    ship[int(m.group(1), 16)] = (int(m.group(2)), int(m.group(3)))
print("shipped .hxx: selectors=%d  ambiguous=%d" % (len(ship), sum(a for _, a in ship.values())))

only_m = set(mine) - set(ship); only_s = set(ship) - set(mine)
diff_c = [s for s in set(mine) & set(ship) if mine[s][0] != ship[s][0]]
diff_a = [s for s in set(mine) & set(ship) if mine[s][1] != ship[s][1]]
print("only-in-walker=%d  only-in-hxx=%d  C differs=%d  ambiguous-flag differs=%d"
      % (len(only_m), len(only_s), len(diff_c), len(diff_a)))
if only_m: print("  only-in-walker:", sorted('%04X' % s for s in only_m)[:20])
if only_s: print("  only-in-hxx   :", sorted('%04X' % s for s in only_s)[:20])
for s in sorted(diff_c)[:20]:
    print("  C  %04X walker=%d hxx=%d" % (s, mine[s][0], ship[s][0]))
for s in sorted(diff_a)[:20]:
    print("  AMB %04X walker=%d hxx=%d" % (s, mine[s][1], ship[s][1]))
print("IDENTICAL" if not (only_m or only_s or diff_c or diff_a) else "MISMATCH")
