# Refactoring the TLCS-900 cores off NeoPop's invented timings

Goal: make `m_cycles` mean something, so the prescaler divisors stop being
per-machine calibration and every variant can take the datasheet taps.

## The two facts the refactor rests on

**1 state = 2/fc.** Stated three ways in the TMP95C061 datasheet (bitsavers
edition, which unlike the 2011 one has a text layer):

- "One cycle clock divided by 2 oscillation frequency is called 1 state."
- "for at least 10 system clocks (10 states: 800ns with a 25MHz" → 80 ns/state
- watchdog "8 to 20 states (640ns to 1.6µs @ 25MHz)" → 80 ns/state
- "Minimum instruction execution time - 160ns at 25MHz" → the fastest
  instruction is 2 states

So a state is one φ period, φ = fc/2. MAME should count states and override
`execute_clocks_to_cycles()` to divide by two, rather than pretend cycles are fc
clocks.

**The 900 instruction timings apply to 900/H.** `TLCS900hv-is.pdf` page 1,
"900, 900/L, 900/H CPU Core Different Points", lists every difference between
the three cores: operating mode, register mode, interrupt vector formula, XNSP,
INTNEST, operating voltage. Instruction timing is not among them. Cross-check:
the /H datasheet's 2-state minimum matches the minimum State in the 900 list.

## Where the data is

`http://www.bitsavers.org/components/toshiba/_dataSheet/TLCS900hv-is.pdf`
(image-only; bitsavers 403s a default curl user-agent, send a browser one).

- **pages 165-173** — "Instruction Lists of 900 (1/10)".."(9/10)", grouped by
  function. Columns: Group, Size, Mnemonic, Codes (hex.), Function, SZHVNC,
  Length (byte), **State**. State carries three numbers: byte, word, long word.
- **page 174** — "(10) Addressing mode", the `+M` adders the other pages refer to.
- Appendix C from page 175 — opcode code maps, useful for tying mnemonics back
  to MAME's opcode-indexed tables.

Regenerate the working images with:

```
pdftoppm -png -r 200 -f 165 -l 174 TLCS900hv-is.pdf pages/p
```

## Plan

1. Transcribe pages 165-174 into a machine-readable table (mnemonic, operand
   form, opcode pattern, length, states per size). **This phase.**
2. Map that onto MAME's opcode-indexed tables in `900tbl.hxx`, which are keyed
   by opcode byte across eight sub-tables.
3. Implement together, never separately: state-based cycle counts,
   `execute_clocks_to_cycles()` dividing by 2, and the prescaler taps becoming
   the datasheet's in every variant (φT1 = fc/8 = 4 states → shift 2, φT4 → 4,
   φT16 → 6, φT256 → 10).
4. Verify against the machines that actually constrain it: ngp/ngpc sound, the
   KN5000 scheduler tick landing near 3 ms, and that namcos10/naomi/taitopjc/
   taitotz still run.

## Why the divisors cannot change before step 3

See README.md in this directory. Each variant currently keeps a different one of
two ratios that cannot both be right while the cycle counts are invented.

---

## Result: the refactor is right in isolation and not shippable as one commit

Implemented on `tlcs900-real-timings` (cycles become states via
`execute_clocks_to_cycles`, 185 opcodes corrected, all three variants taking the
datasheet taps). It builds, validates, boots all five machines — and **ngp sound
plays far too fast**, confirmed by ear.

### What the NGP actually asks for

Tapping the TMP95C061's write-only timer registers while the BIOS runs
(`ngp/ngp_timer_log.lua`) shows it programming, at reset and not changing after:

```
TRUN   <- 80   prescaler on
T23MOD <- 04   timer 3 clock = phiT1
TREG3  <- 62   compare = 98
TRUN   <- 88   timer 3 running
```

so the tick is phiT1/98:

| | φT1 | IRQ | verdict |
|---|---|---|---|
| master | 48 kHz | 490 Hz | sounds right |
| refactor | 768 kHz | 7837 Hz | 16× too fast |
| hardware (fc/8 at fc = 6.144 MHz) | 768 kHz | 7837 Hz | — |

**The refactor's rate is the hardware rate.** And for the known-good 490 Hz to
be hardware-correct, fc would have to be 384 kHz, which is not a real NGP clock.
So master is not faithful either; it is 16× slow on the timer and about 2× fast
on the CPU, and the NGP emulation as a whole has been tuned around that.

### Why it cannot ship

Making the TLCS-900 honest changes CPU speed for every machine using it, and at
least ngp has other clocks — the Z80 at fc/2, the T6W28 at fc/2, the K1GE at fc
— chosen while the CPU ran twice too fast. Correcting one end alone moves the
machine further from hardware, not closer. The same risk applies unexamined to
namcos10, namcond1, namcops2, naomi, dvd-n5xx, kkcount, taitopjc and taitotz.

### What would finish it

1. Establish the NGP's true sound-engine rate from hardware or a
   known-faithful reference, rather than from what MAME currently does.
2. If 7837 Hz is right, find what in the ngp driver compensates for the old 2×
   CPU and fix it in the same change.
3. Only then land the core change, with each affected driver tested.

Steps 1 and 2 are NGP emulation work, not TLCS-900 work, and they gate the rest.

### What is safe to take from this now

- The transcribed timings and the 100% join (`timing/`), which stand on their own.
- The finding that NeoPop's counts are the databook's — 2599 of 2784 exact — so
  the table was never the problem; the unit was.
- The documentation-only change on `tlcs900-prescaler-doc`, which records why the
  divisors differ and changes no behaviour.
