#!/usr/bin/env python3
"""The oracle: align the demo-song MIDI to an emulator capture and score it.

Method
------
The capture is turned into a per-semitone onset-strength surface R[pitch, frame]
(see analyse_capture.rise).  For a candidate tempo the MIDI becomes a sparse
impulse surface M[pitch, frame]; the score for every possible time offset is then
the cross-correlation  sum_p (M[p] * R[p])  evaluated at every lag, which one FFT
per tempo computes in full.  So the (tempo, offset) surface is exact and
exhaustively searched, not sampled.

A global semitone shift k is applied by rolling R's pitch axis, so the search is
over (tempo, offset, semitone-shift).

Nulls
-----
  * PITCH null   -- keep the MIDI onset TIMES, permute the pitches.
  * TIME null    -- keep the pitches, replace the times with a uniform random
                    draw over the same span (same count, same density).
  * OFFSET null  -- the score at offsets far from the peak (the whole surface).
Each null is run with the identical machinery so the numbers are commensurable.
"""
import argparse
import numpy as np

from analyse_capture import rise
from midiparse import read_smf

SR, HOP = 48000, 256
DT = HOP / SR


def load_spec(npz, floor_db=-46.0):
    d = np.load(npz)
    mag, pitches, times = d['mag'], d['pitches'], d['times']
    R = rise(mag, floor_db=floor_db)
    return mag, pitches, times, R


def dilate(R, w):
    """Sliding max over +-w frames along the time axis."""
    out = R.copy()
    for s in range(1, w + 1):
        out[:, s:] = np.maximum(out[:, s:], R[:, :-s])
        out[:, :-s] = np.maximum(out[:, :-s], R[:, s:])
    return out


def midi_notes(path, exclude=(), pmin=24, pmax=108):
    mid = read_smf(path)
    div = mid['division']
    out = []
    for t in mid['tracks']:
        if t['index'] in exclude:
            continue
        for st, en, p, v, ti, ch in t['notes']:
            if pmin <= p <= pmax:
                out.append((st / div, p, v, ti))
    out.sort()
    return out, mid


def corr_surface(notes, Rd, pitches, t_lo, t_hi, bpms, shift=0, weight=None):
    """Return score[bpm, offset_frame] and the offset axis in seconds.

    score[b, j] = sum_i Rd[p_i + shift, j + round(beat_i*60/bpm/DT)]
    """
    P, T = Rd.shape
    pmin = int(pitches[0])
    beats = np.array([n[0] for n in notes])
    pidx = np.array([n[1] - pmin for n in notes])
    w = np.ones(len(notes)) if weight is None else np.asarray(weight, float)
    # pitch shift: a MIDI note p is looked up in band p+shift
    pidx = pidx + shift
    ok = (pidx >= 0) & (pidx < P)
    beats, pidx, w = beats[ok], pidx[ok].astype(int), w[ok]

    NFFT = 1 << int(np.ceil(np.log2(2 * T)))
    Rhat = np.fft.rfft(Rd, NFFT, axis=1)
    nlag = T
    scores = np.zeros((len(bpms), nlag), dtype=np.float32)
    M = np.zeros((P, NFFT))
    for bi, bpm in enumerate(bpms):
        M[:] = 0.0
        fr = np.round(beats * (60.0 / bpm) / DT).astype(int)
        keep = (fr >= 0) & (fr < T)
        np.add.at(M, (pidx[keep], fr[keep]), w[keep])
        Mhat = np.fft.rfft(M, NFFT, axis=1)
        c = np.fft.irfft(np.sum(np.conj(Mhat) * Rhat, axis=0), NFFT)
        scores[bi] = c[:nlag]
    offsets = t_lo + np.arange(nlag) * DT
    return scores, offsets


def hard_count(notes, Rd, pitches, t_lo, t0, bpm, shift, thr):
    """Per-note hit/miss at one alignment.  Returns (hits, inwin, values)."""
    pmin = int(pitches[0])
    P, T = Rd.shape
    n = len(notes)
    hits = np.zeros(n, bool)
    inwin = np.zeros(n, bool)
    vals = np.zeros(n)
    for i, (b, p, v, ti) in enumerate(notes):
        fr = int(round((t0 + b * 60.0 / bpm - t_lo) / DT))
        pi = p - pmin + shift
        if fr < 0 or fr >= T:
            continue
        inwin[i] = True
        if pi < 0 or pi >= P:
            continue
        vals[i] = Rd[pi, fr]
        hits[i] = Rd[pi, fr] >= thr
    return hits, inwin, vals
