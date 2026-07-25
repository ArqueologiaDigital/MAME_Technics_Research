# KN5000 tone-gen — the MODEL of what makes sound VARIANTS differ (firmware-derived)

Author: autonomous MODEL pass, 2026-07-25. Requested by Felipe Sanches, following the DIAGNOSE
pass (`notes/kn5000-variant-diagnosis.md`, `ffda058`) and the working data-derived wave map
(`e2f8b60`).

**Investigation only — no `src/` edits, no rebuild, no MAME run this pass.** Everything below is
read out of the firmware's own code and data: the v142 sub-CPU disassembly
(`kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`, all `L<n>` = line numbers in
that file), the sub-program ROM (`kn5000_subprogram_v142.rom`), and the Table-Data ROM
(IC3/IC1 interleaved). **No heuristics, no clustering, no ear-cataloguing, no invented mappings.**
Where something is not derivable it is said so (§9).

Evidence labels: **MEASURED** (a ROM byte or a disassembled instruction) /
**PROVEN-BY-CONSTRUCTION** (follows from a fully traced code path) / **INFERRED** / **SPECULATIVE**.

Address model (unchanged, `kn5000-firmware-sample-tables.md §1`):
sub-CPU DB address `S` → `table_data` region offset `S − 0x20000`, main-CPU `S + 0x7E0000`;
all DB-internal pointers are rel32 against `*(0x045310) = 0x050000`.
**Sub-program ROM file offset = address − 0xEF00** (MEASURED: the `LABEL_022864` data blob is at
file offset `0x13964`; `0x022864 − 0x13964 = 0xEF00`) — this pass's key unlock for reading the
firmware's own *curve tables*, which live in the code ROM, not the Table-Data ROM.

---

## 0. TL;DR — the four mechanisms, and what the HLE must do

| # | mechanism | status in the firmware | status in the HLE | HLE change required |
|---|---|---|---|---|
| 1 | **VELOCITY SPLIT** — 3 split bytes + 4 `(fine,set)` pairs pick a *different multisample SET*, i.e. a **different `+0x040`** | fully decoded, §3. Rule is `q=0` for the **softest** note — the original `-sample-tables.md §5` statement is **CORRECT** | the *rule* is right; the **key-bed bridge feeds it an inverted quantity** | **YES — `kn5000.cpp`**: the key-bed FIFO high byte is a **key-travel TIME**, not a velocity. §3.3 gives the exact 128-entry conversion table |
| 2 | **MULTI-PARTIAL** — `patch[+0x11]` bit 2·i ⇒ partial *i*; up to **4** partials, each its own chip voice; plus a **synthesised unison partial** for 1-partial patches | fully decoded, §4 | the firmware already emits N independent voices and the HLE renders them all | **no** — but the unison layer is *inaudible* until #3 is fixed (it differs only in `+0x400`) |
| 3 | **TRANSPOSE / DETUNE** — coarse `blk[+0x04]` (semitones, also moves the key zone) and fine `blk[+0x05]` (×2 into `+0x400`), plus the unison detune | fully decoded, §5; **`+0x400` reproduced from ROM bytes 15/16, `+0x040` 19/19** | `update_pitch()` takes pitch from `true_note` and **never reads `+0x400`** for keyed voices | **YES — `kn5000_tonegen.cpp`**: §7.2 gives a three-tier register-only fix |
| 4 | **PATCH-LEVEL TIMBRE** — level, EG, LFO | the scratch→register map is now complete (§6.1) and the *specific* per-variant fields are named (§6.2-6.6) | the HLE reads **4 of 32** per-voice registers | **YES**, and it is a bounded job: render the **4-stage EG** (`+0x9C0/+0xA00/+0xA40`) and the **LFO** (`+0x100/+0x140`). §7.4 |

**The single most consequential finding of this pass** is #1: the firmware's velocity chain is
`FIFO byte → T1[] (a monotone DECREASING table) → touch curve → T2[] → velocity`, so the MAME
bridge — which writes the MIDI velocity straight into that byte — inverts every velocity in the
machine. This **retires MISS #1 of the diagnosis** (which concluded the *zone order* was inverted):
the zone order is exactly as documented; the *input* is inverted. Verified by predicting the
diagnosis's own measured crossings on three instruments: **12/12** (§3.4).

Census over all 629 patches (**MEASURED**): 258 patches declare 1 partial, 216 declare 2, 88
declare 3, 23 declare 4; **235** 1-partial patches are eligible for the synthesised unison layer;
**24** carry a real velocity split; **273** carry a non-zero partial transpose; **208** carry a
non-neutral `patch[+0x5C]` (the `+0x0C0` term).

---

## 1. The note-on pipeline (call graph, MEASURED)

