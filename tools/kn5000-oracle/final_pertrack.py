#!/usr/bin/env python3
"""Definitive per-part table, pooled over the two independent SINE captures and
checked against the positive control.

For each MIDI part and each capture:
    hit rate at semitone shift 0
    the matched null  = the SAME notes with a random musical time shift, at
                        shift 0, averaged over many draws (no max, so no
                        selection bias)
    binomial z of the observed hit count against that null rate
    the full shift profile, to see whether the peak really sits at 0
"""
import numpy as np

import oracle
import surface
from oracle import DT

RUNS = [
    ('sine-A  (sine.wav, demo engaged t=20)', 'spec_sine.npz', 24.0, 37.2, 89.75, 25.451),
    ('sine-B  (sine_early.wav, engaged t=12)', 'spec_sine2.npz', 16.0, 28.2, 90.75, 17.504),
    ('CONTROL (our own render)', 'spec_ctrl.npz', 24.0, 37.2, 89.75, 25.451),
    ('PCM     (det1.wav)', 'spec_det1.npz', 24.0, 54.5, 90.00, 25.477),
]
KMAX = 36
TOL_MS = 40.0
rng = np.random.default_rng(99)

mid = oracle.read_smf('demo_preset_18.mid')
div = mid['division']
tracks = {}
for t in mid['tracks']:
    for st, en, p, v, ti, ch in t['notes']:
        tracks.setdefault(ti, []).append((st / div, p))

pool = {}
for label, spec, t_lo0, t_hi, bpm, t0 in RUNS:
    B, pitches, times, _ = surface.onset_surface(spec, t_lo0, t_hi)
    t_lo = float(times[0])
    Bd = oracle.dilate(B, int(round(TOL_MS / 1000.0 / DT)))
    P, T = Bd.shape
    pm = int(pitches[0])
    occ = float(Bd.mean())

    def hits(items, k=0, shift_beats=0.0):
        b = np.array([x[0] for x in items]) + shift_beats
        p = np.array([x[1] for x in items])
        f = np.round((t0 + b * 60.0 / bpm - t_lo) / DT).astype(int)
        m = (f >= 0) & (f < T)
        f, p = f[m], p[m]
        q = p - pm + k
        g = (q >= 0) & (q < P)
        if len(f) == 0:
            return 0, 0
        return float(Bd[q[g], f[g]].sum()), len(f)

    print(f'\n=== {label}   ({bpm} bpm, t0={t0}s, occupancy {occ*100:.2f}%)')
    print('   part                      n   hit@0   null@0   z      argmax-k  peak   '
          'peak/mean-over-k')
    for ti in sorted(tracks):
        h, n = hits(tracks[ti])
        if n < 10:
            continue
        nl = []
        for _ in range(60):
            h2, n2 = hits(tracks[ti], 0, rng.uniform(2.0, 40.0))
            if n2 >= 10:
                nl.append(h2 / n2)
        q0 = float(np.mean(nl)) if nl else occ
        z = (h / n - q0) / np.sqrt(max(q0 * (1 - q0), 1e-9) / n)
        prof = np.array([hits(tracks[ti], k)[0] / n for k in range(-KMAX, KMAX + 1)])
        kb = int(np.argmax(prof)) - KMAX
        name = (mid['tracks'][ti]['name'] or f'trk{ti}')[:24]
        print(f'   {ti:2d} {name:24s} {n:4d}  {h/n:.3f}   {q0:.3f}  {z:+6.2f}   '
              f'{kb:+3d}    {prof.max():.3f}   {prof.max()/max(prof.mean(),1e-9):.2f}')
        pool.setdefault(ti, []).append((label, n, h, q0, z, kb, prof))

print('\n\n=== POOLED over the two SINE captures (A + B) ===')
print('   part                     n    hit@0   null@0    z       shift profile peak')
for ti in sorted(pool):
    rows = [r for r in pool[ti] if r[0].startswith('sine')]
    if len(rows) < 2:
        continue
    n = sum(r[1] for r in rows)
    h = sum(r[2] for r in rows)
    q0 = sum(r[3] * r[1] for r in rows) / n
    z = (h / n - q0) / np.sqrt(max(q0 * (1 - q0), 1e-9) / n)
    prof = sum(r[6] * r[1] for r in rows) / n
    kb = int(np.argmax(prof)) - KMAX
    name = (mid['tracks'][ti]['name'] or f'trk{ti}')[:24]
    print(f'   {ti:2d} {name:24s} {n:4d}   {h/n:.3f}   {q0:.3f}  {z:+6.2f}   '
          f'argmax k={kb:+3d} ({prof.max():.3f})')
    if abs(z) > 3:
        top = np.argsort(-prof)[:6]
        print('        profile top-6 shifts:',
              ', '.join(f'{k-KMAX:+d}:{prof[k]:.2f}' for k in top))
