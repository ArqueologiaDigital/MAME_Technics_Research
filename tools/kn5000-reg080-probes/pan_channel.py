import collections, csv, os
src = open('/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/_walk.py').read()
src = src.split("pending = collections.defaultdict(dict)")[0]
exec(src)
pending = collections.defaultdict(dict); bursts = []
for line in open('/tmp/tg-burst.log'):
    if not line.startswith('TGB '): continue
    f = line.split()
    if len(f) != 4: continue
    latch, data = int(f[2],16), int(f[3],16)
    ch, reg = latch & 0x3f, latch & 0xffc0
    if reg == 0 and (data & 0xff00) == 0x8100:
        cur = pending.pop(ch, None)
        if cur and 0x40 in cur and 0x400 in cur and 0x80 in cur:
            bursts.append((ch, cur[0x40], cur[0x400], cur[0x80]))
        pending[ch] = {}
        continue
    pending[ch][reg] = data
per = collections.defaultdict(list)
for ch, sel, p400, p080 in bursts:
    b2s = B2.get(sel)
    if not b2s or any(b & 0x80 for b in b2s): continue
    c = C.get(sel)
    if not c: continue
    per[(sel, ch)].append((((p400-0x80-c[0])>>8), (p080>>12)&7))
bysel = collections.defaultdict(dict)
for (sel, ch), rows in per.items():
    sc = sorted(((sum(1 for n,o in rows if T[(n+k)%12]==o), -abs(k), k) for k in range(-12,13)), reverse=True)
    bysel[sel][ch] = (sc[0][2], sc[0][0], len(rows))
print("selectors seen on 2+ voice channels, with per-channel best offset k:")
for sel in sorted(bysel):
    if len(bysel[sel]) < 2: continue
    ks = {v[0] for v in bysel[sel].values() if v[2] >= 3}
    tag = "SAME k" if len(ks) <= 1 else "DIFFERENT k -> per-part term"
    print("  %04X  %s   %s" % (sel, tag,
          " ".join("ch%02d:k%+d(%d/%d)" % (c, v[0], v[1], v[2]) for c, v in sorted(bysel[sel].items()))))
