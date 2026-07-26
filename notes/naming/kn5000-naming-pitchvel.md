# KN5000 sub-CPU disassembly — semantic names for PITCH, VELOCITY/KEY-BED, TIMBRE/TVF, MULTI-PARTIAL

Naming pass, 2026-07-26. Scope: subsystems **D (pitch)**, **E (velocity / key bed)**,
**F (timbre / TVF)** and **G (multi-partial)** of the tone-generator investigation.

Target file: `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`
(all `L<n>` below are 1-based line numbers in that file; runtime address → sub-program ROM
file offset = `addr − 0xEF00`).
Symbol reference: `kn5000-roms-disasm/symbols/subcpu_symbols_reference.txt`.

Every name below was **PREDICT-THEN-CHECK**ed: the note's claim was read first, then the
disassembly at that address was read and the claim confirmed, refined or **contradicted**.
Section 5 lists the corrections — several of them matter more than the names.

Evidence labels: **MEASURED** (a ROM byte or a disassembled instruction read this pass) /
**INFERRED** / **NOT ESTABLISHED**.

---

## 1. Routine names — D. PITCH

| address | old | new name | purpose |
|---|---|---|---|
| `0x023584` | `LABEL_023584` | `Pitch_Resolve_Key_Zone` | key + all transposes + scale tuning + key-follow → absolute pitch `desc[+0x08]` and zone-folded pitch `desc[+0x06]` |
| `0x023A05` | `LABEL_023A05` | `Pitch_Apply_Partial_Detune` | adds the per-zone trim, partial fine transpose (×2), unison/slot detune and part fine tune → `desc[+0x0a]`; sets the BEND-enable bit |
| `0x023A4A` | `LABEL_023A4A` | `Pitch_Emit_Reg400` | adds master fine tune, part detune and the live bend value, saturates, stores to the scratch word that becomes chip register `+0x400` |
| `0x023A8E` | `LABEL_023A8E` | `Pitch_Apply_Zone_Trim` | short-chain form of the above: `desc[+0x0a] = desc[+0x06] + zone trim` only |
| `0x0229EC` | `LABEL_0229EC` | `Pitch_Fold_Octaves_Into_Range` | renormalises a 16-bit-wrapped pitch, then folds by whole octaves into `[kmin,kmax]` |
| `0x02299D` | `LABEL_02299D` | `Pitch_Clamp_Into_Range` | saturates, then clamps (no folding) into `[kmin,kmax]` |
| `0x022B02` | `LABEL_022B02` | `Pitch_Saturate_15bit` | saturate a wrapped log pitch to `0…0x7FFF` |
| `0x022A32` | `LABEL_022A32` | `Pitch_Lookup_Zone_For_Key` | `zone = map[(pitch>>8)&0x7F]` from the SET's 128-byte key→zone map |
| `0x02294E` | `LABEL_02294E` | `Pitch_Get_Patch_Octave_Shift` | per-patch **octave** transpose from tone-record byte `+0x29` |
| `0x028B96` | `LABEL_028B96` | `ScaleTune_Get_Global_Mode` | returns the panel-wide scale-tuning mode byte |
| `0x028D42` | `LABEL_028D42` | `ScaleTune_Is_Global_Enabled` | returns `flags & 0x0200` — global scale tuning vs. the patch's own |
| `0x028C28` | `LABEL_028C28` | `ScaleTune_Get_User_Offset` | one entry of the 12-note user scale |
| `0x02D0BA` | `LABEL_02D0BA` | `ToneGen_WriteVoicePitch` | writes **only** chip register `voice+0x400` — the sole retune path for a sounding voice |
| `0x0271BC` | `LABEL_0271BC` | `Pitch_Bend_Ramp_Tick` | advances the panel BEND / auto-bend ramp one tick |
| `0x028D4C` | `LABEL_028D4C` | `Pitch_Refresh_Sounding_Voices` | re-ships `+0x400` for a part's sounding voices after a tune change / MIDI CC |

