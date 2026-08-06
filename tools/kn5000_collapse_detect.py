#!/usr/bin/env python3
"""KN5000: how many note-ons COLLAPSE into a click, in each render mode, and WHY.

Reads KN5000_NOTELOG CSVs (tools/kn5000_capture_perf.sh writes them) and classifies
every note-on from its own 10 ms envelope profile (`prof10ms`, 24 buckets = 240 ms of
per-voice post-pan peak amplitude).

WHY THIS DETECTOR AND NOT THE STEP DETECTOR. `|x[n]-x[n-1]| > 8000` needs a fundamental
above ~21 kHz to fire on a 16384-peak sine, so it physically CANNOT see a click in sine
mode: a "sine mode has zero clicks" result from it is a null that could not fail. This
one is a RATIO inside a single voice, so its sensitivity is the same at both levels --
and it prints the absolute peaks it worked from so that can be checked, not believed.

VERDICTS

    CLICK      the voice made an AUDIBLE attack and then, while its key was still down,
               fell >= COLLAPSE_DB below that attack and stayed there. This is the thing
               Felipe reports: "clicks in place of notes".
    SHORT      same shape, but the key came up before the tail window opened. A note that
               was ASKED to stop is not a defect; separating these is what stops the
               detector counting staccato, drum hits and rhythm chops.
    INAUDIBLE  the voice never reached AUDIBLE_PEAK at all. Also a defect -- a missing
               note -- but not a click, and mixing the two is what made the earlier
               numbers unreadable.
    OK         everything else.

MECHANISM, attributed per row from the registers in the same row:

    handoff-0  the group0/bank0 hand-off word carried magnitude 0 (`env_hand == 0`), so
               `sample * env_level / 0xFF` mutes the voice outright ~40 us after the gate.
    eg-target-N  the amplitude EG reached a segment whose target level is N (< 200), e.g.
               0x727F = level 114 = -53.06 dB under the derived 16-counts-per-octave law.
    other      neither; read the row.

    kn5000_collapse_detect.py CSV [CSV...]
    kn5000_collapse_detect.py --validate CSV   # show the verdict tracks the register cause
    kn5000_collapse_detect.py --sweep CSV      # show the answer is not knife-edge
"""
import argparse
import collections
import csv
import math
import statistics
import sys

BUCKET_S = 0.010      # one prof10ms bucket, from notelog_rec_t::PROF_SAMPLES
NPROF = 24
ATTACK_BUCKETS = 2    # attack peak = max over 0..20 ms
TAIL_FROM = 3         # the tail window opens at 30 ms
COLLAPSE_DB = 18.0    # tail this far below the attack peak = collapsed into a click
AUDIBLE_PEAK = 1000   # -30 dBFS. Below this the voice is not a click, it is a missing note.


def db(x):
    return 20.0 * math.log10(x) if x > 0 else -120.0


def mechanism(row):
    if int(row["env_hand"]) == 0:
        return "handoff-0"
    lvl = (int(row["eg2_end"], 16) >> 8) & 0xFF
    return f"eg-target-{lvl}" if lvl < 200 else "other"


def classify(row, collapse_db=COLLAPSE_DB, audible=AUDIBLE_PEAK):
    """-> (verdict, tail/attack in dB or None, attack peak)"""
    prof = [int(x) for x in row["prof10ms"].split(";")]
    atk = max(prof[:ATTACK_BUCKETS])
    if max(prof) < audible:
        return "INAUDIBLE", None, atk
    if atk < audible:
        return "OK", None, atk           # sounded, but not in its first 20 ms
    t_ko = float(row["t_ko_rel"])
    ko_b = NPROF if t_ko < 0.0 else int(t_ko / BUCKET_S)
    hi = min(NPROF, ko_b)
    if hi <= TAIL_FROM:
        return "SHORT", None, atk
    ratio = db(max(prof[TAIL_FROM:hi]) / atk)
    return ("CLICK" if ratio <= -collapse_db else "OK"), ratio, atk


def load(path, t0):
    with open(path, newline="") as fh:
        return [r for r in csv.DictReader(fh) if float(r["t_on"]) >= t0]


