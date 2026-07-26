#!/usr/bin/env python3
"""KN5000 IC303 PAN field — regenerate every ROM-side number in
notes/audit/kn5000-output-design.md §1.3.

The claim under test: `partial_block[+0x01]` of every patch partial in the
Table-Data ROM is the partial's PAN (0x00 .. 0x40 centre .. 0x7F), the value the
firmware propagates into IC303 register +0x180 bits[6:0]
(Voice_CC_Pan -> LABEL_032E1E -> tone-slot byte [+0x23]/[+0x24] -> +0x180).

Nothing here is fitted: the byte is read at a fixed offset in a record whose
alignment is self-verified against two independently-derived columns of
notes/data/kn5000-patch-partials.tsv (`fine` = [+0x02], `set` = [+0x03]).

Usage:  python3 tools/kn5000_pan_stats.py
Stdlib only.  Run from the kn7000_mame checkout.
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PARTIALS = os.path.join(REPO, 'notes/data/kn5000-patch-partials.tsv')
ROMDIR = os.path.expanduser('~/compartilhado/kn7000-emulator/roms/kn5000')

CENTRE = 0x40
PAN_OFF = 0x01          # partial_block[+0x01]


def table_data():
    """The 2 MB table_data region, interleaved exactly as kn5000.cpp:1131-1133
    loads it: ROM_LOAD32_WORD(even, 0), ROM_LOAD32_WORD(odd, 2) -- i.e. 16-bit
    words, even ROM supplying bytes 0-1 of each 4-byte group."""
    ev = open(os.path.join(ROMDIR, 'kn5000_table_data_rom_even.ic3'), 'rb').read()
    od = open(os.path.join(ROMDIR, 'kn5000_table_data_rom_odd.ic1'), 'rb').read()
    out = bytearray(len(ev) * 2)
    for k in range(len(ev) // 2):
        out[4 * k:4 * k + 2] = ev[2 * k:2 * k + 2]
        out[4 * k + 2:4 * k + 4] = od[2 * k:2 * k + 2]
    return out


def main():
    rom = table_data()
    rows = [l.rstrip('\n').split('\t') for l in open(PARTIALS)]
    hdr, rows = rows[0], rows[1:]
    ix = {k: i for i, k in enumerate(hdr)}

    ok_fine = ok_set = 0
    pans = collections.Counter()
    by_patch = collections.defaultdict(list)
    for r in rows:
        off = int(r[ix['region_off']], 16)
        if rom[off + 0x02] == int(r[ix['fine']], 16):
            ok_fine += 1
        if rom[off + 0x03] == int(r[ix['set']], 16):
            ok_set += 1
        p = rom[off + PAN_OFF]
        pans[p] += 1
        by_patch[(int(r[ix['patch']]), r[ix['name']].strip())].append(
            (int(r[ix['partial']]), p))

    n = len(rows)
    print("ALIGNMENT self-check (must be %d/%d both):  fine %d  set %d"
          % (n, n, ok_fine, ok_set))
    if ok_fine != n or ok_set != n:
        print("  !! record alignment is wrong -- every number below is meaningless")
        return 1

    print()
    print("PAN field  partial_block[+0x%02X]  over %d partials" % (PAN_OFF, n))
    print("  range                     : %d .. %d   (7-bit field: max must be 0x7F)"
          % (min(pans), max(pans)))
    print("  exactly 0x40 (centre)     : %d  (%.1f%%)" % (pans[CENTRE], 100 * pans[CENTRE] / n))
    print("  0x00 / 0x7F (the extremes): %d / %d" % (pans[0x00], pans[0x7F]))

    # mirror statistic: a pan layout pairs v with 128-v (0 <-> 127 at the ends)
    mirrored = 0
    for v, k in pans.items():
        m = 0x7F if v == 0x00 else (0x00 if v == 0x7F else 0x80 - v)
        mirrored += min(k, pans.get(m, 0))
    print("  values with a mirror partner (128-v): %d  (%.1f%%)"
          % (mirrored, 100 * mirrored / n))

    single = [(k, v[0][1]) for k, v in by_patch.items() if len(v) == 1]
    pairs = [(k, sorted(v)) for k, v in by_patch.items() if len(v) == 2]
    sym = sum(1 for _, v in pairs if v[0][1] + v[1][1] in (0x7F, 0x80))
    print()
    print("  single-partial patches centred : %d / %d"
          % (sum(1 for _, p in single if p == CENTRE), len(single)))
    print("    (the exceptions: %s)"
          % ', '.join("%s=0x%02X" % (k[1], p) for k, p in single if p != CENTRE))
    print("  two-partial patches mirror-paired: %d / %d  (%.1f%%)"
          % (sym, len(pairs), 100 * sym / len(pairs)))
    print("  partial-count histogram: %s"
          % sorted(collections.Counter(len(v) for v in by_patch.values()).items()))

    print()
    print("  stereo layouts (patches whose partials are not all centred), first 12:")
    shown = 0
    for k, v in by_patch.items():
        if any(x[1] != CENTRE for x in v) and len(v) >= 2:
            print("    %-20s %s" % (k[1], ' '.join("%02X" % x[1] for x in sorted(v))))
            shown += 1
            if shown == 12:
                break
    return 0


if __name__ == '__main__':
    sys.exit(main())
