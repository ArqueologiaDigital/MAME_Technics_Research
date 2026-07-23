# KN5000 tone-gen — DECODE STAGE: SET-index → partial-set → register +0x040

Author: autonomous decode pass, 2026-07-23. Requested by Felipe Sanches.
**Investigation only** — no `src/` edits, no rebuild. All instrumentation is runtime-only (MAME lua
RAM reads + a keybed read-tap) in an isolated scratchpad rundir with a **copy** of the pre-init
nvram; `kn7000-emulator/nvram` (owner's live state) was never touched.

This note closes the DECODE STAGE: it untangles `LABEL_032682` / `LABEL_03248B` (SET-index →
partial-SET pointer) and `LABEL_023849` (partial-SET → register +0x040), and decodes the exact bit
semantics of the +0x040 word. It **grounds every claim in the v142 sub-CPU disasm**
(`kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`) **and validates it against a
live DRAM walk** that follows the firmware's own pointer chain and reconstructs +0x040 for every
note — matching the `kn5000-live-captures.md` register fingerprints exactly for Piano, Guitar and
Organ, and (with one keyscale offset) Mallet.

Evidence labels: **MEASURED** (read live / from ROM bytes / from disasm), **PROVEN-BY-CONSTRUCTION**
(follows directly from a traced code path), **INFERRED**, **SPECULATIVE**.

Respecting the chip boundary throughout: IC303 sees only register writes (0x100000 addr / 0x100002
data). Everything below is *how the firmware computes the +0x040 word it writes*; no RAM value ever
crosses to the chip.

---

## 0. TL;DR — the decoded transform

For each key-on, register **+0x040 = record[0]**, the first 16-bit word of the multisample partial
record the firmware selects. The selection is a **two-stage pointer walk**:

```
STAGE A  (LABEL_032682 → LABEL_03248B):   SET index (ptr0[+0x02])  ─┐
         + ptr0[+0x01], part context, note                          ├─▶  SET-descriptor pointer
         + runtime base tables @0x045310 / @0x045314 / @0x04136E   ─┘     (stored to desc+0x1b/+0x1f)

STAGE B  (LABEL_023849):
   1. key = high byte of desc+0x06  (= MIDI note ± per-instrument keyscale)
   2. zoneslot = ptrC[key]                       ; ptrC = 128-entry note→zoneslot keytable
   3. E        = ptrA[4 + zoneslot]              ; ptrA = zoneslot→record-index remap
   4. record   = ptrB + E*stride                 ; ptrB = base of the partial records
                                                 ;   stride chosen by SET[0] bits 5/6/7
   5. +0x040   = record[0]        = { [15:12] = WAVE BANK/class , [11:0] = multisample ENTRY }
```

Where the SET descriptor (in sub-CPU DRAM) is:

| off | field | meaning |
|---|---|---|
| SET[0]      | class/format flags | bits **5/6/7** pick one of six record builders → record **stride** |
| SET[+1..4]  | rel offset → **ptrA** | zone table: 4-byte header, then `ptrA[4+zs]` = record index E |
| SET[+5..8]  | rel offset → **ptrB** | base of the partial-record array (records of `stride` bytes) |
| *(ptrA)     | rel offset → **ptrC** | 128-entry byte keytable: note → zoneslot |

(rel offsets are made absolute by `+ *(0x045310)`; live `*(0x045310) = 0x050000`.)

**+0x040 semantics (decoded):**
* **bits [15:12] = WAVE BANK / partial-class** — a field stored *in the directory record data*
  (record[0]>>12). Per-instrument-constant. Observed 0x0–0x7 (Strings 0, Brass/Bass 1, Mallet 2,
  Guitar/Sax/World/GM 3, Organ/Accordion 4, Flute/Drums 5, Drawbar 6, Piano 7). **It is NOT** a
  physical chip-select (one chip), **NOT** an output bus (bus gains are separate registers
  +0x800…), and **NOT** the firmware's builder-class (Piano's builder is class 4, its +040 nibble
  is 7 — they differ, §4). It is the sample directory's wave-bank/timbre-class selector.
* **bits [11:0] = multisample ENTRY (key-zone) index** — which of the instrument's N zones plays;
  it is record data too, and it is *chosen by the played note* through the two-table remap above.
  Fits in a byte for most instruments (why prior notes called it "the low byte"), but Sax `0x13E`
  and GM `0x112` overflow the byte → the field is the low **12** bits, not 8.

---

## 1. Where the SET index comes from — MEASURED

