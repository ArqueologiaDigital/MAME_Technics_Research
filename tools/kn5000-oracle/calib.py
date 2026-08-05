#!/usr/bin/env python3
"""Calibrate the onset detector on our OWN render, where the truth is known.

This is the load-bearing step: it tells us the detector's ceiling.  Any score
against the emulator has to be read against THIS number, not against 100%.
"""
import sys
import numpy as np

import audio
from midiparse import read_smf
from render_sine import note_events, render, write_wav

SR = 48000


def analyse(x, pmin, pmax, hop=256, periods=20.0, wmin=2048, wmax=8192,
            rel_thresh=0.55, floor_db=-58.0, min_gap_s=0.06):
    mag, pitches, times, _ = audio.semitone_spectrogram(
        x, pmin=pmin, pmax=pmax, hop=hop, periods=periods, wmin=wmin, wmax=wmax)
    lat = audio.band_latency(pmin, pmax, periods=periods, wmin=wmin, wmax=wmax)
    on = audio.detect_onsets(mag, pitches, times, lat, rel_thresh=rel_thresh,
                             floor_db=floor_db, min_gap_s=min_gap_s, hop=hop)
    return on, mag, pitches, times, lat


def match(truth, det, tol, pitch_tol=0):
    """Greedy one-to-one match of truth onsets to detected onsets."""
    det = sorted(det)
    dt = np.array([d[0] for d in det])
    dp = np.array([d[1] for d in det])
    used = np.zeros(len(det), bool)
    hits, miss = [], []
    for (tt, pp) in truth:
        lo = np.searchsorted(dt, tt - tol)
        hi = np.searchsorted(dt, tt + tol)
        best, bestd = -1, 1e9
        for j in range(lo, hi):
            if used[j] or abs(int(dp[j]) - pp) > pitch_tol:
                continue
            e = abs(dt[j] - tt)
            if e < bestd:
                bestd, best = e, j
        if best >= 0:
            used[best] = True
            hits.append((tt, pp, dt[best] - tt))
        else:
            miss.append((tt, pp))
    return hits, miss, used


if __name__ == '__main__':
    bpm = float(sys.argv[1]) if len(sys.argv) > 1 else 120.0
    mid = read_smf('demo_preset_18.mid')
    ev = note_events(mid)
    y = render(ev, bpm)
    write_wav('render_calib.wav', y)
    print(f'rendered {len(ev)} notes at {bpm} bpm, {len(y)/SR:.1f}s')

    # analyse only the first 15 s -- same span we will use against the emulator
    span = int(15 * SR)
    x = y[:span]
    PMIN, PMAX = 24, 108
    on, mag, pitches, times, lat = analyse(x, PMIN, PMAX)
    print('detected onsets in 0-15 s:', len(on))

    spb = 60.0 / bpm
    truth = [(sb * spb, p) for sb, eb, p, v, ti in ev
             if PMIN <= p <= PMAX and sb * spb < 15.0]
    print('truth onsets in 0-15 s:', len(truth))

    for tol in (0.020, 0.040, 0.060, 0.100):
        for ptol in (0, 1):
            hits, miss, used = match(truth, on, tol, ptol)
            errs = np.array([h[2] for h in hits]) if hits else np.array([0.0])
            print(f'  tol={tol*1000:4.0f} ms ptol={ptol}: recall '
                  f'{len(hits)}/{len(truth)} = {len(hits)/len(truth):.3f}  '
                  f'precision {used.sum()}/{len(on)} = {used.sum()/max(1,len(on)):.3f}  '
                  f'dt mean {errs.mean()*1000:+.1f} ms  sd {errs.std()*1000:.1f} ms')
