#!/usr/bin/env python3
"""ROOT(chunk) = 256*nat + 0x80 + C   is the value the LSI must subtract from +0x400 to
get the playback rate.  Two questions:

  Q1  is ROOT quantised to WHOLE OCTAVES globally (i.e. is the missing per-chunk datum
      only 3 bits, not 16)?   -> ROOT mod 3072 must be a tight cluster.
  Q2  can those 3 bits be predicted from anything the CHIP can see: the parameter
      record, the directory entry, the PCM geometry?

Null for Q2: a feature that predicts m must beat the best CONSTANT guess (the modal m)
and must not simply be a proxy for the measured period (which is already in the model).
"""
import collections, json, math, os, sys
sys.path.insert(0, os.path.expanduser('~/compartilhado/kn7000_mame/tools'))
import kn5000_pitch_audit as A
import records as R

pages, d = R.pages, R.d
gt = {tuple(int(x) for x in k.split(',')): v for k, v in json.load(
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gt.json'))).items()}

SR = 48000.0
rows = []
for (pg, e), v in gt.items():
    nat = 69 + 12 * math.log2(SR / (440 * v['P']))
    ROOT = 256 * nat + 128 + v['C']
    rows.append(dict(pg=pg, e=e, cls=v['cls'], C=v['C'], P=v['P'], ns=v['ns'], w=v['w'],
                     nat=nat, ROOT=ROOT, m=v['m'], res=v['res']))
rows.sort(key=lambda r: (r['pg'], r['e']))
trusted = [r for r in rows if abs(r['res']) <= 64]

print("== Q1: is ROOT octave-quantised?  ROOT mod 3072 over the %d trusted chunks ==" % len(trusted))
mods = sorted((r['ROOT'] % 3072) for r in trusted)
print("   min %.0f  p5 %.0f  median %.0f  p95 %.0f  max %.0f   (3072 = one octave)"
      % (mods[0], mods[len(mods) // 20], mods[len(mods) // 2], mods[19 * len(mods) // 20], mods[-1]))
print("   spread %.0f units = %.1f cents" % (mods[-1] - mods[0], (mods[-1] - mods[0]) * 100 / 256))
allmods = sorted((r['ROOT'] % 3072) for r in rows)
print("   ALL %d single-C chunks (incl. the 25 off-lattice): p5 %.0f  median %.0f  p95 %.0f"
      % (len(rows), allmods[len(allmods) // 20], allmods[len(allmods) // 2], allmods[19 * len(allmods) // 20]))
print("   ROOT/256 (= root note under the SR=48k assumption) octave ladder:",
      sorted(collections.Counter(round(r['ROOT'] / 3072) for r in trusted).items()))

print("\n== Q2: predict m ==")
mc = collections.Counter(r['m'] for r in trusted)
base = max(mc.values()) / len(trusted)
print("   NULL (always guess the modal m=%d): %.1f%%" % (mc.most_common(1)[0][0], 100 * base))


def feats(r):
    rec = pages[r['pg']]['recs'][r['e']]
    pr = rec['pairs']
    f = {}
    f['n_pairs'] = len(pr)
    f['rec_len'] = len(rec['raw'])
    f['last_flag'] = pr[-1][1] if pr else -1
    f['last_val'] = pr[-1][0] if pr else -1
    f['first_flag'] = pr[0][1] if pr else -1
    f['first_val'] = pr[0][0] if pr else -1
    f['last_val_hi3'] = (pr[-1][0] >> 5) if pr else -1
    f['flagset'] = tuple(sorted({q[1] for q in pr}))
    f['has_split'] = any(q[1] == 0 for q in pr)
    f['n_split'] = sum(1 for q in pr if q[1] == 0)
    f['top_split'] = max([q[0] for q in pr if q[1] == 0], default=-1)
    f['bot_split'] = min([q[0] for q in pr if q[1] == 0], default=-1)
    f['wave_align'] = (pages[r['pg']]['wave'][r['e']] & 15)
    f['wave_tz'] = (pages[r['pg']]['wave'][r['e']] & -pages[r['pg']]['wave'][r['e']]).bit_length() \
        if pages[r['pg']]['wave'][r['e']] else -1
    f['ns_log2'] = int(math.log2(max(r['ns'], 1)))
    f['param_lo2'] = pages[r['pg']]['param'][r['e']] & 3
    f['page'] = r['pg']
    return f


F = [(feats(r), r['m']) for r in trusted]
names = sorted(F[0][0])
print("   feature                 best-single-value purity   #values   (higher than NULL = signal)")
for nm in names:
    g = collections.defaultdict(collections.Counter)
    for f, m in F:
        g[f[nm]][m] += 1
    correct = sum(c.most_common(1)[0][1] for c in g.values())
    print("     %-14s %6.1f%%   distinct=%d" % (nm, 100 * correct / len(F), len(g)))

# the residual after the period is already known: does any feature explain what nat cannot?
print("\n   CONTROL — how well does the measured period ALONE predict m?")
best = 0; bestc = None
for c in range(-200, 201):
    ok = sum(1 for r in trusted if round((r['nat'] * 256 + c) / 3072) == r['m'])
    if ok > best: best, bestc = ok, c
print("     round((256*nat + %d)/3072) == m for %d/%d = %.1f%%" % (bestc, best, len(trusted), 100 * best / len(trusted)))

print("\n== per-class m ranges (does each PAGE use a narrow set of octaves?) ==")
for cls in (4, 5, 6, 7):
    sub = [r for r in trusted if r['cls'] == cls]
    if not sub: continue
    cc = collections.Counter(r['m'] for r in sub)
    kw = collections.Counter()
    for r in sub: kw[r['m']] += r['w']
    print("   class %d: n=%3d  m: %s   key-weighted: %s" %
          (cls, len(sub), dict(sorted(cc.items())), dict(sorted(kw.items()))))
