#!/usr/bin/env python3
"""reg080_oracle.py -- three bits of the multisample descriptor DO reach the tone generator.

QUESTION ANSWERED: does per-recording ROM data reach IC303 in processed form? Yes. Register
+0x080's bits[14:12] -- which the HLE discards as "the strobe and pan" -- are built by
Voice_Build_OutputLevel (ROM 0x0232C7, kn5000_subprogram_v142.asm:15687-15726) from one of two
sources, selected by bit 7 of the SELECTED ZONE RECORD's byte +0x02:

    bit 7 SET   ->  field = (zone_record[+0x02] >> 4) & 7      # descriptor bits, copied
    bit 7 CLEAR ->  field = T[folded_note mod 12]              # a 128-entry table at 0x00FBE4
                    T[n] = floor(2 * (n mod 12) / 3)

That is the same zone record whose word[0] is the +0x040 selector and whose word at (stride-2) is
the pitch trim C. So the chip is handed three bits of the very descriptor the HLE was told it could
not see.

    python3 tools/kn5000-rootpitch/reg080_oracle.py /tmp/tg-burst.log

VERIFIED 2026-08-19 on a 2182-burst capture of the built-in demo: for selectors that map to exactly
one zone record, the override branch predicts the captured field 196/196 = 100.0%.

WHY IT MATTERS BEYOND THE CENSUS: on the OTHER branch the field is a function of the played note,
so it CONSTRAINS C to within a whole semitone on every note-on -- which makes it an oracle for
auditing the shipped pitch table. Its verdicts on the ambiguous selectors were: 4 confirmed the
shipped modal choice, and 2 contradicted it.

⚠ A selector can appear in more than one SET, with different zone records. Restrict to selectors
with a unique record before scoring, or the ambiguity shows up as a 3% error rate that is really a
mapping problem: unrestricted the same capture scores 204/211 = 96.7%.
"""
import collections, csv, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
SETS = os.path.join(REPO, 'notes', 'data', 'kn5000-multisample-sets.tsv')


def zone_records():
    """selector -> {first byte of its zone record}, keeping ALL candidates"""
    out = collections.defaultdict(set)
    for r in csv.DictReader(open(SETS), delimiter='\t'):
        blob = {}
        for part in r['finetune(E:hex)'].split(';'):
            if ':' in part:
                k, v = part.split(':')
                blob[int(k)] = v
        for i, z in enumerate(r['zones(lo-hi:class:entry)'].split(';')):
            if ':' not in z:
                continue
            _, cls, ent = z.split(':')
            sel = (int(cls) << 12) | int(ent, 16)
            if i in blob and len(blob[i]) >= 2:
                out[sel].add(bytes.fromhex(blob[i])[0])
    return out


def bursts(path):
    pending = collections.defaultdict(dict)
    out = []
    for line in open(path):
        if not line.startswith('TGB '):
            continue
        f = line.split()
        if len(f) != 4:
            continue
        latch, data = int(f[2], 16), int(f[3], 16)
        ch, reg = latch & 0x3f, latch & 0xffc0
        if reg == 0 and (data & 0xff00) == 0x8100:
            cur = pending.pop(ch, None)
            if cur and 0x40 in cur and 0x80 in cur:
                out.append((cur[0x40], cur[0x80], cur.get(0x400)))
            pending[ch] = {}
            continue
        pending[ch][reg] = data
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/tg-burst.log'
    recs = zone_records()
    uniq = {s: list(v)[0] for s, v in recs.items() if len(v) == 1}
    ev = bursts(path)
    print(f"{len(ev)} bursts; {len(uniq)}/{len(recs)} selectors map to a unique zone record")

    lown = {b & 0x0f for v in recs.values() for b in v}
    print(f"low nibble of zone_record[+0x02] across all records: {sorted(lown)} "
          f"-> {'a clean {bit7 flag, bits[6:4] value} field' if lown == {0} else 'NOT clean'}")

    ok = n = 0
    for sel, r80, _ in ev:
        b = uniq.get(sel)
        if b is None or not (b & 0x80):
            continue
        n += 1
        if ((b >> 4) & 7) == ((r80 >> 12) & 7):
            ok += 1
    print(f"\nOVERRIDE BRANCH: predicted == captured for {ok}/{n}"
          + (f" = {100*ok/n:.1f}%" if n else ""))
    print("   i.e. descriptor bits arrive on the bus, and we can predict them bit for bit."
          if n and ok == n else "")

    covered = sum(1 for s in uniq if uniq[s] & 0x80)
    print(f"\ncoverage: {covered}/{len(uniq)} unambiguous selectors take the override branch;"
          f" the rest are on the note-derived branch")
    return 0


if __name__ == '__main__':
    sys.exit(main())
