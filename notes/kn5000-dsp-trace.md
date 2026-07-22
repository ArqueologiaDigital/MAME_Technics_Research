# NEC uPD6383GF — a pointer-arithmetic TRACE, settling the wrap and the modes, and
# reporting the origin as still-unpinned

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-23.
Tool: `tools/kn5000_dsp_trace.py` (standalone replay; imports `kn5000_dsp_params.py`
only for the host map). Follows `kn5000-dsp-addressing.md`, which proved the **relative**
rule and listed three residuals. This note traces those residuals and reports:

* **Q1 — the absolute ORIGIN: STILL NOT PINNED.** A trace from every header-loaded
  register misses every family's host block; the core is left un-edited, on purpose.
* **Q2 — the WRAP modulus: 256, INFERRED and now with a MEASURED lower bound > 0xCF.**
* **Q3 — MODES 3/4/5/6: characterised.** Only mode 6's `addr8` carries operand
  information (the table selector); modes 3, 4, 5 freeze `addr8` at a constant.

Claims are tagged **MEASURED**, **INFERRED**, **PROVEN BY CONSTRUCTION**, or **SPECULATIVE**.
**No audio path was added; the core is still instantiated DISABLED; the KN5000 driver was
not touched.**

Reproduce:

```
python3 tools/kn5000_dsp_extract.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
python3 tools/kn5000_dsp_trace.py
```

## The instrument, and why it is a standalone replay

The task offered two forms: an in-core `trace_program(unit)` or a standalone Python replay
over the extracted images. **The Python replay is the correct instrument here, and the
in-core trace would add nothing**, because:

* the origin/wrap/mode questions are all about *pointer arithmetic over the extracted
  program images*, which are already byte-identical to the live I-RAM
  (`kn5000-dsp-core-draft.md` §3, re-verified: header 60/60, both bodies, stub except the
  two documented patch words 64/71);
* the decoded subset the core executes is exactly the six forms of `-core-draft.md` §1 plus
  the pointer post-increment — it does **not** model which of the chip's six pointer
  registers each `lo12` route selects, so an in-core single-step would reproduce the same
  relative walk this replay computes and reveal no more about the absolute base.

So the core was left untouched (the safety model is preserved trivially: zero core edits),
and the trace is `tools/kn5000_dsp_trace.py`.

---

## Q1 — THE ABSOLUTE ORIGIN: **NOT PINNED** (the core stays un-edited)

The task's experiment, executed: trace each family from each register the header actually
loads, and watch where the pointer sits when the first band/section begins.

### EQ (algo 39, unit 0) — the strong host check, and it excludes all three registers

```
  host writes biquad STATE at {64,68,6C,70,74} (5 bands, stride 4)
  band-motif starts at words [5,14,23,32,41 | 59,68,77,86,95]

  reg 821 = 0x70  ->  band cells BB BF C3 C7 CB   0/5 host state
  reg 827 = 0x6C  ->  band cells B7 BB BF C3 C7   0/5 host state
  reg 825 = 0x25  ->  band cells 70 74 78 7C 80   0/5 host state
  REQUIRED start value to land 5/5 : 0x19   (NONE of 0x70/0x6C/0x25)
```

The **stride is +4, origin-free, and it matches the host stride exactly** (the strongest
external check in the project, unchanged). But the **absolute** base that lands channel-0's
five bands on the host state block `{64,68,6C,70,74}` is `0x19`, and **`0x19` is none of the
three registers the header loads for unit 0**. Traced from the registers that actually exist,
the EQ misses its own host block 0/5 on every one. **MEASURED.**

I tried to rescue it with hypothesis (b) of `-addressing.md` §5 — that a pre-motif word is
inert, shifting the base — and it **fails by construction**: the biquad's within-band walk
`w5..w13` nets exactly `+4` only if every `lo12=0x407` word moves the pointer (`w12 =
212.A.FF.407` contributes the `−1` that closes the band). Making a `0x407` word inert to shift
the origin breaks the `+4` stride the same check depends on. So hypothesis (b) is **dead**;
what survives is (a), a pointer register the header does not load. **PROVEN BY CONSTRUCTION
that (b) cannot supply 0x19.**

