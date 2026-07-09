> Recon report produced 2026-07-09 by the sound-subsystem planning sweep (5 parallel research agents).
> Companion to notes/sound-subsystem-plan.md. Verify page/line citations before building on them.

# KN7000 sound-work knowledge & infrastructure inventory (2026-07-09)

All paths absolute. "notes/" = `/home/fsanches/compartilhado/kn7000_mame/notes/`. "driver" = `/home/fsanches/compartilhado/kn7000_mame/src/mame/matsushita/kn7000.cpp` (1611 lines, current). "kn5000-docs/" = `/home/fsanches/compartilhado/kn5000-docs/`.

---

## 1. WHAT IS ALREADY SOLVED (do not re-derive)

### 1.1 KN7000 tone-generator hardware interface — fully decoded (notes/tone-generator.md)
- **Two TG register sets**: main @ `0x98040000`, sub @ `0x98050000`. One TG access = a 32-bit word split: **HIGH 16 bits (register ADDRESS) → base+0, LOW 16 bits (DATA) → base+2** (write helper `0x487EFF92` main / `0x487EFF70` sub; disasm quoted at tone-generator.md:14-23). A 6-bit field (`and 0x3f`) is OR'd into word bits 20..25 = bits 4..9 of the address half — its meaning (channel vs group/flag) is still open (tone-generator.md:62-67).
- **Register address layout assumed KN5000-style**: `group<<8 | bank<<6 | channel(0..63)` (tone-generator.md:50-52; confirmed for KN5000, see §1.6).
- **Idle traffic**: continuous `0xFC08→0xFC0B` cycle with data 0 on both TGs = system/global refresh, NOT note data (tone-generator.md:34-41).
- **Boot init DOES drive the register path**: at ~t=0.9 s groups `0x04` and `0x0C` are written across all 64 channels/both banks, data 0 (clear/init pass) (tone-generator.md:82-86).
- **TG is write-only** — verified: every firmware ref to `0x98040000/2/4/10` and `0x98050000/2` is a write; no status read exists to satisfy (tone-generator.md:120-123, 141).
- The TG command builders sit under a **command-stream interpreter at `0x487EFExx–0x487F00xx`** (bytes ≥0x80 = commands) (tone-generator.md:66-67).

### 1.2 The precise playback blocker — localized (tone-generator.md:128-152)
- **`MainSoundAdd` = `0x4848C043`** (voice allocator) and **`MainSeqRun` = `0x484948BC`** (sequencer run) **never execute** in MAME across: boot, injected MIDI note, START/STOP double-press.
- **`MainDspCheck` = `0x484A062A` is a stub returning 0** — NOT a readiness gate. There is **no hardware handshake blocking playback**; the gap is that playback is never *triggered*. Two candidate trigger paths: (a) MIDI-receive routing to a sounding part (TMidiInput/MidiInputGrid widget config), (b) starting a rhythm/sequencer via the right panel operation (START/STOP currently navigates to rhythm-select instead of starting play).
- Earlier theory "sound init spins on `0x9805000E` so TG readiness gates notes" (midi-rx.md:39-41) is **superseded** by the above.

### 1.3 Key-bed voice-event FIFO — solved and implemented (tone-generator.md:176-224)
- `0x98050004` (and by symmetry `0x98040004`) is the **keyboard/voice-event FIFO**, identical in role to KN5000 `0x110000` "keyboard input": 16-bit word, **low byte = note, high byte = velocity, velocity 0 = note-off, empty = 0xFFFF**. Poll loops at firmware `0x484480A2` and `0x487F11A8`; downstream note handler `0x4844812D`.
- The driver implements it; **verified end-to-end**: each pushed event is read exactly once by the firmware. PC-keyboard 2-octave note input works (see §2).

### 1.4 MIDI RX — verified working to the byte level (notes/midi-rx.md)
- MIDI-1/2 = SIO SC1/SC2 at `0x34000810`/`0x34000820`, 31250 8N1; RX ISRs `0x484B1E86`/`0x484B2037`; ICRs `0x34000148` (group 0x12) / `0x34000150` (group 0x14). Injected `90 3C 64` + `80 3C 40` → ISR ran exactly 6 times (once per byte). Byte path is done; the gate is downstream routing + dormant playback (midi-rx.md:20-42, 59-75).
- RX byte read at `0x34000819`, low-level handler `0x484B312C`, MIDI-receive state at work RAM `0x50150F44..` (midi-rx.md:63-66).

