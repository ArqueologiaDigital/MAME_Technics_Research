# K4 — the coefficient-cursor rebase (pointer into the disasm tree)

**NEC uPD6383GF-3BA (Technics SX-KN5000, IC311).** 2026-07-26.

The full write-up lives with the microcode it explains:
**`kn5000-roms-disasm/dsp/analysis/k4-cursor.md`**, reproducible with
`python3 dsp/tools/k4_cursor.py`. This file exists so that the notes tree carries
the **correction** and the **constraints on other people's items**.

## The correction — this note tree contains a falsified claim

`kn5000-dsp-cursor-general.md` §1.2, headline **8**:

> "★ Unit 1 has a coefficient-space base of `0x80`. … **INFERRED:** the two
> resident effect units are given the two halves of the 256-word coefficient RAM,
> unit 0 low and unit 1 from `0x80`."

**FALSIFIED as a C-RAM statement.** C-RAM is one flat 256-cell space and it is not
halved at `0x80`:

```
   0x00..0x4F  unit-0 effect coefficient bank    (79/79 unit-0 parameter streams
                                                  say ldptr #$00; max cell 0x2C)
   0x50..0x6F  RESIDENT TABLE A, 32 cells = (32+k)*0x400
   0x70..0x8B  RESIDENT TABLE B, 28 cells = min(1214k, 32767)      <- STRADDLES 0x80
   0x8C..0x8F  never written
   0x90..0xB5  unit-1 effect coefficient bank    (12/12 unit-1 streams:
                                                  ldptr #$90 +30, ldptr #$AE +7)
   0xB6..0xFF  never written
```

The 60-cell table region is a **literal uC-IF blob in the Sub CPU ROM at
`0x01E6BE`** (PROVEN BY CONSTRUCTION; it matches cold-boot capture transfers 4…10
byte for byte) and **no parameter stream ever writes it** (0 of 91). `0x90` is
simply the first 16-aligned cell after it, and the base is a **software**
allocation — a literal in each algorithm's parameter script, with `LABEL_0387E6`
building each individually-addressed poke's destination as an 8-bit **add**.

**What the note actually saw is real, in a different space.** The `0x06` → `0x86`
displacement of effect-level opcode `0x63` is one instance of a systematic pattern
in the **class-1 register file**: over the 91 well-formed parameter streams the
host's `000.1.NN.000` register selects are 368 packets / 23 distinct `NN`, **all
`< 0x80`**, in unit-0 streams and 60 packets / 5 distinct `NN`, **all `≥ 0x80`**,
in unit-1 streams, with **5 of 5** unit-1 numbers a unit-0 number `+ 0x80`
(`85 87 8A 94 D0` ↔ `05 07 0A 14 50`). The boot blob writes the matched pair
`000.1.06.000` / `000.1.86.000` back to back. **MEASURED** (428 packets, 100 %)
**+ PROVEN BY CONSTRUCTION.** Two 256-cell spaces were conflated.

This also resolves **K6**'s "class-1 `addr8` splits on bit 7" lead
(`dsp-k6-input-stage.md`): the split is real and it is the **effect unit**, but the
delay-DRAM sub-ops `0x20/0x30/0x60` are discriminated from register addresses by
**`hi12`** (the `0x8xx`/`0x9xx` escapes), not by `addr8` bit 7.

## Constraints on the ALU / core work

1. ★ **Only `class4 == 0xA` advances the coefficient cursor; `class4 == 8` sets
   word bit 23 but must not advance it.** FORCED by the PARAMETRIC EQ: 10 class-8
   words (`804.8.16.415`, one per biquad section) sit inside a cursor map that is
   proven to the bit — 6 cells per band, 60/60 named, transfer function reproduced
   at max|err| = 0. If class 8 advanced, band *k* would begin at cell `7k`.
   Bit 23 is a **fetch** enable; the **advance** is `class4 == 0xA`.
2. **Do not model `801.0.NN.821` as writing the coefficient cursor.** Its three
   in-program immediates are `0x70`, `0x50`, `0x90`; the bases the bodies need are
   `0x00` and `0x90`. The falsification is independent of which frame order is
   right. (K3, `analysis/k3-pointers.md` item F, has the sharper argument.)
3. **A body's cursor base is an external input**, `0x00` at I-RAM 84 and `0x90` at
   I-RAM 200; it is not derivable from the body's own words.
4. **Preload C-RAM `0x50..0x8B`** from the ROM blob at `0x01E6BE` (or replay the
   boot script). A core that starts with C-RAM zeroed and only replays parameter
   streams reads zeros for every table lookup.

## What K4 leaves open

*Which* instruction copies the per-unit base into the cursor — `800.1.60.00B`
(exactly twice in the machine, once at offset +4 of each per-unit setup block, and
nowhere else) versus the unit-tagged transfer word — and *who* loads that base
register. Three resolutions are enumerated in `k4-cursor.md` §5.2; the cheapest
static test is **disassembling the six uC-IF `op 0..5` handlers** at
`0x03C32E + OFFSETS_14739[op]`, which K4 promotes on the worklist for this reason.
Nothing in K4 needs hardware.
