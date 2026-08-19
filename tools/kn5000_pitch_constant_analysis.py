#!/usr/bin/env python3
"""kn5000_pitch_constant_analysis.py -- what ARE the KN5000 pitch constants?

QUESTION ANSWERED: the tone generator HLE needs a per-selector constant C to recover the true
note behind the absolute pitch the firmware writes. It currently ships as a generated 1444-entry
table, which upstream MAME reviewers are likely to object to. Is that table reducible -- to a
smaller key, a formula, or nothing at all?

    python3 tools/kn5000_pitch_constant_analysis.py

Reads notes/data/kn5000-pitch-trim-table.tsv (produced by tools/kn5000_pitch_audit.py --emit-table)
and reports: how many distinct values there are, how many are zero, whether they are whole
semitones, whether the class alone predicts them, and how much they matter weighted by key span.

WHAT THE ANSWER MEANS: if C were a function of something the emulator already knows (the class
bits, the key range, the root note) the table could be replaced by a formula. If it is a property
of each RECORDING, it is empirical data and no formula exists -- only a table or a runtime read of
the firmware's own descriptors.
"""
import collections, csv, os, statistics, sys

TSV = os.path.join(os.path.dirname(__file__), '..', 'notes', 'data', 'kn5000-pitch-trim-table.tsv')


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else TSV
    rows = list(csv.DictReader(open(path), delimiter='\t'))
    cs = [int(r['C_modal']) for r in rows]
    print(f"{len(rows)} selectors, {len(set(cs))} distinct values of C")
    print(f"range {min(cs)} .. {max(cs)} (1/256 semitone) = {min(cs)/256:.2f} .. {max(cs)/256:.2f} semitones")

    zero = sum(1 for c in cs if c == 0)
    whole = sum(1 for c in cs if c % 256 == 0)
    print(f"C == 0            : {zero:5d}  ({100*zero/len(cs):.1f}%)  <- a C=0 fallback is correct for these")
    print(f"whole semitones   : {whole:5d}  ({100*whole/len(cs):.1f}%)")

    nz = [c for c in cs if c]
    if nz:
        nzw = sum(1 for c in nz if c % 256 == 0)
        print(f"of the {len(nz)} non-zero, whole semitones: {nzw} ({100*nzw/len(nz):.1f}%)"
              f" -- the rest are fractional, i.e. fine tuning, not transposition")
        print(f"   mean {statistics.mean(nz):.0f} ({statistics.mean(nz)/256:.2f} st),"
              f" median {statistics.median(nz):.0f}, stdev {statistics.pstdev(nz):.0f}")

    # Is the class enough of a key? If C were constant per class, 8 numbers would replace 1444.
    byclass = collections.defaultdict(set)
    for r in rows:
        byclass[r['class']].add(int(r['C_modal']))
    varying = [k for k, v in byclass.items() if len(v) > 1]
    print(f"\nclasses: {len(byclass)}; classes where C is NOT constant: {len(varying)}")
    print("   -> the class alone cannot predict C" if varying else "   -> C is a function of class alone!")

    tot = sum(int(r['key_weight']) for r in rows)
    nzwt = sum(int(r['key_weight']) for r in rows if int(r['C_modal']) != 0)
    print(f"\nkey-span weight carried by C != 0 selectors: {100*nzwt/tot:.1f}%")
    print("   -> ignoring C is not an option at that weight" if nzwt / tot > 0.2 else "")

    print(f"\nsmallest faithful representations:")
    print(f"   exceptions only (C != 0)      : {len(nz)} entries")
    print(f"   distinct values + index       : {len(set(cs))} values")
    return 0


if __name__ == '__main__':
    sys.exit(main())
