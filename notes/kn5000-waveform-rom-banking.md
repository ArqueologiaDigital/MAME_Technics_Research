# KN5000 waveform-ROM banking + IC307-resident instruments + fabricated-PCM fallback

Author: autonomous RE pass, 2026-07-23. Requested by Felipe Sanches.
**Analysis + ROM inspection only** — no `src/` edits, no build, no MAME run.

Two deliverables:
* **(A)** which KN5000 instruments play sample data sourced ONLY from IC307 (the one
  dumped wave ROM), so Felipe can select one and evaluate the audio against REAL data;
* **(B)** a fabricated-PCM fallback for the three undumped wave ROMs that preserves the
  good IC307 dump byte-exact.

Evidence labels: **MEASURED** (read directly from ROM bytes / disasm), **INFERRED**
(deduction), **SPECULATIVE**.

Sources (all line numbers 1-based):
* Wave ROMs: `kn7000-emulator/roms/kn5000/kn5000_waveform_rom.ic304..ic307` (4 MiB each)
* Driver ROM defs: `src/mame/matsushita/kn5000.cpp` L1066-1070
* HLE model: `src/mame/matsushita/kn5000_tonegen.{cpp,h}`
* Sub-CPU disasm: `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`
* Register semantics: `notes/kn5000-tonegen-register-semantics.md`
* Authoritative format docs: `kn5000-docs/waveform-rom-format.md`, `kn5000-docs/tone-generator.md`
* KN7000 reference mechanism: `tools/make_wave_pack.py`, `tools/extract_kn5000_waves.py`,
  `src/mame/matsushita/kn_tonegen.{cpp,h}`, `notes/kn7000-tonegen-pcm-mechanism.md`

---

## 0. TL;DR — the answers up front