## 2. Routine names — E. VELOCITY / KEY BED

| address | old | new name | purpose |
|---|---|---|---|
| `0x03D11F` | `ToneGen_Calc_Pitch` **(wrong name)** | `Keybed_Decode_Event` | decodes one key-bed FIFO event into `(MIDI note, velocity)` — computes **no pitch at all** |
| `0x03D1AA` | `ToneGen_Pitch_Adjust` | `Keybed_Vel_BlackKey_Trim` | subtracts the per-mode BLACK-KEY velocity trim |
| `0x03D1C4` | `ToneGen_Pitch_Clamp` | `Keybed_Vel_Clamp` | clamp the strength to `0…0xFF` before the T2 lookup |
| `0x03D1D3` | `ToneGen_Pitch_ClampHi` | `Keybed_Vel_ClampHi` | (interior) |
| `0x03D1E1` | `ToneGen_Pitch_ClampLo` | `Keybed_Vel_ClampLo` | (interior) |
| `0x03D1F5` | `ToneGen_Calc_NoVel` | `Keybed_Decode_NoteOff` | release path: velocity byte := 0 |
| `0x03D0C5` | `ToneGen_Read_Voice_Data` | **kept** | reads the key-bed event FIFO through the tone-generator port; header corrected |
| `0x022824` | `LABEL_022824` | `Velocity_Select_Split_Zone` | 3 split bytes → velocity layer `q ∈ 0..3`, `q=0` softest |
| `0x022844` | `LABEL_022844` | `Velocity_Select_Split_Zone_Alt` | byte-identical twin, second entry point |
| `0x0328E2` | `LABEL_0328E2` | `Partial_Store_Set_Pointer` | caches one velocity layer's SET pointer at `part_struct+0x76+0x25·p+4·q` |
| `0x02B717` | `LABEL_02B717` | `Voice_Build_Partial_Descriptor` | builds one partial's 0x47-byte staging descriptor (split, SET, block, note, velocity) |
| `0x023849` | `LABEL_023849` | `WaveSel_Build_Reg040` | builds the wave-select register `+0x040` (shared with the WAVE-SELECT subsystem) |

## 3. Routine names — F. TIMBRE / TVF

| address | old | new name | purpose |
|---|---|---|---|
| `0x02B4E3` | `LABEL_02B4E3` | `Voice_Build_Register_Set` | runs the 17 parameter builders for one chip voice and bursts the scratch |
| `0x024102` | `LABEL_024102` | `TVF_Build_Dispatch` | 6-way dispatch on `VP[+0x36]&7` → the `+0x100`/`+0x140` builder |
| `0x023D01` | `LABEL_023D01` | `TVF_Build_Full` | mode 1 — the builder every stock sound uses |
| `0x02413E` | `LABEL_02413E` | `TVF_Build_Short` | same registers from the short parameter set `VP[+0x0f..0x14]` |
| `0x024300` | `LABEL_024300` | `TVF_BuildEmit_Short_Dispatch` | 6-way dispatch on `VP[+0x0F]&7`, builds **and** emits |
| `0x022C06` | `LABEL_022C06` | `TVF_Calc_Cutoff` | base + velocity curve + key follow + `0x18`, clamped `[0,0x78]` |
| `0x022C99` | `LABEL_022C99` | `TVF_Calc_Cutoff_NoKeyFollow` | the short set's cutoff (velocity term only) |
| `0x022BF2` | `LABEL_022BF2` | `TVF_Clamp_Cutoff` | `clamp(x, 0, 0x78)` |
| `0x022DA1` | `LABEL_022DA1` | `TVF_Set_Bypass` | writes the reserved "no filter" constants `0x017F` / `0x7F7F` |
| `0x022CE8` | `LABEL_022CE8` | `TVF_Bias_Clamp_Amount` | `min(x + 0x18, 0x78)` |
| `0x022CF8` | `LABEL_022CF8` | `TVF_Lookup_Depth_Amount` | index → `(amount<<8) | sign`, plus a signed **level trim** to a global |
| `0x024444` | `LABEL_024444` | `TVF_Emit_Registers` | 6-way dispatch on `VP[+0x36]&7`, ships `+0x100`/`+0x140` with the live controller offset |
| `0x024366` | `LABEL_024366` | `TVF_Emit_Offset_Reg100` | applies `part[+0x1f]` to the `+0x100` cutoff field only |
| `0x0243CC` | `LABEL_0243CC` | `TVF_Emit_Offset_Both` | applies it to both registers' low 7 bits |
| `0x0253FE` | `LABEL_0253FE` | `Level_Build_Reg0C0` | builds the part/patch level register `+0x0C0` |

