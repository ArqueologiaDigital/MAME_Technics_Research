# KN7000 Sound Subsystem — Research & Emulation Plan

**Status: DRAFT rev 2 for Felipe's review (2026-07-09). No implementation work
has started — Felipe reviews before anything begins.**

Rev 1 answered `~/compartilhado/KN7000/sound-subsystem-research.txt`. Rev 2 folds
in the seven follow-up requests captured verbatim in
[sound-subsystem-plan-rev2-request.txt](sound-subsystem-plan-rev2-request.txt):
frequent commits; a ROM-dumping "trojan" (custom-firmware ROM-backup utility);
SD as an update / code-execution channel; fabricated placeholder wave ROMs;
extending sound RE to KN5000/KN6000/KN6500; and a git-versioned commented
disassembly tree of the DSP programs inside the existing disasm repos.

Grounded in two recon sweeps (ten agents). Full reports live beside this file:

| Report | Contents |
|---|---|
| [sound-hw-architecture.md](sound-hw-architecture.md) | Service manual mined: block diagram, schematics, all sound ICs, test modes |
| [sound-gui-inventory.md](sound-gui-inventory.md) | User's manual mined: every sound screen, Chord Finder procedure, GUI top-level map |
| [dsp-host-interface.md](dsp-host-interface.md) | Firmware static RE: DSP host port found, **embedded SHARC program found**, register protocol |
| [sound-probing-infrastructure.md](sound-probing-infrastructure.md) | What's already solved, current driver surface, Lua probing infra, known dead ends |
| [sharc-lle-assessment.md](sharc-lle-assessment.md) | MAME SHARC core gap analysis for an eventual ADSP-21065L LLE device |
| [rom-backup-and-update-format.md](rom-backup-and-update-format.md) | **rev2** — official `.SLD`/`.INF` update-disk format decoded; reversible ROM-backup custom-firmware path; wave readback window dumps raw samples |
| [sound-cross-model-kn6000-kn6500.md](sound-cross-model-kn6000-kn6500.md) | **rev2** — same ADSP-21065L across KN6000/6500/7000; DSP pool byte-identical KN6000↔KN6500; register map |
| [sound-cross-model-kn5000.md](sound-cross-model-kn5000.md) | **rev2** — KN5000 TG/DSP RE state; what transfers as hypotheses vs known divergences |
| [placeholder-wave-rom-spec.md](placeholder-wave-rom-spec.md) | **rev2** — fabricatable synthetic wave-ROM spec + generator design |
| [dsp-disasm-tree-layout.md](dsp-disasm-tree-layout.md) | **rev2** — where/how the committed SHARC disasm tree lives in kn7000_disassembly |

---

## 0. Executive summary

The recon changed the problem substantially. Headlines:

1. **The DSP's program is NOT missing — it is embedded in our dumped firmware.**
   80 host-download records (71,625 bytes) at program-ROM `0x486BCEC4–0x486CE68D`:
   a resident SHARC kernel + 4 board-variant probe stubs + ~75 per-effect
   microprograms. Verified as genuine ADSP-2106x code with `unidasm -arch sharc`.
   The reverb/chorus/multi/DSP-effect algorithms are therefore fully recoverable
   by static analysis — no chip dumping needed for the DSP side.

2. **The DSP host port was found, and our MAME driver currently breaks it.**
   The CPU talks to the SHARC through an address/data pair:
   `0x98000000` (index) + `0x9C000000` (data) — the `0x9C` bank that the driver
   maps entirely as LCD RAM. The firmware's 10-retry boot probe (expects reg 0
   to read `0x20`) reads stale RAM instead, sets a "DSP dead" flag
   (`0x500066CC=0xFF`), and **silently suppresses the entire effect engine**.
   A small driver fix + a stub that answers the probe un-gates all effect
   traffic for study. This is the highest-value single change available.

3. **Audible *notes* remain blocked by physics, not knowledge**: the PCM samples
   live in four undumped 128-Mbit mask ROMs (IC203/IC204/IC207/IC208, 64 MB
   total) on private TG buses. Correction to an older note: even the service
   sine-wave test plays sine *samples from the wave ROMs*, so it is not a
   ROM-free audio path. Dumping those chips is a physical-hardware campaign
   (§Phase G) and gates only the final synthesis step — every other deliverable
   (specs, captures, DSP RE, trigger path) proceeds without them.

4. **Chord Finder is confirmed as the right deterministic note trigger** (user's
   manual p.57): APC `MODE` → APC SELECT → `CHORD FINDER` (bottom-right LCD
   button) → ear-icon button sounds the displayed chord (default C-E-G), with
   no rhythm engine and no keybed involvement. Which part sounds it is
   undocumented — we'll learn it from the register capture.

Chip identities (service manual, now settled):

