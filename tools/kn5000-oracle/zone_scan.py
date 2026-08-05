#!/usr/bin/env python3
"""Does absolute-pitch accuracy vary OVER TIME or BY REGISTER?

The statistic is the same one kprofile.py uses: hit@0 minus its own
pitch-permuted null, computed INSIDE each bin.  Permuting within the bin keeps
the bin's own register and its own onset times, so the excess is pure
"did it play the right semitone, given that it played something here".

Run it on the emulator AND on our own render; the render is the calibration --
it says how big the excess is when the pitch is known to be right.

  zone_scan.py --spec spec_sineL.npz --t-lo 18 --t-hi 100 --bpm 90.02 --t0 17.425
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
ap.add_argument('--tol-ms', type=float, default=40.0)
ap.add_argument('--draws', type=int, default=200)
ap.add_argument('--tbins', type=int, default=6)
ap.add_argument('--tag', default='out')
a = ap.parse_args()

DRUMS = {10, 16}
rng = np.random.default_rng(31337)
B, pitches, times, _ = surface.onset_surface(a.spec, a.t_lo, a.t_hi)
t_lo = float(times[0])
Bd = oracle.dilate(B, int(round(a.tol_ms / 1000.0 / DT)))
P, T = Bd.shape
pm = int(pitches[0])

mid = oracle.read_smf(a.midi)
div = mid['division']
mel = [(st / div, p, ti) for t in mid['tracks']
       for st, en, p, v, ti, ch in t['notes'] if ti not in DRUMS]
print(f'== {a.tag} {a.spec} [{t_lo:.1f},{a.t_hi:.1f}] bpm={a.bpm} t0={a.t0}')


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


def excess(ns):
    h, n = ev(ns)
    if n < 8:
        return None
    nl = []
    for _ in range(a.draws):
        perm = rng.permutation(len(ns))
        nl.append(ev([(ns[i][0], ns[perm[i]][1], ns[i][2])
                      for i in range(len(ns))])[0])
    mu, sd = float(np.mean(nl)), float(np.std(nl))
    return n, h, mu, h - mu, (h - mu) / max(sd, 1e-9), len(set(x[1] for x in ns))


def show(label, ns):
    r = excess(ns)
    if r is None:
        print(f'   {label:34s}  (fewer than 8 notes in window)')
        return
    n, h, mu, ex, z, npit = r
    print(f'   {label:34s} n={n:4d} pitches={npit:3d}  hit@0={h:.3f} '
          f'nullP={mu:.3f}  EXCESS={ex:+.3f}  z={z:+6.2f}')


bmax = max(x[0] for x in mel)
print(f'\n-- OVER TIME ({a.tbins} bins, pitches permuted WITHIN the bin)')
edges = np.linspace(0, bmax, a.tbins + 1)
for i in range(a.tbins):
    sub = [x for x in mel if edges[i] <= x[0] < edges[i + 1]]
    ta = a.t0 + edges[i] * 60.0 / a.bpm
    tb = a.t0 + edges[i + 1] * 60.0 / a.bpm
    if not sub:
        continue
    show(f'beats {edges[i]:6.0f}-{edges[i+1]:6.0f}  t {ta:5.1f}-{tb:5.1f}s', sub)

print('\n-- BY REGISTER (one-octave bins, pitches permuted WITHIN the bin)')
for lo in range(24, 108, 12):
    sub = [x for x in mel if lo <= x[1] < lo + 12]
    if not sub:
        continue
    show(f'MIDI {lo:3d}-{lo+11:3d}', sub)

print('\n-- PER PART x TIME HALF (pitches permuted within the cell)')
tracks = {}
for x in mel:
    tracks.setdefault(x[2], []).append(x)
for ti in sorted(tracks):
    ns = tracks[ti]
    if len(ns) < 60:
        continue
    nm = (mid['tracks'][ti]['name'] or f'trk{ti}')[:22]
    mid_b = bmax / 2
    show(f'{nm} EARLY', [x for x in ns if x[0] < mid_b])
    show(f'{nm} LATE ', [x for x in ns if x[0] >= mid_b])

print('\n-- PER PART x REGISTER HALF (pitches permuted within the cell)')
for ti in sorted(tracks):
    ns = tracks[ti]
    if len(ns) < 60:
        continue
    nm = (mid['tracks'][ti]['name'] or f'trk{ti}')[:22]
    med = float(np.median([x[1] for x in ns]))
    show(f'{nm} LOW  (<{med:.0f})', [x for x in ns if x[1] < med])
    show(f'{nm} HIGH (>={med:.0f})', [x for x in ns if x[1] >= med])
