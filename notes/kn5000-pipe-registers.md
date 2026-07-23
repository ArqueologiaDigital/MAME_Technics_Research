# KN5000 tone-gen (IC303 / TC183C230002) — FULL register semantics decode

Author: autonomous DECODE pass, 2026-07-23. Requested by Felipe Sanches.

**Goal.** For EVERY register the sub-CPU writes to IC303, decode how its value is computed
from the voice data — the complete `Voice_Init` pre-compute → `ToneGen_WriteVoiceParams` burst
chain — and cross-check against the live capture. Crucially: scan ALL registers (not just
+0x040/+0x440) for anything wave-selection-shaped (a sample address / bank / wave index) hiding
in a register we currently treat as pitch/level.

**Result up front.** The register file is fully mapped. The per-voice waveform is selected by
**exactly one register — +0x040** — and no other. Every other per-voice register is pitch,
timbre/filter, a multi-stage envelope, a level/gate, or a rotating streaming-slot counter. This
is proved two ways: (1) the disassembly shows +0x040 is the only register loaded from the
selected *partial record's first word*, and (2) in the live capture **+0x040 is the only
register whose value changes at a multisample zone boundary** — every other register is either
constant across zones or varies *continuously* with pitch (so cannot be a zone-quantized sample
address).

Evidence labels: **MEASURED** (read live and/or read directly out of the disassembly),
**INFERRED** (deduction), **SPECULATIVE**. Disasm = `kn5000-roms-disasm/archive/asl/subcpu/
kn5000_subprogram_v142.asm` (line/label cited). Live = capture harness `cap_all.lua` on built
`kn7000_mame_build/kn7000`, isolated pre-init nvram (RIGHT1 part 0). Builds on / completes
`kn5000-live-captures.md`, `kn5000-tonegen-register-semantics.md`, `kn5000-voice-pipeline.md`,
`kn5000-wave-number.md`.

---

## 0. The hardware register-address format (MEASURED)

Every write is a two-step: latch a 16-bit *register address* at `0x100000`, then the 16-bit
*data* at `0x100002` (the RES/SET 7,(P6) toggles a write-strobe line around each pair). The
address is `(group<<8) | (bank<<6) | channel`:

* `channel` = bits 0..5 = the voice channel 0..63 (the "base" the writer holds in `IZ`).
* `bank`    = bits 6..7 (the `+0x40/+0x80/+0xC0` steps inside a group).
* `group`   = bits 8..15 (the `+0x100/+0x400/+0x800/…` register-block selector).

So the tone-gen is a 2-D register file: for each of 64 channels there is a set of parameter
slots addressed by (group,bank). Throughout this note a **register is named by its
`(group,bank)` offset with channel=0** — i.e. the constant the writer `ADD`s to the channel
base. This is exactly the `off=0x0NN` column in the capture. (E.g. "reg +0x040" = bank 1;
"reg +0x400" = group 4; "reg +0x800" = group 8.)

---

## 1. `ToneGen_WriteVoiceParams` — the per-voice burst (MEASURED, disasm L29565–29917)

One call = one oscillator/partial. `WA` in = channel base (→`IZ`); `XBC` in = pointer to the
44-byte **chip-image scratch struct at 0x0451CC**. The body is a fixed, unrolled sequence of
`reg ← struct[off]` writes. The complete struct-offset → register map, read straight out of the
code:

