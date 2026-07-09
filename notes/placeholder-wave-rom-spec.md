> Recon report produced 2026-07-09 by the sound-plan rev-2 research sweep.
> Companion to notes/sound-subsystem-plan.md. Verify page/line/address citations before building on them.
> Note: the ROM-backup/custom-firmware work here targets Felipe's OWN instrument for preservation (dumping otherwise-unreadable mask ROMs), analogous to console homebrew — legitimate, reversible, no third party.

# Fabricating placeholder KN7000 wave ROMs (IC203/204/207/208) — RE findings + spec

All firmware addresses are program-ROM CPU addresses (file offset = addr − 0x48400000 in
`/home/fsanches/compartilhado/kn7000_disassembly/baserom/kn7000_program.rom`; disassembly line refs are
`/home/fsanches/compartilhado/kn7000_disassembly/disasm/program.asm`). Service-manual refs are
`/home/fsanches/compartilhado/KN7000/service_manual/technics_sx-kn7000_keyboard.pdf` (PDF page == printed page).

---

## 1. WAVE-ROM ADDRESSING as the KN7000 TG uses it

### 1.1 The readback window — fully decoded (KN7000-native, firmware-verified)

The WAVE ROM checksum routine at **0x4848399E–0x48483B0A** (task range confirmed; alternate entry
0x484839A1 used by callers) is the only firmware code that ever reads wave-ROM data. Protocol, per the
disassembly (program.asm:212540–212664):

```
arg d0 (byte) : TG select — 0 → ports 0x9805000x, ≠0 → 0x9804000x   (0x484839AC beq / 0x484839B0 jmp)
arg d1        : start window WORD address
stack +0x2C   : end   window WORD address (inclusive)
stack +0x30   : start parity (0 or 1)

base+0x6 ← 0x8000 | (word_addr >> 15)        ; PAGE register, bit15 = readback-enable
                                              ; (0x484839B3..0x484839E6; cleared to 0x0000 when done, 0x48483A4D)
base+0x8 ← 0x8000 | (word_addr & 0x7FFF)     ; word OFFSET within page       (0x484839F5..0x484839FD)
base+0xA → 16-bit data read                   ; (0x48483A03)
checksum += (word >> 8) + (word & 0xFF)       ; 32-bit byte-sum accumulator   (0x48483A0C..0x48483A1D)
inner loop: offset = parity, parity+2, … < 0x8000   (0x48483A27..0x48483A32)
outer loop: page = start>>15 … end>>15 inclusive     (0x48483A34..0x48483A47)
(short settle delay via lib call 0x4C03DD74(1) after enabling and after disabling the page reg)
```

So **one TG's wave space is a linear window of 16-bit words**; the two 128-Mbit chips of the pair are
**word-interleaved on parity** (window word bit 0 selects the chip; bits 23..1 are the 23-bit word address
inside one chip — matching "ROMs use bits 0-22" on AWAX0-22/AWAY0-22, service manual sheet 7 p.112 / sheet 8
p.114).

### 1.2 Sweep parameters, banks, and the hardcoded checksums

The per-test dispatcher at **0x48483B60** (cases 0..19, program.asm:212700+) and the parameter caller at
**0x48483B0D** define:

- **Tests 0–3 = internal ROMs**: start=0, end=**0x00FFFFFF** window words (0x48483C0A). Each parity sweep =
  512 pages × 16384 words = **8,388,608 words = exactly one 128-Mbit chip**. Internal pair = 16 M words
  (32 MB) per TG.
- parity table @**0x485CFD04** = `[0,1,0,1,…]`; TG-select table @**0x485CFD28** = `[0,0,1,1, 0×8, 1×8]`
  → test idx **0/1 = TG@0x98050000 parity 0/1**, idx **2/3 = TG@0x98040000 parity 0/1**.