| IC | Part | Role |
|---|---|---|
| IC201 | C1BB00000709 | MASTER TONE GENERATOR LSI, reg port `0x98040000/2` (key FIFO at `0x98040004` is a symmetry inference — only the sub-TG FIFO is firmware-verified) |
| IC205 | C1BB00000709 | SUB TONE GENERATOR LSI, reg port `0x98050000/2`, key FIFO `0x98050004` (verified) |
| IC306 | S21065LKS240 = **ADSP-21065L SHARC** | Effects DSP, host-booted by the CPU (no boot ROM on its bus) |
| IC307/IC308 | KM416S1120DT ×2 | **DSP SDRAM** (4 MB, 32-bit) — *not* tone generators, *not* a second DSP |
| IC203/204/207/208 | C3CBQD00000x | Wave ROMs, 128 Mbit each, **undumped** |
| IC311 | C0FBBK000025 | Main stereo DAC (Panasonic-coded, no commercial equivalent identified) |
| IC309/IC410 | PCM1800E | ADCs (mic/line in; record path) |

Signal flow: `sub TG → master TG → (serial audio, 44.1 kHz world) ↔ SHARC DSP → DAC IC311 → analog`.
Old notes that contradict this (tone-generator.md's early "main TG IC203/204"
labels; the driver's "DSP IC306/IC307" comment) get corrected in Phase 0.

### Revision-2 headlines (the follow-up requests)

5. **We can dump the real ROMs — including the "undumped" wave ROMs — from the
   instrument, reversibly.** The official firmware-update disk format is fully
   decoded (`.SLD` = LZSS with a `JKPRG4K` header; `.INF` = a 32-bit total +
   16 block checksums; no model/version guard beyond the file signatures). A
   *modified PROGRAM update disk* that adds a small backup routine into the
   image's ~71 KB of slack, triggered by repointing one service-menu function
   pointer, can read every ROM and write it to SD — and is fully reversible by
   re-flashing the pristine disks. The **wave-ROM readback window yields raw
   sample words** (the service test only *checksums* them), so all four wave
   ROMs are software-dumpable. This is the "trojan" — a homebrew ROM-backup
   utility for Felipe's own instrument, in the console-homebrew tradition. See
   Phase H. (Bonus preservation finding: our current `kn7000_program.rom` is the
   *update payload*, missing the top ~37 KB resident updater that only a real
   IC16/IC17 readback recovers.)

6. **SD can't run code or flash firmware today — but the backup utility can use
   SD as its output sink**, and once one FDD-delivered custom image is installed
   it can bootstrap an SD update/loader path. The main↔SD link is SIO ch2 to the
   CPSD sub-CPU; the firmware's SD surface is file/content only. Phase H covers
   the fallback ("run payloads from SD") and what the minimum enabling change is.

7. **Placeholder wave ROMs are fabricatable now.** A generator can tile the wave
   space with single-cycle timbres (sine at the diagnostic's banks, distinct
   timbres per bank) so the tone generator produces *something* from any address
   before the real dumps exist — clearly labeled synthetic, never mistaken for a
   dump. Lets us exercise the future TG `sound_stream` and the readback-window
   model end-to-end. See Phase I.

8. **The DSP subsystem is a cross-model win.** The ADSP-21065L is the *identical
   part* in KN6000, KN6500 and KN7000; the KN6000 and KN6500 ship a
   **byte-identical** 80-record microprogram pool, and its parameter (DM) blocks
   are identical to the KN7000's — only the SHARC code (PM) is a newer revision
   on the KN7000. One SHARC device model and one effect-RE effort serve all
   three. The KN5000 is different (two fixed-function effect ASICs, undumped
   internal ROM) but its *tone-generator interface* conventions transfer as
   hypotheses. See Phase J.

9. **The extracted DSP programs become a committed, commented disassembly tree**
   inside the existing `kn7000_disassembly` repo (not a new repo), following its
   generated-and-tracked-listings precedent. Folded into Phase B; layout in
   dsp-disasm-tree-layout.md.

---

## 1. Guiding principles

- **Manual-first (your instruction).** The GUI inventory is now complete
  (sound-gui-inventory.md) — every sound screen, its parameters and ranges, and
  page references. RE effort goes only to what the manuals don't say: register
  encodings, protocols, and the SHARC programs.
- **Capture before synthesize.** Each phase first makes firmware→hardware
  traffic *observable*, then documents it as a programming spec, and only then
  considers emulating behavior. Even with zero audio output, the spec is the
  preservation deliverable.
- **Verify with the machine's own tests.** The service diagnostic has "DSP:
  IC306 / DSP RAM: IC307, IC308" and WAVE ROM checksum tests — these become
  acceptance tests for our device models (they pass ⇔ the model is
  protocol-correct).
- **Integrity policy** (standing): no cross-model data presented as device
  fact; KN5000 knowledge is used as a *hypothesis generator* only, and every
  transferred claim gets KN7000-native confirmation before entering the spec.

---

## 2. The phases

Ordering rationale: A and B are independent and both cheap-to-start; A un-gates
dynamic effect probing (D) while C un-gates note-path capture (E). F/G are the
long-running build-out and the physical campaign. Suggested tick allocation at
the end (§5).

### Phase 0 — Housekeeping & corrections (≈1 tick)

Small, do-first items so later work lands on clean ground:

1. Correct stale docs: tone-generator.md TG↔IC labels (IC201/IC205 are the TGs);
   driver header comment "DSP IC306 / IC307" → "DSP IC306 + SDRAM IC307/IC308";
   the "sine test needs no sample ROM" claim (it does — sine samples live in
   the wave ROMs); io-map.md `0x98070000` is read-only status/strap (all 14
   sites are reads), and add the newly-found banks `0x9C000000`, `0x9CC000xx`,
   `0x9CE00000` cross-reference. Also reconcile the clock-source story:
   boot-performance-and-clock.md says "X105 50 MHz + X103 24 MHz feed the
   DSP/TG section" while the schematic reading gives TG X201 ≈16.9344 MHz and
   DSP X301 ≈30 MHz (both part-number inferences) — one of these needs
   correcting before the numbers enter any spec.
2. **Write** the SHARC record-pool extraction tooling into
   `kn7000_disassembly/tools/` (the recon left only output artifacts, not the
   scripts — the record format is fully specified in dsp-host-interface.md §2,
   so this is a rewrite-from-spec, ~30 lines), plus a Makefile rule for
   `region2.asm` (code region 2 was never in the linear disassembly).
3. Rescue reusable Lua probes from the old session scratchpad
   (`sdump.lua`, `helpid2.lua`, `play.lua`, `tap.lua`) into `kn7000_mame/tools/`.
4. Refresh `kn7000_run/roms/` to the current even/odd ROM layout — **this is
   your hand-run environment**, so it happens with your OK and together with a
   matching published binary, not silently.
5. Extend `mn10300_sim.py`'s `valid_io()` to bank `0x9C` (it currently raises
   on the DSP data port, blocking simulation of the DSP boot path).

