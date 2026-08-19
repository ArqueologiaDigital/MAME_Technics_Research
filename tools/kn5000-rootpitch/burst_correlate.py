#!/usr/bin/env python3
"""burst_correlate.py -- do any tone generator registers carry per-recording ROM data?

QUESTION ANSWERED: the sub-CPU writes ~23 words to IC303 per note-on and the HLE decodes eight.
The project owner's thesis: the multisample descriptor data the HLE needs must reach the chip
somehow, possibly PROCESSED rather than copied. This tests every register against three questions:

  1. Is its value a function of the RECORDING (constant per selector across different notes)?
     Such a register is carrying per-recording data -- the thing we are looking for.
  2. Does it encode the pitch constant C? (map each way and count pure groups)
  3. Do the selectors that the flags-bit-1 extraction bug affects look like C=0 selectors in
     these registers? That is live-machine evidence for the bug, independent of the disassembly.

    python3 tools/kn5000-rootpitch/burst_correlate.py /tmp/tg-burst.log

INPUT: a capture from tools/rigs/kn5000_tg_burst_capture.lua.

RESULTS as of 2026-08-19 (2071 bursts, 91 selectors, 31 registers written):
  * +0x040 (the selector itself), +0x0C0 and +0x4C0 are constant per selector -- but +0x0C0 has
    only 7 distinct values and +0x4C0 only 2, while C has 25 distinct over the same selectors,
    so neither can encode C. They look like bank/page or mode selects.
  * +0x140 has 12 distinct per-recording values and initially APPEARED to track C on a small
    sample; over all 51 selectors it does not (many C map to 7F58; C=0 maps to eight values).
    Recorded here so nobody re-derives that false lead.
  * The five observed bit-1 selectors carry +0x140 in {40DD, 6632}, and 6632 also occurs among
    normal selectors whose table C is 0 -- consistent with their true C being 0, i.e. with the
    extraction bug being real.
"""
import collections, csv, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))


def load_bursts(path):
    pending = collections.defaultdict(dict)
    per = collections.defaultdict(lambda: collections.defaultdict(set))
    notes = collections.defaultdict(set)
    n = 0
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
            if cur and 0x40 in cur:
                sel = cur[0x40]
                n += 1
                for r, v in cur.items():
                    per[sel][r].add(v)
                if 0x400 in cur:
                    notes[sel].add(cur[0x400])
            pending[ch] = {}
            continue
        pending[ch][reg] = data
    return per, notes, n


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/tg-burst.log'
    per, notes, nburst = load_bursts(path)

    C = {}
    for r in csv.DictReader(open(os.path.join(REPO, 'notes/data/kn5000-pitch-trim-table.tsv')), delimiter='\t'):
        C[int(r['sel'], 16)] = int(r['C_modal'])
    flags = {}
    for r in csv.DictReader(open(os.path.join(REPO, 'notes/data/kn5000-multisample-sets.tsv')), delimiter='\t'):
        fl = int(r['flags'], 16)
        for z in r['zones(lo-hi:class:entry)'].split(';'):
            if ':' in z:
                _, cls, ent = z.split(':')
                flags[(int(cls) << 12) | int(ent, 16)] = fl

    multi = [s for s in per if len(notes.get(s, ())) > 1]
    print(f"{nburst} bursts, {len(per)} selectors, {len(multi)} played at 2+ pitches\n")

    print("1. WHICH REGISTERS CARRY THE RECORDING RATHER THAN THE NOTE?")
    regs = sorted({r for s in per for r in per[s]})
    carriers = []
    for reg in regs:
        fixed = [s for s in multi if len(per[s].get(reg, ())) == 1]
        if len(fixed) != len(multi) or not fixed:
            continue
        vals = {list(per[s][reg])[0] for s in fixed}
        carriers.append((reg, len(vals)))
        print(f"   +0x{reg:03X}: constant per selector, {len(vals):3d} distinct values across recordings")
    if not carriers:
        print("   (none)")

    print(f"\n2. DOES ANY CARRIER ENCODE C?  (C has "
          f"{len({C[s] for s in multi if s in C})} distinct values here)")
    for reg, _ in carriers:
        pairs = [(C[s], list(per[s][reg])[0]) for s in multi if s in C and len(per[s].get(reg, ())) == 1]
        fwd, rev = collections.defaultdict(set), collections.defaultdict(set)
        for c, v in pairs:
            fwd[v].add(c)
            rev[c].add(v)
        pf = sum(1 for x in fwd.values() if len(x) == 1)
        pr = sum(1 for x in rev.values() if len(x) == 1)
        verdict = "ENCODES C" if pf == len(fwd) and len(fwd) > 2 else "does not encode C"
        print(f"   +0x{reg:03X}: value->C {pf}/{len(fwd)}, C->value {pr}/{len(rev)}   {verdict}")

    print("\n3. DO THE BIT-1 SELECTORS LOOK LIKE C=0 SELECTORS?")
    b1 = [s for s in per if flags.get(s, 0) & 0x02]
    zeros = [s for s in per if s in C and C[s] == 0 and not (flags.get(s, 0) & 0x02)]
    for reg in (0x140, 0x0C0):
        a = {list(per[s][reg])[0] for s in b1 if len(per[s].get(reg, ())) == 1}
        z = {list(per[s][reg])[0] for s in zeros if len(per[s].get(reg, ())) == 1}
        both = a & z
        print(f"   +0x{reg:03X}: bit-1 {{{' '.join(f'{v:04X}' for v in sorted(a))}}}  "
              f"shares {len(both)} value(s) with C=0 selectors"
              f"{' -> ' + ' '.join(f'{v:04X}' for v in sorted(both)) if both else ''}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
