#!/usr/bin/env python3
"""(a) what the 49 referenced page-2 chunks are, (b) is an accepted 0.30 period real?"""
import json, os, collections, math, random
D = os.path.dirname(os.path.abspath(__file__))
DATA = "/home/fsanches/compartilhado/kn7000_mame/notes/data"
rows = json.load(open(os.path.join(D, "periods.json")))
byc = {(r["page"], r["chunk"]): r for r in rows}

trim = {}
for i, line in enumerate(open(os.path.join(DATA, "kn5000-pitch-trim-table.tsv"))):
    if i == 0:
        continue
    f = line.rstrip("\n").split("\t")
    cls, ent, kw, nd = int(f[1]), int(f[2], 16), int(f[5]), int(f[4])
    if (cls >> 2) & 1:
        trim[(cls & 3, ent)] = (kw, nd)

print("=== the 49 page-2 (class 6) chunks the firmware's SET descriptors actually select ===")
p2 = sorted(k for k in trim if k[0] == 2)
hdr = f"{'entry':>6} {'N':>6} {'branch':>12} {'P(0.5)':>9} {'P(0.30)':>9} {'keyW':>6}"
print(hdr)
for k in p2:
    r = byc.get(k)
    if r is None:
        print(f"{k[1]:6d}  (not in directory)")
        continue
    p5 = "n/a" if r["skipped"] else f"{r['p5']/65536:.2f}"
    p3 = "n/a" if r["skipped"] else f"{r['p3']/65536:.2f}"
    print(f"{k[1]:6d} {r['n']:6d} {(r['b5'] if not r['skipped'] else 'N<32'):>12} {p5:>9} {p3:>9} {trim[k][0]:6d}")

print()
print("=== N/P integrality test on the 94 changed chunks (is the 0.30 period real?) ===")
chg = [tuple(x) for x in json.load(open(os.path.join(D, "changed.json")))]


def dev(n, p):
    q = n / p
    return abs(q - round(q)) / 1.0


real, ctrl = [], []
rnd = random.Random(7)
ns = [byc[c]["n"] for c in chg]
for c in chg:
    r = byc[c]
    p = r["p3"] / 65536.0
    real.append(dev(r["n"], p))
# NULL: same periods, but paired with a DIFFERENT chunk's length (a period that is truly a
# divisor of its own recording should not divide an unrelated one).
for i, c in enumerate(chg):
    r = byc[c]
    p = r["p3"] / 65536.0
    ctrl.append(dev(ns[(i + 37) % len(ns)], p))
med = lambda a: sorted(a)[len(a) // 2]
close = lambda a, t: sum(1 for v in a if v <= t)
print(f"  measured : median |N/P - round(N/P)| = {med(real):.4f};  <=0.05: {close(real,0.05)}/{len(real)}")
print(f"  shuffled : median |N/P - round(N/P)| = {med(ctrl):.4f};  <=0.05: {close(ctrl,0.05)}/{len(ctrl)}")
print("  (a genuine sub-multiple period divides its OWN recording length; the null pairs it")
print("   with another chunk's length. Refutation: measured >> control would kill the claim.)")

print()
print("=== same test on the 465 REFERENCED chunks whose period is ACCEPTED at 0.5 ===")
acc = [k for k in trim if byc.get(k) and not byc[k]["skipped"] and byc[k]["b5"] == "accept"]
a_real = [dev(byc[k]["n"], byc[k]["p5"] / 65536.0) for k in acc]
a_ns = [byc[k]["n"] for k in acc]
a_ctrl = [dev(a_ns[(i + 37) % len(acc)], byc[k]["p5"] / 65536.0) for i, k in enumerate(acc)]
print(f"  accepted@0.5, referenced: {len(acc)} chunks  median {med(a_real):.4f}  <=0.05: {close(a_real,0.05)}")
print(f"  null                    : median {med(a_ctrl):.4f}  <=0.05: {close(a_ctrl,0.05)}")

print()
print("=== P=N fallbacks by length, per page (is 'the whole thing is one cycle' plausible?) ===")
for pg in range(4):
    fb = [r for r in rows if r["page"] == pg and not r["skipped"] and r["p5"] == (r["n"] << 16)]
    if not fb:
        continue
    le = sum(1 for r in fb if r["n"] <= 128)
    mid = sum(1 for r in fb if 128 < r["n"] <= 512)
    big = sum(1 for r in fb if r["n"] > 512)
    print(f"  page {pg}: {len(fb):4d} fallbacks  N<=128: {le:4d}   129..512: {mid:3d}   >512: {big:3d}")

print()
print("=== how many of the 543 fallbacks are BOTH referenced AND longer than 512 samples ===")
bad = [(r["page"], r["chunk"]) for r in rows if not r["skipped"] and r["p5"] == (r["n"] << 16)
       and r["n"] > 512 and (r["page"], r["chunk"]) in trim]
print(f"  {len(bad)}: {bad}")
for c in bad:
    r = byc[c]
    print(f"    p{c[0]}c{c[1]} N={r['n']} peak={r['peak']:.3f} keyW={trim[c][0]}  P0.30={r['p3']/65536:.2f}"
          f"  changed={'YES' if r['p5']!=r['p3'] else 'no'}")
