# KN5000 tone-generator pipeline — DECODE STAGE: tone record & delivery

Author: autonomous RE pass, 2026-07-24. Requested by Felipe Sanches.
**Investigation only** — no `src/` edits, no rebuild. The only tracked change is this note.
Analysis is 100% static (ROM byte reconstruction + disasm), and is **cross-validated
byte-for-byte against the prior live captures** (`notes/kn5000-live-captures.md`,
`kn5000-tone-record.md`, `kn5000-voice-pipeline.md`) rather than re-running MAME.

This is the **TONE RECORD & DELIVERY** stage: how the main-CPU tone/patch record is stored,
how it is shipped to the sub-CPU, where it lands as the `tonerec`, and what `ptr[0..5]` /
`ptr[0]+0x02` mean. It builds on and reconciles the sub-CPU-side notes above (which mapped the
`tonerec` from the *sub* side) by supplying the **main-CPU / delivery side** and proving the
whole chain from the Table-Data ROM.

Evidence labels: **MEASURED** (ROM bytes / disasm / prior live capture), **INFERRED**,
**SPECULATIVE**. Respecting the chip boundary: nothing here claims IC303 sees any of this — the
record is how the *sub-CPU* computes the register writes; the register decode is a separate stage.

Sources
* main-CPU disasm `kn5000-roms-disasm/archive/asl/maincpu/kn5000_v10_program.asm` (v10 = the
  default BIOS `kn5000.cpp` ROM_BIOS(0)).
* sub-CPU disasm `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`.
* table_data ROM `kn5000_original_roms/kn5000/kn5000_table_data_rom_{even.ic3,odd.ic1}` (1 MB each,
  interleaved to the 2 MB `table_data` region: 32-bit word k = ev_word_k | (od_word_k<<16)).
* program ROM `kn5000_original_roms/kn5000/kn5000_v10_program.rom` (2 MB, mapped 0xE00000 mask
  0x1FFFFF).
* driver memory maps `kn7000_mame/src/mame/matsushita/kn5000.cpp`.

---

## 0. TL;DR — the whole chain

```
 TABLE-DATA ROM (IC1/IC3, main 0x800000..0x9FFFFF)          CUSTOM-DATA ROM (IC19, main 0x300000)
   0x830000..0x8A0000 = resident tone/voice DB                0x3E0000 = LZSS sub-program image
        |  (authored WITH sub-CPU addresses baked in)              |  (decompressed to scratch)
        |                                                          |
        |  ==== BOOT-TIME BULK TRANSFER (once) ====================|
        |   SubCPU_Send_Payload (main 0xEF068A): 5 x 64 KB via     |
        |   InterCPU_E1_Bulk_Transfer over the 8-bit latch+MicroDMA|
        v                                                          v
   SUB-CPU DRAM 0x050000..0x0A0000  (verbatim copy)     SUB 0x00F000..0x02F000 + 0x000400
        |                                                    (sub code/data + wavetable params)
        |
        |  the 17 SOUND-GROUP default voices live here as TONE-HEADER records:
        |    PIANO sub 0x05253A  ==  main 0x83253A  (byte-identical, PROVEN)
        v
   Per-selection (runtime): main sends a small voice-change command over the SAME
   latch+MicroDMA path (cmd byte = (chan<<5)|(len-1), dispatched by sub INT0_HANDLER).
   The sub resolves it to a TONE-HEADER pointer in the resident DB and fills the working
   `tonerec` (part_base+0x6E+zone*0x25) with ptr[0..5].
        |
        v
   NOTE-ON voice builder LABEL_02B4E3 reads the tonerec -> computes the IC303 register writes.
```

**The single most useful fact:** the boot transfer maps **main `0x830000` -> sub `0x050000`
verbatim** (`SubCPU_Send_Payload`, asm L134163/L134180-134199). Therefore every `tonerec`
pointer `ptr[k]` (a sub address `0x05xxxx..0x09xxxx`) has an exact twin in the Table-Data ROM at
`ptr[k] - 0x050000 + 0x830000`. I reconstructed the ROM and read those twins **statically**; they
are **byte-identical to the prior live sub-RAM dumps** (e.g. PIANO `ptr0` target). So the delivery
is proven without a live run, and the full record is now readable straight from ROM.

