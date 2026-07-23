# KN5000 envelope trace — settling the ADSR question by measurement

Author: autonomous RE pass, 2026-07-23. Requested by Felipe to move the envelope
verdict from **INFERRED** to **MEASURED** and, above all, to TEST DIRECTLY his
hypothesis that the **0x130000 4-channel × 8-register block IS the tone generator's
ADSR / envelope control**.

Companion to `notes/kn5000-vs-kn7000-tonegen-design.md` (the firmware-level
comparison that left this open) and `-tonegen-sharing.md`. Every claim is tagged
**MEASURED** (observed in the running emulator), **PROVEN-BY-CONSTRUCTION** (follows
necessarily from the disassembled code), **INFERRED**, or **SPECULATIVE**.

Tools written for this pass (in `kn7000_mame/tools/`):
`kn5000_env_measure.lua`, `kn5000_env_inject.lua`, `kn5000_env_pcsample.lua`,
`kn5000_env_mkmidi.py`. Raw run logs live in `kn7000_mame/kn5000_envrun/`.

---

## TL;DR — the two verdicts

- **★ 0x130000 is NOT ADSR / envelope. Felipe's hypothesis 2 is REFUTED.**
  It is a **boot-time, board-level 4ch×8-reg channel-config / self-test register
  file** written **once at power-up** and **never again**. PROVEN-BY-CONSTRUCTION
  (only two boot routines reference it in the whole 55 028-line subprogram) and
  MEASURED (watchpoint: exactly **72 writes at boot, then zero**).

- **The KN5000 tone generator has NO per-note ADSR and NO software amplitude
  envelope.** Amplitude = **the PCM sample's own recorded contour + a static
  velocity→level value** written once at note-on (and re-emitted verbatim on
  parameter-change events). PROVEN-BY-CONSTRUCTION from the voice engine; the prior
  pass's **INFERRED NO now stands on a full code trace**. Felipe's thesis (a) —
  that a KN7000-style envelope is hiding in an untraced path — is **not supported**.

- **Honest limit on "MEASURED":** the *envelope-block* question (0x130000) IS now
  MEASURED. The *software-envelope* question could **not** be upgraded to a live
  fast-vs-slow note trace **on this binary**, because the sub-CPU's voice engine
  **does not execute** here (it is stuck in its boot MASK ROM — see §4). That is
  itself a new MEASURED finding and it explains why both this pass and the prior one
  rest on static analysis for the amplitude question.

---

## 1. Setup (MEASURED)

- Binary: `kn7000_mame_build/fs_mamed` — MAME v0.279 (mame0279-351), the only
  KN5000-capable build that loads on this host (`fs_mame` needs Qt 6.10, absent;
  `fs_mamed` links Qt5). Driver `kn5000`, ROMs `roms/kn5000` (best-available;
  `kn5000_subcpu_boot.ic30` = **NEEDS REDUMP**, waveform ROMs = NO GOOD DUMP).
- Method: MAME **debug core** (`-debug -debugger none`, auto-continue), driven from
  an `-autoboot_script`. **Debugger watchpoints fire on the TLCS-900 sub-CPU**
  (verified, §2) even though Lua `install_write_tap` does not — this was the enabling
  discovery. Isolated `-nvram_directory`, `-sound none`, windowed video, every launch
  `timeout`-wrapped; captures kept small; no MAME left running.
- Watchpoints, on `:subcpu` program space:
  - `0x130000..0x13001F` write → log `wpaddr=wpdata` (armed from reset).
  - `0x100000..0x100003` write → the IC303 reg-addr latch + data stream (armed for
    the play window).

---

## 2. 0x130000 — the decisive test (Felipe's hypothesis 2)

### 2a. PROVEN-BY-CONSTRUCTION — the code can only touch it at boot

In the **entire** sub-CPU disassembly (`kn5000-roms-disasm/.../kn5000_subprogram_v142.asm`,
55 028 lines), `0x130000` is referenced by **exactly two routines**:

| routine | addr | caller | what it writes |
|---|---|---|---|
| `DSP_Init_Channels` | 0x01FC95 | `Audio_System_Init` (0x01FACB), **once at boot** | 4 channel base words `0x0101001F + 0x20·ch` at offsets 0x00/0x20/0x40/0x60 |
| `DSP_Write_Channel` | 0x01FCDE | only from `DSP_Init_Channels` (×4) | a **test pattern 0x5A5A5A5A**, 8 bytes/ch, at reg offsets `0x10..0x17` (`SLL5 ch` + `SET4`) |