`ptr0` = tonerec's first delivered partial pointer (`tonerec = 0x041368 + part*0x11F + 0x6E`;
`ptr0 = *(tonerec)`). `ptr0[+0x02]` = the tone's **multisample-SET index**
(Piano 0x00 / Guitar 0x14 / Brass 0x38 / Organ 0x58 / … — full table in `kn5000-live-captures.md §2`).
`ptr0[+0x01]` is a companion **sub-select** used as a fine index in Stage A.

The read site is `LABEL_032682` (0x032682, asm L34747):

```
LABEL_032682:
    LD L,(XBC+001h)   ; ptr0[+0x01]  → IY (sub-select)
    LD C,(XBC+002h)   ; ptr0[+0x02]  → the SET index
    LD IXL,A          ; A = note
    ...               ; pack: WA=note, DE=SET index, C=ptr0[+0x01], + 2 stack args
    CALR LABEL_03248B
```

Caller = `LABEL_02B576` (voice/key descriptor builder, L26855): `CALL LABEL_032682` (L26910), then
`LD (XWA+01fh),XHL` (L26971-72) stores the returned SET pointer to **desc+0x1f** (and +0x1b).
(**MEASURED** for the reads; **PROVEN-BY-CONSTRUCTION** for the store.)

---

## 2. STAGE A — `LABEL_03248B`: SET index → SET-descriptor pointer

`LABEL_03248B` (0x03248B, L34554) **decomposes the SET-index byte** and indexes runtime tables:

```
LD IZL,C ; AND IZ,007fh      ; IZ = ptr0[+0x01] & 0x7F     (fine sub-select)
LD IYL,E ; AND IY,000fh      ; IY = SET & 0x0F             (group / record-stride hint)
LD IXL,E ; AND IX,00c0h      ; IX = SET & 0xC0             (sub-family)
LD C,E   ; AND BC,0030h      ; dispatch on SET & 0x30 :
    ==0x10 → LABEL_0324DD      (the paged / streamed-voice families — FLUTE/SAX/WORLD/ORGAN/GM etc.
                               uses the per-part table 0x04136E and bases 0x045318/0x04531C)
    ==0x30/0x20/0x00 → LABEL_0324D1 → LABEL_0323E5   (the ordinary multisample families)
```

`LABEL_0323E5` (L34495) sub-dispatches on **SET & 0xC0** to pick a base triple `{XHL,XIX,IY}` from
the tone-bank struct at `*(0x045314)` (offsets 0x0c/0x10/0x14/0x18/0x1c/0x20 and 0xea/0xf0), then:

```
LABEL_032469:
    idx  = ((SET & 0x0F) << 7) + (ptr0[+0x01] & 0x7F)     ; composite index
    ent  = *( XHL + idx*2 + *(0x045310) )                 ; table entry (rel offset)
    SETp = *(0x045310) + XIX + IY * ent                   ; absolute SET-descriptor pointer  → RET
```

So the SET index is treated as a **structured address**, not a scalar: `&0x30` = primary family,
`&0xC0` = sub-family, `&0x0F` = group, and `ptr0[+0x01]` = the fine slot within the group. The
result is an absolute pointer into DRAM tables that were unpacked from the tone ROM at boot.

**Honesty:** Stage A's numeric body is traced instruction-by-instruction (**MEASURED** disasm) but I
did **not** re-derive the boot-time contents of `*(0x045310)/*(0x045314)/0x04136E`; instead I read
the **resolved SET pointer live** (desc+0x1f) and validated the *whole* chain end-to-end in §3.
This is why the note is authoritative on the transform even though Stage A's tables are runtime data.

---

## 3. STAGE B — `LABEL_023849`: SET pointer → +0x040 — MEASURED + LIVE-VALIDATED

`LABEL_023849` (0x023849, L15805) is the first pre-compute in the note-on chain
(`LABEL_02B4E3` L26813 calls it, then bursts scratch 0x0451CC to the chip via
`ToneGen_WriteVoiceParams`). It reads **desc+0x1f = SETp** and walks:

```
XIZ  = *(desc+0x1f)                       ; SETp
ptrA = *(SETp+1) + *(0x045310)            ; L15810-13
ptrB = *(SETp+5) + *(0x045310)            ; L15814-16
ptrC = *(ptrA)   + *(0x045310)            ; L15817-20
key  = (desc+0x06 >> 8) & 0x7F            ; L15822 + LABEL_022A32 (AND 7f00h; SRA 8)
zs   = ptrC[key]                          ; L15824-25   note→zoneslot
E    = ptrA[4 + zs]                       ; L15828-30
; dispatch on SET[0] bits 6,7,5 → one of six builders (each: record=ptrB+E*stride;
;   (0451CEh)=record[0]  →  reg +0x040 ; and OR a pitch-class into desc+0x01)
```

