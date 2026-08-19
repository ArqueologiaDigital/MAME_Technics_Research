import collections, csv, os
src = open('/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/_walk.py').read()
src = src.split("stat = collections.Counter()")[0]
exec(src)
# rebuild set membership
SETS = collections.defaultdict(set)
for i in range(n_sets):
    d = set_base + set_stride * i
    stride = 6 if (img[d] & 0x80) else 4
    ptrA = rel(u32(d + 1)); ptrB = rel(u32(d + 5)); ptrC = rel(u32(ptrA))
    for key in range(128):
        SETS[i].add(u16(ptrB + stride * img[ptrA + 4 + img[ptrC + key]]))
sel2set = collections.defaultdict(set)
for i, s in SETS.items():
    for x in s: sel2set[x].add(i)

per = collections.defaultdict(list)
for sel, p400, p080 in bursts:
    b2s = B2.get(sel)
    if not b2s or any(b & 0x80 for b in b2s): continue
    c = C.get(sel)
    if not c: continue
    per[sel].append(((p400 - 0x80 - c[0]) >> 8, (p080 >> 12) & 7))
best = {}
for sel, rows in per.items():
    sc = sorted(((sum(1 for n, o in rows if T[(n + k) % 12] == o), -abs(k), k) for k in range(-12, 13)), reverse=True)
    best[sel] = (sc[0][2], sc[0][0], len(rows))
for target in (0x507D, 0x5027, 0x5035, 0x5086, 0x303C, 0x0002):
    sets = sel2set.get(target, set())
    print("sel %04X in SETs %s" % (target, sorted(sets)))
    peers = sorted({s for i in sets for s in SETS[i]} & set(best))
    for p in peers:
        k, m, n = best[p]
        print("     peer %04X  k=%+3d  %d/%d" % (p, k, m, n))
