# KN5000 tone-gen — the "+0x440 wave-number resolver" (LABEL_02177E) fully decoded

Author: autonomous DECODE-STAGE pass, 2026-07-24. Requested by Felipe Sanches.
**Capture + static-RE only — no `src/` edits, no rebuild.** All instrumentation was
runtime-only (MAME lua taps + RAM reads) in an isolated scratchpad rundir with a **copy** of
the pre-init nvram; `kn7000-emulator/nvram` (owner's live state) was never touched.

Evidence labels: **MEASURED** (read live from the running machine / disasm bytes),
**INFERRED** (deduction from measured data), **SPECULATIVE**.

Sources: sub-CPU disasm `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`
(ExecTrace addresses = **runtime** addresses); built driver
`/home/fsanches/compartilhado/kn7000_mame_build/kn7000`, roms `kn7000-emulator/roms`;
isolated copy of the pre-init nvram (RIGHT1=Piano / RIGHT2=Bigband Brass / LEFT=Modern E.P.).
Builds on / **corrects the framing of** `kn5000-wave-number.md`, `kn5000-live-captures.md`.

---

## 0. TL;DR — the decisive answer to the DECODE STAGE question

**`LABEL_02177E` is NOT a genuine `(instrument,note) -> wave-number` mapping. It is a
per-note-on DMA / voice-SLOT allocator for the streamed / "extended-synthesis" voices.**
The tables it walks (`0x24E6`, `0x2126`, `0x1E4D`, plus the static `0xF48C`/`0xF4AC` index
maps) are **RAM allocation-bookkeeping (free-lists)**, not a waveform table — their
wave-mapping columns are **`0xFF` (empty)** at runtime. Two independent, decisive facts:

1. **The resolver is not even called for ordinary PCM voices.** Its caller
   (`LABEL_024BE3`/`LABEL_024DBE`, the "+0x440 builder") gates it behind
   `tonerec[+0x1a] != 0` **OR** `part_base[+0x0a] bit15 set`. For PIANO / BRASS / GUITAR /
   STRINGS / MALLET / WORLD PERC / ORCHESTRAL PAD / BASS / ACCORDION REGISTER / DRUM KITS
   both are false, so `+0x440` stays `0x0000` (its pre-cleared value) and **`0xF48C` is never
   read** (MEASURED — the resolver's private table). This — not "the resolver returns 0" —
   is why the earlier note saw `+0x440 = 0` everywhere.

2. **When it IS called (FLUTE, SAX, ORGAN, GM SPECIAL), its output is a slot counter, not a
   wave index.** MEASURED, same instrument, three octaves apart: the wave-*identity* register
   `+0x040` and the value in `+0x440` behave like this —

   | instr | note | +040 (identity) | +400 (pitch) | +440 | +480 |
   |---|---|---|---|---|---|
   | FLUTE | C3 | 5000 | 33A8 | **0040** | 0000 |
   | FLUTE | C4 | 5000 | 3FA8 | **0041** | 0000 |
   | FLUTE | C5 | 5000 | 4BA8 | **0042** | 0000 |
   | ORGAN | C3 | 4001 | 3080 | **00C0** | 0040 |
   | ORGAN | C4 | 4002 | 3C80 | **00C1** | 0041 |
   | ORGAN | C5 | 4003 | 4880 | **00C2** | 0042 |
   | GM SPECIAL | C3 | 3113 | 3C80 | **00C0** | 0000 |
   | GM SPECIAL | C4 | 3112 | 4880 | **00C1** | 0000 |
   | GM SPECIAL | C5 | 3115 | 5480 | **00C2** | 0000 |

   `+0x440`'s low byte **increments by 1 per note-on** (0x40→0x41→0x42, 0xC0→0xC1→0xC2) and is
   **independent of pitch** — C3 and C5 are two octaves apart yet differ by exactly the
   note-on count, not by a wave/multisample index. This confirms `kn5000-live-captures.md`
   CORRECTION #2 and supplies its mechanism.

**Consequence for the chip-map stage:** the wave selection is carried **entirely by `+0x040`**
(class·zone, produced by the *other* resolver `LABEL_032682`→`LABEL_03248B`), which the HLE
already selects on. `+0x440`/`+0x480` must be modeled as **DMA/voice-slot numbers, never as a
wave index.** There is no hidden `(instrument,note)->wave` table here to recover.

---

## 1. Critical measurement-discipline correction: the disasm addresses are **RAM**, the
`.rom` file is packed

The sub-CPU map is `map(0x000000,0x0fffff).ram()` (1 MB DRAM, IC9/IC10 — `kn5000.cpp:429`).
The boot ROM **decompresses** `kn5000_subprogram_v142.rom` into this DRAM; the disasm's
ExecTrace addresses (`0x02177E`, tables `0x2126`/`0x24E6`/`0xF48C`/`0x1E4D`) are **runtime
DRAM addresses**, which do **not** equal offsets in the packed `.rom` file. Proof (MEASURED):
`.rom` byte `[0x24EE]=0x36` but **runtime** `[0x24EE]=0xFF`; `.rom [0x2177E]` and runtime
`[0x2177E]` also differ. **Any static dump of these tables from the `.rom` file is wrong** —
all table contents below were read from the running machine. (A trap the RULES warn about;
predicting the `.rom` layout and checking against runtime = MISS, corrected here.)

---

## 2. `LABEL_02177E` decoded (asm L12300+) — control flow

Args (byte regs): `A = note` (`voice[+0x04]`), `C = tone/set` (`voice[+0x00]`),
`E = keyflag` (a bank/mode flag from the caller). Locals: `l4=E`, `l6=C`, `l8=A`.
Returns 16-bit `HL = (l4|0x80)<<8 | wavenum` on success, low byte `0xFF` on "not found".
Note the frame macro semantics: `DEC 8,XSP` allocates 8 bytes ⇒ **`INC 8,WA` means +8**, not
+1 (verified against `INC 4,IX`/`INC 1,XIX` elsewhere) — this is load-bearing below.

Gates (L12305-12312): `l6 >= 0x40` → fail; `l8 (note) >= 0x1A` → fail; else main path.
So the resolver only accepts a **"note" < 0x1A (26)** — i.e. `voice[+0x04]` is a **key-zone /
slot index (0..25), not a MIDI note** (MEASURED: ORGAN's C4 reaches a non-fail path, which a
MIDI-60 input could not).

**Main path** `LABEL_0217AD` (L12320):
```
QIZL = F48C[l4 & 0x1F]                 ; static index map (0..3)
l2   = F4AC[l4]                        ; static variant map (0..0x0E)
QIZH = 24E6[l6*12 + QIZL + 8]          ; <-- QIZL+8 = columns 8..11
if QIZH >= 0xC0: goto LABEL_021846     ; ALWAYS taken (see §3)
... (2126[QIZH*5] validation, never reached) ...
```
**Alternate** `LABEL_021846` (L12373): `BIT 5,l4` → if clear → `LABEL_0218AD`
(the `E=0x0D`/`0x0C` fallback-voice callers land here); if set → `LABEL_02174C(QIZL)`.

`LABEL_0218AD` (L12419): `QIZH = 1E4D[note*27 + l2]`; `if QIZH>=0xC0 → LABEL_021908`
(**ALWAYS taken**, §3) → `LABEL_02174C(QIZL)` → `LABEL_021463`/`LABEL_02129C` (bookkeeping,
§4) → `LABEL_0210A2(QIZH,QIZL)` = final wavenum.

`LABEL_02174C(QIZL)` (L12269): reads a **3-entry constant table at `0x210B`** =
`{+0:0x00, +4:0x40, +8:0x80}` selected by `QIZL & 3` → QIZH ∈ {0x00,0x40,0x80}.
`LABEL_0210A2` (L11549): `QIZL&3∈{0,1}→QIZH&0x3F; ==2→(QIZH-0x40)&0x7F; ==3→QIZH&0x7F`.
Net fallback wavenum ≈ `0x00` (0x40→0x00, 0x80→0x40), then combined with slot/bank bits by
the caller (§5).

---

## 3. Why the wave-mapping path is universally dead — MEASURED runtime tables

Read live from DRAM after boot (`dumpver.lua`, `dumpruntab.lua`):

* **`0x24E6`, all 64 rows × 12 bytes:** cols 0-7 = the row index (identity), **cols 8-11 =
  `0xFF` for every one of the 64 tones** (`ANY_NONFF_24E6_COLS8_11 = false`, MEASURED). The
  resolver reads exactly `col = QIZL+8 ∈ {8..11}` ⇒ **`QIZH = 0xFF` always** ⇒ the
  `0x2126` validation branch is never taken.
* **`0x1E4D`, note rows 0..0x19 (all valid notes) × 27 bytes: entirely `0xFF`**
  (`ANY_NONFF_1E4D_validnotes = false`, MEASURED) ⇒ the `LABEL_0218AD` path always bails to
  `LABEL_02174C`. The one non-`0xFF` row is note `0x1A` at `0x210B` = the fallback constants
  `00 FF FF FF 40 FF FF FF 80 …` (i.e. the `{00,40,80}` `LABEL_02174C` reads directly), sitting
  exactly past the 26 valid rows (`0x1E4D + 26*27 = 0x210B`). **INFERRED:** deliberate layout.
* **`0xF48C[0..0x1F]` (static):** `00 00 00 00 01 01 01 01 02 02 02 02 03 00 03 00 01 01 01
  01 00…` = `keyflag&0x1F -> QIZL` (a 0..3 sub-slot).
* **`0xF4AC[0..0x1F]` (static):** `00 01 02 03 … 0C 0D 0C 0D 0E 0E 0E 0E 00…` = `keyflag ->`
  variant (mostly identity).
* **`0x2126`, 192 entries × 5:** `{+0=e+1, +1=e-1, +2=0x1A, +3=0x00, +4=slot}`; the `+4`
  field is **`0xFF` (=free) for all entries at idle** (MEASURED). `+0/+1` = a doubly-linked
  **free-list** (next/prev).

So even though `0xF48C`/`0xF4AC` are real static maps, they only ever feed the `0xFF`
wave-columns → the tiny `LABEL_02174C` fallback. **There is no populated wave table.**

---

## 4. `0x2126`/`0x1E4D`/`0x24E6` are ALLOCATION bookkeeping, not a wave map — INFERRED

Decisive tell: `LABEL_02129C` (L11785) and `LABEL_021463` (L11950) **WRITE** these tables
(`LD (XIX+004h),C`, `LD (XIX+004h),0ffh`, `LD (XHL+DE),C`, `LD (XHL+BC),0ffh`). A pure
`(instrument,note)->wave` ROM lookup never writes its own table. Combined with the `0x2126`
free-list shape (`next/prev/…/slot`, `slot=0xFF=free`) and the per-note-on incrementing
`+0x440` (§0), these are a **voice / DMA-slot allocator's occupancy maps**: the "resolver"
finds/records a free streaming slot for the note and returns its index. `LABEL_021463` cross-
links `2126`↔`1E4D`; `LABEL_02129C` links `24E6`↔`2126`. (SPECULATIVE detail: exact
alloc/free protocol; the FUNCTION — slot allocation — is INFERRED-solid from the writes +
the live counter.)

---

## 5. `LABEL_024CAB` (the "+0x440 builder", asm L17865-18104) — where +0x440/+0x480 come from

`LABEL_024BE3` is the per-voice programmer that fills the 44-byte scratch struct `0x0451CC`
(`+0x10 -> reg +0x440`, `+0x12 -> reg +0x480`). Three branches, all MEASURED-consistent:

* **`tonerec[+0x1a] != 0`** (FLUTE 0x40, SAX 0xC0, WORLD PERC 0x40): main branch →
  `CALL LABEL_02177E` → `LABEL_02DB16` (extended DMA setup) → **`LABEL_024CAB`** stores
  `[0x0451DC] = (tonerec[+0x1a]&0xC0) | wavenum` (gated `wavenum < 0x80`).
* **`tonerec[+0x1a] == 0` AND `part_base[+0x0a] bit15 SET`** (ORGAN 0xC004, GM SPECIAL 0xC004):
  `LABEL_024DBE` (L18043) → `CALL LABEL_02177E` with `E=0x0D` (osc1) / `LABEL_024E66` `E=0x0C`
  (osc2) → stores `[0x0451DC] = (wavenum&0x7F) | LABEL_033E02(note,ks,1)` and
  `[0x0451DE] = wavenum | LABEL_033E02(note,ks,0)`.
* **`tonerec[+0x1a] == 0` AND `part_base[+0x0a] bit15 CLEAR`** (all ordinary voices): both the
  `LABEL_024DBE` and `LABEL_024E66` gates (`BIT 0fh,(part_base[+0x0a])`) fall through to
  `LABEL_024F3C` **without touching** `0x0451DC`/`0x0451DE` → **+0x440/+0x480 = 0** (their
  boot-cleared value). MEASURED: F48C never read, `S440=[0000]` only.

**The per-note-on increment** in `+0x440`/`+0x480` comes from `LABEL_033E02` (L36909): it
indexes `part[+0x5d]&0x0F` (a per-voice **type** field, 0..11) through a jump table at `0xFB96`
to a per-type handler that returns the DMA-slot/bank component. So `+0x440 = slot(part-type,
counter) | small-wavenum(≈0)`. **INFERRED** (mechanism) + **MEASURED** (the counter).

MEASURED resolver call fingerprints (in-window `0xF48C` reads):
FLUTE `[00]=00,[04]=01`; ORGAN/GM `[0C]=03,[10]=01` — i.e. `keyflag` ∈ {0x0C,0x0D,0x10,0x20}
(bank/osc/mode-dependent), consistent with the `E=0x0D`/`0x0C`/`bank|0x20` callers. Ordinary
voices: **no `0xF48C` read at all.**

---

## 6. Predict-then-check log (RULES compliance)

* PRED: `.rom` file offset = table address → **MISS** (it's packed; runtime DRAM differs). Fixed.
* PRED: `INC 8` = +1 → **MISS** (it is +8; changes which `24E6` column is read to 8-11=`0xFF`).
* PRED (from task hint): resolver dead due to "note==0x1A demand" → **PARTIAL HIT**: the
  `note<0x1A` gate does bound the input, but the *primary* reason ordinary voices get +0x440=0
  is the **caller gate** (`part_base[+0x0a] bit15` / `tonerec[+0x1a]`), not the note gate; and
  for the voices that DO reach it, the tables are `0xFF`-empty so it degenerates to a slot
  allocator. Reported in full.
* PRED: `+0x440` encodes a per-note wave number → **MISS** (note-independent slot counter,
  MEASURED across C3/C4/C5). This is the headline finding.

## 7. Honest gaps
* The exact per-type handlers behind `LABEL_033E02`'s `0xFB96` jump table (slot/free protocol)
  are not byte-decoded — not needed for the conclusion (the slot behaviour is measured).
* Whether the `0x24E6`/`0x1E4D` wave-columns are EVER populated in some other firmware
  mode/config (custom expansion samples) is untested; in the shipped preset config they are
  `0xFF` for all 64 tones / all valid notes (MEASURED here).
* Reproduce scripts: `scratchpad/cap_res.lua` (per-note resolver capture),
  `scratchpad/dumpver.lua`/`dumpruntab.lua` (runtime table dumps),
  `scratchpad/run_res.sh` (isolated-nvram runner).
