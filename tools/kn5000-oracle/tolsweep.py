#!/usr/bin/env python3
"""Is the pitch RIGHT but the note-to-time assignment SCRAMBLED?

hit@0 == nullP@0 says the capture looks like the score with its pitches
permuted.  A permutation is exactly what a broken note DISPATCH would produce
while a broken pitch CALCULATION would not.  The two are separable by relaxing
the time tolerance: if the right pitch is played but a little early or late, or
in the wrong order inside a bar, then widening the window recovers the excess
over the null, whereas a genuinely wrong pitch never appears at any tolerance.

Every tolerance gets its own null, built by permuting the pitches over the same
note list and scored through the same dilation.

  tolsweep.py --spec spec_sineL.npz --t-lo 18 --t-hi 132.5 --bpm 90 --t0 17.419
"""
import argparse
import numpy as np

import oracle
import surface
from oracle import DT

ap = argparse.ArgumentParser()
ap.add_argument('--spec', required=True)
ap.add_argument('--midi', default='demo_preset_18.mid')
ap.add_argument('--t-lo', type=float, required=True)
ap.add_argument('--t-hi', type=float, required=True)
ap.add_argument('--bpm', type=float, required=True)
ap.add_argument('--t0', type=float, required=True)
ap.add_argument('--draws', type=int, default=40)
ap.add_argument('--tag', default='out')
a = ap.parse_args()

DRUMS = {10, 16}
rng = np.random.default_rng(2718)
B, pitches, times, _ = surface.onset_surface(a.spec, a.t_lo, a.t_hi)
t_lo = float(times[0])
mid = oracle.read_smf(a.midi)
div = mid['division']
mel = [(st / div, p, ti) for t in mid['tracks']
       for st, en, p, v, ti, ch in t['notes'] if ti not in DRUMS]

print(f'== {a.tag} {a.spec} [{t_lo:.1f},{a.t_hi:.1f}] bpm={a.bpm} t0={a.t0}')
print(f'   {"tol_ms":>7s} {"occ":>7s} {"n":>5s} {"hit@0":>7s} {"nullP":>7s} '
      f'{"EXCESS":>8s} {"z":>7s}')
for tol in (40, 80, 160, 320, 640, 1280):
    Bd = oracle.dilate(B, int(round(tol / 1000.0 / DT)))
    P, T = Bd.shape
    pm = int(pitches[0])
    occ = float(Bd.mean())

    def ev(ns):
        b = np.array([x[0] for x in ns])
        p = np.array([x[1] for x in ns])
        f = np.round((a.t0 + b * 60.0 / a.bpm - t_lo) / DT).astype(int)
        m = (f >= 0) & (f < T)
        f, p = f[m], p[m]
        if len(f) == 0:
            return 0.0, 0
        q = p - pm
        g = (q >= 0) & (q < P)
        return float(Bd[q[g], f[g]].sum()) / len(f), len(f)

    h, n = ev(mel)
    nl = []
    for _ in range(a.draws):
        perm = rng.permutation(len(mel))
        nl.append(ev([(mel[i][0], mel[perm[i]][1], mel[i][2])
                      for i in range(len(mel))])[0])
    mu, sd = float(np.mean(nl)), float(np.std(nl))
    print(f'   {tol:7d} {occ:7.3f} {n:5d} {h:7.3f} {mu:7.3f} {h-mu:+8.3f} '
          f'{(h-mu)/max(sd,1e-9):+7.2f}')
