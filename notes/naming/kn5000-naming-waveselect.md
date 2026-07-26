# KN5000 sub-CPU naming proposal — subsystem C: WAVE / SAMPLE SELECTION

Author: autonomous NAMING pass, 2026-07-26. Requested by Felipe Sanches.
Target: `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`
(+ `symbols/subcpu_symbols_reference.txt`).

**Scope:** everything that turns "the user picked sound X and pressed key K with velocity V" into
the single 16-bit word the tone generator receives at register **`+0x040`** — plus the four big
Table-Data structures (patch records, velocity-split records, multisample-SET descriptors, named
tone records) and the legacy `+0x440` path.

Evidence labels used below: **MEASURED** (an instruction in the v142 disasm, or ROM bytes read
this pass), **PROVEN-BY-CONSTRUCTION** (follows from a traced path), **INFERRED**, **SPECULATIVE**.
Everything was **PREDICT-THEN-CHECK**ed against the disassembly before a name was assigned; §1
lists the places where the prior notes turned out to be wrong or imprecise.

**No line numbers are cited.** The `.asm` was being edited concurrently while this pass ran
(the parallel subsystem agents), so every prior note's `L#####` citations are already stale.
All anchors here are **addresses**, which are stable.

---

## 0. Byte-identity verification — DONE, PASSED

The proposal was not merely written, it was **assembled**. In an isolated scratchpad copy of the
tree (so as not to collide with the other subsystem agents editing the same file):

1. snapshot the current `.asm` → assemble with `tools/asl/asl -w` → `p2bin` → **baseline binary**;
2. apply **all 45 label renames of §3**, **16 new `EQU` definitions**, **symbolic replacement of
   16 distinct address-literal patterns** (215 individual literal → symbol substitutions:
   `ToneDB_RelBase` ×27, `ToneDB_RootPtr` ×45, `Part_State_Array` ×70, `ToneGen_Scratch_WaveSel`
   ×13, `Voice_Desc_Staging` ×12, `WaveSel_ZoneRec_PitchWordB` ×10, `ExtVoice_*` ×38), and one
   routine-header comment block;
3. re-assemble.

```
asl: 3 passes, 0 errors, 0 warnings
md5(base.bin)    = 89359904a3216e8cdbbc5399925396f2   256768 bytes
md5(renamed.bin) = 89359904a3216e8cdbbc5399925396f2   256768 bytes   -> BYTE-IDENTICAL
rebuilt ROM (part_a 256B + part_b from 60416) == original_ROMs/kn5000_subprogram_v142.rom  EXACT
```

So the whole naming set — including replacing bare hex addresses by `EQU` symbols in operands
such as `LDA XBC, 0F48Ch:24` and `LD (0451CEh), WA` — is **provably byte-neutral**. The `EQU`
block must be placed with the existing `EQU`s at the top of the file (before first use) so ASL
resolves them in pass 1 and picks identical operand widths.

**Name-collision check:** none of the prefixes `ToneDB_`, `WaveSel_`, `ExtVoice_`, `Wave_`,
`Patch_`, `VelSplit_`, `NamedTone_` occurs in any of the five `symbols/*_symbols_reference.txt`
files. No ASL reserved word or TLCS-900 register/mnemonic is shadowed.

**Note on the second tree:** `v142/subcpu/kn5000_subprogram_v142.s` (the LLVM build, now the
Makefile's primary target) contains **zero** `LABEL_` names — it carries an older, independent,
and in this subsystem **actively wrong** auto-naming (e.g. `0x03248B` is called
`SlotParam_WriteDispatch`, `0x0323E5` is `VoiceBufIdx_Decode`, `0x031F71` is
`DSP_LookupVoiceBuffer`; none of those is what the code does). `symbols/subcpu_symbols_reference.txt`
still carries the `LABEL_` names, i.e. it tracks the ASL tree. Renaming in the ASL tree therefore
does **not** break the LLVM build (separate files), but the two trees should eventually be
reconciled; the misleading LLVM names are listed in §7 so they are not lost.

---

## 1. CORRECTIONS to the prior notes (the valuable part)

### 1.1 `LABEL_032682` does **not** read the tone record's `+0x01/+0x02` — and there are **two** Stage-A feeders with **different** record types (MEASURED)

The task brief and `kn5000-pipe-partialset.md §1` say `LABEL_032682` reads `ptr0[+0x01]`/`ptr0[+0x02]`
of the tone record. `kn5000-firmware-sample-tables.md §2.2` corrects that to `+0x02`/`+0x03`.
**Both are right about a different structure, and neither says so.** The disasm shows two callers
of `LABEL_03248B`, reading two *different* record types:

| feeder | record it reads | fine | set |
|---|---|---|---|
| `0x0325FC` | the **0x51-byte patch PARTIAL BLOCK** (`*(tonerec)`, i.e. `ptr[0]`) | `blk[+0x02]` | `blk[+0x03]` |
| `0x032682` | the **0x15-byte NAMED-RECORD PARTIAL SLOT** (`named_rec + 0x10 + 0x15*p`) | `slot[+0x01]` | `slot[+0x02]` |

and the two structures are the **same layout shifted by one byte** — the 0x15-byte slot is the
0x51-byte block minus its leading constant `+0x00` format byte:

```
patch block : +00 fmt(=0) +01 flags +02 FINE +03 SET +04 coarse +05 fine-tune +06 flags/keyfollow ...
named slot  :             +00 flags +01 FINE +02 SET +03 coarse +04 fine-tune +05 ...
```

Independently confirmed from ROM bytes: named record #2 `"FluteKeyClick"` slot0 =
`40 78 40 …` → `(fine=0x78, set=0x40)`, exactly the pair `kn5000-sample-name-table.tsv` lists.

### 1.2 `LABEL_02177E`'s `A` argument is the **PART index**, not a note (MEASURED)

`kn5000-pipe-resolver.md §2` says "`A = note` (`voice[+0x04]`)" and then reasons that
`voice[+0x04]` must be "a key-zone / slot index (0..25), not a MIDI note" because of the
`A < 0x1A` gate. The descriptor builders settle it: **`desc+0x04` is written with the PART index**
(`LD (XBC+004h),A` with `A` = the part argument, in *both* `0x02B576` and `0x02B861`), and
`desc+0x05` is `note | 0x80`. So the `< 0x1A` gate is a part-count bound, and the resolver is
per-part, not per-note. The note's *conclusion* ("not a MIDI note") stands; its *identification*
was open, and this closes it.

### 1.3 `LABEL_032AE0` reads a **sub-tone selector table inside the patch header at `+0x27`** — and the "extended key range" mechanism is now fully decoded (MEASURED, end-to-end)

`kn5000-firmware-sample-tables.md §10` lists as open gaps: what `desc+0x17` is on the second
path, and how the 610-record named table is reached. Traced this pass:

```
note-on, note >= 0x78 (120)  AND  SET_desc[+0x00] bit1 set
   i        = note - 0x78 + SET_desc[+0x0b]
   {lo,hi}  = u16[ SET_desc[+0x0c] ]                    <-- +0x0c is NOT a base pitch here
   patch    = ToneDB_Find_PatchRecord(lo, hi)
   {lo2,hi2}= u16[ patch + 0x27 + 2*i ]                 <-- sub-tone selector table
   named    = ToneDB_Resolve_NamedToneRecord(lo2, hi2)  <-- a 58-byte NAMED TONE RECORD
   slot     = named + 0x10 + 0x15*p ; (fine,set) = slot[+1], slot[+2]  -> Stage A1
```

Checked against ROM bytes, and it lands exactly:

* the SET flags census is `0x00`×318, `0x01`×3, `0x02`×13, `0x08`×10, `0x80`×134, `0x81`×9 —
  and **all 13 bit-1 descriptors have `+0x0c = 0x417F`**, i.e. `{lo=0x7F, hi=0x41}`, and `0x41`
  is one of exactly three special bank values `ToneDB_Find_PatchRecord` accepts
  (`{0..7, 0x40, 0x41, 0x70}`). A base pitch could not possibly be 0x417F for all 13.
* `{0x7F,0x41}` resolves to patch record **#335 `"  Special Kit   "`** (type `0x80`,
  partial map `0x00` — *no ordinary partials at all*, which is why it only ever appears as a
  sub-tone donor).
* its `+0x27` table is three identical 8-entry groups (matching the three observed
  `SET_desc[+0x0b]` values `0x00 / 0x08 / 0x10`), whose non-zero entries resolve to named
  records **`"Pick Noise 4"`, `"Pick Noise 1"`, `"Pick Noise 3"`, `"Fret Noise"`**.
