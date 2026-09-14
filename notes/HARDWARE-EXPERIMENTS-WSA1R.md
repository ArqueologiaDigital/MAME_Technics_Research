# Experiments on the SX-WSA1R — what the real hardware can settle

**Companion to `HARDWARE-QUESTIONS-PENDING-FELIPE.md`.** That file is *parked*: the KN5000 is in
storage abroad. This one is **live** — Felipe has the WSA1R, and it carries **three**
`D6383GF-3BA` DSPs (IC5, IC6, IC30), the same part as the KN5000's IC311 and the KN1500's IC3.

Written 2026-09-14, when the decode queue ran out of ROM-side anchors: coverage is **1397
undecoded of 7273 pooled words (80.8 %)** and every large remaining block is shut *on the evidence
the ROMs contain*, not for want of effort.

## The three constraints, from Felipe, that shape every design below

1. **No audio input.** All excitation must come from the machine's own tone generator. Nothing here
   asks you to feed a signal in.
2. **No digital output** — the machine's own jacks are analogue only. So **bit-exact capture is off
   the table for everything in this file**, and nothing below depends on it. Every measurement here
   is *parametric* — a rate, a delay in samples, a curve, a decay time — and those survive the DAC
   intact.
   ★ **UPDATED 2026-09-15, and it is cheaper than "buy the extension board".** The board is the
   **SY-ES1** (S/PDIF, 44.1 kHz, 20-bit), and it is *passive*: no ROM, no bus buffer, no address
   decoder, so the firmware cannot even detect it. Everything that makes it work is already on
   connector **CN14** of a stock machine — `MCK`, `BCK`, `LRCK` plus three independent data lanes.
   A four-wire tap into any I²S receiver gets the same bits without sourcing two discontinued
   parts. ★★ And tap `SUBOUT2`/`SUBOUT3` (CN14 pins 6/7), not the main output: those are IC30's
   `DO2`/`DO3`, **program-DSP outputs with nothing summed into them that a stock machine never
   listens to** — the un-mixed wet signal these experiments have had to do without.
   ⚠ Unchecked: whether the shipped microprogram ever writes `DO2`/`DO3`. Details in
   `kn5000-roms-disasm/dsp/hardware/upd6383-pinout.md`.
3. **MIDI in and out.** Worth more than it looks: it gives *repeatable* excitation (exact note,
   exact velocity, exact timing, no hand-playing), and the machine will dump its own state.

⚠ **What this cannot do, stated up front:** it cannot validate the emulator bit-exactly, and it
cannot touch the **bit-11 encoding** block (169 words). Those are control words — register and
pointer loads — and no audio measurement sees them. Anything claiming otherwise would be an
inference dressed as a measurement.

---

## Tier 0 — five minutes, no instruments, highest value per effort

### E0.1 — Photograph the three DSP markings, and the delay DRAM's part number

**What to do:** with the unit **unplugged**, open it and photograph the full top marking of IC5,
IC6 and IC30, and of the memory chips sitting next to them. Straight on, in focus, whole package
including the date/lot line.

**Why it is asked.** The DSP part is recorded as `D6383GF-3BA` from the schematic, and a dealer
listing ties `UPD6383GF-3BA` to house number `GGC1163` — but nobody in this project has read the
actual silkscreen. More importantly, the delay arena's RAM is **inferred** to be an
`M5M44260AJ-7S`, and `STRATEGIC-REVIEW-2026-07-31` item **X1** records that *no search was ever
run* for its datasheet and calls it "the cheapest external item in the project".

**What the answer changes.** The delay RAM's real organisation (page size, refresh, word width)
turns a load-bearing *inference* about the delay arena into a measured fact. It bears on the
delay-escape words and on `r3-delaydram.md`'s region arithmetic. And if any chip near the DSPs is a
**µPD6382** (the 19-bit sibling), that is a find in its own right — the 638x family is absent from
every NEC databook on bitsavers.

⚠ Mains voltages and a rare instrument. If you would rather not open it, skip this one; everything
below works with the case closed.

### E0.2 — Capture a SysEx bulk dump

**What to do:** connect MIDI OUT to a computer, select **`SYSEX BULK DUMP`** from the machine's own
menu, and save the raw byte stream. Do it twice: once on a factory-ish state, once after changing
**one** effect parameter by **one** step, and keep both files.

