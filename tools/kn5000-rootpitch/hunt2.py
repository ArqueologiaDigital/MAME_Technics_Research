#!/usr/bin/env python3
"""Null-gated hunt for the 3-bit ROOT OCTAVE in the IC307 parameter records.

Every purity figure is compared with a PERMUTATION NULL (m shuffled across chunks, the
feature values left alone), because a feature with many distinct values scores high by
construction.

Sharpest test of all: if the record determines the root, two chunks with BYTE-IDENTICAL
records must have the same m.
"""
import collections, json, math, os, random, sys
sys.path.insert(0, os.path.expanduser('~/compartilhado/kn7000_mame/tools'))
import kn5000_pitch_audit as A
import records as R

HERE = os.path.dirname(os.path.abspath(__file__))
gt = {tuple(int(x) for x in k.split(',')): v for k, v in json.load(open(os.path.join(HERE, 'gt.json'))).items()}
tr = {k: v for k, v in gt.items() if abs(v['res']) <= 64}
rng = random.Random(17)

print("trusted chunks: %d   m distribution: %s" %
      (len(tr), dict(sorted(collections.Counter(v['m'] for v in tr.values()).items()))))
for cls in (4, 5, 6, 7):
    sub = {k: v for k, v in tr.items() if v['cls'] == cls}
    print("   class %d (page %d): n=%3d  m: %s" %
          (cls, cls & 3, len(sub), dict(sorted(collections.Counter(v['m'] for v in sub.values()).items()))))


def purity(feat, target):
    g = collections.defaultdict(collections.Counter)
    for k in target:
        g[feat[k]][target[k]] += 1
    return sum(c.most_common(1)[0][1] for c in g.values()) / len(target)


def gated(name, feat, target, draws=200):
    obs = purity(feat, target)
    ks = list(target)
    nn = []
    for _ in range(draws):
        vs = [target[k] for k in ks]; rng.shuffle(vs)
        nn.append(purity(feat, dict(zip(ks, vs))))
    mu = sum(nn) / len(nn); sd = (sum((x - mu) ** 2 for x in nn) / len(nn)) ** .5 or 1e-9
    z = (obs - mu) / sd
    print("   %-22s purity %5.1f%%   null %5.1f%% +- %4.1f   z = %+6.2f%s"
          % (name, 100 * obs, 100 * mu, 100 * sd, z, "   <== SIGNAL" if z > 4 else ""))
    return z


M = {k: v['m'] for k, v in tr.items()}
print("\n== features of the parameter record ==")
feat = {}


def rec(k):
    return R.pages[k[0]]['recs'][k[1]]


cand = {
    'record bytes (exact)': lambda k: bytes(rec(k)['raw'][2:]),
    'n pairs': lambda k: len(rec(k)['pairs']),
    'first flag': lambda k: rec(k)['pairs'][0][1] if rec(k)['pairs'] else -1,
    'first value': lambda k: rec(k)['pairs'][0][0] if rec(k)['pairs'] else -1,
    'first val>>5': lambda k: (rec(k)['pairs'][0][0] >> 5) if rec(k)['pairs'] else -1,
    'first val&7': lambda k: (rec(k)['pairs'][0][0] & 7) if rec(k)['pairs'] else -1,
    'last flag': lambda k: rec(k)['pairs'][-1][1] if rec(k)['pairs'] else -1,
    'last value': lambda k: rec(k)['pairs'][-1][0] if rec(k)['pairs'] else -1,
    'last val>>5': lambda k: (rec(k)['pairs'][-1][0] >> 5) if rec(k)['pairs'] else -1,
    'flag set': lambda k: tuple(sorted({p[1] for p in rec(k)['pairs']})),
    'marker flags only': lambda k: tuple(f for _, f in rec(k)['pairs'] if f & 0xC0),
    'top split byte': lambda k: max([v for v, f in rec(k)['pairs'] if f == 0], default=-1),
    'n splits': lambda k: sum(1 for _, f in rec(k)['pairs'] if f == 0),
    'PCM samples log2': lambda k: int(math.log2(max(tr[k]['ns'], 1))),
    'page': lambda k: k[0],
    'chunk index >>4': lambda k: k[1] >> 4,
}
for nm, fn in cand.items():
    gated(nm, {k: fn(k) for k in M}, M)

print("\n== the sharpest test: do BYTE-IDENTICAL records carry the same m? ==")
g = collections.defaultdict(list)
for k in M:
    g[bytes(rec(k)['raw'][2:])].append(M[k])
multi = {kk: v for kk, v in g.items() if len(v) > 1}
same = sum(1 for v in multi.values() if len(set(v)) == 1)
npair = sum(len(v) * (len(v) - 1) // 2 for v in multi.values())
agree = sum(sum(1 for i in range(len(v)) for j in range(i + 1, len(v)) if v[i] == v[j]) for v in multi.values())
print("   %d record byte-strings are shared by >1 chunk (%d chunks, %d pairs)"
      % (len(multi), sum(len(v) for v in multi.values()), npair))
print("   groups whose chunks all share one m: %d/%d ; PAIRWISE agreement %d/%d = %.1f%%"
      % (same, len(multi), agree, npair, 100.0 * agree / max(npair, 1)))
ms = list(M.values())
nn = []
for _ in range(400):
    rng.shuffle(ms)
    mm = dict(zip(list(M), ms))
    a = 0; t = 0
    for kk, v in g.items():
        ks = [k for k in M if bytes(rec(k)['raw'][2:]) == kk]
        if len(ks) < 2: continue
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                t += 1; a += (mm[ks[i]] == mm[ks[j]])
    nn.append(a / max(t, 1))
mu = sum(nn) / len(nn)
print("   NULL (m shuffled): %.1f%%  -> %s" % (100 * mu,
      "records DO carry the octave" if 100.0 * agree / max(npair, 1) > 100 * mu + 15 else
      "no more agreement than chance"))
