# Questions only the real hardware can answer — PARKED

⚠ **Felipe has no access to his KN5000 as of 2026-09-03.** The instrument is in
storage in another country, with no date set for access. These questions are
therefore **parked, not pending**: do not plan work that blocks on an answer,
do not re-ask, and do not quietly substitute an inference for the measurement.

When access returns, this file is the queue. Each entry states the question in
terms Felipe can act on without reading any code, what is already established,
and — the part that matters — **what changes depending on the answer**. A
question whose answer changes nothing does not belong here.

---

## Q1 — Does the KN5000 visibly re-seek when a floppy is INSERTED?

**What to do:** power the instrument up with the drive empty, let it settle,
then insert a disk and watch (and listen to) the drive without touching any
control. Does the head visibly step / does the drive audibly seek on insertion
alone?

**Why it is asked.** Main-CPU **PD.6** is read by two floppy routines and, three
instructions after the Port G pedal reads, into the pedal parameter block at
`0x8EBE` (`v10 audio/audio_control_engine.s:1869`). The schematic settles the
*pin* — net **FD.I/O**, IC5 pin 17, 4.7 kΩ pull-up — but not its meaning. The
name `Check_for_Floppy_Disk_Change` was supplied by an earlier analysis pass and
is **not ground truth**.

**What the answer changes.** The driver currently *inverts* MAME's `dskchg_r()`,
which already carries hardware polarity. If PD.6 really is disk-change, that
inversion is wrong and the boot path changes when it is corrected — which is
exactly why it was not flipped on the strength of a routine name. A visible
re-seek on insertion supports disk-change; no reaction points at PD.6 being
something else, and at the pedal read being the honest one.

---

## Q2 — Is CN12 a serial port, and does anything connect to it?

**What to do:** look at the connector labelled **CN12** on the real machine. How
many pins, is it a recognisable serial shape, is anything ever plugged into it,
and does the manual or the case marking name it?

**Why it is asked.** The KN5000 **sub CPU** carries a complete UART driver at
interrupt level 5 that nothing in the firmware appears to point at. A finished
driver for a port that is never used is unusual enough to be worth one look at
the hardware.

**What the answer changes.** If CN12 is that UART's port, the sub CPU has an
external interface nobody has modelled, and the driver has a missing device
rather than dead code. If it is not, the UART driver is vestigial — most likely
shared-source residue from a sibling model — and the right action is to record
that and stop looking.

---

## Q3 — Is there an audible mute at power-OFF, distinct from the main CPU's
power-down?

**What to do:** with the volume up and a note sounding if possible, switch the
instrument off and listen. Is there a distinct click/mute *before* the sound
dies away, or does the audio simply stop with the machine?

