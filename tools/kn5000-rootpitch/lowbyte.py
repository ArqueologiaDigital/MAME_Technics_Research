#!/usr/bin/env python3
"""lowbyte.py -- how much of the pitch constant C is readable from the register stream?

QUESTION ANSWERED: the tone generator HLE needs C, a per-recording constant, to recover the true
note from register +0x400. The chip is never told C -- the sub-CPU folds it in before writing:

    +0x400 = (note << 8) + 0x80 + C + 2*fine + detune

One equation, two unknowns, so C cannot be recovered in full. BUT true notes are integers, so the
SUB-SEMITONE part of C survives in the low byte of +0x400 and can be read straight off the bus.

    python3 tools/kn5000-rootpitch/lowbyte.py

WHY IT MATTERS: 77 of the 1444 selectors are AMBIGUOUS -- the firmware tables give them more than
one C -- and the generator currently resolves them by taking a modal value, with ties broken by
dictionary insertion order. That is not a rule, it is an accident. The low byte gives a real one:
of the candidate C values for a selector, pick the one whose low byte matches the +0x400 the chip
was actually given. It can only choose among values the tables already list, so it is a refinement
and not a new source of data.

INPUT: kon.log in this directory -- a committed capture of note-on events from the built-in demo,
one line per gate: `KON <time> <voice> <selector> <pitch>`.
"""
import collections, csv, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
KON = os.path.join(HERE, 'kon.log')
TSV = os.path.join(REPO, 'notes', 'data', 'kn5000-pitch-trim-table.tsv')


def load_table():
    """selector -> (modal C, [all candidate C values])"""
    out = {}
    for r in csv.DictReader(open(TSV), delimiter='\t'):
        cands = []
        for part in r['all_C'].split(';'):
            if ':' in part:
                cands.append(int(part.split(':')[0]))
        out[int(r['sel'], 16)] = (int(r['C_modal']), cands or [int(r['C_modal'])])
    return out


def main():
    table = load_table()
    events = []
    for line in open(KON):
        f = line.split()
        if len(f) >= 5 and f[0] == 'KON':
            events.append((int(f[3], 16), int(f[4], 16)))
    print(f"{len(events)} note-on events, {len(table)} selectors in the table")

    def hit_rate(cfn):
        n = ok = 0
        for sel, pitch in events:
            if sel not in table:
                continue
            n += 1
            if ((pitch - 0x80 - cfn(sel)) & 0xff) == 0:
                ok += 1
        return ok, n

    ok, n = hit_rate(lambda s: table[s][0])
    print(f"integer-note hit rate with C from the table : {100*ok/n:5.1f}%  ({ok}/{n})")
    ok0, n0 = hit_rate(lambda s: 0)
    print(f"                    control, C = 0          : {100*ok0/n0:5.1f}%  ({ok0}/{n0})")

    single = {s for s, (_, c) in table.items() if len(set(c)) == 1}
    ok1 = n1 = 0
    for sel, pitch in events:
        if sel in single:
            n1 += 1
            if ((pitch - 0x80 - table[sel][0]) & 0xff) == 0:
                ok1 += 1
    if n1:
        print(f"          restricted to single-C selectors : {100*ok1/n1:5.1f}%  ({ok1}/{n1})")

    # Can the low byte separate the ambiguous selectors?
    amb = {s: set(c) for s, (_, c) in table.items() if len(set(c)) > 1}
    seen = collections.defaultdict(set)
    for sel, pitch in events:
        if sel in amb:
            seen[sel].add(pitch & 0xff)
    full = part = none = 0
    for s, cands in amb.items():
        lows = {c & 0xff for c in cands}
        if s not in seen:
            none += 1
        elif len(lows) == len(cands) and seen[s] <= lows:
            full += 1
        else:
            part += 1
    # Two DIFFERENT questions, and conflating them overstates the payoff:
    #   (a) IN PRINCIPLE: do a selector's candidate C values have distinct low bytes, so that a low
    #       byte COULD choose between them?
    #   (b) IN PRACTICE: did this capture actually observe that selector at all?
    principle = sum(1 for cands in amb.values() if len({c & 0xff for c in cands}) == len(cands))
    print(f"\nambiguous selectors: {len(amb)}")
    print(f"   candidates have distinct low bytes (could be separated) : {principle}")
    print(f"   observed in this capture at all                         : {len(amb) - none}")
    print(f"      of those, fully separated by what was observed       : {full}")
    print(f"      partially                                            : {part}")
    print(f"   never observed here (so unproven either way)            : {none}")
    print("\n   NOTE: the first line is an upper bound on the payoff, not the payoff. A selector\n"
          "   whose candidates differ in their low bytes can only be disambiguated when the machine\n"
          "   actually plays it, and most of these were never played in this capture.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
