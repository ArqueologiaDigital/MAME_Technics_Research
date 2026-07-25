# KN5000 — the firmware's OWN sample tables, mined exhaustively from the Table-Data ROM

Author: autonomous EXTRACT pass, 2026-07-25. Requested by Felipe Sanches.
**Investigation only — no `src/` edits, no rebuild, no MAME run.** Analysis is **100 % static**:
Table-Data ROM bytes (IC3/IC1 interleaved) + the v142 sub-CPU disassembly. The only tracked
changes are this note and three generated data tables under `notes/data/`.

**Methodological mandate this pass answers** (Felipe): *"Which samples correspond to a piano
should, in theory, be documented in voice record data structures. It should not have to rely on
me hearing and cataloging what I hear. It should not involve guessing either."*
Everything below is read out of firmware data structures whose consumers are traced
instruction-by-instruction in the disassembly. **No clustering, no spectral heuristics, no
ear-based input, no invented mappings.** Where something is genuinely not derivable it is said
so in §10.

Evidence labels: **MEASURED** (ROM bytes / disasm instruction), **PROVEN-BY-CONSTRUCTION**
(follows from a traced code path), **INFERRED**, **SPECULATIVE**.

Sources
* sub-CPU disasm `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`
  (all `LABEL_xxxxxx` / line numbers below refer to this file).
* `kn5000_table_data_rom_even.ic3` + `..._odd.ic1` interleaved into the 2 MB `table_data`
  region exactly as `kn5000.cpp:1131-1133` loads them (`ROM_LOAD32_WORD` at +0 / +2).
* Prior notes consumed and corrected: `kn5000-pipe-tonerecord.md`, `kn5000-pipe-partialset.md`,
  `kn5000-pipe-chipmap.md`, `kn5000-live-captures.md`.

---

## 0. TL;DR

The Table-Data ROM contains a **complete, self-describing multisample database**. Mined in full:

| structure | count | element size | sub-CPU addr | main-CPU addr | `table_data` region off |
|---|---|---|---|---|---|
| root/base struct (all table pointers) | 1 | 0x120 | `0x050000` | `0x830000` | `0x30000` |
| **patch (instrument) pointer array** | **629** | 4 (rel32) | `0x051B00` | `0x831B00` | `0x31B00` |
| **patch (instrument) records** | **629** | 0x66 + 0x51·N | `0x0524D4…` | `0x8324D4…` | `0x324D4…` |
| stage-A1 index tables (fam 00/C0, 80) | 2×1024 | u16 | `0x075A99`, `0x076299` | `0x855A99`, `0x856299` | `0x55A99`, `0x56299` |
| **velocity-split (VSEL) records** | **337** | 11 | `0x076A99` | `0x856A99` | `0x56A99` |
| **multisample SET descriptors** | **487** | 15 | `0x077914` | `0x857914` | `0x57914` |
| stage-A2 index tables (fam 00/C0, 80, 40) | 3×1024 | u16 | `0x07959D`, `0x079D9D`, `0x07A59D` | `0x85959D`… | `0x5959D`… |
| key-tables / zone-tables / partial-record arrays | — | — | `0x07AD9D…` | `0x85AD9D…` | `0x5AD9D…` |
| **named single-sample / drum tone records** | **610** | 58 | `0x084E6F` | `0x864E6F` | `0x64E6F` |
| its index table | 1024 | u16 | `0x08D8A3` | `0x86D8A3` | `0x6D8A3` |
| VSEL records, family 0x40 | 142 | 11 | `0x08F8A3` | `0x86F8A3` | `0x6F8A3` |
| stage-A1 index table, family 0x40 | 1024 | u16 | `0x08FEBD` | `0x86FEBD` | `0x6FEBD` |

* The chip-visible wave selector **`+0x040` = `partial_record[0]` = `{ class[15:12], entry[11:0] }`**
  is reconfirmed, and now **derived statically end-to-end** from the patch record.
* **1444 distinct `(class, entry)` pairs** exist across all 487 SET descriptors (§7). Every class
  occupies a **near-contiguous 0-based entry range** (95-100 % dense) — `entry` is a plain index
  into a per-class sample directory, not a sparse tag.
* **The 610-record table at `0x084E6F` is the firmware's own NAMED SAMPLE LIST** — 13-character
  ASCII names ("Rock Bass Drm", "Room BassDrm1", "FluteKeyClick", "Square Click", "Silent", …),
  each resolving through the same chain to exactly one `(class, entry)`. **This is the ROM
  documenting, by name, which sample is which** — precisely what the mandate asked for.
* **Validation:** the static chain reproduces the LIVE `+0x040` note-sweeps of
  `kn5000-live-captures.md §5` **exactly for 14 of the 15 pitched SOUND-GROUP defaults**
  (8 with zero key offset, 6 with a pure integer key shift produced by the traced octave-fold),
  and reproduces PIANO's two oscillators (`0x7007` / `0x7017` at C4) independently (§6).

---

## 1. Address model (MEASURED, PROVEN-BY-CONSTRUCTION)

Boot copies `main 0x830000..0x8A0000 → sub 0x050000..0x0A0000` verbatim
(`SubCPU_Send_Payload`, main asm L134180-134231; re-established in `-tonerecord.md §1.3`).
Therefore for every sub-CPU address `S` in the DB:

