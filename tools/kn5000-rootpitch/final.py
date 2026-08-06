#!/usr/bin/env python3
"""Non-circular statistics for the octave-lattice claim, and the one remaining
chip-legal way to recover the missing octave: "play the recording at the rate nearest
its own native rate"."""
import collections, json, math, os, random, sys
sys.path.insert(0, os.path.expanduser('~/compartilhado/kn7000_mame/tools'))
import kn5000_pitch_audit as A
import records as R

HERE = os.path.dirname(os.path.abspath(__file__))
sets = A.read_sets()
W = A.trim_table(sets)
SR = 48000.0

# ---- 1. the octave lattice, over ALL chunks (no selection on the residual) --------------
rows = []
for sel, cnt in W.items():
    cls, ent = sel >> 12, sel & 0xFFF
    if cls not in (4, 5, 6, 7) or len(cnt) != 1:
        continue
    pg = R.pages[cls & 3]
    if not pg or ent >= pg['count']:
        continue
    P = R.period(cls & 3, ent); ns = pg['samples'][ent]
    if not P or abs(P - ns) < 1e-9 or ns < 64:
        continue
    C = list(cnt)[0]
    nat = 69 + 12 * math.log2(SR / (440 * P))
    rows.append(dict(cls=cls, ent=ent, C=C, P=P, nat=nat, ROOT=256 * nat + 128 + C,
                     w=sum(cnt.values())))
print("== 1. IS THE PER-CHUNK ROOT ON ONE GLOBAL OCTAVE LATTICE? ==")
print("   population: ALL %d single-C selectors on the dumped chip with a measurable "
      "period (NO selection on the answer)" % len(rows))
mods = [r['ROOT'] % 3072 for r in rows]
# circular median
ctr = min(mods, key=lambda a: sum(min(abs(x - a), 3072 - abs(x - a)) for x in mods))
dev = [((x - ctr + 1536) % 3072) - 1536 for x in mods]
ad = sorted(abs(x) for x in dev)
for t in (32, 64, 128, 256):
    n = sum(1 for x in ad if x <= t)
    print("   within +-%3d units (%5.1f cents) of the lattice: %3d/%3d = %5.1f%%   "
          "(uniform-null expectation %.1f%%)"
          % (t, t * 100 / 256, n, len(rows), 100 * n / len(rows), 100 * 2 * t / 3072))
print("   lattice phase = %d units = %.2f semitone;  median |dev| %.0f units = %.1f cents"
      % (ctr, ctr / 256, ad[len(ad) // 2], ad[len(ad) // 2] * 100 / 256))
for cls in (4, 5, 6, 7):
    s = [r for r in rows if r['cls'] == cls]
    dd = sorted(abs(((r['ROOT'] % 3072) - ctr + 1536) % 3072 - 1536) for r in s)
    print("      class %d: n=%3d  within +-64: %5.1f%%  median |dev| %.0f units"
          % (cls, len(s), 100 * sum(1 for x in dd if x <= 64) / len(s), dd[len(dd) // 2]))
oct_hist = collections.Counter(round((r['ROOT'] - ctr) / 3072) for r in rows)
print("   octave index (ROOT-phase)/3072: %s   => %d distinct values = %.1f bits"
      % (dict(sorted(oct_hist.items())), len(oct_hist), math.log2(len(oct_hist))))

# ---- 2. can the octave be chosen by "rate nearest native"? -----------------------------
print("\n== 2. CHIP-LEGAL OCTAVE RULE: is the true rate always the one nearest native? ==")
ROOT = {(r['cls'], r['ent']): r for r in rows}
lg = []
for sid, st, fl, kmin, kmax, root, base, zones in sets:
    for lo, hi, cls, ent, C in zones:
        k = (cls, ent)
        if k not in ROOT or len({c for c in W[(cls << 12) | ent]}) != 1:
            continue
        nat = ROOT[k]['nat']
        for key in range(lo, min(hi, 127) + 1):
            lg.append((key - nat) / 12.0)          # log2 of the playback rate
lg.sort()
print("   %d (zone x key) slots.  log2(playback rate) distribution:" % len(lg))
print("      p1 %+.2f  p5 %+.2f  p25 %+.2f  median %+.2f  p75 %+.2f  p95 %+.2f  p99 %+.2f octaves"
      % tuple(lg[int(len(lg) * q)] for q in (.01, .05, .25, .50, .75, .95, .99)))
best = None
for c in [x / 20.0 for x in range(-60, 61)]:
    ok = sum(1 for x in lg if abs(x - c) < 0.5)
    if best is None or ok > best[0]:
        best = (ok, c)
print("      best single global reference: rate = 2^%.2f  ->  %.1f%% of key slots are within "
      "+-0.5 octave of it (i.e. the octave would be recovered)" % (best[1], 100.0 * best[0] / len(lg)))
print("      so rounding to the nearest lattice point misplaces %.1f%% of key slots by "
      ">=1 octave" % (100.0 - 100.0 * best[0] / len(lg)))

# ---- 3. what the demo actually plays ----------------------------------------------------
print("\n== 3. WHERE THE DEMO'S OWN VOICES LIVE ==")
Cmodal = {sel: c.most_common(1)[0][0] for sel, c in W.items()}
ev = []
for line in open(os.path.join(HERE, 'kon.log')):
    p = line.split()
    if len(p) == 5 and p[0] == 'KON' and float(p[1]) >= 17.0 and int(p[4], 16):
        ev.append((int(p[3], 16), int(p[4], 16)))
byc = collections.Counter(s >> 12 for s, _ in ev)
print("   note-ons by class: %s" % dict(sorted(byc.items())))
print("   classes 0-3 = the UNDUMPED sockets IC304/305/306: %d of %d events (%.0f%%) -- for "
      "those the period the HLE measures is a SUBSTITUTED IC307 recording, so even a "
      "period-based octave rule has nothing real to stand on."
      % (sum(v for k, v in byc.items() if k < 4), len(ev),
         100.0 * sum(v for k, v in byc.items() if k < 4) / len(ev)))
