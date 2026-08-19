#!/usr/bin/env python3
"""burst_fields.py -- which tone generator registers carry the RECORDING, and which carry the NOTE?

QUESTION ANSWERED: the sub-CPU writes ~23 words to IC303 for every note-on, and only eight of the
chip's registers are decoded. The undecoded ones must carry something. This asks the one question
that separates the possibilities without needing to read a single instruction:

    for each register, is its value a function of the SELECTOR (the recording chosen),
    of the NOTE, of both, or of neither?

A register whose value is constant for a given selector across many different notes is carrying
PER-RECORDING data -- which is exactly the data the HLE is missing, and which the firmware must have
got from the multisample descriptors in ROM. That is the "processed before being sent" case.

    python3 tools/kn5000-rootpitch/burst_fields.py /tmp/tg-burst.log

INPUT: a capture from tools/rigs/kn5000_tg_burst_capture.lua -- lines of `TGB <t> <latch> <data>`.
The latch is (group << 8) | (bank << 6) | channel, so writes are grouped per voice and a burst is
segmented at each note-on gate (group 0, data 0x81xx).

READ THE OUTPUT LIKE THIS:
  * "varies with note only"      -> pitch-ish, already understood
  * "constant per selector"      -> PER-RECORDING DATA REACHING THE CHIP. Investigate immediately.
  * "constant overall"           -> a fixed configuration word
  * "varies with both"           -> a computed mix; worth decomposing
"""
import collections, sys


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/tg-burst.log'
    # per voice: the registers written since that voice's last gate
    pending = collections.defaultdict(dict)
    sel_of = {}
    # observations[latch_group][selector] = set of values seen
    obs = collections.defaultdict(lambda: collections.defaultdict(set))
    # and how many distinct notes (pitch values) that selector was played at
    notes = collections.defaultdict(set)
    bursts = 0

    for line in open(path):
        if not line.startswith('TGB '):
            continue
        f = line.split()
        if len(f) != 4:
            continue
        latch, data = int(f[2], 16), int(f[3], 16)
        ch = latch & 0x3f
        reg = latch & 0xffc0

        if reg == 0x0000 and (data & 0xff00) == 0x8100:
            # a gate: close the previous burst for this voice and open a new one
            cur = pending.pop(ch, None)
            if cur and 0x0040 in cur:
                sel = cur[0x0040]
                bursts += 1
                for r, v in cur.items():
                    obs[r][sel].add(v)
                if 0x0400 in cur:
                    notes[sel].add(cur[0x0400])
            pending[ch] = {}
            continue
        pending[ch][reg] = data

    print(f"{bursts} complete note-on bursts, {len(obs)} distinct registers written\n")
    print(f"{'register':>9}  {'selectors':>9}  {'1 value':>8}  {'multi':>6}   verdict")
    for reg in sorted(obs):
        per = obs[reg]
        # restrict to selectors that were played at MORE THAN ONE pitch, otherwise
        # "constant per selector" is trivially true and means nothing
        useful = {s: v for s, v in per.items() if len(notes.get(s, ())) > 1}
        if not useful:
            print(f"    +0x{reg:03X}  {len(per):9d}  {'-':>8}  {'-':>6}   (never seen at 2+ notes)")
            continue
        one = sum(1 for v in useful.values() if len(v) == 1)
        multi = len(useful) - one
        allv = set()
        for v in useful.values():
            allv |= v
        if len(allv) == 1:
            verdict = "constant overall (configuration)"
        elif one == len(useful):
            verdict = "*** CONSTANT PER SELECTOR -- per-recording data ***"
        elif one == 0:
            verdict = "varies within selector (note-dependent)"
        else:
            verdict = f"mixed: {one} selectors fixed, {multi} vary"
        print(f"    +0x{reg:03X}  {len(useful):9d}  {one:8d}  {multi:6d}   {verdict}")

    print("\nSelectors played at 2+ distinct pitches: "
          f"{sum(1 for s in notes if len(notes[s]) > 1)} of {len(notes)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