---

## 1. Delivery mechanism (MEASURED, disasm both sides)

### 1.1 Physical link
Two 8-bit latches (`kn5000.cpp` L437-438, L456-457):
* **main writes `0x140000`** (`subcpu_latch_w`, IC22) -> **sub reads `0x120000`** (`subcpu_latch_r`).
* **sub writes `0x120000`** (`maincpu_latch_w`, IC23) -> **main reads `0x140000`** (`maincpu_latch_r`).
Each latch write raises `/INT0` on the receiver. Bulk bytes are streamed through the *same* latch
address by **TMP94C241 MicroDMA** — main **channel 2** (dest = `0x140000`) sends, sub **channel 0**
(src = `0x120000`) receives (`SubCPU_Init_DMA_Channels`, main asm L138955; comment L138948-950).
This is exactly the "inter-CPU latch / MicroDMA payload" the task cited.

### 1.2 Command framing (main `InterCPU_Send_Data_Block`, asm L139042; sub `INT0_HANDLER` 0x020E86)
* **Standard command byte** = `(A << 5) | (count-1)` — top 3 bits `A` = channel/command class
  (0-7), low 5 bits = length-1 (1..32 data bytes) (asm L139029-139056). Sub reads the byte,
  `AND 0x1F; INC` = length, DMAs that many bytes into buffer `0x10F0`, and dispatches on the top
  bits (sub asm L11280-11289).
* **`0xE1`** = bulk transfer: sub DMAs a **6-byte header `{dst[4], len[2]}`** into `0x1116`, then a
  second DMA of `len` bytes into `dst` (main builds the header at L139242-139249; sub L11255-11261).
* **`0xE2`** = 10-byte extended header (`InterCPU_E2_Send`, asm L139105; sub L11263-11272).
* **`0xE3`** = "payload loaded" flag (sub L11274-11278).
Sub command classes (dispatch by top 3 bits): `AUDIO_CMDHANDLER_00_1F` (0x034D5F),
`_20_3F`(0x01FC7C), `_40_5F`(0x01FC7F), `_60_7F`(0x035893), `_C0_FF`(0x020C12), plus
`MIDI_DISPATCH`(0x034D93) and `CMD_DISPATCH_TABLE`(0x00F46C). A voice/tone change is delivered as
one of these small command packets (part + tone selector); it is **not** a re-shipment of the
record — the record DB is already resident from boot. *(The exact class/opcode of the voice-change
packet was not isolated in this pass — INFERRED from the architecture; see §8.)*

### 1.3 Boot bulk transfer of the tone DB (main `SubCPU_Send_Payload` 0xEF068A, asm L134170)
Issued once, after the sub-CPU is released from reset (asm L134099-134102). MEASURED map
(asm L134180-134231):

| main source | length | sub dest | what |
|---|---|---|---|
| `0x830000` | 0x10000 | `0x050000` | tone/voice DB chunk 0 |
| `0x840000` | 0x10000 | `0x060000` | chunk 1 |
| `0x850000` | 0x10000 | `0x070000` | chunk 2 (oscillator/partial records) |
| `0x860000` | 0x10000 | `0x080000` | chunk 3 |
| `0x870000` | 0x10000 | `0x090000` | chunk 4 |
| `0x3E0000` (IC19, **LZSS-decompressed** via `LABEL_EF41E3`) or Table-Data fallback | 0x10000 ×2 + 0xFF00 | `0x00F000`,`0x01F000`,`0x02F000` | sub code/data + wavetable params |
| (same base) +0 | 0x100 | `0x000400` | sub entry area |

