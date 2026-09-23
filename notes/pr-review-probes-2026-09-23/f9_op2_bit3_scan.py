#!/usr/bin/env python3
"""MEASURED 2026-09-23 on kn7000.zip:
      F9/FB/FD + op2 0x00-0x03 (mulq imm, implemented): 3615
      F9/FB/FD + op2 0x08-0x0B (AM33 mov, misdecoded):   209

   Backs a finding that survived adversarial refutation. Both figures are upper
   bounds - see the CAVEAT below - so 209 is "this encoding is present in the
   image", not "209 instructions execute wrongly". Feed the .ic17/.ic16 halves
   in as kn7000_program_{even,odd}.rom.

Question answered: does the KN7000 program ROM contain F9/FB/FD opcodes whose
op2 has bit 3 set (op2 0x08-0x0B)?  Those are AM33 `mov` per binutils
mn10300-opc.c (0xf90800 / 0xfb080000 / 0xfd080000), but mn10300.cpp:1006's
fast path `(op2 >> 4) == 0 && !BIT(op2, 2)` executes them as mulq-immediate.

CAVEAT: this is an UNFRAMED byte-pair scan.  It does not decode instruction
boundaries, so every count includes data bytes.  It is an upper bound and an
existence hint only -- NOT a measurement of executed instructions.

Run:  python3 f9_op2_bit3_scan.py <dir with kn7000_program_{even,odd}.rom>
"""
import sys, collections, os

d = sys.argv[1] if len(sys.argv) > 1 else '.'
e = open(os.path.join(d, 'kn7000_program_even.rom'), 'rb').read()
o = open(os.path.join(d, 'kn7000_program_odd.rom'), 'rb').read()
b = bytearray()
for i in range(len(e)):
    b += bytes((e[i], o[i]))

c = collections.Counter()
for i in range(len(b) - 1):
    if b[i] in (0xF9, 0xFB, 0xFD):
        c[(b[i], b[i + 1])] += 1

mulq = sum(v for k, v in c.items() if k[1] <= 0x03)          # implemented path
am33mov = sum(v for k, v in c.items() if 0x08 <= k[1] <= 0x0B)  # misdecoded path
print('F9/FB/FD + op2 0x00-0x03 (mulq imm, implemented): %d' % mulq)
print('F9/FB/FD + op2 0x08-0x0B (AM33 mov, misdecoded):  %d' % am33mov)
for k in sorted(c):
    if k[1] <= 0x0B:
        print('  %02X %02X: %d' % (k[0], k[1], c[k]))
