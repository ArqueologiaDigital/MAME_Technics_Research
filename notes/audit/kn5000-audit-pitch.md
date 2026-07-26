# KN5000 IC303 HLE — FULL AUDIT of the PITCH PATH

Audit pass 2026-07-26. Dimension: **pitch only** (`+0x400`, the transposes, the octave fold,
key-follow, the per-zone fine-tunes, portamento/bend, multisample zone boundaries).

Sources, all cited inline:
* SUB-CPU disasm `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`
  (label names ARE the code address; file offset = address − 0xEF00).
* HLE `kn7000_mame/src/mame/matsushita/kn5000_tonegen.{cpp,h}`.
* Firmware SET descriptors `notes/data/kn5000-multisample-sets.tsv` (487 SETs, 2133 zones)
  and partial blocks `notes/data/kn5000-patch-partials.tsv` (1046 blocks) + the Table-Data ROM.
* IC307 dump `roms/kn5000/kn5000_waveform_rom.ic307` (the ONE hardware-rooted wave dump).
* **NEW live capture, this pass** — `scratchpad/pitch/tap1.log`, a watchpoint on the sub-CPU's
  `0x100000..0x100003` over a held keybed C4 on the built KN5000 (MEASURED, 2026-07-26).
* **NEW derived table, this pass** — `notes/data/kn5000-pitch-trim-table.tsv` (1444 rows).

Evidence labels: **MEASURED** (read from ROM/asm/live bus), **INFERRED**, **SPECULATIVE**.

---

## 1. WHAT THE FIRMWARE DOES

### 1.1 `+0x400` is an ABSOLUTE log pitch, 0x100 units/semitone, clamped to [0, 0x7FFF]

`ToneGen_WriteVoiceParams` (asm L29565, PC `0x02D10E`) uploads the 44-byte staging block at
`0x0451CC`; its field `+0x0e` (= address `0x0451DA`) goes to register `voice+0x400`
(asm L29663-29671). MEASURED.

The clamp `LABEL_022B02` (asm L14363-14372, PC `0x022B02`) is decisive about the format:

```
LABEL_022B02:  LD BC,WA ; BIT 0fh,BC ; JR Z,pass        ; bit15 clear -> pass through
               CP WA,0c000h ; JR ULE,-> HL = 7FFFh      ; wrapped high  -> saturate 0x7FFF
               LD WA,0     ;          -> HL = 0000h     ; wrapped low   -> saturate 0
```

so the legal range is 0…0x7FFF = 128 semitones at 0x100/semitone, 0xC00 per octave. MEASURED.

### 1.2 The complete chain (three routines)

**`LABEL_023584`** (asm L15504, PC `0x023584`) — key → zone-selectable log pitch:

```
IZ  = ((slot[+0x05] << 8) & 0x7F00) + 0x80        ; L15517-15520  key<<8 + 0x80
IZ += u16(0x041349)                               ; L15521  MASTER TRANSPOSE, whole semitones
                                                  ;         (set by LABEL_028B30 L23714: sext(byte)<<8)
IZ += sext(part[+0x16])<<8                        ; L15525-15528  part transpose
IZ += sext(part[+0x6d])<<8                        ; L15530-15533  part octave
IZ += LABEL_02294E(part, tone[+0x29])             ; L15544  per-patch key shift (table 0x011ACF)
IZ += <SCALE TUNING>                              ; L15551-15737: modes 0x40/0x41/0x42/0x80/other
                                                  ;   0x41/0x42 = per-key word tables 0x0FCE4/0x0FDE4
                                                  ;   0x80      = per-pitch-class byte x2 (LABEL_028C28)
                                                  ;   other     = 12-entry temperament table 0x011B68 x2
slot[+0x08] = LABEL_022B02(IZ)                    ; L15738-15741 absolute pitch (a different reg path)

L = partial_blk[+0x06] & 7                        ; L15744-15746  KEY-FOLLOW mode
if SET[0] bit1 == 0:                              ; L15749
     if L == 7: IZ  = SET[+0x0c]                  ; L15778-15781  FIXED PITCH (no key follow)
     else:      IZ -= (SET[+0x0b]<<8)+0x80        ; L15754-15761  minus the SET's root key
                if L: IZ >>= L                    ; L15763-15766  key-follow scaling 1/2^L
                IZ += u16(SET[+0x0c])             ; L15768-15771  plus the SET's base pitch
else:  same with the constant 0x4280 for both     ; L15786-15799
IZ += sext(partial_blk[+0x04])<<8                 ; L15800-15806  PARTIAL COARSE TRANSPOSE
IZ += sext(slot[+0x27][+0x20])<<8                 ; L15807-15813  slot coarse offset
slot[+0x06] = L==0 ? fold (LABEL_0229EC)          ; L15814-15827  OCTAVE FOLD  into [kmin,kmax]
                   : clamp(LABEL_02299D)          ; L15828-15840  CLAMP        into [kmin,kmax]
```

