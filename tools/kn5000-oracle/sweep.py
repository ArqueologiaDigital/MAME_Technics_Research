#!/usr/bin/env python3
"""Parameter sweep for the onset detector, scored on our own render."""
import itertools
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
truth = [(sb * spb, p) for sb, eb, p, v, ti in ev if PMIN <= p <= PMAX and sb * spb < 15.0]
print('truth', len(truth))

cache = {}
for periods, wmin, wmax in ((20., 2048, 8192), (12., 1024, 4096), (30., 3072, 12288)):
    key = (periods, wmin, wmax)
    mag, pitches, times, _ = audio.semitone_spectrogram(
        x, pmin=PMIN, pmax=PMAX, hop=256, periods=periods, wmin=wmin, wmax=wmax)
    lat = audio.band_latency(PMIN, PMAX, periods=periods, wmin=wmin, wmax=wmax)
    cache[key] = (mag, pitches, times, lat)
    for rt, fdb, gap in itertools.product((0.20, 0.35, 0.55), (-70., -58., -46.), (0.03, 0.06)):
        on = audio.detect_onsets(mag, pitches, times, lat, rel_thresh=rt,
                                 floor_db=fdb, min_gap_s=gap, hop=256)
        hits, miss, used = match(truth, on, 0.040, 1)
        print(f'per={periods:4.0f} w={wmin}-{wmax} rt={rt:.2f} floor={fdb:.0f} gap={gap:.2f}: '
              f'ndet={len(on):5d} recall={len(hits)/len(truth):.3f} prec={used.sum()/max(1,len(on)):.3f}')
