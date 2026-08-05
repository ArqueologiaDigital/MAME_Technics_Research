#!/usr/bin/env python3
"""All the fixed-alignment measurements on ONE long capture.

Every score is quoted at a FIXED (bpm, t0); nothing is re-optimised, and every
null is evaluated through exactly the same code path as the measurement.

  A  headline hit@0 with NULL-T / NULL-P / NULL-F / BLIND
  B  global semitone-offset histogram (is the error a constant transposition?)
  C  per-part table (n, hit@0, matched null, z, argmax shift)
  D  hit rate over TIME, in bins, pooled and per part
  E  hit rate over REGISTER, in bins, per part

  long_eval.py --spec spec_sine_long.npz --t-lo 18 --t-hi 220 --bpm 90 --t0 19.2 --tag sineL
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
ap.add_argument('--tag', default='out')
ap.add_argument('--tbins', type=int, default=12)
ap.add_argument('--draws', type=int, default=60)
a = ap.parse_args()

DRUM_TRACKS = {10, 16}          # Part 9 and Part 15: a drum note is a kit key
rng = np.random.default_rng(4242)

B, pitches, times, _ = surface.onset_surface(a.spec, a.t_lo, a.t_hi)
t_lo = float(times[0])
Bd = oracle.dilate(B, int(round(a.tol_ms / 1000.0 / DT)))
Any = Bd.max(axis=0)
P, T = Bd.shape
pm = int(pitches[0])
occ = float(Bd.mean())

mid = oracle.read_smf(a.midi)
div = mid['division']
allnotes = [(st / div, p, ti) for t in mid['tracks']
            for st, en, p, v, ti, ch in t['notes']]
mel = [n for n in allnotes if n[2] not in DRUM_TRACKS]

print(f'== {a.tag}  spec={a.spec}  window {t_lo:.2f}..{a.t_hi:.2f}s')
print(f'   FIXED ALIGNMENT bpm={a.bpm:.3f} t0={a.t0:.3f}s   tol=+-{a.tol_ms:.0f} ms')
print(f'   surface {P}x{T}, onsets {int(B.sum())}, occupancy (NULL-F) {occ:.4f}')
print(f'   MIDI notes: all={len(allnotes)} melodic={len(mel)} '
      f'(drums = tracks {sorted(DRUM_TRACKS)})')


def ev(ns, k=0, dbeat=0.0, blind=False):
    """(hit fraction, n in window) for a note list at the fixed alignment."""
    if not ns:
        return 0.0, 0
    b = np.array([x[0] for x in ns]) + dbeat
    p = np.array([x[1] for x in ns])
    f = np.round((a.t0 + b * 60.0 / a.bpm - t_lo) / DT).astype(int)
    m = (f >= 0) & (f < T)
    f, p = f[m], p[m]
    if len(f) == 0:
        return 0.0, 0
    if blind:
        return float(Any[f].mean()), len(f)
    q = p - pm + k
    g = (q >= 0) & (q < P)
    return float(Bd[q[g], f[g]].sum()) / len(f), len(f)


def nullT(ns, lo=2.0, hi=40.0, draws=None, blind=False):
    d = draws or a.draws
    v = [ev(ns, 0, float(rng.uniform(lo, hi)), blind=blind)[0] for _ in range(d)]
    return float(np.mean(v)), float(np.std(v))


def nullTlocal(ns, lo=1.5, hi=6.0, draws=None):
    """Random shift that keeps the notes in the SAME musical region."""
    d = draws or a.draws
    v = []
    for _ in range(d):
        s = float(rng.uniform(lo, hi)) * (1 if rng.random() < 0.5 else -1)
        v.append(ev(ns, 0, s)[0])
    return float(np.mean(v)), float(np.std(v))


def nullP(ns, draws=None):
    d = draws or a.draws
    v = []
    for _ in range(d):
        perm = rng.permutation(len(ns))
        v.append(ev([(ns[i][0], ns[perm[i]][1], ns[i][2]) for i in range(len(ns))])[0])
    return float(np.mean(v)), float(np.std(v))


def zof(h, q, n):
    return (h - q) / np.sqrt(max(q * (1 - q), 1e-9) / max(n, 1))


# ---------------- A: headline ----------------------------------------------
print('\n-- A. HEADLINE (fixed alignment, no re-optimisation)')
print(f'{"subset":10s} {"n":>5s} {"hit@0":>7s} {"NULL-T":>7s} {"NULL-P":>7s} {"NULL-F":>7s} '
      f'{"z":>8s} {"BLIND":>7s} {"blindN":>7s}')
for sub, ns in (('all', allnotes), ('melodic', mel)):
    h, n = ev(ns)
    qt, _ = nullT(ns)
    qp, _ = nullP(ns)
    bl, _ = ev(ns, blind=True)
    bn, _ = nullT(ns, blind=True)
    print(f'{sub:10s} {n:5d} {h:7.3f} {qt:7.3f} {qp:7.3f} {occ:7.3f} '
          f'{zof(h, qt, n):+8.1f} {bl:7.3f} {bn:7.3f}')

# ---------------- B: semitone histogram -------------------------------------
print('\n-- B. GLOBAL SEMITONE-OFFSET SWEEP (melodic only)')
ks = list(range(-24, 25))
hs = [ev(mel, k)[0] for k in ks]
qs, _ = nullP(mel)
mx = max(hs)
for k, h in zip(ks, hs):
    bar = '#' * int(round(60 * h / max(mx, 1e-9)))
    star = ' <<<' if h == mx else ''
    print(f'   {k:+3d} {h:.4f} {bar}{star}')
print(f'   best k={ks[int(np.argmax(hs))]:+d} ({mx:.4f}); k=0 is {hs[ks.index(0)]:.4f}; '
      f'mean over k={np.mean(hs):.4f}; NULL-P={qs:.4f}')

# ---------------- C: per part ------------------------------------------------
tracks = {}
for st, p, ti in allnotes:
    tracks.setdefault(ti, []).append((st, p, ti))
print('\n-- C. PER-PART (matched null = same notes, random 2..40-beat displacement)')
print(f'   {"part":28s} {"n":>4s} {"hit@0":>7s} {"nullT":>7s} {"z":>7s} {"argmax k":>9s} '
      f'{"peak":>7s}')
KMAX = 36
percurve = {}
for ti in sorted(tracks):
    ns = tracks[ti]
    h, n = ev(ns)
    if n < 10:
        continue
    q, _ = nullT(ns)
    prof = np.array([ev(ns, k)[0] for k in range(-KMAX, KMAX + 1)])
    kb = int(np.argmax(prof)) - KMAX
    name = (mid['tracks'][ti]['name'] or f'trk{ti}')[:27]
    tag = ' [DRUMS]' if ti in DRUM_TRACKS else ''
    print(f'   {name:28s} {n:4d} {h:7.3f} {q:7.3f} {zof(h,q,n):+7.2f} {kb:+9d} '
          f'{prof.max():7.3f}{tag}')
    percurve[ti] = prof

# ---------------- D: over time ----------------------------------------------
print(f'\n-- D. HIT RATE OVER TIME ({a.tbins} bins; nullT-local = random +-1.5..6 beat shift)')
bmax = max(x[0] for x in mel)
edges = np.linspace(0, bmax, a.tbins + 1)


def timetable(ns, label):
    print(f'   {label}')
    print(f'      {"bin":>3s} {"beats":>13s} {"t(s)":>13s} {"n":>4s} {"hit@0":>7s} '
          f'{"nullTloc":>8s} {"z":>7s} {"BLIND":>7s} {"blindN":>7s}')
    rows = []
    for i in range(a.tbins):
        sub = [x for x in ns if edges[i] <= x[0] < edges[i + 1]]
        h, n = ev(sub)
        if n < 8:
            print(f'      {i:3d} {edges[i]:6.0f}-{edges[i+1]:6.0f} '
                  f'{"":13s} {n:4d}    (too few)')
            rows.append((i, n, np.nan, np.nan))
            continue
        q, _ = nullTlocal(sub)
        bl, _ = ev(sub, blind=True)
        bq, _ = nullT(sub, blind=True)
        ta = a.t0 + edges[i] * 60.0 / a.bpm
        tb = a.t0 + edges[i + 1] * 60.0 / a.bpm
        print(f'      {i:3d} {edges[i]:6.0f}-{edges[i+1]:6.0f} {ta:6.1f}-{tb:6.1f} '
              f'{n:4d} {h:7.3f} {q:8.3f} {zof(h,q,n):+7.2f} {bl:7.3f} {bq:7.3f}')
        rows.append((i, n, h, q))
    return rows


timetable(mel, 'POOLED MELODIC')
for ti in sorted(tracks):
    if ti in DRUM_TRACKS:
        continue
    if len(tracks[ti]) < 120:
        continue
    name = (mid['tracks'][ti]['name'] or f'trk{ti}')
    timetable(tracks[ti], name)

# ---------------- E: over register ------------------------------------------
print('\n-- E. HIT RATE BY REGISTER (6-semitone bins; nullT = random 2..40-beat shift)')
for ti in sorted(tracks):
    if ti in DRUM_TRACKS:
        continue
    ns = tracks[ti]
    if len(ns) < 60:
        continue
    name = (mid['tracks'][ti]['name'] or f'trk{ti}')
    ps = np.array([x[1] for x in ns])
    lo, hi = int(ps.min()), int(ps.max())
    print(f'   {name}  pitch {lo}..{hi}')
    for b0 in range(lo - lo % 6, hi + 1, 6):
        sub = [x for x in ns if b0 <= x[1] < b0 + 6]
        h, n = ev(sub)
        if n < 8:
            continue
        q, _ = nullT(sub)
        print(f'      MIDI {b0:3d}-{b0+5:3d}  n={n:4d}  hit@0={h:.3f}  nullT={q:.3f}  '
              f'z={zof(h,q,n):+6.2f}')

np.savez_compressed(f'longeval_{a.tag}.npz',
                    **{f'prof{ti}': v for ti, v in percurve.items()},
                    meta=np.array([a.bpm, a.t0, occ, t_lo, a.t_hi]))
print(f'\n   saved longeval_{a.tag}.npz')
