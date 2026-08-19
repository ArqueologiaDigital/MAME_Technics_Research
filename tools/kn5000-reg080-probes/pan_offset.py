import collections, csv, os, re
src = open('/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/_walk.py').read()
src = src.split("stat = collections.Counter()")[0]
exec(src)
# per note-branch selector: best whole-semitone offset k
per = collections.defaultdict(list)
for sel, p400, p080 in bursts:
    b2s = B2.get(sel)
    if not b2s or any(b & 0x80 for b in b2s): continue
    c = C.get(sel)
    if not c: continue
    d = p400 - 0x80 - c[0]
    per[sel].append((d, (p080 >> 12) & 7, c[1]))
print("sel  nd   n   k=0   best_k  best   frac_lowbyte0")
for sel in sorted(per):
    rows = per[sel]
    sc = []
    for k in range(-12, 13):
        sc.append((sum(1 for d, o, _ in rows if T[(((d >> 8) + k) % 12)] == o), k))
    sc.sort(key=lambda x: (-x[0], abs(x[1])))
    base = sum(1 for d, o, _ in rows if T[((d >> 8) % 12)] == o)
    lb0 = sum(1 for d, o, _ in rows if (d & 0xFF) == 0) / len(rows)
    if base < len(rows):
        print("%04X  %s  %4d  %4d   k=%+3d %4d   %.2f" % (sel, rows[0][2], len(rows), base, sc[0][1], sc[0][0], lb0))