Builder / stride table (`LABEL_022A3F`..`022AE7`, L14295-14361), selected by **SET[0]** bits.
The dispatch (L15831-36) is: `BIT6==0 → {BIT7}`, else `{BIT7 → {BIT5}}`. Resolved combinations:

| SET[0] b6 | b7 | b5 | builder | record stride | desc+0x01 OR (pitch-class) | 293E secondary = |
|---|---|---|---|---|---|---|
| 1 | 1 | 1 | 022A3F | 0x0F | 0x7000 | record[+0x0d] |
| 1 | 1 | 0 | 022A61 | 0x0C | 0x5000 | record[+0x0a] |
| 1 | 0 | 1 | 022A83 | 0x0D | 0x3000 | 0 |
| 1 | 0 | 0 | 022AA4 | 0x0A | 0x1000 | 0 |
| 0 | 1 | x | 022AC5 | 0x06 | 0x4000 | record[+0x04] |
| 0 | 0 | x | 022AE7 | 0x04 | (none) | 0 |

Live-observed: Piano SET[0]=0x80 (b6=0,b7=1) → 022AC5/stride0x06; Guitar SET[0]=0x02, Organ/Mallet
SET[0]=0x00 (b6=0,b7=0) → 022AE7/stride0x04. Piano's 293E was nonzero (=record[+0x04], live 0xF841);
Guitar/Organ/Mallet's 293E was 0 — both consistent with the table.

### 3.1 LIVE DRAM walk — the decisive validation

`decode_walk.lua` presses one note, reads `desc+0x1f`, follows the chain above **in lua**, and
reconstructs `record[0]` for a spread of notes. Base `*(0x045310)=0x050000`. Predict-then-check
against the `kn5000-live-captures.md §4` register fingerprints:

**PIANO** — SETp=0x077923, SET[0]=0x80 (b7=1,b6=0,b5=0) → builder **022AC5, stride 0x06**. ptrA,ptrB
resolved; ptrC = the 128-byte note→zoneslot keytable. Reconstructed record[0] for all 7 captured
notes — **7/7 EXACT** (MIDI note in parens):

| note | zoneslot | E | record[0] | capture +040 | ✓ |
|---|---|---|---|---|---|
| C2 (36) | 0x08 | 0x01 | 0x7001 | 7001 | ✓ |
| C3 (48) | 0x0C | 0x04 | 0x7004 | 7004 | ✓ |
| C4 (60) | 0x10 | 0x07 | 0x7007 | 7007 | ✓ |
| E4 (64) | 0x11 | 0x08 | 0x7008 | 7008 | ✓ |
| G4 (67) | 0x12 | 0x08 | 0x7008 | 7008 | ✓ |
| C5 (72) | 0x14 | 0x0A | 0x700A | 700A | ✓ |
| C6 (84) | 0x18 | 0x0D | 0x700D | 700D | ✓ |

osc2 (voice 1) walked independently → 0x7017 at C4 = capture +040b 7017 ✓.