* the 13 bit-1 SET descriptors are the GUITAR family (set #49 is the live-captured GUITAR SET).

So: **MIDI notes 120..127 on a guitar patch play the ROM's fret/pick noise samples**, selected
through the named-tone table. Corroboration from a second, independent code path: the pitch
builder `0x023584` tests the *same* `SET_desc[+0x00]` bit 1 and, when set, **substitutes the
constant `0x4280` for `SET_desc[+0x0c]`** — i.e. the firmware itself knows `+0x0c` is not a
pitch in that case.

### 1.4 The named-tone index table has **4096** entries, not 1024 (MEASURED)

`kn5000-firmware-sample-tables.md §0` lists `0x08D8A3` as `1024 × u16`. It is
`0x08F8A3 − 0x08D8A3 = 0x2000` bytes = **4096 u16** — which is exactly what the addressing needs:
`idx = ((hi & 0x1F) << 7) + (lo & 0x7F)`, max `0xFFF`.

### 1.5 The 58-byte named tone record layout is `name(13) + mask + 2 + 2×0x15` (MEASURED)

Not stated anywhere. `0x0D + 1 + 2 + 2*0x15 = 0x3A = 58` exactly, and it is what `0x02B576`
dereferences (`rec[+0x0d]` as the partial-present mask, `rec + 0x10 + 0x15*p` as partial slot `p`).
Verified against the ROM for records #0..#5 (`"Silent"`, `"Square Click"`, `"FluteKeyClick"`,
`"Rock Bass Drm"`, `"Room BassDrm1"`, `"Room BassDrm2"`), whose slot `(fine,set)` pairs reproduce
`kn5000-sample-name-table.tsv` exactly.

### 1.6 The six Stage-B builders also store the selected record pointer into `desc+0x0F` (MEASURED)

`kn5000-pipe-partialset.md §3` lists what each builder writes (`0x0451CE`, `0x293E`, the
`desc+0x01` OR). It misses `LD (XWA+00fh), XBC` — **every** builder caches the resolved zone-record
address at `desc+0x0F`. Useful: it is the one place the chosen multisample zone record survives
past the burst.

### 1.7 The velocity-split selector exists **twice**, byte-identical (MEASURED)

`0x022824` and `0x022844` are instruction-for-instruction the same routine (velocity vs the three
`VSEL[0..2]` split points → `L = q ∈ 0..3`). `0x022824` is called from the ordinary note-on path
`0x02B717`; `0x022844` from the named-record path `0x02B576`. Prior notes cite them as if they
were different functions.

### 1.8 `DRUM KITS`' `ptr0 = 0x075A48` is **not** a member of the 629-record patch array (MEASURED)

`kn5000-firmware-sample-tables.md §10.3` calls it "a 0x51 block inside a fixed-stride (0x1AA /
4-slot) region". Checked: `0x075A48 − 0x66 = 0x0759E2` does **not** appear in the 629-entry patch
pointer array (the array's pointers jump from `0x02589E` to `0x033079`, straddling it), and
`0x0759E2` is not ASCII. What `0x075A48` *is*: a stand-alone 0x51-byte partial block sitting
**exactly 0x51 bytes before the A1 index table at `0x075A99`**, with `(fine,set) = (0x00,0x00)`.
The drum per-key map remains **unlocated** — but it is now known *not* to be reachable through the
patch pointer array, which removes a wrong lead.

### 1.9 Fine-transpose scaling differs between the two zone-key builders (MEASURED, unexplained)

* `0x02B3DD` (named-record path, the routine `-firmware-sample-tables.md §5.1` transcribes):
  `IZ += sext(slot[+0x04])` — **×1**.
* `0x023809` (also named-record path, called at the end of `0x02B576`):
  `HL += sext(slot[+0x04]) * 2` — **×2**.
* `0x023A05` (the chip PITCH register path, patch-block structure):
  `DE += sext(blk[+0x05]) * 2` — **×2**.

So `-firmware-sample-tables.md §5.1`'s "`IZ += … sext(partial[+4])`" is right *for `0x02B3DD`* but
does not generalise. Since only the **high byte** of the result indexes the key table, the ×1/×2
difference is inconsequential for zone selection — but it is a real discrepancy and should not be
smoothed over in a header.

### 1.10 A1-index overflow: 20 of 1026 active patch blocks index past their table (MEASURED)

`idx = ((set & 0x0F) << 7) + (fine & 0x7F)` can reach 2047, but consecutive A1 tables are
`0x800` bytes = **1024** entries apart (`0x075A99`, `0x076299`; A2: `0x07959D`, `0x079D9D`,
`0x07A59D`). Over the 1046 active partial blocks (mask-gated at `patch+0x11`), 20 produce
`idx >= 1024` and 7 produce a VSEL index outside its array bound. Two readings, undecided:
the three per-family tables are really one contiguous index space that the family byte merely
offsets into (elegant, and 13 of the 20 land on valid VSEL records), **or** those blocks are
dead data. Recorded as an observation, not a conclusion.

### 1.11 The DRAWBAR path is dispatched by the patch **type** byte, and does **not** go through `0x02B576`/`0x032AE0` (MEASURED)

`kn5000-firmware-sample-tables.md §10.2` says "Drawbar voices are built through `LABEL_02B576` /
`LABEL_032AE0` / `LABEL_032A08` from the 610-record footage table". Traced: those three are the
**sub-tone / extended-key-range** path of §1.3, which is a *guitar-noise* mechanism gated on
`note >= 0x78`. The drawbar path is a different, cleanly separated one:

* `WaveSel_Rebuild_PartCaches` (`0x032938`) dispatches on `patch_record[+0x10] & 0xC0`, i.e. on
  the patch **record type** byte (`0x00,0x10,0x20,0x30,0x60,0x80`):
  `0x00` → the ordinary 4×VSEL + 16×SET cache build; **`0x40` (i.e. record type `0x60`, the
  drawbar registrations) → `0x02AAE7` / `0x02AB10` instead**; `0x80`/`0xC0` → nothing.
* Stage B for those voices is `WaveSel_StageB_Build_WaveWord_Footage` (`0x0238F8`), reached from
  `0x02BCD6`, which derives the zone-record index `E` from the partial index (`0x02B154` /
  `0x02B1E0` / `u16[part_state + 0x102 + 2*p]`, all through `0x02B2C2`) rather than from the key
  table, and is hard-wired to stride 6 / pitch class `0x4000`.

That `patch[+0x10] == 0x60` means "drawbar registration" was already stated in
`-firmware-sample-tables.md §2.1`; what is new is that the type byte is the **runtime dispatch
key**, which is why drawbar voices never touch the key-zone tables — and therefore why
DIGITAL DRAWBAR's live `+0x040` is constant across the keyboard. (The prior note attributed that
to a narrow `[kmin,kmax]` fold; the fold is real for its SET, but the *reason the drawbar voice
takes a different builder at all* is the type byte.)

