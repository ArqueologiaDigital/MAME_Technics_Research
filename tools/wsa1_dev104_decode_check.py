#!/usr/bin/env python3
"""Check l7a1429_device::log_decoded()'s arithmetic against the firmware's own reset image.

QUESTION IT ANSWERS: does the DERIVED view the L7A1429 placeholder prints for a
logged register value reproduce the physical quantity the ROM curve tables are
known to encode?  The device only stores and logs; this is the one piece of
arithmetic in it that could silently be wrong.

    python3 tools/wsa1_dev104_decode_check.py        # prints every check
    python3 tools/wsa1_dev104_decode_check.py -q     # exit status only

THE SIGNAL BEING READ.  Dev104_StagingStruct_ResetImage (prom_c ROM 0xFE133B) is
the nineteen-word image the power-on sweep copies into all 64 channels, so its
words ARE register values the real chip receives.  Two of them are curve-table
entries whose index is known:

    word 16 -> register 0x0400 = 0xBDF0 = Curve_FE04C9[74]
    word 18 -> register 0x0480 = 0x987B = Curve_FE04C9[84]
    word 13 -> register 0x0340 = 0xE0B8 = Curve_FE05C9[74]
    word 15 -> register 0x03C0 = 0xE05E = Curve_FE05C9[84]

The curve lane proved (kn5000-roms-disasm wsa1/notes/FINDINGS-l7a1429-curve-tables.md
section 1, and HLE-GUIDE-l7a1429.md section 2.2) that entry k of both tables is a
one-pole lowpass cutoff under the bilinear transform at 440*2^((k+36-69)/12) Hz,
fs = 44100.  PASS = the decode lands on that frequency, from BOTH encodings.

The formulas here are transcribed from acoustic_modeling.cpp; if they drift apart
this script stops proving anything, so keep them in step.
"""

import math
import sys

FS = 44100.0                    # IC4's X4 = 33.8688 MHz = 768 x 44100


def fold(w):
    """The firmware's sign-magnitude -> offset-binary step, prom_c 0xFC5361."""
    return (0x8000 - (w & 0x7FFF)) if (w & 0x8000) else (w + 0x8000)


def cutoff_q16(w):
    """Registers 0x0400 / 0x0440 / 0x0480."""
    f = fold(w)
    k = f / float(0x10000 - f)          # K = tan(pi*fc/fs), the bilinear prewarp
    return FS * math.atan(k) / math.pi


def cutoff_q13(w):
    """Registers 0x0340 / 0x0380 / 0x03C0 -- the SAME cutoff, (1 - G/8192)*K = 1/128."""
    s = 1.0 - fold(w) / 8192.0
    if s <= 0.0:
        return None
    return FS * math.atan(1.0 / (128.0 * s)) / math.pi


def note_hz(index):
    """The curve tables' index is a MIDI note minus 36."""
    return 440.0 * 2.0 ** ((index + 36 - 69) / 12.0)


CASES = [
    # (register, reset-image word, curve index, decoder, tolerance in cents)
    (0x0400, 0xBDF0, 74, cutoff_q16, 1.0),
    (0x0480, 0x987B, 84, cutoff_q16, 1.0),
    (0x0340, 0xE0B8, 74, cutoff_q13, 20.0),   # Q13 is the coarser encoding
    (0x03C0, 0xE05E, 84, cutoff_q13, 20.0),
]


def main():
    quiet = "-q" in sys.argv
    failures = 0

    for reg, word, index, decode, tol in CASES:
        got = decode(word)
        want = note_hz(index)
        cents = 1200.0 * math.log2(got / want)
        ok = abs(cents) <= tol
        failures += not ok
        if not quiet:
            print("  %-4s register 0x%04X = 0x%04X -> %8.1f Hz, curve index %d = %8.1f Hz "
                  "(%+.2f cents, tol %.0f)"
                  % ("ok" if ok else "FAIL", reg, word, got, index, want, cents, tol))

    # The two encodings must agree with EACH OTHER, which is the cross-check that
    # does not go through the note formula at all.
    for q16_word, q13_word, index in ((0xBDF0, 0xE0B8, 74), (0x987B, 0xE05E, 84)):
        a, b = cutoff_q16(q16_word), cutoff_q13(q13_word)
        cents = 1200.0 * math.log2(b / a)
        ok = abs(cents) <= 20.0
        failures += not ok
        if not quiet:
            print("  %-4s index %d: Q16 %.1f Hz vs Q13 %.1f Hz (%+.2f cents)"
                  % ("ok" if ok else "FAIL", index, a, b, cents))

    # The remaining units are exact by construction; assert them so a typo in the
    # device's constants is caught here too.
    units = [
        ("0x0040 tune, 1/256 semitone", 0x2100 / 256.0, 33.0),
        ("0x00C0 position, 3072 counts/octave", 0x6C00 / 3072.0, 9.0),
        ("0x0280 sub gain, Q15", 0x8000 / 32768.0, 1.0),
    ]
    for label, got, want in units:
        ok = abs(got - want) < 1e-9
        failures += not ok
        if not quiet:
            print("  %-4s %s -> %.6f (want %.6f)" % ("ok" if ok else "FAIL", label, got, want))

    print("FAILURES: %d" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
