#!/usr/bin/env python3
"""Staged (tempo, offset, semitone) search for a LONG capture.

oracle2.py searches every (bpm, shift) pair, which costs ~25 min on a 200 s
window.  The same answer comes out of three cheap stages:

  1. coarse tempo sweep at shift 0 over the whole bpm range  (one pass)
  2. fine tempo sweep around the winner                      (one narrow pass)
  3. semitone sweep at the fine tempo band only              (17 narrow passes)

The note-count normaliser is computed analytically (searchsorted) instead of by
a second correlation against a surface of ones, which halves the FFT work and is
exact.

  long_search.py --spec spec_sine_long.npz --t-lo 18 --t-hi 220 --t0-max 30 --tag sineL
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
ap.add_argument('--t0-min', type=float, default=-1e9)
ap.add_argument('--exclude', default='')
ap.add_argument('--tol-ms', type=float, default=40.0)
ap.add_argument('--bpm-lo', type=float, default=50.0)
ap.add_argument('--bpm-hi', type=float, default=220.0)
ap.add_argument('--bpm-step', type=float, default=0.25)
ap.add_argument('--fine-step', type=float, default=0.02)
ap.add_argument('--fine-half', type=float, default=1.0)
ap.add_argument('--shifts', default='-24,-19,-17,-12,-7,-5,-3,-1,0,1,3,5,7,12,17,19,24')
ap.add_argument('--min-frac', type=float, default=0.60,
                help='require this fraction of all notes to be inside the window')
ap.add_argument('--tag', default='out')
a = ap.parse_args()

exc = tuple(int(x) for x in a.exclude.split(',') if x.strip())
shifts = [int(s) for s in a.shifts.split(',')]

B, pitches, times, onlist = surface.onset_surface(a.spec, a.t_lo, a.t_hi)
t_lo, t_hi = float(times[0]), float(times[-1])
w = int(round(a.tol_ms / 1000.0 / DT))
Bd = oracle.dilate(B, w)
occ = float(Bd.mean())
P, T = Bd.shape
print(f'== {a.tag}: {a.spec}  window {t_lo:.2f}-{t_hi:.2f}s ({P} bands x {T} frames)')
print(f'   detected onsets: {int(B.sum())} ({B.sum()/(t_hi-t_lo):.1f}/s)  '
      f'occupancy after +-{a.tol_ms:.0f} ms dilation = {occ*100:.2f}%  <-- CHANCE')

notes, mid = oracle.midi_notes(a.midi, exc)
# ⚠ REACHABILITY. corr_surface only evaluates lags >= 0, so the recovered offset
# is the time of MIDI beat 0 and can never be earlier than the window start.  The
# song's first note is ~2.8 beats in, so with a window starting at 18 s a true
# beat-0 time of ~17.4 s would be UNREACHABLE and the search would silently lock
# onto a wrong tempo.  Re-origin the beats on the first note; the reported offset
# is then the time of THAT note, and beat 0 is recovered arithmetically.
SHIFT = min(n[0] for n in notes)
notes = [(n[0] - SHIFT, n[1], n[2], n[3]) for n in notes]
print(f'   MIDI: {len(notes)} notes (excluded tracks {exc}); '
      f'beats re-origined on the first note at beat {SHIFT:.4f}')
beats = np.array([n[0] for n in notes])
pidx0 = np.array([n[1] for n in notes]) - int(pitches[0])
NMIN = int(a.min_frac * len(notes))


def sweep(bpms, shift):
    """Return frac[bpm, offset], offsets, counts[bpm, offset].

    The count normaliser uses EXACTLY the note subset corr_surface keeps: a note
    whose band p+shift falls outside the analysed pitch range is dropped there,
    so it must not be counted here either.
    """
    S, offs = oracle.corr_surface(notes, Bd, pitches, t_lo, t_hi, bpms, shift)
    q = pidx0 + shift
    keepp = (q >= 0) & (q < P)
    bts = beats[keepp]
    cnt = np.zeros_like(S)
    for bi, bpm in enumerate(bpms):
        fr = np.sort(np.round(bts * (60.0 / bpm) / DT).astype(int))
        j = np.arange(T)
        lo = np.searchsorted(fr, -j, 'left')
        hi = np.searchsorted(fr, T - j, 'left')
        cnt[bi] = hi - lo
    frac = np.where(cnt >= NMIN, S / np.maximum(cnt, 1), np.nan)
    bad = (offs > a.t0_max) | (offs < a.t0_min)
    frac[:, bad] = np.nan
    return frac, offs, cnt


# ---- stage 1: coarse tempo -------------------------------------------------
bpms = np.arange(a.bpm_lo, a.bpm_hi + 1e-9, a.bpm_step)
frac, offs, cnt = sweep(bpms, 0)
prof = np.nanmax(frac, axis=1)
bi = int(np.nanargmax(prof))
base = float(np.nanmean(prof))
half = prof[bi] - 0.5 * (prof[bi] - base)
lo, hi = bi, bi
while lo > 0 and prof[lo] > half:
    lo -= 1
while hi < len(prof) - 1 and prof[hi] > half:
    hi += 1
print(f'\n   COARSE TEMPO (shift 0): peak {prof[bi]:.4f} @ {bpms[bi]:.2f} bpm, '
      f'floor {base:.4f}')
print(f'   half-height {bpms[lo]:.2f}..{bpms[hi]:.2f} bpm  WIDTH {bpms[hi]-bpms[lo]:.2f} bpm')
shown = []
for i in np.argsort(-np.nan_to_num(prof)):
    if any(abs(bpms[i] - s) < 2.0 for s in shown):
        continue
    shown.append(bpms[i])
    print(f'      {bpms[i]:7.2f} bpm  {prof[i]:.4f}')
    if len(shown) >= 8:
        break
np.savez_compressed(f'tempoprof_{a.tag}.npz', bpms=bpms, prof=prof)

# ---- stage 2: fine tempo ---------------------------------------------------
fb = np.arange(bpms[bi] - a.fine_half, bpms[bi] + a.fine_half + 1e-9, a.fine_step)
frac2, offs2, cnt2 = sweep(fb, 0)
p2 = np.nanmax(frac2, axis=1)
j2 = int(np.nanargmax(p2))
bpm_best = float(fb[j2])
oi = int(np.nanargmax(frac2[j2]))
t0_best = float(offs2[oi])
print(f'\n   FINE TEMPO: {bpm_best:.3f} bpm, t0={t0_best:.3f}s, '
      f'score {frac2[j2,oi]:.4f}, n={int(cnt2[j2,oi])}')
b2 = float(np.nanmean(p2))
h2 = p2[j2] - 0.5 * (p2[j2] - b2)
l3, h3 = j2, j2
while l3 > 0 and p2[l3] > h2:
    l3 -= 1
while h3 < len(p2) - 1 and p2[h3] > h2:
    h3 += 1
print(f'   fine half-height {fb[l3]:.2f}..{fb[h3]:.2f} bpm (width {fb[h3]-fb[l3]:.2f})')

# ---- stage 3: semitone shifts at the fine tempo band ------------------------
nb = np.arange(bpm_best - 0.5, bpm_best + 0.5 + 1e-9, 0.05)
print('\n   SEMITONE SWEEP (tempo free within +-0.5 bpm of the winner)')
res = {}
for sh in shifts:
    f3, o3, c3 = sweep(nb, sh)
    if np.all(np.isnan(f3)):
        continue
    k, m = np.unravel_index(np.nanargmax(f3), f3.shape)
    res[sh] = (float(f3[k, m]), float(nb[k]), float(o3[m]), int(c3[k, m]))
    print(f'   shift {sh:+3d}: {f3[k,m]:.4f}  @ {nb[k]:7.2f} bpm  t0={o3[m]:7.3f}s  '
          f'n={int(c3[k,m])}')
bs = max(res, key=lambda s: res[s][0])
print(f'\n   >>> BEST shift {bs:+d}: {res[bs][0]:.4f} @ {res[bs][1]:.2f} bpm '
      f't0(first note)={res[bs][2]:.3f}s')
t0_beat0 = t0_best - SHIFT * 60.0 / bpm_best
print(f'   >>> FIXED ALIGNMENT FOR SCORING: bpm={bpm_best:.3f}  '
      f't0(first note)={t0_best:.3f}  t0(MIDI beat 0)={t0_beat0:.3f}')
print(f'   >>> long_eval.py --bpm {bpm_best:.3f} --t0 {t0_beat0:.3f}')
