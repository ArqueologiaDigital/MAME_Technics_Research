#!/usr/bin/env python3
"""Does the oracle's per-part "Parts 7/11 are at the right absolute pitch" survive a
register-level check?

The oracle scores a MIDI note as a HIT if the emulator produced an ONSET IN THAT PITCH BIN
within +-40 ms -- it never asks WHICH voice produced it.  Here the same test is run on the
captured note-on stream, where every voice's rendered pitch is known exactly:

    hit_any  = some voice, ANY part, renders within +-0.5 st of this note   <- oracle's test
    hit_own  = the voice that IS this note renders within +-0.5 st          <- the real thing

plus the oracle's own null (musical time displacement).
"""
import collections, math, os, random, sys
sys.path.insert(0, os.path.expanduser('~/compartilhado/kn7000_mame/tools'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'oracle'))
import kn5000_pitch_audit as A
import midiparse

HERE = os.path.dirname(os.path.abspath(__file__))
ORACLE = os.path.join(HERE, '..', 'oracle')
W = A.trim_table(A.read_sets())
Cmodal = {sel: c.most_common(1)[0][0] for sel, c in W.items()}

T0, BPM, TOL = 17.40, 90.00, 0.040

ev = []
for line in open(os.path.join(HERE, 'kon.log')):
    p = line.split()
    if len(p) == 5 and p[0] == 'KON':
        t, ch, sel, pit = float(p[1]), int(p[2]), int(p[3], 16), int(p[4], 16)
        if t >= 17.0 and pit and sel in Cmodal:
            ev.append((t, (pit - 128 - Cmodal[sel]) / 256.0, 60 + (pit - 0x3524) / 256.0, sel))
ev.sort()
mid = midiparse.read_smf(os.path.join(ORACLE, 'demo_preset_18.mid'))
div = mid['division']
mn, names = [], {}
for tr in mid['tracks']:
    for st, en, p, v, ti, ch in tr['notes']:
        mn.append((st / div, p, ti))
        names.setdefault(ti, tr.get('name') or str(ti))

grid = collections.defaultdict(list)
for e in ev:
    grid[int(e[0] / TOL)].append(e)


def probe(tp, pitch, which):
    b = int(tp / TOL)
    for bb in (b - 1, b, b + 1):
        for t, nB, nA, sel in grid.get(bb, ()):
            if abs(t - tp) > TOL:
                continue
            if which == 'any' and abs(nA - pitch) <= 0.5:
                return True
            if which == 'own' and abs(nB - pitch) <= 0.5 and abs(nA - pitch) <= 0.5:
                return True
    return False


def run(window, label):
    lo, hi = window
    rng = random.Random(11)
    per = collections.defaultdict(lambda: [0, 0, 0, 0.0])
    for beat, pitch, ti in mn:
        tp = T0 + beat * 60.0 / BPM
        if not (lo <= tp <= hi):
            continue
        d = per[ti]
        d[0] += 1
        d[1] += probe(tp, pitch, 'any')
        d[2] += probe(tp, pitch, 'own')
        # oracle's null: displace the note by a random musical amount, same pitch
        s = 0
        for _ in range(20):
            s += probe(tp + rng.choice([-8, -6, -4, -3, 3, 4, 6, 8]) * 60.0 / BPM, pitch, 'any')
        d[3] += s / 20.0
    print("\n== %s   t=%.1f..%.1f s ==" % (label, lo, hi))
    print("%-26s %5s %8s %8s %8s   %s" % ("part", "n", "hit_any", "null", "hit_own", "z(any)"))
    for ti in sorted(per):
        n, ha, ho, nu = per[ti]
        if n < 8:
            continue
        p0 = nu / n
        z = (ha - nu) / math.sqrt(max(n * p0 * (1 - p0), 1e-9))
        print("%-26s %5d %8.3f %8.3f %8.3f   %+6.2f"
              % (names.get(ti, str(ti))[:26], n, ha / n, p0, ho / n, z))


run((19.25, 28.0), "oracle sine-B window (engage at t=12)")
run((24.0, 37.2), "oracle sine-A window")
run((19.0, 70.0), "the whole capture")
