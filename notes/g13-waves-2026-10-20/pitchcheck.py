#!/usr/bin/env python3
"""pitchcheck.py TRACE... -- does each traced voice, played by the wavedir.py model, sound
at the note the firmware meant?

QUESTION: with sample select = (the voice's TG pair, page = aux bits 19:12, entry = bits 11:0)
and rate = 2**((p18-0x1E200)/0x3000 + E - 9) * C7/44100, is the period of the selected
sample's loop the one that makes the voice sound at the firmware's own note (the voice
record's notePitch16, logged by tg_trace.lua)?

For each note-on: T_pred = rate * 44100 / f(note), the period the loop must have.
  * loop test (exact, no spectrum): a seamless loop holds a whole number of periods, so
    M / T_pred (M = loop length) must be an integer; the column is its distance from the
    nearest integer, in periods ("ok" when <= 0.02). Single-period loops pass exactly.
  * spectral test: T_meas = the period of the last 16384 samples up to the loop end,
    by a harmonic-sum search within +-0.35 octave of T_pred; error 1200*log2(T_meas/T_pred).
    It is fooled by attacks inside that window and by noise-like samples.
Drum voices (notePitch16 0x4280, unpitched) are skipped. Voices whose note is not the key
(organ footages, the digital drawbar's 16'/5 1/3'..., sound-effect layers) fail both tests
by design: their reference here is the key, not the footage.
RUN: python3 pitchcheck.py ~/compartilhado/tmp/g13-waves/trace5/trace.txt [-v]
"""
import sys
from collections import defaultdict
import numpy as np
from wavedir import *
from noteons import noteons


def harmonic_period(x, Tpred, span=0.35):
    x = (x - x.mean()) * np.hanning(len(x))
    N = 1 << int(np.ceil(np.log2(len(x) * 8)))
    X = np.abs(np.fft.rfft(x, N))
    best = None
    for T in np.exp(np.linspace(np.log(Tpred) - span * np.log(2), np.log(Tpred) + span * np.log(2), 1500)):
        idx = (np.arange(1, 9) * N / T).round().astype(int)
        idx = idx[idx < len(X)]
        sc = np.log(X[idx] + 1e-9).mean()
        if best is None or sc > best[0]:
            best = (sc, T)
    return best[1]


def check(tg, aux20, p18, np16):
    e = select(tg, aux20)
    if e is None:
        return None, 'no entry'
    s = stream(tg)
    r = parse_record(record(s, e), e['L'])
    end = e['page'] * PAGE + e['B'] * 16
    n = r['le'] // (2 if e['is8'] else 1) + 16
    e2 = dict(e); e2['end'] = e['B'] + (n + 15) // 16
    x = samples(s, e2)
    seg = x[max(0, r['le'] - 16384): r['le']]
    if len(seg) < 64 or not np.any(seg):
        return None, 'silent loop'
    f = 440.0 * 2 ** (((np16 - 0x80) / 256 - 69) / 12)
    Tpred = rate(p18, e['E']) * 44100.0 / f
    T = harmonic_period(seg, Tpred)
    cyc = (r['le'] - r['ls']) / Tpred
    return (1200 * np.log2(T / Tpred), abs(cyc - round(cyc)) if round(cyc) >= 1 else 1.0), ''


if __name__ == '__main__':
    verbose = '-v' in sys.argv
    by = defaultdict(list)
    seen = {}
    for tr in [a for a in sys.argv[1:] if a != '-v']:
        for n in noteons(tr):
            if not n['mark'] or n['np16'] in (None, 0x4280, 0):
                continue
            g = n['mark'].split()[1]
            key = (n['tg'], n['aux20'], n['p18'], n['np16'])
            if key not in seen:
                seen[key] = check(n['tg'], n['aux20'], n['p18'], n['np16'])
            c, why = seen[key]
            by[g].append(c)
            if verbose:
                print('%-18s tg%d aux20=%05x p18=%05x  %s' % (n['mark'], n['tg'], n['aux20'], n['p18'],
                      '%+6.1f cents, loop off a whole cycle count by %.3f' % c if c is not None else why))
    tot = ok = okl = oke = 0
    for g, cs in sorted(by.items()):
        v = [c for c in cs if c is not None]
        k = sum(abs(c[0]) <= 15 for c in v)
        kl = sum(c[1] <= 0.02 for c in v)
        ke = sum(abs(c[0]) <= 15 or c[1] <= 0.02 for c in v)
        tot += len(cs); ok += k; okl += kl; oke += ke
        print('%-9s voices %3d   loop test ok %3d   spectral within 15 cents %3d   either %3d   no measurement %3d'
              % (g, len(cs), kl, k, ke, len(cs) - len(v)))
    print('all       voices %3d   loop test ok %3d   spectral within 15 cents %3d   either %3d' % (tot, okl, ok, oke))
