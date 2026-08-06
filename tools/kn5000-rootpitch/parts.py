#!/usr/bin/env python3
"""Attribute every captured tone-generator note-on to a MIDI PART, using the
firmware-C-decoded note, and then report per part what the 0x3524 anchor does to it.

This is the direct answer to "what do Parts 7/11 have that Parts 2/8 do not".
"""
import collections, math, os, random, sys
sys.path.insert(0, os.path.expanduser('~/compartilhado/kn7000_mame/tools'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'oracle'))
import kn5000_pitch_audit as A
import midiparse

HERE = os.path.dirname(os.path.abspath(__file__))
ORACLE = os.path.join(HERE, '..', 'oracle')
W = A.trim_table(A.read_sets())
Cmodal = {sel: c.most_common(1)[0][0] for sel, c in W.items()}
Cuniq = {sel: list(c)[0] for sel, c in W.items() if len(c) == 1}

# ---- captured note-ons ------------------------------------------------------------------
ev = []
for line in open(os.path.join(HERE, 'kon.log')):
    p = line.split()
    if len(p) == 5 and p[0] == 'KON':
        t, ch, sel, pit = float(p[1]), int(p[2]), int(p[3], 16), int(p[4], 16)
        if t >= 17.0 and pit and sel in Cmodal:
            ev.append(dict(t=t, ch=ch, sel=sel, pit=pit,
                           nB=(pit - 128 - Cmodal[sel]) / 256.0,
                           nA=60 + (pit - 0x3524) / 256.0))
print("captured note-ons: %d, t = %.1f .. %.1f s" % (len(ev), ev[0]['t'], ev[-1]['t']))

# ---- the demo's own MIDI ----------------------------------------------------------------
mid = midiparse.read_smf(os.path.join(ORACLE, 'demo_preset_18.mid'))
div = mid['division']
mnotes = []
for t in mid['tracks']:
    nm = t.get('name') or ''
    for st, en, p, v, ti, ch in t['notes']:
        mnotes.append(dict(beat=st / div, p=p, ti=ti, name=nm))
print("MIDI notes: %d over %d parts" % (len(mnotes), len({n['ti'] for n in mnotes})))
names = {}
for t in mid['tracks']:
    for st, en, p, v, ti, ch in t['notes']:
        names[ti] = t.get('name') or ('track %d' % ti)
        break


def score(t0, bpm, notes_dec, tol=0.060, half=False):
    """how many MIDI notes have a captured note-on at the right time AND pitch"""
    grid = collections.defaultdict(list)
    for i, e in enumerate(ev):
        grid[int(e['t'] / tol)].append(i)
    hit = 0
    assign = {}
    for k, n in enumerate(mnotes):
        tp = t0 + n['beat'] * 60.0 / bpm
        if not (ev[0]['t'] - 1 <= tp <= ev[-1]['t'] + 1):
            continue
        b = int(tp / tol)
        best = None
        for bb in (b - 1, b, b + 1):
            for i in grid.get(bb, ()):
                if abs(ev[i]['t'] - tp) > tol:
                    continue
                d = abs(notes_dec[i] - n['p'])
                if d <= 0.5 and (best is None or d < best[0]):
                    best = (d, i)
        if best:
            hit += 1
            assign[k] = best[1]
    return hit, assign


nB = [e['nB'] for e in ev]
best = (0, None)
for bpm in [89.5 + 0.25 * i for i in range(9)]:
    for t0 in [16.0 + 0.05 * i for i in range(140)]:
        h, _ = score(t0, bpm, nB)
        if h > best[0]:
            best = (h, (t0, bpm))
h, (t0, bpm) = best[0], best[1]
inwin = sum(1 for n in mnotes if ev[0]['t'] - 1 <= t0 + n['beat'] * 60 / bpm <= ev[-1]['t'] + 1)
print("\n== alignment fitted on the DECODED notes ==")
print("   best t0=%.2f s  bpm=%.2f : %d of the %d MIDI notes in the capture window matched "
      "(%.1f%%)" % (t0, bpm, h, inwin, 100.0 * h / inwin))

rng = random.Random(3)
nulls = []
for _ in range(20):
    sh = list(nB); rng.shuffle(sh)
    b2 = 0
    for bb in [89.5 + 0.25 * i for i in range(9)]:
        for tt in [16.0 + 0.2 * i for i in range(35)]:
            b2 = max(b2, score(tt, bb, sh)[0])
    nulls.append(b2)
print("   NULL (decoded notes permuted, alignment re-optimised each draw): %.0f +- %.0f  "
      "= %.1f%% -> the match is %.1fx chance"
      % (sum(nulls) / len(nulls), (max(nulls) - min(nulls)) / 4,
         100.0 * (sum(nulls) / len(nulls)) / inwin, h / (sum(nulls) / len(nulls))))

hA, _ = score(t0, bpm, [e['nA'] for e in ev])
print("   the SAME match using the 0x3524-anchor note instead: %d (%.1f%%)"
      % (hA, 100.0 * hA / inwin))

# ---- per part ---------------------------------------------------------------------------
_, assign = score(t0, bpm, nB)
per = collections.defaultdict(lambda: dict(n=0, hit=0, sels=collections.Counter(),
                                           err=[], res=[]))
for k, n in enumerate(mnotes):
    tp = t0 + n['beat'] * 60.0 / bpm
    if not (ev[0]['t'] - 1 <= tp <= ev[-1]['t'] + 1):
        continue
    d = per[n['ti']]
    d['n'] += 1
    if k in assign:
        e = ev[assign[k]]
        d['hit'] += 1
        d['sels'][e['sel']] += 1
        d['err'].append(e['nA'] - n['p'])
        d['res'].append(e['nB'] - n['p'])

print("\n== PER PART: what the 0x3524 anchor renders, minus the note the MIDI asks for ==")
print("%-26s %5s %5s  %8s  %s" % ("part", "notes", "match", "med err", "anchor error distribution (semitones)"))
for ti in sorted(per):
    d = per[ti]
    if d['hit'] < 5:
        continue
    e = sorted(d['err'])
    med = e[len(e) // 2]
    within = 100.0 * sum(1 for x in e if abs(x) <= 0.5) / len(e)
    hist = collections.Counter(round(x) for x in e)
    top = ', '.join("%+d:%d" % kv for kv in sorted(hist.items(), key=lambda kv: -kv[1])[:5])
    print("%-26s %5d %5d  %+8.2f  |err|<=0.5: %5.1f%%   %s"
          % (names.get(ti, str(ti))[:26], d['n'], d['hit'], med, within, top))

print("\n== the selectors each part uses, and their C ==")
for ti in sorted(per):
    d = per[ti]
    if d['hit'] < 5:
        continue
    ss = ', '.join("%04X(C=%d,err%+.1f)%s" % (s, Cmodal[s], 60 + (Cmodal[s] - 13476) / 256.0,
                                              '' if s in Cuniq else '*')
                   for s, _ in d['sels'].most_common(4))
    print("   %-26s %s" % (names.get(ti, str(ti))[:26], ss))
print("   (* = the selector carries more than one C in the firmware tables)")