**Why it is asked.** An unmapped device at **`0x150000` / `0x150002`** (address
latch + data, structurally a twin of the sub bus's `0x130000`) receives ~68
writes on every boot in v7, v9 and v10, from `AudioMix_Init`. The traffic is
real and reproducible; which chip answers it is not established.

**What the answer changes.** A separate audible mute implies a real muting
element on that bus and would support mapping `0x150000` as an audio-path
device. Without that, mapping it would **hide a gap behind a fake device**,
which is worse than leaving it unmapped — so this stays unmapped until the
question is answered.

---

## Q4 — SINGLE DELAY at its default preset: does the echo return at ~11 ms or ~23 ms?

**Asked 2026-09-04 (DSP §234).** Select the SINGLE DELAY effect with its
factory default parameters, play one short staccato note into it with the
dry/wet mix audible, and listen (or record) for the FIRST echo: is it a very
short slap of roughly **11 ms** (500 samples at 44.1 kHz), or roughly **23 ms**
(1001 samples)? If the DELAY TIME control is visible, note its displayed value
as well.

**Why it is asked.** The effect-DSP program a09 allocates two delay lines of
500 and 501 samples in cascade (the second is written from the first's return).
Which one the output presents is decided by two undecoded action codes
(`ACT 0x0D`/`0x0E`) sitting immediately before the head write. The reading the
emulator ships — confirmed from disk at PARAMETRIC EQ, 1 of 49 — makes the
output present the **500**-sample tap and discard the second line's product;
the reading every earlier SINGLE DELAY measurement assumed presents the
**1001**-sample cascade. The corpus, the descriptors and the ROM's own
coefficient product (the echo's gain is identical either way) cannot tell them
apart. `dsp/tools/sd_rerun.py act0d0e` in kn5000-roms-disasm.

**What the answer changes.** ~23 ms would refute the shipped `ACT 0x0D`/`0x0E`
pair in the one delay context that reaches it and reopen §133; ~11 ms would
corroborate it and retire §230's lag-1001 criterion as a statement about an
inert model. Either answer is a decode result; the emulator cannot supply it.

---

## Q. THE DECODE QUEUE HAS RUN OUT OF ANCHORS — this is now a hardware question (2026-09-14)

**Why it is being parked rather than pursued.** 1501 of the 8003 pooled uPD6383 words are
undecoded, and every remaining open code has now been checked against **both** anchors this project
owns — the parametric EQ's designed response and SINGLE DELAY's lag-1001 ROM product — by
**membership** (does the model's own section read a cell this word writes, on the relative pointer
walk) rather than by position:

```
   ACT 0x0B          191 words     no anchored carrier
   SRC 0x11          171           documented dependency cycle
   ACT 0x01..0x06    109, 1 decoded   no anchored carrier
   f31 = 3            56           no anchored carrier
   op 0x72 route     (would unblock 247)  shut statically AND dynamically
```

`SINGLE DELAY` contains **0** of these codes, `ROOM REVERB 1` **0**, `PARAMETRIC EQ` **1**. And
`dsp/tools/decoded_selfcheck.py` proves 0 forward / 0 reverse inconsistencies, so none of the 1501
is blocked by a defect in the predicate. **The corpus does not contain a discriminating consumer for
these codes.** That is a fact about the ROM, not about the tooling.

### What would actually settle it, in order of cheapness

1. ★ **Record the KN5000's EFFECT OUT (or DO3 / HD-AE5000 extension out, never the speaker mix) for
   ONE effect that carries an open code, at two settings of one parameter.** COMPRESSOR, ENHANCER
   or ROTARY SPEAKER would each do — all three carry `ACT 0x01..0x06`, none is modelled bit-exactly,
   and none is reachable from the ROM. A single before/after pair gives the first anchored
   quantity in a NONLINEAR effect the project has ever had, which is exactly what §135 and §149 both
   name as the missing ingredient.
2. **Does moving the COMPRESSOR's THRESHOLD audibly change anything?** MEASURED here: its `op 0x72`
   C-RAM cells are rewritten `0x600000` (exactly 0.75) unchanged however the knob moves — both in
   the stored presets and in a live capture with the parameter driven. Either the parameter reaches
   the chip by a path this project has not found, or THRESHOLD does very little on real hardware.
   **Felipe's ear settles which**, and the two readings are not close.
3. **SLOW ATTACKER on real hardware** — still open from the twelve-stub finding, and now more
   pointed: it ships a program byte-identical to NO OPERATION.

⚠ Hardware is stored in another country with no date (`kn5000-hardware-inaccessible`), so this is
parked deliberately. **The absence of an answer is not licence to promote an inference**: the four
codes above stay OPEN and the decode number stays at 81.2 %.

---

## How to use this file

* Answers go **into this file** next to their question, dated, and then into the
  driver or the docs — not into a commit message alone.
* An answer of "I looked and could not tell" is a real answer and should be
  recorded as one; it usually means the question needs re-framing.
* ⚠ Standing project rule: **Felipe's hardware testimony outranks agent
  inference, disassembly and live measurement.** Its absence is not licence to
  promote an inference — leave the item open and say so.