### Phase A — Un-gate the DSP in MAME (≈2–3 ticks) ★highest value/cost ratio

Goal: firmware believes the DSP is alive, downloads its programs, and drives
effect parameters — all captured.

1. **Split the `0x9C` bank in kn7000.cpp**: DSP data port at `0x9C000000`,
   sound-board GPIO/revision byte regs at `0x9CC000xx`, LCD buffer stays at
   `0x9CE00000`. Regression-check: boot still reaches the home screen, LCD
   intact (the LCD buffer base must be confirmed — the firmware pointer base
   `0x9CE00000` was seen in code; verify actual framebuffer traffic offsets
   before narrowing the RAM window).
2. **Host-port stub device**: latch index writes at `0x98000000`; on data-port
   reads answer the boot probe (reg 0 → `0x20`) and the ID/version readback
   (reg `0x0B` — expected values must first be read out of the 4 variant-probe
   records' select logic at `0x48405470–0x4840552E`); keep busy (reg `0x37`
   bit7) deasserted; pulse the completion IRQ (INTC `0x3400015C` bit4) after
   download commits (`0x1C` ← `0xA1`/`0x41`/`0xA0` strobes).
3. **Capture**: log/store the full download stream (PM/DM blocks with target
   addresses) and all register writes with PC + timestamp. Verify the captured
   kernel image is byte-identical to the ROM pool record @`0x486BD9A8` — that
   proves we decode the protocol correctly.
4. **Acceptance test**: service "Other device test" should report
   `DSP: IC306 = OK, DSP RAM: IC307/IC308 = OK` once the stub satisfies
   whatever the test exercises (this may require modeling reg reads/writes into
   a small SDRAM-backed store; the test procedure tells us exactly what
   "healthy" looks like). Blocked on service-mode entry (open question Q5 has
   the workaround: force-call `TestModeFunc 0x484A497B`) — if entry stays
   uncracked, substitute the boot-probe + effect-download capture as the
   acceptance evidence.

Deliverable: `notes/dsp-host-interface.md` upgraded from "static findings" to a
verified protocol spec; driver merged with the stub behind a debug switch.

### Phase B — SHARC program static RE (≈3–5 ticks, parallelizable with A)

Goal: know what each of the ~75 effect microprograms does; name the effect
algorithms; produce the DSP-side half of the programming spec.

1. Productize extraction (Phase 0.2) and **stand up the committed DSP
   disassembly tree** (request 7) inside `kn7000_disassembly` — no new repo.
   Per dsp-disasm-tree-layout.md, following the repo's own generated-and-tracked
   precedent (`disasm/table_directory.asm`):
   - `tools/gen_dsp_records.py` — pool walker (pool bounds/ROM/base as CLI args
     so the *same* tool serves KN6000/KN6500 later): parse the 80 records from
     `baserom/kn7000_program.rom`, repack PM (3×BE u16 → 64-bit LE slot), drive
     `unidasm -arch sharc -basepc <PM target>`, dump DM blocks as typed word
     tables, merge labels/comments.
   - `dsp/` (hand-curated, committed): `README.md` (format + provenance),
     `records.tsv` (manifest: idx, rom_off, cpu_addr, size, blocks, role, name),
     `sym/*.sym` (per-record SHARC symbols+comments — DSP addresses can't go in
     `kn7000.sym` because its consumer skips addrs <0x48400000).
   - `disasm/dsp/*.asm` — generated **and committed** listings (≈<1 MB total),
     so annotation progress shows up as reviewable diffs; `build/dsp/*.bin`
     raw extracts stay git-ignored.
   - `Makefile` `disasm-dsp:` rule wired into the existing `disasm` target;
     `make disasm-dsp && git diff --exit-code disasm/dsp` doubles as a drift
     check. Add the interpreter/downloader functions to `kn7000_manual.sym`
     under a "Effects DSP (ADSP-21065L host port)" section.
