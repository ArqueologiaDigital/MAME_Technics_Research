# Demo stall / chord-finder garbage / "8 Beat 1" — root causes + research plan (2026-07-10)

Felipe asked: dig into the demo playback stall via disassembly; could it (and the chord
finder glitches) be related to the "8 Beat" problem? Answer, after a combined runtime +
4-way disassembly investigation (each finding adversarially re-derived by an independent
verification pass):

**Three symptoms, TWO root causes.** The demo stall was the unmodeled TEMPO TIMER
(now FIXED, commit 60d5392 — demos and rhythm accompaniment PLAY). The chord-finder
garbage and the "8 Beat 1" style list share the OTHER root cause: the style/custom
flash data that is missing from our dumps (unmapped flash windows). They are related
to each other, but not to the stall.

## Root cause 1 (FIXED): the tempo timer TM5 was unmodeled

- ALL sequenced playback (demo songs, rhythm accompaniment, MIDI clock out) is clocked
  by the on-chip 16-bit timer TM5: mode byte 0x34001082, 16-bit reload 0x34001092,
  counter 0x340010A2, underflow -> INTC group 7 (GxICR 0x3400011C, level 4).
- The firmware registers ISR **0x48447084** there (registration 0x4844780C): a
  **96-PPQN tick** (mod-0x60 beat-phase counter at 0x50149664) driving five clock
  consumers. Reload = **1,250,000 / BPM** on TM5's 2 MHz timebase (IOCLK 16 MHz / 8;
  IOCLK derived from the firmware's own MIDI-baud math). At the boot tempo q=120 the
  firmware writes base 0x28B0 = 10416 -> 192 Hz = 96 PPQN x 2 quarters/sec. VERIFIED
  live after modeling: exactly those values appear, the demo Overture plays 30+ s of
  continuous music with its screens advancing, rhythm START/STOP plays steadily.
- The sibling TM4 (mode 0x34001080, base 0x34001090=2000, prescaler 0x34001071) is the
  1000 Hz RTOS scheduler tick — the driver's sys_tick already approximated it, which is
  why the UI/panel worked while everything tempo'd was dead. The ApTimer framework
  (0x48429935/0x484299F1/0x48429C95) is SOFTWARE on top of the scheduler tick (per-task
  records at 0x5000757C stride 0x38, tick counts 0x5011FA8C) — no hardware regs.
- Runtime proof of the gap (before the fix): of the 21 ISRs registered in the library
  dispatch table 0x50380B64, the group-7 slot (0x48447084) was the ONLY app-flash
  handler that never fired; bp-counters showed MainSeqRun/MainPostEvent = 0 calls in
  20 s while a demo "played" its single synchronous first note.
- Driver fix: kn7000.cpp models mode/base/counter with hardware auto-reload semantics
  (start 0x484477D3: mode -> base -> bset/bclr 0x40 load -> bset 0x80 enable; live
  tempo rewrite 0x48447888 takes effect next underflow), asserting intc_assert(7).
- KN6000/KN6500 CAUTION: their sys_tick asserts group 7 at a fixed 1000 Hz (an
  ms-counter hack). If their firmware shares the TM5 tempo scheme (likely, shared
  codebase), their tempo is probably WRONG-RATE; evaluate separately, do not change
  blind (cross-model integrity policy).

## Root cause 2 (OPEN): the style/custom flash data is missing (unmapped windows)

Two independently-verified chains end at the same class of missing data:

### 2a. "8 Beat 1" style list
- The name-resource selector **0x4843385E** probes SIX physical windows for the full
  flash-resident "Technics Rhythms" name resource: **0x48010000 (table ROM +0x10000),
  0x40010000, 0x40610000, 0x40810000, 0x54E00000, 0x54E10000**. In emulation none has
  it (the 0x40/0x54E windows are entirely unmapped; the dumped table ROM has 0xF7 fill
  at +0x10000 and a truncated copy at 0x483E828C — the full resource is physically too
  large for the 4 MiB chip, so it lives on an UNDUMPED flash).
