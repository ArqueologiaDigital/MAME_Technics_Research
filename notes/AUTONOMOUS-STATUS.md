# Autonomous work status — sound-subsystem implementation

This file is the resume point for the autonomous cron loop. Felipe is away for
many hours (started 2026-07-09 ~23:xx). Keep it updated at the end of every work
chunk: what is DONE, what is IN PROGRESS, what is NEXT. Read it first on every
cron tick.

## Hard rules (do not violate)
- **NEVER run MAME with `-video none`** (see memory `never-video-none`). Display
  is available (DISPLAY=:0, wayland-0). Run with visible video.
- Commit notes/plans/code FREQUENTLY (small commits, clear messages).
- After any driver rebuild: run `tools/publish-binary.sh` to refresh the
  host-accessible `kn7000-emulator/` copy (memory `publish-kn7000-binary`).
- After any website edit: rebuild the Jekyll site with Option B
  (`jekyll build -s ~/compartilhado/kn5000-docs -d /tmp/kn-site`) — memory
  `technics-docs-site-build`.
- If the mount throws "Too many open files in system" (ENFILE): run
  `sudo -n /usr/local/sbin/drop-caches` (memory `virtiofsd-enfile-fix`). The
  `--inode-file-handles=prefer` fix is already applied and holding.
- Preservation integrity: reusing another model's ROM is an UNVERIFIED HACK
  until proven (memory `cross-model-rom-integrity`). Placeholder wave ROMs are
  clearly labelled synthetic — fine for bring-up.

## Build / run cheat-sheet
- Driver source: `kn7000_mame/src/mame/matsushita/kn7000.cpp`
- Build dir: `kn7000_mame_build/` — build with the project's usual make (SUBTARGET
  kn7000). Binary: `kn7000_mame_build/kn7000`.
- Run: `cd kn7000_mame_build && ./kn7000 kn7000 -rompath roms -seconds_to_run N
  -nothrottle -autoboot_delay 0 -autoboot_script /path.lua` (NO -video none).
- Lua gotchas: RETAIN every `emu.add_machine_frame_notifier(...)` and
  `install_read_tap/install_write_tap(...)` return value in a `_G` table or GC
  unsubscribes it silently. Program space is 32-bit: taps must cover aligned
  4-byte units (`base..base+3`). Keybed: ports `:KEYS0`/`:KEYS1`, fields "Key C4"
  etc; `field:set_value(1/0)`.

## Current branch: phase-c-stage2 (kn7000_mame)

## DONE
- Phase A: effects-DSP host stub gated by PORT_CONFNAME (verified).
- DSP full disasm+docs (80 records) in kn7000_disassembly (committed).
- Cross-model DSP compare (KN6000==KN6500) committed.
- Placeholder wave ROM generator committed.
- Phase C Stage 0: bring-up sine synth device (KN7000_TONEGEN), audible on PC key.
- Phase C Stage 2 plumbing: io_w routes TG writes to m_tonegen->tg_write();
  m_tg_reg widened to [2][0x10000]; pitch capture (0x2000/0x3000).
- virtiofsd root cause fixed (--inode-file-handles=prefer).
- Website: kn7000 sound-subsystem / effects-dsp / gui-map pages added.

## ★★ MILESTONE COMPLETE 2026-07-10 — KN7000 makes firmware-driven sound

The KN7000 now produces AUDIBLE, correctly-pitched notes driven by its own firmware
voice engine. Committed (96c702c) + published (kn7000-emulator/ binary @ 00:57).

What shipped:
0. Sound is an OPT-IN machine-config switch: CONFIG bit1 "Tone generators /
   firmware sound (experimental)", DEFAULT OFF. OFF = known-good home-screen boot,
   silent (gate 0x7F) — NO regression, verified. ON = gate open + sound, but boot
   then rests on the SD menu (paused SD subsystem). Enable via Tab -> Machine
   Configuration, or cfg CONFIG value=2. (Same pattern as the DSP host-stub switch.)
1. TG gate opened (when the switch is ON): io_r(0x98070000) sets strap bits 1,2
   (TG present) -> gate flag 0x500ce380 = 0x40 -> firmware programs voices per note.