Each 64 KB chunk is one `InterCPU_E1_Bulk_Transfer` (`XWA`=src, `XBC`=len, `XDE`=dst; asm L139213).
So the **entire resident tone/voice DB (main `0x830000..0x8A0000`) is copied verbatim to sub
`0x050000..0x0A0000`** — authored so the sub-CPU pointers baked into it (all `0x05xxxx..0x09xxxx`)
resolve correctly after the copy. **Cross-validation:** ROM `0x83253A` == live sub-RAM `0x05253A`,
byte-for-byte (§4) — independent proof the transfer runs and the mapping is exact.

---

## 2. Where it lands in sub-CPU RAM

* **Resident tone/voice DB:** sub `0x050000..0x0A0000` (from §1.3). Read-only after boot; the
  17 SOUND-GROUP default **tone-header records** live here (table in §6).
* **Working `tonerec` (per part/zone):** `tonerec = 0x041368 + part*0x11F + 0x6E + zone*0x25`
  (0x25 bytes/zone) — in the sub-DRAM gap `0x02F000..0x050000` that is **not** part of the payload,
  i.e. **runtime-built**, not transferred. Its first 0x18 bytes = the six 4-byte little-endian
  pointers `ptr[0..5]`; the 0x0D-byte trailer holds `tonerec[+0x1a]` (legacy bank). This layout is
  the prior notes' MEASURED result and is unchanged here.
* The `tonerec` `ptr[0..5]` all point **back into the resident DB** (`0x05xxxx`/`0x07xxxx`), i.e.
  into the transferred Table-Data image. The per-note **voice descriptor** (`0x2942 + idx*0x47`;
  `part_base` at desc+0x23, `tonerec` at desc+0x27) is filled by the note-on builder
  `LABEL_02B4E3` (asm L26860-26975), which reads the `tonerec` and the DB records it points at.

**Who fills the tonerec's 6 pointers:** the note-on builder only *reads* the tonerec (desc+0x27)
and derives the descriptor pointers via `LABEL_032AE0` (tone-header resolver) and `LABEL_032682`
(SET consumer). The 6-pointer array itself is written earlier by the **voice-select / tone-load
handler** invoked from the main-CPU voice-change command (§1.2). The exact fill routine was not
isolated this pass — **INFERRED** from the split between "read at note-on" and "present in RAM
before note-on" (prior live dumps).

---

## 3. The tone-ID -> tone-header pointer resolution (sub side, MEASURED structure)

The note-on builder passes a **16-bit tone value** (`XSP+0x1e`: low byte + high byte) to
`LABEL_03206F` (0x03206F) -> a per-part base pointer, then `LABEL_032AE0` (0x032AE0, asm L35206)
reads a **pointer directory** at `base + C*2 + 0x27` to obtain the **tone-header pointer** (stored
to desc+0x13). `LABEL_032682` (0x032682, asm L34747) separately consumes `ptr[0]+0x02` (the SET
index, §5) and the note to pick the partial set (stored to desc+0x1b/+0x1f). So a small tone-ID
indexes the resident DB directory to reach the header — consistent with the byte-wide delivery
(no bulk record re-transfer per selection).

---

## 4. The tone-header record ("~0x832000-style record") — full layout, MEASURED

`ptr[0]` points at a **tone-header / voice-definition record**. PIANO's is at sub `0x05253A`
= Table-Data ROM `0x83253A` (the "~0x832000 record" the task named). Its **structure**:

```
record = N x PARTIAL_BLOCK (0x51 bytes each)  ++  NAME (0x10 bytes)
         N in {1,2,4} (drum kits differ);  record length = N*0x51 + 0x10
```

* **PARTIAL_BLOCK** = 0x51 (81) bytes. Block 0 begins with the common header bytes (below), then
  per-partial params (envelope/level/filter/keyscale words — the same data the +0x0C0/+0x140/+0x500
  timbre registers are computed from). Blocks 1..N-1 are further layered partials. The block count
  N tracks the voice's oscillator layering seen in the register capture (PIANO 2, STRINGS 2,
  ORCH PAD/DRAWBAR 4, GUITAR/BRASS/FLUTE/BASS/EP 1).