```
Voice_NoteOn                     L29430   XWA -> {status, part, note, velocity}
  └ Voice_SetVelocity(A=part, C=note, E=VELOCITY, stack=status&7)      L28707
      dispatch on  patch_record[+0x10] & 0xC0        (record TYPE byte)
        0x00 -> LABEL_02BA2C   ***the mainline builder, 4 partials***  L27289
        0x40 -> LABEL_02BF1B   (type 0x60 = drawbar registrations)     L27759
        0x80 -> LABEL_02C2C0   (2 partials)                            L28115
        0xC0 -> return
      then for i = 0..3:  ch = scratch[0x0a+i]; if ch < 0x40:
                            LABEL_02B4E3(ch)  (17 builders)            L26803
                         or LABEL_02C0B6(ch)  (12 builders)            L27927
                            -> ToneGen_WriteVoiceParams(ch, 0x0451CC)  L29565

LABEL_02BA2C  L27289 — calls LABEL_02B717 FOUR times, masks DE = 1, 2, 4, 8:
      LABEL_02B717(part, DE=mask, [a1, VELOCITY, note, a4, p])          L27004
        if ( u16(0x04136A + 0x11F*part) & DE ) == 0  -> partial absent, skip
        VSEL   = *(part_struct + 0x6E + 0x25*a4 + 0x04)
        q      = LABEL_022824(VELOCITY, VSEL)                           L14015
        blk    = *(part_struct + 0x6E + 0x25*a4 + 0x00)   (the 0x51 patch partial block)
        SETp   = *(part_struct + 0x76 + 0x25*a4 + 4*q)    ***velocity-selected SET***
        desc   = 0x2942 + 0x47*p            (the per-partial voice descriptor)
        desc[+0x01] = (q<<6)|0x04   desc[+0x03] = p    desc[+0x04] = part
        desc[+0x05] = note|0x80     desc[+0x0c] = velocity
        desc[+0x13] = patch record  desc[+0x17] = blk   desc[+0x1b] = VSEL
        desc[+0x1f] = SETp          desc[+0x23] = part_struct
        desc[+0x27] = part_struct + 0x6E + 0x25*p
        LABEL_023584(desc)          (pitch / key / zone)                L15504
```

`part_struct = 0x041368 + 0x11F·part`; `*(0x04136E + 0x11F·part)` is the **patch record base**
(PROVEN: `Voice_SetVelocity` L28714-28721 dispatches on `[+0x10]`, which is the record's type byte
`0x00/0x10/0x20/0x30/0x60` — so the pointer is the record start, not `record+0x66`).

**This closes gap #1 of `kn5000-firmware-sample-tables.md §10`** ("which structure supplies
`desc+0x17` when a voice comes from a 0x51 patch block"): it is the 0x51 block of *partial slot
`a4`*, deposited by `LABEL_02B717` L27058-27060.

---

## 2. The scratch buffer is the Rosetta stone

`ToneGen_WriteVoiceParams(WA=chip voice, XBC=0x0451CC)` (L29565) ships a flat 0x2C-byte scratch
buffer to the chip, one word per register, in this fixed order (**MEASURED**, every `ADD WA,xxxx`
/ `LD WA,(XWA+nn)` pair in the routine):

| scratch | chip reg | | scratch | chip reg | | scratch | chip reg |
|---|---|---|---|---|---|---|---|
| `0x0451CE` | **+0x040** | | `0x0451DA` | **+0x400** | | `0x0451E8` | +0x880 |
| `0x0451D0` | **+0x080** (bit15 forced) | | `0x0451DC` | +0x440 | | `0x0451EA` | +0x8C0 |
| `0x0451D2` | **+0x0C0** | | `0x0451DE` | +0x480 | | `0x0451EC` | +0x900 |
| `0x0451D4` | **+0x100** | | `0x0451E0` | +0x4C0 | | `0x0451EE` | +0x940 |
| `0x0451D6` | **+0x140** | | `0x0451E2` | +0x500 | | `0x0451F0` | +0x980 |
| `0x0451D8` | +0x180 | | `0x0451E4` | **+0x800** | | `0x0451F2` | +0x9C0 |
| | | | `0x0451E6` | +0x840 | | `0x0451F4` | **+0xA00** |
| | | | | | | `0x0451F6` | **+0xA40** |

(`+0x080` is written twice — first with bit 15 set, again at the very end of the burst.)

Because the buffer is at fixed addresses, **every register now has a named writer** (grep for
`(0451xxh)`), which is what makes §6 possible.

---

## 3. MECHANISM 1 — VELOCITY SPLIT

### 3.1 The exact rule (MEASURED, `LABEL_022824` L14015 / `LABEL_022844` L14040 — byte-identical twins)

```
LABEL_022824(A = velocity, XBC = VSEL record):
    RES 7, A                       ; v = velocity & 0x7F
    q = 0   if v <= VSEL[0]
        1   if v <= VSEL[1]
        2   if v <= VSEL[2]
        3   otherwise
    return q  (in L)
```

**`q = 0` is the SOFTEST layer.** `kn5000-firmware-sample-tables.md §5` is correct as written.

### 3.2 Does the chosen `(fine,set)` reach a DIFFERENT SET descriptor? — YES, PROVEN-BY-CONSTRUCTION

`LABEL_0328B5` (L34974) reads the pair for zone `q` at `VSEL[3+2q]` (fine) / `VSEL[4+2q]` (set),
runs stage A2 (`LABEL_032750`), and `LABEL_0328E2` (L34996) **stores the resulting SET-descriptor
pointer at `part_struct + 0x76 + 0x25·p + 4·q`** — i.e. the firmware pre-computes, per partial
slot, an array of **four** SET descriptors, one per velocity zone. `LABEL_02B717` L27063-27065
then indexes that array with `q` and puts the result in `desc[+0x1f]`, and `LABEL_023849` (L15805,
the `+0x040` builder) reads `desc[+0x1f]` as its SET. **So velocity chooses the SAMPLE, not just a
level** — exactly as the live capture shows (E.Piano 1: four distinct `+0x040` words, all four
zones observed; Suitcase E.P. and Modern E.P.1 likewise, `kn5000-variant-diagnosis.md §3.4`).

The velocity that reaches `LABEL_022824` is the raw note-on velocity (`Voice_NoteOn` L29444
`LD E,(XIZ+003h)` → `Voice_SetVelocity` E → `LABEL_02BA2C` stack → `LABEL_02B717` `(XSP+0x20)`).
The later `(0x041343) bit1` adjustment (`LABEL_02B717` L27141-27152, `+0x28` on part 0, `+0x0C` on
part 1) happens **after** the split decision and only affects `desc[+0x0c]`.

