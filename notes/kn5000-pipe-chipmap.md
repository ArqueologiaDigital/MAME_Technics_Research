# KN5000 tone-gen — DECODE STAGE: (class,zone) `+0x040` → IC307 waveform address

Author: autonomous CHIP-MAP decode pass, 2026-07-24. Requested by Felipe Sanches.
**Investigation only — no `src/` edits, no rebuild.** Analysis is 100% static (IC307 ROM bytes +
reconstructed Table-Data ROM + sub-CPU disasm), cross-validated against the prior **live** register
captures (`kn5000-live-captures.md`). The only tracked change is this note.

This closes the CRUX stage the task posed: **how the tone-generator chip (IC303 / TC183C230002)
turns the register inputs it receives — primarily `+0x040 = {bank, zone}` — into a specific IC307
waveform / PCM address.** It builds on and consumes the four decode notes it was handed:
`kn5000-pipe-tonerecord.md`, `-partialset.md`, `-resolver.md`, `-registers.md`, plus
`kn5000-ic307-content-map.md`.

Evidence labels: **MEASURED** (ROM bytes / disasm / prior live capture), **INFERRED**,
**SPECULATIVE**. Chip boundary respected throughout: IC303 sees only register writes; every claim
about what the *chip* does with `+0x040` is bounded by what the register stream + the one dumped
wave ROM can support.

Scripts (scratchpad, not committed): `parse307.py` (IC307 index/param decode),
`extract_fast.py` (firmware partial-record arrays), `fft307.py` (per-wave spectra),
`validate_map.py` (overlap + coherence tests).

---

## 0. TL;DR — the answer, and why it is partly a *negative* result

**The waveform the chip plays is selected by exactly one 16-bit register value:
`+0x040 = { class = bits[15:12], entry = bits[11:0] }`** — reconfirmed, and now proven airtight:
the delivered partial record carries **no wave address of any kind** (§1), so the physical PCM
address is resolved **entirely inside the custom LSI**. `class` is a per-instrument-family **bank**;
`entry` is a per-instrument **multisample-zone index** (§2–§3, MEASURED from the firmware's own
partial-record arrays).

**The exact numeric `{class,entry} → IC307-local-index` map is UNDERDETERMINED by the available
data** and cannot be honestly pinned, for one hard reason: the map lives in the TC183C230002's
internal address decode (which chip-selects IC304-307 and drives their ROM address lines from the
16-bit wave-ID), and **IC304/305/306 are NO_DUMP**. Nothing in the firmware, the Table-Data ROM,
the register stream, or IC307 itself ties a firmware `{class,entry}` to an IC307 local index (§5).

Of the four hypotheses the task posed, the evidence decides them cleanly:

| | hypothesis | verdict | basis |
|---|---|---|---|
| **H2** | resolver tables map (set/note)→wave#; `+0x440` is not dead | **FALSIFIED** | `+0x440` is a per-note-on **slot counter**; resolver tables are `0xFF`-empty (prior live, `-resolver.md`) |
| **H4a** | `entry` **directly** indexes IC307's 198-entry table | **FALSIFIED** | 16 low IC307 indices are claimed by ≥2 different classes (§4); `entry` alone can't disambiguate |
| **H3** | a per-instrument ROM table of IC307 wave-numbers | **NOT FOUND** | the delivered record carries only `{class,entry}`+fine-tune, no IC307 numbers (§1) |
| **H1/H4** | `class` = chip/bank select; `entry` = {page, index-within} zone selector | **BEST-SUPPORTED, but numerically underdetermined** | entry blocks span a per-class `0x000..0x1FF` space; Sax/GM/World exceed 198 ⇒ a page bit; IC307's page-0-indexed + 3 MB-tail layout matches (§4–§5) |

So the honest deliverable is: the **register→wave-ID extraction is exact**; the **wave-ID→address
decode is a hardware black box** whose *structure* is well-supported but whose *numbers* need the
missing chips. §6 gives the best-supported HLE mapping (and fixes the current harsh one); §7 says
exactly what would pin the real map.

---