**Why it is asked.** The firmware's SysEx parser accepts two identifiers — `0x7E` (MIDI Universal
Non-Real Time) and `0x50` (a manufacturer ID) — and `MIDI_RX_SysExData` buffers accepted messages
through `0xF41E3C`, whose body is **not yet converted**. So the project knows the machine *has* a
SysEx command set and does not yet know what it means. A dump is the machine describing its own
state layout, for free, with no risk.

**What the answer changes.** Two dumps differing by one parameter step localise that parameter to a
byte, which is the start of a **parameter → coefficient** map. That map is the missing half of
several open questions: the effect parameters are what the firmware turns into the C-RAM
coefficients the DSP multiplies by. It also tells us whether bulk *load* exists, which would let us
set values the front panel cannot reach.

---

## Tier 1 — audio recordings, ranked by what they unblock

Method rules first; they are the project's own and skipping them has cost real work.

* **RULE 12 — a DSP test with no notes playing is not a test.** Drive every recording from MIDI:
  one fixed note, one fixed velocity, held for a stated duration.
* **RULE 13 — a difference from silence is not a signal.** Every take needs a **no-stimulus
  window**: record 5 s of the machine idle, at the same gain, before the note.
* **Record the control.** `eff53_no_operation` is a real program in this machine and is
  byte-identical to a pass-through. Record it at the same settings as every effect you capture. It
  is the dry reference, and it is free.
* **One variable per take.** Change one parameter, one step, and note it in the filename.
* **Don't touch the output gain** between takes in a set, and stay well clear of clipping.
* **96 kHz / 24-bit** if your interface offers it — not because the DSP runs there, but so that
  stair-stepping and aliasing artefacts are not smeared by the anti-alias filter. Note the rate.
* **Filenames:** `E<n>_<effect>_<param>=<value>_<take>.wav`, plus a plain-text `notes.txt` saying
  what every setting was. A recording whose settings are not written down is not usable.

### E1 — ★★★★★ LFO rate and waveform (CHORUS / VIBRATO / FLANGER)

**What to do:** hold one mid-range note for **at least 60 seconds** through
`eff11_vibrato`, then `eff08_flanger`, then a chorus-bearing program. Do it at the **lowest** LFO
rate setting, the middle, and the highest — three takes each, 60 s each. Then repeat the lowest-rate
take at two different DEPTH settings.

**Why it is asked.** This is the single most informative measurement available, because it probes
the one question that blocks the most words. The class-6 table lookup — `SRC 0x13` / class 6, **171
words** — reads a 24-entry table in the DSP's register file at `0x1D`. The project has recovered
that table's contents (a sine, matched to 1 LSB) and its length, but **not how it is indexed**: six
candidate index forms were built and all six refused. And §179 found the first **eight entries
repeated** after the 24, which is what a *windowed* read needs — i.e. interpolation between
entries rather than a bare step.

A 60-second recording settles both halves:

* **Rate.** The ROM anchors the increment at **114 per frame**, which predicts **0.5993 Hz** for the
  KN5000's LFO. Measuring the WSA1R's actual modulation rate to four significant figures tests
  whether the same constant governs this product. ⚠ The 114 is *KN5000-anchored*; a different value
  here is a finding, not an error.
* **Waveform.** Demodulate the pitch (vibrato) or comb-notch (flanger) motion and look at the
  modulation shape. **A 24-entry table read with a bare step shows 24 visible stairs per cycle and
  harmonics at 24 × the LFO rate. An interpolated/windowed read does not.** That is a direct,
  decisive test of the wrap-guard reading, on a quantity the DAC cannot hide.

**What the answer changes.** If the steps are visible, the index is a plain integer and the eight
spare entries mean something else; if they are absent, the read is windowed and the index has a
fractional part — which reframes all six refuted arms at once. Either way the 171 words stop being
blocked on "we cannot see the index".

### E2 — ★★★★ Delay times, to the sample (SINGLE / MULTI TAP / MANUAL DELAY)

**What to do:** a **short, sharp** note (shortest bright patch, full velocity) through
`eff23_single_delay`, `eff24_multi_tap_delay` and `eff25_manual_delay`. Record 10 s so several
repeats are captured. Then sweep the delay-time parameter across its range in a few steps, one take
each, noting the displayed value.

**Why it is asked.** The gap between the direct note and each echo is a **delay length in samples**,
an integer, readable to sample accuracy from a clean analogue recording. The delay arena's
organisation is currently inference (see E0.1), and the KN5000 file's Q4 asks a version of this
question that cannot be answered there.

