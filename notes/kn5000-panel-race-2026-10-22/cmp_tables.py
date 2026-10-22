#!/usr/bin/env python3
"""cmp_tables.py ROMDIR -- compare the KN5000 panel event-index table and the event -> action-list pointer
table between program versions. v10's addresses come from kn5000-docs control-panel-protocol.md
(event table 0xEDA03C, 128 bytes; PanelButton_ActionLists 0xED9C1E, 32 pointers); other versions' are
found by searching for v10's event table bytes."""
import sys
BASE = 0xE00000
d = sys.argv[1]
def rom(v): return open(f'{d}/kn5000_v{v}_program.rom', 'rb').read()
v10 = rom(10)
ev10 = v10[0xEDA03C - BASE:0xEDA03C - BASE + 128]
print('v10 event table:', ev10.hex())
for v in (5, 6, 7, 8, 9, 10):
    r = rom(v)
    hits = [i + BASE for i in range(len(r) - 128) if r[i:i + 128] == ev10]
    print(f'v{v}: event table at', [hex(h) for h in hits])

# The action-list pointer table (32 x u32) and the lists: v7 vs v10, event by event
def lists(r, at):
    out = []
    for i in range(32):
        p = int.from_bytes(r[at - BASE + 4 * i:at - BASE + 4 * i + 4], 'little')
        acts = []
        q = p - BASE
        while 0 <= q < len(r) and r[q] != 0xFF and len(acts) < 40:
            acts.append(r[q:q + 8].hex())
            q += 8
        out.append((p, acts))
    return out
for v in (7, 9):
    a, b = lists(rom(v), 0xED9C1E), lists(v10, 0xED9C1E)
    diff = [i for i in range(32) if a[i][1] != b[i][1]]
    print(f'v{v} vs v10 action lists: {len(diff)} of 32 events differ: {diff}')
    for i in diff[:3]:
        print(f'  event {i}: v{v} @ {a[i][0]:06x} {a[i][1][:4]}')
        print(f'  event {i}: v10 @ {b[i][0]:06x} {b[i][1][:4]}')

# The same lists with the handler address left out (bytes 0-3 only)
a, b = lists(rom(7), 0xED9C1E), lists(v10, 0xED9C1E)
diff = [i for i in range(32) if [x[:8] for x in a[i][1]] != [x[:8] for x in b[i][1]]]
print('v7 vs v10, handlers ignored: events that differ:', diff)
for i in (7,):
    print(f'event {i} v7 :', a[i][1]); print(f'event {i} v10:', b[i][1])