## 1. The selector — `+0x040` only, and it contains no address (MEASURED, now airtight)

The register decode was already established (`-registers.md`): of every per-voice register, **only
`+0x040` is quantized to the multisample zone**; it equals `partial_record[0]`. This pass adds the
**decisive closure**: I pulled the *full* partial records out of the reconstructed Table-Data ROM
(they are statically present — the boot copy `0x830000→0x050000` is verbatim, `-tonerecord.md`).
A partial record is `{ +040 word } { fine-tune words }`, e.g. PIANO's 16 stride-6 records:

```
E   +040   w1     w2         (raw 6 bytes)
0   7000   F400   F55D       05 70 00 f4 5d f5
1   7001   E900   F124       06 70 00 e9 24 f1
...                          ( w1/w2 high bytes = 0xF4 0xE9 0xF0 0xEA 0xEF ... )
15  700F   F300   F247
```

`w1`/`w2` are **signed-negative fine-tune / root words** (0xEA–0xFF band — the *same* per-key
detune vocabulary IC307's own param records use, `-ic307-content-map.md §3.2`); GUITAR's are
`FFD0 FCA0 FD80 F980 …` — identically fine-tune-shaped. **None is an IC307 offset, a `wave_offset`,
or a 24-bit address.** (Confirms `-partialset.md`'s "record[+0x04/0a/0d] → 0x293E fine-tune, stays
on the sub-CPU"; and retires the old `real-sample-select.md` "24-bit sample addresses in the
oscillator records" lead — those 24-bit values were a *different* structure and never reach a
register, exactly the false pattern the task warned of.)

**Therefore the only wave-selection information IC303 ever receives is the 16-bit value
`+0x040 = {class, entry}`.** The chip resolves the PCM address from it internally. This is the chip
boundary in its strongest form: the address *cannot* be in the register stream because it demonstrably
isn't — so "we haven't decoded the encoding" here means "the encoding is the chip's internal ROM
address decoder", not "there's another register".

---

## 2. `entry` (bits 11:0) = per-instrument multisample-zone index — MEASURED from the firmware arrays

I located and dumped each instrument's **partial-record array** (`ptrB`, the array the note-on
builder indexes as `record = ptrB + E*stride`) directly from the Table-Data image, by anchoring on
its live `+040` values. The arrays are unambiguous — each is a compact, per-instrument-local run of
`{class,entry}` records:

| instrument | class | `entry` set (the zones), from the full ROM array |
|---|---|---|
| PIANO | 7 | `0x00 0x01 … 0x0F` (16 consecutive) |
| BRASS | 1 | `0x06 … 0x0C` (7 consecutive) |
| GUITAR | 3 | `0x00 0x01 0x02 0x03` + `0x40 0x41 0x48` |
| STRINGS | 0 | `0x73 0x75 0x77 0x79 0x7B 0x7D 0x7F 0x81 0x91` |
| SYNTH | 0 | `0x09` + `0x19 … 0x1F` + `0x28 0x29 0x2A` |
| ORGAN | 4 | `0x01 … 0x0A` + `0x13` |
| WORLD | 3 | `0xC5 0xC6 0xC7 0xC8` + `0xE1 … 0xE8` |
| SAX | 3 | `0x13E 0x13F 0x140 0x141 0x142 0x144` |
| GM | 3 | `0x112 … 0x116` |

`entry` **steps with the played note through this per-instrument set** (live: PIANO C2→C6 walks
`0x01→0x04→0x07→0x08→0x0A→0x0D`; the full ROM array is `0x00..0x0F`). So `entry` is precisely the
**multisample key-zone index within the instrument**. (MEASURED, arrays + live agree.)

Crucially, **the same low `entry` values are reused by different instruments** (PIANO, GUITAR,
ORGAN, FLUTE all use `entry ≤ 0x03`). So `entry` is *instrument-relative*, not a global ROM index.

---

## 3. `class` (bits 15:12) = per-instrument-family bank — MEASURED

