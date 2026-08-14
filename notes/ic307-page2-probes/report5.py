#!/usr/bin/env python3
"""P11 line 4 — everything the heredocs measured, in one reproducible pass.

Run after p11_consequence.py (which writes periods.json + changed.json).

  1. K-LAW A/B (the oracle that CAN see a period change).
     K = C + 0x80 - 3072*log2(P) mod 3072 must be ONE constant per chip
     (tools/kn5000_pitch_audit.py section 5; FINDINGS-kn5000-chunk-root-pitch.md section 4:
     92.7% of 343 single-C chunks within +-25 cents = +-64 units, uniform null 4.2%).
  2. Device-side fallback census, reconciled against TODO-kn5000-pcm-glitch-attribution.md
     section 4 (565 / 522 / 43 / 7).
  3. Playback RATE and LOOP GEOMETRY before/after, at the keys the firmware maps.
  4. Key-weight share of the affected selectors, against a proportional null.
"""
import json, os, math, collections, random, sys
import numpy as np

sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools")
from kn5000_period_oracle import load_rom, page_dir

D = os.path.dirname(os.path.abspath(__file__))
DATA = "/home/fsanches/compartilhado/kn7000_mame/notes/data"
rows = json.load(open(os.path.join(D, "periods.json")))
byc = {(r["page"], r["chunk"]): r for r in rows}
chg = {tuple(x) for x in json.load(open(os.path.join(D, "changed.json")))}
rom = load_rom()
pages = {p: page_dir(rom, p) for p in range(4)}

# ---------------------------------------------------------------- firmware selector census
sel = {}                                    # (page, entry) -> (C, n_distinct, key_weight)
for i, line in enumerate(open(os.path.join(DATA, "kn5000-pitch-trim-table.tsv"))):
    if i == 0:
        continue
    f = line.rstrip("\n").split("\t")
    cls, ent = int(f[1]), int(f[2], 16)
    if (cls >> 2) & 1:
        sel[(cls & 3, ent)] = (int(f[3]), int(f[4]), int(f[5]))

names = collections.defaultdict(set)
for i, line in enumerate(open(os.path.join(DATA, "kn5000-sample-name-table.tsv"))):
    if i == 0:
        continue
    f = line.rstrip("\n").split("\t")
    for z in f[-1].split(";"):
        try:
            c, e = z.split(":")
            c, e = int(c), int(e, 16)
        except ValueError:
            continue
        if (c >> 2) & 1:
            names[(c & 3, e)].add(f[1].strip())

zkeys = collections.defaultdict(list)
for i, line in enumerate(open(os.path.join(DATA, "kn5000-multisample-sets.tsv"))):
    f = line.rstrip("\n").split("\t")
    if i == 0:
        zi = f.index("zones(lo-hi:class:entry)")
        continue
    if len(f) <= zi:
        continue
    for z in f[zi].split(";"):
        try:
            rng, c, e = z.split(":")
            lo, hi = (int(v) for v in rng.split("-"))
            c, e = int(c), int(e, 16)
        except ValueError:
            continue
        if (c >> 2) & 1:
            zkeys[(c & 3, e)].append((lo, hi))

# ---------------------------------------------------------------------------- 1. K-LAW A/B
def K(c, p_q16):
    return None if not p_q16 else (c + 128 - 3072 * math.log2(p_q16 / 65536.0)) % 3072


def modal(ks):
    return min(ks, key=lambda a: sum(min(abs(x - a), 3072 - abs(x - a)) for x in ks))


def dv(x, k0):
    e = (x - k0) % 3072
    return e - 3072 if e > 1536 else e


single = [k for k, v in sel.items() if v[1] == 1 and k in byc and not byc[k]["skipped"]]
k5 = {k: K(sel[k][0], byc[k]["p5"]) for k in single}
k3 = {k: K(sel[k][0], byc[k]["p3"]) for k in single}
K0 = modal([v for v in k5.values() if v is not None])
d5 = {k: dv(v, K0) for k, v in k5.items() if v is not None}
d3 = {k: dv(v, K0) for k, v in k3.items() if v is not None}
print("=== 1. K-LAW: K = C + 0x80 - 3072*log2(P) mod 3072, one constant per chip ===")
print(f"  single-C referenced chunks: {len(single)}   K0 = {K0:.1f}   uniform null 4.2%")
common = [k for k in single if k in d5 and k in d3]
for lbl, d in (("shipped 0.5", d5), ("P11's 0.30", d3)):
    a = [abs(d[k]) for k in common]
    print(f"  gate {lbl:12s} (like-for-like, n={len(a)}): within +-64u "
          f"{sum(1 for v in a if v <= 64)} ({100 * sum(1 for v in a if v <= 64) / len(a):.1f}%)"
          f"   median |dev| {sorted(a)[len(a) // 2]:.1f}u")
for pg in range(4):
    for lbl, s in ((f"page {pg} accepted@0.5",
                    [k for k in single if k[0] == pg and k in d5 and byc[k]["b5"] == "accept"]),
                   (f"page {pg} P=N fallback",
                    [k for k in single if k[0] == pg and k in d5
                     and byc[k]["p5"] == (byc[k]["n"] << 16)])):
        a = [abs(d5[k]) for k in s]
        if a:
            print(f"    {lbl:22s} n={len(a):3d}  in-cluster {sum(1 for v in a if v <= 64):3d}"
                  f" ({100 * sum(1 for v in a if v <= 64) / len(a):3.0f}%)  median {sorted(a)[len(a) // 2]:7.1f}u")
