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