### 3.3 THE POLARITY DEFECT — the key bed reports a TIME, not a velocity (MEASURED)

`ToneGen_Read_Voice_Data` (L51500) reads the 16-bit key-bed FIFO at `0x110000`:
`L = low byte = key`, `E = high byte`. `ToneGen_Calc_Pitch` (L51556) then converts:

```
x    = T1[E]                       ; byte table @0x01F43E, 256 entries
mode = *(0x4A48)                   ; TOUCH SENSITIVITY 0..9, default 6 (ToneGen_Init L51415)
G    = T_GAIN [0x01F420 + 3*mode]  ; 00 10 20 30 40 50 60 70 80 90
O    = T_OFF  [0x01F421 + 3*mode]  ; D0 C7 BD B4 AB A1 98 8F 86 82
y    = clamp( (x - 0x4D) * G / 0x80 + O , 0 , 0xFF )     ; K1=0x4D @0x01F418, D=0x80 @0x01F41A
vel  = T2[y]                       ; byte table @0x01F53E, 256 entries -> 1..127
```

**`T1 @0x01F43E` is strictly monotone DECREASING** (`FF FF … FF FB F6 F1 …` down to `01 01 … 00`) and
**`T2 @0x01F53E` is monotone INCREASING** (`01 02 … 7F`). Both dumped from
`kn5000_subprogram_v142.rom` at file offsets `0x1053E` / `0x1063E`. A decreasing input table is
only meaningful if the FIFO byte is a **key-travel time** (make→break interval): short time =
hard strike = high velocity.

`kn5000.cpp` puts the **MIDI velocity** in that byte
(`keybed_scan()` L409 `(KEYBED_VELOCITY << 8) | …`, `kbd_midi_rx()` L234 `(vel << 8) | …`), so the
whole machine runs with an inverted, non-linear velocity. That is a *key-bed* modelling defect,
inside the key bed's own interface — the chip boundary is not involved.

**The conversion table the driver should write instead** (mode 6, the power-on default;
`raw = argmin |fw(raw) − v|`, 117/127 exact, max round-trip error 1):

```c
// MIDI velocity -> key-bed travel-time byte. MEASURED: the sub-CPU maps this byte through
// T1[] @0x01F43E (monotone DECREASING) + the TOUCH curve (mode 6 = power-on default,
// ToneGen_Init L51415) + T2[] @0x01F53E. Index 0 is unused (velocity 0 = note off).
static const uint8_t KEYBED_TIME[128] = {
    0,222,222,217,211,206,202,197,194,189,183,178,172,168,165,161,
  157,156,153,152,151,149,147,146,143,142,141,139,138,136,136,135,
  134,133,132,131,130,129,128,125,124,123,120,119,118,115,114,113,
  111,110,109,107,106,104,104,103,102,101,100, 99, 98, 97, 96, 93,
   92, 91, 88, 87, 86, 83, 82, 81, 79, 78, 77, 75, 74, 72, 72, 71,
   70, 69, 68, 67, 66, 65, 64, 61, 60, 59, 56, 55, 54, 51, 50, 49,
   47, 46, 45, 43, 42, 40, 40, 39, 38, 37, 36, 35, 34, 33, 32, 31,
   30, 28, 28, 27, 27, 26, 25, 24, 24, 23, 22, 22, 21, 20, 20,  0 };
```

(`KEYBED_VELOCITY = 100` for the PC keyboard becomes `KEYBED_TIME[100] = 42`.)

### 3.4 PREDICT-THEN-CHECK — the defect reproduces the diagnosis's measurements exactly

Running the *broken* bridge through the traced chain (MIDI velocity → `T1` → touch mode 6 → `T2`
→ `LABEL_022824`) predicts these zone crossings; the diagnosis measured them independently on a
5-step velocity sweep and never saw this code:

| instrument | splits | predicted crossings (broken bridge) | diagnosis MEASURED | |
|---|---|---|---|---|
| E.Piano 1 | 3C/50/64 | q3→q2 at **v42**, q2→q1 at **v70**, q1→q0 at **v98** | between 39-44, 69-74, 94-99 | **3/3** |
| Suitcase E.P. | 59/6D/7F | q2 for v<33, q1 for 33-58, q0 for ≥59 | v20→q2, v45→q1, v70→q0 | **3/3** |
| Modern E.P.1 | 3B/4F/63 | q3 for v<43, q2 43-70, q1 71-98, q0 ≥99 | v20→q3, v45,70→q2, v90→q1, v110,127→q0 | **6/6** |

**12/12.** With the table of §3.3 in place the crossings move to v61/81/101, v90/110/–,
v60/80/100 — i.e. onto the split bytes themselves, which is what the data means.

The diagnosis's crude fit `x ≈ 127 − 0.65·vel` is now the exact table, and its
"the comparison is against a level that falls with velocity" is now identified as
"the comparison is against the velocity, but the velocity the firmware computed is inverted".

---

## 4. MECHANISM 2 — MULTI-PARTIAL

### 4.1 The present map (MEASURED, `LABEL_032C0F`-`LABEL_032D33` L35317-35427)

The runtime word at `0x04136A + 0x11F·part` (= `part_struct[+0x02]`) is built bit by bit from the
patch record's `+0x11`:

```
if patch[+0x11] bit 0  -> DE bit 0      (partial 0)
if patch[+0x11] bit 2  -> DE bit 1      (partial 1)      L35314
if patch[+0x11] bit 4  -> DE bit 2      (partial 2)      L35404
if patch[+0x11] bit 6  -> DE bit 3      (partial 3)      L35400
*(0x04136A + 0x11F*part) = DE                            L35423
```

