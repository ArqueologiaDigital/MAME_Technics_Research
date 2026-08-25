#!/usr/bin/env python3
"""Re-verify, against Toshiba's own TMP95C061 datasheet, every hardware claim the
overlay copy of src/devices/cpu/tlcs900/tmp95c061.cpp asserts about the timers
and about the interrupt nesting counter.

WHY THIS EXISTS
---------------
Three separate passes over this CPU derived the timer prescaler scale, the
16-bit timer semantics and control register 0x3C *from firmware alone*, because
every note in these trees said "no TLCS-900 databook is available to this
project".  That was wrong: the databook is on bitsavers, its text layer is
intact, and it settles all three questions outright -- including the residual
"x2 risk" that the firmware-only derivations could not close, because the
datasheet states the taps as a ratio to fc and never as an absolute frequency.

THE QUESTION EACH CHECK ANSWERS
-------------------------------
  taps        Is phiT1 = fc/8 (shift 3) or fc/128 (shift 7)?   -> fc/8, page 81.
  taps16      Do the 16-bit timers use the same prescaler?     -> yes, page 95.
  t4mod_cle   Which T4MOD bit controls clearing the counter?   -> bit 2, page 95.
  t4mod_clk   What do T4MOD bits[1:0] select?                  -> page 95.
  t5mod       Is T5MOD laid out the same?                      -> yes, page 98.
  trun        Which TRUN bits run the 16-bit timers, and does
              clearing a bit clear the counter?                -> b4/b5, "Stop
                                                                  & Clear", p101.
  comparators Are TREG4 and TREG5 two independent comparators
              (so an equal pair raises BOTH interrupts)?       -> yes, page 103.
  vectors     Which TREG does INTTR4 belong to?                -> TREG4, page 12.
  intnest     Is INTNEST hardware-maintained, and does RETI
              decrement it?                                    -> yes to both,
                                                                  page 11.
  baud        Is the baud generator's tap 0 really fc/4?       -> yes, page 135.

That last one is not about this file: it is the assumption the WSA1's fc = 28 MHz
was derived through (31250 baud * 16 * 14 * 4).  It was flagged as unsupported;
it is in the datasheet.

HOW TO RUN
----------
    python3 notes/wsa1-probes/tlcs900_datasheet_quotes.py [path/to/TMP95c061-ds.pdf]

The PDF is NOT committed (7.4 MB, and it is not ours to redistribute).  Fetch it:

    curl -o /tmp/TMP95c061-ds.pdf \
        http://www.bitsavers.org/components/toshiba/_dataSheet/TMP95c061-ds.pdf

    sha256  ef644920c6cfc20ea7eb88f529510ab5777849a93c8c7e8f75d6fc0947657eaf
    size    7405537 bytes
    192 pages, "Acrobat Distiller 2.1 for Power Macintosh", CreationDate 1996-11-11

Needs `pdftotext` (poppler-utils).  Text-layer checks are automatic; the four
claims that live only inside scanned register figures are listed at the end with
their page numbers so a human can eyeball them in a viewer (they were read that
way on 2026-08-25 and are transcribed here).
"""

import hashlib
import os
import re
import subprocess
import sys

DEFAULT_PDF = "/tmp/TMP95c061-ds.pdf"
EXPECT_SHA = "ef644920c6cfc20ea7eb88f529510ab5777849a93c8c7e8f75d6fc0947657eaf"

# (tag, page-in-document, substring that must appear in the text layer, meaning)
TEXT_CLAIMS = [
    ("taps", 81, "øT1 (8/fc)",
     "Table 3.8 (1): 8-bit timer input clock phiT1 = 8/fc  => shift 3, NOT 7"),
    ("taps", 81, "øT4 (32/fc)",
     "Table 3.8 (1): phiT4 = 32/fc  => shift 5, NOT 9"),
    ("taps", 81, "øT16 (128/fc)",
     "Table 3.8 (1): phiT16 = 128/fc  => shift 7, NOT 11"),
    ("taps", 81, "øT256 (2048/fc)",
     "Table 3.8 (1): phiT256 = 2048/fc  => shift 11, NOT 15"),
    ("taps16", 73, "input clock for 8-bit Timer 0/1",
     "3.8 (1): ONE 9-bit prescaler feeds 8-bit timers 0/1, 16-bit timers 4/5 "
     "and the serial interfaces -- so the 16-bit timers use the same taps"),
    ("taps16", 73, "Timer 4/5 and Serial Interface 0/1",
     "3.8 (1): ... and it is shared with timer 4/5"),
    ("comparators", 103, "The up-counter UC4/UC5 is cleared only when",
     "3.9 (5): UC is cleared only on the TREG5/TREG7 match -- never on TREG4/6"),
    ("comparators", 103, "<CLE>/T5MOD <CLE> = 0",
     "3.9 (5): and that clear can be DISABLED by CLE=0 (free-running counter)"),
    ("comparators", 103, "These are 16-bit comparators which compare the up-",
     "3.9 (5): TWO comparators per unit, each generating its own interrupt --"
     " so TREG4 == TREG5 must raise INTTR4 *and* INTTR5, not just one"),
    ("intnest", 11, "The CPU increments the INTNEST (Interrupt Nesting",
     "3.3.1 step (4): INTNEST is incremented BY HARDWARE on interrupt accept"),
    ("intnest", 11, "decements the INTNEST (Inter-",
     "3.3.1: and RETI decrements it (sic, 'decements' is the datasheet's typo)"),
    ("baud", 135, "φT0 = fc/4",
     "3.11: baud-rate generator tap 0 = fc/4 -- the step the WSA1's fc = 28 MHz"
     " was derived through, previously flagged as an unsupported assumption"),
    ("baud", 135, "φT2 = fc/16",
     "3.11: ... and the rest of that tap table"),
]