`LABEL_0229EC` (asm L14246-14281) folds by whole octaves (`±0x0C00`) until the value lies in
`[(SET[+0x09]<<8)+0x80 , (SET[+0x0a]<<8)+0x80]`; `LABEL_02299D` (L14204-14245) clamps to the same
bounds. MEASURED. The **same** `slot[+0x06]` then selects the sample: `LABEL_022A32` (L14289-14294)
does `key = (slot[+0x06]>>8)&0x7F` and indexes the SET's 128-byte key→zone map (called from
`LABEL_023849` L15805 at L15822-15824). So **wave selection and pitch share one value** — the fold
moves both together.

**`LABEL_023A05`** (asm L15996-16024, PC `0x023A05`) — the `+0x400` word:

```
DE  = slot[+0x06] + u16(0x293E)      ; L15997-15998  + the ZONE RECORD's own tuning trim
DE += sext(partial_blk[+0x05]) * 2   ; L15999-16003  PARTIAL FINE TRANSPOSE, x2 (1 unit=0.39 cent)
DE += sext(slot[+0x27][+0x21])       ; L16004-16008  UNISON / SLOT DETUNE
DE += u16(part[+0x14])               ; L16009-16011  part fine tune  <-- MIDI PITCH BEND lands here
slot[+0x0a] = DE
```

`0x293E` is loaded by whichever zone-record builder ran (`LABEL_022A3F` L14295 … `LABEL_022AE7`
L14353): **stride-15 → rec[+0x0d], stride-12 → rec[+0x0a], stride-6 → rec[+0x04],
strides 13/10/4 → 0.** All 487 SETs in the ROM are stride 4 (344) or stride 6 (143). MEASURED.

**`LABEL_023A4A`** (asm L16025-16055, PC `0x023A4A`) — ship it:

```
DE  = slot[+0x0a] + u16(0x041347)    ; L16026-16027  MASTER FINE TUNE
                                     ;   LABEL_028B23 L23707: (panel byte - 0x40)*2  => +-0.5 semitone
DE ±= u16(part[+0x1d]) if slot[+0x27][+0x18] bit4  ; L16028-16045  part DETUNE, sign from bit5
DE += u16(0x04135A)   if slot[+0x01] bit10         ; L16046-16048  BEND value
0x0451DA = LABEL_022B02(DE)          ; L16049-16054 -> chip +0x400
```

### 1.3 `+0x400` is REWRITTEN on SOUNDING voices — three distinct paths (MEASURED)

`LABEL_02D0BA` (asm L29539-29556) writes **only** `voice+0x400` from the staging block. Callers:

| path | asm | trigger |
|---|---|---|
| per-tick sweep of every keyed voice: `LABEL_023A4A` then `LABEL_02D0BA` | `LABEL_027AC4` L22673, sweep at L22690-22712 | runs whenever `0x041343` bit10 is set — the AUTO-BEND flag |
| auto-bend ramp stepper `LABEL_0271BC` | L21823-21850 | steps `0x04135A` from curve table `0x011C7C` (`value*2`) every tick |
| `LABEL_028D4C` — rewrite `+0x400` for all 64 voices via `LABEL_027F74` | L23938-23992 | called after a master-TUNE change (`LABEL_02A6DB` L25485-25495) and from the MIDI-CC handler (L25198) |

MIDI **pitch bend** is fully implemented: `MIDI_Status_PitchBend` (L38454-38470) → `Voice_PitchBend`
(L25376-25424), which writes the part struct at `+0x12/+0x14` — and `part[+0x14]` is exactly the
term `LABEL_023A05` L16009-16011 adds to `+0x400`. MEASURED.

There is **no** portamento register: `+0x100`/`+0x140` are built by `LABEL_024300` (L16962,
dispatch on `partial_blk[+0x0F]&7`) as an **LFO** rate/depth/delay/waveform pair — mode 0 writes
the "no LFO" constants `0x017F`/`0x7F7F` (`LABEL_022DA1` L14697). Portamento/legato, if realised
at all, can only be the sub-CPU ramping `+0x400` through the paths above. MEASURED (register
identity) / INFERRED (that this is how portamento is realised).

### 1.4 Live confirmation of the whole chain (MEASURED 2026-07-26, `scratchpad/pitch/tap1.log`)

Held keybed C4, default power-on Piano, watchpoint on `0x100000..0x100003`:

```
 v00 +0x040 = 0x7007   v00 +0x400 = 0x34C1      v01 +0x040 = 0x7017   v01 +0x400 = 0x34C1
 ... 3 s hold: NOT ONE register write ...
 release:  +0x840/+0x940/+0xA00/+0x800/+0x900/+0x9C0 burst, then +0x0C0 = 0x0000, +0x000 = 0x7E00
```