tst = [k for k in single if k in chg]
print(f"  THE A/B -- the {len(tst)} single-C referenced chunks the gate changes:")
print(f"    in-cluster at 0.5: {sum(1 for k in tst if k in d5 and abs(d5[k]) <= 64)}"
      f"   at 0.30: {sum(1 for k in tst if k in d3 and abs(d3[k]) <= 64)}")
rnd = random.Random(3)
fake = [abs(dv(K(sel[k][0], int(rnd.uniform(4, min(2048, max(5, byc[k]['n']))) * 65536)), K0))
        for k in tst]
print(f"    same chunks with a RANDOM period (control): {sum(1 for v in fake if v <= 64)}/{len(fake)}")
print("    => both outcomes were reachable: a gate recovering REAL periods would move the")
print("       0.30 column INTO the cluster, as the accepted-period rows above do.")

# ------------------------------------------------------- 2. device-side fallback census
print("\n=== 2. device-side P=N census (detect_period returns samples<<16 for samples<32 too) ===")
dev_fb = []
for pg, v in pages.items():
    for i, (st, ns) in enumerate(v):
        r = byc[(pg, i)]
        if r["skipped"] or r["p5"] == (ns << 16):
            dev_fb.append((pg, i, ns, st))
print(f"  fallbacks {len(dev_fb)} (note: 565)   N<=256 {sum(1 for a in dev_fb if a[2] <= 256)} (522)"
      f"   N>256 {sum(1 for a in dev_fb if a[2] > 256)} (43)")


def zcr(st, ns):
    n = min(ns, 4096)
    x = np.frombuffer(rom, dtype="<i2", count=n, offset=st).astype(np.float64)
    x = x - x.mean()
    return float(np.mean(np.diff(np.signbit(x)) != 0)) if n > 1 else 0.0


big = [a for a in dev_fb if a[2] > 256]
tonal = [a for a in big if zcr(a[3], a[2]) < 0.10]
print(f"  of the {len(big)} long fallbacks: tonal (zcr<0.10) {len(tonal)} (7);"
      f"  referenced {sum(1 for a in big if (a[0], a[1]) in sel)};"
      f"  tonal AND referenced {sum(1 for a in tonal if (a[0], a[1]) in sel)}")
for a in tonal:
    k = (a[0], a[1])
    print(f"    p{k[0]}c{k[1]:<5d} N={a[2]:<6d} zcr={zcr(a[3], a[2]):.3f} peak={byc[k]['peak']:.3f}"
          f" ref={'yes' if k in sel else 'NO ':3s} changed={'YES' if byc[k]['p5'] != byc[k]['p3'] else 'no'}"
          f" names={sorted(names.get(k, []))[:2]}")

# ------------------------------------------------- 3. playback rate + loop geometry A/B
def loop_len(N, P):
    if P == 0 or N == 0:
        return N if N > 0 else 0
    if N <= 2 * P:
        return max(P, (N // P) * P if P <= N else N)
    cap = min(4096, N // 2)
    k = max(1, min(cap // P, (N * 2 // 5) // P))
    return k * P


print("\n=== 3. what a listener gets: rate at the mapped zone centre, and the loop ===")
print(f"{'chunk':>9} {'N':>6} {'keys':>8} {'rate0.5':>8} {'rate0.30':>9} {'loop0.5':>8} {'loop0.30':>9}  name")
for k in sorted(c for c in chg if c in zkeys):
    r = byc[k]
    lo = min(a for a, b in zkeys[k]); hi = max(b for a, b in zkeys[k])
    f = 440 * 2 ** (((lo + hi) / 2 - 69) / 12)
    s5 = 1.0 if r["p5"] == 0 else max(1.0, f * (r["p5"] / 65536) / 48000)
    s3 = 1.0 if r["p3"] == 0 else max(1.0, f * (r["p3"] / 65536) / 48000)
    l5, l3 = loop_len(r["n"], r["p5"] >> 16), loop_len(r["n"], r["p3"] >> 16)
    print(f"  p{k[0]}c{k[1]:<5d} {r['n']:6d} {lo:3d}-{hi:3d} {s5:8.3f} {s3:9.3f}"
          f" {l5 / 48:7.1f}ms {l3 / 48:8.1f}ms  {','.join(sorted(names.get(k, []))[:2])}")
print("  control: P=N and P=0 give the SAME loop (start 0, len N) -- bounding the fallback")
print("  changes only the RATE, never the loop:",
      [(N, loop_len(N, N), loop_len(N, 0)) for N in (352, 1112, 1496)])

# ------------------------------------------------------------------ 4. key-weight share
print("\n=== 4. share of the firmware's key slots ===")
tot = sum(v[2] for v in sel.values())
fb = [k for k in sel if k in byc and not byc[k]["skipped"] and byc[k]["p5"] == (byc[k]["n"] << 16)]
z0 = [k for k in sel if k in byc and not byc[k]["skipped"] and byc[k]["p5"] == 0]
ch = [k for k in sel if k in chg]
kw = lambda s: sum(sel[k][2] for k in s)
print(f"  bank-1 selectors {len(sel)}, total key_weight {tot}")
for lbl, s in (("P=N fallback", fb), ("P=0 aperiodic", z0), ("CHANGED at 0.30", ch)):
    print(f"    {lbl:16s}: {len(s):3d} selectors ({100 * len(s) / len(sel):4.1f}%)"
          f"  key_weight {kw(s):6d} ({100 * kw(s) / tot:4.1f}%)")
print(f"  null: a proportional subset of {len(ch)}/465 selectors carries {100 * len(ch) / 465:.1f}%")