# Claims that live inside scanned figures (no text layer).  Transcribed by hand
# from the rendered page on 2026-08-25; page numbers so they can be re-read.
FIGURE_CLAIMS = [
    (95, "Figure 3.9 (3), T4MOD (0038H) bit map",
     "b7 CAP2T5 | b6 EQ5T5 | b5 CAP1IN | b4 CAP12M1 | b3 CAP12M0 | "
     "b2 CLE | b1 T4CLK1 | b0 T4CLK0.\n"
     "        Timer 4 input clock: 00 External clock (TI4) / 01 phiT1 (8/fc) / "
     "10 phiT4 (32/fc) / 11 phiT16 (128/fc).\n"
     "        Clearing the up-counter UC4: 0 Clear disable / "
     "1 Clear by match with TREG5."),
    (97, "Figure 3.9 (5), T4FFCR (0039H) bit map",
     "b7 TFF5C1 | b6 TFF5C0 | b5 CAP2T4 | b4 CAP1T4 | b3 EQ5T4 | b2 EQ4T4 | "
     "b1 TFF4C1 | b0 TFF4C0.  EQ5T4/EQ4T4 = invert TFF4 on the TREG5/TREG4 "
     "match.  The WSA1 and the KN1500 both write 0x00 -> no inversion asked for."),
    (98, "Figure 3.9 (6), T5MOD (0048H) bit map",
     "b5 CAP3IN | b4 CAP34M1 | b3 CAP34M0 | b2 CLE | b1 T5CLK1 | b0 T5CLK0 -- "
     "the same layout as T4MOD, clearing on the TREG7 match."),
    (101, "Figure 3.9 (10), TRUN (0020H) bit map",
     "b7 PRRUN | b5 T5RUN | b4 T4RUN | b3 T3RUN | b2 T2RUN | b1 T1RUN | "
     "b0 T0RUN, each '0: Stop & Clear, 1: Run (Count up)' -- so writing 0 to "
     "T4RUN/T5RUN must CLEAR the 16-bit up-counter, not just stop it."),
    (101, "Figure 3.9 (9), T45CR (003AH) bit map",
     "b3 PG1T | b2 PG0T | b1 DB6EN | b0 DB4EN.  It is the TREG4/TREG6 double-"
     "buffer enable plus the pattern-generator shift triggers -- NOT an "
     "operating-mode select.  Both Technics firmwares write 0x00, so every "
     "field is at its reset default and leaving T45CR undecoded is exact."),
    (12, "Table 3.3 (1), interrupt table",
     "INTTR4 : 16-bit timer4 (TREG4)  V=0050H  FFFF50H  hdma 14H\n"
     "        INTTR5 : 16-bit timer4 (TREG5)  V=0054H  FFFF54H  hdma 15H\n"
     "        INTTR6 : 16-bit timer5 (TREG6)  V=0058H  FFFF58H  hdma 16H\n"
     "        INTTR7 : 16-bit timer5 (TREG7)  V=005CH  FFFF5CH  hdma 17H\n"
     "        -- so the LOW register's match is INTTR4/INTTR6 and the HIGH "
     "register's is INTTR5/INTTR7, which is the pairing the code implements."),
]


def page_text(pdf, page):
    out = subprocess.run(
        ["pdftotext", "-layout", "-f", str(page), "-l", str(page), pdf, "-"],
        capture_output=True, text=True)
    return out.stdout


def main():
    pdf = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PDF
    if not os.path.exists(pdf):
        print("datasheet not found: %s" % pdf)
        print(__doc__.split("HOW TO RUN")[1])
        return 2

    got = hashlib.sha256(open(pdf, "rb").read()).hexdigest()
    print("pdf    : %s" % pdf)
    print("sha256 : %s  %s" % (got, "OK" if got == EXPECT_SHA else
                               "** DIFFERENT FILE -- page numbers may not line up **"))
    print()

    # Document page N is PDF page N in this file (verified: the printed folio
    # matches the PDF index throughout).
    ok = fail = 0
    for tag, page, needle, meaning in TEXT_CLAIMS:
        txt = page_text(pdf, page)
        flat = re.sub(r"[ \t]+", " ", txt)
        hit = needle in txt or re.sub(r"[ \t]+", " ", needle) in flat
        print("[%s] p.%-4d %-5s %s" % ("PASS" if hit else "FAIL", page, tag, meaning))
        if not hit:
            print("        looked for: %r" % needle)
            fail += 1
        else:
            ok += 1

    print()
    print("text-layer claims: %d PASS, %d FAIL" % (ok, fail))
    print()
    print("FIGURE CLAIMS -- scanned images, no text layer.  Transcribed 2026-08-25;")
    print("re-read them in a viewer at these pages if you doubt one:")
    for page, what, transcription in FIGURE_CLAIMS:
        print("  p.%-4d %s\n        %s" % (page, what, transcription))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
