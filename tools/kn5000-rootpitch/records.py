#!/usr/bin/env python3
"""Per-chunk ROOT OCTAVE: build the ground-truth vector, then hunt for it in the
IC307 parameter records.

GROUND TRUTH.  The firmware's per-zone constant C (kn5000_pitch_audit.py) and the
chunk's MEASURED fundamental period P are related, MODULO ONE OCTAVE, by
      K = C + 0x80 - 3072*log2(P)   ==  K0  (mod 3072),  K0 ~= 127
(audit sec.5: 95-100% of chunks within +-25 cents on 3 of the 4 pages).  So the only
thing the chip cannot get from C is the integer
      m(chunk) = round( (C + 0x80 - 3072*log2(P) - K0) / 3072 )
which is exactly the "per-chunk root pitch, octave part".  If IC307's parameter record
for a chunk carries a field that predicts m, the root pitch IS decodable.

Record grammar (notes/kn5000-ic307-content-map.md sec.3):
    uint16 wave_start ; {value:8, flag:8} * N ; terminator flag has bit7|bit6
"""
import bisect, collections, json, math, os, sys

sys.path.insert(0, os.path.expanduser('~/compartilhado/kn7000_mame/tools'))
import kn5000_pitch_audit as A

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'periods.json')
d = open(A.IC307, 'rb').read()
PAGE = A.PAGE


def parse_page_full(base):
    u16 = lambda o: d[base + o] | (d[base + o + 1] << 8)
    head = u16(0)
    if head == 0 or head & 3:
        return None
    n = head // 4
    param, wave = [], []
    for i in range(n):
        p, w = u16(i * 4), u16(i * 4 + 2)
        if (i and p < param[-1]) or p < n * 4 or w * 16 >= PAGE or u16(p) != w:
            return None
        param.append(p); wave.append(w)
    srt = sorted(set(wave))
    start, samples = [], []
    for i in range(n):
        j = bisect.bisect_right(srt, wave[i])
        end = PAGE if j >= len(srt) else srt[j] * 16
        off = wave[i] * 16
        start.append(base + off)
        samples.append((end - off) // 2 if end > off else 0)
    # parameter record extent: param_ptr[i] .. next STRICTLY GREATER param_ptr
    psrt = sorted(set(param))
    recs = []
    for i in range(n):
        j = bisect.bisect_right(psrt, param[i])
        pend = psrt[j] if j < len(psrt) else (min(wave) * 16)
        raw = d[base + param[i]: base + pend]
        pairs = [(raw[k], raw[k + 1]) for k in range(2, len(raw) - 1, 2)]
        recs.append(dict(ptr=param[i], end=pend, raw=raw, pairs=pairs,
                         shared=sum(1 for x in param if x == param[i]) > 1))
    return dict(count=n, start=start, samples=samples, wave=wave, param=param, recs=recs)


pages = {p: parse_page_full(p * PAGE) for p in range(4)}
per = {tuple(int(x) for x in k.split(',')): v for k, v in json.load(open(CACHE)).items()} \
    if os.path.exists(CACHE) else {}


def period(pg, e):
    k = (pg, e)
    if k not in per:
        P = pages[pg]
        per[k] = A.detect_period(d, P['start'][e], P['samples'][e])
    return per[k]


sets = A.read_sets()
W = A.trim_table(sets)

# ---- per-class K0, circular median on the single-C chunks with a good period ------------
K0 = {}
rows = []
for sel, cnt in W.items():
    cls, ent = sel >> 12, sel & 0xFFF
    if cls not in (4, 5, 6, 7):
        continue
    pg = pages[cls & 3]
    if not pg or ent >= pg['count']:
        continue
    P = period(cls & 3, ent)
    ns = pg['samples'][ent]
    good = P > 0 and abs(P - ns) > 1e-9 and ns >= 64
    rows.append(dict(cls=cls, ent=ent, C=list(cnt)[0] if len(cnt) == 1 else None,
                     Cs=dict(cnt), P=P, ns=ns, good=good, w=sum(cnt.values())))
json.dump({','.join(str(x) for x in k): v for k, v in per.items()}, open(CACHE, 'w'))

for cls in (4, 5, 6, 7):
    ks = [(r['C'] + 128 - 3072 * math.log2(r['P'])) % 3072
          for r in rows if r['cls'] == cls and r['C'] is not None and r['good']]
    if not ks:
        continue
    K0[cls] = min(ks, key=lambda a: sum(min(abs(x - a), 3072 - abs(x - a)) for x in ks))

K_GLOBAL = sum(K0.values()) / len(K0)
print("K0 per class:", {c: round(v, 1) for c, v in K0.items()}, " global mean %.1f" % K_GLOBAL)

# ---- ground-truth m and residual --------------------------------------------------------
gt = {}
for r in rows:
    if r['C'] is None or not r['good']:
        continue
    x = r['C'] + 128 - 3072 * math.log2(r['P']) - K_GLOBAL
    m = round(x / 3072.0)
    res = x - 3072 * m
    gt[(r['cls'] & 3, r['ent'])] = dict(m=m, res=res, C=r['C'], P=r['P'], cls=r['cls'],
                                        w=r['w'], ns=r['ns'])

tight = {k: v for k, v in gt.items() if abs(v['res']) <= 64}
print("ground truth: %d chunks with single C + good period; %d within +-64 units (25 cents) "
      "of the octave lattice = the TRUSTED set" % (len(gt), len(tight)))
print("   m histogram (trusted):", dict(sorted(collections.Counter(v['m'] for v in tight.values()).items())))
print("   native note = 69+12*log2(48000/(440*P)) range: %.1f .. %.1f" % (
    min(69 + 12 * math.log2(48000 / (440 * v['P'])) for v in tight.values()),
    max(69 + 12 * math.log2(48000 / (440 * v['P'])) for v in tight.values())))

json.dump({"%d,%d" % k: v for k, v in gt.items()}, open(os.path.join(HERE, 'gt.json'), 'w'), indent=0)

# ---- what the records look like for the trusted chunks ----------------------------------
print("\n== flag vocabulary over the four pages ==")
fl = collections.Counter()
for p in range(4):
    if pages[p]:
        for r in pages[p]['recs']:
            for v, f in r['pairs']:
                fl[f] += 1
print("   ", dict(sorted(fl.items(), key=lambda kv: -kv[1])[:20]))

print("\n== sample of TRUSTED chunks, sorted by m then native note ==")
print("%-8s %-5s %8s %7s %6s %6s  %s" % ("page/ent", "m", "C", "P", "nat", "res", "record pairs (val/flag)"))
sel = sorted(tight.items(), key=lambda kv: (kv[1]['m'], kv[1]['P']))
for (pg, e), v in sel[:12] + sel[len(sel) // 2 - 6:len(sel) // 2 + 6] + sel[-12:]:
    rec = pages[pg]['recs'][e]
    nat = 69 + 12 * math.log2(48000 / (440 * v['P']))
    print("%d/%03X  %+5d %8d %7.1f %6.1f %+6.0f  %s" % (
        pg, e, v['m'], v['C'], v['P'], nat, v['res'],
        ' '.join('%02x/%02x' % pf for pf in rec['pairs'][:10])))