2. SD Card menu at boot: opening the TG gate advances boot into the SD subsystem,
   which is separately PAUSED (notes/sd-card-emulation-plan.md), so it lands on the
   SD Card menu instead of the home screen. NOT caused by the CPSD probe (verified:
   menu shows with the probe both on and off) and NOT by card-detect ("no card"
   forced -> still SD menu). This is a known SD-HLE gap, tracked separately. Sound
   and the key bed WORK regardless of the displayed screen (melody renders correct
   pitches from the SD-menu boot state).
3. kn7000_tonegen_device synthesizes from the firmware's TG writes:
   - pitch from class 0x2401: note = 60 + (data - 0xC838)/1024  (+0x400/semitone,
     C4=0xC838=MIDI60). VALIDATED spectrally: C4/E4/G4/C5 fundamentals = 262/330/
     392/523 Hz (dominant), no clipping.
   - note-on = 0x2401 write; note-off = 0x0001=0xC000 mute; per-voice attack/decay
     envelope (self-limiting since this sound rings until stolen).
   - placeholder SINE timbre (wave ROMs undumped).

### REMAINING / NEXT (refinements, not blockers) — for the cron loop to continue
DONE: gate fix, firmware-driven synth, pitch decode, opt-in switch (home-screen boot
preserved + verified), publish, website sound page, blog Part 10, memory. DONE (cron
tick 2026-07-10): exponential voice decay (natural, verified); corrected
notes/tg-voice-register-semantics.md with the dynamic capture (pitch=0x2401,
note-off=0x0001=0xC000 -- superseded the wrong static guesses). Remaining, in value order:
1. Quantitative envelope/level decode: the per-voice group-0x00 registers (0x0000-
   0x000D, key-scaled: 0x0001 C4=5400/C5=6300; 0x0004-0x000A = AE00/2C00/9900/35E8/
   25B0; 0x2009=5FFF level) encode the firmware's real attack/decay/sustain rates +
   level. Decode the rate/level encoding (cross-ref kn5000-docs tone-generator.md
   ToneGen_WriteVoiceParams ~L411-444) and drive the synth envelope from them instead
   of the fixed exponential. Also velocity (kbd_push high byte -> level).
2. Velocity: the firmware passes velocity (kbd_push high byte); map it to level.
3. Effects DSP: Phase A host stub verified; next is running/emulating the SHARC
   effect on the audio stream (reverb/chorus) — large; see notes/sound-subsystem-plan.md.
4. Placeholder wave ROMs for a richer-than-sine timbre (kn7000_disassembly/tools/
   make_placeholder_waveroms.py) — but the tonegen would need to honour the firmware's
   sample-select writes to be meaningful; low priority vs the honest sine.
5. SD subsystem (separate, PAUSED): finishing it would let boot reach the home screen
   WITH sound enabled (removing the opt-in trade-off). See notes/sd-card-emulation-plan.md.
6. Cross-model sound RE: PARTIALLY DONE (cron tick 2026-07-10) — KN6000 ALREADY
   drives its TGs live on key-bed notes (no strap gate; boots to play screen, no SD
   block — a cleaner platform than KN7000). Register layout DIFFERS: fine pitch =
   class 0x5800, level 0x4000=0x3FFF, sample params group 0x80. See
   notes/sound-cross-model-kn6000-kn6500.md (dynamic-capture section). TO MAKE KN6000
   SING (high value, next): (a) find its octave/coarse pitch register — needs
   multi-octave notes, but KN6000 :KEYS1 (C5+) gave NO writes, so first check the
   KN6000 key-bed→note mapping / KEYS1 wiring; (b) add a KN6000 branch to
   kn7000_tonegen_device::tg_write (pitch from 0x5800+octave, gate/level from
   0x0000/0x4000); (c) flip kn6000/kn6500 to MACHINE_IMPERFECT_SOUND (likely no CONFIG
   switch needed). KN5000/KN2400/KN2600 still unchecked.

## ★ BREAKTHROUGH 2026-07-10 — the TG gate is found and validated

**Root cause of "no sound": a TG-enable gate flag `0x500ce380` in library RAM
(0x7F = disabled, 0x40 = enabled), tested by ~30 library wrappers that suppress
every per-voice write when it is 0x7F.** It is set from a **probe of the hardware
strap word `0x98070000`** at firmware `0x484d7713`: it tests bit1 (0x02) and bit2
(0x04). If bit1 is CLEAR the probe returns 3 = "no TG" and the gate stays 0x7F.

