#!/usr/bin/env python3
# mkprog6.py ROMDIR OUT.bin -- the KN6000 program flash as the CPU sees it at 0x48400000: the two 16-bit ROMs
# interleaved word by word (ROM_LOAD32_WORD: even at +0, odd at +2), as kn7000.cpp loads them.
import sys
e = open(sys.argv[1] + "/kn6000_program_even.rom", "rb").read()
o = open(sys.argv[1] + "/kn6000_program_odd.rom", "rb").read()
out = bytearray(len(e) * 2)
for i in range(0, len(e), 2):
    out[2 * i:2 * i + 2] = e[i:i + 2]
    out[2 * i + 2:2 * i + 4] = o[i:i + 2]
open(sys.argv[2], "wb").write(out)
