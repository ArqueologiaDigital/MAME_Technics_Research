#!/usr/bin/env python3
"""ramp_probe.py -- what are +0x1C0 and +0x600, the two registers that move DURING a note?

QUESTION ANSWERED: of the tone generator registers neither HLE decodes, these two behave unlike
all the others -- their values climb steadily while a note sounds instead of being set at the gate.
This measures the climb: how often, by how much, and whether the two are related.

    python3 tools/kn5000-rootpitch/ramp_probe.py /tmp/tg-burst2.log

ESTABLISHED (2026-08-19, 1705-gate capture, 64 voices):

  * BOTH are updated once per firmware tick. Median interval 24.58 ms against the firmware's
    measured bank-poll period of 24.576 ms -- so these are written by the periodic voice service
    routine, not by note-on handling.
  * They move IN LOCKSTEP: 350 positive steps each, 568 and 571 writes, all 64 voices.
  * With DIFFERENT step sizes: +0x1C0 steps by a median 94 (range 16..100), +0x600 by a median 7
    (range 1..8).
  * Neither ever steps down; both restart from zero, and about 42% of their zero writes fall within
    20 ms of a gate.

So: a per-voice quantity ramped by software over the first few hundred ms of a note. The obvious
candidates are delayed vibrato / LFO depth or a portamento glide, and this probe does not choose
between them -- see below for the experiment that would.

⚠ A WRONG CONCLUSION, recorded so it is not re-derived. On one voice the pairs read (16,1) (32,2)
  (48,3) (64,4)..., an exact 16x ratio, and it is tempting to call +0x1C0 a fine version of
  +0x600. It is not: across all voices, when both are non-zero the ratio spreads over 16.0, 14.0,
  4.97, 0.98, 1.97, 2.95... The clean run was one voice where both happened to ramp from zero
  together and the pairing sampled them at matching indices. Two independent ramps, updated on the
  same tick.

TO IDENTIFY THEM: capture a patch with obvious delayed vibrato (strings, a synth lead) held for
several seconds against one with none (a piano). If the ramp appears only on the vibrato patch and
its rate tracks the patch's vibrato delay, these are the LFO depth ramp.
"""
import collections, statistics, sys


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/tg-burst2.log'
    rows = []
    for line in open(path):
        if not line.startswith('TGB '):
            continue
        f = line.split()
        if len(f) == 4:
            rows.append((float(f[1]), int(f[2], 16), int(f[3], 16)))
    if rows and all(t == int(t) for t, _, _ in rows[:50]):
        print("⚠ timestamps are whole seconds -- the capture used mac.time.seconds instead of\n"
              "  mac.time:as_double(). Timing results from this file are meaningless.\n")

    for reg_name, REG in (("+0x1C0", 0x1C0), ("+0x600", 0x600)):
        seq = collections.defaultdict(list)
        gates = collections.defaultdict(list)
        for t, l, d in rows:
            ch, r = l & 0x3f, l & 0xffc0
            if r == 0 and (d & 0xff00) == 0x8100:
                gates[ch].append(t)
            elif r == REG:
                seq[ch].append((t, d))
        ivals, incs, downs = [], [], 0
        for s in seq.values():
            for i in range(1, len(s)):
                dt, dv = s[i][0] - s[i - 1][0], s[i][1] - s[i - 1][1]
                if 0 < dt < 0.2:
                    ivals.append(dt * 1000)
                    if dv > 0:
                        incs.append(dv)
                    elif dv < 0:
                        downs += 1
        n = sum(len(v) for v in seq.values())
        print(f"{reg_name}: {len(seq)} voices, {n} writes")
        if ivals:
            print(f"   update interval : median {statistics.median(ivals):6.2f} ms   "
                  f"(firmware bank poll = 24.576 ms)")
        if incs:
            print(f"   positive steps  : median {statistics.median(incs):6.0f}   "
                  f"range {min(incs)}..{max(incs)}   n={len(incs)}")
        print(f"   negative steps  : {downs}")
        near = tot = 0
        for ch, s in seq.items():
            for t, d in s:
                if d == 0:
                    tot += 1
                    near += any(abs(t - g) < 0.02 for g in gates.get(ch, ()))
        print(f"   zeroed near a gate: {near}/{tot}\n")
    return 0


if __name__ == '__main__':
    sys.exit(main())