The MAME driver's io_r returns `0x8000 | (rearsw & 0x1000)` for `0x98070000`
(kn7000.cpp ~line 559) → bits 1,2 are zero → probe = 3 → **gate closed forever**.
The real KN7000 HAS tone generators, so those strap bits must be set.

VALIDATED live (Lua read-tap forcing `data | 0x0006` on 0x98070000):
- gate flag `0x500ce380` becomes **0x0040 (ENABLED)**.
- On a key press the firmware now WRITES TG voice registers: **class 0x3000 =
  13-bit pitch** (C4→0x0BE8, E4→0x0E52…), classes 0x0001/0x0002 = per-voice
  level/env, from PC 0x4C036FDD. TWO voices allocated per note (dual-layer sound).
  Previously: zero. This is "the firmware driving the notes."

CONSEQUENCE (observed by Felipe on video): with the gate open, boot progresses
further and lands on the **SD Card menu** instead of the home screen. Bits 1,2 are
read ONLY by the TG probe (all 14 strap readers mapped), so the SD menu is NOT a
strap-bit side effect — it is the known-flaky SD subsystem now being reached
because sound-init completes. Must handle so boot reaches the play screen.

Subagent full map saved (region2 == 0x4C library image; runtime = flash+0x0384702F).
Key RAM: per-voice HW shadow `0x500ca0b0` stride 0x84 (+0x54 = pitch dword, low 13
bits → class 0x3000); voice state `0x500af940` stride 0xB4; gate `0x500ce380`;
voice-active bitmap `0x500d288c`. TG write primitive: voice<0x40→SUB(0x98050000),
≥0x40→MAIN(0x98040000); reg addr = (voice<<4)|classIndex.

### NEXT (revised, in priority order)
1. Apply the strap fix in the driver (set the TG-present bit(s) on 0x98070000).
   Decide bit1-only (probe=2) vs bits1,2 (probe=1) — both open the gate; pick the
   hardware-accurate one. Rebuild, verify voice writes appear WITHOUT the Lua patch.
2. Keep boot on the play/home screen despite the gate being open: investigate why
   the SD Card menu auto-opens (likely SD card-detect / CPSD); make boot land on
   the play screen (e.g. SD card absent by default). See memory kn7000-sd-strap-gate.
3. Wire the tonegen to SYNTHESIZE from the real TG voice writes: decode class
   0x3000 pitch (map 13-bit code→Hz), key-on/level (0x0001/0x0002), gate voices.
   Replace the Stage-0 kbd_key sine with firmware-driven voices. Publish binary.
4. Calibrate the pitch code→Hz map from several notes; handle the 2-voices-per-note.

## IN PROGRESS — Stage 2 gating question (SIGNIFICANT PROGRESS 2026-07-09)
Does the FIRMWARE emit TG voice writes when a keybed note is played? Answer so
far: **NO — the note is fully received but never becomes a voice.** Established
by a series of Lua tap diagnostics (all runs WITH video):

CONFIRMED end-to-end input path:
- `field:set_value()` on `:KEYS0` DOES fire `kbd_key` (bring-up sine audible in
  -wavwrite at the press times; peaks ~4100-4265).
- The firmware CONSUMES every note-on/off from the FIFO at 0x98050004: PC
  0x484480A3 read note 60/64/67 vel 100 then 0 (C4/E4/G4). 6/6 consumed.
- FIFO poll histogram: ONLY the program.asm reader 0x484480A2/B7 polls at runtime
  (~67k polls each); region2's own reader at 0x487f11a6 does NOT poll during play.
  => the "double-reader steals the note" hypothesis is DISPROVED.

CONFIRMED the play->TG path never fires:
- During the press window: **0** TG writes of ANY non-idle class. The only
  non-idle TG writes in the whole run are BOOT-TIME:
  * groups 0x04/0x0C (channel-config sweep, data 0) from 0x4C037023/0x4C03702F
  * group 0x8000 params (idx 8/A, e.g. a=8008 d=0300, a=800A d=7F00) 426x at t=0
    from 0x4C036FBA  -- boot voice/param init, NOT note voicing.
  * 0xFC08..0xFC0B idle refresh (~390x each) continuously.
