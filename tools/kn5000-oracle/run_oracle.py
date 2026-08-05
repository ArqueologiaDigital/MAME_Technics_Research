#!/usr/bin/env python3
"""The oracle proper: binary onset surface, exhaustive (tempo, offset, semitone)
search, hard matched-fraction score, and three independent nulls.

  run_oracle.py --spec spec_sine.npz --t-lo 24.0 --t-hi 37.2 --t0-max 27.4
"""
import argparse
import numpy as np

import oracle
from oracle import DT

ap = argparse.ArgumentParser()
ap.add_argument('--spec', required=True)
ap.add_argument('--midi', default='demo_preset_18.mid')
ap.add_argument('--t-lo', type=float, required=True)
ap.add_argument('--t-hi', type=float, required=True)
ap.add_argument('--t0-max', type=float, required=True,
                help='latest the song can have started (first audible sample)')
ap.add_argument('--exclude', default='')
ap.add_argument('--thr', type=float, default=0.20)
ap.add_argument('--tol-ms', type=float, default=40.0)
ap.add_argument('--bpm-lo', type=float, default=40.0)
ap.add_argument('--bpm-hi', type=float, default=300.0)
ap.add_argument('--bpm-step', type=float, default=0.25)
ap.add_argument('--shifts', default='0')
ap.add_argument('--min-notes', type=int, default=100)
ap.add_argument('--seed', type=int, default=12345)
ap.add_argument('--tag', default='')
a = ap.parse_args()

rng = np.random.default_rng(a.seed)
exc = tuple(int(x) for x in a.exclude.split(',') if x.strip())
shifts = [int(s) for s in a.shifts.split(',')]

mag, pitches, times, R = oracle.load_spec(a.spec)
sel = (times >= a.t_lo) & (times <= a.t_hi)
R, times = R[:, sel], times[sel]
t_lo, t_hi = float(times[0]), float(times[-1])
B = (R >= a.thr).astype(np.float32)
w = int(round(a.tol_ms / 1000.0 / DT))
Bd = oracle.dilate(B, w)
occ = float(Bd.mean())
print(f'== {a.spec} {a.tag}')
print(f'   window {t_lo:.2f}-{t_hi:.2f}s  {B.shape[0]} bands x {B.shape[1]} frames')
print(f'   raw onset cells {B.sum():.0f} ({B.mean()*100:.2f}%), after +-{a.tol_ms:.0f} ms '
      f'dilation OCCUPANCY = {occ*100:.2f}%  <-- the chance-hit rate')

notes, mid = oracle.midi_notes(a.midi, exc)
print(f'   MIDI {len(notes)} notes, tracks excluded {exc}')

bpms = np.arange(a.bpm_lo, a.bpm_hi + 1e-9, a.bpm_step)
ONE = np.ones_like(Bd)


def search(nts, shift):
    S, offs = oracle.corr_surface(nts, Bd, pitches, t_lo, t_hi, bpms, shift)
    C, _ = oracle.corr_surface(nts, ONE, pitches, t_lo, t_hi, bpms, shift)
    frac = np.where(C >= a.min_notes, S / np.maximum(C, 1), np.nan)
    ok = offs <= a.t0_max
    frac[:, ~ok] = np.nan
    return frac, offs, C


results = {}
for sh in shifts:
    frac, offs, C = search(notes, sh)
    if np.all(np.isnan(frac)):
        print(f'   shift {sh:+d}: no admissible alignment')
        continue
    bi, oi = np.unravel_index(np.nanargmax(frac), frac.shape)
    results[sh] = (frac[bi, oi], bpms[bi], offs[oi], int(C[bi, oi]), frac, offs)
    print(f'   shift {sh:+3d} semitones: best {frac[bi,oi]:.3f} at '
          f'{bpms[bi]:7.2f} bpm, t0={offs[oi]:.3f}s, n={int(C[bi,oi])}')

best_sh = max(results, key=lambda s: results[s][0])
score, bpm, t0, nin, frac, offs = results[best_sh]
print(f'\n   >>> BEST: shift {best_sh:+d}, {bpm:.2f} bpm, t0={t0:.3f}s, '
      f'matched {score:.3f} of {nin} notes')

flat = frac[~np.isnan(frac)]
print(f'   admissible-surface background: mean={flat.mean():.3f} sd={flat.std():.3f} '
      f'p99={np.percentile(flat,99):.3f}  z(peak)={(score-flat.mean())/flat.std():.1f}')

# ---- tempo sharpness -------------------------------------------------------
prof = np.nanmax(frac, axis=1)
bi = int(np.nanargmax(prof))
base = np.nanmean(prof)
half = prof[bi] - 0.5 * (prof[bi] - base)
lo = bi
while lo > 0 and prof[lo] > half:
    lo -= 1
hi = bi
while hi < len(prof) - 1 and prof[hi] > half:
    hi += 1
print(f'   tempo profile: peak {prof[bi]:.3f} at {bpms[bi]:.2f} bpm, floor {base:.3f}, '
      f'half-height width {bpms[lo]:.2f}..{bpms[hi]:.2f} bpm ({bpms[hi]-bpms[lo]:.2f} bpm)')
top = np.argsort(-np.nan_to_num(prof))
shown = []
for i in top:
    if any(abs(bpms[i] - s) < 3.0 for s in shown):
        continue
    shown.append(bpms[i])
    print(f'      {bpms[i]:7.2f} bpm  score={prof[i]:.3f}')
    if len(shown) >= 8:
        break

# ---- NULLS -----------------------------------------------------------------
print('\n   NULLS (identical machinery):')
# 1. pitch-permuted MIDI (same times)
accs = []
for _ in range(5):
    perm = rng.permutation(len(notes))
    nn = [(notes[i][0], notes[perm[i]][1], notes[i][2], notes[i][3]) for i in range(len(notes))]
    f2, o2, C2 = search(nn, best_sh)
    accs.append(np.nanmax(f2))
print(f'     pitch-permuted MIDI : best {np.mean(accs):.3f} +- {np.std(accs):.3f} '
      f'(max over 5 draws {max(accs):.3f})')
# 2. random times, real pitches
accs2 = []
span = max(n[0] for n in notes)
for _ in range(5):
    nn = [(float(rng.uniform(0, span)), notes[i][1], notes[i][2], notes[i][3])
          for i in range(len(notes))]
    nn.sort()
    f3, o3, C3 = search(nn, best_sh)
    accs2.append(np.nanmax(f3))
print(f'     time-randomised MIDI: best {np.mean(accs2):.3f} +- {np.std(accs2):.3f} '
      f'(max over 5 draws {max(accs2):.3f})')
# 3. flat occupancy
print(f'     surface occupancy   : {occ:.3f}   (probability a note at a random '
      f'(pitch,time) lands on an onset cell)')

np.savez_compressed(f'oracle_{a.tag or "out"}.npz', frac=frac, bpms=bpms, offs=offs,
                    best=np.array([best_sh, bpm, t0, score, nin]))
print(f'\n   saved oracle_{a.tag or "out"}.npz')
