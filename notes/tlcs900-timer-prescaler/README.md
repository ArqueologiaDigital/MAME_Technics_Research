# The TLCS-900 8-bit timer prescaler: what the right value is, and why MAME's differs

Settles the divergence left open after the ngp/ngpc regression
(mamedev/mame#16204, reverted by #16255): `tmp95c061` and `tmp95c063` use
prescaler shifts 7/9/11/15 while `tmp94c241` uses 3/5/7/11, for three devices
that are all `tlcs900h_device` with no per-variant clock division.

## The hardware value is not in doubt

TMP95C061B datasheet, page 91 (`tmp95c061b-p91-prescaler.png`), the
manufacturer's own table with worked numbers:

| Clock | at fc = 25 MHz |
|---|---|
| φT1 **(8/fc)** | 320 ns |
| φT4 **(32/fc)** | 1.28 µs |
| φT16 **(128/fc)** | 5.12 µs |
| φT256 **(2048/fc)** | 81.92 µs |

Block diagram on the same page: `oscillation circuit → fc → 1/4 → 9-bit
prescaler`, taps at prescaler bits 0..8 giving φT1, φT2, φT4, φT8, φT16, φT32
… φT256. The two-phase clock φ1/φ2 comes off a *separate* 1/2 divider and is
not what feeds the prescaler.

Page 94 (`tmp95c061b-p94-t01mod.png`) confirms the selector encoding MAME
implements: timer 0 takes 00=TI0, 01=φT1, 10=φT4, 11=φT16; timer 1 takes
00=TO0TRG, 01=φT1, 10=φT16, 11=φT256.

**So φT1 = fc/8, φT4 = fc/32, φT16 = fc/128, φT256 = fc/2048 — shifts 3/5/7/11
against a counter of real fc clocks.** An independent TLCS-900H core
(FluBBaOfWard) agrees: `TIMER_T1_RATE = 8 × BASE` with `BASE = 16 = 1 CPU
cycle`.

## Why MAME cannot use it

`m_timer_pre` does not count fc clocks. It accumulates `m_cycles`, the
instruction cycle counts, and those came from NeoPop, whose author says
plainly:

> "I can at least confirm that the instruction timings are pretty much made up
> and have no bearing on the real hardware … there's no compensation for the
> different addressing modes, etc."
> — nesdev forum thread 18326

The arithmetic closes exactly:

| | T1 divisor |
|---|---|
| NeoPop (`TIMER_T1_RATE = 8 × TIMER_BASE_RATE`, base 32) | 256 |
| MAME, shifts 7/9/11/15 | 128 |
| datasheet, in real fc clocks | 8 |

MAME's 128 is exactly half NeoPop's 256, matching MAME having halved every
instruction count (NOP is 2 in NeoPop, 1 in MAME). So MAME's long-standing
value *is* NeoPop's calibration, carried over faithfully. And 128/8 = **16**:
the shift encodes a 16× compensation for instruction timings that run 16× fast.

**The shift is a calibration constant, not a hardware constant.** Setting it to
the datasheet value while the instruction timings remain fabricated removes the
compensation and leaves the timer 16× fast relative to the CPU — which is what
garbled ngp/ngpc music.

## What the correct implementation is

1. **Today:** 7/9/11/15 on every TLCS-900/H variant. That keeps the timer
   consistent with the CPU speed the software actually perceives, which is the
   only thing that matters while the timings are invented.
2. **`tmp94c241` is currently the odd one out** and, by the same arithmetic,
   the KN5000's 8-bit timers run 16× fast relative to its CPU. This is a
   prediction from the shared instruction table, not an observation — the
   KN5000 was not run for this note. Worth confirming before changing it.
3. **The real fix** is honest instruction timings: give `tlcs900h_device` cycle
   counts in real fc clocks, then *all three* variants become 3/5/7/11 and the
   calibration disappears. That is a large, separately testable piece of work,
   and it must be done together with the shift change, never before it.

## Sources

- TMP95C061B datasheet, Toshiba, 2011-01-26 — pages 91 and 94, captured here.
  `https://media.digikey.com/pdf/Data%20Sheets/Toshiba%20PDFs/TLCS-900,H%20Series.pdf`
  ⚠ image-only PDF: `pdftotext` yields nothing past the prelims. Render with
  `pdftoppm -png -r 150 -f 91 -l 91` and read the page.
- NeoPop/Mednafen timer constants: `mednafen/ngp/interrupt.h`, `interrupt.c`
  (libretro/beetle-ngp-libretro).
- FluBBaOfWard/TLCS900H, `TLCS900H.i`.
- nesdev forum thread 18326, "Toshiba TLCS900/H instruction timings?"
