#!/usr/bin/env python3
"""handoff_probe.py -- what is the +0x000 "hand-off" command, and who receives it?

QUESTION ANSWERED: the tone generator's control register +0x000 carries three things: a note-on
gate (0x81xx), a free (0x7E00), and a third class with bit 15 set that nobody decoded. The minimal
HLE guesses that a low byte of zero means "render this voice silent", which silences a large share
of the demo's note-ons. Is that guess right, and who does it hit?

    python3 tools/kn5000-rootpitch/handoff_probe.py /tmp/tg-burst2.log

FINDINGS (2026-08-19, 1705-gate capture):

  * +0x000 takes only SEVEN distinct values in the whole demo: 0x81xx gates, 0x7E00 frees, the
    hand-offs F0FF / F000 / F1D7 / F187, and one oddity 0x1200.
  * The hand-off value is a property of the SELECTOR CLASS, not of the note:
        class 5 receives F000 for 83.1% of its hand-offs; every other class, ~0%.
  * Class 5 is PERCUSSION. Its selectors play at exactly one pitch value 65% of the time against
    34% for the other classes -- 5049 is always 4C44, 507D and 5086 always 4D44. A voice that never
    transposes is a drum.

⚠ CONSEQUENCE FOR THE HLE, and it is audible. Treating "low byte == 0" as a mute silences exactly
  the F000 voices, i.e. the drum kit. The reference implementation ships that behaviour and its own
  comment records that ~42% of demo note-ons, "including the entire drum part", never sound. This
  probe says why: F000 is the PERCUSSION hand-off, not a mute command. A real KN5000 plays drums in
  its own demo, so the mute reading cannot be right.

  The counter-argument on record is that NOT muting is worse, because those voices then never fall
  silent, are never returned to the free pool, and the allocator starves. If so, the fix is in the
  voice-lifecycle model -- percussion presumably ends by running off the end of its sample -- and
  not in pretending the note was never played.

  This also explains 8 of the 12 selectors that fail the +0x080 pitch oracle: they are class-5
  percussion, so a check based on equal-tempered note recovery is meaningless for them. With those
  8 and the 3 flags-bit-1 selectors accounted for, only one genuine ambiguity remains (409D).
"""
import collections, sys


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/tg-burst2.log'
    cur = {}
    ctrl = collections.Counter()
    ho = collections.defaultdict(collections.Counter)
    pitch = collections.defaultdict(collections.Counter)

    for line in open(path):
        if not line.startswith('TGB '):
            continue
        f = line.split()
        if len(f) != 4:
            continue
        latch, d = int(f[2], 16), int(f[3], 16)
        ch, reg = latch & 0x3f, latch & 0xffc0
        if reg == 0x040:
            cur[ch] = d
        elif reg == 0x400 and ch in cur:
            pitch[cur[ch]][d] += 1
        elif reg == 0x000:
            ctrl[d] += 1
            is_gate = (d & 0xff00) == 0x8100
            if (d >> 15) and not is_gate and d != 0x7E00 and ch in cur:
                ho[cur[ch]][d] += 1

    print(f"+0x000 values: {', '.join(f'{k:04X}x{v}' for k, v in ctrl.most_common())}\n")

    byclass = collections.defaultdict(collections.Counter)
    for sel, c in ho.items():
        for v, n in c.items():
            byclass[sel >> 12][v] += n
    print(f"{'class':>6} {'total':>7} {'F000':>7}  F000 share   verdict")
    for cls in sorted(byclass):
        c = byclass[cls]
        tot = sum(c.values())
        share = 100 * c.get(0xF000, 0) / tot
        print(f"{cls:6d} {tot:7d} {c.get(0xF000,0):7d}  {share:9.1f}%   "
              f"{'<== the F000 class' if share > 50 else ''}")

    for cls in sorted(byclass):
        sels = [s for s in pitch if (s >> 12) == cls]
        if not sels:
            continue
        one = sum(1 for s in sels if len(pitch[s]) == 1)
        tag = "  <== never transposes: percussion" if one / len(sels) > 0.6 else ""
        print(f"   class {cls}: {one}/{len(sels)} selectors play at exactly one pitch{tag}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
