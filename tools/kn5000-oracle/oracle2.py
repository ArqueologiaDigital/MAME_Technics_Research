#!/usr/bin/env python3
"""Oracle v2 -- sparse detected-onset surface, joint (tempo, offset, semitone)
search, hard matched-fraction score, three nulls, and a full mismatch breakdown.

  oracle2.py --spec spec_sine.npz --t-lo 24 --t-hi 37.2 --t0-max 27.4 --tag sine
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
ap.add_argument('--t0-max', type=float, required=True)
ap.add_argument('--exclude', default='')
ap.add_argument('--tol-ms', type=float, default=40.0)
ap.add_argument('--bpm-lo', type=float, default=50.0)
ap.add_argument('--bpm-hi', type=float, default=220.0)
ap.add_argument('--bpm-step', type=float, default=0.25)
ap.add_argument('--shifts', default='-24,-19,-17,-12,-7,-5,-3,-1,0,1,3,5,7,12,17,19,24')
ap.add_argument('--min-notes', type=int, default=100)
ap.add_argument('--nulls', type=int, default=4)
ap.add_argument('--seed', type=int, default=12345)
ap.add_argument('--tag', default='out')
ap.add_argument('--from-render', default=None,
                help='score a rendered WAV instead (self-test)')
a = ap.parse_args()

rng = np.random.default_rng(a.seed)
exc = tuple(int(x) for x in a.exclude.split(',') if x.strip())
shifts = [int(s) for s in a.shifts.split(',')]

B, pitches, times, onlist = surface.onset_surface(a.spec, a.t_lo, a.t_hi)
t_lo, t_hi = float(times[0]), float(times[-1])
w = int(round(a.tol_ms / 1000.0 / DT))
Bd = oracle.dilate(B, w)
occ = float(Bd.mean())
print(f'== {a.tag}: {a.spec}  window {t_lo:.2f}-{t_hi:.2f}s '
      f'({B.shape[0]} bands x {B.shape[1]} frames)')
print(f'   detected onsets: {int(B.sum())} ({B.sum()/(t_hi-t_lo):.1f}/s)  '
      f'occupancy after +-{a.tol_ms:.0f} ms dilation = {occ*100:.2f}%  '
      f'<-- CHANCE-HIT RATE')

notes, mid = oracle.midi_notes(a.midi, exc)
print(f'   MIDI: {len(notes)} notes (excluded tracks {exc})')

bpms = np.arange(a.bpm_lo, a.bpm_hi + 1e-9, a.bpm_step)
ONE = np.ones_like(Bd)
Cbase = None


def search(nts, shift):
    global Cbase
    S, offs = oracle.corr_surface(nts, Bd, pitches, t_lo, t_hi, bpms, shift)
    C, _ = oracle.corr_surface(nts, ONE, pitches, t_lo, t_hi, bpms, shift)
    frac = np.where(C >= a.min_notes, S / np.maximum(C, 1), np.nan)
    frac[:, offs > a.t0_max] = np.nan
    return frac, offs, C


res = {}
for sh in shifts:
    frac, offs, C = search(notes, sh)
    if np.all(np.isnan(frac)):
        continue
    bi, oi = np.unravel_index(np.nanargmax(frac), frac.shape)
    res[sh] = dict(score=float(frac[bi, oi]), bpm=float(bpms[bi]), t0=float(offs[oi]),
                   n=int(C[bi, oi]), frac=frac, offs=offs)
    print(f'   shift {sh:+3d}: {frac[bi,oi]:.3f}  @ {bpms[bi]:7.2f} bpm  '
          f't0={offs[oi]:7.3f}s  n={int(C[bi,oi])}')

best_sh = max(res, key=lambda s: res[s]['score'])
r = res[best_sh]
print(f'\n   >>> BEST: shift {best_sh:+d} semitones, {r["bpm"]:.2f} bpm, '
      f't0={r["t0"]:.3f}s, matched {r["score"]:.3f} of {r["n"]} notes')

frac, offs = r['frac'], r['offs']
flat = frac[~np.isnan(frac)]
print(f'   admissible surface: mean={flat.mean():.3f} sd={flat.std():.3f} '
      f'p99={np.percentile(flat,99):.3f}  z={(r["score"]-flat.mean())/flat.std():.1f}')

prof = np.nanmax(frac, axis=1)
bi = int(np.nanargmax(prof))
base = np.nanmean(prof)
half = prof[bi] - 0.5 * (prof[bi] - base)
lo, hi = bi, bi
while lo > 0 and prof[lo] > half:
    lo -= 1
while hi < len(prof) - 1 and prof[hi] > half:
    hi += 1
print(f'   tempo profile: peak {prof[bi]:.3f} @ {bpms[bi]:.2f} bpm, floor {base:.3f}, '
      f'half-height {bpms[lo]:.2f}..{bpms[hi]:.2f} bpm (width {bpms[hi]-bpms[lo]:.2f})')
shown = []
for i in np.argsort(-np.nan_to_num(prof)):
    if any(abs(bpms[i] - s) < 3.0 for s in shown):
        continue
    shown.append(bpms[i])
    print(f'      {bpms[i]:7.2f} bpm  {prof[i]:.3f}')
    if len(shown) >= 8:
        break

print('\n   NULLS:')
for label, gen in (
        ('pitch-permuted (same times)',
         lambda: [(notes[i][0], notes[p][1], notes[i][2], notes[i][3])
                  for i, p in enumerate(rng.permutation(len(notes)))]),
        ('time-randomised (same pitches)',
         lambda: sorted((float(rng.uniform(0, max(n[0] for n in notes))),
                         n[1], n[2], n[3]) for n in notes)),
        ('time-shifted by a random beat offset',
         lambda: sorted((n[0] + float(rng.uniform(4, 60)), n[1], n[2], n[3])
                        for n in notes))):
    acc = []
    for _ in range(a.nulls):
        f2, _, _ = search(gen(), best_sh)
        acc.append(float(np.nanmax(f2)))
    print(f'     {label:36s} {np.mean(acc):.3f} +- {np.std(acc):.3f} (max {max(acc):.3f})')
print(f'     {"flat occupancy (pure chance)":36s} {occ:.3f}')

# ---------------- mismatch breakdown at the winning alignment ----------------
print('\n   MISMATCH BREAKDOWN at the best alignment')
hits, inwin, vals = oracle.hard_count(notes, Bd, pitches, t_lo, r['t0'], r['bpm'],
                                      best_sh, 0.5)
idx = np.where(inwin)[0]
print(f'     notes inside the window: {len(idx)}')
pm = int(pitches[0])
P, T = Bd.shape
cat = {'hit': 0, 'wrong-octave': 0, 'wrong-semitone(+-1..2)': 0,
       'right-pitch-wrong-time': 0, 'missing (no onset anywhere near)': 0}
octs, semis = [], []
BdAny = Bd.max(axis=0)                    # any onset at all at this time
Wide = oracle.dilate(B, int(round(0.250 / DT)))   # +-250 ms
for i in idx:
    b, p, v, ti = notes[i]
    fr = int(round((r['t0'] + b * 60.0 / r['bpm'] - t_lo) / DT))
    pi = p - pm + best_sh
    if hits[i]:
        cat['hit'] += 1
        continue
    found = None
    for k in (-24, -12, 12, 24):
        q = pi + k
        if 0 <= q < P and Bd[q, fr] > 0.5:
            found = k
            break
    if found is not None:
        cat['wrong-octave'] += 1
        octs.append(found)
        continue
    found = None
    for k in (-2, -1, 1, 2):
        q = pi + k
        if 0 <= q < P and Bd[q, fr] > 0.5:
            found = k
            break
    if found is not None:
        cat['wrong-semitone(+-1..2)'] += 1
        semis.append(found)
        continue
    if 0 <= pi < P and Wide[pi, fr] > 0.5:
        cat['right-pitch-wrong-time'] += 1
        continue
    cat['missing (no onset anywhere near)'] += 1
tot = max(1, len(idx))
for k, n in cat.items():
    print(f'     {k:36s} {n:5d}  {100*n/tot:5.1f}%')
if octs:
    print('     octave-error directions:', {k: octs.count(k) for k in set(octs)})
if semis:
    print('     semitone-error directions:', {k: semis.count(k) for k in set(semis)})

# global semitone-offset histogram: for every in-window MIDI note, which band(s)
# near the predicted time actually fired?
print('\n   SEMITONE-OFFSET HISTOGRAM (over all in-window notes, all bands)')
hist = np.zeros(2 * 40 + 1)
for i in idx:
    b, p, v, ti = notes[i]
    fr = int(round((r['t0'] + b * 60.0 / r['bpm'] - t_lo) / DT))
    pi = p - pm
    for k in range(-40, 41):
        q = pi + k
        if 0 <= q < P and Bd[q, fr] > 0.5:
            hist[k + 40] += 1
tot_k = hist.sum()
for k in range(-40, 41):
    if hist[k + 40] > 0 and abs(k) <= 26:
        bar = '#' * int(60 * hist[k + 40] / max(1, hist.max()))
        print(f'     {k:+3d} {int(hist[k+40]):5d} {100*hist[k+40]/tot_k:5.1f}% {bar}')

np.savez_compressed(f'oracle2_{a.tag}.npz', frac=frac, bpms=bpms, offs=offs,
                    hist=hist, best=np.array([best_sh, r['bpm'], r['t0'],
                                              r['score'], r['n'], occ]))
print(f'\n   saved oracle2_{a.tag}.npz')
