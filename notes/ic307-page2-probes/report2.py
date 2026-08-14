#!/usr/bin/env python3
"""Cross-reference the period-change set against every 'can it be heard' table we hold."""
import json, os, collections
D = os.path.dirname(os.path.abspath(__file__))
DATA = "/home/fsanches/compartilhado/kn7000_mame/notes/data"
rows = json.load(open(os.path.join(D, "periods.json")))
byc = {(r["page"], r["chunk"]): r for r in rows}


def cls_to_page(c):
    return (c >> 2) & 1, c & 3


# --- source A: firmware SET descriptors, per-selector (the pitch-trim census) --------
trim = {}          # (page, chunk) -> key_weight     bank1 only
trim_all = collections.Counter()
for i, line in enumerate(open(os.path.join(DATA, "kn5000-pitch-trim-table.tsv"))):
    if i == 0:
        continue
    f = line.rstrip("\n").split("\t")
    cls, ent, kw = int(f[1]), int(f[2], 16), int(f[5])
    b, p = cls_to_page(cls)
    trim_all[b] += 1
    if b == 1:
        trim[(p, ent)] = trim.get((p, ent), 0) + kw

# --- source B: multisample zone table -----------------------------------------------
zone = collections.Counter()
nsets = 0
for i, line in enumerate(open(os.path.join(DATA, "kn5000-multisample-sets.tsv"))):
    if i == 0:
        hdr = line.rstrip("\n").split("\t")
        zi = hdr.index("zones(lo-hi:class:entry)")
        continue
    f = line.rstrip("\n").split("\t")
    if len(f) <= zi:
        continue
    nsets += 1
    for z in f[zi].split(";"):
        try:
            rng, c, e = z.split(":")
            c, e = int(c), int(e, 16)
        except ValueError:
            continue
        b, p = cls_to_page(c)
        if b == 1:
            zone[(p, e)] += 1

# --- source C: tone-record name table -----------------------------------------------
name = collections.defaultdict(set)
for i, line in enumerate(open(os.path.join(DATA, "kn5000-sample-name-table.tsv"))):
    if i == 0:
        continue
    f = line.rstrip("\n").split("\t")
    nm = f[1].strip()
    for z in f[-1].split(";"):
        try:
            c, e = z.split(":")
            c, e = int(c), int(e, 16)
        except ValueError:
            continue
        b, p = cls_to_page(c)
        if b == 1:
            name[(p, e)].add(nm)

print(f"pitch-trim selectors: bank0(undumped) {trim_all[0]}  bank1(IC307) {trim_all[1]}")
print(f"IC307 chunks referenced: trim {len(trim)}  zone {len(zone)}  nametable {len(name)}")
for pg in range(4):
    tot = sum(1 for r in rows if r["page"] == pg)
    print(f"  page {pg}: {tot:4d} chunks   trim-referenced {sum(1 for k in trim if k[0]==pg):4d}"
          f"   zone-referenced {sum(1 for k in zone if k[0]==pg):4d}"
          f"   name-referenced {sum(1 for k in name if k[0]==pg):4d}")

REF = set(trim) | set(zone) | set(name)
print(f"\nUNION of all three 'referenced' sets on IC307: {len(REF)} of 1495 chunks")

chg = [tuple(x) for x in json.load(open(os.path.join(D, "changed.json")))]
print(f"\n=== the {len(chg)} chunks whose period changes at gate 0.30 ===")
hit = [c for c in chg if c in REF]
print(f"referenced by ANY table: {len(hit)}")
for c in sorted(hit):
    r = byc[c]
    print(f"   p{c[0]}c{c[1]:<4d} N={r['n']:<6d} peak={r['peak']:.3f} P0.30={r['p3']/65536:8.2f} "
          f"N/P={r['n']/(r['p3']/65536):7.3f}  trimKW={trim.get(c,0):5d} zone={zone.get(c,0):3d} "
          f"names={sorted(name.get(c,[]))[:3]}")
for src, s in (("trim", trim), ("zone", zone), ("name", name)):
    print(f"   via {src}: {sum(1 for c in chg if c in s)}")

fb = [(r["page"], r["chunk"]) for r in rows if not r["skipped"] and r["p5"] == (r["n"] << 16)]
print(f"\n=== the {len(fb)} P=N fallback chunks ===")
print(f"referenced by ANY table: {sum(1 for c in fb if c in REF)}")
for pg in range(4):
    f2 = [c for c in fb if c[0] == pg]
    if f2:
        print(f"  page {pg}: {len(f2):4d} fallbacks, {sum(1 for c in f2 if c in REF):4d} referenced"
              f" (trim {sum(1 for c in f2 if c in trim)}, zone {sum(1 for c in f2 if c in zone)},"
              f" name {sum(1 for c in f2 if c in name)})")

z0 = [(r["page"], r["chunk"]) for r in rows if not r["skipped"] and r["p5"] == 0]
print(f"\n=== the {len(z0)} P=0 (aperiodic) chunks: referenced {sum(1 for c in z0 if c in REF)} ===")

# names of the referenced fallbacks, to see WHAT material takes the fallback
print("\n=== named instruments among referenced fallbacks ===")
cnt = collections.Counter()
for c in fb:
    for nm in name.get(c, []):
        cnt[nm] += 1
for nm, k in cnt.most_common(40):
    print(f"   {nm!r} x{k}")