- My earlier assumed pitch class 0x2000/0x3000 and key-on 0x4014 NEVER appear at
  runtime. The low-level TG driver lives in the **0x4C region** (0x4C036xxx-
  0x4C037xxx, self-loaded lib ROM); region2 (0x487eff80) is a second TG writer.

DATA FLOW so far: keybed FIFO -> 0x484480A2 -> 0x4844812D (note->pitch via tables
0x48731534 / 0x487314F4/F6/F8, div-by-12; writes a per-key struct via a0; does
NOT touch TG). Then region2 flush 0x487eff80 emits ONLY idle. So the missing link
is the VOICE ALLOCATOR: something must assign the note to a free TG channel, load
the current sound's waveform/params, set pitch+key-on. That never runs / is gated.

LEADING HYPOTHESES for the gate (to resolve): (a) no playable Sound assigned to
the keyboard part in the emulated boot state (cf. known 8-Beat-1 / .AST / style
templating bugs); (b) a "sound-engine active / part-enabled / local-control"
flag never set; (c) play path waits on a stubbed subsystem (DSP / sound handshake).
A background subagent is statically mapping region2's flush + the gate (RAM
addresses + test instruction). Await it, then target the specific flag/struct.

MORE STATIC DETAIL (2026-07-10):
- The 0x4C-region TG driver == program_region2.asm ROM image. Mapping:
  lib X == program ROM 0x487B8FD1 + (X - 0x4C000000). So runtime 0x4C036F80 ==
  ROM 0x487EFF80. The block 0x487eff69..0x487f0078 is a set of low-level TG
  register-WRITE PRIMITIVES: channel<0x40 -> SUB(0x98050000), >=0x40 ->
  MAIN(0x98040000); reg value built as (chan<<20)|hi|lo. Idle refresh & boot init
  just call these leaves. The voice-flush LOOP/ALLOCATOR is their CALLER (subagent
  is finding it).
- Keybed task 0x48448015 (RTOS-scheduled, no direct callers) reads FIFO via
  0x4844807c/0x484480a2, decodes each note with 0x4844812d into a STACK-LOCAL
  struct (sp+0xc), gathers up to 16 notes into a stack array (sp+0x12), and
  RETURNS without voicing. Flag 0x50007768 and latch 0x501496a2 are internal
  hold/sustain state (self-consumed). 0x50007764 = a pending-count gate: when
  nonzero it calls 0x48448206 instead of reading the FIFO. => this path drains
  keybed events; the actual note->voice allocation is a DIFFERENT task that is not
  emitting -> strongly consistent with hypothesis (a)/(b): no playable performance
  loaded at boot, so the voicer allocates nothing.

DECISION: do NOT rabbit-hole further on the boot-performance gate in parallel
with the subagent (it overlaps the known .AST/style/8-Beat-1 boot bugs, a large
separate effort). Two productive tracks that are UNBLOCKED by the gate:
  T1 (this session): build+verify the tonegen's TG voice-register -> audio
     synthesis engine, driven by INJECTED voice writes (Lua simulating what the
     firmware would write), so the synth path is proven end-to-end and ready.
     Requires reconstructing the TG register map from the DRIVER CODE (subagent
     result), not runtime observation.
  T2: Stage 1 — load placeholder wave-ROM bank-0 samples into the tonegen so it
     plays a wavetable timbre instead of a pure sine (independent, committable).

## NEXT (in order)
1. Re-run /tmp/ktd.lua diagnostic WITH VIDEO; read RESULT + FIFO consumed count.
2. If firmware consumes the note but writes no voice regs → the sound engine is
   in a non-playing UI state; investigate what selects a playable Part/voice
   (Chord Finder / SOUND select). If it never consumes → input path or firmware
   key-scan not reached; inspect how the real key matrix reaches the firmware.
3. Once firmware-driven voice writes appear: map pitch (0x2000/0x3000 13-bit) →
   Hz and key-on (0x4014 strobe) → note gate; drive the tonegen synth from the
   real voice writes (replace the direct note_on tap). Read placeholder wave
   bank-0 samples (Stage 1) for timbre.
4. Rebuild, publish-binary, commit. Update this file + website + memory.

## Plan of record
`kn7000_mame/notes/sound-subsystem-plan.md` (rev2 + execution log). The full
multi-phase plan (A..H) lives there; follow it in order, deferring phases that
need the physical unit (G/H).
