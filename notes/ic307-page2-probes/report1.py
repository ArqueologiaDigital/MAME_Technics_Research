#!/usr/bin/env python3
import json, os, sys, collections
D = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(D, "periods.json")))
DATA = "/home/fsanches/compartilhado/kn7000_mame/notes/data"

print("=== per-page totals, gate 0.5 (shipped) ===")
for pg in range(4):
    rs = [r for r in rows if r["page"] == pg]
    fb = [r for r in rs if not r["skipped"] and r["p5"] == (r["n"] << 16)]
    zero = [r for r in rs if not r["skipped"] and r["p5"] == 0]
    sk = [r for r in rs if r["skipped"]]
    br = collections.Counter(r["b5"] for r in rs if not r["skipped"])
    print(f"page {pg}: {len(rs):4d} chunks  skipped(n<32) {len(sk):3d}  P=N {len(fb):4d}  P=0 {len(zero):3d}  branches {dict(br)}")

print()
print("=== branch of the P=N fallback, per page ===")
for pg in range(4):
    rs = [r for r in rows if r["page"] == pg and not r["skipped"] and r["p5"] == (r["n"] << 16)]
    br = collections.Counter(r["b5"] for r in rs)
    print(f"page {pg}: {len(rs):4d} fallbacks -> {dict(br)}")

print()
print("=== chunks whose period CHANGES when gate 0.5 -> 0.30 ===")
chg = [r for r in rows if not r["skipped"] and r["p5"] != r["p3"]]
per = collections.Counter(r["page"] for r in chg)
print(f"total {len(chg)}  per page {dict(sorted(per.items()))}")
for pg in range(4):
    c = [r for r in chg if r["page"] == pg]
    if not c:
        continue
    ns = [r["n"] for r in c]
    peaks = [r["peak"] for r in c]
    print(f"  page {pg}: {len(c):3d}  N range {min(ns)}..{max(ns)}  peak range {min(peaks):.3f}..{max(peaks):.3f}")
    print("    " + " ".join(f"c{r['chunk']}(N={r['n']},pk={r['peak']:.2f},P={r['p3']/65536:.1f})" for r in c[:12]))

json.dump([[r["page"], r["chunk"]] for r in chg], open(os.path.join(D, "changed.json"), "w"))

print()
print("=== size distribution of P=N fallbacks, page 2 ===")
rs = [r for r in rows if r["page"] == 2 and not r["skipped"] and r["p5"] == (r["n"] << 16)]
h = collections.Counter(r["n"] for r in rs)
print("distinct N values:", len(h))
for n, c in sorted(h.items())[:20]:
    print(f"   N={n:6d} x{c}")
print("  ... largest:", sorted(h.items())[-5:])

print()
print("=== page 2 overall size histogram (all chunks) ===")
rs = [r for r in rows if r["page"] == 2]
h = collections.Counter(r["n"] for r in rs)
tot = len(rs)
small = sum(c for n, c in h.items() if n <= 128)
print(f"page2 {tot} chunks; N<=64: {sum(c for n,c in h.items() if n<=64)}; N<=128: {small}; N<=2048: {sum(c for n,c in h.items() if n<=2048)}; N>2048: {sum(c for n,c in h.items() if n>2048)}")
print("  most common N:", h.most_common(12))
