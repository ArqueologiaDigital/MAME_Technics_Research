#!/usr/bin/env python3
"""aux_eg_probe.py -- what are the six undocumented registers in groups 9 and A?

QUESTION ANSWERED: the sub-CPU writes six per-voice registers that NEITHER the minimal HLE nor the
full private implementation decodes -- +0x900, +0x940, +0x980, +0x9C0, +0xA00, +0xA40. The minimal
device's header guesses "the two auxiliary envelope generators" with nothing behind it. This tests
the guess from the bus alone.

    python3 tools/kn5000-rootpitch/aux_eg_probe.py /tmp/tg-burst.log

THREE PIECES OF EVIDENCE, all from a 2182-burst capture of the built-in demo (2026-08-19):

1. WORD SHAPE. The amplitude EG's words are (target << 8) | rate with rate in 0..0x7F. The group
   9/A words have low bytes <= 0x7F in 85-100% of writes and are dominated by AE00 -- target 0xAE,
   rate 0, which in the amplitude EG's own encoding means "hold at this level".

2. WRITE COUNTS, which is the clincher. Per register, over 2182 bursts:

       amplitude EG   +0x800 6167   +0x840 6337   +0x880 2288
       group 9        +0x900 3659   +0x940 3659   +0x980 2182
       group 9/A      +0x9C0 3659   +0xA00 3659   +0xA40 2182

   The same shape three times: segments 0 and 1 take extra writes, segment 2 takes almost exactly
   one per burst. That is three envelope generators of three segments each, not six unrelated
   registers -- and it groups them as {900,940,980} and {9C0,A00,A40}.

3. TIMING. Group 9/A words are programmed at the gate (about 90% within 1 ms of it), whereas the
   amplitude EG's first two segments are heavily re-armed later in the note -- consistent with the
   amplitude EG being the one that carries release and re-aim, and the other two being set up once.

CONCLUSION: groups 9 and A are two further three-segment envelope generators in the same format as
the amplitude EG. Their targets are mostly 0xAE at rate 0, i.e. flat -- most demo patches do not
modulate them, which is why ignoring them has cost nothing audible so far.

STILL UNKNOWN: which is pitch and which is filter. A patch with an obvious pitch envelope (a
synth-brass swell, a timpani) played while capturing would separate them: the one whose target
tracks the note is the pitch EG.
"""
import collections, sys

AMP = (0x800, 0x840, 0x880)
G9 = (0x900, 0x940, 0x980)
GA = (0x9C0, 0xA00, 0xA40)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/tg-burst.log'
    counts = collections.Counter()
    vals = collections.defaultdict(collections.Counter)
    delays = collections.defaultdict(list)
    last_gate, bursts = {}, 0

    for line in open(path):
        if not line.startswith('TGB '):
            continue
        f = line.split()
        if len(f) != 4:
            continue
        t = float(f[1])
        latch, data = int(f[2], 16), int(f[3], 16)
        ch, reg = latch & 0x3f, latch & 0xffc0
        if reg == 0 and (data & 0xff00) == 0x8100:
            last_gate[ch] = t
            bursts += 1
            continue
        counts[reg] += 1
        vals[reg][data] += 1
        if ch in last_gate:
            delays[reg].append(t - last_gate[ch])

    print(f"{bursts} note-on gates\n")
    print(f"{'group':>12} {'seg0':>16} {'seg1':>16} {'seg2':>16}")
    for name, g in (("amplitude EG", AMP), ("group 9", G9), ("group 9/A", GA)):
        cells = [f"+0x{r:03X} {counts[r]:5d}" for r in g]
        print(f"{name:>12} {cells[0]:>16} {cells[1]:>16} {cells[2]:>16}")
    print("\n   -> segment 2 takes ~one write per burst in all three; the shape repeats")

    print(f"\n{'reg':>7} {'rate-like low byte':>19} {'at the gate':>12}  top values")
    for r in AMP + G9 + GA:
        n = counts[r]
        if not n:
            continue
        lo = sum(c for v, c in vals[r].items() if (v & 0xff) <= 0x7f) / n
        d = delays[r]
        atgate = (sum(1 for x in d if x < 0.001) / len(d)) if d else 0
        top = ' '.join(f'{v:04X}x{c}' for v, c in vals[r].most_common(3))
        print(f"  +0x{r:03X} {100*lo:18.1f}% {100*atgate:11.1f}%  {top}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