| scratch off | scratch addr | → reg | data transform | live meaning (§4) |
|---|---|---|---|---|
| +0x02 | 0451CE | **+0x040** | direct | **WAVE select** = {class<<12 \| wave-slot/zone} |
| +0x04 | 0451D0 | +0x080 | `SET 15` on load, `RES 15` at end | output level + **bit15 = voice GATE** |
| +0x06 | 0451D2 | +0x0C0 | direct | timbre 1 (per-instrument const) |
| +0x08 | 0451D4 | +0x100 | direct | TVF / filter (per-instr, weak key-follow) |
| +0x0a | 0451D6 | +0x140 | direct | timbre 2 / TVF (per-instrument const) |
| +0x0c | 0451D8 | +0x180 | direct | modulation / LFO / pan (per-instr, per-osc) |
| +0x0e | 0451DA | +0x400 | direct | **PITCH** (log, per-note) |
| +0x10 | 0451DC | +0x440 | direct | osc1 wave-slot / DMA rotating counter |
| +0x12 | 0451DE | +0x480 | direct | osc2 wave-slot rotating counter |
| +0x14 | 0451E0 | +0x4C0 | direct | constant 0x4400 (voice-type config) |
| +0x16 | 0451E2 | +0x500 | direct | timbre 3 (per-instrument const) |
| +0x18 | 0451E4 | +0x800 | direct | envelope A |
| +0x1a | 0451E6 | +0x840 | direct | envelope B |
| +0x1c | 0451E8 | +0x880 | direct | envelope C (key-tracked) |
| +0x1e | 0451EA | +0x8C0 | direct | envelope D |
| +0x20 | 0451EC | +0x900 | direct | envelope stage |
| +0x22 | 0451EE | +0x940 | direct | envelope stage |
| +0x24 | 0451F0 | +0x980 | direct | envelope stage |
| +0x26 | 0451F2 | +0x9C0 | direct | envelope stage |
| +0x28 | 0451F4 | +0xA00 | direct | envelope stage (key-tracked) |
| +0x2a | 0451F6 | +0xA40 | direct | envelope stage (key-tracked) |
| (const)| —     | +0x000 | `LDW 0x8100` | per-voice control word (arm) |

**Two structural details in the burst (MEASURED):**

* **Register +0x080 is written twice** — first with **bit 15 forced set** (`SET 0Fh,WA`,
  L29594), and once more at the very end with **bit 15 forced clear** (`RES 0Fh,WA`, L29907).
  Bit 15 of +0x080 is a **latch/gate held high across the whole parameter load and released
  after** — i.e. "load in progress" / voice-arm. Its other bits are the output level.
* **Register +0x000 gets the constant 0x8100** mid-burst (`LDW (100002h:24),8100h`, L29757).
  This is the per-voice control/arm word.

The unused-in-this-note tail of the sub-CPU also has *partial* writers that touch the same
register file — `LABEL_02D436/02D50E/02D5D0/02D620/02D68F` (L29936+) rewrite a subset of the
0x800-group and the +0x080 gate from later struct offsets (+0x2c…+0x3e). These are the
**voice-steal / release / osc-2** helpers; same register semantics, different struct source.

---

## 2. The scratch is filled field-by-field by the tone-record decoders (MEASURED)

The scratch 0x0451CC is **not** memcpy'd from one place; it is written slot-by-slot by the
voice-init decode functions. There are **119 direct stores to 0x0451CE..0x0451F6** across
L14302–L17700 (grep `LD(W)? (0451[C-F]`), one group of stores per register field. Two anchor
points prove the whole chain:

**(a) The clean enumeration — `LABEL_0272A3` (L21896).** The idle/default-voice path fills the
entire scratch in address order, which independently confirms the offset→register map of §1 and
shows the *data sources*:

```
0451CE (+02→reg040 wave)   = 0x0000              ; null voice = wave 0  (⇒ capture discipline: press >9s)
0451DA (+0e→reg400 pitch)  = (0x041360)          ; pitch from RAM
0451D4 (+08→reg100)        = 0x017F              ; filter default
0451D6 (+0a→reg140)        = 0x7F7F              ; timbre default
0451D8 (+0c→reg180)        = 0x0040
0451E0 (+14→reg4C0)        = 0x0000
0451E4 (+18→reg800 env)    = 0xFF7F
0451E6 (+1a→reg840 env)    = (0x041362)          ; env base from RAM
0451E8 (+1c→reg880 env)    = (0x041362)
0451D0 (+04→reg080 level)  = ((0x010764)[idx]<<1); level from a ROM table indexed by (0x041364)
0451EC/EE/F0/F2/F4/F6      = 0                   ; env stages zeroed
```

**(b) The real note-on builder — `LABEL_02B4E3` (L26803) = "Voice_Init_Type4".** For a played
note it takes the per-voice **working struct at `0x04308E + channel*0x47`** (71-byte block) and
runs ~17 decode sub-stages (`LABEL_023849, 023A05, 023A4A, 023AD0, 024102, 024444, 024664,
0248D5, 024BE3, 024F41, 025229, 0253FE, 025589, 025636, 02591D, 026396, 026637`), each of which
reads the tone-record and writes its computed field into the 0x0451CC scratch, then calls
`ToneGen_WriteVoiceParams(0x0451CC, channel)` at L26850. (Related builders live at L26855/
L27616/L27963 for layered/extended parts.)

