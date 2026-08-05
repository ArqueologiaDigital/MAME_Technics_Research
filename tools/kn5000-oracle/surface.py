#!/usr/bin/env python3
"""Build a sparse binary ONSET surface from a cached spectrogram.

Unlike a plain threshold on the rise function, this uses the full onset
detector -- peak-picking in time plus the +-1 semitone DOMINANCE test -- so a
single loud event no longer lights up a whole column of bands.  That is what
makes the pitch axis informative.
"""
import numpy as np
import audio

HOP = 256
PERIODS, WMIN, WMAX = 20., 2048, 8192


def onset_surface(npz, t_lo, t_hi, rel_thresh=0.20, floor_db=-46.0,
                  min_gap_s=0.03, dominance=True):
    d = np.load(npz)
    mag, pitches, times = d['mag'], d['pitches'], d['times']
    sel = (times >= t_lo) & (times <= t_hi)
    mag, times = mag[:, sel], times[sel]
    lat = audio.band_latency(int(pitches[0]), int(pitches[-1]),
                             periods=PERIODS, wmin=WMIN, wmax=WMAX)
    on = audio.detect_onsets(mag, pitches, times, lat, rel_thresh=rel_thresh,
                             floor_db=floor_db, min_gap_s=min_gap_s, hop=HOP,
                             dominance=dominance)
    P, T = mag.shape
    B = np.zeros((P, T), dtype=np.float32)
    pmin = int(pitches[0])
    t0 = float(times[0])
    dt = HOP / 48000.0
    for tt, p, s in on:
        j = int(round((tt - t0) / dt))
        i = p - pmin
        if 0 <= j < T and 0 <= i < P:
            B[i, j] = 1.0
    return B, pitches, times, on