`LABEL_02B717` masks that word with `DE = 1, 2, 4, 8` for partials 0-3 (L27012-27015). So the
"2 bits per partial, bit 2·i" reading of `+0x11` is **PROVEN**, and it is reconciled with the
1/2/4/8 masks the builder uses. **Up to four partials sound simultaneously**, and each gets

* its own **voice descriptor** `0x2942 + 0x47·p` (L27122-27126), and
* its own **chip voice**: `Voice_SetVelocity` loops `i = 0..3` over `scratch[0x0a+i]`, skips any
  entry ≥ 0x40, and runs the full 17-builder register burst per voice (L28755-28787).

**The HLE already renders this correctly** — Harpsichord's three partials appear as three voices
in the live capture. Nothing to change here.

### 4.2 The synthesised UNISON partial — this is the diagnosis's §6.3 "unexplained doubling"

`LABEL_032C0F` L35317-35341, MEASURED:

```
if patch[+0x11] bit2 == 0                      ; partial 1 NOT declared
   and  part_struct[+0x0a] bit15 set           ; (0x041372 + 0x11F*part)
   and  patch[+0x11] bit0 set                  ; partial 0 declared
   and  (patch[+0x5D] & 0x0F) <= 8:
        DE |= 0x8002                           ; declare partial 1 AND set the "cross" flag
```

`LABEL_02BA2C` then reads bits 14/15 of that same word (L27309-27313, L27351-27356) and, when set,
calls `LABEL_02B717` with **`a4 ≠ a5`** — voice slot 1 built from **partial 0's** `(fine,set)`,
VSEL and SET (`a4 = 0`) but with slot 1's own 0x25-byte sub-struct (`a5 = 1`). Result: a second
voice on the **same waveform** whose only difference is a pitch offset added by `LABEL_023A05`
from `desc[+0x27][+0x21]`.

This is exactly what the diagnosis observed: E.Piano 1 and Modern E.P.1 (both `+0x11 = 0x01`)
emit **two** voices with the same `+0x040` and `+0x400` differing by 20 and 24 units, and the
patches that do it are precisely those with `part_struct[+0x0a] = 0xC004` (bit 15 set) while
`0x0004` patches do not. **The `pb0a` bit-15 flag the diagnosis flagged is the gate, confirmed.**

**MEASURED census: 235 of the 258 one-partial patches satisfy the static half of the condition**
(`+0x11` bit2 clear, bit0 set, `patch[+0x5D]&0x0F ≤ 8`), so the runtime flag `part_struct[+0x0a]
bit15` is what actually selects them — its source is **not traced** (§9.2).

Consequence for the HLE: none directly — but today the unison twin is rendered *bit-identically*
to its parent (same chunk, same level, pitch from `true_note`), so it contributes nothing but
+6 dB. Fixing §7.2 turns it into the chorus/unison it is.

---

## 5. MECHANISM 3 — TRANSPOSE, DETUNE, and what `+0x400` really is

### 5.1 The complete pitch chain (MEASURED, `LABEL_023584` L15504 → `LABEL_023A05` L15996 → `LABEL_023A4A` L16025)

```
   IZ  = ((desc[+0x05] << 8) & 0x7F00) + 0x80              ; note<<8 + 0x80
   IZ += u16(0x041349)                                     ; MASTER TUNE
   IZ += sext(part_struct[+0x16]) << 8                     ; part TRANSPOSE  (semitones)
   IZ += sext(part_struct[+0x6d]) << 8                     ; part OCTAVE
   IZ += LABEL_02294E(part, patch_record[+0x29])           ; per-PATCH tune  (header byte +0x29)
   IZ += <scale-tuning / stretch term>                     ; LABEL_028D42 / 0x0FCE4 / 0x0FDE4 / 0x011B68
   desc[+0x08] = LABEL_022B02(IZ)                          ; the ABSOLUTE pitch (a separate reg path)

   L = desc[+0x17][+0x06] & 0x07                           ; partial KEY-FOLLOW mode
   if SETp[0] bit1 == 0:
        if L == 7:  IZ  = SETp[+0x0c]                      ; fixed pitch, no key follow
        else:       IZ -= (SETp[+0x0b] << 8) + 0x80        ; minus the SET's ROOT KEY
                    if L != 0: IZ >>= L                    ; partial key-follow scaling
                    IZ += u16(SETp[+0x0c])                 ; plus the SET's BASE PITCH
   else:  same with the constant 0x4280 in place of root/basepitch

   IZ += sext(desc[+0x17][+0x04]) << 8                     ; *** PARTIAL COARSE TRANSPOSE ***
   IZ += sext(desc[+0x27][+0x20]) << 8                     ; per-slot coarse offset
   desc[+0x06] = L==0 ? fold(IZ, SETp[+9], SETp[+0x0a])    ; LABEL_0229EC: ±0x0C00 octave FOLD
                      : clamp(IZ, SETp[+9], SETp[+0x0a])   ; LABEL_02299D
   key  = (desc[+0x06] >> 8) & 0x7F                        ; LABEL_022A32 L14289

   ; ---- LABEL_023A05: the +0x400 word
   DE  = desc[+0x06] + (0x293E)                            ; + the partial record's WORD B
   DE += sext(desc[+0x17][+0x05]) * 2                      ; *** PARTIAL FINE TRANSPOSE, x2 ***
   DE += sext(desc[+0x27][+0x21])                          ; *** UNISON / SLOT DETUNE ***
   DE += u16(part_struct[+0x14])                           ; part fine tune
   desc[+0x0a] = DE
   ; ---- LABEL_023A4A: ship it
   DE += u16(0x041347)                                     ; global tune / bend
   DE ±= u16(part_struct[+0x1d])  if desc[+0x27][+0x18] bit4   ; vibrato/bend depth
   DE += u16(0x04135A)            if desc[+0x01] bit10
   scratch[0x0451DA] = LABEL_022B02(DE)      ->  chip +0x400
```

