#!/usr/bin/env python3
"""bit1_bus_test.py -- does the running machine agree that the flags-bit-1 extraction is wrong?

QUESTION ANSWERED: `tools/kn5000_pitch_audit.py` computes C as (basepitch - root_pivot) + trim
unconditionally. When a SET descriptor's flags byte has bit 1 set, the firmware substitutes the
literal 0x4280 for BOTH operands, so that term is identically zero and neither field is read
(kn5000_subprogram_v142.asm:16216-16260). The extractor therefore fabricates a +49/+57/+65 semitone
offset for 112 of 1444 selectors.

That argument comes from reading the disassembly. This tests it on the BUS instead, using the
oracle in reg080_note_oracle.py: on the note-derived branch, +0x080 bits[14:12] hold
T[note mod 12], so a wrong C shows up as a failed prediction on every note-on.

    python3 tools/kn5000-rootpitch/bit1_bus_test.py /tmp/tg-burst.log

RESULT (2026-08-19, 2182-burst demo capture) -- for the bit-1 selectors that the demo plays on the
note branch, dropping the coarse term (C = 0 here, since their trim is 0) fits every burst while
the shipped value fits few or none:

    selector   shipped C   agrees   with C=0
    00303C        12543     12/19      19/19
    00303D        12543      0/1        1/1
    00303E        12543      0/1        1/1

Two more bit-1 selectors (003002, 003003) appear only on the override branch, where this test does
not apply -- reported as "n/a" rather than as evidence either way.

This is INDEPENDENT of the disassembly and of the earlier corroboration (that the 13 bit-1 SETs are
exactly the 13 whose root byte is junk). Three lines of evidence, one conclusion.
"""
import collections, csv, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
T = [(2 * (n % 12)) // 3 for n in range(12)]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/tg-burst.log'
    sets = os.path.join(REPO, 'notes/data/kn5000-multisample-sets.tsv')

    tab = {int(r['sel'], 16): int(r['C_modal'])
           for r in csv.DictReader(open(os.path.join(REPO, 'notes/data/kn5000-pitch-trim-table.tsv')), delimiter='\t')}

    flags, recs = {}, collections.defaultdict(set)
    for r in csv.DictReader(open(sets), delimiter='\t'):
        fl = int(r['flags'], 16)
        blob = {}
        for part in r['finetune(E:hex)'].split(';'):
            if ':' in part:
                k, v = part.split(':')
                blob[int(k)] = v
        for i, z in enumerate(r['zones(lo-hi:class:entry)'].split(';')):
            if ':' not in z:
                continue
            _, cls, ent = z.split(':')
            sel = (int(cls) << 12) | int(ent, 16)
            flags[sel] = fl
            if i in blob and len(blob[i]) >= 2:
                recs[sel].add(bytes.fromhex(blob[i])[0])
    uniq = {s: list(v)[0] for s, v in recs.items() if len(v) == 1}

    pending = collections.defaultdict(dict)
    byse = collections.defaultdict(list)
    for line in open(path):
        if not line.startswith('TGB '):
            continue
        f = line.split()
        if len(f) != 4:
            continue
        latch, data = int(f[2], 16), int(f[3], 16)
        ch, reg = latch & 0x3f, latch & 0xffc0
        if reg == 0 and (data & 0xff00) == 0x8100:
            cur = pending.pop(ch, None)
            if cur and {0x40, 0x80, 0x400} <= set(cur):
                byse[cur[0x40]].append((cur[0x80], cur[0x400]))
            pending[ch] = {}
            continue
        pending[ch][reg] = data

    def hits(rows, c):
        return sum(1 for r80, r400 in rows if T[(((r400 - 0x80 - c) >> 8)) % 12] == ((r80 >> 12) & 7))

    print(f"{'sel':>6} {'branch':>9} {'bursts':>6} {'shipped C':>9} {'agrees':>7} {'with C=0':>9}  verdict")
    supports = contradicts = 0
    for sel in sorted(byse):
        if not (flags.get(sel, 0) & 0x02):
            continue
        rows = byse[sel]
        b = uniq.get(sel)
        branch = "override" if (b is not None and b & 0x80) else ("note" if b is not None else "unmapped")
        if branch != "note":
            print(f"{sel:06X} {branch:>9} {len(rows):6d} {tab.get(sel,0):9d} {'-':>7} {'-':>9}  n/a on this branch")
            continue
        hs, hz = hits(rows, tab.get(sel, 0)), hits(rows, 0)
        if hz == len(rows) and hs < len(rows):
            verdict = "SUPPORTS the bit-1 fix"
            supports += 1
        elif hs == len(rows) and hz < len(rows):
            verdict = "CONTRADICTS the bit-1 fix"
            contradicts += 1
        else:
            verdict = "inconclusive"
        print(f"{sel:06X} {branch:>9} {len(rows):6d} {tab.get(sel,0):9d} {hs:7d} {hz:9d}  {verdict}")

    print(f"\n{supports} selector(s) support the correction, {contradicts} contradict it")
    return 0


if __name__ == '__main__':
    sys.exit(main())