### REVERB (algo 16, unit 1) — a weak, non-confirming coincidence

```
  host writes reverb STATE at {86,97,9E,A6,A9,AA,AB,AC,AF,B0,B1,B2}
  class-2/A touched cells: 14 distinct
  best origin offset: 6/12 host hits at ~0xA6
  reg 821=0x50 -> 0/12    reg 827=0x64 -> 3/12    reg 825=0x25 -> 0/12
```

The reverb's best host overlap (6 of 12) sits at an origin of ~`0xA6`, again **no header
register**. 6/12 over 14 cells and 256 candidate offsets is only marginally above chance, so
this is **not** a second confirming anchor — it is a weak lead that happens to point at the
reverb's own high bank. **MEASURED (and reported as weak).**

### PHASER (algo 5, unit 0) — no host check exists

The shared all-pass tap resolves to the single cell `0x76` (origin 0x70), but `0x76` is a
**static coefficient**, absent from the phaser host map by design (`-addressing.md` §3-F1).
The phaser therefore offers **no** host-write/body-read coincidence to pin an origin against.

### The verdict, and why no unified rule closes it

The EQ wants a start of `0x19` (offset `−0x57` from register 821); the reverb wants ~`0xA6`
(offset `+0x56` from register 821). **These are not a common constant from any shared
register**, so there is no "register − K" rule that unifies the two families onto the
header's registers. The two honest surviving readings are exactly the two `-addressing.md`
§5 named, now sharpened:

1. **a per-effect FOURTH pointer register** (the chip has six: CP/DP/BP1/BP2/PR1/PR2), loaded
   for each effect's state block by a word this project does not decode as a load — consistent
   with the census finding zero `0x821`-family loads in the bodies, because the load would be
   in a *different* `lo12` route;
2. **a per-effect descriptor-relative base**: the host writes state at `descriptor_base +
   T1_address` (`-parameters.md` §7), and the body's pointer could be initialised to the same
   per-effect base rather than a per-unit constant.

**This decoded-subset trace cannot separate them**, because both live in register-selection /
per-effect setup that the six decoded forms do not cover. **ABSOLUTE ADDRESSING IS THEREFORE
NOT IMPLEMENTED IN THE CORE** — implementing it on an unverified origin is precisely the
"plausible-but-wrong" trap the disabled-core discipline exists to avoid (`-pointer.md` §5).

