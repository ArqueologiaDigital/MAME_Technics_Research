import collections, csv, os
D = os.path.expanduser('~/compartilhado/kn7000-emulator/roms/kn5000')
ev = open(os.path.join(D, 'kn5000_table_data_rom_even.ic3'), 'rb').read()
od = open(os.path.join(D, 'kn5000_table_data_rom_odd.ic1'), 'rb').read()
img = bytearray(0x200000)
for i in range(0, len(ev), 2):
    j = (i // 2) * 4
    img[j:j+2] = ev[i:i+2]; img[j+2:j+4] = od[i:i+2]
ROOT = 0x30000
u16 = lambda o: img[o] | img[o+1] << 8
u32 = lambda o: u16(o) | u16(o+2) << 16
rel = lambda r: ROOT + r
set_base = rel(u32(ROOT + 0x30)); set_stride = u16(ROOT + 0xEC)
a2 = [rel(u32(ROOT + o)) for o in (0x24, 0x28, 0x2C)]
n_sets = (min(a2) - set_base) // set_stride
B2 = collections.defaultdict(collections.Counter)
for i in range(n_sets):
    d = set_base + set_stride * i
    stride = 6 if (img[d] & 0x80) else 4
    ptrA = rel(u32(d + 1)); ptrB = rel(u32(d + 5)); ptrC = rel(u32(ptrA))
    for key in range(128):
        rec = ptrB + stride * img[ptrA + 4 + img[ptrC + key]]
        B2[u16(rec)][img[rec + 2]] += 1

C = {}
for r in csv.DictReader(open('/home/fsanches/compartilhado/kn7000_mame/notes/data/kn5000-pitch-trim-table.tsv'), delimiter='\t'):
    C[int(r['sel'],16)] = (int(r['C_modal']), int(r['n_distinct']))
T = [(2*(n % 12))//3 for n in range(12)]

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
            bursts.append((cur[0x40], cur[0x400], cur[0x80]))
        pending[ch] = {}
        continue
    pending[ch][reg] = data

stat = collections.Counter(); bad = collections.Counter(); badsel = collections.Counter()
for sel, p400, p080 in bursts:
    obs = (p080 >> 12) & 7
    b2s = B2.get(sel)
    if not b2s: stat['no-record'] += 1; continue
    ovr = all(b & 0x80 for b in b2s); noovr = all(not (b & 0x80) for b in b2s)
    if ovr:
        vals = {(b >> 4) & 7 for b in b2s}
        if len(vals) == 1:
            stat['const-tested'] += 1
            if list(vals)[0] == obs: stat['const-OK'] += 1
            else: stat['const-BAD'] += 1; badsel[('const', sel)] += 1
        else:
            stat['const-ambig-record'] += 1
    elif noovr:
        c, nd = C.get(sel, (None, None))
        if c is None: stat['no-C'] += 1; continue
        d = p400 - 0x80 - c
        if d < 0: stat['neg'] += 1; continue
        stat['note-tested'] += 1
        if T[(d >> 8) % 12] == obs: stat['note-OK'] += 1
        else:
            stat['note-BAD'] += 1; badsel[('note', sel)] += 1
            bad[(sel, nd)] += 1
    else:
        stat['mixed-record'] += 1
print(len(bursts), "bursts")
for k in sorted(stat): print("  %-20s %d" % (k, stat[k]))
if stat['const-tested']: print("CONST branch: %.1f%%" % (100.0*stat['const-OK']/stat['const-tested']))
if stat['note-tested']: print("NOTE  branch: %.1f%%" % (100.0*stat['note-OK']/stat['note-tested']))
print("failing note-branch selectors (sel, n_distinct_C, count):")
for (sel, nd), n in bad.most_common(20): print("   %04X nd=%s x%d" % (sel, nd, n))