* **NAME** = 16 ASCII bytes, space-padded/centred, right after the last block. This is the sound
  name the UI displays — **the "Sound Name Error" (kn5000-29) data lives in this record.**

### Common header (first bytes of block 0) — MEASURED, partial interpretation
| off | PIANO | meaning |
|---|---|---|
| +0x00 | 00 | record type/version (0x00 for all 17) — **MEASURED const** |
| +0x01 | 00 | bank/flags byte: {00,18,40,58} across instruments — **INFERRED** (per-instrument class/bank) |
| **+0x02** | **00** | **multisample-SET index** (consumed by `LABEL_032682`, §5) — **MEASURED** |
| +0x03 | 01 | partials/sub-index-ish: {00,01,02,0xC8}; often (N_partials-1) but not exactly — **SPECULATIVE** |
| +0x04..05 | 00 00 | mostly 0 (DRAWBAR 0xF4, ACCREG 0xFD) — **unclassified** |
| +0x06 | 00 | {00,20,30} — FLUTE/WORLD 0x20, SAX 0x30 — **unclassified** |
| +0x07 | 1E | level/keyrange-ish: {00,1E,28,32} — **SPECULATIVE** |
| +0x0d | 1E | read by builder (asm L26887) then `AND` with keyscale mask -> velocity/keyscale-zone enable — **MEASURED read, INFERRED use** |

Full PIANO record (sub 0x05253A / ROM 0x83253A), 2 partials + name:
```
+00: 00 00 00 01 00 00 00 1E 00 1E 00 1E 00 1E 00 1E
+10: 00 00 00 42 00 00 00 54 15 80 48 21 7F FB 00 00
+20: 7F 7F 00 00 7F 7F 00 00 64 4A 32 4E 00 2E 0F 06
+30: 42 28 70 00 0F 0F 41 20 00 48 3C 60 0A D8 00 00
+40: 28 50 14 58 00 46 00 07 1E 42 00 F1 0F 64 01 42
+50: 89 |--- block 1 (0x51..0xA1, near-duplicate of block 0) ---|
+A2: "  Bright Piano  "        <- 16-byte NAME
```
(EP is 1 partial: name "  Modern E.P.2  " at +0x51; ROM `0x8332B7` == live sub `0x0532B7`.)

---

## 5. `ptr[0]+0x02` = multisample-SET index — ALL 17 verified (MEASURED, static == live)

`ptr[0]+0x02` is read as `C` in `LABEL_032682` (asm L34756: `LD C,(XBC+002h)`) and drives the
partial-SET pick `LABEL_03248B`. Reading it **straight from the reconstructed Table-Data ROM**
(via the §1 mapping) reproduces the live-captured SET index for **every** SOUND-GROUP default:

