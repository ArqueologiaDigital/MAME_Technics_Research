#!/usr/bin/env python3
"""How much of each KN5000 waveform page do the multisample sets actually reference?

Companion to kn5000_class_usage.py (which joins instrument NAMES). This one works from the
multisample zone table and additionally asks whether a class appears ALONE in a set or MIXED
with other classes -- mixing proves the page is played as part of an ordinary instrument
rather than being some isolated special-purpose bank.

Addressing: bank = (class >> 2) & 1, page = class & 3; bank 1 = IC307, the only real dump.

    python3 tools/kn5000_zone_class_usage.py

Reference result (2026-08-14) -- the numbers that reframed task-queue item P11:

    class 6 (IC307 page 2): 12 of 487 sets, 49 distinct entries
    class 7 (IC307 page 3): 12 of 487 sets, 57 distinct entries
    class 5 (IC307 page 1): 202 sets, 164 entries      <- the percussion page, heavily used

★ Page 2 declares 1050 chunks but only 49 are ever referenced here -- about a thousand chunks
that nothing is known to play. Page 3 by contrast is fully used: 57 entries for 57 slots.
This matters because detect_period()'s "P = N" fallback fires on 500 of page 2's chunks,
which is 92% of the whole chip's 543 fallbacks. If those chunks are never played, that
statistic describes silence, not an audible defect.

★ 8 of the 12 class-6 sets MIX class 6 with classes 0, 1, 5 or 7, so the ~49 referenced
page-2 chunks ARE part of ordinary instruments -- they are not an isolated bank. Any fix
should be judged on those 49, not on all 1050.

Written by an analysis agent during the page-2 investigation; rescued from scratch and
kept because its numbers are quoted in the notes.
"""
import csv, collections, sys
D='/home/fsanches/compartilhado/kn7000_mame/notes/data/'
sets={}
cls_sets=collections.defaultdict(set)   # class -> set of set_idx
set_cls=collections.defaultdict(set)    # set_idx -> classes
cls_entries=collections.defaultdict(set)
with open(D+'kn5000-multisample-sets.tsv') as f:
    r=csv.DictReader(f,delimiter='\t')
    for row in r:
        si=int(row['set_idx'])
        sets[si]=row
        for z in row['zones(lo-hi:class:entry)'].split(';'):
            if not z: continue
            rng,c,e=z.split(':')
            c=int(c); e=int(e,16)
            cls_sets[c].add(si); set_cls[si].add(c); cls_entries[c].add(e)
print("total SETs:",len(sets))
for c in sorted(cls_sets):
    print(f"class {c}: {len(cls_sets[c])} SETs, {len(cls_entries[c])} distinct entries, min 0x{min(cls_entries[c]):03X} max 0x{max(cls_entries[c]):03X}")
print()
print("SETs containing class 6:", sorted(cls_sets[6]))
print("count:",len(cls_sets[6]))
print()
print("class-6 SETs that are PURE class 6:", sorted(s for s in cls_sets[6] if set_cls[s]=={6}))
print("class-6 SETs that MIX:", {s:sorted(set_cls[s]) for s in sorted(cls_sets[6]) if set_cls[s]!={6}})