- **Expected checksums hardcoded @0x485CFD18** (compared at 0x48483C2B–0x48483C36):

  | test idx | TG port | parity | expected byte-sum | implied avg byte |
  |---|---|---|---|---|
  | 0 | 0x98050000 | even | **0x8164C77C** | 129.39 |
  | 1 | 0x98050000 | odd  | **0x815CFC83** | 129.36 |
  | 2 | 0x98040000 | even | **0x8331EF0B** | 131.20 |
  | 3 | 0x98040000 | odd  | **0x83254F9D** | 131.15 |

  Averages ≈129–131 ≈ dense, full-chip data — consistent with 16-bit signed PCM filling all 16 MB.
  **These four constants are a concrete, achievable pass/fail target for placeholders.**
- **"BANK 0-15"** (Fig.30 p.34, "MAIN TG BANK 0-15 ROM") = the internal 16 M-word window in 16 × 1 M-word
  banks (window bits 23:20; 2 MB per bank across the pair, 1 MB per chip).
- **Tests 4–19 = wave-expansion boards**: window regions **0x02000000 / 0x02800000 / 0x03000000 /
  0x03800000** (pages 0x400/0x500/0x600/0x700 → page-register bits 10:8 select the fetch source: 0 =
  internal CE, 4–7 = the EXACEX/Y-style expansion enables from the 2-to-4 demux, sheet 7). Sizes and
  expected sums come from **board-resident descriptors read over the CPU bus** (`*(0x570001E8..F4)`,
  `*(0x560001E8..F4)`; length unit = count<<17 words, 0x48483B2C).