| # | instrument | ptr0 (sub) | ROM twin | SET (+0x02) | live? | sound name (from record) |
|---|---|---|---|---|---|---|
| 0 | PIANO | 0x05253A | 0x83253A | 0x00 | ✓ | Bright Piano |
| 1 | GUITAR | 0x054A5D | 0x834A5D | 0x14 | ✓ | Spanish Guitar |
| 2 | STRINGS & VOCAL | 0x056E3C | 0x836E3C | 0x64 | ✓ | Concert Strings |
| 3 | BRASS | 0x05B66C | 0x83B66C | 0x38 | ✓ | Marching Brass |
| 4 | FLUTE | 0x05DB8F | 0x83DB8F | 0x40 | ✓ | Jazz Flute |
| 5 | SAX & REED | 0x05C791 | 0x83C791 | 0x4C | ✓ | Alto Sax |
| 6 | MALLET & ORCH PERC | 0x053938 | 0x833938 | 0x09 | ✓ | Vibraphone |
| 7 | WORLD PERC | 0x055D92 | 0x835D92 | 0x1F | ✓ | Hawaiian Guitar2 |
| 8 | ORGAN & ACCORDION | 0x05A037 | 0x83A037 | 0x58 | ✓ | Full Drawbars |
| 9 | ORCHESTRAL PAD | 0x0642AF | 0x8442AF | 0x64 | ✓ | Strings & Flutes |
| 10 | SYNTH | 0x061279 | 0x841279 | 0x79 | ✓ | Saw Lead |
| 11 | BASS | 0x05EFDE | 0x83EFDE | 0x2B | ✓ | Mellow Ac.Bass |
| 12 | DIGITAL DRAWBAR | 0x090723 | 0x870723 | 0x88 | ✓ | <Rock Drawbars> |
| 13 | ACCORDION REGISTER | 0x0588BE | 0x8388BE | 0x51 | ✓ | German Acdn 2 |
| 14 | GM SPECIAL | 0x060C49 | 0x840C49 | 0x70 | ✓ | Rock Harmonics |
| 15 | DRUM KITS | 0x075A48 | 0x855A48 | 0x00 | ✓ | (drum-kit layout) |
| — | Modern E.P. (LEFT default) | 0x0532B7 | 0x8332B7 | 0x06 | ✓ | Modern E.P.2 |

All 17 SET indices match `notes/kn5000-live-captures.md` §2 exactly (the anchor Piano 0x00 /
Brass 0x38 / EP 0x06 confirmed, plus the other 14). SET is **per-group-scoped, not unique**
(PIANO & DRUM KITS both 0x00; STRINGS & ORCH PAD both 0x64) — as the live note found.

---

## 6. `ptr[0..5]` — what each pointer targets (MEASURED)

The `tonerec`'s six pointers, decoded from the resident DB (PIANO / EP as exemplars):

| ptr | target | contents |
|---|---|---|
| **ptr0** | tone-header record (§4) | record type/bank, **SET@+0x02**, N partial blocks, NAME. PIANO 0x05253A, EP 0x0532B7. |
| **ptr1** | per-partial key-zone / scaling table | groups delimited by `7F 7F 7F`, then `(value, zone-index)` pairs — a keyscale/velocity-zone map. PIANO 0x076ABA: `7F 7F 7F 00 01 00 01 ... 7F 7F 7F 00 05 ...`. **INFERRED** semantics. |
| **ptr2..5** | oscillator / sample-parameter records (15 bytes each) | one per partial/oscillator. |

**Oscillator record (15 bytes) — MEASURED format:**
```
flag(1) | START(3B LE) | 00 | LOOP(3B LE) | 00 | 0C | rate(1,=0x78) | 42 80 42 00
```
* EP (4 distinct oscillators, ptr2..5): START = 0x03078E / 0x03128A / 0x02B397 / 0x0318E3.
* PIANO (ptr2..5 all = 0x077923): START = 0x02DD2E (sequential records there give 0x031203,
  0x031BF4…). `LOOP-START` is a short loop length (15-39 samples here).

**Do NOT overclaim the 24-bit START/LOOP here.** They fall in `0x02xxxx-0x03xxxx`; the prior notes
disagree on whether that is sub-DRAM (`kn5000-voice-pipeline.md §1.2`) or waveform-ROM
(`kn5000-real-sample-select.md §1`), and — decisively — the register-write capture proves **no
24-bit value ever reaches IC303** (the "sample address" false pattern the task warned about).
Their target space is the **wave/oscillator decode stage's** problem, not this one. Here they are
just the tone record's per-oscillator fields.

---

## 7. Main-CPU selection index (the entry point) — MEASURED

Before the sub-CPU ever runs, the main-CPU picks the tone from its own UI tables in program ROM:
* `SOUND_DATA_SECTION_PTRS` (0xE023B0): 16 dwords, one per SOUND-GROUP (0=PIANO … 15=DRUM KITS)
  pointing to that group's per-sound data (asm L36399-36415).