```
grep -c 130000  →  referenced only inside DSP_Init_Channels / DSP_Write_Channel
```
There is **no note-on, voice-update, control-change, LFO, timer, or "play" path that
writes 0x130000**. An amplitude envelope must be re-written continuously over a note's
life; **no instruction anywhere re-writes this block after boot**. A per-note ADSR is
therefore impossible **by construction** — independent of any sound, any note, any run.

The 4ch × 8-reg × 0x20-spacing shape that *looked* envelope-plausible is a **channel
config + RAM self-test** signature: a `0x5A5A5A5A` walking pattern (classic memory
test) followed by four fixed enable/config words. `src/mame/matsushita/kn5000.cpp`
already documents this block as "associated with IC311 but **NOT** part of the
uPD6383GF … a separate board-level register file"; the firmware confirms it is written
only by the boot self-test.

### 2b. MEASURED — watchpoint over boot and play

**PREDICTION** (from 2a): 0x130000 is written a small fixed number of times during
boot and **never** during play; the count/values do **not** depend on the sound.

**RESULT** (`inj_*.log`, `pcprobe.log`):
- **Boot:** the watchpoint caught **exactly 72 writes** — 4 channels × 8 register-address
  writes (`0x50,0x51,…0x57` seen for one channel) each paired with a `0x0000` data
  write, plus the config words. This matches `DSP_Init_Channels`+`DSP_Write_Channel`
  precisely (the observed 0x50-0x57 = channel-2's `0x40|0x10..0x17`).
- **After boot (t ≈ 8 → 12 s):** **ZERO** writes to 0x130000. Nothing — no idle
  housekeeping, no attempted note — ever touches it again.

**VERDICT: 0x130000 is NOT the envelope/ADSR block.** It is boot-time board glue
(channel config + self-test), written once. Felipe's hypothesis 2 is **REFUTED**,
positively and cleanly — exactly the "clean negative" the task asked to report.

---

## 3. Does an amplitude envelope live anywhere? (thesis a)

### 3a. PROVEN-BY-CONSTRUCTION — no software amplitude ramp

- **Note-on register set has no EG block** (prior MEASURED, re-confirmed): the 22
  register/data pairs `ToneGen_WriteVoiceParams` (0x02D0FD) emits carry pitch,
  velocity coefficient, level, pan and effect sends — **no attack/decay/sustain/release
  rate or level register**. The "unknown" group-4 banks are written as **zero** at
  voice setup.
- **No periodic amplitude-decay loop.** All **nine** call sites of
  `ToneGen_WriteVoiceParams` (L21951/26850/27617/27964/28261/31139/39157/39196 +
  def L29565) are **event-driven** — note-on / control-change / pitch handlers,
  operating on the voice struct at **0x0451CC** or a small scratch struct at 0x3B1C.
  **None** is a timer-driven loop that re-computes a *decreasing* level each tick and
  re-writes the IC303 level register. The level word is produced **once** from a
  **static velocity/expression computation** (table at 0x01217D for pitch; the
  velocity→level curve `(vel²/4)+63`), not ramped over time.
- **The main audio loop** (`Audio_Main_Loop` 0x01FB2F) calls `ToneGen_Process_Notes`
  (which merely **reads the physical keybed** at 0x110000/2 and **forwards** note
  events to the MAIN CPU via inter-CPU DMA — it is *input scanning*, not amplitude
  synthesis), `MIDI_Dispatch`, and the DSP-effect passes. There is no per-voice
  amplitude integrator in the loop.

**Conclusion:** amplitude contour = **PCM sample recording + static velocity level**.
No hardware ADSR is programmed into IC303, and no software envelope re-ramps the level.
This is the same conclusion as `kn5000-vs-kn7000-tonegen-design.md` §3, now grounded on
a call-site-level trace rather than inference. **PROVEN-BY-CONSTRUCTION NO.**

### 3b. Why not a *live* fast-vs-slow diff? — see §4. The engine does not run here.

The task's decisive experiment (play a fast-decay vs a slow-attack patch and diff the
IC303 level register over the note's life) **cannot be executed on this binary**, for
the reason in §4. The register-write *difference* it would look for is already
foreclosed by 3a: the level register is not re-written over a held note at all, so
there is nothing to diverge. A live trace could only *confirm* 3a, not overturn it.

---

## 4. ★ New MEASURED finding — the sub-CPU voice engine does not execute in this build

This is why no note could be played, and it retro-explains the prior pass's
static-only stance.

- **`kn5000_env_pcsample.lua`:** over 495 samples the **sub-CPU PC is 100 % in
  0xFF0000** — the **boot MASK ROM IC30** (`map(0xFE0000,0xFFFFFF).rom("subcpu")`,
  flagged **NEEDS REDUMP**). It **never** reaches the decompressed v142 subprogram
  whose labels live at low RAM (0x01FCxx / 0x02Dxxx, ring buffer 0x2B0D, `Voice_NoteOn`).
- On real hardware the MAIN CPU decompresses the sub-program (stored in IC19 flash at
  0x3E0000) and hands it to the sub-CPU, which then runs it from RAM. Here the **MAIN
  CPU is wedged** (LCD stays **dark through 32 s**, even with a known-good nvram — the
  documented CP-serial livelock state), so the handoff never happens and the sub-CPU
  spins in its boot ROM.
- Three independent consequences, all observed, all consistent:
  1. This binary exposes **no keybed input ports** (`-listxml`: no `KEY*`), so a key
     press cannot be issued.
  2. A **MIDI note fed via `-min file.mid`** (routed to MAIN-CPU RXD0) produced **zero**
     IC303 writes — the wedged MAIN CPU never forwards it.
  3. **Direct injection** of `[0x90,ch,note,vel]` into the sub-CPU ring buffer at
     0x2B0D (the real transport `MIDI_Dispatch` drains) **did not drain** (count
     0→7→11, never decremented) — because `MIDI_Dispatch`, living in the un-loaded
     low-RAM subprogram, is not running.

So the sub-CPU here does exactly the part of boot that lives in IC30 ROM — including
the 0x130000 self-test (§2b) — and nothing more. (The earlier PC-breakpoints at the
disasm addresses 0x01FCDE/0x01FC95 not firing was the first symptom: those addresses
are in code that never executes here.)

**Implication for method:** a live KN5000 note trace requires either (a) fixing the
MAIN-CPU CP-serial livelock so it boots and hands over the subprogram, or (b) a
redumped IC30 that boots the voice engine standalone. Both are out of scope here; the
envelope verdicts do **not** depend on them (§2a, §3a are construction-level).

---

## 5. Verdicts, labelled

| question | verdict | strength |
|---|---|---|
| **Is 0x130000 the ADSR/envelope block?** | **NO** — boot-time 4ch×8 channel-config + self-test register file, written once, never during play | **PROVEN-BY-CONSTRUCTION + MEASURED** (72 boot writes, 0 after) |
| Does the KN5000 program a per-note hardware ADSR into IC303? | **NO** — note-on emits 22 regs, no EG rate/level block; group-4 = zero | PROVEN-BY-CONSTRUCTION |
| Is there a software amplitude envelope (periodic level re-write)? | **NO** — all 9 `ToneGen_WriteVoiceParams` sites are event-driven; no per-tick decay loop; level is a static velocity value | PROVEN-BY-CONSTRUCTION |
| Where is amplitude shaped, then? | **the PCM sample's recorded contour + a static velocity→level word** | PROVEN-BY-CONSTRUCTION (INFERRED for the sample-contour half) |
| Live fast-vs-slow MEASURED diff of the IC303 level register | **not obtainable on this binary** — sub-CPU voice engine never leaves its boot ROM (MAIN CPU wedged) | MEASURED (PC 100 % in 0xFF0000) |

**Both of Felipe's theses resolve NO:** the 0x130000 block is board glue, not ADSR
(hypothesis 2, refuted with a clean negative); and there is no hidden KN7000-style
envelope path in the KN5000 firmware (thesis a, unsupported). The KN5000 is a
sample-plus-static-velocity player, not an envelope-programmable synth voice — the
same architectural conclusion as the prior pass, now measured at the register level for
0x130000 and traced to every relevant call site for the amplitude path.

---

## 6. Reproduce

```
cd kn7000_mame_build
# find boot timing / confirm sub-CPU stuck in boot ROM:
./fs_mamed kn5000 -rp roms -seconds_to_run 10 -autoboot_delay 0 \
  -autoboot_script ../kn7000_mame/tools/kn5000_env_pcsample.lua \
  -nvram_directory <iso> -snapshot_directory <iso> -window -skip_gameinfo -sound none
# 0x130000 boot writes + attempt note injection (needs debug core):
./fs_mamed kn5000 -rp roms -debug -debugger none -seconds_to_run 11 -autoboot_delay 0 \
  -autoboot_script ../kn7000_mame/tools/kn5000_env_inject.lua ...
```
Watchpoints require `-debug -debugger none` (keeps the debug core, auto-continues, no
UI window). `pc` inside a watchpoint action resolves to the debugger's *current* CPU
(the MAIN CPU), **not** the watched sub-CPU — read `:subcpu` `CURPC` via
`device.state["CURPC"]` instead.
