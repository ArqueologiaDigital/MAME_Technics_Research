#!/usr/bin/env python3
"""ROM-side PREDICTION of +0x080[14:12] vs what the chip actually received.

Extends tools/kn5000-pitch-probes/kn5000_walk_set_descriptors.py to also collect the zone
record's byte +0x02. Voice_Build_OutputLevel says:
    bit7 set  -> field is the CONSTANT (rec[+2] >> 4) & 7
    bit7 clear-> field is T[folded note mod 12]
So from the ROM alone we can predict, per selector, BOTH the branch and (in the constant case)
the exact 3-bit value the chip must receive. Then we check it against /tmp/tg-burst.log.
"""
import collections, csv, os, sys
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

allb = collections.Counter()
for c in B2.values():
    allb.update(c)
print("zone records reached: %d selectors; rec[+2] value histogram: %s"
      % (len(B2), {('%02X' % k): v for k, v in sorted(allb.items())}))
print("low nibble nonzero: %d of %d" % (sum(v for k, v in allb.items() if k & 0x0F), sum(allb.values())))

# --- bus side ---
pending = collections.defaultdict(dict); bursts = []
for line in open('/tmp/tg-burst.log'):
    if not line.startswith('TGB '): continue
    f = line.split()
    if len(f) != 4: continue
    latch, data = int(f[2], 16), int(f[3], 16)
    ch, reg = latch & 0x3f, latch & 0xffc0
    if reg == 0 and (data & 0xff00) == 0x8100:
        cur = pending.pop(ch, None)
        if cur and 0x40 in cur and 0x400 in cur and 0x80 in cur:
            bursts.append((cur[0x40], cur[0x400], cur[0x80]))
        pending[ch] = {}
        continue
    pending[ch][reg] = data

obs = collections.defaultdict(lambda: collections.defaultdict(set))
for sel, p400, p080 in bursts:
    obs[sel][p400].add((p080 >> 12) & 7)

hit = miss = nopred = 0
rows = []
for sel in sorted(obs):
    fields = set()
    for v in obs[sel].values(): fields |= v
    varies = len(fields) > 1
    if sel not in B2:
        nopred += 1; continue
    b2s = B2[sel]
    ovr = {b for b in b2s if b & 0x80}
    if len(set((b >> 4) & 7 for b in b2s)) == 1 and all(b & 0x80 for b in b2s):
        pred_branch, pred_val = 'const', ((list(b2s)[0] >> 4) & 7)
    elif not ovr:
        pred_branch, pred_val = 'note', None
    else:
        pred_branch, pred_val = 'mixed', None
    if pred_branch == 'const':
        okc = (not varies) and (list(fields)[0] == pred_val)
        rows.append((sel, 'const', pred_val, sorted(fields), okc))
        hit += okc; miss += (not okc)
    elif pred_branch == 'note':
        okn = varies
        rows.append((sel, 'note', None, sorted(fields), okn))
        hit += okn; miss += (not okn)
    else:
        rows.append((sel, 'mixed', None, sorted(fields), None))

print("\nper-selector ROM prediction vs bus:  %d agree, %d disagree, %d mixed-record, %d not reached by walker"
      % (hit, miss, sum(1 for r in rows if r[1] == 'mixed'), nopred))
for sel, br, pv, fs, ok in rows:
    if ok is False or br == 'mixed':
        print("   %04X pred=%-5s val=%s observed=%s" % (sel, br, pv, fs))
