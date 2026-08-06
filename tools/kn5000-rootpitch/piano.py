#!/usr/bin/env python3
"""The acoustic-piano page (class 7 = page 3) in full: 57 chunks, one chromatic
multisample, C known exactly from the firmware, period measured.  If a per-chunk root
pitch lives in the parameter record, this is the page where it must be visible."""
import json, math, os, sys
sys.path.insert(0, os.path.expanduser('~/compartilhado/kn7000_mame/tools'))
import kn5000_pitch_audit as A
import records as R           # re-uses its parse + caches

d = R.d
pg = R.pages[3]
W = A.trim_table(A.read_sets())
print("page 3: %d chunks" % pg['count'])
print("%-4s %-6s %-9s %8s %8s %7s %6s %5s   %s" %
      ("ent", "wave", "rom", "samples", "C", "P", "nat", "m", "record"))
for e in range(pg['count']):
    sel = (7 << 12) | e
    cnt = W.get(sel)
    C = list(cnt)[0] if cnt and len(cnt) == 1 else None
    P = R.period(3, e)
    ns = pg['samples'][e]
    nat = 69 + 12 * math.log2(48000 / (440 * P)) if P else 0
    m = res = None
    if C is not None and P and abs(P - ns) > 1e-9:
        x = C + 128 - 3072 * math.log2(P) - R.K_GLOBAL
        m = round(x / 3072.0); res = x - 3072 * m
    rec = pg['recs'][e]
    print("%-4X %-6X %08X %8d %8s %7.1f %6.1f %5s %+5s   %s" % (
        e, pg['wave'][e], pg['start'][e], ns,
        C if C is not None else (';'.join(str(k) for k in cnt) if cnt else '-'),
        P, nat, m if m is not None else '-', ('%.0f' % res) if res is not None else '-',
        ' '.join('%02x/%02x' % pf for pf in rec['pairs'])))
