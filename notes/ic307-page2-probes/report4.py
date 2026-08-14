#!/usr/bin/env python3
"""THE K-LAW ORACLE (the one that CAN see a period change).

kn5000_pitch_audit.py section 5: K = C + 0x80 - 3072*log2(period), mod 3072, must be ONE
constant per chip (FINDINGS-kn5000-chunk-root-pitch.md section 4: 92.7% of all 343 single-C
chunks within +-25 cents = +-64 units, uniform null 4.2%).

K depends on log2(P), so ANY period change that is not an exact octave moves K. That is
exactly what the zone-slope oracle cannot see. Applied here to A/B gate 0.5 vs 0.30.
"""
import json, os, math, collections, random
D = os.path.dirname(os.path.abspath(__file__))
DATA = "/home/fsanches/compartilhado/kn7000_mame/notes/data"
rows = json.load(open(os.path.join(D, "periods.json")))
byc = {(r["page"], r["chunk"]): r for r in rows}

sel = {}    # (page, entry) -> (C, n_distinct, key_weight)
for i, line in enumerate(open(os.path.join(DATA, "kn5000-pitch-trim-table.tsv"))):
    if i == 0:
        continue
    f = line.rstrip("\n").split("\t")
    cls, ent, C, nd, kw = int(f[1]), int(f[2], 16), int(f[3]), int(f[4]), int(f[5])
    if (cls >> 2) & 1:
        sel[(cls & 3, ent)] = (C, nd, kw)


def K(c, p_q16):
    if not p_q16:
        return None
    return (c + 128 - 3072 * math.log2(p_q16 / 65536.0)) % 3072


def modal(ks):
    return min(ks, key=lambda a: sum(min(abs(x - a), 3072 - abs(x - a)) for x in ks))


def dev(x, k0):
    e = (x - k0) % 3072
    return e - 3072 if e > 1536 else e


single = [k for k, v in sel.items() if v[1] == 1 and k in byc and not byc[k]["skipped"]]
print(f"single-C referenced IC307 chunks with a period: {len(single)}")

for gate, key in (("0.5 (shipped)", "p5"), ("0.30 (P11)", "p3")):
    ks = {}
    for k in single:
        v = K(sel[k][0], byc[k][key])
        if v is not None:
            ks[k] = v
    k0 = modal(list(ks.values()))
    devs = {k: dev(v, k0) for k, v in ks.items()}
    n = len(devs)
    within = sum(1 for v in devs.values() if abs(v) <= 64)
    med = sorted(abs(v) for v in devs.values())[n // 2]
    print(f"  gate {gate:14s}: n={n}  K0={k0:6.1f}  within +-64u (+-25c): {within} ({100*within/n:.1f}%)"
          f"  median |dev| {med:.1f}u = {med*100/256:.1f} cents")
    if key == "p5":
        base_k0, base_dev = k0, devs
    else:
        cand_k0, cand_dev = k0, devs

# uniform null: a period drawn at random puts K anywhere in [0,3072) -> 128/3072 = 4.2%
print("  uniform null (period unrelated to the chunk): 4.2%")

print("\n=== per-page, shipped gate ===")
for pg in range(4):
    d = [abs(v) for k, v in base_dev.items() if k[0] == pg]
    if d:
        print(f"  page {pg}: n={len(d):3d}  within +-64u: {sum(1 for v in d if v<=64)} "
              f"({100*sum(1 for v in d if v<=64)/len(d):.0f}%)  median {sorted(d)[len(d)//2]:.1f}u")

chg = {tuple(x) for x in json.load(open(os.path.join(D, "changed.json")))}
tst = [k for k in single if k in chg]
print(f"\n=== THE A/B: the {len(tst)} single-C REFERENCED chunks whose period changes at 0.30 ===")
print(f"{'chunk':>10} {'N':>6} {'peak':>6} {'P0.5':>9} {'P0.30':>9} {'dev0.5':>8} {'dev0.30':>8} {'verdict':>9}")
better = worse = same = 0
for k in sorted(tst):
    r = byc[k]
    d5, d3 = base_dev.get(k), cand_dev.get(k)
    if d5 is None or d3 is None:
        continue
    verd = "BETTER" if abs(d3) < abs(d5) - 16 else ("WORSE" if abs(d3) > abs(d5) + 16 else "same")
    better += verd == "BETTER"; worse += verd == "WORSE"; same += verd == "same"
    print(f"  p{k[0]}c{k[1]:<6d} {r['n']:6d} {r['peak']:6.3f} {r['p5']/65536:9.2f} {r['p3']/65536:9.2f}"
          f" {d5:8.1f} {d3:8.1f} {verd:>9}")
print(f"  -> BETTER {better}   WORSE {worse}   unchanged-in-K {same}   (threshold 16u = 6 cents)")
print(f"  in-cluster (|dev|<=64) at 0.5: {sum(1 for k in tst if abs(base_dev[k])<=64)}"
      f"   at 0.30: {sum(1 for k in tst if abs(cand_dev[k])<=64)}")

print("\n=== control 1: chunks the gate does NOT change (the law's own noise floor) ===")
un = [k for k in single if k not in chg]
d = [abs(base_dev[k]) for k in un]
print(f"  n={len(d)}  within +-64u: {sum(1 for v in d if v<=64)} ({100*sum(1 for v in d if v<=64)/len(d):.0f}%)"
      f"  median {sorted(d)[len(d)//2]:.1f}u")

print("\n=== control 2: could this test have PASSED by construction? ===")
rnd = random.Random(3)
fake = []
for k in tst:
    r = byc[k]
    p = rnd.uniform(4, min(2048, max(5, r['n'])))
    fake.append(abs(dev(K(sel[k][0], int(p * 65536)), base_k0)))
print(f"  same chunks with a RANDOM period: within +-64u {sum(1 for v in fake if v<=64)}/{len(fake)}"
      f"  median {sorted(fake)[len(fake)//2]:.1f}u")
print("  => a gate that recovered REAL periods would show the 0.30 column moving INTO the")
print("     cluster; random periods sit at the 4.2% null. Both outcomes were reachable.")