**What the answer changes.** It pins the delay-line base addresses and strides against the
`r3-delaydram.md` arithmetic, and the multi-tap spacing exposes how many taps the program really
runs versus how many the listing claims. It also gives the *parameter → samples* transfer, which
is the same parameter-to-coefficient map E0.2 starts.

### E3 — ★★★★ The waveshaper's transfer curve (DISTORTION / OVERDRIVE / FUZZ)

**What to do:** the cleanest sine-like patch you have, one note, swept slowly from the quietest to
the loudest you can achieve **by MIDI velocity** (a ramp of ~20 notes at rising velocity, or one
note under a slow swell if the patch allows). Through `eff00_distortion`, then `eff01_overdrive`,
then `eff02_fuzz`. Then repeat `eff00` at two DRIVE settings.

**Why it is asked.** There is a **concrete numerical contradiction** waiting on this. The class-6
word's `addr8` field is the table's entry count, and at the waveshaper it reads **40**
(`0x28`) — but the register-file window the table lives in is only **32 cells** (`0x1D..0x3C`), and
the 32 recovered entries are odd-symmetric about an exact zero with saturation at ±0.49. Forty
entries do not fit in thirty-two cells.

**What the answer changes.** Plotting output against input recovers the clip curve directly. If the
measured curve has 32 distinguishable segments the `addr8 = 40` reading is wrong and `addr8` is not
a pure entry count; if it has 40, the table is not where the project thinks it is. Either outcome
corrects a load-bearing claim, and the curve itself is an independent check on the 32 entries
already recovered from ROM.

### E4 — ★★★ Reverb impulse responses (the all-pass family)

**What to do:** one short sharp note, 100 % wet if the machine allows it, 15–20 s of tail, through
`eff26_room_reverb_1`, `eff28_plate_reverb_1`, `eff30_concert_reverb_1` and `eff32_dark_reverb_1`.
One take each is enough; add a second at a different DECAY setting for one of them.

**Why it is asked.** **`ACT 0x0B` is 159 words** — the largest single open block — and it is
anchored only as "the all-pass core's fourth multiplicand route", on class A, with three separate
criteria already measured *blind*. The WSA1R's reverbs are also known to differ structurally from
the KN5000's (all-pass ladder versus comb/FDN), and that claim rests on listing topology, not on
sound.

**What the answer changes.** An impulse response makes the early-reflection pattern and the
all-pass ladder's stage delays directly visible, and the decay envelope gives the feedback gains.
That is exactly the quantity the `ACT 0x0B` reading predicts and nothing has yet been able to check.

### E5 — ★★★ Parametric EQ frequency response

**What to do:** hold a note and record through `eff04_parametric_eq` with **all bands flat**, then
with **one band** at maximum boost, then that same band at maximum cut — one take each, for two
different bands. A chromatic MIDI run over a few octaves (one note at a time, same velocity) gives
you a crude but adequate sweep.

**Why it is asked.** The largest *emulation* defect, as opposed to decoding defect, is
`pair_gate.sh` criterion **(C)**: the EQ's pickup cell should hold exactly **one clean copy** of its
input and instead rails at `0x10`. The project calls (C) "the only criterion that separates RIGHT
from merely ALIVE", and it fails under every store-gate arm — including the one promoted today, so
it is downstream and independent.

**What the answer changes.** A measured centre frequency, Q and gain per band, at known parameter
settings, anchors the biquad coefficient chain from the outside. That is what would tell us whether
the scale arms (`PSHIFT`, `C8SHIFT`) are right, and the EQ's coefficient scales are otherwise only
solved statically.

### E6 — ★★ Compressor static curve and timings

**What to do:** through `eff48_peq_compressor`, a rising MIDI-velocity ramp as in E3 (for the
input→output curve), then a **sudden loud note after silence** held for 3 s and released (for
attack and release). Repeat at two THRESHOLD settings, and note whether THRESHOLD is audible at all.

**Why it is asked.** **`f31` 3…7 is 189 words**, and §149 closed it with *"every anchored criterion
is blind to the axis by construction"* — the carriers are the dynamics and distortion families,
whose HLE models are only *graded*, never measured against hardware. The KN5000 file asks whether
the compressor's THRESHOLD is even audible; here it is answerable.

**What the answer changes.** A measured knee, ratio and time constants grade the dynamics HLE, and a
graded HLE is the adjudicator `f31` needs. This is the longest chain in this file — it does not
decode words directly, it makes the instrument that could.

### E7 — ★★ Pitch shifter

**What to do:** one sustained note through `eff54_pitch_shifter` at each available interval setting,
10 s each, plus one take with a short percussive note to expose the grain/window behaviour.