`class` is instrument-constant (Piano 7, Brass/Bass 1, Guitar/Sax/World/GM 3, Strings/OrchPad/Synth
0, Organ/Accordion 4, Flute/Drums 5, Mallet 2, Drawbar 6). It is **data in the record's high nibble**
(`record[0]>>12`), independent of the firmware builder-class (`-partialset.md §4`). Combined with the
`entry` blocks, the full 16-bit `{class,entry}` is a **globally-unique wave ID**: e.g. all class-3
instruments occupy disjoint sub-ranges of a `0x3000..0x31FF` space (Guitar `0x00/0x40`, World
`0xC5/0xE1`, GM `0x112`, Sax `0x13E`). So the wave-ID space is a flat 16-bit `{family, zone}` id;
each id maps to one physical wave across IC304-307.

**8 classes vs 4 chips**, so `class` is *not* a raw 2-bit chip select. Two candidate structures
(both SPECULATIVE): a `class→chip` lookup, or `chip = class & 3` with `bit2` a primary/secondary
layer (that split pairs {3,7},{0,4},{1,5},{2,6} — one bright + one dark family per chip). Neither is
provable from one chip.

---

## 4. Hypotheses tested against IC307 (MEASURED)

**H2 — FALSIFIED (prior live, reconfirmed by structure).** `+0x440`/`+0x480` are per-note-on
rotating **slot counters** (increment +1 per note-on, pitch-independent), and the resolver
`LABEL_02177E`'s tables (`0x24E6/0x1E4D/0x2126`) are `0xFF`-empty at runtime — a voice/DMA-slot
allocator, not a wave map (`-resolver.md`, `-live-captures.md §6`). There is no hidden
`(instrument,note)→wave` table there.

**H4a (entry directly indexes IC307) — FALSIFIED (this pass).** Overlap test (`validate_map.py`):
mapping each instrument's `entry` set onto `IC307[entry]`, **16 IC307 indices are claimed by ≥2
different classes** — `IC307[0x02]` alone is claimed by PIANO(7), GUITAR(3), ORGAN(4), FLUTE(5).
If `entry` were the index, those instruments would share a waveform. So `class` **must** offset or
chip-select; a bare `entry` index is impossible. (This is exactly why the current HLE — which folds
`class` into a hash — at least separates them, even though it lands on the wrong waves.)

**H4a also fails on range.** SAX `entry 0x13E–0x144`, GM `0x112–0x116`, WORLD `0xC6–0xE8` **exceed
IC307's 198-entry page-0 index**. Since `entry` reaches `> 0x100`, a **page / high-order select
(entry bits ~9:8)** is required — matching IC307's own physical layout: a 198-entry index over
**page 0** (first ~1 MB) plus a **3 MB un-indexed tail (pages 1-3)** addressed by a coarse select
(`-ic307-content-map.md §2.3`). So `entry = { page: hi bits, local-index: lo bits }` is the
**best-supported reading** (INFERRED, strong): class-3's blocks at `0x00`, `0x40`, `0xC5`, `0xE1`,
`0x112`, `0x13E` look like page-tiled instrument slots in a `0x000..0x1FF` (2-page) space.

**H3 — NOT FOUND.** No per-instrument table of IC307 wave-numbers exists in the delivered data; the
record carries only `{class,entry}` + fine-tune (§1).

**H1/H4 — the winner (structure), underdetermined (numbers):**
> `class` selects the ROM **chip/bank** (IC304-307); `entry` = `{page, index-within-page}` selects
> the **zone** inside that chip. The chip then dereferences its own on-chip index/param records
> (the IC307 format) to the PCM start. The firmware does the *keyboard* split (producing `entry`);
> the chip does the *address* decode. IC307's per-record key-splits (mostly a constant `64 48 32`,
> not a tiling map — `parse307.py`) are consistent with this: the chip is handed a fully-resolved
> zone and does **not** re-split the keyboard, except in the few tail groups (185-197) that *do*
> carry `+8`-semitone tiling (`-ic307-content-map.md §4`).

The numbers can't be pinned because we can only see chip IC307, and nothing maps a wave-ID to its
local index.