## 4. Routine names — G. MULTI-PARTIAL

| address | old | new name | purpose |
|---|---|---|---|
| `0x032B1E` | `LABEL_032B1E` | `Partial_Build_Present_Word` | **the real entry point** — rebuilds the runtime partial-present word from `patch[+0x11]`/`[+0x12]` |
| `0x032B6B` | `LABEL_032B6B` | `Partial_Try_Unison_Slot0` | synthesise partial 0 as a unison twin of partial 1 (`OR 0x4001`) |
| `0x032C0F` | `LABEL_032C0F` | `Partial_Try_Unison_Slot1` | synthesise partial 1 as a unison twin of partial 0 (`OR 0x8002`) |
| `0x02BA2C` | `LABEL_02BA2C` | `Voice_Build_Four_Partials` | calls the descriptor builder four times with masks 1/2/4/8 |

---

## 5. CORRECTIONS — notes that turned out to be wrong or imprecise

These are the load-bearing results of the pass. Each was found by reading the code after
reading the note, not by re-deriving the note.

### 5.1 `ToneGen_Calc_Pitch` computes **no pitch** — it is the key-bed velocity decoder ★
The symbol has carried that name in the disassembly for a long time and
`notes/kn5000-pitch-velocity.md` cites it as if it were part of the pitch path
("Touch-sensitivity scaling is applied UPSTREAM in the sub-CPU velocity curve (mode 0x4A48,
`ToneGen_Calc_Pitch`)"). The routine at `0x03D11F` does exactly two things:
`(XWA+0) = (key & 0x7F) + 0x24` (the MIDI note) and `(XWA+1) = velocity`, the latter through
the whole touch chain. Renamed `Keybed_Decode_Event`, and its five interior labels renamed off
`ToneGen_Pitch_*`. **MEASURED** (L51556-51641).

### 5.2 The touch record has a **third** byte — a BLACK-KEY velocity trim (NEW) ★
`notes/kn5000-variant-model.md` §3.3 documents the touch curve as
`G = T_GAIN[0x01F420 + 3*mode]`, `O = T_OFF[0x01F421 + 3*mode]` — two bytes with an
unexplained stride of 3. The third byte is used: after the gain/offset stage the routine does
`DIV_C 0x0C` on the MIDI note and takes the **remainder**, and if the pitch class is
**1, 3, 6, 8 or 10** — precisely the five black keys — it subtracts `[0x01F422 + 3*mode]`.
Dumped this pass:

```
mode   0    1    2    3    4    5    6    7    8    9
gain  00   10   20   30   40   50   60   70   80   90
off   D0   C7   BD   B4   AB   A1   98   8F   86   82
black 00   03   06   08   0B   0E   10   13   16   18      <-- NEW
```

So the firmware compensates the different mechanical travel of the black keys, by an amount
that scales with the touch-sensitivity setting (0 at touch OFF, 24 at maximum). The
`KEYBED_TIME[128]` conversion table proposed in §3.3 of that note is therefore correct only
for white keys; a black key given the same travel-time byte comes out up to 24 strength units
— several velocity steps — softer. **MEASURED** (L51586-51604 + ROM bytes at
file offset `0x10520`).

