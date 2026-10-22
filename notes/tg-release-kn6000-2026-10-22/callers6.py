#!/usr/bin/env python3
# callers6.py PROG.BIN TARGET... -- every MN10300 relative call/jump in the KN6000 program image (mkprog6.py) whose
# destination is TARGET: call d16 (CD), call d32 (DD), jmp d16 (CC), jmp d32 (DC), calls d16 (FA FF), calls d32 (FC FF).
# A byte scan, so it can report a false hit inside data or mid-instruction; check each with dis6.sh (README.md here). BASE= overrides the load address 0x48400000.
import struct
import sys

BASE = int(__import__("os").environ.get("BASE", "0x48400000"), 16)
b = open(sys.argv[1], "rb").read()
targets = {int(t, 16) for t in sys.argv[2:]}
for i in range(len(b) - 6):
    pc = BASE + i
    op = b[i]
    hits = []
    if op in (0xCD, 0xCC):
        hits.append(("call16" if op == 0xCD else "jmp16", pc + struct.unpack_from("<h", b, i + 1)[0]))
    if op in (0xDD, 0xDC):
        hits.append(("call32" if op == 0xDD else "jmp32", (pc + struct.unpack_from("<i", b, i + 1)[0]) & 0xFFFFFFFF))
    if op == 0xFA and b[i + 1] == 0xFF:
        hits.append(("calls16", pc + struct.unpack_from("<h", b, i + 2)[0]))
    if op == 0xFC and b[i + 1] == 0xFF:
        hits.append(("calls32", (pc + struct.unpack_from("<i", b, i + 2)[0]) & 0xFFFFFFFF))
    for kind, dst in hits:
        if dst in targets:
            print("%08X %s -> %08X" % (pc, kind, dst))