* `SOUND_CATEGORY_NAMES` (0xE023F0): the 18 category strings for the selection UI (asm L36418).
* Per-group per-sound records — e.g. BRASS (`SOUND_DATA_BRASS_PTRS` 0xE06BB0) is a pointer table to
  **3-byte records** `{lo, hi, 0xFF}` at 0xE06DB0 (asm L36447+): `{00 00 FF}`, `{01 00 FF}`,
  `{03 00 FF}`, `{01 01 FF}`, … The `{lo,hi}` pair is the **16-bit tone selector** the main-CPU
  hands to the sub-CPU (matching the sub's 16-bit tone value in §3); `0xFF` is a terminator.
So: **panel SOUND-GROUP+sound -> main indexes `SOUND_DATA_SECTION_PTRS[group]` -> per-sound
`{lo,hi}` selector -> sent over the latch -> sub resolves it to a tone-header pointer in the
resident DB -> tonerec.** The displayed sound name is the NAME field of that same record (§4),
which is why a failed lookup surfaces as **"Sound Name Error"**. (The precise UI->send glue and the
`{lo,hi}` -> directory-index arithmetic were not fully traced — **INFERRED** from the shapes.)

---

## 8. Reconciliation with prior notes / corrections

* **Confirms** `kn5000-tone-record.md`, `kn5000-voice-pipeline.md`, `kn5000-live-captures.md`:
  `tonerec = 0x041368+part*0x11F+0x6E+zone*0x25`; `ptr[0]+0x02` = SET; `ptr0` = the record. Adds
  the **main-CPU / delivery side** and proves the DB from ROM.
* **New (this pass):** the boot mapping **`0x830000`->`0x050000`** (and 4 more 64 KB chunks), which
  *explains* why `ptr[k]` are `0x05xxxx..0x09xxxx` — they are Table-Data ROM addresses shifted by
  `-0x7E0000`. This lets any tonerec pointer be read directly from ROM.
* **New:** the tone-header record is `N*0x51 + 0x10(name)`; the **NAME field** is embedded in the
  record (the "Sound Name Error" data). All 16 group names + EP recovered from ROM.
* **New:** the runtime delivery framing (`(chan<<5)|(len-1)`, `0xE1/0xE2/0xE3`, MicroDMA ch2/ch0).
* **Does NOT** re-resolve the 24-bit START/LOOP target space — deliberately deferred to the wave
  decode stage (§6), avoiding the "24-bit sample address" trap.

## 9. Honest gaps / open threads

1. The **voice-change command opcode** (which of the sub `AUDIO_CMDHANDLER_*` / MIDI classes carries
   a part's tone selection) and the routine that writes the tonerec's 6 pointers — **INFERRED**,
   not isolated. A live latch tap during a SOUND-GROUP press would pin it (method:
   `install_write_tap(0x140000,...)` on the main bus + dump `tonerec` before/after).
2. Exact meaning of header fields +0x03..+0x07 and the `ptr1` key-zone table encoding — partial.
3. DRUM KITS record layout differs from the `N*0x51+name` pattern (per-key drum map) — not decoded.
4. The `{lo,hi}` selector -> resident-DB directory-index arithmetic (main §7 <-> sub §3) — the two
   ends are established; the exact index math is not.

## 10. Reproduction (all static; nothing committed but this note)

```
# Build the interleaved 2 MB table_data region:
#   region[4k]=ev[2k]; region[4k+1]=ev[2k+1]; region[4k+2]=od[2k]; region[4k+3]=od[2k+1]
# For any tonerec pointer S in 0x050000..0x0A0000:  ROM twin = S - 0x20000 (region offset)
#                                                   main addr = S + 0x7E0000
# e.g. PIANO ptr0 0x05253A -> region 0x3253A -> main 0x83253A ; byte-identical to live sub 0x05253A.
```
Scripts used live in the scratchpad (`mkimg.py`, `probe*.py`, `names.py`, `layout.py`).
Program-ROM sound tables via `kn5000_v10_program.rom` (offset = addr & 0x1FFFFF).
