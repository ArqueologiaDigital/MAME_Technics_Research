#!/usr/bin/env python3
"""At a FIXED alignment, ask three further questions:

  1. PITCH-BLIND timing: does the capture have an onset at ANY pitch at the
     moment the MIDI says a note starts?  (with its own null)
  2. PER-PART transposition: the tone generator's fallback pitch comes from
     reg[8] minus a per-chunk trim that the project has NOT decoded, so any
     transposition error is expected to be PER PART, not global.  For each MIDI
     part, sweep a semitone shift and see whether a sharp peak exists.
  3. The best-shift-per-part score, against the null of doing exactly the same
     sweep on time-randomised MIDI (which absorbs the max-over-73-shifts bias).

  pertrack.py --spec spec_sine.npz --t-lo 24 --t-hi 37.2 --bpm 89.75 --t0 25.451
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
ap.add_argument('--kmax', type=int, default=36)
ap.add_argument('--seed', type=int, default=7)
ap.add_argument('--tag', default='')
a = ap.parse_args()
rng = np.random.default_rng(a.seed)

B, pitches, times, onlist = surface.onset_surface(a.spec, a.t_lo, a.t_hi)
t_lo = float(times[0])
w = int(round(a.tol_ms / 1000.0 / DT))
Bd = oracle.dilate(B, w)
Any = Bd.max(axis=0)
P, T = Bd.shape
pm = int(pitches[0])
occ = float(Bd.mean())
occ_any = float(Any.mean())

mid = oracle.read_smf(a.midi)
div = mid['division']
tracks = {}
for t in mid['tracks']:
    for st, en, p, v, ti, ch in t['notes']:
        tracks.setdefault(ti, []).append((st / div, p, v))

print(f'== per-part analysis  {a.spec}  {a.tag}')
print(f'   alignment: {a.bpm} bpm, t0={a.t0}s, window {t_lo:.2f}-{float(times[-1]):.2f}s')
print(f'   surface occupancy per (pitch,time) = {occ*100:.2f}%; '
      f'ANY-pitch occupancy per time = {occ_any*100:.2f}%')


def frames(beats):
    return np.round((a.t0 + np.asarray(beats) * 60.0 / a.bpm - t_lo) / DT).astype(int)


# ---------------- 1. pitch-blind timing -------------------------------------
allb = np.array([b for ti in tracks for b, p, v in tracks[ti]])
fr = frames(allb)
ok = (fr >= 0) & (fr < T)
blind = Any[fr[ok]].mean()
nulls = []
for _ in range(20):
    sh = rng.uniform(2.0, 30.0)
    f2 = frames(allb + sh)
    o2 = (f2 >= 0) & (f2 < T)
    if o2.sum() > 50:
        nulls.append(Any[f2[o2]].mean())
print(f'\n   1. PITCH-BLIND timing: {blind:.3f} of {int(ok.sum())} in-window MIDI '
      f'onsets land on a frame that has SOME onset')
print(f'      null (same notes, random beat shift): {np.mean(nulls):.3f} '
      f'+- {np.std(nulls):.3f}   flat rate {occ_any:.3f}')

# ---------------- 2/3. per-part semitone sweep ------------------------------
ks = np.arange(-a.kmax, a.kmax + 1)


def sweep(items, shifted_by=0.0):
    b = np.array([x[0] for x in items]) + shifted_by
    p = np.array([x[1] for x in items])
    f = frames(b)
    m = (f >= 0) & (f < T)
    f, p = f[m], p[m]
    if len(f) == 0:
        return None, 0, None
    sc = np.zeros(len(ks))
    for j, k in enumerate(ks):
        q = p - pm + k
        good = (q >= 0) & (q < P)
        sc[j] = Bd[q[good], f[good]].sum() / max(1, len(f))
    return sc, len(f), ks


print(f'\n   2. PER-PART semitone sweep (k = {-a.kmax}..{a.kmax})')
print('      part  n   score@0   best-k  score@best   null(best-k on shuffled time)')
rows = []
for ti in sorted(tracks):
    sc, n, _ = sweep(tracks[ti])
    if sc is None or n < 8:
        continue
    j0 = a.kmax
    jb = int(np.argmax(sc))
    # null: same sweep, same n, but times shifted by a random musical amount
    nl = []
    for _ in range(12):
        s2, n2, _ = sweep(tracks[ti], rng.uniform(2.0, 30.0))
        if s2 is not None and n2 >= 8:
            nl.append(s2.max())
    nm = float(np.mean(nl)) if len(nl) >= 3 else float("nan")
    name = mid['tracks'][ti]['name'] or f'trk{ti}'
    rows.append((ti, name, n, sc[j0], ks[jb], sc[jb], nm))
    print(f'      {ti:2d} {name[:22]:22s} n={n:3d}  {sc[j0]:.3f}   '
          f'{ks[jb]:+3d}   {sc[jb]:.3f}      {nm:.3f}')

rows = [r for r in rows if r[6] == r[6]]        # drop parts with no usable null
tot_n = sum(r[2] for r in rows)
w0 = sum(r[3] * r[2] for r in rows) / tot_n
wb = sum(r[5] * r[2] for r in rows) / tot_n
wn = sum(r[6] * r[2] for r in rows) / tot_n
print(f'\n   3. note-weighted: shift-0 {w0:.3f}   best-per-part {wb:.3f}   '
      f'null(best-per-part on shuffled time) {wn:.3f}   flat {occ:.3f}')
print(f'      => the per-part freedom buys {wb-w0:+.3f}; the null buys {wn-occ:+.3f}. '
      f'Excess over null: {wb-wn:+.3f}')