### 5.3 `LABEL_024300`'s family is **not an LFO** — it is the same TVF pair ★
`notes/audit/kn5000-audit-pitch.md` §1.3 states "`+0x100`/`+0x140` are built by `LABEL_024300`
… as an **LFO** rate/depth/delay/waveform pair", and its **GAP 9** ("no vibrato is ever
produced") is built on that reading. Reading the code: `LABEL_024300` dispatches on
`VP[+0x0F]&7` to `{022DA1, 02413E, 0241A0, 024205, 024250, 0242A1}`, and `LABEL_02413E`
computes

```
V          = TVF_Calc_Cutoff_NoKeyFollow(base = VP[+0x11], depth = VP[+0x10],
                                         curve = VP[+0x0F] >> 5)
desc[+0x42] = ((VP[+0x12] & 7) << 13) | 0x0400 | V      -> +0x100
desc[+0x44] = TVF_Lookup_Depth_Amount(VP[+0x14]) | TVF_Bias_Clamp_Amount(VP[+0x13])  -> +0x140
```

— structurally **identical** to `LABEL_023D01`, field for field, only with the short parameter
set and no key-follow term. There is no rate, no delay and no waveform anywhere in either
family. `notes/audit/kn5000-audit-timbre.md` §1.3/§5.4 (same day, later) has it right; the
pitch audit's §1.3 and GAP 9 should be retracted. The observed live values
(`+0x100 = 0x2466`, `+0x140 = 0x6FDA`) are a cutoff and a depth pair, not "an LFO *is*
programmed". **MEASURED** (L16962-17004, L16772-16810).

### 5.4 The voice descriptor lives in **two** arrays, and the builders read the second ★
`notes/kn5000-variant-model.md` §1/§4.1 records only "its own voice descriptor
`0x2942 + 0x47·p`". That array is a **4-entry staging** array indexed by partial slot.
`Voice_Build_Register_Set` (`LABEL_02B4E3`, the 17 builders) reads
**`0x04308E + 0x47 · chip_voice`** — a 64-entry live array indexed by the chip voice number.
The note-on path copies between them with `LDIRW` + `LDI` (0x23 words + 1 byte = 0x47 bytes,
L27447-27456 / L27464-27473) and then stamps the voice number into `[+0]`. All `desc[+0xNN]`
offsets are identical in both. Everything downstream of the copy — pitch, TVF, level — reads
the **live** array, so any HLE-side or documentation reference to "the descriptor" must say
which. **MEASURED**.

### 5.5 `Partial_Build_Present_Word` starts at `0x032B1E`, and there are **two** unison paths ★
`notes/kn5000-variant-model.md` §4.1/§4.2 gives the range "`LABEL_032C0F`-`LABEL_032D33`
L35317-35427" and documents one synthesis rule (`DE |= 0x8002`). `LABEL_032C0F` is an interior
branch label; the function begins at `LABEL_032B1E` (L35233). The missing first half contains
the **mirror-image** rule:

```
DE = old_present_word & 0x3FF0                  ; bits 0..3 and 14..15 rebuilt, 4..13 kept
if patch[+0x11] bit0: SET 0,DE                  ; partial 0 present
else if part[+0x0a] bit15 and patch[+0x11] bit2 and (patch[+0x5D]&0x0F) <= 8:
        DE |= 0x4001                            ; partial 0 SYNTHESISED from partial 1
if patch[+0x11] bit2: SET 1,DE
else if part[+0x0a] bit15 and patch[+0x11] bit0 and (patch[+0x5D]&0x0F) <= 8:
        DE |= 0x8002                            ; partial 1 SYNTHESISED from partial 0
if patch[+0x11] bit4: SET 2,DE
if patch[+0x11] bit6: SET 3,DE
*(0x04136A + 0x11F*part) = DE
```

`Voice_Build_Four_Partials` reads bit 14 (L27311) and bit 15 (L27354) symmetrically, which
only makes sense with both rules present. **MEASURED**.

