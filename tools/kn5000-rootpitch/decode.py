#!/usr/bin/env python3
"""Decode the captured demo note-ons two ways and test them against the demo's own MIDI.

  A) what the HLE renders today:  note = 60 + (regs[8] - 0x3524)/256
  B) the firmware's per-selector constant:  note = (regs[8] - 0x80 - C(+0x040))/256

Test 1 (alignment-free, self-contained): under (B) the result must be an INTEGER MIDI
note, because regs[8] = 256*key + 0x80 + C by construction.  NULL = the same statistic
with C drawn from a random OTHER selector (keeps the C histogram, kills the pairing).

Test 2: the decoded note multiset vs the demo MIDI's own notes, per part.
"""
import collections, os, random, sys
sys.path.insert(0, os.path.expanduser('~/compartilhado/kn7000_mame/tools'))
import kn5000_pitch_audit as A

HERE = os.path.dirname(os.path.abspath(__file__))
W = A.trim_table(A.read_sets())
Cmodal = {sel: c.most_common(1)[0][0] for sel, c in W.items()}
Cuniq = {sel: list(c)[0] for sel, c in W.items() if len(c) == 1}

ev = []
for line in open(os.path.join(HERE, 'kon.log')):
    p = line.split()
    if len(p) != 5 or p[0] != 'KON':
        continue
    t, ch, sel, pit = float(p[1]), int(p[2]), int(p[3], 16), int(p[4], 16)
    ev.append((t, ch, sel, pit))
ev = [e for e in ev if e[0] >= 17.0 and e[3] != 0]        # demo only, real pitch written
print("note-ons in the demo window with a pitch: %d   distinct selectors: %d"
      % (len(ev), len({e[2] for e in ev})))

known = [e for e in ev if e[2] in Cmodal]
print("selectors present in the firmware C table: %d/%d events (%d selectors, %d of them "
      "single-valued)" % (len(known), len(ev), len({e[2] for e in known}),
                          len({e[2] for e in known if e[2] in Cuniq})))
miss = collections.Counter(e[2] for e in ev if e[2] not in Cmodal)
if miss:
    print("   NOT in the table:", ["%04X:%d" % kv for kv in miss.most_common(8)])


def frac(x):
    y = x - round(x)
    return y


def integrality(vals, tol=0.02):
    return 100.0 * sum(1 for v in vals if abs(frac(v)) <= tol) / max(len(vals), 1)


noteB = [(e, (e[3] - 128 - Cmodal[e[2]]) / 256.0) for e in known]
noteA = [(e, 60 + (e[3] - 0x3524) / 256.0) for e in known]
print("\n== Test 1: is the decoded note an INTEGER MIDI note? ==")
print("   (B) firmware C   : %.1f%% within 0.02 semitone of an integer" % integrality([v for _, v in noteB]))
print("   (A) 0x3524 anchor: %.1f%%" % integrality([v for _, v in noteA]))
rng = random.Random(7)
sels = sorted({e[2] for e in known})
nulls = []
for _ in range(50):
    perm = dict(zip(sels, rng.sample(sels, len(sels))))
    nulls.append(integrality([(e[3] - 128 - Cmodal[perm[e[2]]]) / 256.0 for e in known]))
print("   NULL (C permuted across selectors, 50 draws): %.1f%% +- %.1f"
      % (sum(nulls) / len(nulls), (max(nulls) - min(nulls)) / 4))

bad = [(e, v) for e, v in noteB if abs(frac(v)) > 0.02]
print("   non-integer residues come from %d events / %d selectors:"
      % (len(bad), len({e[2] for e, _ in bad})))
cnt = collections.Counter((e[2], round(frac(v) * 256)) for e, v in bad)
for (s, r), n in cnt.most_common(10):
    print("      sel %04X  residue %+4d units (%.2f st)  n=%d   %s"
          % (s, r, r / 256.0, n, 'AMBIGUOUS C' if s not in Cuniq else 'single-valued C'))

print("\n== decoded note range (B) ==")
ns = sorted(round(v) for _, v in noteB)
print("   min %d  p5 %d  median %d  p95 %d  max %d" %
      (ns[0], ns[len(ns) // 20], ns[len(ns) // 2], ns[19 * len(ns) // 20], ns[-1]))
na = sorted(round(v) for _, v in noteA)
print("   anchor (A) range: min %d  p5 %d  median %d  p95 %d  max %d" %
      (na[0], na[len(na) // 20], na[len(na) // 2], na[19 * len(na) // 20], na[-1]))

# error the anchor makes, per selector, key-weighted by the demo's OWN usage
print("\n== the ANCHOR's error, per selector, weighted by what the DEMO actually plays ==")
err = collections.Counter()
for e in known:
    err[e[2]] += 1
rows = sorted(((60 + (Cmodal[s] - 13476) / 256.0), s, n) for s, n in err.items())
tot = sum(err.values())
print("   %d selectors; anchor error = 60 + (C-13476)/256" % len(rows))
for band in ((-0.5, 0.5), (-2, -0.5), (0.5, 2), (2, 8), (8, 100), (-100, -2)):
    m = [r for r in rows if band[0] <= r[0] < band[1]]
    print("      err in [%+6.1f,%+6.1f): %4d events (%4.1f%%)  %d selectors"
          % (band[0], band[1], sum(r[2] for r in m), 100 * sum(r[2] for r in m) / tot, len(m)))
print("   the ten most-played selectors:")
for s, n in err.most_common(10):
    print("      %04X  n=%4d  C=%6d  anchor err %+7.2f st  cls %d entry %03X %s"
          % (s, n, Cmodal[s], 60 + (Cmodal[s] - 13476) / 256.0, s >> 12, s & 0xFFF,
             '' if s in Cuniq else '(ambiguous)'))
