#!/usr/bin/env python3
"""Offline test of the +0x080[14:12] decode against an ALREADY-CAPTURED burst log.

Claim under test (from the disassembly of Voice_Build_OutputLevel, 0x0232C7):
  bits[14:12] of +0x080 are either
   (a) a CONSTANT read out of the selected zone record (record[+0x02] bits[6:4]), or
   (b) T[folded_note mod 12] with T[n] = floor(2*(n mod 12)/3), from ROM table 0x00FBE4.
Both are per-recording ROM data reaching the chip.

Prediction that needs no new run: for every selector whose field VARIES with the note,
  (reg080 >> 12) & 7  ==  T[ ((reg400 - 0x80 - C(sel)) >> 8) mod 12 ]
with C from the shipped 1444-entry trim table.
"""
import collections, csv, sys

LOG = sys.argv[1] if len(sys.argv) > 1 else '/tmp/tg-burst.log'
TSV = '/home/fsanches/compartilhado/kn7000_mame/notes/data/kn5000-pitch-trim-table.tsv'

C = {}
NDIST = {}
for r in csv.DictReader(open(TSV), delimiter='\t'):
    C[int(r['sel'], 16)] = int(r['C_modal'])
    NDIST[int(r['sel'], 16)] = int(r['n_distinct'])

T = [ (2*(n % 12))//3 for n in range(128) ]

pending = collections.defaultdict(dict)
bursts = []
for line in open(LOG):
    if not line.startswith('TGB '):
        continue
    f = line.split()
    if len(f) != 4:
        continue
    latch, data = int(f[2], 16), int(f[3], 16)
    ch, reg = latch & 0x3f, latch & 0xffc0
    if reg == 0 and (data & 0xff00) == 0x8100:
        cur = pending.pop(ch, None)
        if cur and 0x40 in cur and 0x400 in cur and 0x80 in cur:
            bursts.append((ch, cur[0x40], cur[0x400], cur[0x80]))
        pending[ch] = {}
        continue
    pending[ch][reg] = data

print(f"{len(bursts)} complete bursts with selector+pitch+level")

per = collections.defaultdict(lambda: collections.defaultdict(set))
for ch, sel, p400, p080 in bursts:
    per[sel][(p400 - 0x80 - C.get(sel, 0)) & 0xFFFF].add((p080 >> 12) & 7)

# classify selectors
const_sel, vary_sel = [], []
for sel, m in per.items():
    fields = set()
    for v in m.values():
        fields |= v
    (const_sel if len(fields) == 1 else vary_sel).append(sel)
print(f"{len(per)} selectors: field CONSTANT for {len(const_sel)}, VARIES with note for {len(vary_sel)}")

ok = bad = skipped = 0
badex = collections.Counter()
for ch, sel, p400, p080 in bursts:
    if sel not in C:
        skipped += 1
        continue
    if sel in const_sel:
        continue
    d = p400 - 0x80 - C[sel]
    if d < 0:
        skipped += 1
        continue
    note = d >> 8
    pred = T[note % 12] if note < 128 else T[(note % 12)]
    obs = (p080 >> 12) & 7
    if pred == obs:
        ok += 1
    else:
        bad += 1
        badex[(sel, pred, obs)] += 1
tot = ok + bad
print(f"\nNOTE-BRANCH GATE (only selectors whose field varies):  {ok}/{tot} match"
      + (f" = {100.0*ok/tot:.1f}%" if tot else ""))
print(f"  skipped {skipped} (selector absent from the table or negative note)")
for (sel, pred, obs), n in badex.most_common(12):
    print(f"   mismatch sel {sel:04X}: predicted {pred} observed {obs}  x{n}"
          f"  (C={C[sel]}, n_distinct={NDIST[sel]})")

# For the CONSTANT selectors, is the constant plausible as a record field?
vals = collections.Counter()
for sel in const_sel:
    f = set()
    for v in per[sel].values():
        f |= v
    vals[list(f)[0]] += 1
print("\nCONSTANT-field selectors, histogram of the 3-bit value:", dict(sorted(vals.items())))

# how many notes did each varying selector show?
nn = [len(per[s]) for s in vary_sel]
if nn:
    print(f"varying selectors saw {min(nn)}..{max(nn)} distinct pitches (median {sorted(nn)[len(nn)//2]})")