### 5.6 `patch[+0x12]` is a second 2-bit-per-partial field, and it writes the slot flags (NEW)
Interleaved with the presence tests, the same routine tests `patch[+0x12]`:
`(x & 0x03) == 1`, `(x & 0x0C) == 4`, `(x & 0x30) == 0x10`, `(x & 0xC0) == 0x40` — i.e. the
2-bit code **01** for each partial — and sets or clears **bit 15** of the word at
`0x0413EE / 0x041413 / 0x041438 / 0x04145D + 0x11F·part`. Those four addresses are
`part_struct + 0x6E + 0x25·p + 0x18` for `p = 0..3` — exactly `desc[+0x27][+0x18]`, the
per-slot flags word whose **bits 4/5** gate the pitch detune (`Pitch_Emit_Reg400`) and whose
**bits 6/7** gate the TVF controller offset (`TVF_Emit_Offset_*`). So the patch record carries
a per-partial mode in `+0x12` that is *distinct* from the presence map in `+0x11`.
Also: only the **even** bits of `patch[+0x11]` are read here; the odd bits are not read by this
builder (the "2-bit-per-partial present map" phrasing overstates what is proven).
**MEASURED**.

### 5.7 `Pitch_Get_Patch_Octave_Shift` is an **octave** table, not a general key shift
`notes/audit/kn5000-audit-pitch.md` §1.2 calls table `0x011ACF` a "per-patch key shift".
Its 16 bytes are `A0 AC B8 C4 D0 DC E8 F4 00 0C 18 24 30 3C 48 54` = `−96,−84,…,0,…,+84`
semitones — exact steps of **12**, index 8 = no shift. The routine also returns 0 outright
when `ToneGen_GlobalFlags` bit 1 is set. **MEASURED** (ROM bytes + L14166-14200).

### 5.8 Scale tuning has a second source and a second gate
The audit's pitch chain shows only the global path. The code first calls
`ScaleTune_Is_Global_Enabled` (`flags & 0x0200`): if **clear** the mode byte comes from the
**patch record** `+0x13`, not from the panel's `0x04134D`. And on the global path there is an
extra gate — `Part_PresentWord` **bit 8** must be set or the whole scale-tuning term is
skipped. Mode `0x80` reads `ScaleTune_UserOffsets` = `0x04134E + (key mod 12)`, a 12-byte RAM
user scale. **MEASURED** (L15546-15567, L15610-15628).

### 5.9 `Pitch_Fold_Octaves_Into_Range` has a wrap-normalising first stage
The audit describes only "folds by whole octaves until the value lies in `[kmin,kmax]`".
Before that, the routine loops `while (bit15 set) { if (pitch <= 0xC000) pitch -= 0x0C00;
else pitch += 0x0C00; }` — i.e. it repairs a 16-bit **wrap** by whole octaves, in both
directions, before the range fold. Without it a pitch that under- or overflowed would fold
from the wrong side. **MEASURED** (L14246-14262).

### 5.10 The `+0x140` depth table's third byte is a LEVEL trim, and it is consumed
`notes/audit/kn5000-audit-timbre.md` §1.4 notes that `LABEL_022CF8` "also stash[es] a signed
byte `C` in the global `0x2940`" but not where it goes. It is read back in the **amplitude**
accumulator (`ADD IZ,(2940h)` L20479 and `ADD HL,(2940h)` L20613), so the TVF depth index also
applies a make-up gain in the level domain: `0, −16, −13, −11, −8, −5, −3, 0…` for indices
`0..6`. The two tables are at `0x0119FB` (index bit 7 clear) and `0x011A25` (bit 7 set), each
16 records of `{sign, amount, level-trim}`. **MEASURED**.

### 5.11 `TVF_Build_Full` has a conditional `+0x140` override
The audit gives `desc+0x44 = LABEL_022CF8(VP[+0x50]) | LABEL_022CE8(VP[+0x4f])` unconditionally.
That is the default branch: when **`Part_PresentWord` bit 9** is set, the builder substitutes
the constants `0x48` and `0x8D` for the two patch bytes (L16354-16366). **MEASURED**.

