#!/usr/bin/env python3
"""Why does the detector miss 1/3 of the notes in a PERFECT render?"""
import numpy as np
import audio
from midiparse import read_smf
from render_sine import note_events, render
from calib import match

SR = 48000
PMIN, PMAX = 24, 108
BPM = 120.0
mid = read_smf('demo_preset_18.mid')
ev = note_events(mid)
y = render(ev, BPM)
x = y[:int(15 * SR)]
spb = 60.0 / BPM

full = [(sb * spb, p, v, ti, eb * spb) for sb, eb, p, v, ti in ev
        if PMIN <= p <= PMAX and sb * spb < 15.0]
truth = [(t, p) for t, p, v, ti, e in full]

mag, pitches, times, _ = audio.semitone_spectrogram(
    x, pmin=PMIN, pmax=PMAX, hop=256, periods=20., wmin=2048, wmax=8192)
lat = audio.band_latency(PMIN, PMAX, periods=20., wmin=2048, wmax=8192)
on = audio.detect_onsets(mag, pitches, times, lat, rel_thresh=0.20,
                         floor_db=-46., min_gap_s=0.03, hop=256)
hits, miss, used = match(truth, on, 0.040, 1)
hitset = set((round(h[0], 6), h[1]) for h in hits)
print(f'recall {len(hits)}/{len(truth)}')

# 1) is the note masked by another note at the SAME pitch already sounding?
by_pitch = {}
for t, p, v, ti, e in full:
    by_pitch.setdefault(p, []).append((t, e, v))
for p in by_pitch:
    by_pitch[p].sort()

cats = {}
for t, p, v, ti, e in full:
    h = (round(t, 6), p) in hitset
    overlap = any(t0 < t - 0.005 and e0 > t + 0.005 for t0, e0, v0 in by_pitch[p])
    # loudest simultaneous note anywhere
    sim = [v0 for t0, p0, v0, ti0, e0 in full if t0 <= t < e0]
    loud = max(sim) if sim else v
    key = ('samepitch-overlap' if overlap else
           'quiet(v<%d)' % 40 if v < 40 else
           'masked(v<0.4*max)' if v < 0.4 * loud else 'clean')
    d = cats.setdefault(key, [0, 0])
    d[0] += 1
    d[1] += int(h)
for k, (n, h) in sorted(cats.items()):
    print(f'  {k:22s} n={n:4d} recall={h/n:.3f}')

# recall vs velocity
print('recall vs velocity')
vs = np.array([v for t, p, v, ti, e in full])
hs = np.array([(round(t, 6), p) in hitset for t, p, v, ti, e in full])
for lo, hi in ((0, 30), (30, 50), (50, 70), (70, 90), (90, 128)):
    m = (vs >= lo) & (vs < hi)
    if m.sum():
        print(f'  vel {lo:3d}-{hi:3d}: n={m.sum():4d} recall={hs[m].mean():.3f}')
print('recall vs pitch')
ps = np.array([p for t, p, v, ti, e in full])
for lo, hi in ((24, 48), (48, 60), (60, 72), (72, 84), (84, 109)):
    m = (ps >= lo) & (ps < hi)
    if m.sum():
        print(f'  pitch {lo:3d}-{hi:3d}: n={m.sum():4d} recall={hs[m].mean():.3f}')
print('note density: %.1f onsets/s' % (len(full) / 15.0))