**Supporting coherence fact (MEASURED, `validate_map.py`):** across IC307, **spectrally adjacent
index entries are 1.6× closer than random pairs** (mean L1 spectral distance 0.75 vs 1.19). IC307
lays its waveforms out so that **consecutive indices are a coherent family/multisample** — which is
why the real hardware can address a multisample as a contiguous index run, and why *any* mapping
that walks `entry` through consecutive IC307 indices yields a coherent group (used in §6).

---

## 5. Why the exact map is a black box (the honest limit)

The `{class,entry}→(chip, PCM offset)` function is the **custom LSI's internal address decoder**:
it wires the 16-bit wave-ID to a chip-select among IC304-307 and to those chips' ROM address lines,
then uses each chip's on-ROM index (IC307's 198-entry `{param_ptr, wave_offset}` table) to reach
PCM. That function is:
* **not in the firmware** — the firmware emits only the abstract 16-bit id (§1);
* **not in the Table-Data ROM** — the records carry id + fine-tune, no address (§1);
* **not in the register stream** — proven by the zone-boundary test (`-registers.md §4a`);
* **not derivable from IC307 alone** — IC307's index is a *local* 0-197 index; there is no
  wave-ID→local-index table anywhere in its fully-accounted bytes (`-ic307-content-map.md §0`).

And the three chips the map would land most instruments on (IC304-306) are **NO_DUMP**. In the
driver they are currently BAD_DUMP **mirrors of IC307** (`kn5000.cpp:1161-1163`), so *any* computed
address reads real IC307 PCM — good for "never silent", but it also means **`class` cannot make two
same-`entry` instruments distinct from real data today** (all four banks are the same bytes). This
is the crux of why a *correct* per-instrument timbre is physically unavailable for ~3/4 of the
instruments until the chips are dumped.

---

## 6. Best-supported HLE mapping + validation

### 6.1 The register→wave-ID extraction (EXACT, use this verbatim)
```
cls   = (regs[1] >> 12) & 0x0F      // +0x040 high nibble  = family/bank
entry =  regs[1]        & 0x0FFF    // +0x040 low 12 bits  = multisample zone   <-- FULL 12 bits
```
This is proven (§1-§3). **The current code's `zone = regs[1] & 0xFF` is a MEASURED bug**: it drops
`entry` bits 8-11, collapsing SAX `0x13E→0x3E`, GM `0x112→0x12`, WORLD `0xC6/0xE1` — i.e. it discards
the page bit that distinguishes those instruments' zones.

### 6.2 The physical model (drop-in-faithful skeleton)
```
chip        = class_to_chip(cls)                 // real: LSI chip-select (unknown map; §3)
page,local  = (entry >> 8), (entry & 0xFF)       // real: page/high select + within-page index
addr        = chip_base(chip) + resolve(chip, page, local)   // real: on-ROM index (IC307 format)
```
When IC304-306 are dumped, `class_to_chip` + each chip's own 198-entry index make this **exact with
no scatter**. Until then all `chip_base` alias IC307, so `resolve` must fall back to IC307's index.

### 6.3 The interim placeholder (distinct + coherent NOW; labelled)
Because all four banks currently mirror IC307, distinctness has to come from a **labelled**
per-class spread over IC307's one real bank. The best-supported placeholder — grounded in the §4
coherence fact (consecutive IC307 indices are a coherent group) — is:
```
idx = 1 + ( (cls * 23 + entry) mod 184 )     // 1..184: skip sine@0 and the tail dup/3MB entries 185-197
```
Properties (validated, `validate_map.py`):
* **Coherent multisampling** — an instrument's consecutive `entry` values map to **consecutive**
  IC307 indices (Piano `entry 0x0..0xF → idx 162..177`, a contiguous run ⇒ a coherent family by the
  1.6× adjacency metric). The current code's `base = 1+((bank*41+timbre)%160)` **hash** instead lands
  on an *arbitrary* wave, and several are harsh: PIANO→idx44 (`H4=5.6, H8=5.3` ≫ fundamental — a
  bright inharmonic wave, nothing like a piano), BRASS→idx25 (`H2=3.3`), GM→idx77 (`H3=5.0`).
  Looping one period of those at an unrelated pitch is exactly the harshness Felipe heard.
