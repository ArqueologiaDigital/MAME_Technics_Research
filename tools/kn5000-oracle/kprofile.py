#!/usr/bin/env python3
"""The decisive pitch measurement: hit(k) MINUS its own pitch-permuted null.

A raw hit-rate-versus-semitone-shift curve is not interpretable on its own,
because the emulator's onsets are not spread evenly over the pitch axis: if its
output happens to sit higher than the score, shifting the score UP raises the
hit rate with no pitch information involved at all.

NULL-P removes exactly that.  It keeps every onset time and the whole pitch
histogram and only scrambles WHICH pitch goes with WHICH time, so nullP(k) is
the hit rate a pitch-blind emulator with the same register habits would score at
shift k.  The pitch information at shift k is hit(k) - nullP(k), and a correct
absolute pitch shows up as a SPIKE of that difference at k = 0.

  kprofile.py --spec spec_sineL.npz --t-lo 18 --t-hi 100 --bpm 90.02 --t0 17.425
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
ap.add_argument('--bpm', type=float, required=True)
ap.add_argument('--t0', type=float, required=True)
ap.add_argument('--tol-ms', type=float, default=40.0)
ap.add_argument('--kmax', type=int, default=24)
ap.add_argument('--draws', type=int, default=40)
ap.add_argument('--tag', default='out')
a = ap.parse_args()

DRUMS = {10, 16}
rng = np.random.default_rng(7)
B, pitches, times, _ = surface.onset_surface(a.spec, a.t_lo, a.t_hi)
t_lo = float(times[0])
Bd = oracle.dilate(B, int(round(a.tol_ms / 1000.0 / DT)))
P, T = Bd.shape
pm = int(pitches[0])
occ = float(Bd.mean())

mid = oracle.read_smf(a.midi)
div = mid['division']
allnotes = [(st / div, p, ti) for t in mid['tracks']
            for st, en, p, v, ti, ch in t['notes']]
mel = [n for n in allnotes if n[2] not in DRUMS]
tracks = {}
for n in mel:
    tracks.setdefault(n[2], []).append(n)

print(f'== {a.tag} {a.spec} [{t_lo:.1f},{a.t_hi:.1f}]  bpm={a.bpm} t0={a.t0} occ={occ:.4f}')


def ev(ns, k=0):
    if not ns:
        return 0.0, 0
    b = np.array([x[0] for x in ns])
    p = np.array([x[1] for x in ns])
    f = np.round((a.t0 + b * 60.0 / a.bpm - t_lo) / DT).astype(int)
    m = (f >= 0) & (f < T)
    f, p = f[m], p[m]
    if len(f) == 0:
        return 0.0, 0
    q = p - pm + k
    g = (q >= 0) & (q < P)
    return float(Bd[q[g], f[g]].sum()) / len(f), len(f)


def profile(ns, label):
    ks = list(range(-a.kmax, a.kmax + 1))
    hit = np.array([ev(ns, k)[0] for k in ks])
    n = ev(ns)[1]
    nul = np.zeros((a.draws, len(ks)))
    for d in range(a.draws):
        perm = rng.permutation(len(ns))
        sh = [(ns[i][0], ns[perm[i]][1], ns[i][2]) for i in range(len(ns))]
        nul[d] = [ev(sh, k)[0] for k in ks]
    mu, sd = nul.mean(axis=0), nul.std(axis=0)
    exc = hit - mu
    z = exc / np.maximum(sd, 1e-9)
    print(f'\n   {label}   n={n}')
    print(f'      {"k":>4s} {"hit":>7s} {"nullP":>7s} {"excess":>8s} {"z(perm)":>8s}')
    for i, k in enumerate(ks):
        if abs(k) > 14 and abs(exc[i]) < 0.02:
            continue
        star = ''
        if k == 0:
            star = '   <-- k=0'
        if exc[i] == exc.max():
            star += '   *MAX EXCESS*'
        print(f'      {k:+4d} {hit[i]:7.3f} {mu[i]:7.3f} {exc[i]:+8.3f} {z[i]:+8.2f}{star}')
    kb = ks[int(np.argmax(exc))]
    print(f'      -> max excess at k={kb:+d} ({exc.max():+.3f}); '
          f'k=0 excess {exc[ks.index(0)]:+.3f} (z={z[ks.index(0)]:+.2f})')
    return ks, hit, mu, exc, z


profile(mel, 'POOLED MELODIC')
for ti in sorted(tracks):
    if len(tracks[ti]) < 40:
        continue
    nm = mid['tracks'][ti]['name'] or f'trk{ti}'
    profile(tracks[ti], nm)
