#!/usr/bin/env python3
"""Did a kn5000_patch_probe.lua run actually SELECT the patches it claims to have tested?

This exists because a run that fails to select is INVISIBLE in its own results. On
2026-08-06 a ten-patch ORGAN & ACCORDION sweep produced ten holds, ten envelopes and ten
tidy rows of sustain measurements -- and seven of those patches had silently re-used the
previous patch's wave selector, because the panel had wandered onto the ENTERTAINER screen
and every later soft key landed there instead of on the sound list. Read as a result it
said "nine of ten organ patches sustain fine". What it actually said was "one organ patch
sustains fine, nine times".

So: before any per-patch conclusion is drawn from a run, this must pass. The check is that
consecutive patches differ in the set of wave selectors their note-on used. It is a
NECESSARY condition, not a sufficient one -- two genuinely different patches CAN share a
selector and differ only in envelope or drawbar mix, which is why a repeat is reported as
SUSPECT rather than as proof of failure, and why the LCD snapshot stays the final arbiter.
What it reliably catches is the failure mode above: a long unbroken run of identical
selectors where the patch was supposed to change every time.

usage: kn5000_patch_check.py <rundir> [<rundir> ...]
"""
import csv
import os
import sys


def check(d):
    marks = os.path.join(d, "marks.txt")
    notes = os.path.join(d, "notes.csv")
    if not (os.path.exists(marks) and os.path.exists(notes)):
        print("%s: missing marks.txt or notes.csv" % d)
        return 1
    rows = [r for r in csv.DictReader(open(notes)) if r.get("true_note", "-1") not in ("", "-1")]

    steps = []
    for line in open(marks):
        if line.startswith("#") or not line.strip():
            continue
        f = line.split()
        patch, t0 = (f[0], float(f[2])) if len(f) == 4 else (f[0], float(f[1]))
        if len(f) == 4 and int(f[1]) >= 0:
            continue                       # swept note, not a patch hold
        sels = sorted({r["sel040"] for r in rows if t0 - 0.2 <= float(r["t_on"]) <= t0 + 0.5})
        steps.append((patch, sels))

    print("== %s   %d patch steps" % (d, len(steps)))
    bad = 0
    prev = None
    for patch, sels in steps:
        flag = ""
        if prev is not None and sels and sels == prev:
            flag = "  <== SUSPECT: same selectors as the previous patch"
            bad += 1
        if not sels:
            flag = "  <== no note-on recorded"
            bad += 1
        print("  %-12s %s%s" % (patch, ",".join(sels) if sels else "-", flag))
        prev = sels
    print("  %d of %d steps suspect" % (bad, len(steps)))
    return bad


if __name__ == "__main__":
    rc = 0
    for d in sys.argv[1:]:
        rc += check(d)
    sys.exit(1 if rc else 0)