2. Annotate the resident kernel (258-word PM @`0x8000` + ISR blocks): host
   command loop, download handler, effect-slot scheduler, SPORT/DMA setup —
   this reveals the runtime architecture (how 5 effect slots share the chip;
   the user's manual says 5 SOUND DSPs exist: 3 part + 2 APC, reassignable via
   ALLOCATION p.163 — expect this structure in the kernel).
3. Classify the effect microprograms and correlate with the GUI effect
   catalogue (Reverb: Room1..Dark2 etc.; Chorus1–4; Multi groups: Overdrive,
   Fuzz, Amp Simulator, Limiter, Compressor, Slow Attacker, Dual Delay, Cross
   Delay, …; Sound DSP groups: Tremolo, Auto Pan, Vibrato, Ring Modulator,
   Mixup, Parametric EQ, LFO Filter, Enhancer; 5-band final EQ). The mapping
   table is the 146-entry runtime pointer table `0x500066E0` — captured live in
   Phase A/D, or traced in the simulator once `0x9C` I/O is modeled (Phase 0.5).
4. Cross-reference the CPU-side callers (`0x484052E0` register writes; param
   struct walker `0x4840585D`; effect select `0x48405815(bank, prog)`) so each
   GUI parameter row (names+ranges known from the manual) maps to a DSP
   register index or DM address.

Deliverable: `notes/dsp-effect-catalog.md` (record ↔ effect name ↔ algorithm
sketch ↔ parameter map) + named symbols for the whole DSP driver module
(`0x48404D10–0x48408000`) in `kn7000_manual.sym` + the committed
`kn7000_disassembly/disasm/dsp/` tree with per-record function headers and
semantic labels growing over the phase (request 7 satisfied incrementally).

### Phase C — Trigger playback: Chord Finder (≈2–4 ticks)

Goal: make the firmware call `MainSoundAdd` for the first time in MAME and
capture a complete note-on → TG register sequence.

1. **Prep instrumentation** (the gaps found in prior work):
   - Driver/Lua switch to log non-`0xFC` TG writes with PC+time (the silent
     `m_tg_reg` capture is not enough for diffing).
   - Function-hit counters on `MainSoundAdd 0x4848C043`, `MainSeqRun
     0x484948BC`, and the ear-button widget handler once identified (Lua
     read-taps + CURPC, the reusable harness prior work never preserved).
2. **Navigate**: Lua macro — press APC `MODE` (panel button; SEG map known:
   SEG03 0x02) → on APC SELECT press `CHORD FINDER` — per your instructions
   that is **LCD RIGHT 5**, and the driver already has an "LCD RIGHT 5" port
   (kn7000.cpp:1173); reconcile that with the manual's "bottom-right soft
   button" reading before scripting — *within the auto-return window* (or pin
   with DISPLAY HOLD) → on CHORD FINDER press the rightmost bottom soft button
   (ear icon). All presses held ≥14 frames (established requirement). Confirm
   each screen with the pixel hash / PPM dump tooling.
   - Fallback if soft-button navigation proves fragile: inject event codes
     into the MILK queue at `0x5000757C`. Caveat: only *panel-button* codes
     are established (e.g. START/STOP `0x2020`); whether a screen-contextual
     soft button like the ear icon has a stable, injectable code — and whether
     it fires without its screen open — must be verified first (trace the
     widget handler).
3. **Capture & decode**: expect ~3 voices × the KN5000-style ~22-write
   sequence. This pins, with KN7000-native evidence: the address-word bit
   layout (the open 6-bit field question), key-on strobe, pitch/velocity/pan
   registers, and **which part the ear button uses** (undocumented). Vary
   ROOT/TYPE/INVERSION for more data points.
4. **Secondary triggers** (cheap once navigation works, and they exercise
   different engines): COUNT INTRO "VOICE" (single spoken-sample trigger),
   rhythm START/STOP (drum event stream + tempo), DEMO song, key-bed note via
   the (already working) key FIFO — retest now that instrumentation exists;
   prior "no traffic" results may partly stem from receive-routing defaults,
   which the MIDI PART SETTING screens (manual p.190+) let us change in-GUI.

Deliverable: `notes/tone-generator.md` gains a "KN7000-confirmed note-on
sequence" section (replacing KN5000 analogy with fact); trigger macros in
`kn7000_mame/tools/`.

### Phase D — GUI-driven effect/parameter probing (≈3–5 ticks, needs A; richer after C)

Goal: correlate every sound-related GUI control with its hardware write — the
HLE spec's raw material. The probing playbook (18 prioritized stimuli with
expected traffic, screen by screen) is already written:
sound-gui-inventory.md §5. Highlights:

- REVERB / CHORUS / MULTI type selects and the 5-band EQUALIZER presets →
  DSP program swaps + coefficient blocks (which record downloads, which DM
  writes).