Corollary, also new: `"  Special Kit   "` (patch #335) has type `0x80` → `WaveSel_Rebuild_PartCaches`
does nothing for it. It cannot be selected as a part's own tone; it exists **only** as a sub-tone
donor. That is a structural confirmation of §1.3.

### 1.12 Confirmations (no change needed)

* `+0x040` = `zone_record[0]` = `{ class[15:12], entry[11:0] }` — reconfirmed. The chip-side
  reading (`page = class & 3`, `bank = (class >> 2) & 3`, `entry` = index into that 1 MB page's
  self-delimiting directory) is `kn5000-structural-validation.md §0`; the firmware never splits
  the nibble, so the disassembly should name it `class` and document the chip reading in Notes.
* Stage A1/A2 arithmetic, the 4-entry SET cache at `part+0x76+0x25*p+4*q`, the VSEL layout
  `{3 split points, 4×(fine,set)}`, `+0x440`/`+0x480` = DMA/voice-slot counters, and
  `LABEL_024CAB` as the always-0-for-ordinary-voices `+0x440` writer: **all re-derived and
  confirmed** this pass. A fresh static walk reproduced PIANO block 0 → VSEL `0x076ABA` → SET
  `0x077923` (= live `desc+0x1b` / `desc+0x1f`), PIANO block 1 → SET `0x077932`, and
  `"Silent"` (fine 0x00, set 0x40) → family-0x40 VSEL `0x08F8A3` → SET #341.

---

## 2. The chain, in one picture (all MEASURED)

```
 panel / MIDI  --{lo,hi}-->  ToneDB_Find_ToneRecord (0x03206F)
                                  |
                                  +-- ToneDB_Find_PatchRecord (0x031F71)
                                        C   = bank_tbl[hi] ; idx = (C<<7)+lo
                                        k   = prog_map[idx]
                                        patch = base + patch_ptr_array[k]     (629 records)
                                  |
 per part/partial (tone change):  WaveSel_Rebuild_PartCaches (0x032938)
    for p in 0..3:  WaveSel_Cache_VelSplitPtr (0x0326B6)
                       -> WaveSel_StageA1_FromPatchBlock (0x0325FC)
                            (fine,set) = blk[+2], blk[+3]
                       -> WaveSel_StageA1_FindVelSplit  (0x03248B)
                            -> tonerec[+0x04] = VSEL record ptr        (11 bytes)
      for q in 0..3: WaveSel_Cache_SetDescPtr (0x0328E2)
                       -> WaveSel_StageA2_FromToneRec (0x032839)
                            (fine,set) = VSEL[3+2q], VSEL[4+2q]
                       -> WaveSel_StageA2_FindSetDesc (0x032750)
                            -> part+0x76+0x25*p+4*q = SET descriptor ptr (15 bytes)

 note-on (0x02B717):  q = velocity split (0x022824) -> desc+0x1b = VSEL, desc+0x1f = SET
                      desc+0x06 = folded zone key (0x023584 / 0x02B3DD / 0x023809)
                      WaveSel_StageB_Build_WaveWord (0x023849):
                          ptrA = base + SET[+1] ; ptrB = base + SET[+5] ; ptrC = base + *ptrA
                          key  = (desc+0x06 >> 8) & 0x7F
                          E    = ptrA[4 + ptrC[key]]
                          rec  = ptrB + stride(SET[0]) * E
                          (0x0451CE) = u16[rec]        <-- THE WAVE-SELECT WORD
                      ToneGen_WriteVoiceParams (0x02D101) bursts 0x0451CC -> register +0x040
```

---

## 3. NAMES — routines

Format: `address  LABEL_ (current)  ->  proposed name  —  purpose`.

### 3.1 Tone-database lookup

| addr | current | proposed | purpose |
|---|---|---|---|
| `0x031F71` | `LABEL_031F71` | `ToneDB_Find_PatchRecord` | 16-bit `{lo,hi}` tone selector → patch-record pointer (or a RAM user-tone record) |
| `0x031F87` | `LABEL_031F87` | `ToneDB_Find_PatchRecord_Preset` | preset path: bank byte-table → program map → 629-entry pointer array |
| `0x031FE4` | `LABEL_031FE4` | `ToneDB_Find_PatchRecord_UserA` | `hi==0x10`: RAM user tone `*(0x04531C) + 0x10 + lo*0x1D6` |
| `0x032002` | `LABEL_032002` | `ToneDB_Find_PatchRecord_UserB` | `hi==0x15`: same, base `*(0x045318)` |
| `0x032020` | `LABEL_032020` | `ToneDB_Find_PatchRecord_KitA` | `hi==0x50`: `*(0x04531C) + 0x4980` |
| `0x032032` | `LABEL_032032` | `ToneDB_Find_PatchRecord_KitB` | `hi==0x55`: `*(0x045318) + 0x4980 + (lo&3)*0x2927` |
| `0x032054` | `LABEL_032054` | `ToneDB_Find_PatchRecord_Default` | fallback: patch record #0 |
| `0x03206E` | `LABEL_03206E` | `ToneDB_Find_PatchRecord_Return` | common `RET` |
| `0x03206F` | `LABEL_03206F` | `ToneDB_Find_ToneRecord` | wrapper: `(0x041343)` bit0 selects the alternate map `0x031F16`, else `ToneDB_Find_PatchRecord` |
| `0x032AE0` | `LABEL_032AE0` | `ToneDB_Find_SubToneRecord` | read the `{lo,hi}` sub-tone selector at `patch + 0x27 + 2*i` and resolve it |
| `0x032A08` | `LABEL_032A08` | `ToneDB_Resolve_NamedToneRecord` | `{lo,hi}` → 58-byte **named tone record** (or a RAM user-tone slot) |
| `0x032A68` | `LABEL_032A68` | `ToneDB_Resolve_NamedToneRecord_User` | `hi` bit5 set: RAM path, stride 0x50 at `+0x4AA7` |
| `0x032ADA` | `LABEL_032ADA` | `ToneDB_Resolve_NamedToneRecord_Return` | common exit |

### 3.2 Stage A1 — (fine, set) → velocity-split record

| addr | current | proposed | purpose |
|---|---|---|---|
| `0x0325FC` | `LABEL_0325FC` | `WaveSel_StageA1_FromPatchBlock` | read `(fine,set)` = `blk[+2],blk[+3]` from the patch partial block, call Stage A1 |
| `0x032682` | `LABEL_032682` | `WaveSel_StageA1_FromToneSlot` | read `(fine,set)` = `slot[+1],slot[+2]` from a 0x15-byte named-record partial slot, call Stage A1 |
| `0x03248B` | `LABEL_03248B` | `WaveSel_StageA1_FindVelSplit` | decompose the SET byte, dispatch on `set & 0x30`, return the VSEL record pointer |
| `0x0324D1` | `LABEL_0324D1` | `WaveSel_StageA1_PresetPath` | `set&0x30 ∈ {0,0x20,0x30}` → ROM tables |
| `0x0324DD` | `LABEL_0324DD` | `WaveSel_StageA1_UserTonePath` | `set&0x30 == 0x10` → RAM user-tone VSEL at `+0x1BA + 11*p` inside a 0x1D6 record |
| `0x0323E5` | `LABEL_0323E5` | `WaveSel_StageA1_SelectTables` | `set&0xC0` → `{A1 index table, VSEL array base, VSEL stride}` from the DB root |
| `0x032469` | `LABEL_032469` | `WaveSel_StageA1_IndexLookup` | `e1 = u16[T + 2*(((set&0xF)<<7)+(fine&0x7F))]`; `VSEL = A + stride*e1` |
| `0x0325F6` | `LABEL_0325F6` | `WaveSel_StageA1_Return` | common exit (`RETD 0004h`) |
| `0x0326B6` | `LABEL_0326B6` | `WaveSel_Cache_VelSplitPtr` | store the resolved VSEL pointer into `tonerec+0x04` |

### 3.3 Stage A2 — (fine, set) → multisample SET descriptor

| addr | current | proposed | purpose |
|---|---|---|---|
| `0x032750` | `LABEL_032750` | `WaveSel_StageA2_FindSetDesc` | `(fine,set)` → SET-descriptor pointer via the A2 index tables |
| `0x032814` | `LABEL_032814` | `WaveSel_StageA2_IndexLookup` | the common `e2`/stride arithmetic |
| `0x032839` | `LABEL_032839` | `WaveSel_StageA2_FromToneRec` | fetch `VSEL[3+2q]/[4+2q]` via `tonerec+0x04`, call Stage A2 |
| `0x0328B5` | `LABEL_0328B5` | `WaveSel_StageA2_FromVelZone` | same, with the VSEL pointer already in `XBC` |
| `0x0328E2` | `LABEL_0328E2` | `WaveSel_Cache_SetDescPtr` | store the SET pointer into `part + 0x76 + 0x25*p + 4*q` |
| `0x032938` | `LABEL_032938` | `WaveSel_Rebuild_PartCaches` | rebuild all 4 VSEL + 16 SET caches of one part after a tone change |

### 3.4 Stage B — SET descriptor + key → the `+0x040` wave word

| addr | current | proposed | purpose |
|---|---|---|---|
| `0x023849` | `LABEL_023849` | `WaveSel_StageB_Build_WaveWord` | walk `ptrC`/`ptrA`/`ptrB`, pick the key zone, emit the `+0x040` word |
| `0x0238F3` | `LABEL_0238F3` | `WaveSel_StageB_Return` | common exit |
| `0x022A32` | `LABEL_022A32` | `WaveSel_KeyTable_Lookup` | `key = (desc+0x06 >> 8) & 0x7F`; return `ptrC[key]` (the fine zone slot) |
| `0x022A3F` | `LABEL_022A3F` | `WaveSel_Emit_ZoneRecord_S15` | stride-15 zone record; pitch class `0x7000`; word B = `rec[+0x0d]` |
| `0x022A61` | `LABEL_022A61` | `WaveSel_Emit_ZoneRecord_S12` | stride-12; class `0x5000`; word B = `rec[+0x0a]` |
| `0x022A83` | `LABEL_022A83` | `WaveSel_Emit_ZoneRecord_S13` | stride-13; class `0x3000`; word B = 0 |
| `0x022AA4` | `LABEL_022AA4` | `WaveSel_Emit_ZoneRecord_S10` | stride-10; class `0x1000`; word B = 0 |
| `0x022AC5` | `LABEL_022AC5` | `WaveSel_Emit_ZoneRecord_S6` | stride-6; class `0x4000`; word B = `rec[+0x04]` |
| `0x022AE7` | `LABEL_022AE7` | `WaveSel_Emit_ZoneRecord_S4` | stride-4; no pitch-class OR; word B = 0 |
| `0x0238F8` | `LABEL_0238F8` | `WaveSel_StageB_Build_WaveWord_Footage` | drawbar/footage variant: `E` from `0x02B154`/`0x02B1E0`/`part+0x102+2*p`, stride 6 only |
| `0x02399D` | `LABEL_02399D` | `WaveSel_StageB_Store_WaveWord` | shared tail: store `+0x040`/word B, apply the `(0x041343)` bit2 class-doubling |

### 3.5 Legacy `+0x440` / streamed-voice slot path

Naming here is deliberately **hedged**: `kn5000-pipe-resolver.md` proves *what the code does not
do* (it is not a wave lookup — its tables are all-`0xFF` at runtime and its output increments once
per note-on, independent of pitch) and infers slot allocation from the fact that the routines
**write** their own tables. The allocator reading is INFERRED-solid, not MEASURED.

| addr | current | proposed | purpose |
|---|---|---|---|
| `0x02177E` | `LABEL_02177E` | `ExtVoice_Alloc_StreamSlot` | **INFERRED** DMA/voice-slot allocator for streamed ("extended synthesis") voices; returns `(keyflag\|0x80)<<8 \| slotnum`, low byte `0xFF` = fail |
| `0x02174C` | `LABEL_02174C` | `ExtVoice_Slot_FallbackConst` | 3-entry constant table `{0x00,0x40,0x80}` selected by `QIZL & 3` |
| `0x0210A2` | `LABEL_0210A2` | `ExtVoice_Slot_ToWaveNumber` | fold a slot byte into the 7-bit "wave number" field |
| `0x024BE3` | `LABEL_024BE3` | `ExtVoice_Build_SlotRegisters` | fills scratch `+0x10`/`+0x12` (registers `+0x440`/`+0x480`); clears them first, so ordinary voices get 0 |
| `0x024CAB` | `LABEL_024CAB` | `ExtVoice_Store_SlotNumber` | stores `(tonerec[+0x1a] & 0xC0) \| slotnum` into scratch `+0x10`; gated `slotnum < 0x80` |

Left as `LABEL_` (bookkeeping protocol not decoded — SPECULATIVE): `0x0217AD`, `0x021846`,
`0x0218AD`, `0x021908`, `0x02129C`, `0x021463`, `0x024DBE`, `0x024E66`.

### 3.6 Already-good names — do not touch

`ToneGen_WriteVoiceParams` (`0x02D101`), `ToneGen_WriteSingleReg` (`0x02D41B`),
`ToneGen_Read_Voice_Data` (`0x03D0C5`), `ToneGen_Calc_Pitch` (`0x03D11F`),
`ToneGen_WriteExtParams_*`, `Voice_ParamFinalize`. Only their **headers** should gain the
register-map / scratch-struct documentation of §5.

---

## 4. ROUTINE HEADERS (repo style, ready to paste)

```
; ----------------------------------------------------------------------------
; ToneDB_Find_PatchRecord - resolve a 16-bit tone selector to a patch record
; Entry: WA = selector low byte  (program 0..0x7F)
;        BC = selector high byte (bank)
; Exit:  XHL = pointer to the patch record (sub-CPU address, 0x05xxxx..0x09xxxx)
; Notes: MEASURED. Preset banks are {0..7, 0x40, 0x41, 0x70}; anything else falls
;        through to the RAM user-tone / kit paths, and finally to patch record #0.
;        Preset path:  C   = byte[ ToneDB_Root->BankTable + hi ]
;                      idx = (C << 7) + lo
;                      k   = u16[ ToneDB_Root->BankTable + 0x80 + 2*idx ]
;                      rec = ToneDB_RelBase + u32[ ToneDB_Root->PatchPtrs + 4*k ]
;        The 629-entry pointer array is at sub 0x051B00, the records at 0x0524D4+.
;        Evidence: notes/kn5000-firmware-sample-tables.md 2.3 (re-derived here).
; ----------------------------------------------------------------------------
ToneDB_Find_PatchRecord:	; 031F71h

; ----------------------------------------------------------------------------
; ToneDB_Find_ToneRecord - tone-selector front end (preset map vs alternate map)
; Entry: WA = selector low byte, BC = selector high byte
; Exit:  XHL = patch-record pointer
; Notes: MEASURED. (0x041343) bit 0 selects the alternate resolver 0x031F16;
;        otherwise ToneDB_Find_PatchRecord. Bit 0 is clear in the shipped config.
; ----------------------------------------------------------------------------
ToneDB_Find_ToneRecord:	; 03206Fh

; ----------------------------------------------------------------------------
; ToneDB_Find_SubToneRecord - follow a patch's sub-tone reference to a named record
; Entry: XWA = patch record, C = sub-tone index i, E = part index
; Exit:  XHL = pointer to the resolved 58-byte named tone record
; Notes: MEASURED. Reads the 2-byte selector {lo,hi} at patch + 0x27 + 2*i and
;        hands it to ToneDB_Resolve_NamedToneRecord.
;        Reached from the note >= 0x78 branch of the note-on dispatcher, where
;        i = note - 0x78 + SET_desc[+0x0b].  For the guitar SETs (SET flags bit1)
;        this lands on patch record #335 "  Special Kit   ", whose +0x27 table
;        selects "Pick Noise 1/3/4" and "Fret Noise" (MEASURED from ROM bytes).
;        INFERRED: that the +0x27 region is a general sub-tone table; for patches
;        that never take this branch those bytes are ordinary patch parameters.
; ----------------------------------------------------------------------------
ToneDB_Find_SubToneRecord:	; 032AE0h

; ----------------------------------------------------------------------------
; ToneDB_Resolve_NamedToneRecord - {lo,hi} -> one of the 610 named tone records
; Entry: WA = lo, BC = hi, DE = sub-index, stack word = part index
; Exit:  XHL = named tone record pointer (58 bytes), or a RAM user-tone slot
; Notes: MEASURED. ROM path (hi bit 5 clear):
;            idx = ((hi & 0x1F) << 7) + (lo & 0x7F)          ; 0..0xFFF
;            e   = u16[ ToneDB_Root->NamedIndex + 2*idx ]    ; 4096-entry table
;            rec = ToneDB_Root->NamedArray + 58*e            ; stride from root+0xEE
;        The named array (610 records at sub 0x084E6F) is the ROM's own list of
;        sample names - see the NamedTone_Record layout block.
;        CORRECTION: the index table at 0x08D8A3 holds 4096 entries (0x2000
;        bytes), not the 1024 quoted in kn5000-firmware-sample-tables.md.
; ----------------------------------------------------------------------------
ToneDB_Resolve_NamedToneRecord:	; 032A08h

; ----------------------------------------------------------------------------
; WaveSel_StageA1_FromPatchBlock - Stage A1 fed from a 0x51-byte patch block
; Entry: A = part index, C = partial index p
; Exit:  XHL = velocity-split (VSEL) record pointer
; Notes: MEASURED. Reads ptr0 = *(Part_State_Array + part*Part_State_Size
;        + 0x6E + p*0x25), then (fine,set) = ptr0[+0x02], ptr0[+0x03].
;        Passes the per-part user-tone index byte (Part_State_Array + part*
;        Part_State_Size + 0x19) as the second stack argument, which Stage A1
;        only consumes on the set&0x30 == 0x10 (user tone) branch.
; ----------------------------------------------------------------------------
WaveSel_StageA1_FromPatchBlock:	; 0325FCh

; ----------------------------------------------------------------------------
; WaveSel_StageA1_FromToneSlot - Stage A1 fed from a 0x15-byte named-record slot
; Entry: XBC = partial slot (named_record + 0x10 + 0x15*p)
;        A = partial index p, E = note, stack word = part index
; Exit:  XHL = velocity-split (VSEL) record pointer
; Notes: MEASURED. (fine,set) = slot[+0x01], slot[+0x02].
;        The 0x15-byte slot is the 0x51-byte patch block shifted down by one
;        byte (the block's constant +0x00 format tag is absent), so its +1/+2
;        are the block's +2/+3.  This is why two prior notes disagreed about
;        which offsets carry FINE and SET - both were right about a different
;        record.  MEASURED CAVEAT: this feeder passes the NOTE in the second
;        stack argument where the patch-block feeder passes a user-tone index;
;        the value is only read on the set&0x30 == 0x10 branch, which no traced
;        caller of this feeder reaches.
; ----------------------------------------------------------------------------
WaveSel_StageA1_FromToneSlot:	; 032682h

; ----------------------------------------------------------------------------
; WaveSel_StageA1_FindVelSplit - (fine, set) -> velocity-split record pointer
; Entry: BC = FINE byte, DE = SET byte, WA = partial index
;        stack: +0 part index, +2 user-tone index (or note, see the feeders)
; Exit:  XHL = pointer to an 11-byte velocity-split (VSEL) record
; Notes: MEASURED. The SET byte is a STRUCTURED address, not a scalar:
;            set & 0x30 = path      (0x10 -> RAM user tone, else ROM tables)
;            set & 0xC0 = family    (picks the index table / array / stride)
;            set & 0x0F = group     (high 4 bits of the composite index)
;            fine & 0x7F           = slot within the group
;        ROM path:  e1   = u16[ A1_index_table + 2*(((set&0xF)<<7) + (fine&0x7F)) ]
;                   VSEL = A1_array_base + 11*e1
;        Validated statically: PIANO block 0 (fine 0x00, set 0x01) -> VSEL
;        0x076ABA, matching the live desc+0x1b capture.
; ----------------------------------------------------------------------------
WaveSel_StageA1_FindVelSplit:	; 03248Bh

; ----------------------------------------------------------------------------
; WaveSel_StageA1_SelectTables - pick the A1 table triple from the SET family
; Entry: DE = set & 0xC0
; Exit:  XHL = A1 index-table rel offset, XIX = VSEL array rel offset,
;        IY = VSEL record stride (11)
; Notes: MEASURED. Families 0x00 and 0xC0 share root+0x0C/+0x18/+0xEA;
;        0x80 -> root+0x10/+0x1C/+0xEA;  0x40 -> root+0x14/+0x20/+0xF0.
;        Absolute addresses in the shipped ROM: 0x075A99 / 0x076299 / 0x08FEBD
;        (index tables), 0x076A99 / 0x08F8A3 (VSEL arrays).
; ----------------------------------------------------------------------------
WaveSel_StageA1_SelectTables:	; 0323E5h

; ----------------------------------------------------------------------------
; WaveSel_StageA1_IndexLookup - the shared A1 index arithmetic
; Entry: WA = fine & 0x7F, BC = set & 0x0F, XHL/XIX/IY = the table triple
; Exit:  XHL = absolute record pointer (ToneDB_RelBase + array + stride*entry)
; Notes: MEASURED. idx = (BC << 7) + WA;  entry = u16[table + 2*idx].
;        The index can reach 2047 while consecutive tables are 1024 entries
;        apart; 20 of 1046 active patch blocks do exceed 1023 (see the naming
;        note 1.10) - either the three tables form one contiguous index space
;        or those blocks are dead data.  UNRESOLVED.
; ----------------------------------------------------------------------------
WaveSel_StageA1_IndexLookup:	; 032469h

; ----------------------------------------------------------------------------
; WaveSel_Cache_VelSplitPtr - resolve and cache a partial's VSEL pointer
; Entry: WA = part index, C = partial index p
; Exit:  none (writes tonerec+0x04)
; Notes: MEASURED. If part_state[+0x00] bit 0 is set the voice is a RAM user
;        tone and the pointer is 0x044FCE + 0x1AA + 11*p; otherwise it is the
;        result of WaveSel_StageA1_FromPatchBlock.  Either way it lands in
;        tonerec+0x04 - which is the "ptr1" that kn5000-pipe-tonerecord.md 6
;        described as an undecoded "key-zone / scaling table with 7F 7F 7F
;        group delimiters".  Those 7F bytes are the three velocity split points
;        of the VSEL record; the note's PIANO example 0x076ABA is VSEL #3.
; ----------------------------------------------------------------------------
WaveSel_Cache_VelSplitPtr:	; 0326B6h

; ----------------------------------------------------------------------------
; WaveSel_StageA2_FindSetDesc - (fine, set) -> multisample SET descriptor
; Entry: A = FINE byte, C = SET byte
; Exit:  XHL = pointer to a 15-byte SET descriptor
; Notes: MEASURED. Same shape as Stage A1 with the A2 tables:
;            family 0x00/0xC0 -> root+0x24 (or +0x9C), array root+0x30
;            family 0x80      -> root+0x28 (or +0xA0), array root+0x34
;            family 0x40      -> root+0x2C (or +0xA4), array root+0x38
;        (0x041343) bit 2 chooses the +0x9C/+0xA0/+0xA4 alternates; MEASURED:
;        both triples hold identical values in this ROM, so the gate is a no-op.
;        All three array pointers equal 0x077914 - one 487-entry SET array.
;        Stride 15 comes from root+0xEC (or root+0xF2 for family 0x40).
; ----------------------------------------------------------------------------
WaveSel_StageA2_FindSetDesc:	; 032750h

; ----------------------------------------------------------------------------
; WaveSel_StageA2_FromVelZone - pick the SET for one velocity zone
; Entry: A = velocity zone q (0..3), XBC = VSEL record
; Exit:  XHL = SET descriptor pointer
; Notes: MEASURED. (fine, set) = VSEL[3 + 2*q], VSEL[4 + 2*q].
; ----------------------------------------------------------------------------
WaveSel_StageA2_FromVelZone:	; 0328B5h

; ----------------------------------------------------------------------------
; WaveSel_Cache_SetDescPtr - cache one (partial, velocity-zone) SET pointer
; Entry: A = part index, C = partial index p, E = velocity zone q
; Exit:  none (writes part_state + 0x76 + 0x25*p + 4*q)
; Notes: MEASURED. The 4x4 cache the note-on path indexes after the velocity
;        split; it is why note-on does no table walking of its own.
; ----------------------------------------------------------------------------
WaveSel_Cache_SetDescPtr:	; 0328E2h

; ----------------------------------------------------------------------------
; WaveSel_Rebuild_PartCaches - rebuild a part's whole selection cache
; Entry: A = part index
; Exit:  none
; Notes: MEASURED. Dispatches on (patch_record[+0x10] & 0xC0), i.e. on the
;        patch record TYPE byte reached through Part_ToneRecPtr:
;          0x00 (types 0x00/0x10/0x20/0x30, the ordinary patches)
;               -> for p in 0..3: cache the VSEL pointer, then for q in 0..3
;                  cache the SET pointer  (4 VSEL + 16 SET pointers)
;          0x40 (type 0x60 = drawbar registrations)
;               -> the 0x02AAE7 / 0x02AB10 drawbar/footage pair instead
;          0x80/0xC0 (type 0x80, e.g. "  Special Kit   ") -> nothing; such
;               records are only ever reached as SUB-TONE donors, never as a
;               part's own tone.
;        Called on every tone change, from five sites.
; ----------------------------------------------------------------------------
WaveSel_Rebuild_PartCaches:	; 032938h

; ----------------------------------------------------------------------------
; WaveSel_StageB_Build_WaveWord - key zone -> the +0x040 wave-select word
; Entry: XWA = voice descriptor (0x47 bytes: the staging array at 0x2942,
;        indexed by partial, or the live voice array at 0x04308E)
; Exit:  (ToneGen_Scratch_WaveSel) = the 16-bit word destined for register +0x040
;        desc+0x0F = the selected zone record; desc+0x01 |= the pitch class
;        WaveSel_ZoneRec_PitchWordB = the record's signed pitch offset (or 0)
; Notes: MEASURED. SETp = desc+0x1F, then
;            ptrA = ToneDB_RelBase + u32[SETp+1]      ; zone remap table
;            ptrB = ToneDB_RelBase + u32[SETp+5]      ; zone record array
;            ptrC = ToneDB_RelBase + u32[ptrA]        ; 128-byte note->slot map
;            key  = (desc+0x06 >> 8) & 0x7F
;            E    = ptrA[4 + ptrC[key]]
;            record = ptrB + stride(SETp[0]) * E ;  word = u16[record]
;        Record stride comes from SETp[0] bits 6/7/5 -> one of six emitters.
;        MEASURED over all 487 descriptors: bits 5 and 6 are never set, so only
;        stride 6 (bit7 set) and stride 4 occur.
;        The emitted word is { class = bits[15:12], entry = bits[11:0] }.  The
;        CHIP reads that class as page = class & 3 and bank = (class >> 2) & 3,
;        with entry indexing that 1 MB page's self-delimiting directory
;        (notes/kn5000-structural-validation.md 0) - the firmware never splits
;        the nibble itself.
; ----------------------------------------------------------------------------
WaveSel_StageB_Build_WaveWord:	; 023849h

; ----------------------------------------------------------------------------
; WaveSel_KeyTable_Lookup - map the folded key to a fine zone slot
; Entry: XWA = ptrC (128-byte note->zone-slot table), BC = desc+0x06
; Exit:  L = zone slot
; Notes: MEASURED. key = (BC & 0x7F00) >> 8, i.e. the high byte of the folded
;        log-pitch, which is a MIDI note number in 1/256-semitone units.
; ----------------------------------------------------------------------------
WaveSel_KeyTable_Lookup:	; 022A32h

; ----------------------------------------------------------------------------
; WaveSel_Emit_ZoneRecord_S6 - stride-6 zone-record emitter
; Entry: XBC = ptrB, DE = zone record index E, XWA = voice descriptor
; Exit:  (ToneGen_Scratch_WaveSel) = record[0]
;        desc+0x0F = record address ; desc+0x01 |= 0x4000
;        WaveSel_ZoneRec_PitchWordB = record[+0x04]
; Notes: MEASURED. Selected when SET flags bit6 = 0 and bit7 = 1 (134 + 9 of the
;        487 descriptors).  Record = [+0..1] the +0x040 word, [+2..3] pitch word
;        A, [+4..5] pitch word B.  The 0x4000 stamped into desc+0x01 is the
;        firmware's PITCH class and is unrelated to the +0x040 class nibble
;        (PIANO uses this emitter yet its +0x040 nibble is 7).
;        Siblings: _S15 (0x022A3F), _S12 (0x022A61), _S13 (0x022A83),
;        _S10 (0x022AA4), _S4 (0x022AE7) - same shape, other strides.
; ----------------------------------------------------------------------------
WaveSel_Emit_ZoneRecord_S6:	; 022AC5h

; ----------------------------------------------------------------------------
; WaveSel_StageB_Build_WaveWord_Footage - drawbar/footage variant of Stage B
; Entry: XWA = voice descriptor
; Exit:  as WaveSel_StageB_Build_WaveWord (always stride 6, class 0x4000)
; Notes: MEASURED. Instead of the key table it derives E from the partial index
;        desc+0x03:  p == 0 -> 0x02B154, p < 3 -> 0x02B1E0, else
;        u16[ part_state + 0x102 + 2*p ]; each result passes through 0x02B2C2.
;        Shares the tail WaveSel_StageB_Store_WaveWord with the main builder,
;        including the (0x041343) bit 2 class-doubling.  MEASURED live:
;        0x041343 = 0x0208 there, so bit 2 is clear and no doubling happens.
; ----------------------------------------------------------------------------
WaveSel_StageB_Build_WaveWord_Footage:	; 0238F8h

; ----------------------------------------------------------------------------
; ExtVoice_Alloc_StreamSlot - allocate a streaming/DMA voice slot (INFERRED)
; Entry: A = part index (must be < 0x1A), C = desc+0x00 (must be < 0x40),
;        E = keyflag / bank-mode byte (masked to 0x3F on entry)
; Exit:  HL = ((keyflag | 0x80) << 8) | slot number, or low byte 0xFF on failure
; Notes: This is NOT a wave-number resolver, despite its historical name.
;        MEASURED (notes/kn5000-pipe-resolver.md): its wave-mapping columns are
;        0xFF for all 64 tones and all 26 valid rows at runtime, so the lookup
;        always degenerates to the 3-entry fallback table; and the value the
;        caller ships to register +0x440 increments by exactly 1 per note-on and
;        is INDEPENDENT of pitch (C3/C4/C5 -> 0x40/0x41/0x42).
;        INFERRED: the tables are voice/DMA slot occupancy maps - decisive tell,
;        the helpers 0x02129C and 0x021463 WRITE them, which a ROM lookup never
;        does; ExtVoice_SlotPool_Entries has a next/prev/.../slot free-list shape
;        with slot = 0xFF meaning free.
;        CORRECTION: A is the PART index (desc+0x04 is written with the part
;        index by both descriptor builders), which is what the A < 0x1A gate
;        bounds - kn5000-pipe-resolver.md called it a note and then a key-zone.
;        Ordinary PCM voices never reach here: their caller gates on
;        tonerec[+0x1a] != 0 or part_state[+0x0a] bit 15, both false, so
;        registers +0x440/+0x480 keep their cleared value 0.
; ----------------------------------------------------------------------------
ExtVoice_Alloc_StreamSlot:	; 02177Eh

; ----------------------------------------------------------------------------
; ExtVoice_Build_SlotRegisters - fill scratch +0x10/+0x12 (regs +0x440/+0x480)
; Entry: XWA = voice descriptor
; Exit:  none (writes ToneGen_VoiceParam_Scratch +0x10 / +0x12)
; Notes: MEASURED. Clears both words first, so the "no extended synthesis" case
;        is 0 by construction.  Three branches:
;          tonerec[+0x1a] != 0                        -> allocate + 0x02DB16
;          tonerec[+0x1a] == 0, part+0x0a bit15 set   -> 0x024DBE / 0x024E66
;          otherwise                                  -> nothing written
; ----------------------------------------------------------------------------
ExtVoice_Build_SlotRegisters:	; 024BE3h

; ----------------------------------------------------------------------------
; ExtVoice_Store_SlotNumber - store the allocated slot into the +0x440 scratch
; Entry: stack local = slot number, XWA = voice descriptor
; Exit:  scratch +0x10 = (tonerec[+0x1a] & 0xC0) | slot   (only if slot < 0x80)
; Notes: MEASURED. Also indexes a 0x1B-byte per-slot bookkeeping record at
;        0x04424E + 0x1B*slot and stores the voice's velocity at its +0x06.
; ----------------------------------------------------------------------------
ExtVoice_Store_SlotNumber:	; 024CABh
```

---

## 5. DATA-STRUCTURE COMMENT BLOCKS

These describe records that live in the **transferred Table-Data image** (main `0x830000..0x8A0000`
copied verbatim to sub `0x050000..0x0A0000` at boot), so they are `EQU`-only in the disassembly —
no bytes are emitted. Sub address `S` ↔ main address `S + 0x7E0000` ↔ `table_data` region offset
`S - 0x020000`.

```
; ----------------------------------------------------------------------------
; ToneDB_Root - root of the resident tone database (sub 0x050000)
; Set once, statically, by DSP_System_Init_Continue:
;   (ToneDB_RelBase) = (ToneDB_RootPtr) = 0x050000 ; (0x045318) = 0x0A0000
;   (0x04531C) = (0x045320) = 0x7800       ; RAM user-tone area
; Every pointer inside the DB is a 32-bit offset relative to (ToneDB_RelBase).
;   +0x04  -> bank byte-table (0x050100); u16 program map at +0x80 (0x050180)
;   +0x08  -> patch pointer array (0x051B00), 629 x rel32
;   +0x0C  -> A1 index table, families 0x00/0xC0   (0x075A99, 1024 x u16)
;   +0x10  -> A1 index table, family 0x80          (0x076299, 1024 x u16)
;   +0x14  -> A1 index table, family 0x40          (0x08FEBD, 1024 x u16)
;   +0x18  -> VSEL array, families 0x00/0xC0/0x80  (0x076A99, 337 x 11)
;   +0x1C  -> VSEL array, family 0x80              (0x076A99, same array)
;   +0x20  -> VSEL array, family 0x40              (0x08F8A3, 142 x 11)
;   +0x24/+0x9C -> A2 index table, fam 0x00/0xC0   (0x07959D, 1024 x u16)
;   +0x28/+0xA0 -> A2 index table, fam 0x80        (0x079D9D, 1024 x u16)
;   +0x2C/+0xA4 -> A2 index table, fam 0x40        (0x07A59D, 1024 x u16)
;   +0x30/+0x34/+0x38 -> SET descriptor array      (0x077914, 487 x 15)
;   +0x74  -> named-tone index table               (0x08D8A3, 4096 x u16)
;   +0x78  -> named-tone record array              (0x084E6F, 610 x 58)
;   +0xEA/+0xF0 = 11   VSEL record stride
;   +0xEC/+0xF2 = 15   SET descriptor stride
;   +0xEE       = 58   named tone record stride
; Array bounds are proven by (gap to the next structure) / stride, and each
; equals (max index in its own index table) + 1.
; ----------------------------------------------------------------------------

; ----------------------------------------------------------------------------
; Patch_Record - one instrument ("sound"), 629 of them at sub 0x0524D4
;   layout: NAME(0x10) ++ HEADER(0x56) ++ N x Patch_PartialBlock(0x51)
;   +0x00 .. +0x0F   16-byte ASCII name, space-centred (the name the UI shows)
;   +0x10            record/format type: 0x00,0x10,0x20,0x30,0x60,0x80
;   +0x11            partial-present map, TWO BITS PER PARTIAL:
;                      partial i present <=> bit (2*i) set   (01,05,11,15,45,51,55)
;   +0x12 .. +0x26   patch parameters (effect sends, level/pan matrices, EQ)
;   +0x27 .. +0x56   read by ToneDB_Find_SubToneRecord as 24 x 2-byte {lo,hi}
;                    sub-tone selectors (INFERRED as a general field; MEASURED
;                    for patch #335 "  Special Kit   ", where they select
;                    "Pick Noise 1/3/4" and "Fret Noise")
;   +0x57 .. +0x65   further patch parameters
;   +0x66 + 0x51*b   partial block b
; The pointer array at 0x051B00 holds rel32 offsets; a tonerec's ptr[0] points
; at a BLOCK (record + 0x66 + 0x51*b), not at the record.
; ----------------------------------------------------------------------------

; ----------------------------------------------------------------------------
; Patch_PartialBlock - one partial of a patch record, 0x51 bytes
;   +0x00  format tag, 0x00 for all 1046 active blocks in this ROM
;   +0x01  partial flags {00,18,40,58,7F,...}
;   +0x02  FINE  - low index into the Stage A1 composite index (masked 0x7F)
;   +0x03  SET   - {family 0xC0, path 0x30, group 0x0F}
;   +0x04  coarse transpose, signed semitones (added as sext<<8)
;   +0x05  fine transpose, signed (added as sext*2, i.e. 1/128 semitone)
;   +0x06  bits 0..2 = pitch key-follow shift (7 = fixed pitch)
;   +0x07..+0x50  envelope / level / filter / keyscale parameters
; MEASURED: over the 1046 mask-active blocks the SET byte distributes as
;   family 0x00 x892, 0x40 x51, 0x80 x101, 0xC0 x2 ;
;   path   0x00 x977, 0x10 x20 (user tone), 0x20 x39, 0x30 x10.
; ----------------------------------------------------------------------------

; ----------------------------------------------------------------------------
; VelSplit_Record - velocity switch over four multisample SETs, 11 bytes
;   337 records at sub 0x076A99 (families 0x00/0x80/0xC0)
;   142 records at sub 0x08F8A3 (family 0x40)
;   +0x00  velocity split point 0     ] q = 0 if vel <= [0]
;   +0x01  velocity split point 1     ]     1 if vel <= [1]
;   +0x02  velocity split point 2     ]     2 if vel <= [2] else 3
;   +0x03 + 2*q  FINE for velocity zone q
;   +0x04 + 2*q  SET  for velocity zone q
; The q selector is ExtVoice-independent and lives in 0x022824 / 0x022844
; (byte-identical duplicates).  0x7F 0x7F 0x7F in the first three bytes means
; "no velocity switching" - which is what the "7F 7F 7F group delimiters" of
; kn5000-pipe-tonerecord.md 6 actually were.
; ----------------------------------------------------------------------------

; ----------------------------------------------------------------------------
; MultiSet_Descriptor - one multisample SET header, 15 bytes
;   487 descriptors at sub 0x077914
;   +0x00  format flags
;            bit7 -> zone-record stride 6, clear -> stride 4
;            bits 5/6 select the 15/12/13/10-byte emitters - NEVER SET in this ROM
;            bit1 -> +0x0B/+0x0C are a SUB-TONE reference, not root/base pitch
;                    (13 descriptors, all guitar; see the naming note 1.3)
;            bit0 -> amplitude ceiling 0xFE instead of 0xFF (read in the EG path)
;            bit3 -> 10 descriptors set it; consumer not identified
;          census: 0x00 x318, 0x01 x3, 0x02 x13, 0x08 x10, 0x80 x134, 0x81 x9
;   +0x01  rel32 -> ptrA, the zone-slot remap table.  ptrA[0..3] is itself a
;                   rel32 -> ptrC (the 128-byte note -> zone-slot key table);
;                   ptrA[4 + slot] = the zone record index E
;   +0x05  rel32 -> ptrB, the zone-record array (stride from bit7)
;   +0x09  key range minimum (MIDI note) - lower bound of the octave fold
;   +0x0A  key range maximum (MIDI note) - upper bound of the octave fold
;   +0x0B  root key ... OR, when bit1 is set, the base index of the sub-tone
;          table inside the referenced patch record (observed 0x00/0x08/0x10)
;   +0x0C  base pitch, 1/256 semitone (0x4280 = note 0x42 + 0x80) ... OR, when
;          bit1 is set, a 16-bit {lo,hi} tone selector (all 13 hold 0x417F)
;   +0x0E  0x00
; ----------------------------------------------------------------------------

; ----------------------------------------------------------------------------
; MultiSet_ZoneRecord - one key zone of a multisample SET
;   record = ptrB + stride * E ;  E = ptrA[4 + ptrC[key]]
;   stride 6 : [0..1] the +0x040 wave word, [2..3] pitch word A (s16),
;              [4..5] pitch word B (s16, added into the final pitch)
;   stride 4 : [0..1] the +0x040 wave word, [2..3] pitch word A (s16)
;   +0x040 word = { class = bits[15:12] , entry = bits[11:0] }
;     class 0..7 observed; entry needs all 12 bits (class 3 has 179 entries
;     above 0xFF).  1444 distinct (class, entry) pairs exist across all 487
;     descriptors; each class is a 95-100% dense 0-based range, i.e. entry is
;     a plain directory index (notes/kn5000-firmware-sample-tables.md 8).
; ----------------------------------------------------------------------------

; ----------------------------------------------------------------------------
; NamedTone_Record - the ROM's own named sample list, 58 bytes x 610
;   at sub 0x084E6F, indexed through the 4096-entry table at 0x08D8A3
;   +0x00 .. +0x0C   13-byte ASCII name  ("Rock Bass Drm", "Fret Noise", ...)
;   +0x0D            partial-present mask (AND-ed with the caller's 1/2/4/8)
;   +0x0E, +0x0F     unclassified
;   +0x10 + 0x15*p   partial slot p (p = 0,1) - see NamedTone_PartialSlot
; 0x0D + 1 + 2 + 2*0x15 = 0x3A = 58 exactly.
; This table is where the ROM says, by name, what each sample is: every record
; resolves through Stage A1/A2/B to exactly one (class, entry) pair.
; ----------------------------------------------------------------------------

; ----------------------------------------------------------------------------
; NamedTone_PartialSlot - one partial of a named tone record, 0x15 bytes
;   +0x00  partial flags (0x40 / 0x48 observed)
;   +0x01  FINE   (== Patch_PartialBlock +0x02)
;   +0x02  SET    (== Patch_PartialBlock +0x03)
;   +0x03  coarse transpose, signed semitones (sext<<8)
;   +0x04  fine transpose, signed
;   +0x05..+0x14  envelope / level / filter parameters
; Layout == Patch_PartialBlock shifted down one byte (no format tag), truncated
; to 0x15 bytes.  MEASURED against records #0..#5 of the array.
; ----------------------------------------------------------------------------

; ----------------------------------------------------------------------------
; ToneGen_VoiceParam_Scratch - the 44-byte register image ToneGen_WriteVoiceParams
; bursts to one voice.  Struct offset -> tone-generator register offset:
;   +0x02 -> +0x040   wave select  { class[15:12], entry[11:0] }  <-- Stage B
;   +0x04 -> +0x080   gate/control; written with bit15 SET to open the burst and
;                     re-written with bit15 CLEAR as the final write
;   +0x06 -> +0x0C0   level / keyscale        +0x18 -> +0x800
;   +0x08 -> +0x100   TVF cutoff              +0x1A -> +0x840
;   +0x0A -> +0x140                           +0x1C -> +0x880
;   +0x0C -> +0x180                           +0x1E -> +0x8C0
;   +0x0E -> +0x400   absolute log pitch      +0x20 -> +0x900
;   +0x10 -> +0x440   DMA/voice slot          +0x22 -> +0x940
;   +0x12 -> +0x480   DMA/voice slot          +0x24 -> +0x980
;   +0x14 -> +0x4C0                           +0x26 -> +0x9C0
;   +0x16 -> +0x500                           +0x28 -> +0xA00
;                                             +0x2A -> +0xA40
; Every write is: RES 7,(P6) / LD (100000h),reg / NOP / SET 7,(P6) /
; LD (100002h),data - P6.7 is the A23 chip-select for the tone generator.
; ----------------------------------------------------------------------------
```

---

## 6. EQU SYMBOL PROPOSALS

To be inserted with the existing `EQU` block at the top of the file (**before** first use, so ASL
resolves them in pass 1 and picks identical operand widths). Verified byte-neutral in §0.

```
; ---- sub-CPU DRAM: wave/sample selection state -----------------------------
Part_State_Array		EQU 041368h	; per-part state, stride Part_State_Size
Part_State_Size			EQU 011Fh
Part_ToneRecPtr			EQU 04136Eh	; +0x06 in the part struct: patch-record ptr
Part_UserToneIndex		EQU 041381h	; +0x19 in the part struct
ToneGen_Config_Word		EQU 041343h	; bit0 alt tone map, bit1 vel curve, bit2 alt A2 tables
ToneDB_RelBase			EQU 045310h	; = 0x050000, base for every rel32 in the DB
ToneDB_RootPtr			EQU 045314h	; = 0x050000, the DB root struct
ToneDB_RamBankB			EQU 045318h	; = 0x0A0000
ToneDB_RamBankA			EQU 04531Ch	; = 0x007800, RAM user-tone area
Voice_Desc_Staging		EQU 02942h	; 4 staging descriptors, indexed by PARTIAL 0..3
Voice_Desc_Array		EQU 04308Eh	; the live per-VOICE descriptor array (INFERRED)
Voice_Desc_Size			EQU 047h
WaveSel_ZoneRec_PitchWordB	EQU 0293Eh	; signed pitch offset from the zone record
ToneGen_VoiceParam_Scratch	EQU 0451CCh	; 44-byte register image (see 5)
ToneGen_Scratch_WaveSel		EQU 0451CEh	; scratch +0x02 -> register +0x040
ToneGen_Scratch_Gate		EQU 0451D0h	; scratch +0x04 -> register +0x080
ToneGen_Scratch_ExtSlot0	EQU 0451DCh	; scratch +0x10 -> register +0x440
ToneGen_Scratch_ExtSlot1	EQU 0451DEh	; scratch +0x12 -> register +0x480

; ---- sub-CPU DRAM: streamed-voice slot bookkeeping (ExtVoice) --------------
ExtVoice_SlotMap_ByNote		EQU 01E4Dh	; 27 rows x 27 bytes  (0x1E4D..0x2125)
ExtVoice_Slot_FallbackTable	EQU 0210Bh	; {0x00,0x40,0x80} at +0,+4,+8
ExtVoice_SlotPool_Entries	EQU 02126h	; 192 x 5: {next, prev, 0x1A, 0x00, slot}
ExtVoice_ToneSlotMap		EQU 024E6h	; 64 rows x 12 bytes (cols 8..11 = wave map)

; ---- sub-CPU program image: static maps (0x00F000..0x02F000 payload) -------
ExtVoice_KeyFlag_SubSlot_Map	EQU 0F48Ch	; 32 bytes: keyflag&0x1F -> sub-slot 0..3
ExtVoice_KeyFlag_Variant_Map	EQU 0F4ACh	; 32 bytes: keyflag -> variant 0..0x0E

; ---- resident tone database (transferred Table-Data image) -----------------
ToneDB_Base			EQU 050000h	; sub twin of main 0x830000
ToneDB_BankTable		EQU 050100h	; bank byte -> sub-index (0..10)
ToneDB_ProgramMap		EQU 050180h	; u16[(sub_index<<7) + program] -> patch #
ToneDB_PatchPtrArray		EQU 051B00h	; 629 x rel32
ToneDB_PatchRecords		EQU 0524D4h	; 629 records, 0x66 + 0x51*N bytes
ToneDB_A1Index_Fam00		EQU 075A99h	; 1024 x u16
ToneDB_A1Index_Fam80		EQU 076299h	; 1024 x u16
ToneDB_A1Index_Fam40		EQU 08FEBDh	; 1024 x u16
ToneDB_VelSplit_Records		EQU 076A99h	; 337 x 11
ToneDB_VelSplit_Records_Fam40	EQU 08F8A3h	; 142 x 11
ToneDB_MultiSet_Descriptors	EQU 077914h	; 487 x 15
ToneDB_A2Index_Fam00		EQU 07959Dh	; 1024 x u16
ToneDB_A2Index_Fam80		EQU 079D9Dh	; 1024 x u16
ToneDB_A2Index_Fam40		EQU 07A59Dh	; 1024 x u16
ToneDB_NamedTone_Index		EQU 08D8A3h	; 4096 x u16
ToneDB_NamedTone_Records	EQU 084E6Fh	; 610 x 58
ToneDB_DefaultPartialBlock	EQU 075A48h	; the stand-alone 0x51 block (DRUM KITS ptr0)

; ---- record field offsets --------------------------------------------------
PATCH_NAME			EQU 000h	; 16 ASCII bytes
PATCH_TYPE			EQU 010h
PATCH_PARTIAL_MAP		EQU 011h	; 2 bits per partial
PATCH_SUBTONE_TABLE		EQU 027h	; 2-byte {lo,hi} entries
PATCH_BLOCK0			EQU 066h
PATCH_BLOCK_SIZE		EQU 051h
PBLK_FINE			EQU 002h
PBLK_SET			EQU 003h
PBLK_COARSE_TRANSPOSE		EQU 004h
PBLK_FINE_TRANSPOSE		EQU 005h
PBLK_PITCH_FOLLOW		EQU 006h	; bits 0..2
VSEL_SPLIT0			EQU 000h
VSEL_SPLIT1			EQU 001h
VSEL_SPLIT2			EQU 002h
VSEL_ZONE0_FINE			EQU 003h	; zone q: +3+2q fine, +4+2q set
VSEL_RECORD_SIZE		EQU 00Bh
MSET_FLAGS			EQU 000h
MSET_PTRA			EQU 001h	; rel32 -> zone remap table
MSET_PTRB			EQU 005h	; rel32 -> zone record array
MSET_KEY_MIN			EQU 009h
MSET_KEY_MAX			EQU 00Ah
MSET_ROOT_KEY			EQU 00Bh
MSET_BASE_PITCH			EQU 00Ch
MSET_RECORD_SIZE		EQU 00Fh
NTONE_NAME			EQU 000h	; 13 ASCII bytes
NTONE_PARTIAL_MASK		EQU 00Dh
NTONE_SLOT0			EQU 010h
NTONE_SLOT_SIZE			EQU 015h
NSLOT_FINE			EQU 001h
NSLOT_SET			EQU 002h
NSLOT_COARSE_TRANSPOSE		EQU 003h
NSLOT_FINE_TRANSPOSE		EQU 004h
NTONE_RECORD_SIZE		EQU 03Ah
; ---- voice descriptor, 0x47 bytes (both arrays share this layout) ----------
VD_TONE				EQU 000h
VD_FLAGS			EQU 001h	; word: bits12..14 pitch class (Stage-B OR),
					;   bit10 computed-cutoff gate, bits6..7 velocity zone,
					;   low bits a voice-type code (0x12 named / 0x04 patch)
VD_PARTIAL			EQU 003h
VD_PART				EQU 004h
VD_NOTE				EQU 005h	; note | 0x80
VD_ZONE_KEY			EQU 006h	; folded log-pitch; high byte indexes ptrC
VD_PITCH			EQU 008h
VD_VELOCITY			EQU 00Ch
VD_ZONE_RECORD			EQU 00Fh	; set by every Stage-B emitter
VD_TONE_RECORD			EQU 013h
VD_PARTIAL_BLOCK		EQU 017h
VD_VELSPLIT			EQU 01Bh
VD_MULTISET			EQU 01Fh
VD_PART_STATE			EQU 023h
VD_TONEREC			EQU 027h
; ---- tonerec (Part_State_Array + part*Part_State_Size + 0x6E + 0x25*p) -----
TREC_PARTIAL_BLOCK_PTR		EQU 000h	; -> Patch_PartialBlock  (ptr[0])
TREC_VELSPLIT_PTR		EQU 004h	; -> VelSplit_Record     (ptr[1])
TREC_LEGACY_BANK		EQU 01Ah	; != 0 -> extended-synthesis path
TREC_ZONE_SIZE			EQU 025h
PART_SETCACHE			EQU 076h	; +0x76 + 0x25*p + 4*q -> MultiSet_Descriptor
```

`Part_ToneRecPtr` / `Part_UserToneIndex` are given as absolute EQUs because the code always
addresses them as `0x04136E + part*0x11F` / `0x041381 + part*0x11F`, i.e. as independent arrays,
never as `Part_State_Array + 0x06`.

---

## 7. The LLVM tree's conflicting names (for reconciliation, not for use)

`v142/subcpu/kn5000_subprogram_v142.s` currently calls these routines by names that describe
something else entirely. Recorded so the mismatch is visible when the trees are merged:

| addr | LLVM tree name | what it actually is |
|---|---|---|
| `0x031F71` | `DSP_LookupVoiceBuffer` | patch-record lookup |
| `0x032002` | `VoiceBuf_TypeCheck_0x15` | user-tone bank B path |
| `0x0323E5` | `VoiceBufIdx_Decode` | Stage A1 table selection |
| `0x03248B` | `SlotParam_WriteDispatch` | Stage A1 velocity-split lookup |
| `0x022A3F..0x022AE7` | `SlotParam_WriteType0..7` | the six zone-record emitters |

---

## 8. Open items (deliberately NOT named)

1. **The drum-kit per-key map.** `0x075A48` is proven *not* to be a patch-array record (§1.8);
   the mechanism that turns a drum key into a named tone record is still unlocated. The
   `ToneDB_Find_SubToneRecord` path decoded in §1.3 is the *guitar noise* mechanism, and its
   index range (`note - 0x78 + root`) cannot cover a 128-key drum map.
2. **SET flags bit 3** (10 descriptors) — no consumer identified.
3. **`0x0217AD` / `0x021846` / `0x0218AD` / `0x021908` / `0x02129C` / `0x021463`** — the
   slot alloc/free protocol; left as `LABEL_`.
4. **A1 index overflow** (§1.10) — 20 of 1046 blocks index past their table; the "one contiguous
   index space" reading is plausible but not proven.
5. **Patch header `+0x12..+0x26` and `+0x57..+0x65`** — untouched; effect sends / level / EQ.
6. **What the chip does with `(class, entry)`** — outside this subsystem by construction; the
   firmware never emits a PCM address.
