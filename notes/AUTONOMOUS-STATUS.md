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

## ★★ F.3 AUDIO ROUTING WORKS 2026-07-10 — TG audio flows THROUGH the effects DSP (audible)

The tone-generator audio now runs through the ADSP-21065L and out to the speakers.
Felipe confirmed AUDIBLE: DSP off = TG passes through unchanged; DSP on = the output
sounds DIFFERENT (the DSP is processing the sound). Committed kn7000_mame 4514170,
published, blog pending. Built on the verified F.3 research (notes/f3-implementation-
plan.md) + runtime probes (notes/f3-iop-runtime-capture.md).

What shipped:
 - Step 1 (aliasing, commit 61556c3): 21065L internal SRAM 0x9000-0x1FFFF now shared
   across the PM and DM buses (address-map handlers with the core's <<16/>>16 48-bit
   convention, DRC-safe) so the biquad reads the host-loaded coefficients (verified
   PM(0x9800)==DM(0x9800)) instead of zeros.
 - Step 2 (commit 4514170): iop65l_w walks the kernel's DMA transfer-control blocks to
   derive the 8 SPORT autobuffer bases at runtime (TX0=0xC342, RX0=0xC362, etc.).
 - Verified the audio contract by probe: 1 stereo frame per IRQ0 (2 out words/int ->
   44.1kHz/sample, tick rate is right), in/out are contiguous 8-frame rings 0x20 apart,
   default passthrough copies in->out. SPORTs externally clocked; audio via DMA not PIO.
 - Step 3 (routing): kn7000_dsp_bridge_device between TG and speakers; its stream and the
   dsp_audio_tick swap frames through two rings (feed TG->DSP input, take DSP output->
   speakers). Transparent when the DSP is off (no regression, verified).

CFG GOTCHA (cost hours): the CONFIG bits are SEPARATE PORT_CONFNAME fields -> the cfg
needs one <port> line PER bit with its own mask: bit0 (DSP) = mask "1" value "1", bit1
(TG sound) = mask "2" value "2". A single mask="3" value="2" line does NOT set bit1.

RESOLVED (commit f83a6a1): the "different sound" was a ring-MISALIGNMENT artifact, now
fixed. Root cause: without the modelled SPORT DMA advancing the autobuffer index, the
kernel writes its output frame to a FIXED position each IRQ0 (tapped: always 0xC350/
0xC351) and reads input 0x20 below (0xC370/0xC371) -- NOT a cycling ring. The tick
walked pos 0..7 so only 1/8 hit the real slot (~0.125 == the measured 0.126 attenuation)
-> the rest stale -> attenuation + clicks. FIX = fixed addresses TX0+0xE (out) / RX0+0xE
(in). Now spectrally VERIFIED CLEAN: DSP-on == DSP-off tone within 1% (RMS + fundamental
ratio 1.01), no added HF -- a faithful dry passthrough through the DSP. Bridge sync also
hardened (bounded rings, prime+hold-last, no bypass/DSP mixing). How to A/B compare:
capture off = CONFIG bit1 only, on = bit0+bit1, both press "Key C4" at t>=16, -wavwrite,
Goertzel at 262 Hz (see the /tmp analysis this session).

NEXT / open:
 - AUDIBLE EFFECT: the default slot (PM 0x8400) is a dry copy, so off==on. FINDING
   (tapped PM 0x8400-0x8420 writes over a boot+note): ZERO writes -- the firmware does
   NOT upload any effect microprogram by default, so the DSP runs the dry passthrough
   (correct, matches off==on). To hear reverb/chorus the firmware must be driven to
   SELECT an effect (host DspEffectSelect -> uploads rec05-76 to PM 0x8400). NEXT:
   figure out the trigger -- likely a panel/effect selection, and it may be gated by the
   SD-menu boot state (the TG gate lands on the SD menu, not the play screen, where
   effect selection normally happens). When an effect IS loaded, re-derive the +0xE
   output offset (it's the passthrough's I4 landing; a real effect may write elsewhere --
   tap the TX0 region write address as done this session).
 - SD-card menu still shows when the TG gate is opened (known: kn7000-sd-strap-gate) --
   separate issue, sound works regardless of screen.
 - Dry/wet mix + SPORT1 role: only if the output is 100% wet (hardware may sum a dry
   bypass). PM/DM 40-bit data path unmodelled (fine unless an effect enables it).

## ★★ DSP DRC ENABLED 2026-07-10 (Felipe: "port the ops to sharcdrc.cpp — yes let's do it!")

