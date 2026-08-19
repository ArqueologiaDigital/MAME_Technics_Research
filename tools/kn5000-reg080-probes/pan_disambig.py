import collections, csv, os
src = open('/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/_walk.py').read()
src = src.split("stat = collections.Counter()")[0]
exec(src)
ALL = {}
for r in csv.DictReader(open('/home/fsanches/compartilhado/kn7000_mame/notes/data/kn5000-pitch-trim-table.tsv'), delimiter='\t'):
    ALL[int(r['sel'],16)] = [int(x.split(':')[0]) for x in r['all_C'].split(';')]
amb = [s for s in ALL if len(ALL[s]) > 1]
print("ambiguous selectors in table: %d; seen in capture: %d" % (len(amb), len([s for s in amb if any(b[0]==s for b in bursts)])))
res = collections.Counter()
for sel in sorted({b[0] for b in bursts} & set(amb)):
    b2s = B2.get(sel)
    if not b2s or any(b & 0x80 for b in b2s):
        res['override-branch(no help)'] += 1; continue
    cands = ALL[sel]
    rows = [(p400, (p080>>12)&7) for s,p400,p080 in bursts if s == sel]
    ok = [c for c in cands if all(T[(((p400-0x80-c)>>8) % 12)] == o for p400,o in rows)]
    res['resolved to 1' if len(ok)==1 else ('all %d survive' % len(ok) if ok else 'none survive')] += 1
    print("  %04X  %3d bursts  candidates %s -> survivors %s" % (sel, len(rows), cands, ok))
print(dict(res))
