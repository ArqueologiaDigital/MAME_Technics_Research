#!/usr/bin/env python3
"""Stage 1: exhaustive (tempo, offset) search + nulls.

  run_search.py <spec.npz> <t_lo> <t_hi> [--exclude 10,16] [--shift 0]
"""
import argparse
import numpy as np

import oracle
from oracle import DT

ap = argparse.ArgumentParser()
ap.add_argument('spec')
ap.add_argument('t_lo', type=float)
ap.add_argument('t_hi', type=float)
ap.add_argument('--midi', default='demo_preset_18.mid')
ap.add_argument('--exclude', default='')
ap.add_argument('--shift', type=int, default=0)
ap.add_argument('--bpm-lo', type=float, default=40.0)
ap.add_argument('--bpm-hi', type=float, default=300.0)
ap.add_argument('--bpm-step', type=float, default=0.25)
ap.add_argument('--tol-ms', type=float, default=40.0)
ap.add_argument('--out', default=None)
a = ap.parse_args()

exc = tuple(int(x) for x in a.exclude.split(',') if x.strip())
mag, pitches, times, R = oracle.load_spec(a.spec)
sel = (times >= a.t_lo) & (times <= a.t_hi)
R = R[:, sel]
times = times[sel]
t_lo = float(times[0])
w = int(round(a.tol_ms / 1000.0 / DT))
Rd = oracle.dilate(R, w)
print(f'{a.spec}: {R.shape[0]} bands x {R.shape[1]} frames, window '
      f'{t_lo:.2f}-{times[-1]:.2f}s, dilation +-{w} frames ({w*DT*1000:.0f} ms)')

notes, mid = oracle.midi_notes(a.midi, exc)
print(f'MIDI: {len(notes)} notes (excluding tracks {exc}), span '
      f'{notes[0][0]:.1f}-{notes[-1][0]:.1f} beats')

bpms = np.arange(a.bpm_lo, a.bpm_hi + 1e-9, a.bpm_step)
S, offs = oracle.corr_surface(notes, Rd, pitches, t_lo, times[-1], bpms, a.shift)
# normalise: divide by the number of MIDI notes that actually land inside the
# window at that (bpm, offset), so a tempo that puts 3 notes in the window cannot win
cnt, _ = oracle.corr_surface(notes, np.ones_like(Rd), pitches, t_lo, times[-1],
                             bpms, a.shift)
Sn = np.where(cnt >= 40, S / np.maximum(cnt, 1), 0.0)

bi, oi = np.unravel_index(np.argmax(Sn), Sn.shape)
print(f'\nBEST  bpm={bpms[bi]:.2f}  t0={offs[oi]:.4f}s  mean-rise={Sn[bi,oi]:.4f} '
      f'({int(cnt[bi,oi])} notes in window)')
flat = Sn[Sn > 0]
print(f'surface: mean={flat.mean():.4f} sd={flat.std():.4f} '
      f'p99={np.percentile(flat,99):.4f} max={flat.max():.4f}  '
      f'z(peak)={(Sn[bi,oi]-flat.mean())/flat.std():.1f}')

# tempo profile: best offset for each tempo
prof = Sn.max(axis=1)
print('\ntop tempi (best offset each):')
order = np.argsort(-prof)
shown = []
for i in order:
    if any(abs(bpms[i] - s) < 2.0 for s in shown):
        continue
    shown.append(bpms[i])
    j = int(np.argmax(Sn[i]))
    print(f'   {bpms[i]:7.2f} bpm  t0={offs[j]:7.3f}s  score={prof[i]:.4f}')
    if len(shown) >= 10:
        break

# sharpness of the peak in tempo
half = prof[bi] - 0.5 * (prof[bi] - flat.mean())
lo = bi
while lo > 0 and prof[lo] > half:
    lo -= 1
hi = bi
while hi < len(prof) - 1 and prof[hi] > half:
    hi += 1
print(f'\ntempo peak half-height width: {bpms[lo]:.2f} .. {bpms[hi]:.2f} bpm '
      f'({bpms[hi]-bpms[lo]:.2f} bpm wide)')

if a.out:
    np.savez_compressed(a.out, S=Sn, bpms=bpms, offs=offs, cnt=cnt)
    print('saved', a.out)
