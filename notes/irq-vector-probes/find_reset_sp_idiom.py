#!/usr/bin/env python3
"""Question answered: does each KN-family firmware set SP itself in its crt0,
and with what value?  Locates the idiom
    fc dc <imm32>  mov imm32,a0
    f2 f0          mov a0,sp
    f8 fe f4       add -0xc,sp
in a de-interleaved program ROM (loads at 0x48400000).
Usage: find_reset_sp_idiom.py <prog.bin> [...]
Pass  = exactly one hit, and its address is inside the crt0 reached from the
reset vector at file offset 0 (`jmp` d32 little-endian).
"""
import struct, sys
TAIL = bytes.fromhex('f2f0f8fef4')
for f in sys.argv[1:]:
    d = open(f, 'rb').read()
    assert d[0] in (0xcc, 0xdc), f'{f}: no jmp at reset vector'
    if d[0] == 0xdc:
        rv = 0x48400000 + struct.unpack('<I', d[1:5])[0]
    else:
        rv = 0x48400000 + struct.unpack('<H', d[1:3])[0]
    i, hits = 0, []
    while True:
        i = d.find(TAIL, i)
        if i < 0:
            break
        if d[i-6:i-4] == b'\xfc\xdc':
            hits.append((0x48400000+i-6, 0x48400000+i-4,
                         struct.unpack('<I', d[i-4:i])[0]))
        i += 1
    print(f'{f}: reset vector -> {rv:#010x}')
    for a, c, v in hits:
        print(f'    mov {v:#010x},a0 / mov a0,sp / add -0xc,sp  @ {a:#010x}'
              f'  (imm32 at {c:#010x})')
