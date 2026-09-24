#!/usr/bin/env python3
"""Is the firmware's voice-record note recoverable from the TG register stream?

THE QUESTION
  kn7000.cpp reads the note out of CPU work RAM at a hardcoded, firmware-build
  specific address (KN7000_VOICE_RECORDS). If the note is a function of what the
  chip is actually TOLD -- the 18-bit pitch value p18, plus the bank/zone carried
  in the aux word -- that read can be deleted.

WHAT IS TESTED, in order
  1. Is np16 an affine function of p18 overall?  The driver's own fallback claims
     np16 = 24576 + (p18 - 0x1C838)/4  (1024 p18 units per semitone, MIDI 96 at
     0x1C838). Report the residual from that.
  2. If the residual is not zero, is it CONSTANT WITHIN each (bank, zone)?  Then it
     is a per-zone tuning offset and is recoverable, because bank and zone arrive
     through register class 0x1C02.
  3. NULL CONTROL: shuffle the (bank, zone) labels across rows and re-measure. If
     shuffled grouping explains the residual just as well, the grouping explains
     nothing and step 2 was an artefact of having many small groups.

RUN  python3 analyse_pitch.py rows.tsv
"""
import sys, random, statistics, collections

PRED_ANCHOR, PRED_MIDI96, PRED_PER_SEMI = 0x1C838, 24576, 4.0

def predicted(p18):
    return PRED_MIDI96 + (p18 - PRED_ANCHOR) / PRED_PER_SEMI

def spread(vals):
    return 0.0 if len(vals) < 2 else max(vals) - min(vals)

def group_report(rows, keyfn, label):
    g = collections.defaultdict(list)
    for r in rows:
        g[keyfn(r)].append(r['np16'] - predicted(r['p18']))
    spreads = [spread(v) for v in g.values()]
    tight = sum(1 for s in spreads if s < 0.5)
    print(f"  {label}: {len(g)} groups, {tight} with residual spread < 0.5 "
          f"({100.0*tight/len(g):.0f}%), median spread {statistics.median(spreads):.2f}")
    return g, tight / len(g)

def main(path):
    rows = []
    with open(path) as f:
        head = f.readline().strip().split('\t')
        for line in f:
            if not line.strip():
                continue
            d = dict(zip(head, line.rstrip('\n').split('\t')))
            rows.append({k: int(v, 16) if k == 'aux' else int(v) for k, v in d.items()})
    print(f"rows: {len(rows)}")
    if not rows:
        print("NO ROWS -- nothing to decode. This is not a negative result about the "
              "hardware; it means the capture found no note-on with an active record.")
        return 1

    res = [r['np16'] - predicted(r['p18']) for r in rows]
    print(f"\n1. residual from the driver's fallback  np16 - (24576 + (p18-0x1C838)/4)")
    print(f"   n={len(res)}  min={min(res):.2f}  max={max(res):.2f}  "
          f"median={statistics.median(res):.2f}  spread={max(res)-min(res):.2f}")
    if max(res) - min(res) < 0.5:
        print("   => the register stream ALREADY carries the note; the RAM read is redundant.")
        return 0

    print(f"\n2. is the residual constant within a (bank, zone)?")
    _, frac = group_report(rows, lambda r: (r['bank'], r['zone']), "(bank,zone)")
    group_report(rows, lambda r: r['zone'], "zone alone")
    group_report(rows, lambda r: r['aux'], "full aux word")

    print(f"\n3. NULL CONTROL -- same grouping sizes, labels shuffled")
    shuffled = [dict(r) for r in rows]
    labels = [(r['bank'], r['zone']) for r in rows]
    random.seed(1)
    random.shuffle(labels)
    for r, l in zip(shuffled, labels):
        r['bank'], r['zone'] = l
    _, nullfrac = group_report(shuffled, lambda r: (r['bank'], r['zone']), "(bank,zone) SHUFFLED")
    print(f"\n   real {100*frac:.0f}%  vs  null {100*nullfrac:.0f}%")
    if frac > nullfrac + 0.2:
        print("   => the offset is a genuine function of (bank, zone), which the chip is "
              "told -> recoverable without reading RAM.")
    else:
        print("   => grouping explains no more than chance; the note is NOT recoverable "
              "from p18 and aux alone in this capture.")
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else 'rows.tsv'))