- SOUND DSP screen: PART ∧/∨, type select, DEPTH, VARIATION, EDIT param rows →
  one write per press; EFFECT EDIT's PARAMETER/VALUE table is a ready-made
  name↔register map, one algorithm at a time.
- PART SETTING p.2 per-part EQ (LOW/HI FC+GAIN) → decides whether per-part EQ
  is TG-side or DSP-side.
- MASTER TUNING, KEY SCALING templates → global TG registers (distinctive
  block-write signatures).
- MONITOR/SEPARATE settings, PANIC (all-notes-off) → routing latch
  (`0x9805000E` modes 2/3/A/B/C/D), DAC bit-bang on `0x98060000` (CS/CLK/DATA
  bits; words `0x1220`/`0x1380` seen in init), global-silence register.
  (Physical volume sliders are excluded: they're analog pots read via
  PWM/panel boards and the driver's PORT_ADJUSTERs are unwired — no 0x98
  traffic to expect.)
- Static cross-check for each finding: the widget handler → helper-call chain
  in the disassembly (symbol table first: `kn7000.sym`).

Deliverable: `notes/sound-parameter-map.md` — GUI control → register/command,
per screen.

### Phase E — The Programming Guide (≈2 ticks, consolidation)

Merge A–D into the document your instructions asked for: **"KN7000 Sound
Subsystem Programming Guide"** — how software drives this hardware:

- TG register model (address encoding, per-voice map, global regs, key FIFOs,
  init sequences, the `0xFC0x` refresh) — KN7000-confirmed values.
- DSP host protocol (probe/ID, download record format, command strobes, busy/
  IRQ handshake) + effect catalogue + per-effect parameter maps.
- Audio routing & control plane: `0x9805000E` mode latch, `0x98060000` DAC
  serial config, board type/revision straps (`0x98070000`, `0x9CC00021`),
  clocks (TG 16.9344 MHz = 384×44.1k; DSP ~30 MHz osc; 11.2896 MHz = 256×44.1k).
- Signal-flow diagram (service-manual-accurate: sub→master TG serial mix,
  4-in/4-out TG↔DSP serial channels, DAC, SD/USB analog bypass, record loop).
- Open-questions register (whatever remains: Device A identity, TG interrupt
  roles TGS.INT1/2, CP.CLK/CP.DATA link, wave-expansion protocol).

This is also the natural blog-post material (2–3 posts: "The DSP program was
inside the firmware all along", "Making the KN7000 play a chord", "How the
KN7000 sound engine is programmed").

### Phase F — Emulation build-out (open-ended; decision gate after E)

Two tracks, decided when the specs exist:

- **TG HLE** (`sound_stream` device, template: `kn5000_tonegen.cpp` — note it
  lives only on the unmerged `kn5000_research_tonegen` branch of
  `~/compartilhado/mame`, reachable via
  `git show kn5000_research_tonegen:src/mame/matsushita/kn5000_tonegen.cpp`):
  register file → voices; pitch/volume/pan from captured semantics. **Gated on
  wave-ROM dumps for real output**; before dumps exist it can still pass
  structural tests (voice allocation visible, WAVE ROM test checksums fail
  loudly, which is honest).
- **DSP LLE** (roadmap in sharc-lle-assessment.md): MAME's 2106x core covers
  the ISA + has host-boot precedent (model2 host-upload pattern is our shape);
  new work = `adsp21065l_device` subclass (internal SRAM maps, IOP bank instead
  of fatalerror stubs, SDRAM-as-RAM) + **SPORT serial-audio emulation, which
  has no precedent in MAME** — the genuinely new piece, sized only after the
  kernel RE (Phase B) shows which SPORT features the firmware actually uses.
  An intermediate HLE option: interpret captured effect parameters directly
  (skip the SHARC) — decide with data.

### Phase G — Wave-ROM dumping (physical; folded into the Phase H backup utility)

Rev 2 collapses most of the old Phase G into **Phase H** (the ROM-backup
utility), because the recon confirmed a clean software dump path:

- **The wave-ROM readback window yields RAW sample words** (`0x9804/50006/8/A`:
  `+6` ← `0x8000|page`, `+8` ← `0x8000|word-offset`, `+A` = raw 16-bit read).
  The service WAVE ROM test walks all banks of both TGs through it and only
  *checksums* the data (routine `0x4848399E–0x48483B0A`, dispatcher
  `0x484A2E3A`), so the same addressing dumps the full ~64 MB. No desolder
  needed if the backup utility runs.
- Targets: IC203 (C3CBQD000002), IC204 (…001), IC207 (…004), IC208 (…003),
  128 Mbit each, on the private TG buses (never CPU-visible except through the
  window).
- **Fallback only if the utility route is rejected**: desolder-and-read (TSOP
  mask ROMs) or an interposer capture on the wave **expansion connectors**
  during the WAVE ROM test — unproven (separate chip enables; needs schematic
  confirmation that internal-ROM traffic is visible there).
- Also inventory: SY-EW01..04 expansion boards (separately dumpable wave sets),
  and the KN6000/KN6500 `QSIGX3C640xx` wave ROMs (same window, Phase J).
- Exact per-ROM capacity (16 MB vs 32 MB per chip) is unresolved in the manual;
  the window addresses far more than either, so the dumper isn't constrained by
  it — it walks until the data mirrors or goes empty.

### Phase H — ROM-backup utility ("trojan") + SD channel (needs the real unit)

Goal (request 3 & 4): when Felipe has a KN7000, back up **all** its ROMs —
program/table/rhythm/picture/custom **and the four wave ROMs** — to SD card,
reversibly, using a custom-firmware backup routine delivered through the
instrument's own update mechanism. This is homebrew for hardware he owns, in the
console-homebrew tradition; full detail in rom-backup-and-update-format.md.

Everything up to "insert the disk" is developed and tested **in MAME** first, so
the real-hardware step is a single well-rehearsed action.

1. **Update-disk packager** (`kn7000_extraction` already has the inverse of every
   step): an LZSS *compressor* + `.INF` emitter that repackages a modified linear
   program image into `JK1.SLD`/`JK2.SLD` + `SMCKPR*.INF` + verbatim
   `TECHNICS.PR*` + `DUMMY.2`, split at the 0x200000 boundary. Round-trip test:
   repack the *unmodified* image and confirm it's byte-identical to the shipped
   `kn7-16` disks — proves the packager before any patch.
2. **Backup routine** (MN10300 asm, placed in the image's ~71 KB of `0xFF`
   slack): dumps the directly-mapped ROMs by copy loop and the wave ROMs by the
   readback window (Phase G), writing to SD via the firmware's SD-save API (SD =
   the only practical sink for ~64 MB), with a MIDI-SysEx fallback for the small
   ROMs. Reuse real entry points (SD status `0x4855D901`, FAT I/O `0x485335FF`,
   library memcpy `0x4C003051`).