- UI: **MainWaveRomTestFunc 0x484A2E3A** (kn7000.sym:700) runs idx 0,1,2,3 and writes OK/NG to widgets
  0x010000F7/F8/**FA/F9** + banner 0xFB (0x484A2E62–0x484A2FE3).

**Flag — main/sub ↔ IC-pair assignment is not fully settled.** The screen row order is "MAIN … IC203, IC204"
then "SUB … IC207, IC208" (p.34), but tests 0/1 (the *first* widget pair F7/F8) hit **0x98050000** — if the
widgets are laid out in screen order, IC203/IC204 belong to the 0x9805 TG, inverting the current
"main=0x98040000" convention. Resolution needs the dialog resource for widgets 0xF7–0xFB. For fabrication
this only affects which file gets which ballast target, and it is **self-correcting**: run the WAVE ROM test
in MAME and see which fields read OK/NG.

### 1.3 Where the waveform directory lives

- **The firmware never reads wave data at runtime.** Grep of the full disassembly: `0x9804000A`/`0x9805000A`
  (and +6/+8) appear *only* inside the checksum routine (program.asm:212546–212654). Normal playback never
  CPU-reads samples or in-ROM descriptors.
- **All CPU-side sound parameters live in the "JK" chunk of the table ROM**: directory entry [6] at
  **0x48000018** → chunk **0x4806EA98** (tag `4A 4B` "JK", ≈0xCB450 bytes; next dir entry 0x48139EE8). The
  boot-time source-selection routine at **0x48449EF4** caches the chunk base and its header sub-pointers
  (+0x14, +0x18 → pointer blocks at chunk+0xB2234/+0xB2288, containing offset directories and what looks
  like an ~0x473-entry per-sound offset table) into globals 0x5003A554…0x5003A5A8. The chunk body begins with
  20-byte sound-ID records (BCD-like ID, flags 0x0020, sequential index).
- **Wave-expansion boards prove the split**: a board carries (a) TG-visible wave data on the 80-pin
  connectors and (b) a **CPU-visible flash** (0x57000000 / 0x56000000) whose header is: +0x00 u32 = 0x200
  (data start), +0x04/+0x08 → two 16-char ID strings (validated char-by-char against class table 0x485B8518),
  +0x0C → **the board's own JK sound-parameter chunk**, +0x1E8..0x1F4 → wave-set {size, checksum} descriptors
  (0x48449EF4–0x4844A179). I.e. Technics ships the *parameters* on the CPU bus and only PCM on the TG bus —
  strong evidence that for internal sounds, too, **start/loop/pitch parameters are delivered to the TG via
  register writes from CPU-side tables, not read from an in-ROM directory by the CPU**.
- Whether the **TG chip itself** dereferences an in-ROM index (KN5000-style) cannot be proven from firmware.
  The KN5000 template (`/home/fsanches/compartilhado/kn5000-docs/waveform-rom-format.md`): 198-entry index at
  ROM offset 0 `{param_ptr, wave_offset×16 bytes}`, variable-length key-zone/loop param records
  (flags 0x40 = possible loop marker, 0x80 = end), signed 16-bit LE PCM, and **entry 0 = a perfect 256-sample
  sine** (lines 34–121). Under the integrity policy this is a **cross-model hypothesis only**.

### 1.4 What a KN7000 waveform descriptor contains — honest status

**Not found yet.** No note-on TG register sequence has ever been captured (playback is trigger-gated in MAME:
`kn7000_mame/notes/tone-generator.md:129–152`), and `MainSoundAdd` (0x4848C043) has **zero direct call
sites** in the linear disassembly (dispatched indirectly). Known KN7000-native facts about the register
interface: writes are 32-bit {addr16→base+0, data16→base+2} pairs (helper 0x487EFF92, with a 6-bit field ORed
at word bits 20–25); boot init writes register groups 0x04/0x0C across all 64 channels; the 0xFC0x group is a
periodic system refresh; +4 = keybed event FIFO; +6/8/A = readback window; +0xE = routing latch. The
waveform-select / start-address / loop registers are **unidentified** — the KN5000 map (pitch-increment,
velocity-latch, waveform-control groups; `kn5000-docs/waveform-rom-format.md:123–139`) is the working
template. The first captured note-on (Chord-Finder plan, sound-subsystem-plan.md Phase C) or a SOUND SYSTEM
test run in MAME will pin them.

### 1.5 The service SOUND SYSTEM sine test (pp.34–35, §8.10; §11.1 p.41)

Mode 1 plays a **full-amplitude sine at each key's pitch; C keys exercise IC203&204, C# keys IC207&208** —
one sine exercises **both chips of a pair**, which is the behavioral confirmation of the word-interleave
(§1.1): adjacent samples alternate chips (dual AWAX/AWAY fetch = simultaneous sample-pair read, presumably
for hardware interpolation). The diagnostic window proc (**SineWaveWindowProc 0x484A302F**, kn7000.sym:702)
is UI-only: key-name display via note%12 → string table 0x4860D28C, mode-select 0–5 handler 0x484A3151; the
sine is triggered through the normal engine with a diagnostic patch whose parameters come from the CPU side.
So the sine's exact ROM address is **not hardcoded in the test UI** — it will show up in the driver's
existing `m_tg_reg` capture (kn7000.cpp:239) when the test runs.

---

## 2. MINIMAL PLACEHOLDER SPEC

### 2.1 Strategy: address-agnostic content

Since we cannot yet know which start addresses the firmware programs, the placeholder must sound right **from
any address**: tile the entire wave space with single-cycle waveforms so that any {start, loop} the TG lands
on yields a clean periodic tone. This makes both targets — (a) the diagnostic sine and (b) "the home-screen
patch produces SOMETHING" — satisfiable without knowing the descriptor format.

### 2.2 Per-TG master image (16 M words = 32 MB), then split by parity

| window words | content |
|---|---|
| 0x000000–0x0007FF | **KN5000-style directory** (198×4B index @0 + minimal param records), entry 0 → the sine tile base — pure insurance in case the TG hardware reads an in-ROM index; explicitly speculative |
| 0x000800–0x000FFF | ASCII provenance block (see §4) |
| bank 0 remainder | **256-word full-amplitude sine cycle, tiled** (±30000; at 44.1 kHz untransposed ≈172 Hz root — the TG pitch-increments to each key) |
| banks 1–13 | one distinct timbre per bank, tiled: saw, triangle, pulse 25/50%, sine+3rd harmonic, detuned pairs, … — **bank-identifying timbres** so any captured-but-unmapped address is audibly identifiable |
| bank 14 | one-shot stand-in: exponentially decaying noise bursts (drum-ish) at every 0x4000-word boundary |
| bank 15 | quiet sine tile + **checksum-ballast area** (tool-adjusted words so the file's byte-sum can hit the §1.2 constants exactly, only with `--match-checksums`) |
| every bank start +0x40 | 64-word ASCII marker "SYNTHETIC bank NN" (an audible click is acceptable — and diagnostic — in a placeholder) |

Split: `chip_even[i] = master[2i]`, `chip_odd[i] = master[2i+1]` → each file is 8 M words = **16,777,216
bytes, exactly the real 128-Mbit chip size**. Each chip then carries a 128-word version of each cycle, and
the pair reassembles to the intended waveform whichever parity↔chip polarity the silicon uses (worst case:
one-sample skew, inaudible for a placeholder).

### 2.3 Full-size vs sparse

- **The checksum test always sweeps all 16 M words per pair** (start 0, end 0x00FFFFFF — §1.2); there is no
  in-ROM size field for internal ROMs. Truncated images ⇒ the unmapped tail reads as bus default ⇒ NG.
- **Playback does not care**: for sound experiments a small (e.g. 2 MB) image mirrored by the MAME handler is
  fine.
- Recommendation: **emit full 16 MiB files** (tiled content compresses to almost nothing in a zip) so one
  artifact serves both purposes. Two modes:
  - default: **checksums intentionally NOT matched** → WAVE ROM test honestly reports NG (integrity-friendly);
  - `--match-checksums`: ballast solved so all four tests report OK — used only to exercise/verify the
    readback-window emulation end-to-end.

### 2.4 File ↔ chip assignment (provisional)

`kn7000_wave_ic204_placeholder.bin` = TG-A even, `…ic203…` = TG-A odd, `…ic208…` = TG-B even, `…ic207…` =
TG-B odd, where TG-A = 0x98040000 and TG-B = 0x98050000 under the current convention — **both the main/sub↔IC
question (§1.2 flag) and even/odd↔AWAX/AWAY are provisional**. The manifest records the mapping; a MAME run
of the WAVE ROM test disambiguates empirically (four distinct sums ⇒ each OK/NG field identifies its file).

---

## 3. GENERATION APPROACH

### 3.1 Tool: `tools/make_placeholder_waveroms.py` (proposed home: kn7000_disassembly/tools/)

~150 lines, numpy int16. Pipeline per TG: build the 16 M-word master (bank plan from a small table in the
script or a YAML), stamp directory + provenance + markers, optionally solve ballast (byte-sum of word w is
`(w>>8)+(w&0xFF)`, so e.g. 0xFFFF contributes 510 and 0x0000 contributes 0 — fill k ballast words with 0xFFFF
plus one remainder word; exact-solve is trivial since targets and content sums are 32-bit integers), split
parities, write four `.bin` + `manifest.json` (generation date, git rev, parameters, per-file sha1, the
provisional chip mapping, and `"synthetic": true`). Sine amplitude ±30000 (diag mode 1 is "full amplitude",
p.34; keep 10% headroom).

### 3.2 MAME loading

Replace the commented stanza at `kn7000_mame/src/mame/matsushita/kn7000.cpp:1534–1538` — **note its 0x400000
sizes are wrong** (KN5000 values; the real chips are 128 Mbit = 0x1000000 each, service manual pp.54–55):

```
ROM_REGION16_LE( 0x2000000, "wave_a", ROMREGION_ERASE00 )   // TG @0x98040000, window-word order
ROM_LOAD32_WORD( "kn7000_wave_ic204_placeholder.bin", 0x000000, 0x1000000, BAD_DUMP CRC(...) ) // SYNTHETIC
ROM_LOAD32_WORD( "kn7000_wave_ic203_placeholder.bin", 0x000002, 0x1000000, BAD_DUMP CRC(...) ) // SYNTHETIC
ROM_REGION16_LE( 0x2000000, "wave_b", ROMREGION_ERASE00 )   // TG @0x98050000
ROM_LOAD32_WORD( "kn7000_wave_ic208_placeholder.bin", 0x000000, 0x1000000, BAD_DUMP CRC(...) )
ROM_LOAD32_WORD( "kn7000_wave_ic207_placeholder.bin", 0x000002, 0x1000000, BAD_DUMP CRC(...) )
```

`ROM_LOAD32_WORD` interleaving reproduces the window-word order directly, so **window word W = region
u16[W]**.

- **Readback-window handler** (new, next to the existing io_w cases at kn7000.cpp:473–479): latch base+6
  (page, honor bit15 enable) and base+8 (offset); read base+0xA returns
  `region16[((page & 0x1FF) << 15) | (offset & 0x7FFF)]` for pages <0x200, expansion pages 0x400+ return
  0xFFFF (no boards). Acceptance test: the service WAVE ROM test completes and reports the expected
  OK/NG pattern.
- **Future TG sound_stream**: per-voice fetch keeps a 24-bit sample position `n` per port; the interpolation
  pair is `region16[(n<<1)|0]` and `region16[(n<<1)|1]` (or per-port addressing once the real X/Y semantics
  are captured); register semantics filled in from the `m_tg_reg` capture as Phase C lands. Template device:
  `git show kn5000_research_tonegen:src/mame/matsushita/kn5000_tonegen.cpp` in ~/compartilhado/mame.

### 3.3 Validation loop (all inside MAME, no hardware risk)

1. Load placeholders → run WAVE ROM test (service mode via the `TestModeFunc 0x484A497B` force-call
   workaround) → confirms the window model and pins the file↔IC assignment.
2. Run SOUND SYSTEM test mode 1, press keys via the already-working keybed FIFO (kn7000.cpp `kbd_push`) →
   the captured TG writes reveal the sine's real bank/address and the waveform-select register — **the first
   KN7000-native descriptor evidence** — then refine the placeholder layout to put proper content at the real
   addresses.

---

## 4. RISKS — what we cannot know without the real ROMs, and anti-confusion measures

**Unknowable until dumps or captures exist:**
- **Sample encoding**: 16-bit signed linear PCM is the KN5000-dumped precedent and fits the 16-bit AWD bus
  and the ~129–131 average-byte checksums, but companded/DPCM formats are not excluded. Placeholder assumes
  linear; if wrong, output is distorted-but-present (acceptable for a placeholder).
- **In-ROM index existence & format**: the embedded KN5000-style directory is insurance, not fact; the TG may
  ignore ROM offset 0 entirely (and the interleave means "offset 0" spans both chips anyway).
- **Loop metadata location** (TG registers vs in-ROM records) and the waveform-select register encoding
  (§1.4 "not found").
- **X/Y↔parity and IC↔TG-port assignment** (§1.2 flag) — affects labeling only, self-correcting in MAME.
- The real ROMs' actual content layout — nothing transfers from placeholders to preservation claims.

**Keeping placeholders unmistakably synthetic** (per the cross-model/ROM-integrity policy):
- filenames carry `_placeholder`; `BAD_DUMP` flag + `// SYNTHETIC — generated, NOT read from hardware`
  comments in ROM_START; never presented under the bare mask-ROM part numbers C3CBQD00000x;
- embedded ASCII provenance in every bank ("KN7000 SYNTHETIC PLACEHOLDER WAVE ROM — NOT A DUMP — generated
  <date> — kn7000_disassembly/tools/make_placeholder_waveroms.py"), so even a hexdump of a stray copy
  self-identifies;
- `manifest.json` with sha1s published beside the files and mirrored into `kn7000_mame/notes/` so the
  synthetic hashes are on record before anyone can confuse them with future real dumps;
- default build **fails** the WAVE ROM checksum test (honest NG); the sum-matched variant is opt-in, clearly
  named (e.g. `…_placeholder_sumfix.bin`), and exists only to exercise the test path;
- when the real IC203/204/207/208 dumps arrive (Phase G readback-window dump or desolder campaign,
  sound-subsystem-plan.md:299–322), the placeholders are deleted from the ROM set, not kept as fallbacks.