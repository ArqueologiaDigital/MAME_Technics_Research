# KN5000 tone-gen (IC303 / TC183C230002) — LIVE ground-truth capture dataset

Author: autonomous live-capture pass, 2026-07-23. Requested by Felipe Sanches.
**Capture only** — no `src/` edits, no rebuild. All instrumentation was runtime-only
(MAME lua write-taps on the sub-CPU bus + RAM reads), run in an isolated scratchpad rundir
with a **copy** of the pre-init nvram; `kn7000-emulator/nvram` (owner's live state) was never
touched. The only tracked change is this note.

This is the empirical dataset the whole waveform-decode rests on: for **all 16 panel
SOUND-GROUP instruments** (both button rows CPR_SEG1 + CPR_SEG2), across **7 notes spanning the
keyboard** (C2 C3 C4 E4 G4 C5 C6), the full note-on register-write stream the firmware sends to
IC303 (address latch 0x100000 / data 0x100002) plus the part-0 sub-CPU tonerec behind it.

Evidence labels: **MEASURED** (read live from the running machine), **INFERRED** (deduction from
the measured data), **SPECULATIVE**. Builds on / **corrects** `kn5000-voice-pipeline.md`,
`kn5000-wave-number.md`, `kn5000-tonegen-register-semantics.md`.

Sources: built driver `/home/fsanches/compartilhado/kn7000_mame_build/kn7000`, roms
`kn7000-emulator/roms`, isolated copy of the pre-init nvram (boots to the PMEM play screen:
RIGHT1=Piano, RIGHT2=Bigband Brass, LEFT=Modern E.P.). Sub-CPU disasm cross-refs =
`kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`.

---

## 0. TL;DR / what changed vs prior notes

* **All 16 SOUND-GROUP instruments captured LIVE**, each with a distinct part-0 tonerec SET
  index and a distinct IC303 register fingerprint (§2, §3). Instruments 7-16 were never captured
  live before this pass; here they are.
* **The per-instrument identity is register +0x040** = `{ high nibble = partial CLASS/bus, low
  byte = multisample KEY-ZONE }`, plus the instrument-constant **timbre triple +0x0C0 / +0x140 /
  +0x500**. Confirmed for all 16 (§3). The +0x040 low byte steps as the played note crosses split
  points (§5). This is fully within the chip boundary (register inputs only).
* **CORRECTION #1 — `+0x440` is NOT `0` for all instruments.** Prior notes tested only
  Piano/Brass/Guitar/Strings/Organ and concluded "wave-number 0 for everything". FALSE in
  general: the **extended-path instruments — FLUTE, SAX & REED, WORLD PERC, ORGAN & ACCORDION,
  GM SPECIAL — write a NONZERO +0x440** (0x0040..0x00CD range) and additionally program the
  extended register set +0x540/+0x580/+0x5C0/+0x600/+0x640/+0x1C0 (§6, §7).
* **CORRECTION #2 — that nonzero +0x440 is NOT a wave/instrument selector.** DECISIVE test
  (§6): playing the **same note C4 five times** on FLUTE holds +0x040=0x5000 and pitch
  +0x400=0x3FA8 CONSTANT while **+0x440 increments 0x40→0x41→0x42→0x43→0x44 per note-on**,
  tracking the allocated voice channel. So +0x440's low byte is a **per-note-on rotating
  voice/DMA-slot counter**; its top bits are the bank (`tonerec[+0x1a] & 0xC0`). It carries no
  per-pitch or per-instrument waveform identity — reinforcing that the HLE must select the
  waveform from +0x040 (+ timbre triple), never +0x440.
* The SET index is **scoped per sound-group, not global**: PIANO and DRUM KITS both read SET
  0x00; STRINGS & VOCAL and ORCHESTRAL PAD both read SET 0x64 — yet their register fingerprints
  differ (§2/§3). The class nibble is likewise shared across instruments (class 0x3 = Guitar,
  Sax, World Perc, GM Special; class 0x0 = Strings, Orch Pad, Synth), so neither SET nor class
  alone identifies a voice; the timbre triple disambiguates.

---

## 1. Method (MEASURED)

Two write-taps reconstruct the exact ordered stream to IC303: 0x100000 latches the 16-bit
register address, 0x100002 the 16-bit data. `addr = (group<<8)|(bank<<6)|channel` (channel =
voice 0..63). Logging is **gated to a 12-frame window right after each note-on**, which excludes
the 64-channel note-OFF bus-gain sweep and captures the note-ON burst cleanly. Per instrument the
part-0 tonerec (`0x041368 + 0x6E`) is dumped once. Instruments are selected by driving the panel
SOUND-GROUP buttons for the (default-selected) RIGHT1 part; notes are pressed on the 61-key bed.

Two capture disciplines learned this pass (both were silent-failure traps):
1. **Press only after t≈9 s.** Note-ons before the voice/tone finishes loading program +0x040=0
   (a null voice). At t≥9 s Piano C4 gives the real 0x7007.
2. **The voice allocator marches monotonically up all 64 channels and does not free within a
   run** (release tails hold channels). >~60 note-ons exhaust polyphony and later note-ons are
   silently dropped. Captured in **4 short runs of ≤4 instruments** (≤56 channels) to stay under
   the 64-voice pool. The first instrument of a slice can miss its button press (fires exactly at
   the boot-settle frame) and stay on the default Piano — each instrument here is taken from a run
   where it was NOT first (verified: distinct SET index + fingerprint).

---

## 2. Per-instrument part-0 tonerec (SET index + bank fields) — MEASURED

`SET` = `ptr[0]+0x02` (the multisample-set selector consumed by `LABEL_032682`→`03248B`).
`pb0a` = `part_base[+0x0a]` (bit15 → §4 wave-fallback path). `tr1a` = `tonerec[+0x1a]` (bank;
`&0xC0` becomes the top bits of +0x440). `ptr0` = first delivered partial pointer (sub-CPU DRAM).

| # | instrument | SOUND-GROUP button | SET | pb0a | tr1a | ptr0 |
|---|---|---|---|---|---|---|
| 0 | PIANO | CPR_SEG2 0x01 | 0x00 | 0x0004 | 0x0000 | 0x05253A |
| 1 | GUITAR | CPR_SEG2 0x02 | 0x14 | 0x0004 | 0x0000 | 0x054A5D |
| 2 | STRINGS & VOCAL | CPR_SEG2 0x04 | 0x64 | 0x0004 | 0x0000 | 0x056E3C |
| 3 | BRASS | CPR_SEG2 0x08 | 0x38 | 0x0004 | 0x0000 | 0x05B66C |
| 4 | FLUTE | CPR_SEG2 0x10 | 0x40 | 0x0004 | 0x0040 | 0x05DB8F |
| 5 | SAX & REED | CPR_SEG2 0x20 | 0x4C | 0x0004 | 0x00C0 | 0x05C791 |
| 6 | MALLET & ORCH PERC | CPR_SEG2 0x40 | 0x09 | 0x0004 | 0x0000 | 0x053938 |
| 7 | WORLD PERC | CPR_SEG2 0x80 | 0x1F | 0x0004 | 0x0040 | 0x055D92 |
| 8 | ORGAN & ACCORDION | CPR_SEG1 0x01 | 0x58 | 0xC004 | 0x0000 | 0x05A037 |
| 9 | ORCHESTRAL PAD | CPR_SEG1 0x02 | 0x64 | 0x0004 | 0x0000 | 0x0642AF |
| 10 | SYNTH | CPR_SEG1 0x04 | 0x79 | 0x0004 | 0x0000 | 0x061279 |
| 11 | BASS | CPR_SEG1 0x08 | 0x2B | 0x0004 | 0x0000 | 0x05EFDE |
| 12 | DIGITAL DRAWBAR | CPR_SEG1 0x10 | 0x88 | 0x0004 | 0x0000 | 0x090723 |
| 13 | ACCORDION REGISTER | CPR_SEG1 0x20 | 0x51 | 0x0004 | 0x0000 | 0x0588BE |
| 14 | GM SPECIAL | CPR_SEG1 0x40 | 0x70 | 0xC004 | 0x0000 | 0x060C49 |
| 15 | DRUM KITS | CPR_SEG1 0x80 | 0x00 | 0x8004 | 0x0000 | 0x075A48 |

Note the collisions: PIANO/DRUM KITS share SET 0x00; STRINGS & VOCAL/ORCHESTRAL PAD share SET
0x64 (SET is per-group-scoped). Nonzero `tr1a` (FLUTE 0x40, SAX 0xC0, WORLD PERC 0x40) and
`pb0a` bit15 (ORGAN 0xC004, GM SPECIAL 0xC004, DRUM KITS 0x8004) mark the instruments that take
the extended / wave-fallback path and emit nonzero +0x440 (§6).

---

## 3. Canonical C4 register fingerprint — MEASURED (osc1 voice)

`+040` = class·zone (osc1). `+040b` = osc2 layer (blank = single-oscillator voice). Timbre triple
`+0C0 / +140 / +500` is instrument-constant across notes. `+440` = osc1 wave-number reg (rotating
slot, §6). `ext` = extended register set present.

| instrument | class | +040 | +040b | +0C0 | +140 | +500 | +440 | ext |
|---|---|---|---|---|---|---|---|---|
| PIANO | 7 | 7007 | 7017 | 7400 | 6FDA | 2C68 | 0000 |  |
| GUITAR | 3 | 3002 | — | 5A00 | 6FD7 | 2C60 | 0000 |  |
| STRINGS & VOCAL | 0 | 0077 | 0089 | 7F00 | 7F58 | 7F7F | 0000 |  |
| BRASS | 1 | 1007 | — | 5A00 | 66D8 | 007F | 0000 |  |
| FLUTE | 5 | 5000 | — | 5A00 | 7F58 | 7F7F | 0042 | EXT |
| SAX & REED | 3 | 313E | 409B | 6E00 | 6648 | 7F7F | 00C2 | EXT |
| MALLET & ORCH PERC | 2 | 2096 | 5089 | 5A00 | 66DA | 2C7F | 0000 |  |
| WORLD PERC | 3 | 30C7 | — | 5A00 | 7F58 | 7F7F | 0049 | EXT |
| ORGAN & ACCORDION | 4 | 4002 | 4002 | 5A00 | 66C7 | 7F7F | 00C9 | EXT |
| ORCHESTRAL PAD | 0 | 0075 | 0085 | 7F00 | 6629 | 007F | 0000 |  |
| SYNTH | 0 | 001B | 001B | 5A00 | 7F58 | 4D7F | 0000 |  |
| BASS | 1 | 109C | — | 4600 | 7F25 | 7F60 | 0000 |  |
| DIGITAL DRAWBAR | 6 | 6096 | 6288 | 007F | 6631 | 007F | 0000 |  |
| ACCORDION REGISTER | 4 | 4058 | 4061 | 5A00 | 66D8 | 7F7F | 0000 |  |
| GM SPECIAL | 3 | 3112 | 3112 | 5A00 | 7F58 | 2C7F | 00C2 | EXT |
| DRUM KITS | 5 | 5069 | — | 5A00 | 7F5F | 0000 | 0000 |  |

Class nibble (high nibble of +040) observed across the set spans **0x0..0x7** (prior notes only
saw 0/1/3/4/7): 0=Strings/OrchPad/Synth, 1=Brass/Bass, 2=Mallet, 3=Guitar/Sax/World/GM,
4=Organ/Accordion, 5=Flute/Drums, 6=Digital Drawbar, 7=Piano.

---

## 4. Full per-note dataset — MEASURED (osc1 voice unless noted)

Columns: played channel `ch`, `+040`(osc1) / `+040b`(osc2), timbre triple, `+400` note log-pitch,
`+440`(osc1)/`+440b`(osc2) wave-slot reg, `+480`(osc2 wave-slot), `ext`.

### PIANO  (SET 0x00, button CPR_SEG2 0x01)

| note | ch | +040 | +040b | +0C0 | +140 | +500 | +400 | +440 | +440b | +480 | ext |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C2 | 0 (+1 osc) | 7001 | 7011 | 7400 | 6FDA | 2C68 | 1DCE | 0000 | 0000 | 0000 |  |
| C3 | 2 (+1 osc) | 7004 | 7014 | 7400 | 6FDA | 2C68 | 28E8 | 0000 | 0000 | 0000 |  |
| C4 | 4 (+1 osc) | 7007 | 7017 | 7400 | 6FDA | 2C68 | 34C1 | 0000 | 0000 | 0000 |  |
| E4 | 6 (+1 osc) | 7008 | 7018 | 7400 | 6FDA | 2C68 | 35EC | 0000 | 0000 | 0000 |  |
| G4 | 8 (+1 osc) | 7008 | 7018 | 7400 | 6FDA | 2C68 | 38EC | 0000 | 0000 | 0000 |  |
| C5 | 10 (+1 osc) | 700A | 701A | 7400 | 6FDA | 2C68 | 41AD | 0000 | 0000 | 0000 |  |
| C6 | 12 (+1 osc) | 700D | 701D | 7400 | 6FDA | 2C68 | 4CB4 | 0000 | 0000 | 0000 |  |

### GUITAR  (SET 0x14, button CPR_SEG2 0x02)

| note | ch | +040 | +040b | +0C0 | +140 | +500 | +400 | +440 | +440b | +480 | ext |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C2 | 14 | 3000 | — | 5A00 | 6FD7 | 2C60 | 2480 | 0000 | — | 0000 |  |
| C3 | 15 | 3001 | — | 5A00 | 6FD7 | 2C60 | 3080 | 0000 | — | 0000 |  |
| C4 | 16 | 3002 | — | 5A00 | 6FD7 | 2C60 | 3C80 | 0000 | — | 0000 |  |
| E4 | 17 | 3002 | — | 5A00 | 6FD7 | 2C60 | 4080 | 0000 | — | 0000 |  |
| G4 | 18 | 3002 | — | 5A00 | 6FD7 | 2C60 | 4380 | 0000 | — | 0000 |  |
| C5 | 19 | 3003 | — | 5A00 | 6FD7 | 2C60 | 4880 | 0000 | — | 0000 |  |
| C6 | 20 | 3003 | — | 5A00 | 6FD7 | 2C60 | 5480 | 0000 | — | 0000 |  |

### STRINGS & VOCAL  (SET 0x64, button CPR_SEG2 0x04)

| note | ch | +040 | +040b | +0C0 | +140 | +500 | +400 | +440 | +440b | +480 | ext |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C2 | 21 (+1 osc) | 0073 | 0083 | 7F00 | 7F58 | 7F7F | 1C86 | 0000 | 0000 | 0000 |  |
| C3 | 23 (+1 osc) | 0075 | 0085 | 7F00 | 7F58 | 7F7F | 2B93 | 0000 | 0000 | 0000 |  |
| C4 | 25 (+1 osc) | 0077 | 0089 | 7F00 | 7F58 | 7F7F | 31A6 | 0000 | 0000 | 0000 |  |
| E4 | 27 (+1 osc) | 0079 | 0089 | 7F00 | 7F58 | 7F7F | 3B7E | 0000 | 0000 | 0000 |  |
| G4 | 29 (+1 osc) | 007B | 008B | 7F00 | 7F58 | 7F7F | 38A0 | 0000 | 0000 | 0000 |  |
| C5 | 31 (+1 osc) | 007B | 008D | 7F00 | 7F58 | 7F7F | 3DA0 | 0000 | 0000 | 0000 |  |
| C6 | 33 (+1 osc) | 007F | 0091 | 7F00 | 7F58 | 7F7F | 4986 | 0000 | 0000 | 0000 |  |

### BRASS  (SET 0x38, button CPR_SEG2 0x08)

| note | ch | +040 | +040b | +0C0 | +140 | +500 | +400 | +440 | +440b | +480 | ext |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C2 | 35 | 1006 | — | 5A00 | 66D8 | 007F | 0DA8 | 0000 | — | 0000 |  |
| C3 | 36 | 1006 | — | 5A00 | 66D8 | 007F | 19A8 | 0000 | — | 0000 |  |
| C4 | 37 | 1007 | — | 5A00 | 66D8 | 007F | 2A97 | 0000 | — | 0000 |  |
| E4 | 38 | 1007 | — | 5A00 | 66D8 | 007F | 2E97 | 0000 | — | 0000 |  |
| G4 | 39 | 1008 | — | 5A00 | 66D8 | 007F | 2DB0 | 0000 | — | 0000 |  |
| C5 | 40 | 1009 | — | 5A00 | 66D8 | 007F | 388C | 0000 | — | 0000 |  |
| C6 | 41 | 100B | — | 5A00 | 66D8 | 007F | 448C | 0000 | — | 0000 |  |

### FLUTE  (SET 0x40, button CPR_SEG2 0x10)

| note | ch | +040 | +040b | +0C0 | +140 | +500 | +400 | +440 | +440b | +480 | ext |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C2 | 42 | 5000 | — | 5A00 | 7F58 | 7F7F | 27A8 | 0040 | — | 0000 | EXT |
| C3 | 43 | 5000 | — | 5A00 | 7F58 | 7F7F | 33A8 | 0041 | — | 0000 | EXT |
| C4 | 44 | 5000 | — | 5A00 | 7F58 | 7F7F | 3FA8 | 0042 | — | 0000 | EXT |
| E4 | 45 | 5000 | — | 5A00 | 7F58 | 7F7F | 43A8 | 0043 | — | 0000 | EXT |
| G4 | 46 | 5000 | — | 5A00 | 7F58 | 7F7F | 46A8 | 0044 | — | 0000 | EXT |
| C5 | 47 | 5000 | — | 5A00 | 7F58 | 7F7F | 4BA8 | 0045 | — | 0000 | EXT |
| C6 | 48 | 5002 | — | 5A00 | 7F58 | 7F7F | 5A4D | 0046 | — | 0000 | EXT |

### SAX & REED  (SET 0x4C, button CPR_SEG2 0x20)

| note | ch | +040 | +040b | +0C0 | +140 | +500 | +400 | +440 | +440b | +480 | ext |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C2 | 14 (+1 osc) | 313F | 409B | 6E00 | 6648 | 7F7F | 2480 | 00C0 | 0040 | 0000 | EXT |
| C3 | 16 (+1 osc) | 3140 | 409B | 6E00 | 6648 | 7F7F | 3080 | 00C1 | 0041 | 0000 | EXT |
| C4 | 18 (+1 osc) | 313E | 409B | 6E00 | 6648 | 7F7F | 3C80 | 00C2 | 0042 | 0000 | EXT |
| E4 | 20 (+1 osc) | 3141 | 409B | 6E00 | 6648 | 7F7F | 4080 | 00C3 | 0043 | 0000 | EXT |
| G4 | 22 (+1 osc) | 3141 | 409B | 6E00 | 6648 | 7F7F | 4380 | 00C4 | 0044 | 0000 | EXT |
| C5 | 24 (+1 osc) | 3142 | 409B | 6E00 | 6648 | 7F7F | 4880 | 00C5 | 0045 | 0000 | EXT |
| C6 | 26 (+1 osc) | 3144 | 409B | 6E00 | 6648 | 7F7F | 5480 | 00C6 | 0046 | 0000 | EXT |

### MALLET & ORCH PERC  (SET 0x09, button CPR_SEG2 0x40)

| note | ch | +040 | +040b | +0C0 | +140 | +500 | +400 | +440 | +440b | +480 | ext |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C2 | 28 (+1 osc) | 2097 | 5089 | 5A00 | 66DA | 2C7F | 3080 | 0000 | 0000 | 0000 |  |
| C3 | 30 (+1 osc) | 2097 | 5089 | 5A00 | 66DA | 2C7F | 3C80 | 0000 | 0000 | 0000 |  |
| C4 | 32 (+1 osc) | 2096 | 5089 | 5A00 | 66DA | 2C7F | 4880 | 0000 | 0000 | 0000 |  |
| E4 | 34 (+1 osc) | 2096 | 5089 | 5A00 | 66DA | 2C7F | 4C80 | 0000 | 0000 | 0000 |  |
| G4 | 36 (+1 osc) | 2096 | 5089 | 5A00 | 66DA | 2C7F | 4F80 | 0000 | 0000 | 0000 |  |
| C5 | 38 (+1 osc) | 2098 | 5089 | 5A00 | 66DA | 2C7F | 5480 | 0000 | 0000 | 0000 |  |
| C6 | 40 (+1 osc) | 209A | 5089 | 5A00 | 66DA | 2C7F | 6080 | 0000 | 0000 | 0000 |  |

### WORLD PERC  (SET 0x1F, button CPR_SEG2 0x80)

| note | ch | +040 | +040b | +0C0 | +140 | +500 | +400 | +440 | +440b | +480 | ext |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C2 | 42 | 30C6 | — | 5A00 | 7F58 | 7F7F | 2480 | 0047 | — | 0000 | EXT |
| C3 | 43 | 30C6 | — | 5A00 | 7F58 | 7F7F | 3080 | 0048 | — | 0000 | EXT |
| C4 | 44 | 30C7 | — | 5A00 | 7F58 | 7F7F | 3C80 | 0049 | — | 0000 | EXT |
| E4 | 45 | 30C7 | — | 5A00 | 7F58 | 7F7F | 4080 | 004A | — | 0000 | EXT |
| G4 | 46 | 30C7 | — | 5A00 | 7F58 | 7F7F | 4380 | 004B | — | 0000 | EXT |
| C5 | 47 | 30C7 | — | 5A00 | 7F58 | 7F7F | 4880 | 004C | — | 0000 | EXT |
| C6 | 48 | 30C7 | — | 5A00 | 7F58 | 7F7F | 5480 | 004D | — | 0000 | EXT |

### ORGAN & ACCORDION  (SET 0x58, button CPR_SEG1 0x01)

| note | ch | +040 | +040b | +0C0 | +140 | +500 | +400 | +440 | +440b | +480 | ext |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C2 | 21 (+1 osc) | 4001 | 4001 | 5A00 | 66C7 | 7F7F | 2480 | 00C7 | 0047 | 0040 | EXT |
| C3 | 23 (+1 osc) | 4001 | 4001 | 5A00 | 66C7 | 7F7F | 3080 | 00C8 | 0048 | 0041 | EXT |
| C4 | 25 (+1 osc) | 4002 | 4002 | 5A00 | 66C7 | 7F7F | 3C80 | 00C9 | 0049 | 0042 | EXT |
| E4 | 27 (+1 osc) | 4002 | 4002 | 5A00 | 66C7 | 7F7F | 4080 | 00CA | 004A | 0043 | EXT |
| G4 | 29 (+1 osc) | 4002 | 4002 | 5A00 | 66C7 | 7F7F | 4380 | 00CB | 004B | 0044 | EXT |
| C5 | 31 (+1 osc) | 4003 | 4003 | 5A00 | 66C7 | 7F7F | 4880 | 00CC | 004C | 0045 | EXT |
| C6 | 33 (+1 osc) | 4003 | 4003 | 5A00 | 66C7 | 7F7F | 5480 | 00CD | 004D | 0046 | EXT |

### ORCHESTRAL PAD  (SET 0x64, button CPR_SEG1 0x02)

| note | ch | +040 | +040b | +0C0 | +140 | +500 | +400 | +440 | +440b | +480 | ext |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C2 | 14 (+3 osc) | 0073 | 0083 | 7F00 | 6629 | 007F | 108C | 0000 | 0000 | 0000 |  |
| C3 | 18 (+3 osc) | 0073 | 0083 | 7F00 | 6629 | 007F | 1C8C | 0000 | 0000 | 0000 |  |
| C4 | 22 (+3 osc) | 0075 | 0085 | 7F00 | 6629 | 007F | 2B99 | 0000 | 0000 | 0000 |  |
| E4 | 26 (+3 osc) | 0075 | 0085 | 7F00 | 6629 | 007F | 2F99 | 0000 | 0000 | 0000 |  |
| G4 | 30 (+3 osc) | 0077 | 0087 | 7F00 | 6629 | 007F | 2CAC | 0000 | 0000 | 0000 |  |
| C5 | 34 (+3 osc) | 0077 | 0089 | 7F00 | 6629 | 007F | 31AC | 0000 | 0000 | 0000 |  |
| C6 | 38 (+3 osc) | 007B | 008D | 7F00 | 6629 | 007F | 3DA6 | 0000 | 0000 | 0000 |  |

### SYNTH  (SET 0x79, button CPR_SEG1 0x04)

| note | ch | +040 | +040b | +0C0 | +140 | +500 | +400 | +440 | +440b | +480 | ext |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C2 | 42 (+1 osc) | 0019 | 0019 | 5A00 | 7F58 | 4D7F | 248A | 0000 | 0000 | 0000 |  |
| C3 | 44 (+1 osc) | 0019 | 0019 | 5A00 | 7F58 | 4D7F | 308A | 0000 | 0000 | 0000 |  |
| C4 | 46 (+1 osc) | 001B | 001B | 5A00 | 7F58 | 4D7F | 3C8A | 0000 | 0000 | 0000 |  |
| E4 | 48 (+1 osc) | 001B | 001B | 5A00 | 7F58 | 4D7F | 408A | 0000 | 0000 | 0000 |  |
| G4 | 50 (+1 osc) | 001C | 001C | 5A00 | 7F58 | 4D7F | 438A | 0000 | 0000 | 0000 |  |
| C5 | 52 (+1 osc) | 001D | 001D | 5A00 | 7F58 | 4D7F | 488A | 0000 | 0000 | 0000 |  |
| C6 | 54 (+1 osc) | 001E | 001E | 5A00 | 7F58 | 4D7F | 548A | 0000 | 0000 | 0000 |  |

### BASS  (SET 0x2B, button CPR_SEG1 0x08)

| note | ch | +040 | +040b | +0C0 | +140 | +500 | +400 | +440 | +440b | +480 | ext |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C2 | 56 | 1099 | — | 4600 | 7F25 | 7F60 | 1880 | 0000 | — | 0000 |  |
| C3 | 57 | 109A | — | 4600 | 7F25 | 7F60 | 2480 | 0000 | — | 0000 |  |
| C4 | 58 | 109C | — | 4600 | 7F25 | 7F60 | 3080 | 0000 | — | 0000 |  |
| E4 | 59 | 109C | — | 4600 | 7F25 | 7F60 | 3480 | 0000 | — | 0000 |  |
| G4 | 60 | 109C | — | 4600 | 7F25 | 7F60 | 3780 | 0000 | — | 0000 |  |
| C5 | 61 | 109D | — | 4600 | 7F25 | 7F60 | 3C80 | 0000 | — | 0000 |  |
| C6 | 62 | 109E | — | 4600 | 7F25 | 7F60 | 4880 | 0000 | — | 0000 |  |

### DIGITAL DRAWBAR  (SET 0x88, button CPR_SEG1 0x10)

| note | ch | +040 | +040b | +0C0 | +140 | +500 | +400 | +440 | +440b | +480 | ext |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C2 | 21 (+2 osc) | 6096 | 6288 | 007F | 6631 | 007F | 1880 | 0000 | 0000 | 0000 |  |
| C3 | 25 (+2 osc) | 6096 | 6288 | 007F | 6631 | 007F | 2480 | 0000 | 0000 | 0000 |  |
| C4 | 29 (+2 osc) | 6096 | 6288 | 007F | 6631 | 007F | 3080 | 0000 | 0000 | 0000 |  |
| E4 | 33 (+2 osc) | 6096 | 6288 | 007F | 6631 | 007F | 3480 | 0000 | 0000 | 0000 |  |
| G4 | 37 (+2 osc) | 6096 | 6288 | 007F | 6631 | 007F | 3780 | 0000 | 0000 | 0000 |  |
| C5 | 41 (+2 osc) | 6096 | 6288 | 007F | 6631 | 007F | 3C80 | 0000 | 0000 | 0000 |  |
| C6 | 45 (+2 osc) | 6096 | 6288 | 007F | 6631 | 007F | 4880 | 0000 | 0000 | 0000 |  |

### ACCORDION REGISTER  (SET 0x51, button CPR_SEG1 0x20)

| note | ch | +040 | +040b | +0C0 | +140 | +500 | +400 | +440 | +440b | +480 | ext |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C2 | 14 (+1 osc) | 4058 | 4061 | 5A00 | 66D8 | 7F7F | 187A | 0000 | 0000 | 0000 |  |
| C3 | 16 (+1 osc) | 4058 | 4061 | 5A00 | 66D8 | 7F7F | 247A | 0000 | 0000 | 0000 |  |
| C4 | 18 (+1 osc) | 4058 | 4061 | 5A00 | 66D8 | 7F7F | 307A | 0000 | 0000 | 0000 |  |
| E4 | 20 (+1 osc) | 4058 | 4061 | 5A00 | 66D8 | 7F7F | 347A | 0000 | 0000 | 0000 |  |
| G4 | 22 (+1 osc) | 4058 | 4061 | 5A00 | 66D8 | 7F7F | 377A | 0000 | 0000 | 0000 |  |
| C5 | 24 (+1 osc) | 405A | 4062 | 5A00 | 66D8 | 7F7F | 3C7A | 0000 | 0000 | 0000 |  |
| C6 | 26 (+1 osc) | 405E | 4065 | 5A00 | 66D8 | 7F7F | 487A | 0000 | 0000 | 0000 |  |

### GM SPECIAL  (SET 0x70, button CPR_SEG1 0x40)

| note | ch | +040 | +040b | +0C0 | +140 | +500 | +400 | +440 | +440b | +480 | ext |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C2 | 28 (+1 osc) | 3114 | 3114 | 5A00 | 7F58 | 2C7F | 3080 | 00C0 | 0000 | 0000 | EXT |
| C3 | 30 (+1 osc) | 3113 | 3113 | 5A00 | 7F58 | 2C7F | 3C80 | 00C1 | 0000 | 0000 | EXT |
| C4 | 32 (+1 osc) | 3112 | 3112 | 5A00 | 7F58 | 2C7F | 4880 | 00C2 | 0000 | 0000 | EXT |
| E4 | 34 (+1 osc) | 3112 | 3112 | 5A00 | 7F58 | 2C7F | 4C80 | 00C3 | 0000 | 0000 | EXT |
| G4 | 36 (+1 osc) | 3112 | 3112 | 5A00 | 7F58 | 2C7F | 4F80 | 00C4 | 0000 | 0000 | EXT |
| C5 | 38 (+1 osc) | 3115 | 3115 | 5A00 | 7F58 | 2C7F | 5480 | 00C5 | 0000 | 0000 | EXT |
| C6 | 40 (+1 osc) | 3116 | 3116 | 5A00 | 7F58 | 2C7F | 6080 | 00C6 | 0000 | 0000 | EXT |

### DRUM KITS  (SET 0x00, button CPR_SEG1 0x80)

| note | ch | +040 | +040b | +0C0 | +140 | +500 | +400 | +440 | +440b | +480 | ext |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C2 | 42 | 5024 | — | 4A00 | 7F5F | 0000 | 4D44 | 0000 | — | 0000 |  |
| C3 | 43 | 5041 | — | 4A00 | 7F5F | 0000 | 551E | 0000 | — | 0000 |  |
| C4 | 44 | 5069 | — | 5A00 | 7F5F | 0000 | 4EBC | 0000 | — | 0000 |  |
| E4 | 45 | 5072 | — | 5A00 | 7F5F | 0000 | 4D44 | 0000 | — | 0000 |  |
| G4 | 46 | 5062 | — | 5A00 | 7F5F | 0000 | 5144 | 0000 | — | 0000 |  |
| C5 | 47 | 5080 | — | 5A00 | 7F5F | 0000 | 4EBC | 0000 | — | 0000 |  |
| C6 | 48 | 5065 | — | 5A00 | 7F5F | 0000 | 4D44 | 0000 | — | 0000 |  |

---

## 5. +0x040 low byte = key-zone; stepping across notes (osc1) — MEASURED

| instrument | C2 | C3 | C4 | E4 | G4 | C5 | C6 |
|---|---|---|---|---|---|---|---|
| PIANO | 7001 | 7004 | 7007 | 7008 | 7008 | 700A | 700D |
| GUITAR | 3000 | 3001 | 3002 | 3002 | 3002 | 3003 | 3003 |
| STRINGS & VOCAL | 0073 | 0075 | 0077 | 0079 | 007B | 007B | 007F |
| BRASS | 1006 | 1006 | 1007 | 1007 | 1008 | 1009 | 100B |
| FLUTE | 5000 | 5000 | 5000 | 5000 | 5000 | 5000 | 5002 |
| SAX & REED | 313F | 3140 | 313E | 3141 | 3141 | 3142 | 3144 |
| MALLET & ORCH PERC | 2097 | 2097 | 2096 | 2096 | 2096 | 2098 | 209A |
| WORLD PERC | 30C6 | 30C6 | 30C7 | 30C7 | 30C7 | 30C7 | 30C7 |
| ORGAN & ACCORDION | 4001 | 4001 | 4002 | 4002 | 4002 | 4003 | 4003 |
| ORCHESTRAL PAD | 0073 | 0073 | 0075 | 0075 | 0077 | 0077 | 007B |
| SYNTH | 0019 | 0019 | 001B | 001B | 001C | 001D | 001E |
| BASS | 1099 | 109A | 109C | 109C | 109C | 109D | 109E |
| DIGITAL DRAWBAR | 6096 | 6096 | 6096 | 6096 | 6096 | 6096 | 6096 |
| ACCORDION REGISTER | 4058 | 4058 | 4058 | 4058 | 4058 | 405A | 405E |
| GM SPECIAL | 3114 | 3113 | 3112 | 3112 | 3112 | 3115 | 3116 |
| DRUM KITS | 5024 | 5041 | 5069 | 5072 | 5062 | 5080 | 5065 |

The high nibble (class) is fixed per instrument; the **low byte is the multisample key-zone** and
steps piecewise as the note rises (e.g. PIANO 01→04→07→08→0A→0D; GUITAR 00→01→02→03; STRINGS
73→75→77→79→7B→7F). DRUM KITS is the exception — every key is a different percussion instrument,
so its low byte jumps non-monotonically (24/41/69/72/62/80/65), the signature of a per-key drum
map rather than a pitched multisample.

---

## 6. +0x440 is a per-note-on rotating slot counter, not a wave number — MEASURED

Playing the **same note C4 five times** on FLUTE (identical pitch), gated capture of +040/+400/+440:

```
REP0 C4:  +040.ch00=5000  +400.ch00=3FA8  +440.ch00=0040
REP1 C4:  +040.ch01=5000  +400.ch01=3FA8  +440.ch01=0041
REP2 C4:  +040.ch02=5000  +400.ch02=3FA8  +440.ch02=0042
REP3 C4:  +040.ch03=5000  +400.ch03=3FA8  +440.ch03=0043
REP4 C4:  +040.ch04=5000  +400.ch04=3FA8  +440.ch04=0044
```

+040 (waveform) and +400 (pitch) are **constant**; +440 **increments by 1 per note-on** and
tracks the rotating voice channel. In the §4 sweep the same signature appears across pitch: for
FLUTE, C2→C3 (+12 semitones) and E4→G4 (+3 semitones) BOTH bump +440 by exactly +1 — impossible
for a pitch-derived index. **INFERRED:** +0x440 = `{ bits from tonerec[+0x1a]&0xC0 = bank } |
{ low byte = a rotating per-note-on voice/DMA-buffer slot }`. It is the KN5000's streamed-voice
slot handle, present only for the extended-path instruments (FLUTE/SAX/WORLD/ORGAN/GM), and 0 for
ordinary multisample voices (Piano/Guitar/Strings/Brass/Mallet/OrchPad/Synth/Bass/Drawbar/
Accordion/Drums). **It carries no waveform identity** — do not select on it.

---

## 7. Extended register set (streamed-voice control) — MEASURED, semantics SPECULATIVE

The extended-path instruments additionally program registers +0x1C0 / +0x540 / +0x580 / +0x5C0 /
+0x600 / +0x640, and — unlike the per-voice identity registers — these are written to **fixed low
auxiliary channels** (ch02, ch08, ch09), i.e. a shared streaming-control block rather than the
played voice channel. Observed values at C4:

| instrument | aux ch | +1C0 | +540 | +580 | +5C0 | +600 | +640 |
|---|---|---|---|---|---|---|---|
| FLUTE | (low) | 0000@2 | 0120@2 | 0120@2 | — | 0000@2 | — |
| SAX & REED | (low) | 0000@2 | 00E0@2 | 00E0@2 | — | 0000@2 | — |
| WORLD PERC | (low) | — | — | 00D0@9 | — | 0060@8 | — |
| ORGAN & ACCORDION | (low) | 1000@2 | 0126@2 | 0260@9 | 0126@2 | 0075@9 | 0046@2 |
| GM SPECIAL | (low) | — | — | 0034@2 | 0040@2 | 000F@2 | 0008@2 |

These correspond to `ToneGen_WriteExtParams_56` / `LABEL_02DA96` in the disasm. Their exact
meaning (DMA start / length / rate for the streamed sample?) is **not decoded** here — flagged for
the decode pass. They are per-instrument-distinct and would be the place a streamed voice's real
sample parameters live, if anywhere in the register stream.

---

## 8. Corrections to prior notes

* `kn5000-wave-number.md` §0/§2 ("+0x440 = wave-number 0 for **every** instrument"): **corrected**
  — true only for the 11 non-extended instruments; FLUTE/SAX/WORLD/ORGAN/GM emit nonzero +0x440.
* Any reading of +0x440 as "the wave number that selects the sample": **corrected** — §6 proves it
  is a per-note-on rotating slot counter (bank | slot), constant across repeats of a pitch only in
  its bank bits, incrementing in its low byte. No waveform identity.
* `kn5000-voice-pipeline.md` §5 class list (nibbles 7/1/3/0/4): **extended** — the class nibble
  also takes 2 (Mallet), 5 (Flute/Drums), 6 (Digital Drawbar).
* Unchanged / reconfirmed: per-instrument identity is +0x040 (class+zone) + timbre triple
  +0x0C0/+0x140/+0x500; the chip boundary holds (no sub-CPU RAM value ever reaches IC303).

---

## 9. Reproduction & honest gaps

Runner (isolated; nothing committed but this note):
```
SP=<scratchpad>; cp nvram2/kn5000/nvram{1,2} $SP/cap_run/nvram/kn5000/
cd kn7000-emulator && ISTART=<n> ICNT=4 timeout 150 kn7000 kn5000 -rp roms -window -nomaximize \
  -skip_gameinfo -nvram_directory $SP/cap_run/nvram -autoboot_delay 0 \
  -autoboot_script $SP/cap_all.lua -seconds_to_run 42 -nothrottle
```
Instruments 0-3 from one full run; 4-15 from ISTART slices {4,8,12} plus targeted re-runs
{ISTART=6,10} to place ORGAN and DIGITAL DRAWBAR as non-first (their button-drop artifact). The
+0x440 counter test = `repnote.lua` (warm-up PIANO → select FLUTE → 5×C4).

Gaps (honest):
* Captured on **part 0 (RIGHT1) only** — the SOUND-GROUP button retargets RIGHT1's voice, which is
  the clean single-part path. RIGHT2/LEFT layer voices were not separately keyed (default split
  sounds only RIGHT1 on the bed).
* Within each sound GROUP, only the **default/first sound** was captured (the group button selects
  it); the per-sound variation inside a group is not swept.
* The extended registers (§7) are captured but **not decoded** (DMA/stream params unknown).
* +0x400 note log-pitch is captured raw; its companding is non-linear in the raw value (already
  handled correctly by the HLE's per-period resample — not re-analyzed here).