### 5.12 TVF key follow uses the **transposed** pitch, not the played key
`TVF_Calc_Cutoff` reads `(desc[+0x08] >> 8) & 0x7F`, and `desc[+0x08]` is the *absolute log
pitch after every transpose and scale-tuning term*, written by `Pitch_Resolve_Key_Zone`. The
audit says "the played note", which is only true for an untransposed patch. For the 273
patches that carry a transpose the filter tracks the **sounding** note. **MEASURED**.

### 5.13 Minor precisions
* `TVF_Build_Dispatch` and `TVF_Emit_Registers` accept indices 0..5; **6 and 7 fall through to
  the bypass entry** (the `CP BC,0 / JR MI` guard is dead — the value is zero-extended).
* `Pitch_Clamp_Into_Range` also performs the bit-15 saturation, which the audit attributes only
  to `Pitch_Saturate_15bit`.
* `Voice_Build_Partial_Descriptor`'s velocity boost (`+0x28` on part 0, `+0x0C` on part 1 when
  `ToneGen_GlobalFlags` bit 1 is set) is clamped through a `[0,0x7F]` helper, and happens
  **after** the split decision — confirming `notes/kn5000-variant-model.md` §3.2.
* Notes `>= 0x78` take a separate path in `Voice_Build_Partial_Descriptor` that is only viable
  when `SET[0]` bit 1 is set; otherwise the partial is silently dropped. Purpose
  **NOT ESTABLISHED** — deliberately left unnamed.
* `LABEL_022982` (the 4-byte block reached by the `0xF693` dispatch inside
  `Pitch_Get_Patch_Octave_Shift`, for part indices `0x10..0x19`) is **NOT ESTABLISHED** and
  keeps its `LABEL_` name.

---

## 6. EQU-style symbol proposals (data, RAM state, struct offsets)

Applied to the disassembly as a documentation-only `EQU` block (an `EQU` emits no bytes; the
operands in the code are deliberately **not** substituted, so the image stays byte-identical).

### 6.1 Key bed — travel time → MIDI velocity

| symbol | address | what it is |
|---|---|---|
| `Keybed_Touch_TimeRef` | `0x01F418` | word `0x004D`, the travel-time reference point |
| `Keybed_Touch_Divisor` | `0x01F41A` | word `0x0080`, the gain divisor |
| `Keybed_Touch_Curve_Table` | `0x01F420` | 10 × 3-byte records, indexed by touch mode |
| `Keybed_Touch_Curve_Gain` | `+0x00` | record field: gain `00,10,…,90` |
| `Keybed_Touch_Curve_Offset` | `+0x01` | record field: offset `D0,C7,…,82` |
| `Keybed_Touch_Curve_Black` | `+0x02` | record field: **BLACK-KEY trim** `00,03,…,18` |
| `Keybed_Time_To_Strength` | `0x01F43E` | 256 bytes, monotone **decreasing** (T1) |
| `Keybed_Strength_To_Velocity` | `0x01F53E` | 256 bytes, monotone **increasing**, 1..127 (T2) |
| `Keybed_Touch_Mode` | RAM `0x4A48` | TOUCH SENSITIVITY 0..9, power-on default 6 |

### 6.2 Pitch — ROM tables

| symbol | address | what it is |
|---|---|---|
| `Patch_OctaveShift_Table` | `0x011ACF` | 16 signed bytes, `−96…+84` semitones in steps of 12 |
| `ScaleTune_PerKey_Offsets_41` | `0x00FCE4` | 128 words, scale-tuning mode `0x41` |
| `ScaleTune_PerKey_Offsets_42` | `0x00FDE4` | 128 words, scale-tuning mode `0x42` |
| `ScaleTune_Temperament_Table` | `0x011B68` | 12 rows × 12 signed bytes; row 0 is all zeros (equal temperament); unit = 2/256 semitone = 0.78 cent |
| `Pitch_Bend_Curve_Table` | `0x011C7C` | signed bytes; `value × 2` → `Pitch_BendValue` |