3. **Trigger**: repoint ONE service-menu function pointer
   (`0x4874AD34–0x4874AFF0`, e.g. the WAVE ROM test slot) to the backup routine.
   Leave the reset vector, boot (`0x4840FF7E`), kernel-init (`0x484D7111`) and
   the panel-combo→updater path **byte-identical** — this bounds the risk to the
   level of an official firmware update.
4. **Validate in emulation**: once Phase A/I make the driver model the wave
   window, run the repackaged image in MAME and confirm the backup routine reads
   the (placeholder) wave data and produces well-formed output files — end to
   end, before touching hardware.
5. **On real hardware** (Felipe's call, clearly flagged): install via PANEL
   MEMORY 1-2-3-4; run the backup; **restore by re-flashing the pristine
   `kn7-16` disks**. The resident updater (top ~37 KB) is never erased. A full
   IC16/IC17 readback additionally recovers that missing resident block — a
   preservation bonus (our current program.rom is only the update payload).
6. **SD as an update/code channel (request 4)**: today SD can't flash firmware
   or run code (main↔SD is SIO ch2 to the CPSD sub-CPU; SD surface is
   file/content only). Deliverable is (a) documenting that clearly, and (b) the
   minimum enabler — a custom image (installed via step 3) that adds a loader
   reading a `.SLD`/payload from an SD file through the existing SD-file API and
   feeding it to the install logic. So "system updates from SD" and "run
   payloads from SD" both become possible *after* one FDD-delivered bootstrap;
   spec them, build if Felipe wants the convenience.

Deliverables: `tools/` packager + backup-routine source (assembled/tested in
MAME), `notes/rom-backup-and-update-format.md` upgraded to a build/run/restore
runbook, and — once run on the real unit — the real wave-ROM and
resident-updater dumps entering the ROM set (replacing placeholders).

### Phase I — Placeholder wave ROMs (≈1–2 ticks; unblocks TG audio testing early)

Goal (request 5): synthesize stand-in wave ROMs so TG emulation can be exercised
before the real dumps. Spec in placeholder-wave-rom-spec.md.

1. `tools/make_placeholder_waveroms.py` (numpy int16): build a per-TG 16 M-word
   master tiled with single-cycle waveforms — a full-amplitude 256-sample sine
   in bank 0 (the diagnostic's target), distinct timbres per bank (saw, pulse,
   harmonic mixes) so any captured-but-unmapped address is audibly identifiable,
   a decaying-noise "drum" bank, plus an embedded KN5000-style directory at
   offset 0 as insurance. Split each master into even/odd → four
   `kn7000_wave_ic{203,204,207,208}_placeholder.bin`, exactly 16 MiB each.
2. **Address-agnostic by design**: because we don't yet know the real
   start/loop/pitch registers, tiling makes any {start,loop} the TG lands on
   yield a clean tone — so both the diagnostic sine test and "the home patch
   makes *something*" work without knowing the descriptor format.
3. **Two modes**: default leaves the checksums intentionally wrong (WAVE ROM
   test honestly reports NG); `--match-checksums` solves ballast words so all
   four report OK — used only to exercise the readback-window model end to end.
4. **Kept unmistakably synthetic** (integrity policy): `_placeholder` filenames,
   `BAD_DUMP` + `// SYNTHETIC` in ROM_START, ASCII provenance embedded in every
   bank, a `manifest.json` with sha1s mirrored into `notes/`; deleted from the
   ROM set the moment real dumps arrive. Never presented under the bare
   `C3CBQD00000x` part numbers.
5. MAME wiring: fix the placeholder ROM_START (current sizes are wrong — KN5000
   values; real chips are 128 Mbit) and add the readback-window handler so
   `region16[(page<<15)|offset]` answers `+A` reads.

Deliverable: the generator + four placeholder images + manifest, and a driver
that loads and pages them — the substrate for Phase F's TG `sound_stream` and a
concrete way to validate the Phase H dumper in emulation.

### Phase J — Cross-model sound RE: KN5000 / KN6000 / KN6500 (≈3–5 ticks; huge DSP reuse)

Goal (request 6): extend the sound RE to the siblings, documenting similarities
*and* differences. Reports: sound-cross-model-kn6000-kn6500.md,
sound-cross-model-kn5000.md.

- **KN6000 / KN6500 — near-total DSP reuse.** Same ADSP-21065L (`S21065LKS240`),
  same host protocol (index `0x98000000` / data `0x9C000000`, ids `0x9C0/2/4`,
  dead-flag guard — dead-flag is `0x50005D98` on KN6xxx vs `0x500066CC` on
  KN7000), same 80-record embedded pool. The KN6000 and KN6500 pools are
  **byte-identical**; their DM (parameter) blocks match the KN7000's, only the
  PM (code) differs (KN7000 = newer build). Actions:
  - Everything built for the KN7000 SHARC (host-port stub, `adsp21065l_device`,
    the disasm tree, the effect catalogue) is parameterized to also serve
    KN6000/KN6500 — `gen_dsp_records.py` already takes pool bounds as CLI args.
  - **Diff the PM blobs** KN6xxx↔KN7000 to isolate exactly what the KN7000's
    effect-code revision changed — a cheap, high-signal RE shortcut.
  - Create the KN6000/KN6500 committed DSP disasm trees in *their* disasm repos
    when those exist (none today — clone the kn7000_disassembly layout).
- **KN6000/KN6500 tone generator** = one `D82398GD001` (64-voice) at
  `0x98050000/2`, with the *same* keybed FIFO (`+4`) and wave-readback window
  (`+6/8/A`) conventions as the KN7000 — so the readback dump path and the TG
  interface transfer; the chip and its init sequence differ (no `0x98050010`
  init-strobe pattern). Wave ROMs = 4×64 Mbit (KN6000) / 6×64 Mbit (KN6500)
  `QSIGX3C640xx`, undumped — same software dump path (Phase H/J). KN6500 is a
  superset of KN6000 (one KN6500 dump covers KN6000's four chips). Also
  undumped: the IC13/IC14 table mask ROMs (the current MAME "table" ROMs are an
  IK2-mirror placeholder) — likely where the TG sample maps live.
- **KN5000 — interface transfers, backend does not.** Its TG (`TC183C230002`,
  64-voice, register-indirect at `0x100000/2`) has a fully documented per-voice
  register map, note-on write grammar, and voice-control constants
  (`0x8100`/`0x7E00`/`0x1200`) — the working *hypotheses* for decoding the
  KN7000 TG (verify natively; the KN7000 sound-init layer was reworked, `SwbtWr`
  is absent). But KN5000 effects are **two fixed-function ASICs**
  (DS3613GF-3BA + MN19413) with undumped internal ROM — architecturally unlike
  the KN7000's host-booted SHARC, so the KN5000 DSP does *not* transfer. Its
  `kn5000_tonegen.cpp` (branch device) is the proven `sound_stream` scaffold to
  port for the KN7000 TG (Phase F).
- Deliverable: `notes/sound-cross-model.md` — the similarity/difference matrix
  as living doc, and cross-model reuse wired into Phases A/B/F so the KN7000
  work lands on all applicable models.

### Stretch — GUI flow-chart (sound cluster ≈1–2 ticks; full system larger)

For the **sound cluster** the raw material is done: sound-gui-inventory.md §4
lists every top-level screen with page, opener, and purpose, sound screens
flagged — turning that into a mermaid/graphviz chart (nodes = screens, edges =
panel button/soft button/auto-return) is mechanical. The **entire-system**
chart you asked for as the wider goal is bigger than it looks: the sub-screen
flows of Performance Pads, Sequencer (~30 manual pages), Composer, Disk, SD,
Control, Customize and MIDI were only inventoried at top level, so budget a
separate manual-reading pass for those before charting them. Render into
`notes/img/` + the docs site; emulator screenshots can decorate each node using
the existing per-screen snapshot tooling.

---

## 3. What we will NOT spend time on (and why)

- Blind stimulus poking (MIDI notes / START/STOP without instrumentation) —
  three prior null results; instrumentation first (Phase C.1).
- Modeling TG/DSP hardware "to unblock playback" — disproven theory; playback
  is trigger-gated, not hardware-gated.
- Synthesis code before specs and wave ROMs — yields nothing audible and the
  spec would churn under it. (Placeholder wave ROMs, Phase I, are the exception:
  they let TG plumbing be tested, and are explicitly labeled synthetic.)
- Re-deriving anything in the ten recon reports or the manuals — cite instead.
- Presenting placeholder waves, IK2-mirror table ROMs, or cross-model reuse as
  real device data — integrity policy; everything synthetic/borrowed stays
  labeled, and cross-model facts are hypotheses until natively confirmed.
- Any irreversible hardware step. The backup utility (Phase H) is designed so
  every patch is reversible by re-flashing the pristine disks, and is fully
  rehearsed in MAME before the real unit is touched.

## 4. Risks & open questions

| # | Risk / question | Mitigation |
|---|---|---|
| Q1 | **Device A identity** (`0x98010000` mailbox + `0x98020004/8/A/E`, DMA via `0x32000800`): wave-expansion interface? sound-board supervisor? | Schematic deep-read + boot-time capture in Phase A; its presence-detect protocol is fully mapped already |
| Q2 | The `0x9C` bank split may collide with real LCD traffic | Verify framebuffer write ranges before narrowing; regression = boot-to-home + screen hash |
| Q3 | Chord Finder ear button may route through APC parts with rhythm-engine preconditions | Fallbacks queued: COUNT INTRO voice, DEMO, key-bed note with MIDI-routing GUI changes, MILK event injection |
| Q4 | DSP ID values for the 4 variant probes unknown until the select logic is read | Small, bounded disassembly task inside Phase A.2 |
| Q5 | Service-mode entry combo still uncracked (limits acceptance tests) | Independent puzzle; force-call `TestModeFunc 0x484A497B` via Lua/RAM as a workaround; do not block phases on it |
| Q6 | Wave-ROM readback window: raw reads are firmware-verified, but bank coverage (all 4 ROMs × 16 banks?) and non-diag-mode availability are unknown; any real-hardware dumper implies patched firmware = reflash risk | Characterize in disassembly first (zero risk); hardware decision is Felipe's |
| Q7 | 21065L SPORT emulation effort unknown | Sized after kernel RE (Phase B.2); HLE-params alternative exists |
| Q8 | **Brick risk of the backup custom-firmware (Phase H)** if the boot/updater path is altered | Keep reset vector + boot + kernel-init + panel-combo→updater byte-identical; confine edits to `0xFF` slack + one menu pointer; rehearse fully in MAME; restore = re-flash pristine `kn7-16` disks (resident updater never erased) |
| Q9 | **Update-disk packager correctness** (a bad `.SLD`/`.INF` could produce an `ILLEGAL DISK` or, worse, a bad flash) | Round-trip the *unmodified* image first and byte-compare to shipped disks before any patch; reproduce the exact `.INF` checksums |
| Q10 | **Wave-ROM per-chip size unknown** (16 vs 32 MB) — affects placeholder size and dump length | Window addresses far more than either; dumper walks until data mirrors/empties; placeholders use the service-test's 32 MB-per-TG constant |
| Q11 | KN5000 register-map / voice-constant transfer may not hold (reworked sound-init layer) | Treated strictly as hypotheses; confirmed against KN7000 capture (Phase C) before entering any spec |
| Q12 | Committed DSP `.asm` listings could churn if `unidasm` output drifts across MAME versions | Deterministic generator (no timestamps/abs paths); a unidasm-format change is one mechanical commit, separated from annotation commits |

## 5. Suggested cadence & first moves

Same cron-tick pattern as the panel plan. Commit notes/plans/tools every tick
(your standing instruction — already in effect for these docs). Proposed order
once you approve:

1. Phase 0 (one tick, mechanical) — housekeeping + corrections.
2. Phase A ticks until the DSP download capture matches the ROM records
   (highest value/cost: un-gates the whole effect engine).
3. Phase B in parallel ticks (static, no emulator) — builds the committed DSP
   disasm tree (request 7) as it goes.
4. Phase I (placeholder waves) early — small, unblocks TG audio + Phase H
   validation in MAME.
5. Phase C (Chord Finder) — the marquee note-trigger experiment.
6. Phase J (cross-model) interleaved — mostly free reuse on the DSP side; the
   PM-blob diff (KN6xxx↔KN7000) is a cheap early win.
7. D → E consolidation; blog posts at milestones (the "DSP program was inside
   the firmware — and it's the same across four models" post can go out right
   after Phase A verifies the protocol).
8. **Phase H** software/packager work proceeds in MAME anytime; the
   **real-hardware** dump waits for the unit and an explicit go from you.
9. F/G decision gates with you.

Independence for parallel ticks: Phase 0, A, B, I have no ordering constraint
among them beyond A needing 0.1's bank-split groundwork; J's DSP half rides on
B; H's software half rides on the packager + I; only H's hardware step and G's
fallback need the physical unit.

**Nothing starts — including Phase 0 — until you've reviewed this plan.**
Corrections, re-prioritizations, and "don't touch that" notes welcome —
especially on: the 0x9C bank split (Q2); the backup custom-firmware safety
envelope (Q8/Q9) since it touches your instrument; the cross-model scope
(how far to push KN5000/6000/6500 now vs later); and whether you want the SD
update/loader convenience (Phase H.6) built or just specified.