**Why it is asked.** The KN5000 ships PITCH SHIFTER as a **byte-identical copy of NO OPERATION** —
a stub. The WSA1R has a real one, and it is the *only* real one in the pooled corpus. Separately,
the strongest external lead in the project is a **Pioneer CDJ-500** firmware dump (same chip, and
its DSP-shaped feature is Master Tempo — key-lock pitch shifting), named in the strategic review as
the only route to the bit-11 drought.

**What the answer changes.** The measured shift ratio and grain period characterise the one
pitch-shifter program we have, which is the closest available proxy for what a CDJ-500 corpus would
contain — and it tells us in advance what to look for there.

---

## If you only have half an hour

**E0.2** (bulk dump — no instruments, no risk), then **E1** at the lowest LFO rate for 60 s on
`eff11_vibrato`, then **E3** on `eff00_distortion`. Plus the `eff53_no_operation` control at the
same settings. Those three recordings alone bear on 171 + 189 words and one outright numerical
contradiction.

## Where to put the results

Anywhere you like, then tell me the path. Large WAVs need not be committed — the project's rule is
that the **recipe** must be, and this file is it. What must be written down and kept is
`notes.txt`: for every take, the effect name, every parameter value, the note and velocity, the
sample rate and bit depth, and the output-gain position. I will add the analysis scripts beside
this file as each measurement arrives, so every number they produce can be re-derived.

## ★★ THE ACTIVE COUNTERPART: `HARDWARE-CUSTOM-DSP-PROGRAMS-WSA1R.md` — ✅ BUILT

⚠ **SUPERSEDED.** This heading used to read *"⛔ DOCUMENTED, NOT TO BE BUILT"*, citing Felipe's
2026-09-14 instruction. He **reversed it the same day** (`/goal implement the custom rom`), and the
monitor now exists: 397 bytes in prom_a's padding behind a four-byte hook, answering `IDENT` and
`PEEK` over real MIDI with a stock-ROM negative control —
`WSA1R-SYSEX-MONITOR-BUILD.md` and `tools/wsa1r-sysex-monitor/midi_roundtrip.sh`.

⛔ What it still cannot do is reach the **DSP**: the µPD6383s hang off **CPU 2**'s ports, so
`LOAD`/`POKE`/`RUN` must cross the inter-processor mailbox. That, not the ROM patch, is the
remaining work. **Everything in THIS file remains live** — the eight audio experiments need
nothing but a MIDI cable, an audio interface and the stock instrument, and none of them touches
a ROM.

Everything in this file is **passive** — it measures what the stock firmware already does. The
third document asks the stronger question: can we put **our own microcode** into IC30? That reaches
what no audio measurement can, including the **bit-11 block (169 words)** this file cannot touch,
and it would decode `f31` 3…7 (189 words) and `SRC 0x11` (139) almost directly.

★ Its centrepiece is Felipe's own proposal: **a custom SysEx debug monitor in ROM** — burn once,
then load probe microcode and read results back over MIDI forever, in exact integers instead of
analogue levels. That turns the remaining decode into an automatable sweep over all ~321 undecoded
word shapes, and it is the only route that can locate the chip's **COND field** and its
**GF-setting instruction**, because RQ1–3 and GF1–3 are host-side lines that ROM analysis cannot
see.

✅ **The blocking question is answered: the program ROMs are SOCKETED** (Felipe, 2026-09-14), so
the monitor can be delivered with no soldering. What it asks of you now is **A1.0** in that file —
lift all four program ROMs and dump them, checking against the hashes recorded there. That costs
nothing, validates your reader before anything is ever written, and would tell us whether **IC22**
(the `AM29F400T` flash, `NO_DUMP`) and the six **wave mask ROMs** (`NO_DUMP`, and the reason this
emulation has no audio) are reachable too. The one remaining question is the schematic's: does it
bring the DSP's **GF1–3 / RQ1–3**, pins 83–88, to a CPU port or to a jumper/pull-up? The other two routes — triggering the 57 body records the firmware already has, and
decoding the SysEx ring consumer — are mine to do and either could make opening the instrument
unnecessary.

## How to use this file

Each entry states what to do without reading any code, why it is asked, and what changes depending
on the answer. An experiment whose outcome changes nothing does not belong here — and neither does
one whose answer I could get from the ROM. ⚠ If a measurement contradicts something this project
has written down, the measurement wins: Felipe's hardware testimony outranks agent inference,
disassembly and live emulation, and that has already been the right call more than once.