* **Distinct instruments** — `cls*23` puts each of the 8 families in its own 23-wide IC307 band, so
  different-class instruments never collide (the audible-distinctness requirement). Same-class
  instruments (e.g. STRINGS vs SYNTH, both class 0) separate naturally because their `entry` blocks
  differ (`0x73+` vs `0x19+`).
* **Honest limit** — class-3 spans `entry 0x00..0x144` (>184), so it wraps; with one chip, some
  overlap is unavoidable. That overlap is the *physical* reason the KN5000 needs 4 chips + pages —
  not a mapping bug. Labelled placeholder; replaced by §6.2 when the chips are dumped.

The constants `23`/`184` are tunable by ear (Felipe's ground truth); the *structure* (full 12-bit
`entry`, consecutive-zone stepping, per-class band) is the supported part.

---

## 7. What would pin the real map

1. **Dump IC304/305/306.** Then, for each, parse its 198-ish-entry index (IC307 format), and the
   `{class,entry}→chip` question reduces to matching each instrument's known `entry` set against
   the chips' waves (FFT family-match, using this note's per-instrument `{class,entry}` table §2).
2. **One hardware probe** would settle the decode without any dump: log the TC183C230002's **ROM
   address + chip-select lines** while playing a *known* instrument+note (whose `{class,entry}` is
   in §2). That directly reveals `{class,entry} → (chip, offset)` — the single missing function.
   (This is the only place the map physically exists.)
3. Absent either, the §6.3 placeholder is the ceiling: real timbre for whatever lives in IC307,
   coherent-but-not-authentic for the rest.

---

## 8. Predict-then-check log (RULES compliance)

* PRED: `entry` directly indexes IC307's 198 table → **MISS** (16 cross-class index collisions; §4).
* PRED: the delivered partial record contains a wave address (the old 24-bit-address lead) →
  **MISS** — records carry only `{class,entry}` + fine-tune words (§1). The 24-bit values were a
  different structure, never a register (the exact false pattern the task flagged).
* PRED: `class` is a raw 2-bit chip select → **MISS** — 8 classes observed, so it's a `class→chip`
  LUT or `{chip:2,layer:1}` (§3, SPECULATIVE).
* PRED (task H1): `class`=chip/page, `entry`=index-within → **PARTIAL HIT** — supported as the
  *structure* (entry has a page bit; IC307's page-0+tail layout matches), but the numeric map is
  underdetermined without IC304-306 (§4-§5).
* PRED: consecutive IC307 indices are a coherent family → **HIT** (1.6× vs random; §4) — this is
  what makes any consecutive-`entry` mapping sound coherent.

## 9. Honest gaps
* The `class→chip` function and the exact `entry` page/index bit-split are INFERRED, not pinned
  (§3-§4). Needs §7.
* Which instrument(s) physically live in IC307 is not proven (would need IC304-306 to exclude, or a
  family-match with labelled real recordings). The tail multisample groups 185-197 (`+8`-semitone,
  shared recordings FCA6/FEF6) are IC307's clearest whole-instrument multisamples but do not line up
  with any captured instrument's `entry` range, consistent with those instruments living off-chip.
* IC307's per-record `64 48 32` splits are read as fixed sub/velocity regions (not keyboard tiling)
  because they don't shift across entries except in the tail groups; their exact role is unconfirmed.

## 10. Reproduction (all static)
```
# IC307 index + param records + shared-offset multisample groups:
python3 parse307.py
# firmware partial-record arrays (per-instrument {class,entry} sets):
python3 extract_fast.py
# per-wave spectra:  python3 fft307.py
# overlap + coherence + current-map defect:  python3 validate_map.py
# table_data region: region[4k+0,1]=even[2k,2k+1]; region[4k+2,3]=odd[2k,2k+1];
#   sub addr S (0x05xxxx..0x09xxxx) -> region offset S-0x20000 (verbatim boot copy of 0x83xxxx).
```