**PREDICT-THEN-CHECK — HIT.** Before running this I computed, from `kn5000-multisample-sets.tsv`
alone, that SET #1 zone "60-63 → class 7 entry 0x007" carries trim `0xF841 = −1983`, so
`+0x400 = (60<<8) + 0x80 − 1983 = 0x34C1`. The bus says `0x34C1`. Exact.

Two by-products worth recording (outside this dimension, both MEASURED):
* **`+0x400` is NOT rewritten during a plain held note.** The bend/tune paths of §1.3 are the only
  producers, so Gap 1 below is latent until the player uses bend / tune / a CC — which is precisely
  Felipe's USB-MIDI-controller scenario.
* **The firmware DOES write a `0x7E00` key-off on release** (`+0x000 = 0x7E00`, preceded by
  `+0x0C0 = 0x0000`). `kn5000_tonegen.cpp:230-231` asserts the opposite ("The sub-CPU never writes
  a 0x7E00 key-off … when a held key is released") and builds the group-9 release heuristic on that
  premise. The premise is false for keybed notes. Flagged for the release/envelope auditor.

### 1.5 The per-zone constant is DATA, not a mystery — and it is a function of the `+0x040` word

Define, per SET zone, the constant everything else is measured against:

```
C(zone) = (SET.basepitch − ((SET.root<<8)+0x80)) + trim(zone)
so, with no transposes:   +0x400 = (key<<8) + 0x80 + C
```

MEASURED over all 487 SETs / 2133 zones (`notes/data/kn5000-pitch-trim-table.tsv`, generated this
pass):

* 1444 distinct `+0x040` selectors. **1367 of them (94.7%) carry exactly ONE value of `C`.**
* Restricted to the 143 stride-6 SETs alone: **367 of 368 selectors carry one trim** — one
  exception, `+0x040 = 0x6028`, with two values exactly 3072 apart (one octave). This reproduces
  the claim in `kn5000_tonegen.h:180-187` independently.
* The 77 ambiguous selectors are recordings a *different SET* deliberately plays transposed. They
  carry 29.2% of the key-weighted zone mass; choosing the key-weighted modal `C` would still be
  wrong for 13.4% of key slots.

**PREDICT-THEN-CHECK — MISS, reported.** I predicted the ambiguity could be resolved from the ROM
by the page-local law of `kn5000-structural-validation.md` (`K = C + 0x80 − 3072·log2(period)` is
constant per 1 MB page, modulo an octave). The law itself holds well — fitting one circular-median
constant per page on the *unambiguous* selectors gives

```
class 7 (piano)  K_page=137.8   57 of  57 chunks within +-64 units (+-25 cents), max dev 39.0
class 4          K_page=123.9  167 of 175 within +-64                            median dev  9.7
class 6          K_page=129.1   42 of  48 within +-64                            median dev  5.6
class 5          K_page=126.7   58 of 102 within +-64  <- page 1 = drums/flutes, where
                                                          detect_period is least reliable
```

— **but it does not resolve the ambiguity**: of the 55 ambiguous selectors on the dumped pages only
**11** have exactly one candidate `C` within ±25 cents of their page constant; **28** have none
(23 of those 28 are on class 5) and 16 have no measurable period at all. So the ambiguity is **NOT**
resolvable this way. Report it, do not paper over it.

---

## 2. WHAT THE HLE DOES

`kn5000_tonegen.cpp:717-792` `update_pitch()`:

* `pitch_period_q16 == 0` (aperiodic recording) → `pitch_step = 0x10000`, native rate, **`+0x400`
  never consulted** (`:743-747`).
* `true_note >= 0` → `note_f = true_note + pitch_offset`, `freq = 440·2^((note_f−69)/12)`
  (`:752-758`). `true_note` is the MIDI note recovered by correlating the voice's key-on with the
  key-bed/USB-MIDI FIFO (`assign_chord_notes()` `:384-455`, 0.30 s window, chord pairing by
  `voice_pitch_index()` `:365-368`).
* else → `semis = (regs[8] − 0x3524)/256`, `freq = 261.63·2^(semis/12)` (`:766-773`).
* `step = freq · pitch_period_q16 / 48000` (`:785`) — the recording's *measured* fundamental
  (`detect_period()` `:1083-1178`) resampled onto the target frequency.

`pitch_offset` (the only thing `+0x400` contributes when `true_note >= 0`) is produced by
`resolve_note_group()` (`:584-713`), which
1. skips any voice with `!wave_real` (`:598`) — `wave_real` requires `bank == IC307_BANK` (`:1265`);
2. **learns** `trim = regs[8] − 256·true_note − 0x80` at runtime, but only from a key press whose
   partials all land within 0.5 semitone of each other *and* span ≥2 distinct chunks (`:612-653`),
   marking a chunk CONFLICTED if two observations differ by >128 units;
3. resolves each voice from its own chunk's learned trim (`:665-678`, rejected if the implied note
   is >25 semitones from the played note), then propagates within a chunk (`:683-699`), then
   mean-centres a flat press with nothing learned (`:703-709`).