### 1.5 Wave ROMs — the strategic blocker (tone-generator.md:154-174)
- **Audible emulation is impossible with the current ROM set.** PCM samples live in four undumped mask ROMs **IC203/IC204/IC207/IC208 (C3CBQD000002/1/4/3)** — physically separate chips, not in the firmware-update disks. Confirmed via service manual "8.9 WAVE ROM test" / "8.10 SOUND SYSTEM test". NO_DUMP placeholders are written (commented) in the driver ROM_START (kn7000.cpp:1526-1538).
- **Curiosity with plan value**: the service **SOUND SYSTEM test emits pure sine waves per key — needs no sample ROM** — the only path to any diagnostic-only tone (tone-generator.md:170-173).

### 1.6 KN5000 transferable knowledge (shared codebase)
From kn5000-docs/tone-generator.md (KN5000 TG = IC303 TC183C230002, 64-voice, register-indirect — the KN7000's template):
- **Full per-voice register map** (32 regs = 8 groups × 4 banks): group0.0 Voice Control (state machine `0x7E00` idle / `0x8100` key-on / `0x1200` transition), 0.1 pitch increment (0x8000=1.0×), 0.2 voice-mode/velocity (bit15 latch strobe), 0.3 waveform control, 1.x pitch/portamento, **4.0 note key info (`note<<8 | bit15`)**, 5.x modulation/extended (bit15 strobes), **8.0 main volume (0xFF80=mute)**, 8.1/8.2 pan L/R (0x3C=center), 8.3 + 9.0-9.3 DSP/effect sends, A.x aux (lines 82-112).
- **`ToneGen_WriteVoiceParams` exact 22-write note-on sequence with KEY-ON (`0x8100` to reg 0) in the middle** (lines 411-445); **note-off = `+0xC0`←0 then `+0x00`←`0x7E00`** (lines 464-468); mute idiom `0x840=0xFF00`, `0x800=0xFF80` (line 477).
- **Global registers with init values**: `0x0200-0x0205`, `0x0C00-0x0C05`, `0x0E00` (lines 183-197); init writes 2,317 register pairs (line 212).
- **Keyboard-input interface format** (0x110000/0x110002) — already ported to the KN7000 FIFO (§1.3).
- **A working MAME TG device exists**: `kn5000_tonegen_device` in `kn5000_tonegen.cpp` — register-indirect latch, 64-voice state, 48 kHz `sound_stream`, pitch/pan/volume/interpolation/release from the register file + waveform region (lines 345-374). **This is the code template for a future KN7000 TG device.**
- **Waveform ROM format** (kn5000-docs/waveform-rom-format.md): dumped IC307 = 198-entry index (param_ptr + wave_offset×16 bytes) + signed 16-bit PCM. Plausible (unverified) template for the KN7000 C3CBQD ROMs once dumped.
- **DSP caution — chips do NOT transfer**: KN5000 uses DSP1 IC311 DS3613GF-3BA (8-bit parallel) + DSP2 IC310 MN19413 (bit-bang serial); the KN7000 uses an **ADSP-21065L SHARC (IC306)** — a completely different device. What may transfer is the *firmware-side effect architecture*: 5 EFF slots, 56-byte parameter blocks (word[0] = algorithm ID, e.g. 0x0014 = CONCERT REVERB 1), a bytecode interpreter batching register writes, 12-bit effect parameters (kn5000-docs/audio-subsystem.md:425-742). But note kn5000-docs/technics-shared-codebase.md:157: the KN5000 tone-init helper `SwbtWr` is **absent in the KN7000 — "sound-init layer reworked"** — so expect divergence.
- kn5000-docs/**kn7000-sequencer.md** (KN7000-specific): sequencer engine API `MT_Seq_PlayRequest`, `EV_PlayRequest`/`EV_PlayStartIni` events, engine runs in the **AP task** — directly relevant to triggering `MainSeqRun`.
- kn5000-docs/audio-subsystem.md MIDI dispatch: CC handler map (CC#91 reverb depth → voice struct +0x7F, CC#95 chorus +0x72, etc., lines 205-219 + sound-parameter-protocol.md) — useful naming/semantics reference for the KN7000's part parameters.

### 1.7 Supporting solved context
- **I/O map of the whole 0x98 sound bank** (notes/io-map.md:132-159): `0x98000000`(16b×1), `0x98010000`(8b×3), `0x98020004/8/A/E`(8b), `0x9804xxxx`/`0x9805xxxx` sets incl. `0x9805000C/E`, `0x98060000`(8b×6, boot writes 0xFF), `0x98070000`(16b×14, boot reads = strap). Boot hardware-init order at io-map.md:177-184.
- **Interrupts/scheduler fully working** (notes/interrupt-mechanism.md): INTC at `0x34000100`, IAGR = group<<3, quick vector `0x4C03DDA0` vs scheduler vector `0x4C03DE26` (level 6 tick), ICR levels (SIO=1, tick=6). Any future TG/DSP IRQ modeling plugs into `intc_assert()`.
- **Clocks** (notes/boot-performance-and-clock.md): CPU 32 MHz (16 MHz × PLL2, MIDI-baud cross-checked); **audio master = 11.2896 MHz (256 × 44.1 kHz); X105 50 MHz + X103 24 MHz feed the DSP/TG clock section** — the sample rate for a future sound_stream is 44.1 kHz.
- **Service/factory test suite mapped** (notes/service-diagnostic-mode.md): `TestModeFunc 0x484A497B` dispatcher; sound-relevant tests `DspTestFunc 0x484A0626`, `TestCrosstalkFunc 0x484A16DD/0x484A170D`, `TestSampleFunc 0x484A173D/0x484A1766` (sample play), `MainWaveRomTestFunc 0x484A2E11`; menu pointer tables `0x4874AD34–0x4874AFF0`. Entry combo (hold C#3+D#3+C#4 at power-on) **not yet cracked** (§4).
- **Panel event codes** (notes/panel-dispatch-table.md, gui-toolkit-event-system.md): START/STOP = event `0x2020` (queue code `0x00702020`), sound-category selector = `0x2004`/`0x2086`, genre = `0x2005`; MILK event queue at `0x5000757C`; **grep `/home/fsanches/compartilhado/kn7000_disassembly/kn7000.sym` (73 KB of firmware-named symbols) before RE'ing any UI/sound function**.

---

## 2. CURRENT DRIVER SOUND SURFACE (kn7000.cpp, register by register)

Whole bank mapped to catch-all handlers: `map(0x98000000, 0x9807ffff).rw(io_r, io_w)` (line 408). `offset` = 16-bit word index (byte addr = offset<<1).

| Register | R/W | Status in driver | Where |
|---|---|---|---|
| `0x98040000` | W | **Modeled**: main-TG address latch → `m_tg_addr[0]` | io_w case `0x20000`, line 473 |
| `0x98040002` | W | **Modeled**: data → `m_tg_reg[0][addr]` if addr<0x1000 (0xFC0x group silently accepted, not stored) | line 474-476 |
| `0x98050000/2` | W | **Modeled**: same for sub TG → `m_tg_addr[1]` / `m_tg_reg[1][]` | lines 477-480 |
| `0x98040004` | W | **Stubbed**: accepted, discarded ("main TG control") | case `0x20002`, line 481 |
| `0x98040010` | W | **Stubbed**: accepted, discarded | case `0x20008`, line 481 |
| `0x98050004` | R | **Modeled**: keyboard/voice-event FIFO pop (`m_kbd_fifo[16]`, head/tail), returns 0xFFFF when empty | io_r offset `0x28002`, lines 444-449 |
| `0x9805000E` | R/W | **Modeled as readback latch** `m_snd_500e` (init loop at fw `0x4854BC59` writes d1\|0x80 and spins until it reads it back) | lines 453-454 (R), 463-467 (W) |
| `0x98070000` | R | **Modeled as strap**: returns `0x8000 \| (REARSW & 0x1000)` — bit15 = skip factory diagnostic, bit12 = MIDI-IN/BASS-PEDAL switch SW701 | lines 429-435 |
| `0x98000000`, `0x98010000`, `0x98020004/8/A/E`, `0x98040006/8/A`, `0x98050006/8/A/C`, `0x98050010`, `0x98060000` | — | **Unmodeled**: fall through to `logerror` (reads return 0) | io_r line 455-458, io_w line 484-485 |

Supporting state/plumbing:
- `m_tg_addr[2]`, `m_tg_reg[2][0x1000]` declared lines 238-239, save-stated lines 1396-1397. **Capture is silent — there is no logging/dump of captured TG registers today.**
- Key bed: `kbd_push(note,vel)` line 231-232; `INPUT_CHANGED_MEMBER(kbd_key)` lines 685-688 (fixed velocity 0x64); ports `KEYS0`/`KEYS1` = 2 octaves + C6, tracker layout Z..M / Q..I, C4=0x3C (lines 1290-1323).
- MIDI: `kn7000_sio_uart_device` byte↔bit bridge, 31250 8N1 (lines 111-147); `mdin1/mdout1/mdin2/mdout2` standard MAME MIDI slots (lines 1484-1494); RX → `sio_rx_push` → `intc_assert(0x12/0x14)` (lines 779-794); TX out works (lines 851-855). **Caveat**: SIO ch2 is double-booked MIDI-2/CPSD-SD (enum line 252); always-setting ch2 status bit6 (TxRDY) breaks boot (comment lines 726-728).
- Volume sliders `VOL_MAIN/VOL_APCSEQ/VOL_MIC/VOL_LINEIN` are **unwired PORT_ADJUSTERs** (lines 1275-1278).
- No `sound_stream`/speaker device at all; machine flagged `MACHINE_NO_SOUND` (line 1603). Machine-config TODO at line 1496-1497.

---

## 3. PROBING INFRASTRUCTURE (how to run, script, inject, log)

### Launch
- **Active build tree**: `/home/fsanches/compartilhado/kn7000_mame_build/` (binary `./kn7000`; ROMs `roms/kn7000/kn7000_{program,table}_{even,odd}.rom`). Rebuild with `SOURCES=.../kn7000.cpp` per notes/kn1500-lcd.md:11; after every rebuild run `bash /home/fsanches/compartilhado/kn7000_mame/tools/publish-binary.sh` (publishes to `/home/fsanches/compartilhado/kn7000-emulator/`).
- **Hand-run copy**: `/home/fsanches/compartilhado/kn7000_run/` (`./kn7000 kn7000 -rompath ./roms`; flags documented in RUN.txt: `-window`, `-nothrottle`, `-video none -seconds_to_run N`, `-log` → `error.log`, `-debug`). **CAVEAT: kn7000_run/roms/kn7000/ still holds the old monolithic `kn7000_program.rom`/`kn7000_table.rom`; the current driver loads even/odd images — refresh from the build tree before use.**
- Headless probing pattern (panel-completion-plan.md, panel-sweep-tooling.md): `./kn7000 kn7000 -rompath roms -video none -autoboot_script <script>.lua [-seconds_to_run N]`. Boot reaches home at ~12-13 emulated s (scripts wait to t≥15-17 s). **Throttled `-video none` keeps `register_frame_done` at 60 Hz; `-nothrottle` makes frame callbacks sparse** (panel-completion-plan note).
- Hygiene before each run: `pkill -9 -f 'kn7000 kn7000'` and `sudo -n /usr/local/sbin/drop-caches` (virtiofs ENFILE) — panel-sweep-tooling.md:32.

### Scripted button presses (the proven mechanism)
Lua `-autoboot_script`, fields resolved by mask:
```lua
local function setbtn(p,mk,v)
  for _,f in pairs(manager.machine.ioport.ports[":"..p].fields) do
    if f.mask==mk then f:set_value(v) end end end
-- e.g. START/STOP: setbtn("SEG12",0x08,1) ... hold ≥14 frames ... setbtn("SEG12",0x08,0)
```
**Presses MUST be held ~14+ frames** — 1-frame taps are cleared by the input frame-update before the 250 Hz panel scan samples them (panel-sweep-tooling.md:66-68; driver comment kn7000.cpp:944-945). Reference scripts:
- `/home/fsanches/compartilhado/kn7000_mame/tools/panel_probe.lua` — boots once, `m:save("home")` at 17 s, then per button `m:load("home")` → press → `m.video:snapshot()` (savestate reset trick avoids ~75 s reboots).
- Old-session scratchpad (191 scripts, still on disk): `/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/74c7edc4-f16b-4349-97a0-39242e320cdb/scratchpad/` — notably `sdump.lua` (env-driven PBSEG/PBMASK/PBOUT one-boot press+PPM dump), `helpid2.lua` (HELP-mode button naming via title-strip stacking), `play.lua` (plays key-bed notes by pressing `":KEYS0" "Key C4"` fields), `probe_seq.lua`, `tap.lua`. These are in a session temp dir — copy anything worth keeping into the repo.
- Useful UI tricks: **HELP = SEG08 0x08** then any button → LCD shows "HELP : <NAME>"; **DEMO×2 = return home** (DEMO = SEG09 0x40 in current ports); EXIT bound at SEG08 0x20 in the driver (kn7000.cpp:1102).

### Playing notes / injecting MIDI
- **Key-bed notes (easiest)**: press `":KEYS0"`/`":KEYS1"` fields from Lua (see play.lua) → kbd FIFO → firmware note handler. Fixed velocity 0x64.
- **Real MIDI**: `./kn7000 kn7000 -mdin1 midiin` (host MIDI source), `-mdout1 midiout` (midi-rx.md:45-48).
- **Raw MIDI byte injection**: past verification used a **temporary C++ hook in `sys_tick` calling `sio_rx_push(1, byte)`** (midi-rx.md:20-22 "temporary sys_tick hook; removed afterward"). **No Lua-accessible injection path exists today** (gap, §5).

### Capturing register writes / memory probing
- `-log` → `error.log` via `logerror` — all *unmodeled* 0x98 accesses are logged with PC context (io_r/io_w). **Modeled TG writes are NOT logged** (captured silently to `m_tg_reg`); the tick-ss+1 experiment used a temporary "log every non-FC0x TG write" hack (tone-generator.md:76-89) — re-add when needed.
- **Lua memory taps** (surviving pattern in tap.lua/probe.lua): `space:install_read_tap(lo,hi,name,cb)` / `install_write_tap` on `manager.machine.devices[":maincpu"].spaces["program"]`, with PC attribution via `cpu.state["CURPC"].value`. Used for style-table read tracing and CLUT/FB write watching; equally usable to watch TG-driver code paths or work-RAM sound state. Direct RAM pokes from Lua were used to set the panel-test flag `0x5006BFB2` (service-diagnostic-mode.md:76-83).
- **Screen validation without video**: sparse pixel-grid hash `shash()` and full-frame PPM dump via `scr:pixel` (panel-sweep-tooling.md:6-31). Note the environment conflict: `manager.machine.video:snapshot()` HANGED in the starved-virtiofs environment (panel-sweep-tooling.md:22) but worked in later runs with `-video none` (panel-completion-plan note) — the `scr:pixel` PPM dump is the always-safe path.
- **Static tooling**: `/home/fsanches/compartilhado/kn7000_disassembly/` — `kn7000.sym` (firmware reflection symbols; grep it FIRST), `tools/mn10300_sim.py` (boot interpreter), plus `unidasm <bytes.bin> -arch mn10300 -basepc 0xADDR` from the mame-sony-video tree (memory note; beware unidasm's 0xF4-opcode 1-byte mis-decode desync, boot-performance-and-clock.md:28-30).
- **How MainSoundAdd/MainSeqRun were probed**: tone-generator.md (tick zz+1) records the result but no surviving script records the mechanism; the reusable equivalents are (a) a Lua read-tap + CURPC counter, or (b) a temporary driver-side PC hook. Treat as needing to be (re)built — see §5.

---

## 4. KNOWN DEAD ENDS (do not repeat)

1. **Blind stimulus → TG traffic**: injected MIDI note-on, START/STOP press, and a "DEMO" press each produced ZERO non-0xFC TG writes (tone-generator.md:76-112). The playback engine is dormant; more blind button/MIDI pokes will not change that.
2. **"TG readiness gate" theory** — dead: MainDspCheck is a stub; TG is write-only; the `0x9805000E` latch already unblocks init. Modeling more TG/DSP *hardware* will not start playback (tone-generator.md:128-152). The work is the **trigger path** (MIDI part routing / rhythm start), then synthesis.
3. **Single-frame Lua presses are silently missed** — the original "DEMO did nothing" and several sweep no-ops were input-timing artifacts, not firmware behavior (panel-completion-plan interaction-survey note; panel-sweep-tooling.md:66-68). Always hold ≥14 frames.
4. **Service-mode entry via the voice FIFO fails**: injecting held C#3/D#3/C#4 (0x31/0x33/0x3D) into `0x98050004` early in boot does NOT enter the test menu — the boot key-check reads the held keys via some other path (panel serial or key-matrix register) or different note numbering (service-diagnostic-mode.md:49-57).
5. **Panel-test flag `0x5006BFB2=1` alone** only re-routes button dispatch; it does not bring up the test screen, and the emulator panel test is **circular** for ioport mapping (service-diagnostic-mode.md:76-102).
6. **Screen-hash button identification can be fooled** (EXIT=SEG20 0x01 was actually TEMPO+; the HELP screen displays the tempo digit) — use HELP-info naming instead (panel-sweep-tooling.md:75-80).
7. **SIO ch2 status bit6 (TxRDY) must not be forced set** — breaks boot because ch2 doubles as MIDI-2 (kn7000.cpp:726-728).
8. **Single-boot multi-press sweeps are contaminated** (screen stack, modal screens); use fresh boot or savestate-reset per press (panel-sweep-tooling.md:34-42).
9. **Populating the custom flash from 01CTMINI.AST did not fix the "8 Beat 1" style-name defaulting** — names are templated at boot `0x484420CB`, a separate bug (memory note kn7000-ast-codec-zlib) — relevant if the rhythm engine is used as the playback trigger.
10. **Any synthesis-stage work yields no audio until IC203/204/207/208 are physically dumped** (tone-generator.md:154-174). The one exception that needs no samples: the service SOUND SYSTEM sine test.

---

## 5. GAPS (infrastructure the sound plan needs but does not exist)

1. **TG-write trace/diff tooling.** `m_tg_reg` capture is silent and Lua-invisible. Needed: a driver-side switch (env var/ioport/Lua-pokeable flag) to `logerror` non-FC0x TG writes with timestamps + PC, and/or expose `m_tg_reg` as a memory share Lua can read; plus a small diff script (baseline vs stimulus) — this is the primary observable for "did playback trigger".
2. **Function-hit counters for `MainSoundAdd 0x4848C043` / `MainSeqRun 0x484948BC`.** The zz+1 probe mechanism was not preserved. Needed: a reusable harness (Lua tap on the function's stack-frame writes, MAME debugger `bpset` via autoboot, or a driver debug hook) that reports call counts per run.
3. **Lua-drivable MIDI byte injection.** Today raw injection requires editing C++ (`sio_rx_push` hook). A small debug port (e.g. a Lua-pokeable RAM mailbox polled by `sys_tick`, or `emu.register_periodic` writing to an exposed function) would make MIDI-routing experiments scriptable.
4. **Screen-navigation macro library.** Triggering playback likely requires navigating UI (MIDI settings screen to check receive routing; rhythm select → start). No reusable "navigate to screen X" macros exist — only one-off press scripts; the button-identity map still has holes (0x2040/0x2030 families etc., panel-completion-plan.md). The savestate trick (panel_probe.lua) + HELP-naming are the building blocks.
5. **Service-mode entry** — cracking the boot key-combo read (or force-branching to `TestModeFunc 0x484A497B`) would unlock `TestSampleFunc`/SOUND SYSTEM sine test = the only sample-ROM-free audio; the early-boot key read path is unfound (§4.4).
6. **A KN7000 TG `sound_stream` device** does not exist (kn5000_tonegen.cpp is the template) — deliberately deferred behind trigger-path + wave-ROM dumping.
7. **DSP (IC306 ADSP-21065L) host interface unidentified** — which of `0x98000000/0x98010000/0x98020004..E/0x98060000` talk to the SHARC (boot pokes `0x98060000=0xFF`, reads `0x98070000`) is unmapped; no SHARC boot-image source identified. Static RE gap; MAME has an ADSP-21062 SHARC core to evaluate for reuse.
8. **Housekeeping**: refresh `/home/fsanches/compartilhado/kn7000_run/roms/` to the even/odd ROM layout; rescue the reusable Lua scripts out of the volatile session scratchpad (`/tmp/claude-1000/.../74c7edc4.../scratchpad/`) into `kn7000_mame/tools/`.
9. **Key-bed completeness**: only ~2 octaves, fixed velocity, exact KN key-range/split unverified, downstream voice-slot/MIDI-out processing unconfirmed (tone-generator.md:220-224) — matters once notes are expected to allocate voices.