**Full Piano zone map** (MEASURED, from ptrC ⊗ ptrA — the complete key-range→zone table the task
asked for; `+040 = 0x7000 | E`, so Piano's ENTRY index == E, 16 zones total):

| MIDI note range | zoneslot | E = ENTRY | +0x040 |
|---|---|---|---|
| 0–35   | 00–07 | 0x00 | 7000 |
| 36–39  | 08 | 0x01 | 7001 |
| 40–43  | 09–0A | 0x02 | 7002 |
| 44–47  | 0B | 0x03 | 7003 |
| 48–51  | 0C | 0x04 | 7004 |
| 52–55  | 0D–0E | 0x05 | 7005 |
| 56–59  | 0F | 0x06 | 7006 |
| 60–63  | 10 | 0x07 | 7007 |
| 64–67  | 11–12 | 0x08 | 7008 |
| 68–71  | 13 | 0x09 | 7009 |
| 72–75  | 14 | 0x0A | 700A |
| 76–79  | 15–16 | 0x0B | 700B |
| 80–83  | 17 | 0x0C | 700C |
| 84–87  | 18 | 0x0D | 700D |
| 88–91  | 19–1A | 0x0E | 700E |
| 92–96+ | 1B–1C | 0x0F | 700F |

The lowest ~3 octaves collapse to zone 0 (ptrA maps zoneslots 0–7 → E0); above that, zones widen to
~3–6 semitones. **This is the multisample split map, addressable purely from the played note.**

**GUITAR** — SETp=0x077BF3, SET[0]=0x02 (b6=0,b7=0) → builder **022AE7, stride 0x04**. 7/7 EXACT:
C2→3000, C3→3001, C4→3002, E4→3002, G4→3002, C5→3003, C6→3003 (all match capture).

**ORGAN** — SETp=0x07877E, SET[0]=0x00 → builder **022AE7, stride 0x04**. 7/7 EXACT: C2/C3→4001,
C4/E4/G4→4002, C5/C6→4003 (all match capture). (Organ is an extended-path instrument — it also
emits +0x440/+0x540 etc. — but its +0x040 selection is this same mechanism; the extended registers
are *additional*, not a replacement.)

**MALLET** — SETp=0x077AC7, SET[0]=0x00 → builder **022AE7, stride 0x04**. Reconstruction matched
capture **after a +12-semitone shift** of the ptrC index: capture C4(60)=2096 = walk note 72;
capture C5(72)=2098 = walk note 84; capture C6(84)=209A = walk note 96; etc. → MALLET applies a
one-octave keyscale to `desc+0x06` before the keytable lookup (the mallet/glockenspiel voice sounds
an octave up). Mechanism confirmed; the transpose lives in `desc+0x06`, not re-derived here.

---

## 4. What each +0x040 bit means — DECODED

**HIGH NIBBLE (bits [15:12]) = WAVE BANK / partial-class.** It is `record[0]>>12`, i.e. **data in
the multisample directory**, not a computed class. Decisive proof it is *data*, not the firmware
builder-class: **Piano** runs builder 022AC5 (OR class **4** into desc+0x01, stride 6) yet its
+0x040 nibble is **7**; **Guitar** runs builder 022AE7 (class **0**, stride 4) yet its nibble is
**3**. The builder-class governs record *stride* and the *pitch* class stamped into desc+0x01; the
+0x040 nibble is an independent field the chip reads to pick the wave bank. It ranges 0x0–0x7 across
the 16 sound-groups and groups instruments into ~8 wave banks (Strings/OrchPad/Synth share 0;
Guitar/Sax/World/GM share 3; …). **Ruled out:** chip-select (single IC303), output bus (separate
+0x800 registers). **INFERRED role:** a wave-group/timbre-class index into the chip's internal
sample directory; whether it maps 1:1 to the IC307 "4×1 MB page" layout is **SPECULATIVE** (nibble
range 0–7 exceeds 4 pages, so it is more likely a partial/wave-class than a raw ROM page).

**FALSIFIED sub-hypothesis (predict-then-check):** I predicted Mallet's nibble 2 and Drawbar's 6
might be nibble-*doublings* of an underlying class (the `LABEL_02399D` path doubles `record[0] & 
0xF000` when `0x041343` bit2 is set, L15969-76: 1→2, 3→6). **MISS** — live `0x041343 = 0x0208`,
**bit2 = 0** for Mallet, and its record[0] is genuinely 0x2096–0x209A. Classes 2 and 6 are real
directory data, not doubling artifacts.

**LOW 12 BITS (bits [11:0]) = multisample ENTRY / key-zone index.** = `record[0] & 0x0FFF`, also
directory data, but the *record chosen* is driven by the played note via §3's two-table remap. It is
piecewise-constant across the keyboard, stepping at split points (Piano 001→004→…→00F over 16
zones). Called "the low byte" in prior notes because it fits a byte for most instruments — but
**Sax 0x13E and GM 0x112 overflow the byte**, so the correct width is 12 bits. DRUM KITS is the
exception: every key is a different percussion instrument, so its ENTRY jumps non-monotonically (a
per-key drum map, not a pitched multisample) — consistent with a keytable whose `ptrC[note]` is a
near-identity drum index rather than a coarse zone.

**Two-level remap — why two tables (ptrC then ptrA):** `ptrC` gives a fine ~2-semitone zoneslot for
all 128 keys; `ptrA[4+zs]` then *collapses* zoneslots to actual records, letting the low register
reuse zone 0 and giving instrument-specific, non-uniform zone widths without a 128-entry
per-instrument record list. (PROVEN-BY-CONSTRUCTION + MEASURED for Piano.)

---

## 5. Corrections to prior notes

* `kn5000-voice-pipeline.md §3.2` — the builder→instrument mapping (Piano=022A3F/stride0x0F/class7,
  Guitar=022A83/stride0x0D/class3, Brass=022AA4, Organ=022AC5) is **WRONG**. Live: Piano =
  **022AC5/stride0x06** (SET[0]=0x80), Guitar/Organ/Mallet = **022AE7/stride0x04** (SET[0]=0x02/0x00).
  The six builders are **record-format strides**, not instrument categories, and their class names
  (7000/5000/…/4000) are the desc+0x01 **pitch**-class OR — *not* the +0x040 nibble.
* `kn5000-voice-pipeline.md §0/§6` — "+0x040 high nibble already carries the same class (data + code
  agree)" is **FALSE**: for Piano the code-class (4) and data-nibble (7) **disagree**. The +0x040
  nibble is purely `record[0]` data.
