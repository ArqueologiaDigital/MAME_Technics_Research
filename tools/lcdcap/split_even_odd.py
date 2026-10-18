#!/usr/bin/env python3
"""split_even_odd.py -- split a linear 4 MiB KN7000 flash image into the even/odd 2 MiB halves MAME's
kn7000 set loads with ROM_LOAD32_WORD (even = bytes 0,1 of each dword, odd = bytes 2,3). Used to run
the SP7001 build-942 program + table images in the kn7000 driver (which has no -bios for them).
Usage: python3 -I split_even_odd.py LINEAR.rom EVEN_OUT ODD_OUT
"""
import sys, hashlib
d = open(sys.argv[1], 'rb').read()
d = d + b'\xff' * (0x400000 - len(d))
ev = bytearray(); od = bytearray()
for i in range(0, 0x400000, 4):
    ev += d[i:i + 2]; od += d[i + 2:i + 4]
open(sys.argv[2], 'wb').write(ev); open(sys.argv[3], 'wb').write(od)
print(sys.argv[2], hashlib.sha1(ev).hexdigest()); print(sys.argv[3], hashlib.sha1(od).hexdigest())