* **(A) shortlist verdict: NO panel instrument can be *proven* IC307-only from the data
  we have.** The wave-number → physical-chip decode lives **inside** the custom
  Matsushita LSI (TC183C230002) and is absent from the firmware, the Table Data ROM, and
  the single IC307 dump. `kn5000-docs/waveform-rom-format.md` lists this exact question as
  an **Open Question** ("How does the tone generator's address bus map to the 4-chip ROM
  layout?"). This is the honest answer and it saves a fruitless blind test. **But** the
  situation is favourable and there IS a concrete way to hear real IC307 PCM — see §3.
* The single most useful correction I found: **the HLE reads the WRONG register for wave
  selection.** It uses `reg[3]` (group0.bank3, +0x0C0), but the firmware's resolved
  waveform NUMBER (0-191) is written to **group4.bank1 (+0x440) = `regs[9]`** in the HLE's
  folded index. (MEASURED, §2.)
* **The only explicit multi-bank selector anywhere in the write path** is a 2-bit field
  `tonerec[+0x1a] & 0xC0` OR'd on top of the wave number at that same +0x440 write
  (asm L17944-17962). It is the **prime candidate for the chip-select** but is unproven
  (bit-6 overlap with the wave number; could instead be a loop/mode flag). (§2.4.)
* **(B)** IC307's own dumped bytes are the ground truth for the KN5000 wave-bank format.
  The KN7000 fabricated-sine work is used **only as a reference for the MECHANISM**
  (fake-with-the-real-mechanism: play a placeholder sample through the real playback
  datapath; the `make_wave_pack` tooling *shape*) — **NOT** its invented ROM container
  format. The fabricated IC304/305/306 banks must be **genuine IC307-format banks**
  (198-entry index at offset 0, param records, signed-16-LE PCM, `wave_offset*16`
  addressing) so they are a real model of a KN5000 wave bank and drop-in replaceable.
  IC307 (0xC00000-0xFFFFFF) passes through **verbatim, byte-exact**. Design + format spec
  + A/B/revert gate in §4-§6.

> **Weighting (Felipe, 2026-07-23):** the KN7000 sample ROMs are fully AI-generated
> speculative fabrications, not hardware-rooted. Trust IC307's real bytes/index as ground
> truth over any KN7000 analogy. For (A) this changes nothing except: keep IC307 byte-exact
> and verbatim. For (B): derive the KN5000 fabricated-bank format from IC307's own bytes,
> not from the KN7000 pack.

---

## 1. IC307 structure — MEASURED

IC307 = `kn5000_waveform_rom.ic307`, 4,194,304 bytes, CRC 20ff4629, loaded at `waveform`
region offset **0xC00000** (`kn5000.cpp:1070`). It is a self-describing bank:

```
Offset       Contents
0x000000     Main index table: 198 entries × 4 bytes  (ends 0x000318)
0x000318     Variable-length parameter records         (to ~0x001A30)
0x001A30     Signed 16-bit LE PCM waveform data
0x3FFFC0     0xFF padding
```

### 1.1 Index entry format — MEASURED, HLE is correct

Each 4-byte entry is `{ uint16 param_ptr, uint16 wave_offset }` LE. Byte address of the
PCM = `wave_offset * 16`. Matches `kn5000_tonegen.h:103-107` (`wave_index_entry_t`) and
the `*16` in `kn5000_tonegen.cpp:395`.

First bytes I read at offset 0: `1803 a301  1a03 c301  2403 7302 ...`
→ entry0 `param_ptr=0x0318, wave_offset=0x01A3` (byte 0x1A30),
  entry1 `param_ptr=0x031A, wave_offset=0x01C3`, …

**NUM_INDEX_ENTRIES = 198 is confirmed self-consistently:** entry0's `param_ptr = 0x0318
= 792 = 198×4` — it points to the first byte past the index table. (MEASURED. Matches
`kn5000_tonegen.h:131`.)

Enumerating all 198 entries (python over the dump): every `wave_offset*16` lies in
`0x001A30 … 0x0FEF60` and is **monotonically increasing** — i.e. IC307's own index is
**fully self-contained**: all 198 waveforms it names live inside IC307, in its first
~1.04 MB. **No index entry points outside IC307's own 4 MB.** (MEASURED.)

Per `kn5000-docs/waveform-rom-format.md`: **186 unique waveforms** (some entries share a
`wave_offset`), index 0 = a 256-sample perfect sine (test/fallback tone), and the tail
entries are long multi-cycle samples (e.g. wave 0xFEF6 ≈ 1.5 M samples shared by 7
entries). Most are multi-cycle PCM recordings → the KN5000 is **PCM sample-based**, not
single-cycle wavetable.

### 1.2 The upper ~3 MB of IC307 — MEASURED anomaly, INFERRED cause

A nonzero-density scan shows IC307 is 97-99 % nonzero across ALL 4 MB, yet its 198-entry
index only reaches ~1.04 MB. The bytes at 0x100000 / 0x200000 / 0x300000 *look*
table-like at a glance but do NOT parse as clean monotonic index tables (e.g. 0x100000
entry0 `param_ptr=0x02A0`→168 entries but wave_offsets non-monotonic; 0x200000 →1072
"entries", implausible). **INFERRED:** the upper 3 MB is additional PCM the main index
does not reach with a 16-bit `wave_offset` (max reach `0xFFFF*16 = 0xFFFF0` ≈ 1 MB). It
is most likely reached by a **coarser "page"/high-order select** the custom chip applies
— consistent with the docs' open question. Not fully reversed here; flagged.

---

## 2. How an instrument selects a waveform — the write path (MEASURED from disasm)

The chip is **register-indirect**: the sub-CPU writes a 16-bit register ADDRESS to
0x100000 then DATA to 0x100002 (`ToneGen_WriteSingleReg`, asm L29919-29926; docs
"Register Configuration Interface"). It **never writes a raw ROM address** — it writes an
abstract waveform NUMBER plus synthesis params, and the chip does the ROM-address decode
internally (`kn5000_tonegen.cpp:367-372` says exactly this).

### 2.1 The per-voice write burst — MEASURED

`ToneGen_WriteVoiceParams` (asm L29565+) writes ~23 register/data pairs from a 44-byte
scratch struct at **0x0451CC**. Struct-field → register map (MEASURED from the `ADD WA,
<off>` sequence, cross-checked with `tone-generator.md`):

| struct off | register (+off) | group.bank | role |
|---|---|---|---|
| +0x02 | +0x040 | 0.1 | pitch increment (semitone table) |
| +0x04 | +0x080 | 0.2 | velocity + latch strobe |
| +0x06 | +0x0C0 | 0.3 | *"waveform control"* (docs) — but see §2.3 |
| +0x08 | +0x100 | 1.0 | interpolated/portamento pitch |
| +0x0A | +0x140 | 1.1 | secondary pitch offset (detune) |
| +0x0C | +0x180 | 1.2 | expression coeff |
| +0x0E | +0x400 | 4.0 | note key info (note<<8) |
| **+0x10** | **+0x440** | **4.1** | **wave NUMBER (osc 1) — see §2.2** |
| **+0x12** | **+0x480** | **4.2** | **wave NUMBER (osc 2) — see §2.2** |
| +0x14 | +0x4C0 | 4.3 | level/key param |
| +0x16 | +0x500 | 5.0 | modulation param |
| — | +0x000 | 0.0 | key-on 0x8100 |
| +0x1A/+0x1C… | +0x840/+0x880… | 8.x/9.x | pan / bus gains / effect sends |

### 2.2 The actual waveform NUMBER is built by a key-zone resolver and lands in +0x440 / +0x480 — MEASURED

The struct fields +0x10 (→+0x440) and +0x12 (→+0x480) are computed in
`LABEL_024CAB…024E66` (asm ~L17930-18160), which stores to `0x0451DC` (=struct+0x10) and
`0x0451DE` (=struct+0x12):

```
LABEL_024CAB (asm L17944-17962):
    LD WA,(XSP+00eh); EXTZ XWA            ; XSP+00e = resolved WAVE NUMBER
    LD XBC,0000001bh; CALL LABEL_03D8CA   ; * 0x1b (27)
    LDA XIZ,04424Eh; ADD XIZ,XHL          ; XIZ = 0x04424E + wavenum*27  (per-wave RAM record)
    ...
    CPW (XSP+00eh),0080h; JRL NC ...      ; guard: wavenum < 0x80
    LD WA,(XSP+008h); LD WA,(XWA+01ah)    ; tonerec[+0x1a]
    AND WA,00c0h                          ; keep bits 6-7  (§2.4)
    OR  WA,(XSP+00eh)                     ; | wavenum
    LD (0451DCh),WA                       ; -> struct+0x10 -> register +0x440
```

The wave NUMBER itself (`XSP+00e`) comes from `LABEL_02177E` (asm L12300+), a **key-zone
resolver**: given (note, program/tone, keyscale) it walks firmware ROM tables at 0x2126
(5-byte records), 0x24E6 (12-byte records), 0xF48C/0xF4AC, and returns an 8-bit wave
number. It **clamps invalid results to 0xFF and treats numbers ≥ 0xC0 as invalid**
(`CP …,0c0h; JR NC → LD_L 0ffh`, asm L12351/12388). So **valid wave numbers are 0x00-0xBF
(0-191)** — which fits entirely inside IC307's 198-entry index range. (MEASURED.)

A SECOND wave number is resolved and written to +0x480 (`LABEL_024E66`, stores 0x0451DE)
→ the KN5000 voice is **dual-oscillator**: a note can layer two waveforms, potentially in
two different banks. **Consequence for (A):** an instrument is "IC307-only" only if BOTH
oscillators' wave numbers decode to IC307.

### 2.3 HLE discrepancy — the model resolves the wrong register — MEASURED

`resolve_waveform` (`kn5000_tonegen.cpp:363-427`) uses `reg[3]` (group0.bank3, +0x0C0) low
byte as the wave index. But +0x0C0 is NOT the wave number:
`0x0451D2` (=struct+0x06 → +0x0C0) is computed in `LABEL_025433`/`LABEL_025499`
(asm L18733/L18810) as `(keyscale_level<<8) | tonerec[+0x12]` — a **level/keyscale/filter
word**, clamped to 0..0x7F then `SLA 8`. The real wave number is at **+0x440 = `regs[9]`**
(group_map[4]=2, bank1 → reg_idx 2*4+1 = 9) and the 2nd osc at **+0x480 = `regs[10]`**.
`tone-generator.md` even carries a caution that the old "waveform pointer" labels on the
group-0 registers were wrong ("firmware analysis … confirms they carry pitch and velocity
data instead"). So the HLE's `reg[3]`-as-index is an approximation on top of an already
mislabelled register. **This is the first thing to fix when wiring real IC307 playback.**

### 2.4 The candidate bank-select: `tonerec[+0x1a] & 0xC0` — MEASURED field, UNPROVEN meaning

The 2-bit field OR'd above the wave number at the +0x440 write (asm L17960) is the **only
explicit "extra high bits" applied to a wave selector anywhere in the trace**. Two bits →
0..3 → exactly the count of ROM chips. This is the strongest lead for the chip-select. It
is **unproven**, for two reasons: (a) it overlaps bit 6 of the 7-bit wave number, so it is
not a clean 2+6 split; (b) it could equally be a loop/mode/second-domain flag. `tonerec`
here is `(XSP+008)`, a pointer into loaded tone/patch data (Table Data ROM IC1/IC3). If it
IS the chip-select, then **the bank of each instrument is a 2-bit field in its tone
record** — decodable once we can dump/annotate the tone records and correlate. Flagged as
the #1 follow-up for resolving (A) properly.

---

## 3. (A) — what Felipe can actually do to hear REAL IC307 data

Static analysis cannot name a provably-IC307-only panel instrument (§0, §2.4). But the
practical picture is good, because **every valid wave number (0-191) indexes into IC307's
own self-contained 198-entry table** (§1.1, §2.2). Two usable routes:

### Route 1 (immediate, guaranteed-real, but a test tone, not a "sound"):
IC307 **index 0 = a 256-sample perfect sine** (MEASURED; docs confirm). Any voice the
firmware resolves to wave number 0 plays genuine IC307 PCM. This is the surest "real
data" signal but it is the built-in test/fallback tone, not a named instrument.

### Route 2 (the real deliverable — a runtime capture recipe, needs the §4 fallback first):
Because the chip-select is unknown, the correct move is **empirical, not static**:
1. Implement §2.3 (read the wave number from `regs[9]`/+0x440 and `regs[10]`/+0x480
   instead of `reg[3]`) and the §4 fallback.
2. Add a one-line `logerror` in `resolve_waveform` dumping, per note-on: `ch`, the two
   wave numbers, and `tonerec[+0x1a]&0xC0` (the candidate bank).
3. On the running machine select each SOUND-GROUP instrument (PIANO, GUITAR, STRINGS &
   VOCAL, BRASS, FLUTE, SAX & REED, MALLET & ORCH PERC, WORLD PERC, ORGAN & ACCORDION,
   ORCHESTRAL PAD, SYNTH, BASS, DIGITAL DRAWBAR, DRUM KITS …), play middle C, and read the
   captured wave numbers.
4. **Any instrument whose BOTH oscillator wave numbers are 0-191 AND whose candidate-bank
   field decodes to IC307 will sound from real data.** Until the bank decode is nailed, the
   safe interpretation is: with the HLE forced to resolve every wave number through IC307's
   index (which it already does — `chip_base = 0xC00000`, `kn5000_tonegen.cpp:384`), the
   sound you hear IS real IC307 PCM — the only uncertainty is whether it is the *correct*
   waveform for that instrument.

**Honest bottom line for (A):** the current emulator ALREADY plays IC307 data for every
voice (it hard-codes `chip_base = 0xC00000`); what it gets wrong is *which* IC307 waveform
(wrong register, §2.3). So the fastest path to "select an instrument and evaluate real
IC307 audio" is not to find a magic instrument — it is to **fix the wave-select register
(§2.3) and then trust that every instrument is sounding real IC307 PCM**, using Route 2 to
tell which instruments are getting their *intended* waveform. No blind panel hunt needed.

### Predict-then-check (reported honestly)
* PREDICTED a bank-select bit would be found in the write path → **partial hit**: found a
  2-bit candidate (`tonerec[+0x1a]&0xC0`) but could not prove it is the chip-select.
* PREDICTED the index table might cross into missing banks → **miss (good news)**: IC307's
  index is fully self-contained; no cross-bank pointers. All 198 waveforms are real.
* PREDICTED the HLE's `reg[3]` wave index was right → **miss**: the wave number is at
  +0x440/`regs[9]`, not +0x0C0/`reg[3]`.

---

## 4. (B) — fabricated-PCM fallback that preserves IC307

### 4.1 The KN7000 tool is a MECHANISM reference only — the FORMAT comes from IC307

Two independent reasons not to copy the KN7000 pack:
1. The KN7000's **all four** wave ROMs are undumped, so `make_wave_pack.py` builds a whole
   16 MB synthetic pack and the driver loads it `ROM_LOAD_OPTIONAL`/`BAD_DUMP`. KN5000 is
   the **inverse case**: three chips missing, **one chip REAL**. We must NOT replace the
   real bank; we only fabricate for the holes.
2. **Per Felipe (2026-07-23): the KN7000 sample ROMs are fully AI-generated speculation,
   not hardware-rooted.** So its `KN7WVSY2` container is an *invented* format — do **not**
   mirror it. Reuse only the KN7000 *pattern*: honest in-source label, a single PCM
   datapath, deterministic device_start synthesis, drop-in replaceability.

**The fabricated KN5000 banks' FORMAT is derived from IC307's own dumped bytes** (§1,
§4.6) — because IC307 is the one real, hardware-rooted artifact we have. A fabricated
IC304/305/306 must be a genuine IC307-format bank, so that when the real chips are dumped
they slot in with zero code change.

### 4.2 What is already on disk (MEASURED) — reuse candidates

`kn7000-emulator/roms/kn5000/` already contains fabricated `kn5000_waveform_rom.ic304`,
`.ic305`, `.ic306` (4 MiB each), distinct md5s, ~99-100 % nonzero. Their first 64 bytes
are an index-table-shaped header **identical across 304/305/306** but different from
IC307. `tools/extract_kn5000_waves.py` documents them as *"the KN5000 project's own
SYNTHETIC sine/saw/triangle banks … NOT donor material"* and "Entry 0 of each chip is a
256-sample test wave." So these are **pre-existing labelled placeholders**.

**MEASURED (2026-07-23): they already conform to IC307's real format** — which is exactly
what Felipe's weighting asks for. Parsing `kn5000_waveform_rom.ic304`'s header:
`entry0.param_ptr = 0x0318` (⇒ **198 entries**, same 4-byte `{param_ptr, wave_offset}`
layout as IC307), `wave_offset*16` addressing, **monotonic** offsets 0x0009A0…0x0A6560;
param records at 0x318 use the same `{wave_offset word, param words with 0x40/0xC0
markers}` shape (`9a00 ba00 4000 cb00 4000 …` vs IC307 `a301 c301 4000 3000 2000 00c0 …`);
PCM at the first `wave_offset*16` is signed-16-LE (a rising ramp: `0000 1103 2206 3209
…`). So **the on-disk fabricated banks are genuine IC307-format banks** with placeholder
content — structurally faithful and reusable. (304/305/306 share an identical header,
differing only in PCM — a plausible "parallel layers" model.)

**They are currently INERT**: the driver declares IC304/305/306 `NO_DUMP`
(`kn5000.cpp:1067-1069`), so MAME does not load them (it fills the region with 0x00). Any
fallback must actively route data into 0x000000-0xBFFFFF.

### 4.3 The line that distinguishes "real" from "needs fabrication" — MEASURED

The region-offset test is exact and simple, because IC307 occupies a fixed, contiguous
sub-range of the `waveform` region:

```
IC304  0x000000 – 0x3FFFFF   fabricate
IC305  0x400000 – 0x7FFFFF   fabricate
IC306  0x800000 – 0xBFFFFF   fabricate
IC307  0xC00000 – 0xFFFFFF   REAL — pass through untouched
```

So: **`byte_offset >= 0xC00000` ⇒ real IC307 byte, played verbatim; `< 0xC00000` ⇒
fabricated.** No per-byte tagging needed. Define `static constexpr uint32_t IC307_BASE =
0xC00000;` (already present, `kn5000_tonegen.cpp:390`) as the single source of truth.

### 4.4 Recommended fill source — pick and justify

The fill must be a **genuine IC307-format bank** (§4.6), placeholder content only. Three
options; recommendation **A** (build faithful banks with a tool), with **C** as the
zero-effort reuse and **B** as the zero-asset stand-in:

* **A. Build faithful IC307-format placeholder banks with a small tool (RECOMMENDED).**
  Mirror the *shape* of `make_wave_pack.py` but emit the **IC307 container** (§4.6): a
  198-entry index at offset 0, param records, then signed-16-LE PCM with `wave_offset*16`
  addressing — placeholder sample content (a labelled single-cycle sine at index 0, like
  IC307, plus a few simple timbres). Produce three 4 MiB files
  `kn5000_waveform_rom.ic304/5/6`. Load them in the driver as **`BAD_DUMP`** (honest: not a
  real dump) at 0x000000/0x400000/0x800000. Deterministic, hardware-format-faithful,
  drop-in replaceable, and it makes the missing banks a real *model* of a KN5000 wave bank.
  This is the option that best satisfies Felipe's weighting.

* **C. Reuse the existing on-disk fabricated `.ic304/5/6` (fastest).** §4.2 MEASURED that
  they are **already** valid IC307-format banks (198-entry index, param_ptr=0x318,
  `wave_offset*16`, s16le PCM). Load them `BAD_DUMP` (never a bare `ROM_LOAD` — do not
  dignify fabricated data as a genuine dump). Zero new tooling. Only caveat: their exact
  placeholder timbres are arbitrary; if that is acceptable, this is the pragmatic pick and
  is format-faithful today.

* **B. Mirror IC307 into the missing banks at read time (zero assets, substitution).** If a
  voice resolves to `wave_start < IC307_BASE`, remap the read to `IC307_BASE + (wave_start
  & 0x3FFFFF)` — play IC307's real PCM for missing-bank voices too. Simplest and always
  musical, but it is a *substitution*, not a modelled bank, so it must be clearly labelled
  "IC307 mirror stand-in for undumped IC304-306" and it is NOT what "drop-in replaceable"
  means (nothing to replace). Good as an interim before A/C.

Whichever is chosen, **the IC307 path is unchanged**: for `wave_start >= 0xC00000` the
render reads `m_waveform_data` directly, byte-exact, exactly as today (§4.3 offset test).

### 4.6 The IC307-format container spec — derived from IC307's real bytes (for option A)

Build each fabricated 4 MiB bank as a faithful copy of IC307's structure (all fields
MEASURED from the dump in §1):

```
0x000000  Index table: 198 entries × 4 bytes, LE
            entry[i] = { uint16 param_ptr, uint16 wave_offset }
            entry[0].param_ptr = 0x0318  (= 198*4; self-delimiting, MUST hold)
            wave_offset is the PCM byte address / 16  (x16 granule = 8 samples)
0x000318  Parameter records (variable length), one per index entry, referenced
            by param_ptr. Record = uint16 wave_start (== the index wave_offset)
            then 0..N param words [flags:8][value:8]:
              flags 0x00 = key-zone boundary (value = MIDI note, descending)
              flags 0x01/0x08 = per-key pitch/tuning (value 0xF0..0xFF = -offset)
              flags 0x40 = mid/loop marker, 0x80 = end, 0xC0 = terminal zone
<min off> Signed 16-bit LE PCM, full range; wave_offset*16 = byte address.
0x3FFFC0  0xFF padding to 4 MiB.
```

Placeholder CONTENT rules (honest, minimal): index 0 = a single-cycle sine (as IC307's
index 0 is), the rest a few simple labelled waveforms; give each a trivial 1-zone param
record (`wave_start` word + a `0x80`/`0xC0` end marker) so the param walker has valid data.
Encoding MUST match IC307: **signed 16-bit little-endian**, `wave_offset*16` byte
addressing, `param_ptr` self-delimiting. Do NOT invent a header/magic (that was the KN7000
mistake). When IC304-306 are dumped, the real files replace these byte-for-byte and the
driver line changes from `BAD_DUMP` to a real `CRC/SHA1` — no code change.

### 4.5 Faithful mechanism (the non-negotiable)

Follow `fake-with-the-real-mechanism`: the fabricated bytes are placeholders, but they are
played through the **same sample-playback datapath** as IC307 (start/len/loop/interp in
`sound_stream_update`, `kn5000_tonegen.cpp:557-617`). No `sin()` in the render loop — if a
sine is used it is materialised as PCM first (as KN7000 does). In-source label required:
*"fabricated placeholder PCM for undumped IC304-306; datapath faithful, data is not;
drop-in replaceable when the chips are dumped (fill 0x000000-0xBFFFFF, change nothing
else)."*

---

## 5. (B) — the minimal `kn5000_tonegen` changes (spec, not code)

1. **Fix the wave-select register (prerequisite, §2.3).** In `resolve_waveform`, take the
   wave number from `regs[9]` (group4.bank1, +0x440) low bits — and optionally the 2nd
   oscillator from `regs[10]` (+0x480) — instead of `reg[3]`. Mask to the index range
   (`% NUM_INDEX_ENTRIES`, numbers are already 0-191). Keep the IC307 index lookup at
   `IC307_BASE` exactly as now for real voices.

2. **Compute `wave_start` with the bank offset instead of hard-coding IC307.** Today
   `chip_base = 0xC00000` unconditionally (`kn5000_tonegen.cpp:384`). Change to derive the
   bank from the candidate select (`tonerec[+0x1a]&0xC0`, once validated) → `chip_base =
   bank * 0x400000`. Until the bank decode is proven, keep `chip_base = 0xC00000` (all real
   IC307) as the safe default so the fix is behaviour-preserving.

3. **Reads by region (§4.3/§4.4).**
   * **Options A/C (load BAD_DUMP banks):** the fabricated bytes now live IN the `waveform`
     region at 0x000000-0xBFFFFF, so `read_waveform_sample` and the interpolation reads
     (`kn5000_tonegen.cpp:581-589`) work unchanged — no helper, no owned buffer. IC307
     reads at ≥0xC00000 are untouched.
   * **Option B (mirror):** add a helper `map_off(off) = (off >= IC307_BASE) ? off :
     (IC307_BASE | (off & 0x3FFFFF))` and route the sample reads through it.

4. **`has_pcm_data` becomes true for fabricated voices automatically.** Today it is gated on
   the region byte being nonzero (`kn5000_tonegen.cpp:520-522`); with `NO_DUMP` the region
   is zero-filled → missing-bank voices are silent. With A/C the loaded placeholder PCM is
   nonzero → the existing test passes with no change, **and IC307 voices are unaffected**
   (their bytes were always nonzero). For option B, evaluate the gate on `map_off(...)`.

5. **`device_reset`/`device_start`: no new state for A/C** (data is in the region). Option B
   needs only the helper. No `save_item` changes.

No change to the register decode, the envelope handling, or the stream format. The 2nd
oscillator (§2.2) can be deferred — mixing both is an enhancement, not required for sound.

---

## 6. A/B + revert gate (MEASURED-once-built; do not skip)

Before/after must be captured with the same scripted note. Positive-control discipline
(`measurement-discipline-emulation`): prove the instrument can SEE the change.

1. **IC307 stays byte-exact.** With the fallback active, a voice that resolves to an IC307
   waveform (wave number → `wave_start >= 0xC00000`) must read the **identical** PCM bytes
   as HEAD. Assert in a scratch log: `wave_start` and the first 8 samples equal the raw
   `region[wave_start..]`. Any difference = the fallback leaked into the real bank → revert.
2. **A real note plays** from fabricated data: a missing-bank voice (`wave_start <
   0xC00000`) now emits nonzero audio (was silent). Capture a WAV, confirm RMS > 0.
3. **A/B the IC307-resident path by ear/FFT:** pick a note the firmware resolves to a low
   wave number (Route 1, wave 0 = sine, or any 0-191) and confirm before==after
   (fabrication must not perturb the real path). Same spectral gate the KN7000 change used
   (< 0.01 semitone, level within ~1 %).
4. **`-validate` all seven drivers** (kn5000, kn6000, kn6500, kn7000, kn2400, kn2600,
   kn1500) clean; **kn5000 boots** to its play screen.
5. **Revert guard:** for A/C, reverting = change the driver lines back to `NO_DUMP` (the
   region zero-fills, missing banks go silent again, IC307 unchanged); for B, remove the
   `map_off` helper. Either way today's exact behaviour returns. Keep the default
   `chip_base = 0xC00000` until §2.4 is proven so no instrument silently moves off the real
   bank.

6. **Driver edit for A/C:** replace `kn5000.cpp:1067-1069` `NO_DUMP` lines with
   `ROM_LOAD("kn5000_waveform_rom.ic304", 0x000000, 0x400000, BAD_DUMP CRC(...) SHA1(...))`
   etc. (BAD_DUMP flags them as fabricated). IC307 line (0xC00000) is untouched.

---

## 7. Open items (honest)

* **The chip-select decode is unresolved.** `tonerec[+0x1a]&0xC0` (§2.4) is the lead;
  proving it needs the tone-record layout (Table Data ROM IC1/IC3) annotated and
  correlated with per-instrument wave-number captures (§3 Route 2).
* **IC307's upper 3 MB** (§1.2) is unindexed by the main table — a coarse page select is
  suspected but not reversed.
* **Dual-oscillator layering** (§2.2): "IC307-only" strictly requires both osc wave numbers
  to decode to IC307; the runtime capture must log both.
* Whether the KN5000 wave ROMs are shared with KN6000/KN7000 (docs open question) is out of
  scope here but would change the fabrication strategy if answered.
