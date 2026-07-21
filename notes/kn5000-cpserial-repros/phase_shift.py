#!/usr/bin/env python3
"""phase_shift.py <in.lua> <out.lua> <delta_seconds>

Shift EVERY scheduled event in a repro lua by the same delta: `press(t, ...)`,
`snap(t, ...)` and `at(t, ...)`.  The schedule is otherwise untouched, so the
run is the same 220 (or 90, or 38) presses in the same order at the same
intervals -- only the emulated-time PHASE changes.

Why it exists (2026-07-22): the CP-serial misframe is PHASE-DEPENDENT, and one
schedule samples exactly one phase.  The February oracle build maps every b3
press correctly at delta=0 and reproduces the original PIANO -> ORCHESTRAL PAD
scramble at delta=+0.017.  A one-phase clean run therefore proves nothing about
a build; sweep at least {0, +0.007, +0.017} before calling anything fixed or
broken.  See notes/kn5000-cpserial-INDEX.md, top section.

  python3 phase_shift.py b3.lua /tmp/b3_d17.lua 0.017
  ./run.sh b3_d17 /tmp/b3_d17.lua <binary>
"""
import re, sys

if len(sys.argv) != 4:
    sys.exit(__doc__)
src, dst, delta = sys.argv[1], sys.argv[2], float(sys.argv[3])
out = []
n = 0
for line in open(src):
    m = re.match(r'^(press|snap|at)\((\d+\.?\d*)(,.*)$', line)
    if m:
        line = "%s(%.4f%s\n" % (m.group(1), float(m.group(2)) + delta, m.group(3))
        n += 1
    out.append(line)
open(dst, 'w').write(''.join(out))
print("wrote %s: %d events shifted by %+.4f s" % (dst, n, delta))