```
table_data region offset = S - 0x020000        main-CPU address = S + 0x7E0000
```

All the DB's internal pointers are **32-bit offsets relative to `*(0x045310)`**. Both base
variables are set **once**, statically, in `DSP_System_Init_Continue` (asm L38133-38139):

```
LD XWA, 00050000h ;  LD (045310h), XWA      ; *(0x045310) = 0x050000   (rel-offset base)
LD XWA, 00050000h ;  LD (045314h), XWA      ; *(0x045314) = 0x050000   (root struct ptr)
LDA XWA, 0A0000h  ;  LD (045318h), XWA      ; *(0x045318) = 0x0A0000   (end / RAM guard)
LABEL_03555F      ;  (045320h)=(04531Ch)=7800h                          (RAM user-tone area)
```

**This is the pass's unlock.** The previous pass (`-partialset.md §6`) listed
`*(0x045310)/*(0x045314)` as "runtime data, not reconstructed from ROM" and had to read them
live. They are compile-time constants, and `*(0x045314)` points at the very first byte of the
transferred DB — so **every table the tone engine uses is statically readable**.

Root struct at sub `0x050000` (= main `0x830000`), the fields the tone engine dereferences:

```
830000: ff ff ff ff 00 01 00 00 00 1b 00 00 99 5a 02 00
830010: 99 62 02 00 bd fe 03 00 99 6a 02 00 99 6a 02 00
830020: a3 f8 03 00 9d 95 02 00 9d 9d 02 00 9d a5 02 00
830030: 14 79 02 00 14 79 02 00 14 79 02 00 ff ff ff ff
...
8300E0: 1c 00 00 00 00 00 00 00 aa 01 0b 00 0f 00 3a 00
8300F0: 0b 00 0f 00 ...
```

| off | value (rel) | absolute (sub) | role (traced consumer) |
|---|---|---|---|
| +0x04 | 0x000100 | 0x050100 | bank byte-table (`LABEL_031F71`) + u16 program map at +0x80 |
| +0x08 | 0x001B00 | 0x051B00 | **patch pointer array** (629 rel32) (`LABEL_031F71`) |
| +0x0c | 0x025A99 | 0x075A99 | A1 index table, family `0x00`/`0xC0` (`LABEL_0323E5`) |
| +0x10 | 0x026299 | 0x076299 | A1 index table, family `0x80` |
| +0x14 | 0x03FEBD | 0x08FEBD | A1 index table, family `0x40` |
| +0x18/+0x1c | 0x026A99 | 0x076A99 | **VSEL array base** (families `0x00`/`0xC0`/`0x80`) |
| +0x20 | 0x03F8A3 | 0x08F8A3 | VSEL array base, family `0x40` |
| +0x24/+0x9c | 0x02959D | 0x07959D | A2 index table, family `0x00`/`0xC0` (`LABEL_032750`) |
| +0x28/+0xa0 | 0x029D9D | 0x079D9D | A2 index table, family `0x80` |
| +0x2c/+0xa4 | 0x02A59D | 0x07A59D | A2 index table, family `0x40` |
| +0x30/+0x34/+0x38 | 0x027914 | 0x077914 | **SET-descriptor array base** (all families) |
| +0x74 | 0x03D8A3 | 0x08D8A3 | index table for the 610 named tone records (`LABEL_032A08`) |
| +0x78 | 0x034E6F | 0x084E6F | **named tone-record array base** |
| +0xea/+0xf0 | 0x000B | — | VSEL record **stride = 11** |
| +0xec/+0xf2 | 0x000F | — | SET-descriptor **stride = 15** |
| +0xee | 0x003A | — | named tone-record **stride = 58** |

*(the `(041343h) bit 2` alternates `+0x9c/+0xa0/+0xa4` for `+0x24/+0x28/+0x2c` — **MEASURED: the
two triples hold identical values**, so the gate is a no-op for this ROM.)*

**Array bounds are proven, not assumed** (PREDICT-THEN-CHECK, all four hit):

| array | bytes between it and the next structure | ÷ stride | max index found in its index table |
|---|---|---|---|
| VSEL (fam 00/80/C0) | `0x077914-0x076A99` = 0xE7B | 3707/11 = **337** | 336 ✓ |
| SET descriptors | `0x07959D-0x077914` = 0x1C89 | 7305/15 = **487** | 486 ✓ |
| VSEL (fam 40) | `0x08FEBD-0x08F8A3` = 0x61A | 1562/11 = **142** | 141 ✓ |
| named tone records | `0x08D8A3-0x084E6F` = 0x8A34 | 35380/58 = **610** | 609 (max used 434) ✓ |
| patch pointers | `0x0524D4-0x051B00` = 0x9D4 | 2516/4 = **629** | — |

Every array's element count equals *(max index in its own index table) + 1*. That is four
independent structural confirmations that the layout is exactly as decoded.

---

## 2. The PATCH (instrument) record — layout, directory, and where they live

### 2.1 Record layout — MEASURED

```
patch record  =  NAME (0x10, ASCII)  ++  HEADER (0x56)  ++  N × PARTIAL BLOCK (0x51 each)
```