def report(path, rows):
    cls, mech, ratios, peaks = (collections.Counter(), collections.Counter(),
                                collections.defaultdict(list), collections.defaultdict(list))
    for r in rows:
        c, ratio, atk = classify(r)
        cls[c] += 1
        peaks[c].append(atk)
        if ratio is not None:
            ratios[c].append(ratio)
        if c == "CLICK":
            mech[mechanism(r)] += 1
    n = sum(cls.values())
    print(f"\n=== {path}   mode={rows[0]['mode']}   note-ons={n} ===")
    for c in ("CLICK", "SHORT", "OK", "INAUDIBLE"):
        v = cls[c]
        med_r = (f" med tail/atk {statistics.median(ratios[c]):7.1f} dB" if ratios[c]
                 else " " * 26)
        med_p = f" med attack peak {int(statistics.median(peaks[c])):6d}" if peaks[c] else ""
        print(f"  {c:9s} {v:5d}  {100.0*v/n:5.1f}% of note-ons{med_r}{med_p}")
    print(f"  CLICK FRACTION = {cls['CLICK']/n:.4f}   "
          f"NOT-A-PROPER-NOTE (CLICK+INAUDIBLE) = {(cls['CLICK']+cls['INAUDIBLE'])/n:.4f}")
    for m, v in mech.most_common(6):
        print(f"     click mechanism {m:18s} {v:5d}")
    return cls, n


def validate(path, rows):
    """The verdict must TRACK the register cause, and must be able to come out both ways."""
    print(f"\n--- VALIDATION: {path} ---")
    g = collections.defaultdict(collections.Counter)
    for r in rows:
        w = int(r["adv12_word"], 16)
        if int(r["env_hand"]) == 0:
            key = "hand-off word = 0"
        elif w == 0xFFFF:
            key = "never left segment 1"
        else:
            key = f"seg-1 decay target {(w >> 8) & 0xFF:3d}"
        g[key][classify(r)[0]] += 1
    for k, c in sorted(g.items(), key=lambda kv: -sum(kv[1].values()))[:8]:
        tot = sum(c.values())
        print(f"  {k:24s} n={tot:5d}  CLICK={c['CLICK']:5d} SHORT={c['SHORT']:5d} "
              f"OK={c['OK']:5d} INAUDIBLE={c['INAUDIBLE']:5d}   click fraction "
              f"{c['CLICK']/tot:.3f}")
    print("  A detector that could not fail would print the same fraction on every line.")


def sweep(path, rows):
    print(f"\n--- SENSITIVITY: {path} ---")
    print(f"  {'audible floor':>14s} " + "".join(f"{d:>10.0f} dB" for d in (12, 18, 24, 30)))
    for a in (328, 1000, 3277):
        row = f"  {a:>14d} "
        for d in (12.0, 18.0, 24.0, 30.0):
            k = sum(1 for r in rows if classify(r, d, a)[0] == "CLICK")
            row += f"{k:>13d}"
        print(row)
    print("  (rows = audible-peak floor in output LSBs, columns = collapse threshold)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+")
    ap.add_argument("--t0", type=float, default=22.6,
                    help="drop rows before this emulated time (boot chime + menu)")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--by", default=None)
    args = ap.parse_args()

    for path in args.csv:
        rows = load(path, args.t0)
        if not rows:
            print(f"{path}: no rows after t0={args.t0}", file=sys.stderr)
            continue
        report(path, rows)
        if args.validate:
            validate(path, rows)
        if args.sweep:
            sweep(path, rows)
        if args.by:
            tab = collections.defaultdict(collections.Counter)
            for r in rows:
                tab[r[args.by]][classify(r)[0]] += 1
            print(f"  --- by {args.by} (top 12) ---")
            for k, c in sorted(tab.items(), key=lambda kv: -sum(kv[1].values()))[:12]:
                print(f"    {k:>8s}  n={sum(c.values()):5d}  CLICK={c['CLICK']:5d} "
                      f"SHORT={c['SHORT']:5d} OK={c['OK']:5d} INAUDIBLE={c['INAUDIBLE']:5d}")


if __name__ == "__main__":
    main()