`(0x293E)` is set by whichever record builder ran (`LABEL_022A3F`…`LABEL_022AE7`, L14295-14361):
**stride-6 → `record[+0x04..05]` (word B); stride-4 → 0.**

### 5.2 So `+0x400` is an ABSOLUTE log-pitch register

`+0x400 = (effective note << 8) + 0x80 + wordB(chunk) + 2·fine + detune + tunings`, in **1/256
semitone** units (0x100 per semitone, **0xC00 per octave**). `wordB` is the ROM's per-recording
tuning trim.

**PREDICT-THEN-CHECK — computed entirely from ROM bytes, then compared with the live capture of
`kn5000-variant-diagnosis.md §3` (which this pass never re-ran):**

| sound | note | `+0x040` pred/meas | `+0x400` pred/meas | |
|---|---|---|---|---|
| Piano p0 | C3/C4/C5 | 7004/7007/700A — all exact | **28E8 / 34C1 / 41AD** — all exact | ✓ |
| Piano p1 | C3/C4/C5 | 7014/7017/701A — all exact | — | ✓ |
| Piano 1 Octave p0 | C3/C4/C5 | 7007/7019/701C — all exact | **34C9 / 392C / 46BB** — all exact | ✓ |
| Piano 1 Octave p1 | C3/C4/C5 | 7004/7007/7019 — all exact | 28E8 / 34C1 / 3924 — all exact | ✓ |
| Honky-Tonk p0 | C4 | 7007 | **34B5** exact (fine −6 ⇒ −12) | ✓ |
| Honky-Tonk p1 | C4 | 7007 | pred 34CD, **meas 34D9** | **MISS, §8** |
| Electric Grand p0/p1 | C4 | 200F / 200F | **3BC6 / 3BC8** exact (fine +1 ⇒ +2) | ✓ |
| Harpsichord p0/p1/p2 | C4 | 1065 / 1076 / 40A3 exact | 3C80 / 3C80 / **3508** exact (coarse −12 + fold) | ✓ |

**`+0x040`: 19/19. `+0x400`: 15/16.** The chain that produces both — including the octave fold,
the key-follow shift, and the ×2 on the fine transpose — is therefore verified end-to-end.

The one miss is Honky-Tonk partial 1, `+12` units short: its `part_struct[+0x0a]` is `0xC004`
(bit 15 set) so it also receives the slot-detune term `desc[+0x27][+0x21]`; the byte that fills
`desc[+0x27][+0x20/+0x21]` is **not traced** (§9.2). The HLE does not need it — the value arrives
in `+0x400`.

### 5.3 Why the HLE loses all of it

`kn5000_tonegen.cpp::update_pitch()` L557-579 uses `true_note` (the key-bed/MIDI note) whenever it
is known, and only falls back to `regs[8]` for uncorrelated voices. So:

* **Piano 1 Octave** — partial 0 correctly selects chunk `0x019` (a zone an octave up) *and*
  `+0x400 = 0x392C`, but the HLE resamples chunk 25 to the played C4 → no octave. MEASURED by the
  diagnosis: C5/C4 partial ratio 0.146 vs plain Piano's 0.343, i.e. *lower*.
* **Honky-Tonk / Electric Grand / every unison layer** — two voices, same chunk, `+0x400`
  differing by 12…36 units → today two *bit-identical* voices, no beating.
* **273 of 629 patches** carry a transpose that is dropped.

---

## 6. MECHANISM 4 — PATCH-LEVEL TIMBRE: which field reaches which register

### 6.1 Builder map (MEASURED, from the scratch addresses of §2)

| chip reg | scratch | builder | what it is |
|---|---|---|---|
| `+0x040` | `0451CE` | `LABEL_023849` L15805 → `LABEL_022A3F..AE7` L14295 | **wave select** (decoded, shipped) |
| `+0x080` | `0451D0` | `LABEL_0232C7` L15195 / `LABEL_02331C` L15230 | initial amplitude, log-domain |
| `+0x0C0` | `0451D2` | `LABEL_0253FE` L18655 (`LABEL_025499` L18736 in the short chain) | per-patch level/brightness scalar |
| `+0x100` `+0x140` | `0451D4/D6` | `LABEL_024300` L16962, dispatch on `blk[+0x0F]&7` | **LFO** (rate / depth / delay / waveform) |
| `+0x400` | `0451DA` | `LABEL_023A05` L15996 → `LABEL_023A4A` L16025 | **pitch** (§5) |
| `+0x500` `+0x8C0` | `0451E2/EA` | `LABEL_02492D` L17603 / `LABEL_0249BF` L17662 | (not decoded) |
| `+0x800` | `0451E4` | `LABEL_025589` L18856 | **level** (velocity- and key-scaled) |
| `+0x9C0` `+0xA00` `+0xA40` | `0451F2/F4/F6` | `LABEL_0248D5` L17566 | **4-stage envelope** rates+levels |

### 6.2 `+0x0C0` — and the one field that separates Piano from Bright Piano

`LABEL_0253FE` (L18655-18696), MEASURED:

```
DE = part_struct[+0x0f]                              ; the PART's expression/level
if DE != 0:
     DE += patch_record[+0x5C] - 0x40                ; *** PATCH HEADER BYTE +0x5C ***
     DE += sext(part_struct[+0x66])
     clamp 0..0x7F ;  DE <<= 8
DE |= part_struct[+0x12]        (or 0x7F in global modes 5/6)
scratch[0x0451D2] = DE     ->  chip +0x0C0
```

