#!/usr/bin/env python3
"""Is +0x400 a PURE LOG PLAYBACK RATE?

The audit (tools/kn5000_pitch_audit.py sec.5) fits  K = C + 0x80 - 3072*log2(period)
MODULO 3072 (one octave) and gets K_page = 123.9 / 126.7 / 129.1 / 137.8 for the four
IC307 pages -- i.e. essentially ONE GLOBAL constant ~= 0x80.

This script asks the question the audit did NOT ask: does the law hold WITHOUT the
modular reduction?  If it does, the per-chunk "root pitch" is nothing but the
recording's OWN pitch, which the HLE already measures -- and the absolute pitch of an
uncorrelated (demo/rhythm) voice is recoverable as

    note = regs[8]/256 - 12*log2(period_samples) - K/256          [= voice_rho() - K/256]

Outputs the key-weighted error distribution of that proposal, directly comparable with
audit sec.2 (the 0x3524 anchor: 0.4% of key slots within +-0.5 semitone).
"""
import bisect, collections, json, math, os, sys

sys.path.insert(0, os.path.expanduser('~/compartilhado/kn7000_mame/tools'))
import kn5000_pitch_audit as A

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'periods.json')

d = open(A.IC307, 'rb').read()
pages = {p: A.parse_page(d, p * A.PAGE) for p in range(4)}

per = {}
if os.path.exists(CACHE):
    per = {tuple(int(x) for x in k.split(',')): v for k, v in json.load(open(CACHE)).items()}


def P(cls, e):
    """(period_float, samples, reliable) or None if the chunk does not exist."""
    pg = pages[cls & 3]
    if not pg or e >= pg['count']:
        return None
    k = (cls & 3, e)
    if k not in per:
        per[k] = A.detect_period(d, pg['start'][e], pg['samples'][e])
    return per[k], pg['samples'][e]


sets = A.read_sets()
W = A.trim_table(sets)

rows = []          # (cls, entry, C, keyweight, period, samples, ambiguous)
for sel, cnt in sorted(W.items()):
    cls, ent = sel >> 12, sel & 0xFFF
    if cls not in (4, 5, 6, 7):
        continue                      # classes 0-3 are on the UNDUMPED sockets
    r = P(cls, ent)
    if r is None:
        continue
    p, ns = r
    for C, w in cnt.items():
        rows.append((cls, ent, C, w, p, ns, len(cnt) > 1))

json.dump({','.join(str(x) for x in k): v for k, v in per.items()}, open(CACHE, 'w'))

# ------------------------------------------------------------------ the law, NOT reduced
def kraw(C, p):
    return C + 128 - 3072 * math.log2(p)


usable = [r for r in rows if r[4] > 0 and abs(r[4] - r[5]) > 1e-9]   # drop detect_period fallbacks
print("selectors on dumped pages: %d rows, %d with a usable period (%d were the "
      "'whole chunk' fallback or aperiodic)" % (len(rows), len(usable), len(rows) - len(usable)))

ks = [kraw(C, p) for cls, e, C, w, p, ns, amb in usable]
ks_s = sorted(ks)
med = ks_s[len(ks_s) // 2]
print("\n== RAW (no mod 3072) K = C + 0x80 - 3072*log2(period) ==")
print("   median %.1f   IQR %.1f .. %.1f   min %.1f  max %.1f"
      % (med, ks_s[len(ks_s) // 4], ks_s[3 * len(ks_s) // 4], ks_s[0], ks_s[-1]))

oct_hist = collections.Counter(round((k - med) / 3072.0) for k in ks)
print("   octave residual round((K-med)/3072):", dict(sorted(oct_hist.items())))
within = lambda t: sum(1 for k in ks if abs(k - med) <= t)
for t, lbl in ((32, '12.5c'), (64, '25c'), (128, '50c'), (256, '1 semitone')):
    print("   within +-%4d units (%-10s): %4d / %4d = %5.1f%%" % (t, lbl, within(t), len(ks),
                                                                 100.0 * within(t) / len(ks)))

# key-weighted, per class, comparable with audit sec.2
print("\n== PROPOSED DECODE  note = rho - K/256 : key-weighted error, semitones ==")
for cls in (4, 5, 6, 7, None):
    sub = [r for r in usable if cls is None or r[0] == cls]
    if not sub:
        continue
    tot = sum(r[3] for r in sub)
    errs = sorted(((kraw(r[2], r[4]) - med) / 256.0, r[3]) for r in sub)
    acc = 0
    pct = {}
    for e, w in errs:
        acc += w
        for q in (1, 5, 25, 50, 75, 95, 99):
            if q not in pct and acc >= tot * q / 100:
                pct[q] = e
    ok = lambda t: 100.0 * sum(w for e, w in errs if abs(e) <= t) / tot
    print("   class %-4s n=%4d keymass=%6d  |err|<=0.5: %5.1f%%   <=0.1: %5.1f%%   "
          "median %+.3f  p5 %+.2f p95 %+.2f" %
          (str(cls), len(sub), tot, ok(0.5), ok(0.1), pct.get(50, 0), pct.get(5, 0), pct.get(95, 0)))

# the SAME statistic for the CURRENT 0x3524 anchor, restricted to the same rows (fair null)
print("\n== CURRENT 0x3524 anchor, SAME rows (the null this must beat) ==")
tot = sum(r[3] for r in usable)
errs = sorted((60 + (r[2] - 13476) / 256.0, r[3]) for r in usable)
ok = lambda t: 100.0 * sum(w for e, w in errs if abs(e) <= t) / tot
acc = 0
pct = {}
for e, w in errs:
    acc += w
    for q in (5, 25, 50, 75, 95):
        if q not in pct and acc >= tot * q / 100:
            pct[q] = e
print("   |err|<=0.5: %5.1f%%   <=0.1: %5.1f%%   median %+.3f   p5 %+.2f p95 %+.2f"
      % (ok(0.5), ok(0.1), pct.get(50, 0), pct.get(5, 0), pct.get(95, 0)))

# ---------------------------------------------------------------- who is right by accident?
# error of the CURRENT anchor as a function of C: err = 60 + (C-13476)/256
print("\n== which C values the 0x3524 anchor happens to get RIGHT ==")
print("   err=0    <=> C = %d" % (13476 - 15360))
print("   C=0      <=> err = %+.2f semitones" % (60 + (0 - 13476) / 256.0))
byC = collections.Counter()
for cls, e, C, w, p, ns, amb in rows:
    byC[C] += w
print("   most common C (key-weighted):")
for C, w in byC.most_common(12):
    print("      C=%6d  keymass %6d  anchor err %+7.2f st" % (C, w, 60 + (C - 13476) / 256.0))
