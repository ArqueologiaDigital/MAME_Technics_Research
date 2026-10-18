#!/usr/bin/env python3
"""patch_gate.py -- set the KN7000 program-ROM byte at CPU 0x4840000F (the debug gate read by
GetRomConfigByte 0x484D7928) to a new value in a scratch copy of kn7000_program_odd.rom.

MAME's kn7000 set loads the program with ROM_LOAD32_WORD: even file = bytes 0,1 of each dword,
odd file = bytes 2,3. Byte 0x0F of the image = dword 3, byte 3 -> odd file offset 3*2+1 = 7.

Usage: python3 patch_gate.py ODD_ROM_IN ODD_ROM_OUT [VALUE_HEX]   (default FF)
"""
import sys, hashlib, zlib
src, dst = sys.argv[1], sys.argv[2]
val = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0xFF
d = bytearray(open(src, 'rb').read())
print('odd[7] before = %02X' % d[7])
d[7] = val
open(dst, 'wb').write(d)
print('odd[7] after  = %02X' % d[7])
print('out crc32=%08x sha1=%s' % (zlib.crc32(d) & 0xffffffff, hashlib.sha1(d).hexdigest()))
