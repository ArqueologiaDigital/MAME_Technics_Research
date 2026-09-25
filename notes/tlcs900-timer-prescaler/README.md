# The TLCS-900 8-bit timer prescaler: what the right value is, and why MAME's differs

Settles the divergence left open after the ngp/ngpc regression
(mamedev/mame#16204, reverted by #16255): `tmp95c061` and `tmp95c063` use
prescaler shifts 7/9/11/15 while `tmp94c241` uses 3/5/7/11, for three devices
that are all `tlcs900h_device` with no per-variant clock division.

## Status: confirmed by users

The revert (#16255) is confirmed to have restored ngp/ngpc sound -- Felipe
relayed user reports on 2026-09-25 that it is back in good condition. That
matters for this note's argument, which otherwise rested only on the divisor
being byte-identical to what stood for twenty years: the calibrated value is now
empirically the one ngp/ngpc needs, not merely the one that used to be there.

Nobody involved in the fix ever reproduced the fault locally. The captures taken
here never got the BIOS to play (see `../dsp-noise-split/` for why a null from an
idle machine is not evidence), so the confirmation came from users running the
release.

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

**The overlay's own KN5000 disassembly settles what the earlier draft of this
note got wrong.** It named the consumer: on the sub-CPU, timer 3 is the task
scheduler's tick (`TaskSched_ConfigAndDispatch` stops timer 3, sets
`TREG3 = 0x1D`, sets the timer-3 interrupt level and restarts it), and
`T23MOD = 0x1D` selects φT256 — which matches the live reading from a running
kn5000 (`T8RUN` 0x02→0x0A, `T01MOD`/`T23MOD` = 0x1D).

That makes the tick period computable, and it decides the question:

| taps | KN5000 scheduler tick (TREG3 = 0x1D, φT256, fc = 20 MHz) |
|---|---|
| datasheet 3/5/7/11, as `tmp94c241` has | **~3.0 ms (337 Hz)** |
| calibrated 7/9/11/15, as the siblings have | ~47.5 ms (21 Hz) |

~3 ms is an ordinary RTOS tick; 47 ms is not. So `tmp94c241` is **right as it
stands**, and aligning it to its siblings — which this note's first draft
proposed, and which was implemented and then withdrawn — would have run the
KN5000's scheduler 16× slow.

So neither value is universally correct, and the divergence is not a mistake to
be tidied away:

- A divisor fixes two ratios at once: the timer's rate in emulated real time,
  and its rate relative to how fast the core retires instructions. With the
  cycle counts invented, the two cannot both be right.
- `tmp95c061`/`tmp95c063` keep the second, which is what ngp/ngpc music needs.
- `tmp94c241` keeps the first, which is what the KN5000's scheduler needs.
- **Change neither.** The real fix is honest instruction timings for
  `tlcs900h_device`; once `m_cycles` counts clocks, both ratios coincide and
  every variant takes the datasheet values. That has to land as one piece of
  work, never as a divisor change on its own.

What went into MAME from this is documentation only: the reasoning beside all
three variants, and named constants in `tmp95c063` in place of bare shifts. No
value moved — the timer functions are byte-identical to master with the
constants resolved.

## Sources

- TMP95C061B datasheet, Toshiba, 2011-01-26 — pages 91 and 94, captured here.
  `https://media.digikey.com/pdf/Data%20Sheets/Toshiba%20PDFs/TLCS-900,H%20Series.pdf`
  ⚠ image-only PDF: `pdftotext` yields nothing past the prelims. Render with
  `pdftoppm -png -r 150 -f 91 -l 91` and read the page.
- NeoPop/Mednafen timer constants: `mednafen/ngp/interrupt.h`, `interrupt.c`
  (libretro/beetle-ngp-libretro).
- FluBBaOfWard/TLCS900H, `TLCS900H.i`.
- nesdev forum thread 18326, "Toshiba TLCS900/H instruction timings?"

## Where the factor of 16 is NOT

Felipe asked whether the crystal might be divided before the internal clocks are
derived, which would explain the gap between the datasheet's phiT1 = fc/8 and the
fc/128 the ngp behaves as if it has. It would, but the evidence rules it out:

- **No on-chip clock gear.** The TMP95C061 datasheet has no programmable clock
  divider, no SYSCR, no "clock gear". Its only clock features are the RUN / IDLE
  / STOP standby modes and the oscillation warm-up counter.
- **phiT1 = fc/8 is confirmed three times over.** The prescaler table [3, p.91];
  the serial chapter independently giving phiT0 = fc/4, phiT2 = fc/16,
  phiT8 = fc/64, phiT32 = fc/256, which fits phiTn = fc/8n exactly; and the
  block diagram feeding the 9-bit prescaler from fc/4.
- **The selector really does mean phiT1.** "When T01MOD7,6 = 00 and
  T01MOD3,2 = 01, oT1 becomes the input of timer 1 (8 bit timer mode)" -- so
  MAME's selector-to-tap mapping is right, and T23MOD = 0x04 really is phiT1.
- **The clock really is 6.144 MHz.** Published NGP hardware summaries give the
  TLCS-900H at 6.144 MHz and the Z80 at 3.072 MHz, and ngp.cpp's own screen
  timing corroborates it: 6.144 MHz / (515 x 199) = 59.95 Hz.

So fc is right, the tap is right, and the tap's meaning is right -- yet
fc/8 with TREG3 = 0x62 gives 7837 Hz where ~490 Hz is what sounds correct.

## Where it therefore must be

Not in the clock tree, and not in the prescaler. What remains is the path
between the timer and the sound:

- MAME raises the Z80 interrupt on the **rising edge of TO3**
  (`ngp_state::tlcs900_porta`), and TFF3 toggles once per timer-3 match, so the
  Z80 sees match/2. If the hardware divides further between TFF3 and the Z80,
  that is where the missing factor lives. TFFCR is written 0x0C, 0xFC, 0xCC and
  0xB0 by the BIOS and is only partly modelled.
- Or the ngp BIOS's rate routine does not mean what its constants suggest. The
  reading here -- that dividing a requested period by 20.48 us implies one phiT1
  count is 20.48 us -- is an inference from `mul WA,1000; div WA,0x5000`, not a
  proven unit.

Settling it needs real hardware (measure the Z80 interrupt rate on a running
console) or NGP-specific documentation of the TO3 path. Until then the shipped
divisors preserve the rates that are known to sound right, and the submitted
change does not depend on the answer: it changes the CPU's unit, not any timer.