* Any statement that +0x040's zone selector is "the low **byte**": widen to **low 12 bits** (Sax
  0x13E, GM 0x112).
* Reconfirmed unchanged: +0x040 = `record[0]`; the timbre triple +0x0C0/+0x140/+0x500 is computed by
  *other* precompute functions (023A05…) and is instrument-constant; +0x440 is the rotating slot
  counter (`kn5000-live-captures.md §6`), never a waveform selector; the chip boundary holds.

---

## 6. Honest gaps

* **Stage A (03248B) base tables** `*(0x045310)/*(0x045314)/0x04136E` were read as resolved
  live values, not reconstructed from their boot-time ROM source; the SET-index→SET-pointer
  *arithmetic* is traced but its *inputs* are runtime data. The end-to-end chain is nonetheless
  validated (§3), so +0x040 is fully decoded even though Stage A's tables are not statically dumped.
* Full ptrC/ptrA tables dumped for **Piano** only (complete zone map). Guitar/Organ/Mallet validated
  at the 7 captured notes + their record arrays, not their full 128-entry keytables.
* The **keyscale/transpose** applied to `desc+0x06` before the ptrC lookup (visible as Mallet's +12)
  was not traced to its source function; it explains the one instrument whose raw-note reconstruction
  was offset.
* The chip's *internal* use of the +0x040 nibble (wave-class vs ROM page vs partial engine) is
  INFERRED; the exact directory format IC303 dereferences from +0x040 lives in the undumped
  IC304-306 and is **not needed** for the HLE, which can select on (bank, entry) directly.

---

## 7. HLE consequence (register-inputs only)

The selector the HLE must key on is the **full 16-bit +0x040 word** = `{ bank[15:12], entry[11:0] }`,
*not* its high byte. Using `(regs[1]>>8)&0xFF` (as the shipped `select_waveform_index` does) discards
the ENTRY low bits and collapses every multisample split to one wave; and it mis-splits Sax/GM
(entry>0xFF). Correct key: `bank=(regs[1]>>12)&0xF`, `entry=regs[1]&0x0FFF`. This is exactly the
value the firmware computes from (SET index, note) via §3, so selecting on it reproduces the
per-instrument, per-key-zone waveform choice from the register stream alone — no RAM peeking, chip
boundary intact. (Real per-zone PCM fidelity remains blocked on the NO_DUMP IC304-306; this is a
*selection* decode, not a sample-data recovery.)

---

## 8. Reproduction

`decode_walk.lua` (scratchpad): install a keybed read-tap; at t≥9.5 s optionally press a SOUND-GROUP
button (`INAME/IPORT/IMASK` env), press C4, then dump `desc = 0x04308E + V*0x47`, `SETp=*(desc+0x1f)`,
`ptrA=*(SETp+1)+base`, `ptrB=*(SETp+5)+base`, `ptrC=*(ptrA)+base` (`base=*(0x045310)`), the 128-byte
ptrC keytable, the ptrA `[4+zs]` remap, and reconstruct `record[0]=*(ptrB+E*stride)` per note.

```
SP=<scratchpad>; cp $SP/nvram2/kn5000/nvram{1,2} $SP/wr/nvram/kn5000/
cd kn7000-emulator && INAME=GUITAR IPORT=CPR_SEG2 IMASK=0x02 timeout 90 kn7000 kn5000 -rp roms \
  -window -nomaximize -skip_gameinfo -nvram_directory $SP/wr/nvram -autoboot_delay 0 \
  -autoboot_script $SP/decode_walk.lua -seconds_to_run 20 -nothrottle
```
Default (no INAME) walks Piano. Cross-checks the register fingerprints in `kn5000-live-captures.md`.
