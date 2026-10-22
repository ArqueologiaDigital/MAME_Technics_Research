#!/usr/bin/env python3
"""tggates.py A.txt B.txt -- the note-on gates in two tgseq.lua captures: a write to the data port
(0x100002) while the latched address has no class bits (latch & 0xFFC0 == 0) and data 0x81nn, as
tools/rigs/kn5000_softkey_sweep.lua counts them. Prints how many each run has and whether the
(latch, data) gate sequences are the same, in order."""
import sys


def gates(p):
    latch, out = 0, []
    for line in open(p):
        off, data, mask = (int(x, 16) for x in line.split())
        if off < 0x100002:
            latch = data
        elif (latch & 0xFFC0) == 0 and (data & 0xFF00) == 0x8100:
            out.append((latch, data))
    return out


a, b = gates(sys.argv[1]), gates(sys.argv[2])
print(f'{sys.argv[1]}: {len(a)} gates; {sys.argv[2]}: {len(b)} gates; same sequence: {a == b}')
if a != b:
    i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
    print(f'first difference at gate {i}: {a[i] if i < len(a) else None} vs {b[i] if i < len(b) else None}')

# The same with the voice slot (the latch) left out: the firmware assigns voices by timing.
da, db = [d for _, d in a], [d for _, d in b]
print(f'gate data only: same sequence: {da == db}; equal as multisets: {sorted(da) == sorted(db)}')
import difflib
sm = difflib.SequenceMatcher(None, da, db, autojunk=False)
ops = [op for op in sm.get_opcodes() if op[0] != 'equal']
print(f'gate data edits from A to B: {len(ops)}', ops[:5])