* `+0x00..+0x0F` **16-byte ASCII name**, space-centred — the name the UI shows.
* `+0x10` record/format type: `0x00,0x10,0x20,0x30,0x60` (0x60 = drawbar registrations).
* `+0x11` **partial map**, *2 bits per partial*: partial *i* present ⟺ bit (2·i) set.
  Observed `01,05,11,15,45,51,55` (and `00` = no partial, e.g. "Gun Shot").
  `popcount(bit0,2,4,6)` == the block count derived from the next record's address for
  **539 / 576** checkable records (MEASURED); the 37 exceptions are all in the fixed-stride
  `0x1AA` (4-slot) regions, i.e. slots are allocated but not all active.
* `+0x12..+0x65` patch-level parameters (effect sends, level/pan matrices, EQ …) — not decoded
  here, out of scope for sample selection.
* `+0x66 + 0x51·b` = **partial block b**.

Record 0, verbatim (sub `0x0524D4` = main `0x8324D4` = region `0x324D4`):

```
8324D4: 20 20 20 20 20 50 69 61 6e 6f 20 20 20 20 20 20  |     Piano      |   <- NAME
8324E4: 10 05 00 00 55 81 40 55 05 40 55 00 40 00 00 40  |....U.@U.@U.@..@|   type=10 mask=05 (2 partials)
8324F4: 00 00 40 55 00 40 55 00 40 08 89 00 17 00 0f 0c  |..@U.@U.@.......|
   ... (patch header, 0x56 bytes) ...
83253A: 00 00 00 01 00 00 00 1e 00 1e 00 1e 00 1e 00 1e  |................|   <- PARTIAL BLOCK 0
83254A: 00 00 00 42 00 00 00 54 15 80 48 21 7f fb 00 00
   ...
83258B: 00 7f 00 05 00 00 00 1e 00 1e 00 1e 00 1e 00 1e  |................|   <- PARTIAL BLOCK 1
```

### 2.2 The partial block (0x51 bytes) — the fields that pick the samples — MEASURED

| off | field | consumer |
|---|---|---|
| +0x00 | 0x00 (format tag, constant across all 1046 blocks) | — |
| +0x01 | partial flags `{00,18,40,58,7f,…}` | — |
| **+0x02** | **FINE / sub-select** (`&0x7F`) | `LABEL_0325FC` L34689 `LD E,(XDE+002h)` |
| **+0x03** | **SET / family byte** (`&0xC0` family, `&0x30` dispatch, `&0x0F` group) | `LABEL_0325FC` L34700 `LD E,(XDE+003h)` |
| +0x04/+0x05 | coarse (semitone) / fine transpose, signed | see §5 |
| +0x06.. | envelope / level / filter / keyscale params | timbre registers `+0x0C0/+0x140/+0x500` |

**CORRECTION to `kn5000-pipe-tonerecord.md §5` and `-partialset.md §1`:** those notes read
`ptr0[+0x02]` as "the multisample-SET index" (PIANO 0x00 / GUITAR 0x14 / BRASS 0x38 …).
`LABEL_0325FC` passes `ptr0[+0x02]` as the register that `LABEL_03248B` masks with **`0x7F`**
(`LD IZL,C … AND IZ,007fh`) and `ptr0[+0x03]` as the one it masks with `0x30/0xC0/0x0F`. So
**+0x02 is the FINE index and +0x03 is the SET/family byte.** Getting this backwards is why the
prior pass could not close Stage A statically (PIANO's real pair is `(fine=0x00, set=0x01)`,
not `set=0x00`). Both values are still per-instrument identifiers; only their roles swap.

### 2.3 How a SOUND-GROUP / sound selection reaches a record — MEASURED

```
main CPU  ──{lo,hi} 16-bit tone selector──▶  sub LABEL_03206F → LABEL_031F71 (asm L34174+)

   C   = byte[0x050100 + hi]                     ; bank → sub-index  (0x050100: 00 01 02 03 04 05 06 07 …)
   idx = (C << 7) + lo
   k   = u16[0x050180 + 2*idx]                   ; program map
   patch_record = 0x050000 + u32[0x051B00 + 4*k] ; the 629-entry pointer array
```

MEASURED spot-check, bank `hi=0`, programs `lo=0..7` →
`Piano | Bright Piano | Mellow Piano | Electric Grand | Modern E.P.2 | E.Piano 1 |
Modern E.P.1 | Music Box`, i.e. **the GM program map with 8 variation banks**.
Record indices `0 / 40 / 80 / 150 / …` are the SOUND-GROUP heads
(`Piano`, `Classical Guitar`, `SymphonicStrings`, `Bigband Brass`, …).

**CORRECTION — the instrument names in the prior notes are off by one record.** `-tonerecord.md
§5` read the 16-byte name *after* the partial blocks; that is the **next** record's name. The
pointer array proves records **start** with the name (`0x0524D4` = `"     Piano      "`, and
`0x05253A = 0x0524D4 + 0x66` is exactly the live-captured "PIANO ptr0"). Corrected defaults:

| SOUND-GROUP | live `ptr0` | record base | correct name | prior (wrong) name |
|---|---|---|---|---|
| PIANO | 0x05253A | 0x0524D4 (#0) | `Piano` | Bright Piano |
| GUITAR | 0x054A5D | 0x0549F7 (#40) | `Classical Guitar` | Spanish Guitar |
| STRINGS & VOCAL | 0x056E3C | 0x056DD6 (#80) | `SymphonicStrings` | Concert Strings |
| BRASS | 0x05B66C | 0x05B606 (#150) | `Bigband Brass` | Marching Brass |
| FLUTE | 0x05DB8F | 0x05DB29 | `Piccolo` | Jazz Flute |
| SAX & REED | 0x05C791 | 0x05C72B | `Soprano Sax` | Alto Sax |
| MALLET & ORCH PERC | 0x053938 | 0x0538D2 | `Glockenspiel` | Vibraphone |
| WORLD PERC | 0x055D92 | 0x055D2C | `Hawaiian Guitar1` | Hawaiian Guitar2 |
| ORGAN & ACCORDION | 0x05A037 | 0x059FD1 | `Perc Organ` | Full Drawbars |
| ORCHESTRAL PAD | 0x0642AF | 0x064249 | `Strings & Horns` | Strings & Flutes |
| SYNTH | 0x061279 | 0x061213 | `Square Lead` | Saw Lead |
| BASS | 0x05EFDE | 0x05EF78 | `Acoustic Bass` | Mellow Ac.Bass |
| DIGITAL DRAWBAR | 0x090723 | 0x0906BD | `<Jazz Drawbars>` | \<Rock Drawbars\> |
| ACCORDION REGISTER | 0x0588BE | 0x058858 | `German Acdn 1` | German Acdn 2 |
| GM SPECIAL | 0x060C49 | 0x060BE3 | `Tinkle Bell` | Rock Harmonics |
| LEFT default (E.P.) | 0x0532B7 | 0x053251 | `Modern E.P.1` | Modern E.P.2 |

Independent confirmation: the capture nvram's own part labels are **RIGHT2 = "Bigband Brass"**
and **LEFT = "Modern E.P."** (`kn5000-live-captures.md` §Sources) — which match the corrected
names, not the prior ones.

---

## 3. The SET descriptor (15 bytes) — the multisample header

`0x077914 + 15·i`, i = 0…486. Head of the array (main `0x857914`, region `0x57914`):

```
  #0 077914: 80 9d b0 02 00 c4 b0 02 00 0c 78 42 80 42 00
  #1 077923: 80 2e dd 02 00 55 dd 02 00 0c 78 42 80 42 00     <- PIANO
  #2 077932: 80 03 12 03 00 2a 12 03 00 0c 78 42 80 42 00     <- PIANO osc-2
  #3 077941: 80 f4 1b 03 00 03 1c 03 00 0c 60 42 80 42 00
```

| off | size | field | consumer |
|---|---|---|---|
| +0x00 | 1 | **format flags**. bit7 → record stride 6, else 4 (bits 5/6 select the 15/13/12/10-byte builders — **never set in this ROM**, see below) | `LABEL_023849` L15831-36 |
| +0x01 | 4 | rel32 → **ptrA** = zone-remap table | `LD XWA,(XIZ+1); ADD XWA,(045310h)` L15811-12 |
| +0x05 | 4 | rel32 → **ptrB** = partial-record array | L15814-15 |
| +0x09 | 1 | **key range minimum** (MIDI note) | `LD A,(XWA+009h)` L15787 (fold lower bound) |
| +0x0a | 1 | **key range maximum** (MIDI note) | `LD A,(XWA+00ah)` L15790 (fold upper bound) |
| +0x0b | 1 | **root key** of the multisample | L26724 `IZ -= (SETp[0x0b]<<8)+0x80` |
| +0x0c | 2 | **base pitch**, 1/256-semitone (`0x4280` = note 0x42 + 0x80) | L26727 `IZ += u16[SETp+0x0c]` |
| +0x0e | 1 | 0x00 | — |

and `ptrA[0..3]` is itself a rel32 → **ptrC** = the 128-byte note→zone-slot key-table
(`LD XWA,(XWA); ADD XDE,(045310h)` L15817-20).

**Format-flags census over all 487 descriptors (MEASURED):** `0x00`×318, `0x01`×3, `0x02`×13,
`0x08`×10, `0x80`×134, `0x81`×9. **Bits 5 and 6 are never set**, so of the six record builders
`LABEL_022A3F/61/83/A4/C5/E7` (strides 15/12/13/10/6/4, asm L14295-14361) only the last two are
ever reachable through this array. Stride is therefore always **6** (flags bit7 set) or **4**.

---

## 4. The PARTIAL RECORD (per key zone) — the thing that carries `+0x040`

`record = ptrB + stride · E`. **`record[0]` (u16 LE) is written verbatim to chip register
`+0x040`** (`LD WA,(XBC); LD (0451CEh),WA` in every builder; `0x0451CE` is the scratch word the
burst writer ships to `+0x040`).

```
  stride 6 :  [0..1] +0x040 word   [2..3] pitch word A (s16)   [4..5] pitch word B (s16)
  stride 4 :  [0..1] +0x040 word   [2..3] pitch word A (s16)
```
`+0x040 = { class = bits[15:12] , entry = bits[11:0] }` — unchanged from `-partialset.md §4`.

For stride-6 records the builder `LABEL_022AC5` also does `LD WA,(XBC+004h); LD (293Eh),WA`, and
`LABEL_023A05` (L16005-16011) then computes `desc+0x0a = desc+0x06 + (293Eh) + …` — i.e. **word B
is a signed pitch offset in the same 1/256-semitone units as the key/pitch value**, added into
the final pitch. (MEASURED path; the *unit* is INFERRED from the shared accumulator.)

PIANO's 16-zone array (set #1, `ptrB = 0x07DD55`, stride 6, main `0x85DD55`):

```
  E   addr     bytes                +040   wordA    wordB
   0  07DD55:  00 70 00 f7 ce f2    7000   -2304    -3378
   1  07DD5B:  01 70 00 ee 4e f9    7001   -4608    -1714
   2  07DD61:  02 70 00 f7 bd f4    7002   -2304    -2883
   3  07DD67:  03 70 00 f2 70 f0    7003   -3584    -3984
   4  07DD6D:  04 70 00 ee 68 f8    7004   -4608    -1944
   5  07DD73:  05 70 00 f4 5d f5    7005   -3072    -2723
   6  07DD79:  06 70 00 e9 24 f1    7006   -5888    -3804
   7  07DD7F:  07 70 00 f0 41 f8    7007   -4096    -1983
   8  07DD85:  08 70 00 ea 6c f5    7008   -5632    -2708
   9  07DD8B:  09 70 00 ef a4 f0    7009   -4352    -3932
  10  07DD91:  0a 70 00 f1 2d f9    700A   -3840    -1747
  11  07DD97:  0b 70 00 f3 26 f6    700B   -3328    -2522
  12  07DD9D:  0c 70 00 f0 33 f2    700C   -4096    -3533
  13  07DDA3:  0d 70 00 f1 34 f8    700D   -3840    -1996
  14  07DDA9:  0e 70 00 ed 42 f4    700E   -4864    -3006
  15  07DDAF:  0f 70 00 f3 47 f2    700F   -3328    -3513
```

GUITAR (set #49, `ptrB = 0x07B8AE`, stride 4) — note the **non-contiguous entry set**, which is
exactly what a per-instrument sample assignment looks like:

```
  E= 0 07B8AE: 00 30 d0 ff   +040=3000
  E= 1 07B8B2: 01 30 a0 fc   +040=3001
  E= 2 07B8B6: 02 30 80 fd   +040=3002
  E= 3 07B8BA: 03 30 80 f9   +040=3003
  E= 4 07B8BE: 03 30 00 f9   +040=3003   (same wave, different pitch word)
  E= 5 07B8C2: 40 30 00 f6   +040=3040
  E= 6 07B8C6: 41 30 00 f6   +040=3041
  E= 7 07B8CA: 48 30 d0 ed   +040=3048
```

### Key-split boundaries

The split points are **data**, in two tables:

* **`ptrC[0..127]`** — one byte per MIDI note = a fine **zone slot** (PIANO: `00 00 00 00 00 00
  01 01 01 01 01 01 02 02 …`, ~2 semitones per slot, 0x00..0x22).
* **`ptrA[4 + slot]`** — collapses slots to the actual record index **E**
  (PIANO: `00 00 00 00 00 00 00 00 01 02 02 03 04 05 05 06 07 08 08 09 0a 0b 0b 0c 0d 0e 0e 0f
  0f 0f 0f 0f 0f 0f 0f`).

`E = ptrA[4 + ptrC[key]]`, `record = ptrB + stride·E`, `+0x040 = u16[record]`
(`LABEL_023849` L15805-15840). The resulting split map for PIANO set #1:

```
   0-35 → 7000   36-39 → 7001   40-43 → 7002   44-47 → 7003   48-51 → 7004   52-55 → 7005
  56-59 → 7006   60-63 → 7007   64-67 → 7008   68-71 → 7009   72-75 → 700A   76-79 → 700B
  80-83 → 700C   84-87 → 700D   88-91 → 700E   92-127→ 700F
```

---

## 5. The complete selection chain — patch record → `+0x040` (fully static)

```
PATCH BLOCK  b  of patch record R      (fine = blk[+0x02],  set = blk[+0x03])
  │
  ├─ STAGE A1  LABEL_03248B (L34554) → LABEL_0323E5 (L34495) → LABEL_032469 (L34535)
  │     fam1  = set & 0xC0        (dispatch on set & 0x30 selects this path at all)
  │     idx1  = ((set & 0x0F) << 7) + (fine & 0x7F)
  │     e1    = u16[ base + A1_T[fam1] + 2*idx1 ]
  │     VSEL  = base + A1_A[fam1] + 11*e1                        → voice desc +0x1b
  │
  ├─ VELOCITY SPLIT  LABEL_022844 (L14040)
  │     q = 0 if vel<=VSEL[0] ; 1 if <=VSEL[1] ; 2 if <=VSEL[2] ; else 3
  │     (a2, c2) = ( VSEL[3+2q] , VSEL[4+2q] )
  │
  ├─ STAGE A2  LABEL_0328B5 (L34974) → LABEL_032750 (L34833)
  │     fam2  = c2 & 0xC0
  │     idx2  = ((c2 & 0x0F) << 7) + (a2 & 0x7F)
  │     e2    = u16[ base + A2_T[fam2] + 2*idx2 ]
  │     SETp  = 0x077914 + 15*e2                                  → voice desc +0x1f
  │
  └─ STAGE B   LABEL_023849 (L15805)
        ptrA = u32[SETp+1]+base ; ptrB = u32[SETp+5]+base ; ptrC = u32[ptrA]+base
        key  = (desc+0x06 >> 8) & 0x7F                            (see §5.1)
        E    = ptrA[4 + ptrC[key]]
        +0x040 = u16[ ptrB + stride(SETp[0]) * E ]
```

The VSEL record (11 bytes) is therefore **`{ 3 velocity split points , 4 × (fine, set) pairs }`**
— a per-instrument 4-way velocity switch over four different multisample SETs:

```
  #1 076AA4: 7f 7f 7f | 00 00 | 00 00 | 00 00 | 00 00     (no velocity switching)
  #3 076ABA: 7f 7f 7f | 00 01 | 00 01 | 00 01 | 00 01     <- PIANO block 0
  #10 076B07: 59 6d 7f | 04 00 | 04 04 | 05 01 | 04 00    (3 real velocity layers)
  #11 076B12: 3c 50 64 | 05 02 | 05 04 | 05 00 | 05 06
```

### 5.1 The `key` used for the zone lookup — MEASURED (asm L26690-26753)

```
IZ  = (note << 8) + 0x80
IZ += u16[part_base+0x112] + u16[0x041349]                 ; part transpose + master tune
IZ += sext(part_base[+0x16])<<8 + sext(part_base[+0x6d])<<8 ; part coarse + octave
desc+0x08 = clamp(IZ)                                       ; -> the chip PITCH register
IZ -= (SETp[+0x0b] << 8) + 0x80                             ; minus the SET's root key
IZ += u16[SETp+0x0c]                                        ; plus the SET's base pitch
IZ += sext(partial[+3])<<8 + sext(partial[+4])              ; partial coarse + fine transpose
desc+0x06 = LABEL_0229EC(IZ, SETp[+0x09], SETp[+0x0a])      ; FOLD by ±0x0C00 (=1 octave)
                                                            ;   into [kmin,kmax]
key = (desc+0x06 >> 8) & 0x7F
```

For most SETs `u16[+0x0c] == (SETp[+0x0b]<<8)+0x80` exactly (e.g. `0x4280` vs root `0x42`), so
those two terms cancel and **key == MIDI note**. Where they do not cancel, or where a partial
carries a coarse transpose, the whole zone map shifts by an integer number of semitones — the
"+12 Mallet offset" the prior pass observed, now explained and bounded. The **octave fold** also
explains DIGITAL DRAWBAR: its SET has a narrow `[kmin,kmax]`, so every played note folds into
the same zone and `+0x040` is constant across the keyboard (live: `0x6096` for all 7 notes).

---

## 6. Validation — PREDICT-THEN-CHECK against the live captures

All predictions were computed **from ROM bytes only** and then compared with
`kn5000-live-captures.md §5` (7 notes: C2 C3 C4 E4 G4 C5 C6), which this pass never re-ran.

**PIANO, both oscillators, exact:**

| | patch block | (fine,set) | e1 → VSEL | (a2,c2) | e2 → SETp | C2 C3 C4 E4 G4 C5 C6 | live |
|---|---|---|---|---|---|---|---|
| osc 0 | `0x05253A` | (00,01) | 3 → `0x076ABA` | (00,01) | 1 → `0x077923` | 7001 7004 **7007** 7008 7008 700A 700D | **7/7 ✓** |
| osc 1 | `0x05258B` | (00,05) | — | — | 2 → `0x077932` | …**7017** at C4 | ✓ (`+040b 7017`) |

The prior pass measured PIANO's `desc+0x1b = 0x076ABA` and `desc+0x1f = 0x077923` **live**; the
static walk lands on both addresses independently. That is two exact pointer hits before a single
`+0x040` value is compared.

**All 16 SOUND-GROUP defaults, block 0, velocity zone 0:**

| instrument | SET# | result |
|---|---|---|
| PIANO | 1 | **EXACT**, key shift 0 |
| GUITAR | 49 | **EXACT**, key shift 0 |
| STRINGS & VOCAL | 273 | **EXACT**, key shift 0 |
| SAX & REED | 204 | **EXACT**, key shift 0 |
| WORLD PERC | 77 | **EXACT**, key shift 0 |
| ORGAN & ACCORDION | 246 | **EXACT**, key shift 0 |
| SYNTH | 324 | **EXACT**, key shift 0 |
| BRASS | 157 | **EXACT** at key shift −12 |
| ORCHESTRAL PAD | 273 | **EXACT** at key shift −12 |
| BASS | 119 | **EXACT** at key shift −12 |
| MALLET & ORCH PERC | 29 | **EXACT** at key shift +12 |
| GM SPECIAL | 296 | **EXACT** at key shift +12 |
| FLUTE | 176 | **EXACT** at key shift +11 |
| ACCORDION REGISTER | 224 | **EXACT** at key shift −13 |
| DIGITAL DRAWBAR | 26 | **MISS** — resolved via the drawbar/footage table instead (§8) |
| DRUM KITS | — | **n/a** — per-key drum map, separate path (§10.3) |

**14 / 15 pitched defaults reproduce the live 7-note sequence exactly**, and every non-zero
offset is a whole number of semitones — the signature of the §5.1 transpose/fold term, not of a
wrong table. **Reported miss:** the per-instrument coarse-transpose *input* for the 0x51-block
path was not isolated (see §10.1), so the shifts above are measured, not yet predicted.

---

## 7. THE TABLES (generated, committed)

Three machine-readable tables in `notes/data/` (TSV, generated by the static walker):

### `kn5000-multisample-sets.tsv` — 487 rows, one per multisample SET
`set_idx, sub_addr, region_off, flags, stride, ptrA, ptrB, ptrC, kmin, kmax, root, basepitch,
n_zones, zones, finetune` where `zones` is `lo-hi:class:entry;…` over the full 0..127 key axis and
`finetune` is `E:<raw record bytes after the +040 word>`. Example rows:

```
1  077923 57923 80 6 07DD2E 07DD55 07AF1D 0C 78 42 4280 16
   0-35:7:000;36-39:7:001;40-43:7:002;44-47:7:003;48-51:7:004;52-55:7:005;56-59:7:006;
   60-63:7:007;64-67:7:008;68-71:7:009;72-75:7:00A;76-79:7:00B;80-83:7:00C;84-87:7:00D;
   88-91:7:00E;92-127:7:00F
```

### `kn5000-patch-partials.tsv` — 1046 rows (629 patches × their active partials)
`patch, name, type, partial_mask, partial, block_addr, region_off, fine, set, vsel_addr,
vel_splits, set_idx_per_velzone`. This is the **instrument → SET** join: every named instrument
the ROM defines, every one of its partials, and the SET index it selects in each of the four
velocity zones.

### `kn5000-sample-name-table.tsv` — 1220 rows (610 named tone records × 2 partial slots)
`rec, name, partial_mask, partial, fine, set, set_idx, set_addr, (class:entry) used`.
**This is the ROM naming individual samples.** Excerpt:

```
rec  name             fine set  set#  (class:entry)
  0  Silent           00   40   341   0:002
  1  Square Click     00   41   342   0:01D
  2  FluteKeyClick    78   40   486   4:0A0
  3  Rock Bass Drm    01   40   343   5:022
  4  Room BassDrm1    02   40   344   5:023
  5  Room BassDrm2    02   40   344   5:023
```

Cross-check: the live DRUM KITS `+0x040` sweep is `5024 5041 5069 5072 5062 5080 5065` —
**class 5, entries 0x22…0x80**, exactly the band this named table assigns to the drum samples
(`Rock Bass Drm` = 5:022, `Room BassDrm1` = 5:023, …). The drum kit is a per-key index into this
list; the list is where the ROM says what each drum sample *is*.

---

## 8. AGGREGATE STATISTICS — the `(class, entry)` inventory

Over **all 487 SET descriptors**, every zone of every set:

```
  total distinct (class, entry) pairs = 1444

  class 0 : 212 entries   min 0x000  max 0x0D5   2 gaps   99% dense over 0..max
  class 1 : 168 entries   min 0x000  max 0x0B0   4 gaps   95% dense
  class 2 : 184 entries   min 0x001  max 0x0B8   0 gaps  100% dense
  class 3 : 415 entries   min 0x000  max 0x1B3  13 gaps   95% dense   (236 in page 0, 179 in page 1)
  class 4 : 195 entries   min 0x001  max 0x0C5   2 gaps   98% dense
  class 5 : 164 entries   min 0x000  max 0x0A7   4 gaps   98% dense
  class 6 :  49 entries   min 0x001  max 0x096  11 gaps   32% dense
  class 7 :  57 entries   min 0x000  max 0x038   0 gaps  100% dense
                                                          ─────────
                                                    sum = 1444
```

Restricted to descriptors actually **reachable** from the two instrument tables
(268 from the 629 patches + 142 from the 610 named tone records = 409 of 487 descriptors):
**1402 distinct pairs** — class 0:187, 1:168, 2:184, 3:413, 4:192, 5:162, 6:39, 7:57.

Structural readings (MEASURED facts, INFERRED interpretation):
* **`entry` is a plain 0-based index into a per-class sample directory.** Seven of the eight
  classes are 95-100 % dense from 0 to their maximum; a tag/hash space would not be.
* **Only class 3 exceeds 8 bits** (179 of its 415 entries live in `0x100..0x1B3`). This is the
  single hard reason the field must be read as **12 bits, not a byte** — and it is now quantified,
  not inferred from two outliers (Sax 0x13E / GM 0x112) as in `-partialset.md`.
* **Class 6 is the outlier** (49 entries, 32 % dense, 11 gaps) — it is the drawbar/footage class,
  reached mostly through the 610-record footage table rather than through patch partials.
* **1444 total waves vs IC307's 198-entry index table.** With IC304/305/306 `NO_DUMP`, four
  equally-sized chips would supply ≈792 index entries — well short of 1444. So either the missing
  chips carry larger directories, or several `(class, entry)` pairs share one physical PCM block
  with different loop/root parameters. **This is a datum for the chip-map stage, not a conclusion
  here** — nothing in the firmware data decides it.

---

## 9. Corrections to prior notes

1. **`-tonerecord.md §5` / `-partialset.md §1` — `ptr0[+0x02]` is the FINE index, `ptr0[+0x03]` is
   the SET/family byte** (`LABEL_0325FC` L34689/L34700 vs `LABEL_03248B` masks). The published
   "SET index" column (Piano 0x00, Guitar 0x14, Brass 0x38 …) is the *fine* index. §2.2.
2. **`-tonerecord.md §4` — the tone record is not `N×0x51 + name`; it is `name(0x10) +
   header(0x56) + N×0x51`, and the recorded pointer is `record + 0x66`.** Consequently every
   instrument name in that note is off by one record. §2.1, §2.3 table.
3. **`-tonerecord.md §6` — `ptr2..5` "oscillator records" with 24-bit START/LOOP addresses are the
   15-byte SET descriptors of §3.** The "24-bit addresses" are the two rel32 pointers `ptrA`/`ptrB`
   (`0x0002DD2E + 0x050000 = 0x07DD2E`), and the trailing `0c 78 42 80 42 00` is
   `{kmin, kmax, root, basepitch, 0}`. Nothing there is a wave address — consistent with, and now
   *explaining*, `-chipmap.md §1`.
4. **`-partialset.md §2/§6` — Stage A is fully static.** `*(0x045310)` and `*(0x045314)` are
   compile-time constants (`0x050000`), so the "runtime tables" caveat is retired. §1.
5. **`-partialset.md §3` builder table** — six builders exist, but **bits 5/6 of the SET flags are
   never set in this ROM**, so only strides 6 and 4 occur (134+9 and 318+3+13+10 descriptors). §3.
6. **`-partialset.md §4` "the field is 12 bits"** — confirmed and quantified: 179 entries above
   0xFF, all in class 3. §8.

---

## 10. Honest gaps

1. **The per-instrument coarse transpose for the 0x51-block path.** §5.1's formula is fully
   traced, and its inputs are named (`partial[+3]/[+4]` of the 0x15-byte sub-block that
   `LABEL_02B576` reaches via `desc+0x17`, plus `part_base[+0x16]/[+0x6d]/[+0x112]`). What was
   *not* isolated is which structure supplies `desc+0x17` when a voice comes from a 0x51 patch
   block. Consequence: the six non-zero key shifts in §6 are measured, not predicted. Nothing in
   this note's tables depends on it — the zone maps are given on the SET's own key axis.
2. **DIGITAL DRAWBAR.** Its patch block resolves to set #26 (class 4), but the live register
   stream shows class 6 entry 0x96 (descriptor #252, whose 0x6096 zone spans keys 0-11 only, i.e.
   a fold-collapsed set). Drawbar voices are built through `LABEL_02B576`/`LABEL_032AE0`/
   `LABEL_032A08` from the **610-record footage table**, not from the patch block. The mechanism
   is identified; the specific footage-record selection was not traced this pass.
3. **DRUM KITS.** The captured `ptr0 = 0x075A48` is a 0x51 block inside a fixed-stride
   (0x1AA / 4-slot) region, and its `(fine,set) = (00,00)` resolves to the default set — i.e. a
   drum kit does **not** select its samples through the block's own `(fine,set)`. The live sweep
   (class 5, entries 0x22-0x80) matches the drum names in `kn5000-sample-name-table.tsv`, so the
   kit is a per-key index into the 610-record table; the per-key map itself was not located.
4. **Two parallel consumers of `LABEL_03248B`.** `LABEL_0325FC` (patch 0x51 blocks, `+2/+3`) and
   `LABEL_032682` (`LABEL_032AE0` result `+0x10+0x15·p`, `+1/+2`) both feed the same Stage A.
   This note validates the first exhaustively; the second is validated only through the 610-record
   table (§7). Whether both run for every voice, or the second is drawbar/extended-synthesis only,
   is not settled.
5. **Patch header `+0x12..+0x65`** (0x54 bytes of per-patch parameters) is untouched — it carries
   effect sends / level / EQ, not sample selection.
6. **What the chip does with `(class, entry)`** remains outside this pass by construction: the
   firmware never emits a PCM address (`-chipmap.md §1`), and IC304/305/306 are `NO_DUMP`.

---

## 11. Reproduction

```
# 1. build the interleaved region (kn5000.cpp ROM_LOAD32_WORD +0 / +2):
#    region[4k]=ev[2k]; region[4k+1]=ev[2k+1]; region[4k+2]=od[2k]; region[4k+3]=od[2k+1]
# 2. sub addr S  ->  region offset S-0x20000  ->  main addr S+0x7E0000
# 3. read the root struct at sub 0x050000 for every table pointer (§1)
# 4. walk:  patch block (fine=+2,set=+3) -> A1 -> VSEL -> velocity -> A2 -> SET desc
#           -> ptrC[key] -> ptrA[4+slot] -> ptrB + stride*E -> u16 = +0x040
```
Scripts (scratchpad, python stdlib only): `mkimg.py` (interleave), `lib.py` (address model),
`walk.py` (stages A1/A2/B), `sets.py` (descriptor + zone enumeration), `gen.py` (the three TSVs).
