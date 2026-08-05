#!/usr/bin/env python3
"""Mismatch breakdown at semitone shift 0 (the hypothesis under test), with the
identical breakdown for the positive control so every row has a reference."""
import numpy as np

import oracle
import surface
from oracle import DT

RUNS = [
    ('CONTROL', 'spec_ctrl.npz', 24.0, 37.2, 89.75, 25.451),
    ('SINE-A', 'spec_sine.npz', 24.0, 37.2, 89.75, 25.451),
    ('SINE-B', 'spec_sine2.npz', 16.0, 28.2, 90.75, 17.504),
    ('PCM', 'spec_det1.npz', 24.0, 54.5, 90.00, 25.477),
]
TOL_MS, WIDE_MS = 40.0, 250.0
mid = oracle.read_smf('demo_preset_18.mid')
div = mid['division']
notes = [(st / div, p, ti) for t in mid['tracks'] for st, en, p, v, ti, ch in t['notes']]

CATS = ['exact hit (right pitch, right time)',
        'right pitch, +-250 ms late/early',
        'octave error (+-12 / +-24)',
        'near-miss (+-1 or +-2 semitones)',
        'other pitch (some onset, wrong pitch)',
        'nothing at all (silence at that instant)']
print(f'{"category":40s}' + ''.join(f'{r[0]:>10s}' for r in RUNS))
table = {c: [] for c in CATS}
extra = {}
for label, spec, t_lo0, t_hi, bpm, t0 in RUNS:
    B, pitches, times, _ = surface.onset_surface(spec, t_lo0, t_hi)
    t_lo = float(times[0])
    Bd = oracle.dilate(B, int(round(TOL_MS / 1000.0 / DT)))
    Wide = oracle.dilate(B, int(round(WIDE_MS / 1000.0 / DT)))
    Any = Bd.max(axis=0)
    P, T = Bd.shape
    pm = int(pitches[0])
    cnt = {c: 0 for c in CATS}
    octdir = {}
    n = 0
    for b, p, ti in notes:
        f = int(round((t0 + b * 60.0 / bpm - t_lo) / DT))
        if f < 0 or f >= T:
            continue
        n += 1
        q = p - pm
        if 0 <= q < P and Bd[q, f] > 0.5:
            cnt[CATS[0]] += 1
            continue
        if 0 <= q < P and Wide[q, f] > 0.5:
            cnt[CATS[1]] += 1
            continue
        hit = None
        for k in (-12, 12, -24, 24):
            if 0 <= q + k < P and Bd[q + k, f] > 0.5:
                hit = k
                break
        if hit is not None:
            cnt[CATS[2]] += 1
            octdir[hit] = octdir.get(hit, 0) + 1
            continue
        if any(0 <= q + k < P and Bd[q + k, f] > 0.5 for k in (-2, -1, 1, 2)):
            cnt[CATS[3]] += 1
            continue
        if Any[f] > 0.5:
            cnt[CATS[4]] += 1
            continue
        cnt[CATS[5]] += 1
    for c in CATS:
        table[c].append(100.0 * cnt[c] / max(1, n))
    extra[label] = (n, octdir)
for c in CATS:
    print(f'{c:40s}' + ''.join(f'{v:9.1f}%' for v in table[c]))
print(f'{"in-window MIDI notes":40s}' + ''.join(f'{extra[r[0]][0]:10d}' for r in RUNS))
print('\noctave-error directions (semitones):')
for label, _, _, _, _, _ in RUNS:
    print(f'   {label:10s} {extra[label][1]}')
