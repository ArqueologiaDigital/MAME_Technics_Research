> Recon report produced 2026-07-09 by the sound-plan rev-2 research sweep.
> Companion to notes/sound-subsystem-plan.md. Verify page/line/address citations before building on them.
> Note: the ROM-backup/custom-firmware work here targets Felipe's OWN instrument for preservation (dumping otherwise-unreadable mask ROMs), analogous to console homebrew — legitimate, reversible, no third party.

# KN5000 Sound Subsystem — Reverse-Engineering State Inventory
(for the KN7000 sound-plan cross-model comparison section)

Sources: `/home/fsanches/compartilhado/kn5000-docs/` (tone-generator.md, audio-subsystem.md, waveform-rom-format.md, dsp-bytecode-interpreter.md, swbwr-tone-init.md, sound-parameter-protocol.md, technics-shared-codebase.md), MAME mainline `/home/fsanches/compartilhado/mame/src/mame/matsushita/kn5000.cpp`, and git branch `kn5000_research_tonegen` of `/home/fsanches/compartilhado/mame` (`kn5000_tonegen.cpp`, `kn5000_dsp.cpp` — these device files exist **only on that branch**).

---

## 1. Tone Generator (TG)

**Chip:** IC303 = **TC183C230002**, custom Matsushita LSI, 64-voice PCM wavetable synth (tone-generator.md:7-25). Single chip (vs KN7000's two C1BB00000709). Companion RAM: IC308/IC309 = M5M44260AJ7S 4Mbit DRAM each ("DSP1/DSP2 work RAM" per tone-generator.md:305-306; mapped as writable "Waveform/sample RAM" at SubCPU 0x1E0000, stubbed `noprw` — tone-generator.md:354, branch kn5000.cpp:298).

**Bus master:** the **Sub CPU** (TMP94C241F, TLCS-900/H2) drives the TG — not the main CPU (audio-subsystem.md:9-54). This is a structural difference from KN7000 (see §5).

**Register-indirect interface** (tone-generator.md:31-52):
- `0x100000` (16-bit W) = register **address latch**; `0x100002` (16-bit R/W) = **data port**.
- Strict CS protocol: P6.7 GPIO asserted low during the address write, deasserted to latch, then data written, 3 NOPs hold time (asm at tone-generator.md:42-50). P6.7 doubles as A23 for TG access (tone-generator.md:63, audio-subsystem.md:1154).

**Register address encoding** (tone-generator.md:66-75):
```
bits 15-8 = register group | bits 7-6 = sub-bank (0-3) | bits 5-0 = channel (0-63)
addr = base + bank*0x40 + channel
```

**Per-voice map — 32 regs = 8 groups (0x00,0x01,0x04,0x05,0x06,0x08,0x09,0x0A) × 4 banks**, fed from a 44-byte firmware struct (tone-generator.md:84-111):
- g0.b0 `+0x000` voice control state machine: **0x8100 = KEY ON, 0x7E00 = idle/key-off, 0x1200 = decay transition** (tone-generator.md:167-174)
- g0.b1 `+0x040` pitch increment (semitone table, 0x8000 = 1.0x; ROM table 0x01217D)
- g0.b2 `+0x080` voice mode/velocity — **bit 15 = latch strobe** (SET then re-write CLEAR; velocity vol = vel²/4+63, range 63-4095 — waveform-rom-format.md:133)
- g0.b3 `+0x0C0` waveform control (cleared on note-off)
- g1 `+0x100/0x140/0x180/0x1C0` interpolated pitch / detune / velocity-expression coeff / key-on flag (hardcoded 0x8100)
- g4 `+0x400..0x4C0` note key info (note<<8, bit15 active) + 3 level/key banks
- g5 `+0x500..0x5C0` modulation + 3 extended params (bit-15 strobed)
- g6 `+0x600/0x640` aux routing
- g8 `+0x800..0x8C0` **main volume (0xFF80=mute, lower=louder)**, pan L, pan R (0-0x78, center 0x3C), DSP send level
- g9 `+0x900..0x9C0` 4 independent DSP effect sends; gA `+0xA00/0xA40` secondary aux

**13 global registers**: 0x0200-0x0205 (system), 0x0C00-0x0C05 (effects), 0x0E00 (master), with documented init values (tone-generator.md:179-197).

**Init sequence** — `ToneGen_Config_Init` @ SubCPU 0x02DFCF (tone-generator.md:199-219): (1) write the 13 global regs from RAM struct 0xF8BB; (2) copy 68-byte per-voice template from ROM 0xF8D5 → RAM 0x2AA4; (3) per each of the 64 channels: mute (0x840=0xFF00, 0x800=0xFF80), write 22 voice params, re-mute, idle (0xC0=0, 0x00=0x7E00), then strobed extended params — **2,317 register/data pairs total, confirmed in MAME log** (tone-generator.md:212). Then `ToneGen_Poll_Init` @0x03D227 drains 16 hw slots as note-offs.

**Note-on write order** — `ToneGen_WriteVoiceParams` @0x02D0FD, 22 pairs from the 44-byte struct: pitch → velocity-latch SET → waveform → pitches → note-key → level banks → modulation → **main volume → KEY ON (constant 0x8100) → pan L/R → DSP sends → aux** → velocity-latch CLEAR. Key-on deliberately sits *after* volume, *before* pan (tone-generator.md:113-142, 411-445). Note-off = `+0xC0`←0x0000 then `+0x00`←0x7E00 (tone-generator.md:464-468).

**Key-input interface** (tone-generator.md:54-63; audio-subsystem.md:1934-1943): the **keybed wires directly to IC303**, which does hardware scanning/velocity/debounce. SubCPU reads events at `0x110002` (status, bit0=ready) / `0x110000` (data: low byte=note, high byte=velocity). Pitch math: `ToneGen_Calc_Pitch` @0x03D11F, note+36, octave=/12, semitone table (tone-generator.md:446-462).

---

## 2. DSP / Effects

**Chips — memory claim CONFIRMED:** **DSP1 = IC311 DS3613GF-3BA** (8-bit parallel bus + memory-mapped 0x130000) and **DSP2 = IC310 MN19413** (GPIO bit-bang serial) — audio-subsystem.md:70, 1360-1369, 1378-1383; tone-generator.md:249-251, 307-308. Caveat: swbwr-tone-init.md:158 says "DSP1 (IC310, MN19413)" — that is a one-off typo in that page; all other pages and the MAME device headers agree on IC311=DSP1. Both are **fixed-function effects ASICs with internal ROM, no public docs, undumped**.

**Host interface** (audio-subsystem.md:68-118):
- Shared 8-bit data bus on SubCPU Port Z; P7.3=WR, P7.4=RD, P7.5=CS1(DSP1), P7.6=command/data select, PE.6=CS2(DSP2), PH.0=ready input, PH.1/PH.2=resets, PE.0=MUTE.
- Write protocol: select chip → poll PH.0 ready (timeout 8000 iters) → set C/D → strobe WR with byte on PZ (audio-subsystem.md:85-97). Key routines `DSP_Send_Command` 0x036331, `DSP_DispatchCommand` 0x03C0D4, etc. (audio-subsystem.md:99-118).
- **DSP2 is actually SPI-like bit-bang**: PF.0=SDA, PF.2=SCLK, PE.6=CS, 9 SCLK edges/byte MSB-first; register writes = CMD 0x30 + 4-byte groups `[0x00, addr, val_hi, val_lo]` (audio-subsystem.md:1393-1412).
- Secondary **memory-mapped path at 0x130000/0x130002** (addr/data bytes): 4 channels × 0x20 regs, channel base = N×0x20+0x10 (audio-subsystem.md:120-137; tone-generator.md:221-239).

**Effect architecture** (audio-subsystem.md:425-530):
- **5 EFF slots**; per-slot **56-byte parameter block = 28 words, word[0] = algorithm ID** (e.g. 0x0014 = CONCERT REVERB 1); slot buffers at SubCPU 0x4496+slot×0x38 (audio-subsystem.md:483-497).
- MainCPU→SubCPU **command 0x2D**, 4-layer protocol (latch 0x120000 → ring buffer 0x3B60 → 8-byte header w/ EFF-slot selector 0x0A-0x0E → diff-compare into slot buffer) (audio-subsystem.md:425-497).
- Master **`DSP_State_Dispatcher`** runs an 11-step mute/algo-change/disconnect/unmute/link/volume pipeline (audio-subsystem.md:350-423).
- **100 algorithm IDs** (name table at MainCPU ROM 0xE32A7A: CHORUS, FLANGER, 12 reverb subtypes 16-27, DISTORTION 32, GEQ 79, combos 64-99 …) mapping **40 effect indices → 12 algo types** via ROM table 0x01F596 (audio-subsystem.md:1454-1556, 1781-1835). 84-86 named parameters at MainCPU 0xE324C4/0xE324D0 (audio-subsystem.md:908-927, 1557-1588).
- **EFF-chip mapping** (0x1ED6D): slots 0-1 → DSP1 (slot 1 = hardcoded reverb/chorus programs), slots 2-4 → DSP2 (slot 2 up to 46 params) (audio-subsystem.md:825-836).

**Bytecode interpreter — yes, but it is HOST-side, not DSP microcode** (audio-subsystem.md:542-777; dsp-bytecode-interpreter.md:13-50):
- Level 1: `DSP_BytecodeInterpreter_Init` @0x03C266 executes ROM-resident programs of `[opcode:4][count:12]` instructions; opcodes 0-5 = native TLCS-900 write handlers (1,613 bytes @0x03C32E; 12-bit and 16-bit packed coefficient addressing; Handler-0/5 "Branch C" mixes a 32-bit runtime parameter into template coefficients = real-time control), 0xD = yield/SPI-idle, 0xE = raw command+data, 0xF = end.
- Level 2: `DSP_PerParameterTranslator` @0x03CB8E, opcodes 0x21/0x24/0x40/0x61-0x78 (LUT fetch, 2/3-point interp, biquad coeff/warp, SOS coeff, EQ/reverb/detune curves) mapping MIDI 0-127 → coefficients (audio-subsystem.md:863-906).
- Program tables: algorithm programs @0x1ED7C (100 entries), parameter programs @0x1EF0C (47 unique), register-address/param-mapping tables @0x1F09C/0x1F22C (audio-subsystem.md:838-861).

**Effect program storage — the decisive cross-model answer:** *"The DSP chips do NOT receive external microcode… DSPs are pre-programmed at manufacture"* (audio-subsystem.md:1414-1432). The KN5000 firmware only writes configuration/coefficients. **This is the opposite of the KN7000**, whose ADSP-21065L SHARC receives 80 host-download microprogram records embedded in the dumped firmware (@0x486BCEC4-0x486CE68D). Consequence: KN5000 effect DSP behavior can only be inferred from register traffic (known commands 0x01 bulk-init, 0x03 algo-select, 0x0F flush, 0x10 enable, 0x30 sub-addressed param write, 0x60 bulk — audio-subsystem.md:1590-1635); a full 60-second MAME boot trace exists including a reconstructed **DSP1 internal coefficient address map for the reverb (module 0xC8) and chorus (module 0x54) algorithms** (audio-subsystem.md:1637-1881) and a 112-register DSP2 map (audio-subsystem.md:1703-1779).

---

## 3. Wave ROMs

**Inventory** (waveform-rom-format.md:13-20; mame kn5000.cpp:732-736): IC304 QS6GU3C32375, IC305 QS6GT3C33A01, IC306 QS6GU3C32374 — all 4MB, **NO_DUMP**; **IC307 QS6GX3C32008 — DUMPED** (CRC 20ff4629, SHA1 4b511bf…). Combined as `ROM_REGION16_LE(0x1000000, "waveform")`, IC307 at 0xC00000.

**IC307 format — the template for KN7000 placeholder fabrication** (waveform-rom-format.md:22-121):
1. **Index table @0x0000**: 198 entries × 4 bytes: `{uint16 param_ptr; uint16 wave_offset;}` LE; `wave_offset × 16 = byte address` (granularity 16 bytes = 8 samples). First entry's param_ptr (0x0318 = 198×4) self-validates the table size.
2. **Parameter records @0x0318-0x1A2F**: variable length, `uint16 wave_start` + N param words encoded `[flags:8][value:8]` — flags 0x00 key-zone boundary (value = MIDI key, listed descending), 0x01/0x08 per-key tuning (value = signed offset), 0x40 mid-record marker (suspected loop point), 0x80 end, 0xC0 terminal zone. Loop points are believed to live here — the SubCPU never writes loop registers; the TG reads them from ROM autonomously (waveform-rom-format.md:155).
3. **PCM @0x1A30**: **signed 16-bit little-endian PCM**, full range, 186 unique multi-cycle waveforms; **index 0 = perfect 256-sample sine** (test tone). Native rate unknown; DAC (IC313 PCM69AU 18-bit) suggests 44.1/48 kHz output.

Open question logged there: "Are waveform ROMs shared across Technics keyboard models (KN6000, KN7000)?" (waveform-rom-format.md:157) — unanswered.

---

## 4. MAME State

**Mainline** (`/home/fsanches/compartilhado/mame/src/mame/matsushita/kn5000.cpp:165`): TG is `map(0x100000, 0x100003).noprw()` — a pure stub. The sound devices live on **branch `kn5000_research_tonegen`** (tip commit 9957c22f "Fix tone gen voice timing for missing waveform ROMs").

**`kn5000_tonegen.cpp` (branch, 603 lines) implements:**
- `device_sound_interface`, **stereo `sound_stream` at 48 kHz** (kn5000_tonegen.cpp:56-59).
- Full register-indirect protocol (`addr_w`/`data_w`/`data_r` mapped at 0x100000/0x100002 — branch kn5000.cpp:290-291), 64 voices × 32 regs via a group map for groups {0,1,4,5,6,8,9,A}, 13 global regs (kn5000_tonegen.cpp:137-210).
- Key-on/off from the g0.b0 state machine (0x8100/0x7E00), waveform resolve on the g0.b2 **bit-15 latch strobe** (kn5000_tonegen.cpp:182-204).
- **Synthesis**: pitch = reg[1]×2 as 16.16 step (0x8000=1.0) with octave shift from reg[8] ((note+36)/12, base octave 3); volume = (reg[2]&0xFFF velocity) × inverted reg[20] main volume; pan from reg[21]/reg[22] (0-0x78, center 0x3C = unity); linear-interpolated PCM fetch; loop = wrap-to-start while key held; **release = linear 50 ms fade (2400 samples)**; **hold counter = 4800 samples (100 ms)** so firmware status polls (data_r returns 0x8100 while held) see the voice active — note tone-generator.md:369 still says "2-second hold timer"; the branch tip reduced it to 100 ms (kn5000_tonegen.cpp:441-457, 474-603).
- **Missing-ROM strategy** (the tip commit): voices whose PCM region is absent (IC304-306) still advance a position counter using IC307's index-table lengths so sequencer part-tracking (DRAM[0x10420] bitmask) clears correctly, but render no audio (kn5000_tonegen.cpp:502-539).
- Keybed queue: `push_keybed_event()` fed from MAME input ports, read back at 0x110000/0x110002 (kn5000_tonegen.cpp:236-256; branch kn5000.cpp:292-293).

**Stubbed / approximate:** waveform-index mapping is a guess (reg[3] low byte → IC307 index; the real chip's register→ROM-address logic is unknown — kn5000_tonegen.cpp:352-366, tone-generator.md:372); no multi-stage envelope; no loop-point parsing from parameter records; waveform RAM 0x1E0000 `noprw`; `kn5000_dsp.cpp` = **DSP1 register-latch stub only** (4×0x20 register file, logs, no audio — kn5000_dsp.h:36-58); **DSP2 is not a device at all** (bit-bang decoded by SubCPU port callbacks); no effects audio anywhere (audio-subsystem.md:1945-1998). A separately documented MAME bug: PH.0 unconnected made every DSP write burn an 8000-iteration ready-poll timeout (~16 s SwbtWr block); fix = return ready on the Port H callback (swbwr-tone-init.md:152-205).

Also relevant: **SwbtWr** (`SwbtWr_ReinitBothBanks`, MainCPU system_handlers.s:1422) is the KN5000 Main-CPU tone-init dispatcher — event buffer @0xBD3C, ~450 4-byte events/preset, two ROM callback-bank tables (0xEE7786/0xEE7CA7) (swbwr-tone-init.md:38-148).

---

## 5. Transfer to KN7000 — hypotheses and known differences

All items below are **hypotheses to be verified against KN7000 firmware/hardware** (per the cross-model integrity policy) — the two firmwares share a codebase but the KN7000 sound-init layer was reworked (`SwbtWr` @0x1F410 in KN5000 is **absent in KN7000** — technics-shared-codebase.md:157).

**Likely carry-overs (test these first):**
- **Address/data register-indirect idiom.** KN5000 TG = 0x100000/0x100002; KN7000 TG ports 0x98040000/2 and 0x98050000/2 follow the same pair shape. Hypothesis: KN7000 register addresses use a KN5000-like `[group:8][bank:2][channel:6]` encoding (possibly widened for more voices), with the same **bit-15 latch-strobe SET/CLEAR** discipline on mode/extended registers.
- **Voice-control state-machine constants**: look for **0x8100 (key-on), 0x7E00 (idle), 0x1200 (decay)** writes in KN7000 TG traffic — these are firmware-chosen values likely preserved across the shared codebase.
- **Write-ordering grammar**: pitch → strobed mode/velocity → waveform → note-key → levels → main volume → KEY ON → pan/sends → strobe release; and note-off = waveform-clear then 0x7E00.
- **Numeric conventions**: inverted volume (0xFF80 = mute), pan range 0-0x78 with 0x3C center, velocity volume = vel²/4+63, pitch semitone ratio 0x8000 = 1.0 with octave = (note+36)/12 (12-entry semitone table — KN5000 ROM 0x01217D; grep kn7000_table.rom for the same 12-word table).
- **Global-register families** at groups 0x02/0x0C/0x0E (system/effects/master) with small init constants.
- **Wave-ROM layout as the placeholder template**: per-chip index table at offset 0 (`{param_ptr, wave_offset×16}` entries), parameter records with key-zone/loop flag words, **signed 16-bit LE PCM**, and a **256-sample perfect sine as entry 0**. Fabricated KN7000 placeholder ROMs (4×128Mbit C3CBQD00000x) should follow this structure so the TG-side addressing hypotheses are testable; the KN7000 readback window (0x9804/5xxx6/8/A page+offset+data) gives a direct way to validate fabricated content against the service WAVE ROM checksum test.
- **Effect-slot model**: 5 EFF slots, 56-byte/28-word parameter blocks with **word[0] = algorithm ID**, the 100-entry algorithm-name vocabulary, and the algorithm-ID → program lookup concept. On KN7000 the "program" side plausibly resolves to one of the **80 embedded SHARC microprogram records** instead of a coefficient-bytecode pointer.
- **Proprietary CC set** (0x91 reverb depth, 0x95, 0x97, 0x9B-0x9D vibrato/tremolo) and the MIDI-like internal event protocol.
- **MAME modeling recipe**: the KN5000 tonegen device (register-file + sound_stream HLE, missing-ROM timing-only voices, hold counter for firmware status polls) is a proven scaffold to port for the KN7000 TG devices; also port the PH.0-style lesson — make ready/busy status lines return "ready" or boot-time init loops will spin on timeouts.

**Known divergences (do NOT assume parity):**
- **Effects backend is architecturally different**: KN5000 = two fixed-function ASICs (DS3613GF-3BA + MN19413) with **internal, undumped ROM**, configured by a SubCPU-side bytecode interpreter; KN7000 = **one ADSP-21065L SHARC, host-booted, with all microprograms embedded in the dumped firmware** — i.e. KN7000 effects are fully emulatable in principle, KN5000's are not. The KN5000 Level-1/Level-2 bytecode machinery therefore does *not* map onto the KN7000 host-download path directly; only the parameter-translation concepts (MIDI value → coefficient curves, opcodes 0x61-0x78) may survive as C-level logic in the KN7000 firmware.
- **CPU topology**: KN5000 sound runs on a dedicated Sub CPU (TMP94C241F) behind an inter-CPU latch (0x120000) + ring buffers; KN7000's MN10300 talks to its TGs directly at 0x9804/0x9805 (the KN7000's second MCU is the SD u-COM, unrelated to synthesis). Any KN5000 SubCPU address cited above is meaningless on KN7000 — only the *protocol shapes* transfer.
- **TG chip count/part**: 1× TC183C230002 vs 2× C1BB00000709 (main+sub); voice distribution across the two KN7000 chips is unknown — don't assume 64 voices per chip from KN5000's 64 total.
- **Keybed path**: on KN5000 the keybed wires **directly into the TG** and note events are read at 0x110000/0x110002. Whether the KN7000 TGs have an equivalent key-event read port (e.g. near 0x9804000x) is unverified — worth probing, but the KN7000 may scan the keybed elsewhere.
- **Wave ROMs**: 4×32Mbit shared-address-space (16MB) vs 4×128Mbit (64MB) on private TG buses; KN5000 has no documented CPU-side wave-ROM readback window (SubCPU never reads wave data), whereas KN7000 has one — so KN7000 wave-ROM dumping via the readback window has no KN5000 precedent to copy.
- **`SwbtWr` absent in KN7000** (technics-shared-codebase.md:157): the sound-init/event-dispatch layer was rewritten; don't search KN7000 for SwbtWr-shaped bank tables — find the reworked equivalent instead.
- Doc hygiene: when citing the KN5000 DSPs, use **DSP1=IC311 DS3613GF-3BA / DSP2=IC310 MN19413** (swbwr-tone-init.md:158 has the chips swapped — a typo).

---

## 6. KN7000 VERIFICATION RESULTS (2026-07-10) — §5 hypotheses resolved against the now-working KN7000

The §5 items were hypotheses written before the KN7000 sound worked. The KN7000 tone generator
now runs firmware-driven in MAME and its per-voice register map + DSP upload have been RE'd, so
here is what actually transferred from the KN5000 and what did NOT (integrity policy: these are
now KN7000-verified facts, not KN5000 inferences). Sources: kn7000-tg-enable-gate memory,
notes/tg-voice-register-semantics.md, sharc-lle-assessment.md.

| §5 hypothesis (from KN5000) | KN7000 reality | verdict |
|---|---|---|
| Register-indirect address/data port pair | YES — MAIN 0x98040000/2, SUB 0x98050000/2, latch addr then data | **CONFIRMED (shape)** |
| Address encoding `[group:8][bank:2][channel:6]` (KN5000) | KN7000 is `[group:6 (b15:10)][channel:6 (b9:4, stride 0x10)][index:4 (b3:0)]` | **DIFFERENT encoding** |
| bit-15 latch-strobe SET/CLEAR on mode regs; key-on = 0x4014↔0xc014 strobe | NOT seen at runtime for the default sound; KN7000 note-on = the **class-0x2401 pitch write itself**; no 0x4014 strobe | **DISPROVED for KN7000** |
| Voice constants 0x8100 (key-on), 0x7E00 (idle), 0x1200 (decay) | KN7000 note-OFF/mute = **class 0x0001 = 0xC000** (+ 0x0002=0xC000, envelope regs 0x0004-0x000A → 0). No 0x8100/0x7E00/0x1200 | **DISPROVED (different constants)** |
| Inverted volume, 0xFF80 = mute | **Present** — class 0x0000 = 0xFF80 appears in the KN7000 note-on/reset block (KN5000-style inverted level survived) | **CONFIRMED** |
| Pitch: ratio 0x8000 = 1.0, octave from a 12-entry semitone table | KN7000 pitch = **class 0x2401, +0x400/semitone, C4=0xC838** (linear-in-semitone code, not a 0x8000-ratio); note→pitch computed by fw 0x4844812D via tuning tables + ÷12 | **DIFFERENT encoding (same ÷12 spirit)** |
| Effect-slot model: 5 EFF slots, word[0]=algorithm ID | KN7000 DSP = **10-slot** engine; effects load as SHARC microprograms at PM 0x8400 on top of a resident kernel (runtime upload confirmed) | **DIFFERENT (10 slots, microprograms)** |
| Effects backend: KN5000 fixed-function ASICs (undumped) vs KN7000 host-booted SHARC (emulatable) | **Exactly right** — KN7000's 80 SHARC records recovered + the host-upload path validated at runtime; KN5000's ASIC ROMs remain unrecoverable | **CONFIRMED (the key difference)** |
| MAME recipe: register-file + sound_stream HLE; make status lines return "ready" | KN7000 tonegen IS a register-file + sound_stream HLE; and the "return ready" lesson applied — the KN7000 needed the **TG-present strap** open (gate 0x500ce380) + the 0x9805000E sound-init readback latch to proceed | **CONFIRMED (recipe worked)** |

**Bottom line:** the KN5000 gave the right *shapes* (register-indirect pairs, inverted-volume
convention, ÷12 pitch spirit, HLE-with-ready-status recipe, and — decisively — the correct read
that the KN7000's SHARC effects are emulatable while the KN5000's ASICs are not), but the KN7000's
exact *encodings* (address bitfield, pitch code, note-on/off constants, slot count) are its own and
had to be measured directly. Cross-model value was real but at the level of method, not literal
register values — consistent with "shared codebase, reworked sound-init layer."