**PREDICT-THEN-CHECK.** ROM bytes: `patch[+0x5C]` = **0x5A** (Piano), **0x40** (Bright), **0x40**
(Mellow). Predicted `+0x0C0` high byte: Piano = part-level **+26**, Bright = part-level **+0**,
Mellow = **identical to Bright**. Diagnosis MEASURED: `7400 / 5A00 / 5A00` — Piano is exactly
`0x74 − 0x5A = 26` above the other two, and Bright ≡ Mellow. **3/3.**

`+0x5C` is non-neutral in **208 of 629** patches (values 0x00…0x7F, 421 patches at the neutral
0x40). It is the ROM's own per-patch "level/brightness" parameter, and it is *the only* traced
field that distinguishes Piano from Bright Piano outside the envelope.

### 6.3 `+0x800` — level (the register the HLE already reads)

`LABEL_025589` L18856-18893, MEASURED:

```
IZ = <accumulated log level: part volume, patch level, key scaling>
if blk[+0x2E] != 0:                                   ; *** VELOCITY SENSITIVITY of level ***
     IZ += LABEL_022B2A( sext(blk[+0x2E]), velocity, shift=4 )
     ; LABEL_022B2A L14394:  sext(VELCURVE[velocity]) * sensitivity >> 4
     ;   VELCURVE @0x00FF64 (128 signed bytes, 0xC0 = -64 at vel 0 … 0x00 at vel 127)
     ;   a NEGATIVE sensitivity first remaps velocity through 0x00FEE4 (127-v)
clamp 0..0xFF
scratch[0x0451E4] = (IZ << 8) | TBL_0x011963[ blk[+0x28] ]      ->  chip +0x800
```

MEASURED `blk[+0x2E]`: Piano `0x0F`, Bright/Mellow `0x0C`. At velocity 100 the traced term alone
predicts Piano **6 units louder** in the log-attenuation domain; the diagnosis MEASURED `0xD1` vs
`0xDA` = 9 units. **Partial hit: 6 of 9 accounted for**; the residual is another term in the same
accumulator (`blk[+0x1D]` = `0xFB` vs `0x00` — a signed level key-scale — is the prime candidate,
not traced). Reported as an incomplete trace, not a completed one.