So the full data lineage is:
**tone record (sub-CPU DRAM) → decode sub-stages (L14302–17700) → 44-byte scratch 0x0451CC →
`WriteVoiceParams` burst → IC303 registers.** No sub-CPU RAM pointer is ever handed to the chip;
only *computed field values* are. The chip boundary holds.

---

## 3. The wave-selection core — how +0x040 is computed (MEASURED, disasm L14289–14361)

This is the load-bearing decode. The multisample partial is picked by one of **six
class-specific selectors** (`LABEL_022A3F/022A61/022A83/022AA4/022AC5/022AE7`). Each does the
same shape — `partial = set_base + zone_index * stride` — with a **per-class record stride** and
a **per-class nibble OR'd into the working address**, then reads the partial record's first word
into the wave register:

| selector | stride (record size) | class nibble OR'd | classes seen in capture |
|---|---|---|---|
| L022A3F | 0x0F | 0x7000 | 7 = Piano |
| L022A61 | 0x0C | 0x5000 | 5 = Flute / Drums |
| L022A83 | 0x0D | 0x3000 | 3 = Guitar / Sax / World / GM |
| L022AA4 | 0x0A | 0x1000 | 1 = Brass / Bass |
| L022AC5 | 0x06 | 0x4000 | 4 = Organ / Accordion |
| L022AE7 | 4 (`SLA 2`) | (none = 0) | 0 = Strings / OrchPad / Synth |

The decisive two instructions (e.g. L14301–14302):

```
LD  WA, (XBC)          ; XBC = set_base + zone*stride  → first word of the selected partial rec
LD  (0451CEh), WA      ; store it to scratch +0x02  → becomes register +0x040
```

Therefore **register +0x040 = partial_record[0]**, whose **low byte is the wave-slot/key-zone
number stored in the tone data** and whose **high nibble is the partial class** (OR'd at
`ORW (XWA+001h),0x7000` etc.). The `zone_index` itself comes from a key→zone lookup
(`LABEL_022A32`: `AND BC,7F00h; SRA 8; LD L,(XWA+BC)` — a per-set 128-entry key map), which is
why +0x040's low byte **steps at split points as the played note rises** (Piano 01→04→07→08→0A→
0D) and jumps non-monotonically for DRUM KITS (per-key drum map).

The selector also stashes the *partial pointer* at working-struct +0x0F and a per-partial
fine-tune/root word at 0x293E (from `partial_rec[+0x0d/+0x0a/+0x04]`). **That pointer and
fine-tune stay on the sub-CPU** — they feed the pitch/timbre math (regs +0x400/+0x100) but are
never sent to the chip. The only thing that crosses to IC303 is the wave-slot *number* in
+0x040. This is exactly the chip boundary the project posits: the chip takes the slot number in
+0x040 and looks up the physical PCM start address in its own wave-ROM index (IC307's 198-entry
`{param_ptr, wave_offset}` table at offset 0). **The PCM address is resolved on-chip from
+0x040; it is not, and need not be, written as a register.**

---

## 4. Live cross-check — the wave-selection hunt (MEASURED)

Full unfiltered in-window register stream captured for Piano/Guitar/Strings/Brass (slice 0–3),
Strings/Brass/Flute/Sax (slice 2–5), 7 notes each. The registers that had **never** been
tabulated (+0x100, +0x180, +0x4C0, the whole +0x800…+0xA40 group, +0x000) are now decoded.

### 4a. The zone-boundary test (decisive)

Within one instrument, compare a register across notes and watch what happens at a **multisample
zone boundary** (where +0x040's low byte changes) versus **within a zone** (E4→G4 are both
Piano zone 0x08). A sample-address register MUST jump at zone boundaries and hold within a zone.

Piano, osc1, across C2→C6:

```
+040 (WAVE) : 7001 7004 7007 7008 7008 700A 700D   ← steps at every zone boundary  ✅ selector
+100        : 244E 244E 244E 244F 2450 2452 2455   ← flat across C2/C3/C4 zone changes; creeps only high → key-follow filter, NOT address
+180        : 0000 0000 0000 0000 0000 0000 0000   ← constant
+4C0        : 4400 4400 4400 4400 4400 4400 4400   ← constant
+880 (env)  : 2E00 3200 3800 3A00 3B00 3D00 4300   ← changes E4→G4 *within* zone 0x08 → pitch-continuous, NOT address
+A00 (env)  : 42E8 3CE8 36E8 34E8 33E8 31E8 2BE8   ← changes within a zone → NOT address
+A40 (env)  : 32B0 2CB0 26B0 24B0 23B0 21B0 1BB0   ← changes within a zone → NOT address
+0C0/+140/+500 (timbre) : constant per instrument   ← NOT address
```