### 6.3 Pitch — RAM state

| symbol | address | what it is |
|---|---|---|
| `ToneGen_GlobalFlags` | `0x041343` | bit 1 patch-octave disable / velocity boost, bit 9 global scale tuning, bit 10 bend active, bits 11–14 bend-ramp state |
| `Pitch_MasterFineTune` | `0x041347` | word, `(panel byte − 0x40) × 2` |
| `Pitch_MasterTranspose` | `0x041349` | word, `sext(panel byte) << 8` |
| `Part_Mode_Byte` | `0x04134C` | global part mode (5/6 force the `+0x0C0` low field to `0x7F`) |
| `ScaleTune_GlobalMode` | `0x04134D` | `0x00/0x40/0x41/0x42/0x80` or a temperament row |
| `ScaleTune_UserOffsets` | `0x04134E` | 12 signed bytes, one per pitch class (C…B) |
| `Pitch_BendValue` | `0x04135A` | word, 1/256 semitone |
| `Pitch_BendRampPhase` | `0x04135C` | word, index into `Pitch_Bend_Curve_Table` |
| `Pitch_ScaleTune_FlatOffset` | `0x041366` | word, the scale-tuning mode-`0x40` constant |

### 6.4 Timbre / TVF

| symbol | address | what it is |
|---|---|---|
| `TVF_Velocity_Curves` | `0x011519` | 7 × 128 signed bytes, `−64` at velocity 0 → ≈0 at 127 |
| `TVF_Depth_Table_A` | `0x0119FB` | 16 × 3 bytes `{sign, amount, level trim}` (index bit 7 clear) |
| `TVF_Depth_Table_B` | `0x011A25` | mirror table (index bit 7 set) |
| `TVF_Depth_LevelTrim` | RAM `0x2940` | written by `TVF_Lookup_Depth_Amount`, read by the amplitude accumulator |

### 6.5 Voice descriptors, part structs and the chip scratch

| symbol | address | what it is |
|---|---|---|
| `WaveSel_Zone_Trim` | RAM `0x293E` | per-zone tuning trim, 1/256 semitone |
| `Voice_Desc_Staging` | RAM `0x2942` | 4 × 0x47 bytes, indexed by **partial slot** `p` |
| `Voice_Desc_Table` | RAM `0x04308E` | 64 × 0x47 bytes, indexed by **chip voice** number |
| `Part_Struct_Base` | RAM `0x041368` | 0x11F bytes per part |
| `Part_PresentWord` | `+0x02` = `0x04136A` | bits 0–3 partial present, bit 8 scale-tune enable, bit 9 fixed `+0x140`, bits 14/15 unison cross flags |
| `Part_PatchRecord_Ptr` | `+0x06` = `0x04136E` | pointer to the 629-record patch table entry |
| `Part_Flags0A` | `+0x0a` = `0x041372` | bit 15 arms the unison layer |
| `Part_Slot_Sub_Base` | `+0x6E` = `0x0413D6` | 4 × 0x25-byte per-partial slots |
| `Part_Slot_SetPtrs` | slot `+0x08` = `0x0413DE` | 4 SET-descriptor pointers, one per velocity zone |
| `Part_Slot_Flags` | slot `+0x18` = `0x0413EE` | b4/b5 pitch detune enable+sign, b6/b7 TVF offset enable+sign, b15 from `patch[+0x12]` code 01 |
| `TG_Scratch_Base` | `0x0451CC` | 0x2C-byte tone-generator parameter scratch |
| `TG_Scratch_Reg040` | `+0x02` = `0x0451CE` | → chip `+0x040` wave select |
| `TG_Scratch_Reg0C0` | `+0x06` = `0x0451D2` | → chip `+0x0C0` part/patch level |
| `TG_Scratch_Reg100` | `+0x08` = `0x0451D4` | → chip `+0x100` TVF cutoff |
| `TG_Scratch_Reg140` | `+0x0a` = `0x0451D6` | → chip `+0x140` TVF depth pair |
| `TG_Scratch_Reg400` | `+0x0e` = `0x0451DA` | → chip `+0x400` log pitch |