`pitch_offset` is reset to 0 at every key-on (`:1338`) and is **only** recomputed inside
`assign_chord_notes()` — i.e. at key-on. A later `+0x400` write calls `update_pitch()` (`:261-262`)
but that recomputes the identical frequency.

Registers `+0x100`/`+0x140` are stored as `regs[4]`/`regs[5]` (`:195`) and never read.

---

## 3. THE DELTA — numbered gaps

### GAP 1 — Every mid-note pitch change is dropped: pitch bend, auto-bend, master-tune change, MIDI CC, portamento

**Wrong.** `update_pitch()` derives the frequency from `true_note + pitch_offset` (`:756`), and
`pitch_offset` is written only by `assign_chord_notes()` at key-on (`:1349`, `:437`, `:712`). A
`+0x400` rewrite on a sounding voice therefore produces **no pitch change at all**, even though the
device does re-enter `update_pitch()` for it (`:261-262`).

**Audible consequence.** The pitch-bend wheel of a USB-MIDI controller does nothing (the sub-CPU
parses it — `MIDI_Status_PitchBend` L38454 → `Voice_PitchBend` L25376 → `part[+0x14]` →
`LABEL_023A05` L16009 → `+0x400`). The panel BEND effect (`LABEL_0271BC` L21823, curve table
`0x011C7C`, re-shipped per tick by `LABEL_027AC4` L22690-22705) does nothing. Changing master TUNE
while notes ring does nothing (`LABEL_02A6DB` L25485 → `LABEL_028D4C` L23938). Any portamento/glide
does nothing.

**Firmware-derived fix (no table, no heuristic, zero risk to absolute pitch).** At the note-on gate
latch `v.pitch_ref = v.regs[8]`; in `data_w`'s group-4/bank-0 branch, while `key_on`, do
`v.pitch_offset += (int(v.regs[8]) − int(v.pitch_ref))/256.0; v.pitch_ref = v.regs[8];` then
`update_pitch()`. Both values are the same register on the same chunk, so the chunk's unknown trim
cancels **exactly** and the delta is the true bend in 1/256 semitone. This is a pure register
difference — nothing outside the chip boundary, nothing learned.

