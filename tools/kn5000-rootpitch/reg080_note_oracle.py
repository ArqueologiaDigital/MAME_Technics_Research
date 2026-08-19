#!/usr/bin/env python3
"""reg080_note_oracle.py -- audit the shipped pitch table against the bus.

QUESTION ANSWERED: on the note-derived branch, register +0x080 bits[14:12] hold
T[folded_note mod 12] with T[n] = floor(2*(n mod 12)/3) -- a table lookup on the note the firmware
computed. That pins the note MODULO 12, so for every note-on it constrains C to within a whole
semitone. Which means the bus can AUDIT the shipped 1444-entry pitch table:

    for each note-on, does T[((+0x400 - 0x80 - C(selector)) >> 8) mod 12] equal the captured field?

    python3 tools/kn5000-rootpitch/reg080_note_oracle.py /tmp/tg-burst.log

A selector whose every burst agrees is consistent with its shipped C. One that disagrees is either
carrying the wrong C, or is subject to a whole-semitone term added AFTER the octave fold (part
transpose, bend, master tune), which moves +0x400 without moving this field.

RESULTS on the 2182-burst demo capture (2026-08-19):
  * 53 of 67 note-branch selectors agree on every burst with the shipped C.
  * 2 are fully explained by choosing a DIFFERENT C that the firmware tables already list for them:
        selector 0002 -> 2756 (shipped 0)      64/64 bursts
        selector 508D -> 3132 (shipped -1408)  24/24 bursts
    Both are among the 77 AMBIGUOUS selectors, which the generator currently resolves by taking a
    modal value with ties broken by dictionary insertion order. This is a real tie-break rule and
    it disagrees with the current one twice.
  * 12 need a whole-semitone offset that no listed candidate provides. OPEN.

⚠ DO NOT try to recompute C from the zone-record bytes without first confirming the record layout
  in the disassembly. An attempt here assumed the tsv's record column holds bytes +0x02..+0x05 and
  produced WORSE agreement than the shipped table, which is a sign the offset guess was wrong --
  not evidence about the table.
"""
import collections, csv, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
T = [(2 * (n % 12)) // 3 for n in range(12)]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/tg-burst.log'

    tab = {}
    for r in csv.DictReader(open(os.path.join(REPO, 'notes/data/kn5000-pitch-trim-table.tsv')), delimiter='\t'):
        cands = [int(p.split(':')[0]) for p in r['all_C'].split(';') if ':' in p]
        tab[int(r['sel'], 16)] = (int(r['C_modal']), int(r['n_distinct']), sorted(set(cands)))

    recs = collections.defaultdict(set)
    for r in csv.DictReader(open(os.path.join(REPO, 'notes/data/kn5000-multisample-sets.tsv')), delimiter='\t'):
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
                recs[sel].add(bytes.fromhex(blob[i])[0])
    uniq = {s: list(v)[0] for s, v in recs.items() if len(v) == 1}

    pending = collections.defaultdict(dict)
    byse = collections.defaultdict(list)
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
            if cur and {0x40, 0x80, 0x400} <= set(cur):
                sel = cur[0x40]
                b = uniq.get(sel)
                if b is not None and not (b & 0x80) and sel in tab:   # note branch only
                    byse[sel].append((cur[0x80], cur[0x400]))
            pending[ch] = {}
            continue
        pending[ch][reg] = data

    def hits(rows, c):
        return sum(1 for r80, r400 in rows if T[(((r400 - 0x80 - c) >> 8)) % 12] == ((r80 >> 12) & 7))

    clean = corrected = open_ = 0
    print(f"{'sel':>6} {'bursts':>6} {'shipped':>8} {'agree':>6}   verdict")
    for sel, rows in sorted(byse.items(), key=lambda kv: -len(kv[1])):
        modal, nd, cands = tab[sel]
        h = hits(rows, modal)
        if h == len(rows):
            clean += 1
            continue
        alt = [(hits(rows, c), c) for c in cands if c != modal]
        best = max(alt) if alt else (0, None)
        if best[0] == len(rows):
            corrected += 1
            print(f"{sel:06X} {len(rows):6d} {modal:8d} {h:6d}   CORRECTED -> C={best[1]} "
                  f"({best[0]}/{len(rows)}), a candidate the tables already list")
        else:
            open_ += 1
            print(f"{sel:06X} {len(rows):6d} {modal:8d} {h:6d}   OPEN: no listed candidate fits")
    print(f"\n{clean} selectors agree with the shipped C on every burst")
    print(f"{corrected} corrected by a listed candidate")
    print(f"{open_} still open")
    return 0


if __name__ == '__main__':
    sys.exit(main())