**The exact experiment that separates the survivors** (needs an ENABLED core or real
hardware, both outside this trace's remit): enter the EQ body with the core running and read
the C-RAM pointer register when the first band section (`word 5`) executes. If it reads `0x19`
from a register the header never wrote, reading (1) is confirmed and that register is the
fourth pointer; if the header's `0x821` has been re-initialised to a per-effect base, reading
(2) is confirmed. One number, from the address bus, ends it — exactly as `-pointer.md` §8
predicted for this residual.

---

## Q2 — THE WRAP MODULUS: **256, INFERRED, with a MEASURED lower bound**

```
  MEASURED: firmware pokes absolute DSP RAM addresses up to 0xCF (207).
    written > 0x7F: 81 84 86 89 8E 90 91 97 9E A1 A3 A6 A9 AA AB AC AF B0 B1 B2 B6 B7 B8 CF
  A pointer that wrapped at 128 could never reach 0xCF -> modulus STRICTLY > 207.
```

This is the measurement `-addressing.md` §4 lacked. The firmware writes real, absolute DSP
RAM addresses (`-parameters.md` §2: `NN` in `801.0.NN.821` is computed as an address), and the
largest is `0xCF = 207`. A pointer register that wrapped mod 128 could never form an address
`≥ 0x80`, yet the machine demonstrably writes and reads up to `0xCF`. **mod-128 is ruled out by
measurement.** Given the 8-bit `addr8` field and the documented 256×24 C-RAM/D-RAM, the modulus
is **256**.

It remains **INFERRED, not directly MEASURED**: the reverb is the program whose arithmetic
crosses the boundary (excursion `−176..80` under origin 0x50, a 256-cell span), but because the
origin is unpinned (Q1) no single reverb word's absolute address has been independently
confirmed straddling `255→0`. So 256 is fixed by the field width + the RAM size + the measured
`> 207` floor, not by observing a wrap. One address-bus trace from an enabled core confirms it
directly.

---

## Q3 — MODES 3/4/5/6: **characterised** (only mode 6 carries an operand)

`class4 = bit3(mult) ‖ bits[2:0](mode)`. Modes 2/A move the pointer; 3/4/5/6 freeze it, so
their `addr8` means something else. Measured over the 91 valid images:

| mode | n | `addr8` | `lo12` | prev→this→next `lo12` | reading |
|---|---|---|---|---|---|
| **3** | 33 | **frozen 0x20** (32/33) | `44C` | `1C0 → 44C → 041` | a **constant modulation / envelope offset**; the read `1C0` and immediate `041` bracket it (the `C40.3.20.44C` "envelope detector" word). `addr8` is **not** an index. **INFERRED** |
| **4** | 54 | **frozen 0x01** | `1CE` | `4CD → 1CE → 1CE` | the **third word of the 3-word table-lookup idiom** (`012.4.01.1CE`), always after the class-6 selector. `addr8 = 1` is the constant fetch/apply step, **not** an index. **MEASURED (position)** |
| **5** | 42 | **always 0x00** (unused) | `647` | `839 → 647 → 688` | a **fixed-function biquad/filter step**; `addr8` carries **no** information. **INFERRED** |
| **6** | 54 | **VARIES {18,28,1E,20,1A}** | `4CD`/`407` | `C63 → 4CD → 1CE` | the **middle word of the table-lookup idiom**; `addr8` is the **TABLE SELECTOR** (indexes a lookup table — LFO waveform / distortion curve). **MEASURED** |

The clean result: **of the four frozen-pointer modes, only mode 6's `addr8` carries operand
information** (it indexes a table). Modes 3, 4 and 5 pin `addr8` at a constant (0x20 / 0x01 /
0x00), so "the pointer does not move" here does **not** mean "`addr8` indexes something else" —
it means `addr8` is a fixed micro-op field. This confirms and firms up the established readings
(class 6 = table selector; class 4 = part of the same idiom; class 3 = modulation offset) and
adds mode 5 (previously only named) as an operand-less fixed step.

Mode 6's five selector values `{0x18, 0x28, 0x1E, 0x20, 0x1A}` are the concrete table indices
the 25 LFO/distortion images use — the next lead for decoding *which* table each selects, which
needs the coefficient-bank contents, not more field statistics.

---

## Coverage

No new body word is decoded — Q1 and Q2 are machine-state facts about the `class4`/`addr8`
*fields* (already counted), and Q3 pins the *meaning* of `addr8` in four modes without adding a
`lo12`/`hi12` vocabulary entry. Honest scoped source coverage is **unchanged at 18.3 %
(545/2974)**, per `-addressing.md` §8. Counting a field-property or a mode characterisation as a
word decode would be the over-claim the whole series refuses.

## What still needs real hardware (or an enabled core)

1. **The absolute origin (Q1).** One C-RAM address-bus read at the EQ's first band section
   separates "fourth pointer register" from "per-effect descriptor base". Until then, absolute
   addressing stays out of the core.
2. **The wrap modulus, directly (Q2).** The same address-bus trace confirms 256 by observing a
   `255→0` wrap; the current value is inferred + bounded, not observed.
3. **Mode 6's table contents (Q3).** The five selector values are known; the tables they index
   are in the coefficient bank and are not yet read.