**Conclusion (MEASURED): +0x040 is the ONLY register that is quantized to the multisample zone.**
+0x880/+0xA00/+0xA40/+0x100 all change *between E4 and G4, which share a zone* — impossible for a
per-sample address; they track the note pitch continuously (envelope key-scaling / filter
key-follow). Everything else is constant. **Nothing wave-selection-shaped hides in a
pitch/level/envelope register.**

### 4b. The +0x800…+0xA40 group is a multi-stage ENVELOPE (MEASURED)

Per-instrument C4, osc1:

```
                 +800  +840  +880  +8C0  +900  +940  +980  +9C0  +A00  +A40
PIANO   (decay)  FF80  FF00  3800  00B0  AE00  AE00  AE00  FF00  36E8  26B0
BRASS   (swell)  FF80  FF00  097F  0000  FFF0  8EF8  7A00  AE00  AE00  AE00
STRINGS (slow)   FF80  FF00  3674  0000  AE00  AE00  AE00  AE00  AE00  AE00
FLUTE   (sustain)E67F  5E74  326A  0000  AE00  AE00  AE00  AE00  AE00  AE00
```

Reads exactly like an envelope generator: PIANO programs decaying tail stages (+A00/+A40 =
36E8/26B0, and they get *faster*/smaller as the note rises — envelope key-scaling); BRASS
programs a rising attack (+900/+940/+980 = FFF0/8EF8/7A00); STRINGS/FLUTE leave the stages at
the idle sentinel **0xAE00** (= sustained, no decay). 0xAE00 is the "unused stage" fill (matches
`LABEL_0272A3` zeroing / default). The pre-writes `+800=FF80, +840=FF00` before each burst are a
**click-free channel mute** (force max attenuation) so a stolen still-sounding voice doesn't
pop; the burst then overwrites +800/+840 with the real envelope start. This is envelope data,
not addresses.

### 4c. Register +0x000 = key-on trigger (MEASURED)

Each osc burst writes `+000 = 0x8100` (arm). After *all* of a note's oscillators are loaded, a
separate pass writes **`+000 = 0xF0FF` per channel** (last two lines of every note window) —
the **note-on strobe** that starts the voice(s) together. (Velocity was fixed in the capture, so
0xF0FF is constant here; the high byte is the likely velocity/gate carrier — SPECULATIVE.)

### 4d. +0x440 / +0x480 reconfirmed as rotating slot counters, not selectors (MEASURED)

Reconfirms `kn5000-live-captures.md` §6: 0 for the 11 ordinary voices; for the streamed voices
(Flute/Sax/World/Organ/GM) the low byte is a **per-note-on rotating DMA/voice-slot counter**
(+1 each note-on regardless of pitch) and the top bits are the bank (`tonerec[+0x1a]&0xC0`).
No waveform identity.

---

## 5. Extended registers (streamed voices) — decoded (MEASURED, disasm L30535–30818)

Five instruments (FLUTE/SAX/WORLD/ORGAN/GM SPECIAL — the ones with nonzero +0x440) also program
an extended block written to a **fixed low aux channel** (ch01/08/09), not the played voice
channel. Three writers, each using the same **bit-15 gate** latch pattern as +0x080:

| writer (label / line) | reg | struct off | gate |
|---|---|---|---|
| `WriteExtParams_15` L30759 | +0x540 | +0x3a | write-if-bit15, then rewrite bit15-clear |
| `WriteExtParams_15` L30759 | +0x1C0 | +0x38 | direct |
| `WriteExtParams_56` L30535 | +0x580 | +0x3c | bit15-gate |
| `WriteExtParams_56` L30535 | +0x600 | +0x40 | direct |
| `WriteExtParams_56b` L30676 | +0x5C0 | +0x3e | bit15-gate |
| `WriteExtParams_56b` L30676 | +0x640 | +0x42 | direct |