This register is already consumed by the HLE, and it is why Piano and Bright Piano *do* differ
today — by exactly the +5.38 dB / ×1.857 gain the diagnosis measured (9 attenuation units at the
device's `K = 10` gives ×2^0.9 = ×1.866).

### 6.4 `+0x9C0 / +0xA00 / +0xA40` — the amplitude ENVELOPE

`LABEL_0248D5` L17566-17565ff, MEASURED: the builder reads `desc[+0x17]` (the 0x51 partial block)
and uses **`+0x3D, +0x40, +0x42, +0x44, +0x49, +0x4A, +0x4B`**, each pair
`(blk[+0x3D] + blk[+0x40|+0x42|+0x44])` clamped to `[0xFFCE, 0x0032]` and mapped through
`LABEL_022B68` (table `0x0119C8`) into a rate nibble, with the levels velocity-scaled by
`LABEL_022BB8(blk[+0x49], blk[+0x4A|+0x4B], velocity)`. Two rates are packed per register:

```
+0x9C0 = (level0 << 8) | rate(blk[+0x3D] + blk[+0x40])
+0xA00 = (level1 << 8) | rate(blk[+0x3D] + blk[+0x42])
+0xA40 = (level2 << 8) | rate(blk[+0x3D] + blk[+0x44])
```

ROM bytes for the three pianos (identical in both partials):

| | `+0x2E` | `+0x3C` | `+0x3D` | `+0x3E` | `+0x40` | `+0x41` | `+0x42` | `+0x43` | `+0x4B` |
|---|---|---|---|---|---|---|---|---|---|
| Piano | 0F | 0A | **D8** | 00 | **28** | 50 | **14** | 58 | F1 |
| Bright Piano | 0C | 0A | **D8** | 28 | **28** | 50 | **14** | 58 | F1 |
| Mellow Piano | 0C | 00 | **F6** | 0A | **0A** | 5A | **00** | 5A | 00 |

which is exactly why the live capture has `+0xA00 = 36E8 / 36E8 / 36F6` and
`+0xA40 = 26B0 / 26B0 / 36F6`: **Piano and Bright Piano share an envelope; Mellow Piano has a
different one.** These are the *only* registers (with `+0x080` and `+0x100`) that separate Bright
from Mellow at all.

### 6.5 `+0x100 / +0x140` — the LFO

`LABEL_024300` L16962 dispatches on **`blk[+0x0F] & 0x07`** through a 6-entry jump table at
`0x0000F6B3`; mode 0 (`LABEL_022DA1` L14697) writes the "no LFO" constants `0x017F` / `0x7F7F`.
The active branches (`LABEL_02413E / 0241A0 / 024205 / 024250 / 0242A1`) build
`desc[+0x42] = (…<<13) | (…<<10) | … | 0x80` and `desc[+0x44]`, consuming **`blk[+0x36]`**
(`LABEL_024102`, `LABEL_024444`) and **`blk[+0x37]`, `blk[+0x3C]`, `blk[+0x4D]`, `blk[+0x50]`**
(`LABEL_023FBD`, `LABEL_02403D`).

ROM bytes: `blk[+0x36]` = **41 / 61 / 61** and `blk[+0x37]` = **20 / 17 / 11** for
Piano / Bright / Mellow — matching the measured `+0x140 = 6FDA / 5BDA / 5BDA` (Piano differs) and
`+0x100 = 244E / 2461 / 2445` (all three differ). The exact packing of each branch is **not**
decoded here (§9.4); which byte lands in which field is.

### 6.6 `+0x080` — initial amplitude

`LABEL_0232C7` L15195, MEASURED:
```
BC = <input> + part_struct[+0x0c] + part_struct[+0x10] + desc[+0x33]
clamp 0..0xFF ; BC = 2 * u16[0x010764 + 2*BC]                        ; log->linear table
WA = partial_record[+0x02] bit7 ? ((partial_record[+0x02] & 0x70) << 8)
                                : u16[0x0000FBE4 + 2*(desc[+0x06] >> 8)]   ; key-dependent
scratch[0x0451D0] = 0x8000 | BC | WA        ->  chip +0x080
```

---

## 7. What the HLE must change — register-only, ranked

### 7.1 `kn5000.cpp` — key-bed velocity polarity  (**biggest correctness win, smallest patch**)

Replace the MIDI velocity in the FIFO high byte with `KEYBED_TIME[vel]` (§3.3) in **both**
`keybed_scan()` (L409) and `kbd_midi_rx()` (L234); `KEYBED_VELOCITY = 100` becomes
`KEYBED_TIME[100] = 42`. Cite `ToneGen_Read_Voice_Data` L51500 / `ToneGen_Calc_Pitch` L51556 and
the two ROM tables in the comment. Effects: all 24 velocity-split patches pick the correct sample
layer, the velocity→level curve stops running backwards, and `+0x800` responds the right way round.
This is a **key-bed** fix; the tone-gen device is untouched.

### 7.2 `kn5000_tonegen.cpp::update_pitch()` — honour `+0x400`

`+0x400` (`regs[8]`) is a log-pitch word at **0x100 units per semitone / 0xC00 per octave**
(§5, verified 15/16). It is the *only* register carrying transpose, detune and unison offsets.
Three tiers, each strictly better than today, each register-only:

* **Tier A (no new state).** Within a note-on correlation group, for the sub-set of voices that
  resolved to the **same chunk**, compute `ref = mean(regs[8])` and use
  `freq_i = f(true_note) · 2^((regs[8]_i − ref) / 3072.0)`.
  The group's centre pitch is unchanged (so nothing can regress), and the *relative* spread
  becomes exact. This alone restores Honky-Tonk's beating (Δ=36 ⇒ ±0.4 % ⇒ ~2 Hz at C4),
  Electric Grand's Δ=2 detune, and every synthesised unison layer (§4.2) — i.e. every case where
  the HLE currently renders two bit-identical voices.
* **Tier B (one small per-chunk table).** Learn `wordB(chunk) = regs[8] − 256·true_note − 0x80`
  from key-bed-correlated voices (median over observations), then drive **every** voice from the
  register: `freq = 440·2^(((regs[8] − 0x80 − wordB(chunk))/256 − 69)/12)`. This additionally fixes
  the *coarse* transposes that change chunk (Piano 1 Octave, Piano 2 Octave, Harpsichord's third
  partial, 273 patches in total) and replaces the crude `0x3524` anchor in the demo/rhythm
  fallback (L577) with the correct one.
* **Tier C (the real fix — next investigation).** Decode the **per-chunk ROOT PITCH** in the wave
  ROM's parameter records. It is *inside* the chip boundary (the LSI reads those records), and with
  it `freq = f_root(chunk)·2^((regs[8] − R(chunk))/3072)` needs neither `true_note` nor
  `detect_period` — it would retire `assign_chord_notes()` and the ±7-cent residual at once.
  `kn5000-datamap-applied.md §7 gap 4` already names this as the open item; §5.2 here shows the
  register that consumes it.

**Do not** replace the anchor with a single global constant: the per-chunk trim `wordB` spans
±118 units (±0.46 semitone) inside one piano multisample (MEASURED: −1944 / −1983 / −1747 for
zones 4 / 7 / 10 of SET #1), so a global anchor would regress absolute pitch from ±7 cents to
±46 cents.

### 7.3 Multi-partial — no change

The firmware already emits one independent chip voice per present partial (§4.1) and the device
renders all 64. What looks like "layers collapse" is a *symptom* of 7.2, not a missing mechanism.

### 7.4 Timbre — implement the ENVELOPE and the LFO

Bright Piano and Mellow Piano are **identical in the sample path by design** (same `(fine,set)`,
same VSEL, same SETs, same `+0x040`, same `+0x400`, same `+0x0C0`). On the real instrument they can
only differ through `+0x080`, `+0x100/+0x140` and `+0x9C0/+0xA00/+0xA40` — the initial amplitude,
the LFO, and the 4-stage envelope (§6.4-6.6, and the ROM bytes that produce them). So:

* **`+0x9C0 / +0xA00 / +0xA40` — a 4-stage amplitude envelope**, `(level << 8) | rate` per stage
  (§6.4). Replacing the current single `env_level` magnitude (`regs[0]` low bits) with a real
  segment-stepping EG driven by these three registers is the concrete next step, and it is the
  register contract that makes Piano ≠ Bright ≠ Mellow.
* **`+0x100 / +0x140` — the LFO** (rate/depth/delay/waveform, selected by `blk[+0x0F]&7`).
  Modulating pitch and/or amplitude from these two words is what separates Tremolo E.Piano,
  Wurly E.Piano and the vibrato'd strings/brass from their static twins.
* **`+0x0C0`** — a per-patch level/brightness scalar whose *value* is now derived (§6.2). Whether
  the LSI applies it as a filter cutoff or as a second gain term is **not decidable from the
  firmware** — do not guess; it is not what separates Bright from Mellow in any case.

---

## 8. PREDICT-THEN-CHECK summary, misses included

Every prediction below was computed from ROM bytes / disassembly in this pass and compared with the
independently-captured live register stream of `kn5000-variant-diagnosis.md`, which was not re-run.

| what | result |
|---|---|
| `+0x040` from the full static chain, 8 sounds × 1-3 partials × 1-3 keys | **19 / 19 exact** |
| `+0x400` from the full static chain (fold, key-follow, wordB, coarse, fine×2) | **15 / 16 exact** |
| `+0x0C0` from `patch[+0x5C]` (Piano−Bright = +26, Bright ≡ Mellow) | **3 / 3 exact** |
| velocity-zone crossings under the *broken* bridge, 3 instruments | **12 / 12** |
| the `+0x11` 2-bit present map vs the 1/2/4/8 builder masks | **PROVEN-BY-CONSTRUCTION** |
| the `pb0a` bit-15 doubling flagged by the diagnosis | **explained** (`LABEL_032C0F` `DE |= 0x8002`) |
| `+0x800` Piano-vs-Bright difference from `blk[+0x2E]` | **partial: 6 of 9 units** — reported |

**MISS 1 — Honky-Tonk partial 1**, `+0x400` predicted `34CD`, measured `34D9`. The extra `+12`
comes from `desc[+0x27][+0x21]` (the slot detune of §5.1); the byte that fills it is not traced.
Same residual the diagnosis reported; now localised to one struct field.

**MISS 2 — `+0x800`**, the traced velocity-sensitivity term accounts for 6 of the 9 measured
attenuation units between Piano and Bright Piano. The other terms of the same accumulator were not
traced (`blk[+0x1D]` = `FB`/`00` is the likely remainder). Reported, not asserted.

**Corrected from the DIAGNOSE pass:** its **MISS #1** ("the velocity-zone order is inverted; the
compared value is a level that falls with velocity") is **withdrawn**. The order is `q=0` for the
softest, exactly as `kn5000-firmware-sample-tables.md §5` states; what is inverted is the key-bed
bridge (§3.3). The diagnosis's own measurements are reproduced exactly by that explanation (§3.4).

**Corrected from `kn5000-firmware-sample-tables.md §10 gap 1:** `desc+0x17` for a 0x51-block voice
is the partial block of slot `a4` (`LABEL_02B717` L27058), and the per-instrument coarse transpose
is `blk[+0x04]` — so the six non-zero key shifts of that note's §6 are now *predicted*, not just
measured (see the Piano 1 Octave / Harpsichord rows above).

---

## 9. Honest gaps

1. **What the LSI does with `+0x080 / +0x0C0 / +0x100 / +0x140 / +0x9C0 / +0xA00 / +0xA40`.** The
   firmware side is decoded (what value, from which byte, through which table). The *response* of
   the undumped IC303 is not, and cannot be settled from the emulator. The register semantics named
   in §6 ("envelope", "LFO") follow from the *inputs* (rates, levels, key-follow, delay), which is
   evidence about the firmware's intent, not a datasheet.
2. **`desc[+0x27][+0x20] / [+0x21]`** (the per-slot coarse/fine detune) and **`part_struct[+0x0a]`
   bit 15** (the unison gate) are read but their writers are not traced. Both are visible on the
   bus in `+0x400`, so the HLE does not need them.
3. **`patch[+0x5B]`** (Piano 0x00 vs Bright/Mellow 0x40) has no traced consumer yet.
4. **The five active LFO branches** of `LABEL_024300` are named but their bit packing into
   `desc[+0x42]/[+0x44]` is not fully decoded.
5. **`+0x500`, `+0x8C0`, `+0x180`, `+0x440`, `+0x480`, `+0x4C0`, `+0x840`, `+0x880`, `+0x900`,
   `+0x940`, `+0x980`** — builders are located (§2 makes that mechanical) but not decoded.
6. **The undumped bank is unchanged and dominates.** 312 of 629 patches are wholly on IC304/305/306
   (`kn5000-variant-diagnosis.md §5`), including Rock Piano and every E.Piano. Nothing in this note
   changes that; the mechanisms above make the *variants that share a dumped bank* differentiate.

---

## 10. Reproduction

```bash
# 1. sub-program ROM: file offset = address - 0xEF00
python3 - <<'EOF'
d=open('roms/kn5000/kn5000_subprogram_v142.rom','rb').read(); B=0xEF00
T1=list(d[0x1F43E-B:0x1F43E-B+256])   # key-bed TIME -> strike strength (DECREASING)
T2=list(d[0x1F53E-B:0x1F53E-B+256])   # strength -> velocity 1..127 (INCREASING)
G=d[0x1F420-B+3*6]; O=d[0x1F421-B+3*6]              # TOUCH mode 6 = power-on default
fw=lambda r:(lambda n:T2[max(0,min(255,(abs(n)//0x80)*(1 if n>=0 else -1)+O))])((T1[r]-0x4D)*G)
EOF

# 2. Table-Data ROM: interleave IC3/IC1 exactly as kn5000.cpp:1131-1133, region off = S-0x20000
#    walk: patch record -> (fine,set) -> A1 -> VSEL -> velocity zone q -> A2 -> SET desc
#          -> LABEL_023584 pitch chain -> ptrC[key] -> ptrA[4+slot] -> ptrB + stride*E
#          -> +0x040 = u16[rec] ,  +0x400 = fold(...) + wordB + 2*blk[+5]
#    (scratchpad: lib.py = image + address model, pitch.py = the §5.1 chain)

# 3. the disassembly, all line numbers above:
#    kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm
```

Key entry points, for the next pass: `Voice_SetVelocity` L28707, `LABEL_02BA2C` L27289,
`LABEL_02B717` L27004, `LABEL_023584` L15504, `LABEL_023A05` L15996, `LABEL_0248D5` L17566,
`LABEL_024300` L16962, `LABEL_0253FE` L18655, `LABEL_025589` L18856,
`ToneGen_WriteVoiceParams` L29565, `ToneGen_Calc_Pitch` L51556.
