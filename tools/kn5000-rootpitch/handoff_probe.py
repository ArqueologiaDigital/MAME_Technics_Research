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

⚠ THE CONCLUSION THIS PROBE ORIGINALLY DREW WAS WRONG, and the way it was wrong is worth keeping.

  From the facts above it concluded that F000 is a percussion MODE flag, that reading it as a mute
  silences the drum kit, and that the mute could therefore be removed. Two of those are true. The
  third is not, and Felipe caught it by ear within minutes of the change: the machine droned a
  wrong note constantly, from boot onwards.

  WHAT THE PROBE COULD NOT SEE: it only looked at the demo. At the end of boot the firmware leaves
  ONE voice gated and never freed, handed off with F000, with all three envelope segments
  programmed to HOLD. The firmware is relying on F000 meaning silence. Any renderer that gives that
  voice output drones for the rest of the session -- and a windowed RMS gate over a playing demo
  cannot see a drone that is present in every window.

  WHAT IT ACTUALLY IS: the low byte is an OUTPUT LEVEL, 0x00..0xFF. F0FF is full, F1D7 is 0.84,
  F187 is 0.53, F000 is silent. That explains every observation including the boot voice, and it is
  strictly better than the binary mute it replaced, which rendered F1D7 and F187 at full scale.

  The "457 of 457 freed" measurement was correct and irrelevant: it showed the demo's F000 voices
  are freed promptly, which says nothing about the one at boot that never is.

  ALWAYS RE-RUN THE NULL CONTROL after touching anything in the render path. It was measured once,
  early, and quoted for hours as though still valid.

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