(These extend the scratch past its 44-byte core to ~0x44 bytes: fields +0x38..+0x42.)

**Are these a sample address / DMA pointer? Test: hold pitch, vary note.** FLUTE across C3→C6
(three octaves):

```
+540 = 0120  +580 = 0120  +600 = 0000  +1C0 = 0000   (all CONSTANT; only the aux-channel index increments)
SAX  : +540 = 00E0  +580 = 00E0  ...     (per-instrument constant, different value)
```

**Conclusion (MEASURED): the extended registers are per-instrument CONSTANTS** (Flute 0x0120,
Sax 0x00E0), invariant across 3 octaves of pitch. They are the streamed-voice **control block**
(playback-rate / loop-length / stream-enable for the DMA'd sample) — **not** a per-note sample
address and **not** a wave selector. The waveform for these voices is still chosen by +0x040
(Flute +040=0x5000 held constant across its whole range; the multisample is one wave stretched).
Their exact DMA meaning (rate vs length) is **SPECULATIVE** — but decisively ruled out as wave
selection.

---

## 6. `ToneGen_WriteGlobalConfig` — global, not per-voice (MEASURED, disasm L30334–30504)

For completeness: the remaining tone-gen registers the chip receives are the **global** block —
regs `0x200..0x205`, `0xC00..0xC05`, `0xE00`, sourced from a 0x1a-byte global struct (bit 3 of
0x041343 conditionally toggles bit 3 of word 0). These are master mixer / effect-send / config.
**They are never written in a note-on window** (the capture's note-on stream contains only the
per-voice groups 0x000–0xA40); they carry no per-voice wave identity.

---

## 7. Full answer to the DECODE question

* **Every register the chip receives is now mapped to a scratch offset and a data source**
  (§1–§2, §5–§6). The value of each = a field the voice-init decoders computed from the tone
  record (§2b), or a global-config field (§6).
* **Wave/sample/bank selection lives in exactly one register: +0x040**, and its value is
  literally the first word of the selected multisample partial record — `{class<<12 |
  wave-slot}` (§3). The chip resolves the physical IC307 PCM address from that slot via its own
  on-chip wave-ROM index. This is fully within the chip boundary.
* **Nothing wave-selection-shaped hides elsewhere.** Proven by the zone-boundary test (§4a):
  +0x040 is the *only* register quantized to the multisample zone; every candidate we treated as
  pitch/level/envelope (+0x100, +0x180, +0x800…+0xA40) is either constant across zones or varies
  *continuously with pitch within a zone*, and the extended block (+0x540…+0x640, +0x1C0) is a
  per-instrument constant. None can be a sample address.
* **Implications for the HLE:** keep selecting on +0x040 (the current `kn5000_tonegen.cpp`
  approach is on the right register). The remaining "sounds bad" problem is the
  (bank,zone)→IC307-group *mapping* — the HLE must map +0x040 low byte through the **same
  198-entry IC307 index table the chip uses**, not an ad-hoc group guess. The harshness is a
  wrong-entry lookup, not a wrong register. Secondary faithfulness wins available for free from
  this decode: model the +0x800-group as a real multi-stage envelope (Piano decays, Brass swells,
  Strings/Flute sustain — the 0xAE00 sentinel = "stage unused"), and honor the +0x080 bit-15
  gate / +0x000=0xF0FF key-on strobe for click-free note starts.

---

## 8. Honest gaps

* Meanings of **+0x100** (TVF/filter cutoff, weak key-follow) and **+0x180** (LFO/mod/pan) are
  INFERRED from their per-instrument + weak-key-scaling behavior, not bit-decoded; the exact
  envelope-stage semantics of +0x800…+0xA40 (which word = rate vs level per DADSR stage) are
  characterized (envelope, key-scaled) but not fully field-parsed.
* The extended block's exact streaming parameter (rate vs loop-length vs enable) is SPECULATIVE;
  only "per-instrument constant, not an address/selector" is MEASURED.
* Captured part 0 (RIGHT1), default sound per group, fixed velocity. Global-config block (§6)
  not swept.
* The tone-record → scratch field computations (§2b) are cited by their store sites
  (L14302–17700) and the wave-select core is fully read (§3); the per-field arithmetic of the
  ~17 note-on sub-stages (pitch companding, filter key-follow) is not each individually decoded —
  only their *targets* (which scratch field) and the wave/pitch/envelope ones are.
