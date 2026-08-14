#!/usr/bin/env python3
"""Which waveform page does each named KN5000 instrument actually play from?

Joins the tone-record table (instrument NAMES) to the wave addressing, using the decode
established 2026-08-14:

    bank = (class >> 2) & 1      page = class & 3      bank 1 = IC307 (the only real dump)

WHY IT MATTERS: detect_period()'s "P = N" fallback is wildly uneven across IC307's four
pages -- 11/198, 32/168, 500/1050, 0/57 -- so before treating that as a defect one has to
know what each page holds. This tool answers it from the firmware's own naming.

    python3 tools/kn5000_class_usage.py

Reference result (2026-08-14), which reframed task-queue item P11:

    class 0 (bank0 page0):     3 pairs  Silent, Square Click, Wind
    class 1 (bank0 page1):     1 pair   Pick Noise 1
    class 2 (bank0 page2):    25 pairs  Carillon, TublarBell A..
    class 3 (bank0 page3):    31 pairs  Fret Noise, Orch.Hit, Timpani..
    class 4 (bank1 page0):    60 pairs  AmbientHammer, Applause 1-7..
    class 5 (bank1 page1):   333 pairs  Agogo, Bongo, Analog Snare..   <- the percussion page
    class 6 (bank1 page2):     9 pairs  Organ Click -- entries 0x028,0x030..0x068, stride 8
    class 7 (bank1 page3):     0        <- nothing in this table names it

★ Page 2 has exactly ONE named user, "Organ Click", reaching 9 of its 1050 chunks; page 3 has
none at all. So the overwhelming majority of the chip is not referenced by any NAMED tone
record here. Either those chunks are reached by another mechanism (drum-kit map, rhythm
engine, sub-CPU) or they are genuinely unused. Until that is settled, do NOT read page 2's
period-detection failures as an audible defect -- almost nothing has been shown to play them.
An organ key-click is a transient, which fits page 2 holding one-shot material.

Note the multisample zone table (kn5000-multisample-sets.tsv) DOES reference classes 6 and 7
(77 and 128 refs), so the two tables disagree about what exists. That disagreement is itself
a finding and is being investigated separately.
"""
import collections
import os
import re
import sys

NAMES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "notes", "data", "kn5000-sample-name-table.tsv")


def main():
    if not os.path.exists(NAMES):
        sys.exit(f"missing {NAMES}")
    by_class = collections.defaultdict(set)
    rows = 0
    with open(NAMES) as fh:
        fh.readline()
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) < 9:
                continue
            rows += 1
            name = f[1].strip()
            # The field separates references with EITHER a comma or a semicolon. Splitting
            # on comma alone silently dropped the only two semicolon rows -- both "Organ
            # Click" -- and made class 6 look completely unreferenced. Corrected 2026-08-14.
            for ce in re.split(r"[;,]", f[8]):
                m = re.match(r"^(\d+):([0-9A-Fa-f]+)$", ce.strip())
                if m:
                    by_class[int(m.group(1))].add((name, int(m.group(2), 16)))

    print(f"tone records read: {rows}\n")
    print(f"{'class':>5} {'bank':>5} {'page':>5} {'(name,entry) pairs':>19}  sample of names")
    for c in range(8):
        pairs = by_class.get(c, set())
        names = sorted({n for n, _ in pairs})
        sample = ", ".join(names[:5]) if names else "-- none --"
        print(f"{c:>5} {(c >> 2) & 1:>5} {c & 3:>5} {len(pairs):>19}  {sample}")
    missing = [c for c in range(8) if not by_class.get(c)]
    if missing:
        print(f"\n★ classes with no named reference at all: {missing}")
        print("  (bank 1 = IC307; its page 2 alone holds 1050 of the chip's 1495 chunks)")


if __name__ == "__main__":
    main()
