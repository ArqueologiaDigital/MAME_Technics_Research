#!/usr/bin/env python3
"""Headline numbers, all at the FIXED recovered alignment (no re-optimisation),
so every null is constructed exactly like the measurement.

  MEASURED  hit@0        fraction of in-window MIDI notes whose pitch band has a
                         detected onset within +-40 ms of the predicted time
  NULL-T    time-shift   same notes, same pitches, times displaced by a random
                         2..40 beat offset (destroys timing, keeps everything else)
  NULL-P    pitch-perm   same times, pitches permuted among the notes (destroys
                         pitch, keeps timing and the pitch histogram)
  NULL-F    flat         surface occupancy = probability a note at a random
                         (pitch, time) lands on an onset cell
  BLIND     pitch-blind  fraction landing on a frame with SOME onset, any pitch
"""
import numpy as np

import oracle
import surface
from oracle import DT

RUNS = [
    ('CONTROL our own render', 'spec_ctrl.npz', 24.0, 37.2, 89.75, 25.451),
    ('SINE-A  sine.wav', 'spec_sine.npz', 24.0, 37.2, 89.75, 25.451),
    ('SINE-B  sine_early.wav', 'spec_sine2.npz', 16.0, 28.2, 90.75, 17.504),
    ('PCM     det1.wav', 'spec_det1.npz', 24.0, 54.5, 90.00, 25.477),
]
TOL_MS = 40.0
rng = np.random.default_rng(2024)

mid = oracle.read_smf('demo_preset_18.mid')
div = mid['division']
notes = [(st / div, p, ti) for t in mid['tracks'] for st, en, p, v, ti, ch in t['notes']]
drums = {10, 16}
mel = [n for n in notes if n[2] not in drums]

print(f'{"run":26s} {"subset":10s} {"n":>5s} {"hit@0":>7s} {"NULL-T":>7s} {"NULL-P":>7s} '
      f'{"NULL-F":>7s} {"z":>7s} {"BLIND":>7s} {"blindN":>7s}')
out = {}
for label, spec, t_lo0, t_hi, bpm, t0 in RUNS:
    B, pitches, times, _ = surface.onset_surface(spec, t_lo0, t_hi)
    t_lo = float(times[0])
    Bd = oracle.dilate(B, int(round(TOL_MS / 1000.0 / DT)))
    Any = Bd.max(axis=0)
    P, T = Bd.shape
    pm = int(pitches[0])
    occ = float(Bd.mean())

    def ev(ns, k=0, dbeat=0.0, blind=False):
        b = np.array([x[0] for x in ns]) + dbeat
        p = np.array([x[1] for x in ns])
        f = np.round((t0 + b * 60.0 / bpm - t_lo) / DT).astype(int)
        m = (f >= 0) & (f < T)
        f, p = f[m], p[m]
        if len(f) == 0:
            return 0.0, 0
        if blind:
            return float(Any[f].mean()), len(f)
        q = p - pm + k
        g = (q >= 0) & (q < P)
        return float(Bd[q[g], f[g]].sum()) / len(f), len(f)

    for sub, ns in (('all', notes), ('melodic', mel)):
        h, n = ev(ns)
        nt = [ev(ns, 0, rng.uniform(2, 40))[0] for _ in range(40)]
        npr = []
        for _ in range(40):
            perm = rng.permutation(len(ns))
            npr.append(ev([(ns[i][0], ns[perm[i]][1], ns[i][2])
                           for i in range(len(ns))])[0])
        bl, _ = ev(ns, blind=True)
        bln = [ev(ns, 0, rng.uniform(2, 40), blind=True)[0] for _ in range(40)]
        q = float(np.mean(nt))
        z = (h - q) / np.sqrt(max(q * (1 - q), 1e-9) / n)
        print(f'{label:26s} {sub:10s} {n:5d} {h:7.3f} {q:7.3f} {np.mean(npr):7.3f} '
              f'{occ:7.3f} {z:+7.1f} {bl:7.3f} {np.mean(bln):7.3f}')
        out[(label, sub)] = (h, q, float(np.mean(npr)), occ, z, bl, float(np.mean(bln)), n)

print('\nRECOVERY (emulator hit@0 as a fraction of the control\'s hit@0):')
for sub in ('all', 'melodic'):
    c = out[('CONTROL our own render', sub)][0]
    for label in ('SINE-A  sine.wav', 'SINE-B  sine_early.wav', 'PCM     det1.wav'):
        h = out[(label, sub)][0]
        print(f'   {label:26s} {sub:10s} {h:.3f} / {c:.3f} = {h/c:.2f}')
