#!/usr/bin/env python3
"""Pure-sine renderer for a Standard MIDI File.  numpy only, no samples.

Envelope (stated exactly, as required):
    linear attack  5 ms  from 0 to 1
    flat sustain   for the rest of the notated duration
    linear release 40 ms from 1 to 0, appended AFTER the notated note-off
Amplitude = 0.20 * (velocity/127).  Sines are summed; the mix is scaled by a
single global constant so the peak sits at -1 dBFS (no limiting, no clipping,
so the sum stays exactly linear).

Usage: render_sine.py <in.mid> <out.wav> --bpm 120 [--exclude-tracks 10,16]
"""
import argparse
import numpy as np
import wave

from midiparse import read_smf

SR = 48000
ATTACK = 0.005
RELEASE = 0.040


def note_events(mid, exclude=(), pitch_lo=0, pitch_hi=127):
    """(start_beat, end_beat, pitch, velocity, track) in BEATS."""
    div = mid['division']
    ev = []
    for t in mid['tracks']:
        if t['index'] in exclude:
            continue
        for st, en, p, v, ti, ch in t['notes']:
            if not (pitch_lo <= p <= pitch_hi):
                continue
            ev.append((st / div, en / div, p, v, ti))
    ev.sort()
    return ev


def render(ev, bpm, sr=SR, gain=0.20):
    spb = 60.0 / bpm
    end = max(e[1] for e in ev) * spb + RELEASE + 0.5
    y = np.zeros(int(end * sr) + 1)
    for sb, eb, p, v, ti in ev:
        t0 = sb * spb
        dur = max(0.01, (eb - sb) * spb)
        n0 = int(round(t0 * sr))
        nn = int(round((dur + RELEASE) * sr))
        if nn <= 0:
            continue
        f = 440.0 * 2.0 ** ((p - 69.0) / 12.0)
        n = np.arange(nn)
        # start at a random-but-deterministic phase so simultaneous equal pitches
        # do not build an artificially huge peak
        ph = ((p * 2654435761 + int(t0 * 1e4) * 40503) % 65536) / 65536.0
        s = np.sin(2 * np.pi * f * n / sr + 2 * np.pi * ph)
        envp = np.ones(nn)
        na = min(nn, int(ATTACK * sr))
        if na > 1:
            envp[:na] = np.linspace(0, 1, na)
        nr = int(RELEASE * sr)
        if nr > 0:
            envp[-nr:] *= np.linspace(1, 0, nr)
        amp = gain * (v / 127.0)
        y[n0:n0 + nn] += amp * s * envp
    pk = np.abs(y).max()
    if pk > 0:
        y *= 10 ** (-1.0 / 20.0) / pk
    return y


def write_wav(path, y, sr=SR, stereo=False):
    d = np.clip(np.round(y * 32767), -32768, 32767).astype('<i2')
    w = wave.open(path, 'wb')
    w.setnchannels(2 if stereo else 1)
    w.setsampwidth(2)
    w.setframerate(sr)
    if stereo:
        d = np.repeat(d[:, None], 2, axis=1).ravel()
    w.writeframes(d.tobytes())
    w.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('midi')
    ap.add_argument('out')
    ap.add_argument('--bpm', type=float, default=120.0)
    ap.add_argument('--exclude-tracks', default='')
    ap.add_argument('--pitch-lo', type=int, default=0)
    ap.add_argument('--pitch-hi', type=int, default=127)
    ap.add_argument('--stereo', action='store_true')
    a = ap.parse_args()
    exc = tuple(int(x) for x in a.exclude_tracks.split(',') if x.strip())
    mid = read_smf(a.midi)
    ev = note_events(mid, exc, a.pitch_lo, a.pitch_hi)
    y = render(ev, a.bpm)
    write_wav(a.out, y, stereo=a.stereo)
    print(f'{len(ev)} notes, {len(y)/SR:.2f} s @ {a.bpm} bpm -> {a.out}')
