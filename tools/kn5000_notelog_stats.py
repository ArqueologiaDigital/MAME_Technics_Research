#!/usr/bin/env python3
"""Summarise a KN5000_NOTELOG per-note-on CSV.

Pure stdlib. Reads one or more capture CSVs and prints, per capture:

  * how many note-on gates were logged, and how they ENDED (peak/RMS buckets);
  * the CLICK vs SUSTAINED split, using the 10 ms envelope profile rather than a
    crest factor -- "a quick click then a very faint sound" and "a note at the right
    level" have similar peaks and only barely different RMS, but completely different
    profile SHAPES;
  * a contingency table of any register column against that split.

CLICK is defined as prof10ms[0] > 8 * max(prof10ms[5:]), i.e. the first 10 ms is more
than 18 dB above everything from 50 ms on. Notes that rendered nothing in their first
window are reported separately as 'zero' and are never counted as either.

    kn5000_notelog_stats.py CSV...                 # the standard summary
    kn5000_notelog_stats.py --by eg0_lvl CSV...    # split by any column
    kn5000_notelog_stats.py --where env_hand=255 --by eg0_lvl CSV...

--t0 drops rows before an emulated time (default 22.6, which is where the scripted
performance selection lands; earlier rows are the boot chime and the menu).
"""
import argparse
import collections
import csv
import os
import sys


def classify(row):
    prof = [int(x) for x in row["prof10ms"].split(";")]
    if prof[0] <= 0:
        return "zero"
    return "CLICK" if max(prof[5:]) * 8 < prof[0] else "SUST"


def load(path, t0, where):
    out = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            if float(r["t_on"]) < t0:
                continue
            if where and r.get(where[0]) != where[1]:
                continue
            out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+")
    ap.add_argument("--t0", type=float, default=22.6)
    ap.add_argument("--by", default=None, help="column to cross-tabulate against CLICK/SUST")
    ap.add_argument("--where", default=None, metavar="COL=VAL")
    ap.add_argument("--top", type=int, default=10)
    a = ap.parse_args()

    where = tuple(a.where.split("=", 1)) if a.where else None

    for path in a.csv:
        rows = load(path, a.t0, where)
        name = os.path.basename(path)
        if not rows:
            print(f"== {name}: no rows"); continue
        cls = collections.Counter(classify(r) for r in rows)
        n = len(rows)
        print(f"== {name}  notes={n}"
              f"  CLICK={cls['CLICK']} ({100*cls['CLICK']/n:.1f}%)"
              f"  SUST={cls['SUST']} ({100*cls['SUST']/n:.1f}%)"
              f"  zero={cls['zero']} ({100*cls['zero']/n:.1f}%)"
              + (f"   [{a.where}]" if where else ""))

        # outcome buckets on the voice's own contribution
        buckets = collections.Counter()
        for r in rows:
            p = float(r["peak"])
            buckets["silent" if p == 0 else
                    "<100" if p < 100 else
                    "<1000" if p < 1000 else
                    "<5000" if p < 5000 else ">=5000"] += 1
        print("   peak buckets:", dict(buckets))

        if a.by:
            tab = collections.defaultdict(collections.Counter)
            for r in rows:
                tab[r[a.by]][classify(r)] += 1
            order = sorted(tab, key=lambda k: -sum(tab[k].values()))[:a.top]
            print(f"   {a.by:>12} {'n':>7} {'CLICK':>7} {'SUST':>7} {'zero':>6}  %click")
            for k in order:
                c = tab[k]; tot = sum(c.values())
                print(f"   {k:>12} {tot:7d} {c['CLICK']:7d} {c['SUST']:7d} {c['zero']:6d}"
                      f"  {100*c['CLICK']/tot:5.1f}%")
        print()


if __name__ == "__main__":
    sys.exit(main())