The SHARC now runs on MAME's recompiler, not the interpreter: DSP-on went from
~36-48% to ~72% real time — essentially the DSP-off speed (the machine is now
MN10300-interpreter-bound, the SHARC is near-free). Committed kn7000_mame 3fa7e3a,
published. Felipe also provided the ADSP-21065L Technical Reference PDF (in the repo
root) — used it to confirm the 21065L memory map (internal SRAM 0x8000-0x1FFFF,
external memory 0x20000+, IVT at 0x8000).

What the DRC needed (MAME's SHARC DRC was 2106x-only; sharcdrc.cpp + sharcfe.cpp now
overlaid too, symlinked by build.sh):
 - `m_dsp->enable_recompiler()` in the driver (the DRC is opt-in per driver).
 - Interrupt vectoring: hardcoded 0x20000 -> `irq_vector_base()` (0x8000).
 - Front-end loop map: `l2 == 1` assert -> device internal-memory base (so the
   kernel's DO..UNTIL loops compile).
 - Internal-SRAM fast path (m_blocks, unpopulated on the 21065L): keyed off new
   `drc_sram_base()`; 21065L returns out-of-range so all accesses go through the
   address map. THE SEGFAULT was the kernel clearing an external delay buffer at
   0x20000, which the 2106x path treated as internal SRAM -> null m_blocks store.
 - Mapped the 21065L's real memory: internal SRAM 0x8000-0x1FFFF + external SDRAM
   0x20000-0xFFFFF (delay lines; also needed for F.3 audio).
 - Fixed-point multiplier/MAC ops (single + multi function): the DRC stubbed them
   to abort; `generate_unimplemented_compute` now falls back to the interpreter's
   COMPUTE() for the one instruction (fast-ireg flush + astat pack/unpack around
   the C-call). Blocks compile instead of forcing whole-device interpretation.
 - `BIT TOGGLE ASTAT` (main-loop ping-pong flag): implemented (was abort).
Perf caveat is RESOLVED. Remaining SHARC-DRC follow-ups (not blocking): self-
modifying-PM invalidation is disabled for the 21065L (fine — effect programs are
host-uploaded, not SHARC-written; but effect-SWITCHING may need block invalidation
on the host PM write); PM/DM internal-SRAM aliasing not modelled (filter state read
via PM 0x9800 currently reads its own PM RAM, not the uploaded DM coefficients) --
matters for correct AUDIO (F.3), not for running.

## Cron-tick verification (2026-07-10, post-F.2)
Published binary re-verified: `kn7000-emulator/kn7000` is byte-identical (md5
e50d8ac2…) to the validated build-tree binary; a fresh default-config run boots
cleanly to the home screen (PMEM A-, no faults). Artifact healthy. NOTE: the cron
prompt's "awaits Felipe's greenlight / plateau" context is STALE — Felipe greenlit
the DSP LLE and F.1+F.2 are DONE (below). F.3 (SPORT audio) is next but has an
external dependency (the ADSP-21065L Hardware Reference is NOT in the repo — only
the 14-page EP datasheet) needed to pin the SPORT-DMA memory map, so it is NOT a
safe unattended start (guessing the map would risk wrong audio). Leave F.3 for a
focused session / Felipe's input on scope + the ~5% perf tradeoff. See the F.3 plan
+ open question in notes/sound-subsystem-plan.md.

## ★★ MILESTONE COMPLETE 2026-07-10 — DSP effects kernel BOOTS & RUNS (F.1 + F.2)

Felipe greenlit the DSP LLE ("go build it", "go ahead with F.2"). The recovered
ADSP-21065L (IC306) effects kernel now host-boots and runs to its IRQ0-driven main
loop inside MAME — no faults. Committed kn7000_mame `3aca274`, published.

- **F.1** (earlier): `adsp21065l_device` SHARC variant added (fork of MAME's 2106x
  core: sharc.h/.cpp overlaid, symlinked by build.sh; internal PM 0x8000-0x8fff,
  DM 0x8000-0xffff + IOP stub). KN7000 boots with it present (halted).
- **F.2 upload**: `dsp_data_w` decodes the host-boot stream — 8 blocks / 805 words
  (4 DM: 9800/9C40/C000/C302, 4 PM: 8000/8300/8400/8D00), framed reg-0x40 addr /
  reg-0x1C block cmd (0xA1 PM-commit, 0x41 DM-commit, 0xA0 end) / index-0x04 stream
  (48-bit PM = 3x16 LSW-first → wbuf[2]:[1]:[0]; 32-bit DM = 2x16 low-first).
  Uploaded words match the disasm EXACTLY (PM 0x8005/0x807a/0x8300). **RELEASE point
  = the final _bare_ 0xA0** (block-open flag: 0xA1/0x41 opens, 0xA0 closes; a 0xA0
  with no open block and words>0 is the "go"). The FIRST 0xA0 is a 0-word reset
  handshake — releasing there ran the DSP into garbage (the earlier bug).
- **F.2 SHARC-core fixes** (sharcops.hxx now also overlaid): `irq_vector_base()`
  virtual = 0x8000 for the 21065L (taken IRQ vectors to base+which*4; IRQ0=0x8020);
  `reset_pc()` = 0x8004 (MAME primes daddr=pc+1 and executes daddr first → first-exec
  0x8005 = JUMP init, skipping the boot-wait IDLE at 0x8004, which our glue has
  already satisfied). Implemented the missing fixed-point **multiplier/MAC ops** the
  kernel's biquad-seed routine uses: single-function MRF/MRB = Rx*Ry and MR ± Rx*Ry
  (signed/unsigned, integer/fractional, MR select, round); multi-function parallel
  MAC+ALU multiop 0x06, 0x08-0x16, 0x20-0x2f. (These were genuine gaps in MAME's
  SHARC interpreter — general, not 21065L-specific.)
- **F.2 driver tick**: `dsp_audio_tick` (emu_timer) pulses the SHARC's IRQ0 at a
  provisional **44.1 kHz** (`DSP_FRAME_HZ`) once the kernel is released. Only ASSERT
  is needed (the core auto-clears the pending bit when it TAKES the interrupt). This
  stands in for the SPORT/codec frame sync until F.3.
- **Validated**: with CONFIG bit0 "Effects DSP host stub" ON, the DSP reaches its
  main loop — distinct PCs 0x8021 (IRQ0 ISR: R13=1 "frame arrived"), 0x807b/0x80f8
  (mainloop), no faults over 12 s. Default boot (stub OFF, DSP halted) still reaches
  the home screen unchanged (screenshot verified).
- **Perf caveat**: the SHARC runs on MAME's INTERPRETER at ~5% realtime with the
  44.1 kHz tick. So the stub stays **opt-in / default OFF**. Speeding it up (SHARC
  DRC — needs my mult ops + vector-base/reset_pc ported to sharcdrc.cpp; and/or a
  lower real IRQ0 rate once the SPORT block size is known) is a follow-up.

### NEXT — F.3 SPORT audio (make the effect actually process the audio stream)
Model the SHARC's serial ports (SPORT) so audio flows TG output → DSP → DAC, and
replace the synthetic 44.1 kHz IRQ0 tick with the real SPORT/codec frame sync that
paces the kernel. Kernel refs: init 0x8D00 sets up SPORTs/SDRAM/DMA; IRQ0 ISR 0x8020
sets R13=1; mainloop 0x807a consumes a frame. See notes/sound-subsystem-plan.md (F.3)
and the DSP disasm (kn7000_disassembly/disasm/dsp/rec04_kernel_*.asm).

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
6. Cross-model sound RE: INVESTIGATED, KN6000 audio DEFERRED (2 cron ticks 2026-07-10).
   KN6000 DOES drive its TGs live on key-bed notes (no strap gate; boots to play screen,
   no SD block). BUT its pitch is NOT extractable by register-diffing: class 0x5800 is a
   fine/detune field (clusters, non-monotonic), and the pitch-varying info is in the
   group-0x00 voice-param registers (0x0000/0x0004 move ~6-9/semitone, not clean) — a
   separate channel space + multisample. Cracking it needs STATIC RE of the KN6000
   note→pitch routine (unidasm on kn6000_program; analog of KN7000's 0x4844812D) or the
   undumped IC13/IC14 table + wave ROMs. Do NOT enable kn6000/kn6500 sound with a
   wrong-pitch guess. Full notes: sound-cross-model-kn6000-kn6500.md. KN5000/KN2400
   still unchecked.

DONE (cron tick 2026-07-10 #3): honor the firmware's per-voice LEVEL (class 0x2009) in
the synth (normalized so the default 0x5FFF = unity → current sound unchanged, verified;
softer/louder levels now flow through). Groundwork for velocity/voice-balance.

### PLATEAU NOTE — the KN7000 sound is in a strong, complete state; remaining work is
### either large multi-session or blocked. Honest triage:
- **Envelope RATES (attack/decay/sustain): BLOCKED.** The KN5000 doc confirms the
  hardware EG rate→time law is UNDOCUMENTED (its own emulation punts to a linear fade).
  Decoding it needs hardware observation or deep RE we can't do from the register values
  alone. Current exponential decay is a reasonable honest placeholder. Do not guess rates.
- **KN6000/KN6500 audio: DEFERRED** — pitch needs static RE of its note→pitch routine
  (see sound-cross-model-kn6000-kn6500.md). KN5000/KN2400/KN2600 unchecked.
- **SD subsystem: USER-PAUSED** (memory kn7000-sd-strap-gate). Fixing it would let KN7000
  boot to the home screen WITH sound (removing the opt-in switch) and unblock sound-
  selection — but respect the pause; do not sink ticks into it autonomously.
- **Real timbre: ROM-BLOCKED** — the 4 PCM wave ROMs are undumped.

## ★★★ EFFECTS-DSP LLE GREENLIT BY FELIPE (2026-07-10) — BUILDING IT (Phase F)

Felipe said "greenlight the DSP LLE — go build it." Phased build; verify build+boot at each
step; never break the working KN7000. Key facts (all validated, see sharc-lle-assessment.md):
MAME has the 2106x SHARC core (ADSP21062/21060); 21065L internal map PM 0x8000-0x8Dxx / DM
0x9800-0x9Cxx + 0xC000-0xC3xx / SDRAM 0x80000+; IOP stub set 0x08-0x0F,0x28-0x3C,0x53-0x7B,
0xE0-0xFC; host-upload protocol reg0x40=addr, 0x1C=0xA1 PM/0x41 DM (validated live, 258 blocks);
ext-port DMA ch 8/9. CRITICAL CORE FINDING: adsp21062_device::m_blocks is PRIVATE and pm_r/pm_w
use a block-interleave scheme hardcoded to the 21062 geometry -> the 21065L variant CANNOT live
in kn7000.cpp; it needs the SHARC core FORKED into the repo (MN10300 precedent:
kn7000_mame/src/devices/cpu/<core>/ symlinked into kn7000_mame_build/src/...).

PROGRESS:
- F.1-STEP-0 ✅ DONE + committed (kn7000.cpp) + PUBLISHED: instantiated ADSP21062 in kn7000()
  (host-boot mode, idle). KN7000 boots to the home screen, no fatalerror, SHARC compiled+linked.
  BUILD LEARNINGS (important, in build.sh now / cpu.lua):
    * Adding the SHARC needs REGENIE=1 + USE_QTDEBUG=0 (REGENIE else fails on Qt 'moc').
    * LATENT MAME BUG fixed: cpu.lua DRC_CPUS names the SHARC "ADSP21062" but its flag is
      "ADSP2106X" -> SHARC-only builds fail to link drcuml. build.sh now idempotently adds
      "ADSP2106X" to DRC_CPUS.
    * Canonical build = kn7000_mame/build.sh (SOURCES=kn7000.cpp,kn1500.cpp; registers both in
      mame.lst). After REGENIE churn, a STALE libmame_kn7000.a (only kn7000.o, missing kn1500.o)
      caused 'undefined driver_kn1500' -> fix = delete build/.../bin/.../mame_kn7000/libmame_kn7000.a
      + generated .../drivlist.o, rebuild WITHOUT REGENIE. So: REGENIE once to add a device, then
      rm the stale mame archive, then plain make.
- F.1-STEP-1 ✅ DONE + committed + PUBLISHED: forked sharc.h/.cpp into the overlay
  (kn7000_mame/src/devices/cpu/sharc/, symlinked by build.sh). Added **adsp21065l_device**:
  plain-RAM 21065L maps (PM map(0x8000,0x8fff).ram(); DM map(0x8000,0xffff).ram() covering
  0x9800/0xC000; IOP 0x00-0xFF -> iop65l_r/w stubs returning 0/accepting). Changed m_blocks
  required_->optional_shared_ptr_array. Driver now instantiates ADSP21065L (host-boot, idle).
  VERIFIED: KN7000 boots to home screen, no fatalerror. **F.1 IS COMPLETE — the SHARC variant
  exists in MAME and integrates.** (No REGENIE needed for STEP-1 — new device type in an
  existing source file; just symlink + plain make.)

  === F.2 (NEXT) — driver host-boot glue: actually load + run the DSP program ===
  The firmware host-boots via 0x98000000(index)/0x9C000000(data): reg 0x40=target addr,
  reg 0x1C=0xA1(PM commit)/0x41(DM commit)/0xA0(end), then streams words (3x16 per 48-bit PM
  word via fw 0x484050B8; 2x16 per DM word via 0x4840511A). PLAN for kn7000.cpp dsp_data_w /
  io_w (extend the existing Phase-A stub):
    1. Track the DSP index writes: reg 0x40 -> latch m_dsp_dl_addr (2x16); reg 0x1C -> m_dsp_dl_mode
       (0xA1 PM / 0x41 DM / 0xA0 end).
    2. On data-port writes while mode=PM: accumulate 3x16 -> one 48-bit word -> write to the SHARC
       PM at m_dsp_dl_addr via m_dsp->space(AS_PROGRAM).write_qword(addr<<?,word) [addr in words;
       program space is -3 granularity -> check the byte/word addressing]; addr++. Mode=DM:
       accumulate 2x16 -> 32-bit -> m_dsp->space(AS_DATA).write_dword; addr++.
    3. On reg 0x1C=0xA0 (end/sync): the kernel record is fully loaded -> RELEASE the SHARC from
       host-boot so it runs. Check how BOOT_MODE_HOST releases (model2.cpp copro_boot clears
       INPUT_LINE_HALT; sharc.cpp device_reset host path). May need set_input_line(INPUT_LINE_HALT,
       CLEAR) or the sharc host-boot-done path. Kernel entry = reset vector (SDRAM POST first).
    4. VERIFY: tap the SHARC PC (m_dsp->state) advancing through 0x8xxx; no iop fatalerror (the
       iop65l stubs handle it); ideally the SDRAM POST reg 0x0B readback. Gate all this behind the
       existing CONFIG bit0 "Effects DSP host stub" switch (default OFF) so it's opt-in until F.3.
  CAUTION: the driver's 0x9C bank currently maps dsp_data_r/w only for 0x9c000000-3 (the rest is
  lcdbuf RAM). The program-space write granularity (-3) means PM addresses may be byte vs word --
  verify with a small test (write one known word, read it back via m_dsp->space).
  === F.3 (after F.2) — SPORT audio: TG output -> DSP -> DAC (the big new piece) ===
- F.1-STEP-1: fork sharc.h+sharc.cpp into the repo, add adsp21065l_device (21065L PM/DM maps +
  IOP stubs), swap m_dsp to it.
- F.2: driver host-boot glue (latch reg0x40 addr; on 0x1C 0xA1/0x41 DMA the streamed words into
  the SHARC internal PM/DM; release it). Verify the kernel runs (PC advances, no fatalerror).
- F.3: SPORT audio (TG output -> DSP -> DAC). The big new piece.

### DECISION POINT FOR FELIPE (reached 2026-07-10, cron tick #5) [SUPERSEDED — greenlit above]
The sound subsystem is at a strong, complete plateau: the KN7000 makes firmware-driven,
correctly-pitched sound (opt-in switch; home-screen boot preserved), fully documented
(website + blog Part 10). The ONE remaining big piece — the effects-DSP LLE — is now
FULLY SPEC'd and ready to build (memory map + IOP set derived; MAME SHARC core confirmed),
but it is a LARGE, shared-MAME-core effort (new adsp21065l device variant + SPORT audio
from scratch) whose payoff is a reverb/chorus on the placeholder sine until the wave ROMs
are dumped. Autonomous cron ticks have (correctly) NOT undertaken that shared-core surgery
unattended — the risk of leaving the build broken overnight outweighs it, and it deserves
Felipe's explicit go-ahead. **When Felipe returns: decide whether to commit to the DSP LLE
(F.1-F.3).** Everything is ready so it can start fast (see notes/sharc-lle-assessment.md §5
+ IOP set).

Safe SMALL items a cron tick CAN do autonomously without that decision (pick one if
resuming): ~~validate the host-upload path~~ DONE (tick #6 — runtime upload cross-validates
the §5 memory map + the F.2 protocol; see sharc-lle-assessment.md + tools/dsp_upload_capture.lua);
~~cross-model KN5000 sound check~~ DONE (tick #7 — §6 of sound-cross-model-kn5000.md resolves
the KN5000 hypotheses against the working KN7000; cross-model sound docs KN5000/6000/6500 now
complete); minor doc/website polish; re-verify the published binary.
Avoid: risky shared-core changes, the user-paused SD subsystem, wrong-pitch guesses.

DONE (tick #9, 2h cron): FINAL QA of the PUBLISHED deliverable (kn7000-emulator/, run as
Felipe will). Default boot = home screen, gate 0x7F silent (no regression); switch ON (CONFIG
bit1) = correct-pitch sound C4/G4/C5 = 262/392/523 Hz, no clipping. Confirmed the publish
packaging (binary+roms+run.sh) works end-to-end; no leftover cfg (default stays OFF). Nothing
else to do this tick — plateau holds.

CRON CADENCE (tick #8): slowed the autonomous cron from every-20-min to **every 2 hours**
(job c0d0df57) during the plateau — the safe-small-item menu is nearly exhausted and the big
item awaits Felipe. The 2h prompt says: do at most ONE genuinely-useful safe item per tick, or
nothing. Felipe can ask for a faster cadence anytime; his return is a normal message that
resumes work immediately regardless of cron timing.

DONE (tick #8): brought the persistent memory current — the kn7000-sound-subsystem memory
still said "awaiting Felipe's review / run the TG diagnostic" (badly outdated) and cited the
wrong pitch class (0x3000); corrected to "KN7000 sings, pitch=0x2401, DSP LLE awaits greenlight",
and fixed the MEMORY.md index lines. (Memory persists via the filesystem; no git needed.)

NOTE (tick #7): the safe-small-item menu is nearly exhausted and the sound subsystem is at a
strong, complete, well-documented plateau. The remaining substantial work (effects-DSP LLE)
needs Felipe's greenlight on the shared-core effort. Future autonomous ticks: prefer
re-verifying the published binary / minor polish over inventing marginal work; do NOT start
the shared-core SHARC build unattended. The KN7000-sings milestone + all RE/validation is
committed and published; everything is ready for Felipe's DSP decision.

### NEXT MAJOR EFFORT (pending greenlight) = the EFFECTS DSP (Phase F, LLE) — in the cron goal.
Feasibility CONFIRMED this tick: MAME has a 2106x SHARC core (ADSP21062/21060, same ISA as
the 21065L); the 80 DSP programs are recovered+disassembled. Full analysis in
notes/sharc-lle-assessment.md. It is a LARGE multi-session build (the 21065L I/O
personality + SPORT audio have no MAME precedent), so tackle it in phases across ticks:
  F.1 — add an `adsp21065l_device` subclass in src/devices/cpu/sharc/ (adsp21060 pattern):
        21065L internal PM/DM maps, IOP regs as LOGGED stubs (replace the fatalerror
        defaults at sharc.cpp:367/443). Wire it into the kn7000 SUBTARGET build; verify it
        BUILDS and the KN7000 still boots (device present, unused). SAFE, additive.
        >>> PREREQUISITES DONE (cron tick 2026-07-10 #4), both derived from the recovered
        program (no full datasheet needed) — see notes/sharc-lle-assessment.md §5 + IOP set:
        - Internal memory map: PM (48-bit) 0x8000-0x8Dxx (effects @0x8400); DM 0x9800-0x9Cxx
          + 0xC000-0xC3xx; IOP 0x00-0xFF; external SDRAM (plain .ram) at 0x80000+.
        - IOP stub set (offsets the program touches; base core fatalerrors on the NEW ones):
          handled: 0x02,0x08-0x0F(host mailbox, heavy),0x20; NEW stubs: 0x28-0x3C, 0x53-0x7B,
          0xE0-0xFC; system IMASK/IRPTL modeled by core. Ext-port DMA = ch 8/9 (not 6/7).
        So the SUBCLASS CAN BE WRITTEN DIRECTLY next tick. NOTE the caveat recorded in the
        assessment (F.3 SPORT audio is large; DSP processes the placeholder sine until wave
        ROMs are dumped) — a good point for Felipe to confirm committing the effort; but F.1
        itself is safe/additive and proves the recovered DSP programs run on MAME's SHARC.
  F.2 — driver boot glue: host-upload the recovered DSP program via the 0x98000000(index)/
        0x9C000000(data) port (model2.cpp copro_ctl1_w/external_dma_write pattern). Verify
        the SHARC loads the kernel record and runs (PC advances, no fatalerror).
  F.3 — SPORT audio: stream TG output → DSP → DAC through the (new) serial-port model.
        Verify the effect processes audio. This is the genuinely new, biggest piece.
Each phase is one-or-more ticks; commit + verify build/boot at each step; never break the
working KN7000 driver. If a tick can't safely complete a phase, do a bounded sub-step and
record where it stands.

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
