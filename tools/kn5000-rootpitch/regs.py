#!/usr/bin/env python3
"""Which per-voice register (if any) carries the chunk's ROOT OCTAVE?

For every register 0..31 ask:
  * is it ever written at all?
  * is it a FUNCTION OF THE SELECTOR alone (the property a per-chunk root must have)?
  * does it correlate with the missing octave  m = (C + 0x80 - 3072*log2(P) - K)/3072 ?
NULL for the last: the same test with m permuted across selectors.
"""
import collections, json, math, os, random, sys
sys.path.insert(0, os.path.expanduser('~/compartilhado/kn7000_mame/tools'))
import kn5000_pitch_audit as A

HERE = os.path.dirname(os.path.abspath(__file__))
W = A.trim_table(A.read_sets())
Cmodal = {sel: c.most_common(1)[0][0] for sel, c in W.items()}
gt = {tuple(int(x) for x in k.split(',')): v for k, v in
      json.load(open(os.path.join(HERE, 'gt.json'))).items()}

NAME = {0: '+0x000 ctrl', 1: '+0x040 WAVE', 2: '+0x080', 3: '+0x0C0',
        4: '+0x100 TVF', 5: '+0x140', 6: '+0x180 pan', 7: '+0x1C0',
        8: '+0x400 PITCH', 9: '+0x440', 10: '+0x480', 11: '+0x4C0',
        12: '+0x500', 13: '+0x540', 14: '+0x580', 15: '+0x5C0',
        16: '+0x600', 17: '+0x640', 18: '+0x680', 19: '+0x6C0',
        20: '+0x800 EG0', 21: '+0x840 EG1', 22: '+0x880 EG2', 23: '+0x8C0',
        24: '+0x900', 25: '+0x940', 26: '+0x980', 27: '+0x9C0',
        28: '+0xA00', 29: '+0xA40', 30: '+0xA80', 31: '+0xAC0'}

ev = []
for line in open(os.path.join(HERE, 'kon2.log')):
    p = line.split()
    if p and p[0] == 'KON' and len(p) == 35 and float(p[1]) >= 17.0:
        ev.append((float(p[1]), int(p[2]), [int(x, 16) for x in p[3:]]))
print("note-ons captured with the full register set: %d" % len(ev))
unk = collections.Counter()
for line in open(os.path.join(HERE, 'kon2.log')):
    p = line.split()
    if p and p[0] == 'UNK':
        unk[p[3]] += 1
print("writes to register groups the HLE does not map:", dict(unk) or "NONE")

print("\n%-14s %6s %6s   %s" % ("register", "wrote", "values", "function of the selector?"))
bysel = collections.defaultdict(lambda: collections.defaultdict(set))
for t, ch, R in ev:
    for i, v in enumerate(R):
        bysel[i][R[1]].add(v)
for i in range(32):
    vals = {v for _, _, R in ev for v in [R[i]]}
    if vals == {0}:
        continue
    d = bysel[i]
    single = sum(1 for s, vs in d.items() if len(vs) == 1)
    print("%-14s %6d %6d   %d/%d selectors carry exactly one value (%.0f%%)"
          % (NAME[i], sum(1 for _, _, R in ev if R[i] != 0), len(vals), single, len(d),
             100.0 * single / len(d)))

# ---- correlate each candidate with the missing octave ----------------------------------
print("\n== does any register predict the missing octave m? ==")
sel_m = {}
for sel in {R[1] for _, _, R in ev}:
    cls, ent = sel >> 12, sel & 0xFFF
    if cls in (4, 5, 6, 7) and (cls & 3, ent) in gt:
        g = gt[(cls & 3, ent)]
        if abs(g['res']) <= 64:
            sel_m[sel] = g['m']
print("   %d of the %d selectors the demo plays are on the DUMPED chip with a trusted m"
      % (len(sel_m), len({R[1] for _, _, R in ev})))
if sel_m:
    mc = collections.Counter(sel_m.values())
    print("   NULL (always guess the modal m=%d): %.1f%%"
          % (mc.most_common(1)[0][0], 100.0 * max(mc.values()) / len(sel_m)))
    rng = random.Random(5)
    for i in range(32):
        pairs = {}
        for _, _, R in ev:
            if R[1] in sel_m:
                pairs.setdefault(R[i], collections.Counter())[sel_m[R[1]]] += 1
        if len(pairs) <= 1:
            continue
        n = sum(sum(c.values()) for c in pairs.values())
        acc = sum(c.most_common(1)[0][1] for c in pairs.values()) / n
        # permutation null: shuffle m over selectors, keep the register values
        nn = []
        for _ in range(30):
            ks = list(sel_m); vs = [sel_m[k] for k in ks]; rng.shuffle(vs)
            pm = dict(zip(ks, vs))
            p2 = {}
            for _, _, R in ev:
                if R[1] in sel_m:
                    p2.setdefault(R[i], collections.Counter())[pm[R[1]]] += 1
            nn.append(sum(c.most_common(1)[0][1] for c in p2.values()) / n)
        mu = sum(nn) / len(nn); sd = (sum((x - mu) ** 2 for x in nn) / len(nn)) ** .5
        flag = '  <== ABOVE NULL' if acc > mu + 4 * sd else ''
        print("   %-14s purity %5.1f%%  null %5.1f%% +- %.1f  (%d distinct values)%s"
              % (NAME[i], 100 * acc, 100 * mu, 100 * sd, len(pairs), flag))
