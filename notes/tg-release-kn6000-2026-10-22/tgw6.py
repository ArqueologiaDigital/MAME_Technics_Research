#!/usr/bin/env python3
# tgw6.py TGW.TXT FROM TO -- probe6.lua's TG write log between two emulated times, one write per line with its voice and
# register class decoded: "t vN cls CCCC addr data pc" (voice = addr bits 9:4, cls = addr & 0xFC0F). Used for the
# note-on, key-off and cls 0x0000 tables in README.md.
import sys
a, b = float(sys.argv[2]), float(sys.argv[3])
for l in open(sys.argv[1]):
    t, ad, d, pc = l.split()
    if a <= float(t) < b:
        A = int(ad, 16)
        print(f"{float(t):.6f} v{(A >> 4) & 0x3F:<2} cls {A & 0xFC0F:04X} {ad} {d} {pc}")