- Fallback: the program-ROM STUB resource **0x48729988**, whose header declares
  **count = 1**. The resolver 0x48433AC4 gates every per-style entry on
  entry < count(*0x50034B74) -> every style-ID out of range -> the fallback string
  "  8 Beat 1" (0x4872AB42). That is the whole bug: the list builds 10 valid slots
  with REAL style-IDs (genre tables 0x48735EE4 -> e.g. BALLAD list 0x485B8A04,
  IDs 0x065B..0x0762), and every NAME resolution falls back.
- Note the real display-name data DOES exist elsewhere in the dumps (StyleGenreTable
  0x4873ACC0 / StyleRecordTable 0x4873BEE8 name ptrs) — but this GUI path resolves
  through the flash resource, not those tables.

### 2b. Chord-finder garbage pitch
- The chord finder itself is CORRECT: root/type interval tables at prog-ROM
  0x48763794/0x48763888 produce the right MIDI notes, queued at 0x50092600 and posted
  as note-ons on **part 0x21 (CHORDFINDER)** through the same library event ring the
  keybed uses.
- The garbage appears at TG-voice setup: the voice copies tone-element descriptor
  pointers from the PART TONE BLOCK at **0x500CE404 + part*0x130** (part 0x21 ->
  0x500D0B34). Pitch = ((note - centerKey) << 8 + coarse/fine tune) >> keyScaleExponent
  + 0x4280, all taken from those descriptors. Part 0x21's block holds the boot-time
  NULL default (default tone assignment selector 0x20 -> lib 0x4C00C233 -> NULL for
  any part outside keyboard parts 0x10-0x12), so the pitch math runs on garbage —
  including descriptor exponent 7 = note-INDEPENDENT pitch, which is exactly the
  observed root-invariant 0x37B0 slot. Keybed parts get real descriptors, hence
  correct keybed pitch through the very same writer (lib 0x4C036FBA).
- On real hardware part 0x21 is programmed by style/APC part setup whose data source
  is the factory rhythm/style flash — the same missing-data family as 2a. (Confirmed
  post-timer-fix: chord finder STILL garbage with sequencing alive, as predicted —
  it is data, not clock.)

## Research plan (pinpoint + fix the remaining root cause)

Phase A — identify the physical chips behind the probe windows. Read the KN7000
service manual (repo: service_manual/) chip-select / memory-decode pages and map
0x40010000/0x40610000/0x40810000/0x54E00000/0x54E10000 (+ the known 0x56000000
custom / 0x57000000 factory apertures from kn7000.sym) to ICs. Compare the KN5000
reference architecture (custom_data IC19 programmed by the Initial Data disk;
rhythm_data IC14; table_data IC1/IC3). Deliverable: window -> chip table in
notes/table-rom-structure.md.

Phase B — hunt the "Technics Rhythms" resource in data we already have.
**DONE 2026-07-10 — EXHAUSTIVE NEGATIVE.** Searched: (1) 01CTMINI.AST DEFLATE payload
(0x1E0000 bytes) + all idd7000 files; (2) the kn7-14 TABLE update disks JKT1/JKT2.SLD
(LZSS-decompressed: full image = 0x3E94D4 bytes = BYTE-SIZE-IDENTICAL to our dumped
table ROM, same truncated copy at +0x3E828C only) and the kn7-16 program disks;
(3) the KN7000 CD-ROM (PC software only), scd7000 (style converters), cb7-update.
NO full resource anywhere, incl. raw-DEFLATE scans of every >10KB binary. The
update-disk catalog (TECHNICS.PR*) lists KN7KR1/2 RHYTHM and KN7KCT CUSTOM-DATA disk
types, but none were ever distributed on the archive sites we have -- the factory
rhythm/style flash is factory-programmed only. => Phase C (real-HW dump) is the ONLY
faithful source; Phase D (labeled synthetic) is the only interim.

### Appendix: probe/resource mechanics (for Phase C/D implementation)
- Prober 0x4843D6DC: strncmp "Technics Rhythms" at 0x48010000, 0x40610000,
  0x40010000, 0x54E10000, 0x40810000, then UNCONDITIONALLY returns 0x54E00000 as the
  last resort. Selector 0x4843385E inits the winner; a strncmp mismatch (ret -3)
  falls back to the prog-ROM stub 0x48729988. So **0x54E00000 is the natural install
  window** (no strncmp gate ahead of it; driver has no map conflicts there).
