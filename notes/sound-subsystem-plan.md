# KN7000 Sound Subsystem — Research & Emulation Plan

**Status: DRAFT for Felipe's review (2026-07-09). No implementation work has started.**

Written in response to `~/compartilhado/KN7000/sound-subsystem-research.txt`. Grounded
in a five-agent recon sweep whose full reports live beside this file:

| Report | Contents |
|---|---|
| [sound-hw-architecture.md](sound-hw-architecture.md) | Service manual mined: block diagram, schematics, all sound ICs, test modes |
| [sound-gui-inventory.md](sound-gui-inventory.md) | User's manual mined: every sound screen, Chord Finder procedure, GUI top-level map |
| [dsp-host-interface.md](dsp-host-interface.md) | Firmware static RE: DSP host port found, **embedded SHARC program found**, register protocol |
| [sound-probing-infrastructure.md](sound-probing-infrastructure.md) | What's already solved, current driver surface, Lua probing infra, known dead ends |
| [sharc-lle-assessment.md](sharc-lle-assessment.md) | MAME SHARC core gap analysis for an eventual ADSP-21065L LLE device |

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

1. Productize extraction (Phase 0.2), extract all 80 records → per-record
   `.bin` + repacked 8-byte-LE `.d64` + `unidasm -arch sharc` listings, checked
   into `kn7000_disassembly/dsp/` with a manifest (offset, size, PM/DM blocks,
   target addresses).
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
(`0x48404D10–0x48408000`) in `kn7000_manual.sym`.

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

### Phase G — Wave-ROM dumping campaign (physical; your hardware, parallel to all)

- **A software dump path likely EXISTS**: the wave-ROM *readback window*
  (`0x9804/50006/8/A`: `+6` ← `0x8000|page`, `+8` ← `0x8000|word-offset`,
  `+A` = **raw data read**) is how the service WAVE ROM test reads words — the
  checksum is computed by the *firmware*, in software, from raw data. So the
  CPU can read wave words; the real open questions are whether the window
  reaches all four ROMs / all 16 banks, and whether it works outside diagnostic
  mode. First tick of this phase: characterize the window in the disassembly,
  then design the dump vehicle. Note the honest cost: running a dumper on the
  real instrument means either driving it over an existing I/O channel (MIDI
  bulk dump? floppy/SD write?) from patched firmware — and **reflashing
  IC16/IC17 on your KN7000 is not risk-free** — this decision is explicitly
  yours.
- Targets: IC203 (AWAY, C3CBQD000002), IC204 (AWAX, …001), IC207 (BWAY, …004),
  IC208 (BWAX, …003) — 128 Mbit each, on private TG buses.
- If readback-window dumping fails: desolder-and-read campaign (TSOP mask
  ROMs), or possibly an interposer capture on the wave **expansion connectors**
  during the WAVE ROM test — but note this path is *unproven*: the connectors
  carry EXAWD/EXBWD nets and *separate* chip enables (internal ROMs = banks
  0–15, expansions above), so whether the internal ROMs' traffic is visible
  there needs schematic confirmation first. The KN5000 waveform-ROM format doc
  gives the expected data shape either way.
- Also inventory: SY-EW01..04 expansion boards (separately dumpable wave sets).

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
  spec would churn under it.
- Re-deriving anything in the five recon reports or the manuals — cite instead.

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

## 5. Suggested cadence & first moves

Same cron-tick pattern as the panel plan. Proposed order once you approve:

1. Phase 0 (one tick, mechanical).
2. Phase A ticks until the DSP download capture matches the ROM records.
3. Phase B in parallel ticks (static, no emulator needed).
4. Phase C (Chord Finder) — the marquee experiment.
5. D → E consolidation; blog posts at the milestones (DSP-found post can go
   out immediately after Phase A verifies the protocol — it's a great story).
6. F/G decision gates with you.

**Nothing starts — including Phase 0 — until you've reviewed this plan.**
Corrections, re-prioritizations, and "don't touch that" notes welcome —
especially on the 0x9C bank split (Q2) and the wave-ROM campaign options
(Phase G), which involve your hardware.