### 6.6 Struct offsets referenced by the headers (documented in prose, not EQU'd)

Voice descriptor (`Voice_Desc_Staging[p]` and `Voice_Desc_Table[ch]`, 0x47 bytes):

```
+0x00  chip voice number (stamped after the copy)
+0x01  word: bits 6..7 velocity zone q, bit 2 always set, bit 10 BEND enable,
              bits 12..15 the wave-record class from WaveSel_Build_Reg040
+0x03  partial slot p          +0x04  part index
+0x05  played key | 0x80       +0x06  zone-folded log pitch (drives pitch AND wave)
+0x08  absolute log pitch      +0x0a  detuned log pitch
+0x0c  velocity                +0x0f  zone record pointer
+0x13  tone/patch record       +0x17  0x51-byte partial block (VP)
+0x1b  velocity split record   +0x1f  SET descriptor (velocity-selected)
+0x23  part struct             +0x27  part_struct + 0x6E + 0x25*p (this partial's slot)
+0x42  the +0x100 word         +0x44  the +0x140 word
```

Partial block `VP` (0x51 bytes), TVF-relevant fields:

```
long set : +0x36 b2:0 builder select, b7:5 velocity curve; +0x37 velocity depth;
           +0x39 key-follow centre, +0x3a/+0x3b key range lo/hi; +0x3c key-follow depth;
           +0x4d base cutoff; +0x4e -> +0x100 bits 15:13; +0x4f -> +0x140 low 7 bits;
           +0x50 depth-amount index (bit 7 selects the table)
short set: +0x0f b2:0 builder select, b7:5 velocity curve; +0x10 velocity depth;
           +0x11 base cutoff; +0x12 -> +0x100 bits 15:13; +0x13 -> +0x140 low 7;
           +0x14 depth-amount index
pitch    : +0x04 coarse transpose (semitones), +0x05 fine transpose (x2),
           +0x06 b2:0 key-follow mode L (0 = full, 7 = FIXED pitch)
```

Chip register `+0x100` bit layout (MEASURED):
`{[15:13] 3-bit field from VP, [10] computed-cutoff-present, [8] set only by the bypass
constant, [7] mode flag set by some builders, [6:0] CUTOFF 0..0x78, 0x7F = bypass}`.

---

## 7. Verification

Baseline and post-edit, using the repo's own ASL flow:

```
make rebuilt_ROMs/kn5000_subprogram_v142.rebuilt.rom
cmp rebuilt_ROMs/kn5000_subprogram_v142.rebuilt.rom original_ROMs/kn5000_subprogram_v142.rom
```

Both produce `2a83880411869c56664b1fa04443b8b7` — **byte-identical**, 0 errors, 0 warnings.
No symbol collided; nothing was left unrenamed for collision reasons.

## 8. Deliberately NOT named

* `LABEL_022982` — the 4-byte block the `0xF693` dispatch reaches for part indices
  `0x10..0x19`. Purpose not established.
* The `>= 0x78` note path in `Voice_Build_Partial_Descriptor`.
* `LABEL_023DB5`, `LABEL_023EC2`, `LABEL_023FBD`, `LABEL_02403D`, `LABEL_0241A0`,
  `LABEL_024205`, `LABEL_024250`, `LABEL_0242A1` — the TVF builder variants no stock sound
  selects. They fill the same two registers, but which parameter fields they read has not been
  traced, so a name would be a guess.
* `LABEL_023A99` — a variant of `Pitch_Emit_Reg400` whose destination was not confirmed.
* `LABEL_032839` — the SET resolver called by `Partial_Store_Set_Pointer`; it belongs to the
  WAVE-SELECT subsystem.
* The **meaning** of `+0x140` (decode exact, role not established) and of `+0x080` bits[14:12]
  — both remain open per `notes/audit/kn5000-audit-timbre.md` GAP 2 / GAP 3.
