#!/usr/bin/env python3
"""Listening deliverables: a full-song sine render at the measured tempo, and a
stereo A/B whose LEFT channel is that render and whose RIGHT channel is the
emulator capture, both on the emulator's own clock.

  make_ab.py --bpm 90.0 --t0 17.4 --cap long_sine.wav --lo 18 --hi 132.5
"""
import argparse
import numpy as np
import wave

import audio
import render_sine as rs
from midiparse import read_smf

ap = argparse.ArgumentParser()
ap.add_argument('--bpm', type=float, required=True)
ap.add_argument('--t0', type=float, required=True, help='time of MIDI beat 0 in the capture')
ap.add_argument('--cap', default='long_sine.wav')
ap.add_argument('--lo', type=float, default=18.0)
ap.add_argument('--hi', type=float, default=132.5)
ap.add_argument('--render-out', default=None)
ap.add_argument('--ab-out', default='ab_long_L_render_R_emulator.wav')
a = ap.parse_args()

SR = 48000
mid = read_smf('demo_preset_18.mid')
ev = rs.note_events(mid)
y = rs.render(ev, a.bpm)
if a.render_out:
    rs.write_wav(a.render_out, y)
    print(f'{len(ev)} notes, {len(y)/SR:.1f} s @ {a.bpm} bpm -> {a.render_out}')

# place the render on the capture's clock
lead = int(round(a.t0 * SR))
ren = np.concatenate([np.zeros(max(0, lead)), y]) if lead >= 0 else y[-lead:]

cap, _ = audio.load_wav(a.cap)
n0, n1 = int(a.lo * SR), int(a.hi * SR)
L = ren[n0:n1] if len(ren) > n0 else np.zeros(0)
R = cap[n0:n1]
n = max(len(L), len(R))
L = np.pad(L, (0, n - len(L)))
R = np.pad(R, (0, n - len(R)))
# equalise loudness so neither side masks the other
for v in (L, R):
    pk = np.abs(v).max()
    if pk > 0:
        v *= 0.9 / pk
st = np.stack([L, R], axis=1).ravel()
d = np.clip(np.round(st * 32767), -32768, 32767).astype('<i2')
w = wave.open(a.ab_out, 'wb')
w.setnchannels(2)
w.setsampwidth(2)
w.setframerate(SR)
w.writeframes(d.tobytes())
w.close()
print(f'A/B {a.lo}..{a.hi}s  LEFT=render@{a.bpm}bpm  RIGHT={a.cap} -> {a.ab_out}')