**Confidence: MEASURED** (both the firmware path and the HLE's inaction).

---

### GAP 2 — Voices with no key-bed correlation (rhythm, auto-accompaniment, demo, MIDI-driven parts on other channels) play at a nearly arbitrary pitch

**Wrong.** The fallback (`:766-773`) treats `regs[8]` as a global log pitch against the hard-coded
anchor `0x3524`. `0x3524` is the value captured for **MIDI 68 (G#4)** on the piano SET, but the code
maps it to **C4 (261.63 Hz)** — an 8-semitone error before anything else — and it ignores the
per-selector constant `C` entirely, which spans −8448…+5120 units (−33…+20 semitones).

**Quantified (MEASURED, from `kn5000-pitch-trim-table.tsv`).** Rendered note minus true note is
`60 + (C − 13476)/256` semitones. Key-weighted over all 2133 SET zones:

```
percentile   1%     5%     25%    50%    75%    95%    99%
error     −12.53  −0.62  +7.36  +7.36  +18.12 +24.16 +72.36   semitones
min −27.61   max +72.36   |error| <= 0.5 semitone for 0.4% of key slots
```

Even inside the single default piano multisample the error changes by 7.6 semitones between
adjacent zones (zone 60-63 → −0.4 semitone, zone 68-71 → −8.0 semitones).

**Audible consequence.** Everything the instrument plays by itself that has a measurable
fundamental — the auto-accompaniment bass and chords, the Feature Demo melody, sequencer playback —
is transposed by a per-zone-random amount, and steps by several semitones whenever the melody
crosses a sample-zone boundary. (Drums are unaffected: they are aperiodic, so `:743-747` plays them
at native rate.)

**Firmware-derived fix.** Replace the anchor with the decoded constant:
`note = (regs[8] − 0x80 − C(regs[1]))/256`, `C` from the baked table of §1.5. For the 94.7% of
selectors with a unique `C` this is **exact**; for the rest, keep today's behaviour and flag.

**Confidence: MEASURED.**

---

### GAP 3 — All partial/part/master transposes are discarded for 63% of the wave-selection space, because `resolve_note_group()` refuses any voice not on IC307

**Wrong.** `:598` skips a voice unless `wave_real`, and `:1265` sets `wave_real` only for
`bank == IC307_BANK`. `+0x040` classes 0-3 decode to bank 0 (the undumped socket) —
**1353 of the 2133 SET zone references (63%)**. Those voices keep `pitch_offset = 0` forever, so
their coarse/fine transposes, unison detune, master transpose and scale tuning are all dropped.

The stated justification ("on an undumped socket the recording played has no connection to the
pitch the register asks for", `:1261-1264`) does not apply to the *offset*: the constant `C` comes
from the **firmware's** SET descriptors, not from the wave ROM, so it is known for banks 0/2/3 too.
Only the timbre is substituted; the note the firmware asked for is fully determined.

**Audible consequence.** 273 of 629 patches carry a transpose (`kn5000-variant-model.md` §5.3); the
majority of them live on the undumped bank, so today they render with every transposition removed —
octave layers collapse onto the played note, detuned unisons render bit-identically (no beating).

**Firmware-derived fix.** Gate the pitch resolution on "the `+0x040` word has a known `C`", not on
"the chunk is on IC307".

**Confidence: MEASURED** (the gate and the class→bank map; the 63% is a zone count).

---

### GAP 4 — The 110 partials with KEY-FOLLOW ≠ 0 (including the 2 FIXED-PITCH ones) track the key 1:1 instead of at their programmed ratio

**Wrong.** `LABEL_023584` L15744-15781 scales the key offset by `1/2^L`, `L = partial_blk[+0x06]&7`,
and treats `L == 7` as a *fixed* pitch (`IZ = SET[+0x0c]`, no key follow at all). The HLE anchors on
the played note, i.e. it always renders `L = 0`.

**Census (MEASURED this pass, read directly from the Table-Data ROM at each block's `region_off`,
`notes/data/kn5000-patch-partials.tsv` + the interleaved IC3/IC1 image):**

```
blk[+0x06]&7 :  0 -> 936    1 -> 27   2 -> 22   3 -> 50   4 -> 6   5 -> 1   6 -> 2   7 -> 2
                (110 of 1046 partial blocks = 10.5% are NOT full key-follow)
blk[+0x04] (coarse) nonzero: 167 of 1046      blk[+0x05] (fine) nonzero: 364 of 1046
```

(The 167/364 figures independently reproduce `kn5000-variant-model.md` §5.1's census — 1046−879=167
and 364 — which is a useful cross-check that the block layout is read correctly.)

**Audible consequence.** A key-follow-3 partial should move 1/8 semitone per key; the HLE moves it a
full semitone, so two octaves above the SET root it is **21 semitones sharp**. A fixed-pitch partial
(`L = 7`) should stay on one note across the whole keyboard and instead follows the key.

**Firmware-derived fix.** The same one as Gaps 2/3 — `+0x400` already contains the key-follow
result, so decoding `note` from `(regs[8], regs[1])` reproduces every `L` exactly. Algebraically:
with `V = SET.basepitch + ((key<<8)+0x80+T − pivot)>>L + coarse·256 + trim`, the decode
`(V − 0x80 − C)/256` collapses to exactly the firmware's scaled pitch, and for `L = 7` to exactly
`SET.root` for every key. PROVEN-BY-CONSTRUCTION.

**Confidence: MEASURED (census + firmware) / INFERRED (the audible size, which depends on how far
the key is from the SET root).**

---

### GAP 5 — `voice_pitch_index()` is NOT monotonic with pitch in 163 of 487 SETs, so chord notes get paired to the wrong voices

**Wrong.** `:365-368` builds `(regs[1] & 0x0F)·0x100000 + regs[8]`, and `:358-364` claims this "makes
the combined value MONOTONIC with musical pitch across zone boundaries". Two independent reasons it
is not:

* `regs[1]`'s entry field is **12 bits**, not 4 (`decode_wave_select()` `:991`
  `r.entry = w & 0x0FFF`). `& 0x0F` aliases entry 0x017 onto 0x007, 0x010 onto 0x000, etc.
* `regs[8]` alone is **not** monotonic in key, because `C` changes at every zone boundary — e.g. in
  the default piano SET, key 63 → `0x37C1` but key 64 → `0x35EC`, a *decrease*.

**Quantified (MEASURED).** Walking every key 0…127 of every SET and evaluating the expression:
**non-monotonic in 163 of 487 SETs (33%)**. First failures: SET 8 at key 63→64
(`0x00F03EC6 → 0x000038F7`), SET 9/11/12/13/14/15/16 at key 35→36, SET 10 at 43→44, SET 19 at
107→108.

**Audible consequence.** `assign_chord_notes()` `:432-438` pairs the *rank* of a voice's pitch index
with the *rank* of the input note, so on those SETs a chord that straddles the offending boundary
has two of its notes swapped between voices — the chord sounds with the wrong intervals. (The
verification quoted in the code, C4/E4/G4 on the default piano, happens to sit inside a monotonic
SET, which is why it passed.)

**Firmware-derived fix.** Adopting the `C`-table decode retires `voice_pitch_index()` and
`assign_chord_notes()` from the pitch path altogether — the note comes from the registers, so no
pairing is needed. If the correlation machinery is kept for other purposes, the index must use the
full 12-bit entry *and* the per-selector `C`: `index = 256·note = regs[8] − 0x80 − C(regs[1])`.

**Confidence: MEASURED.**

---

### GAP 6 — The per-chunk trim is LEARNED at runtime by a heuristic, when it is a decoded constant in the firmware's own tables

**Wrong (methodologically and in effect).** `:612-653` infers `trim` from live play: it requires a
key press whose partials are all within 0.5 semitone *and* span two distinct chunks, and it marks a
chunk CONFLICTED (never usable again) if two observations differ by more than 128 units. Direct
consequences:

* **Order-dependent, non-deterministic output.** Whether "Piano 1 Octave" renders its octave at all
  depends on whether a *previous* press happened to teach chunks 0x019 and 0x007. The same patch on
  the same key can render differently in two sessions.
* **Poisonable.** A patch that transposes *every* partial equally passes the flatness test, so the
  first observation of a chunk can be learned with the transpose baked in. The guard only *detects*
  the contradiction later and then disables the chunk (`st = 2`) — it never corrects it. Until then
  the wrong trim is applied as real pitch, accepted up to ±25 semitones (`:673`) and clamped at ±30
  (`:712`).
* **Coverage.** It can only ever learn chunks reached from a "flat, two-distinct-chunk" press on
  bank 1 — a small subset of the 1444 selectors, and none of the 63% on bank 0 (Gap 3).

The value it is guessing is `C`, and `C` is in `notes/data/kn5000-multisample-sets.tsv` for every
selector, derived from the firmware's SET descriptors with no ear, no clustering, no curation. The
task's methodological directive applies literally here.

**Firmware-derived fix.** Bake `notes/data/kn5000-pitch-trim-table.tsv` (1444 rows, `sel → C`) as a
decoded constant — expressly permitted by the chip-boundary rule ("ROM tables … may be baked in as
decoded constants") and exactly parallel to how the IC307 page directories are already used. Then

```cpp
// the ONLY inputs are the two chip registers
const int32_t C = pitch_trim(v.regs[1]);          // baked, from the firmware SET descriptors
const double note = (double(int(v.regs[8])) - 128.0 - double(C)) / 256.0;
freq = 440.0 * std::pow(2.0, (note - 69.0) / 12.0);
```

and delete the learner, the CONFLICTED state, the ±25/±30 clamps, and (for pitch) the whole
key-bed correlation path. Keep the current key-bed-anchored path only as the fallback for the 77
ambiguous selectors and for any `+0x040` the table does not cover.

**Confidence: MEASURED** (that `C` is in the data and is single-valued for 94.7% of selectors);
**INFERRED** (that baking it is strictly better in every non-ambiguous case — it is exact there,
whereas the learner is exact only after the right press has happened).

---

### GAP 7 — Aperiodic recordings ignore `+0x400` completely

**Wrong.** `:743-747` returns `pitch_step = 0x10000` for any chunk whose `detect_period()` gave 0,
without looking at `+0x400`. The firmware still ships a meaningful pitch for those voices (a
fixed-pitch drum partial gets `SET[+0x0c] + coarse·256 + …`, and master TRANSPOSE/TUNE are added to
every voice at L15521/L16027).

**Audible consequence.** A drum kit that uses one recording at two pitches (a common trick — the
IC307 content map §4 shows recordings reused per zone) renders both copies identically; master
transpose/tune has no effect on percussion.

**Firmware-derived fix.** Apply the *relative* part only, which needs no root: latch `regs[8]` the
first time this chunk is keyed and scale by `2^((regs[8] − ref)/3072)`. Or, with the `C` table,
`step = 2^((regs[8] − 0x80 − C)/3072 − k)` for a per-chunk reference `k`.

**Confidence: MEASURED** (the code path and the firmware's write); **SPECULATIVE** on the audible
size — the real chip's rate for an aperiodic chunk depends on its root field in the wave ROM, which
is documented ABSENT from IC307's records (`kn5000-ic307-content-map.md` §3.4), so "native rate" may
well be right for most drums. Do not change this one without a root decode.

---

### GAP 8 — A voice belonging to the accompaniment can steal the pitch of a key the player pressed 300 ms earlier

**Wrong.** `assign_chord_notes()` `:390-406` takes "the most recent input note-on within 0.30 s" as
the chord for **any** voice that keys on, with no test that this voice was actually caused by the
key bed. A rhythm/accompaniment/demo voice starting inside that window is given one of the player's
notes as `true_note` and is pitched to it.

**Audible consequence.** While the player holds a chord, accompaniment voices jump onto the played
notes; the moment the window expires they fall back to the (already wrong, Gap 2) `0x3524` anchor.
Intermittent, tempo-dependent pitch instability in the accompaniment.

**Firmware-derived fix.** Same as Gaps 2/6 — with a register-derived note there is nothing to
correlate. If the correlation is retained, it must be restricted to voices whose part the key bed
actually drives, which is not visible at the chip boundary — another argument for the table.

**Confidence: MEASURED** (code); **INFERRED** (that it fires in practice — not yet observed live,
because reproducing it needs the accompaniment running under a held chord).

---

### GAP 9 — `+0x100`/`+0x140` (the LFO pair) are stored and never read, so no vibrato is ever produced

**Wrong (incomplete, not incorrect).** `LABEL_024300` (asm L16962-16984) builds them from
`partial_blk[+0x0F]&7` through a 6-entry jump table at `0x0000F6B3`; mode 0 (`LABEL_022DA1` L14697)
emits the "no LFO" constants `0x017F`/`0x7F7F`, and the live capture above shows the piano getting
`+0x100 = 0x2466`, `+0x140 = 0x6FDA` — i.e. an LFO *is* programmed. `LABEL_024366` L17006 modulates the low 7
bits of `+0x100` by `part[+0x1f]` with the sign from `slot[+0x27][+0x18]` bits 6/7, which is the
same "depth with a signed part offset" shape `LABEL_023A4A` uses for the pitch detune.

**Audible consequence.** Every vibrato'd sound (strings, brass, the Tremolo/Wurly electric pianos)
renders perfectly static.

**Fix.** Not decidable from the firmware alone: the *inputs* (rate, depth, delay, waveform) are
traced, but whether the LSI routes the LFO to pitch, amplitude or both is internal to IC303. State
the uncertainty rather than guessing a destination.

**Confidence: MEASURED** (registers and builders); **SPECULATIVE** (that they modulate pitch).

---

### GAP 10 — The rendered pitch is set by a MEASUREMENT of the PCM, not by the ROM's declared tuning

**Wrong in principle, small in effect.** `:785` sets the rate from `detect_period()`, so every
chunk is forced to play its measured fundamental exactly at the equal-tempered played note. The
firmware instead declares the tuning: `+0x400` and the chunk's root. Any difference between the
recording's true pitch and the ROM's belief about it — deliberate stretch tuning, the per-key detune
tables that fill IC307 records 180/181 (`kn5000-ic307-content-map.md` §3.2), or simply the
recording's own inharmonicity — is silently removed.

**Quantified (MEASURED, this pass).** Using `K(chunk) = C + 0x80 − 3072·log2(period)` on the
acoustic-piano page (class 7, page 3, all 57 chunks, periods measured with the HLE's own
`detect_period()` re-implemented in Python):

```
class 7 (piano): spread 57.9 units = 22.6 cents;  IQR 18.8 = 7.3 cents;  max dev from K_page 39.0 = 15.2 cents
class 6        :                                  IQR 14.8 = 5.8 cents
class 5        :                                  IQR 24.6 = 9.6 cents
class 4        :                                  IQR 18.2 = 7.1 cents
```

and per-zone, for the default piano SET #1, the difference between what the ROM declares and what
the HLE renders runs −6.2 … +9.8 cents, giving **zone-boundary steps of up to 12.6 cents that the
HLE renders as exactly 0.0 cents** (full table in §4 below).

**Audible consequence.** Sub-audible as absolute pitch. It does mean the KN5000's own multisample
tuning character is replaced by textbook equal temperament, and that the HLE's chromatic scale is
*smoother* than the real instrument's.

**Fix.** Only after the chunk root is decoded — the residual above is a mixture of the ROM's
intent and `detect_period()`'s own estimation error, and the two cannot be separated without it.
Explicitly **not** a "just apply the trim" fix: applying `C` on top of a period-derived rate would
double-correct.

**Confidence: MEASURED** (the numbers); **INFERRED** (the split between ROM intent and estimator
error, which is unresolved).

---

## 4. WHAT I AUDITED AND FOUND CORRECT

* **The `+0x400` scale and offset.** 0x100 units/semitone, 0xC00/octave, `+0x80` half-semitone
  centring, range clamped to [0, 0x7FFF] — the model in `kn5000_tonegen.cpp:525-539` and
  `.h:177-196` matches `LABEL_022B02` and `LABEL_023584` exactly. Confirmed again live.
* **The `+0x040` decode.** `page = (w>>12)&3`, `bank = (w>>14)&3`, `chunk = w & 0x0FFF` reproduced
  the live `0x7007`/`0x7017` for C4 and matched the SET descriptor's zone map key-for-key. No change
  needed.
* **The register-address decode** (`ch = addr&0x3F`, `bank = (addr>>6)&3`, `group = addr>>8`) —
  re-verified against `ToneGen_WriteVoiceParams` L29565-29940 field by field. Correct.
* **Sub-sample period refinement.** Rounding the fundamental to whole samples would detune by up to
  `1200/(2P)` cents — 83 cents at the top of the piano bank where `P = 7.2`. The 16.16 period
  (`:1148-1163`) is necessary and correctly applied at `:785`. Verified by re-implementing the
  estimator and reproducing the documented 16/16 monotone period ladder
  (237.40 … 7.21 samples, span 60.50 semitones vs. the firmware's 16 zones × 4 semitones = 60).
* **Multisample zone boundaries.** Better than I expected. For the default piano SET the firmware's
  own declared step at each of the 15 boundaries is
  `−6.8, +12.6, −9.1, +0.2, −1.8, −0.3, +4.1, −3.0, +2.1, −3.9, −1.2, −1.0, +4.4, −6.3, +7.8` cents;
  the HLE renders 0.0 at every one. **Worst-case error 12.6 cents, RMS 5.5 cents.** This is a real
  divergence (Gap 10) but it is not what anyone is hearing.
* **Honky-Tonk-style unison detune on ONE chunk.** Both partials share `+0x040`, so
  `resolve_note_group()`'s mean-centring branch (`:703-709`) spreads them by their own register
  difference even with nothing learned. Honky-Tonk's `Δ+0x400 = 0x24 = 36` units → ±7 cents → a
  ~2.1 Hz beat at C4. Correct as-is *provided* the press is flat; a patch with both a transpose and
  a detune loses the detune (that path needs `hi−lo < 0.5`).
* **The default Piano's two partials.** `+0x040 = 0x7007` and `0x7017` with an identical
  `+0x400 = 0x34C1`: page 3 is two byte-identical 16-chunk runs, so these are the same recording at
  the same pitch. Rendering them identically in pitch is correct; they differ only in `+0x080` and
  `+0x180`, which is the level/expression dimension, not this one.
* **Aperiodic recordings play at native rate.** Given that IC307 carries no root field, this is the
  only defensible choice today (see Gap 7 — flagged, but deliberately *not* recommended for change).
* **Chromatic pitch for a key-bed/MIDI note on an untransposed patch is exact.** `+0x400` for C4
  matched the ROM prediction to the unit, and the equal-tempered formula at `:757` is exact by
  construction. The reported ±5…14-cent measurement residuals in `kn5000-pitch-velocity.md` are
  autocorrelation quantisation in the *verification*, not in the renderer.

---

## 5. RANKED RECOMMENDATION

| # | change | risk | what it buys |
|---|---|---|---|
| 1 | **Gap 1** — latch `pitch_ref` at key-on, apply `(regs[8] − pitch_ref)/256` on later `+0x400` writes | none (pure register delta, absolute pitch untouched) | pitch bend, auto-bend, live tune changes, portamento |
| 2 | **Gap 6/2/3/4/5** — bake `sel → C` and derive `note = (regs[8] − 0x80 − C)/256` | medium; keep the key-bed path as fallback for the 77 ambiguous selectors | every transpose/detune/fold/key-follow/fixed-pitch/scale-tuning, correct accompaniment & demo pitch, retires the learner and the chord pairing |
| 3 | **Gap 5 alone**, if 2 is deferred — use the full 12-bit entry in `voice_pitch_index()` | low | stops chords inverting on 33% of SETs |
| 4 | **Gap 9** — LFO | blocked: destination not decidable from the firmware | vibrato |
| 5 | **Gap 10 / Gap 7** — chunk root decode in the wave-ROM parameter records | research | retires `detect_period()` from the pitch path entirely |

## 6. REPRODUCTION

Everything numeric above is regenerated by one committed script — no scratch state, stdlib only:

```bash
cd kn7000_mame
python3 tools/kn5000_pitch_audit.py                # prints all six checks (~3 min: it re-runs
python3 tools/kn5000_pitch_audit.py --emit-table   # detect_period on 382 IC307 chunks)
#   1. per-selector constant C, single-valued vs ambiguous
#   2. the 0x3524 fallback-anchor error distribution
#   3. voice_pitch_index() monotonicity over all 487 SETs
#   4. partial-block key-follow / coarse / fine census (interleaves IC3/IC1 as
#      ROM_LOAD32_WORD, kn5000.cpp:1166-1167, and reads blk[+0x04/+0x05/+0x06] at region_off)
#   5. the IC307 page law and its per-class concentration
#   6. the default piano's zone-boundary steps
# --emit-table rewrites notes/data/kn5000-pitch-trim-table.tsv (the sel -> C table Gap 6 wants)
```

The live bus capture:

```bash
cp <pre-init nvram2> <isolated>/kn5000/ ; cd kn7000-emulator
OUT=/tmp/tap1.log timeout 300 ./kn7000 kn5000 -rompath ./roms -pluginspath ./plugins \
    -skip_gameinfo -window -nomaximize -nvram_directory <isolated> \
    -autoboot_script ../kn7000_mame/tools/kn5000_pitch_tap.lua -debug -debugger none
# the tap is one debugger watchpoint:
#   sub.debug:wpset(subsp,"w",0x100000,4,"1",'printf "IC %06X=%04X", wpaddr, wpdata; g')
# T_ARM/T_ON/T_OFF/T_END and KEYPORT/KEYMASK are env vars (default KEY2 mask 1 = C4).
```