- Resource format (byte-verified on the stub + the truncated table copy): base+0 =
  "Technics Rhythms" (16B); u24BE@base+0x18 -> header block whose +2 u16BE = COUNT
  (*0x50034B74; stub=1, real=0xDD=221); u24BE@base+0x1E -> subtable of u24BE
  name-record offsets (x3 bytes); u24BE@base+0x1B (via the table-ROM directory
  dirbase u32@0x4800014C) -> nametable of 0x800 u16BE entries (*0x50034B7C).
  Entry semantics in resolver 0x48433AC4: plain entry < count -> name =
  base + u24BE(subtable + entry*3), 13-byte records; entry&0xC000==0x4000 ->
  secondary subtable *(0x50034B90) (= table ROM 0x48244F78, INTACT in our dump);
  entry&0xC000==0x8000 -> one indirection through the nametable then as plain.
- The real resource is LARGE: the truncated copy's subtable has offsets up to
  +0x22B434 (~2.3 MB of records) -- the full flash image is multi-MB, reinforcing
  that it lives on the big undumped rhythm/style flash chip.
- A Phase-D synthetic needs only: header + count=0xDD + a self-consistent subtable +
  221 x 13-byte name records built from the REAL names in prog-ROM StyleGenreTable
  0x4873ACC0 / StyleRecordTable 0x4873BEE8 (+ the intact 0x48244F78 records), a few
  KB total, installed at 0x54E00000. Label SYNTHETIC per the integrity policy.

Phase C — real-hardware dump (the definitive fix). Felipe's KN7000 can dump the
missing flash itself: the ROM-backup route in notes/rom-backup-and-update-format.md
(modified PROGRAM update disk; ~71KB slack; SD as output sink) — extend the backup
routine to read the style/custom flash windows (exact windows now known from Phase A)
in addition to the wave-ROM readback. This fixes 2a AND 2b faithfully.

Phase D — interim placeholders (clearly labeled SYNTHETIC, integrity policy):
 - 2a: synthesize a minimal valid name resource (count + nametable + 3-byte offset
   subtable + name records — format decoded) from the REAL style names already in
   prog-ROM StyleGenreTable/StyleRecordTable, installed at a probe window. Fixes the
   list display honestly (real names, synthetic container). Label SYNTHETIC.
 - 2b: after a style/APC engage now works (timer fixed), first check whether normal
   style playback programs part 0x21 via internal 0xC0 events (the agents could not
   find the trigger statically; test dynamically with a running rhythm + APC ON).
   Only if not: consider seeding part 0x21's tone block with a keyboard-part
   descriptor as a labeled stopgap and verify C-E-G spectrally.

Phase E — regression sweep enabled by the timer fix (cheap wins to verify):
 tap tempo / tempo box changes (live reload rewrite is modeled), metronome,
 MIDI clock out, performance pads, sequencer record/play, the five tick consumers
 (0x50149666/0x5014967A/0x50149670/0x50149684/0x5014968E) — identify each's role.

Phase F — cross-model: evaluate KN6000/KN6500 TM5 (their group-7 1000 Hz hack vs a
real reload-programmed tempo timer) and KN2400/2600 once their drivers mature.

## Where each claim was verified
- TM5/ISR/constant chain: independent re-disassembly confirmed every load-bearing
  instruction (0x484477D3, 0x4844780C, 0x48447847: mov 0x001312D0 -> 0x5003A540).
- Stub resource: byte-verified (count u16BE = 0x0001 at file 0x3299B1; nametable
  uniformly 0x845A; sub[0] -> "  8 Beat 1" at 0x32AB42).
- Chord chain: root/type tables verified as valid data; part-block arithmetic and
  NULL default confirmed; pitch formula matches all observed values including the
  root-invariant slot. Independent verification pass: CONFIRMED (12 evidence items
  re-derived, incl. the lib default-assign 0x4C00C233 keyboard-part gate).
- Demo engine (independent 4th investigation): demo data = 10 songs, zlib-compressed
  setup+sequence+sound blobs, ENTIRELY in the dumped program ROM, loads correctly --
  the stall was purely the clock chain, matching the fix. Useful state addrs: RUN
  gate 0x5014966E bit15, stop 0x50149656, count-in 0x50149696 bits15&7, clock-source
  byte 0x50149662 (internal vs MIDI-clock).
