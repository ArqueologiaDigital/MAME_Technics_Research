# Plan: emulating the Technics keyboards' DSP chips properly in MAME (2026-10-21)

Felipe asked for a plan he can choose the next steps from. This is planning only: no emulator code was changed. The
KN7000's effects DSP (IC306, ADSP-21065L) gets most of the space; the other machines' DSPs are covered in
section 1.3 and step S21.

Everything below cites its evidence. Four kinds are used:

- **unit**: a pass on Felipe's KN7000 (cnv_romdump passes 6-8, DSPTONE iteration 1, Another World's DSP mode);
- **run**: a MAME run, with its script and result committed;
- **code**: reading the overlay, the firmware's DSP programs or the ADSP-21065L User's Manual
  (`~/compartilhado/KN7000/ADSP-21065L_SHARC_DSP_Users_Manual.pdf`, "UM" below);
- **notes**: an earlier note, cited as written and not re-checked here.

Two light checks were run for this plan, on the published emulator (md5 `3077b137`, overlay `a9e822a`):
`notes/dsp-plan-2026-10-21/` (commit `a26eb15`; scripts, runner and results). They confirm G3 by a run and show
which machines' SHARC kernels run at all.

Short names: **K** = `technics-roms-disasm/kn7000/dsp/kernel-architecture.md`; **probe** =
`notes/dsp-probe-2026-10-20/README.md`; **DT** = `technics-roms-disasm/kn7000/tools/dsptone/README.md`;
**AW** = `technics-anotherworld/kn7000/README-CNV.md` (cited by section, because the file is being edited);
`kn7000.cpp`, `kn5000.cpp`, `kn7000_tonegen.cpp` and the other driver files are in `src/mame/matsushita/`, and
`sharc.cpp` is `src/devices/cpu/sharc/sharc.cpp`, all in this repo at `a26eb15`.

## 0. The plan on one page

**Where we are.** The KN7000's SHARC runs the firmware's real effect programs, and the unit has confirmed that the
downloaded code, the set-up registers, the 44.1 kHz frame rate, the per-frame handshake and FLAG3 all match (passes
6-8). Two programs of our own (DSPTONE, Another World's mixer) run on both the unit and MAME. What is not faithful
is everything between the SHARC and the DAC: the serial ports carry no data (the driver reads and writes fixed ring
words once a frame), and a hand-tuned "bridge" mixes the returns with constants. Two audible errors follow from it.
With REVERB on, MAME probably plays the reverb's wet output instead of the dry sound plus the wet (D2). And it mixes
the CHORUS unit's return only while CHORUS is on, where the unit evidently mixes it with REVERB off too (D1). Also
wrong: save states stop the effects (G3, measured today), and the DRC and the interpreter give different audio (22%
of samples; 2026-10-21: the interpreter takes IRQ0 late and drops three frames in four, the DRC is right, D11). The
clock, 66 MHz instead of 60 (G5), was set to 60 on 2026-10-21 (S3). The "noise" Felipe hears is the emulation running
below real time, not the DSP's output (D12, `notes/dsp-noise-2026-10-21/`).

**Top five next steps.**
1. S1-S3: fix the save state, add the bypass switch, set 60 MHz. Each is small, and each has a ready check.
2. S4-S5: keep the dry sound with REVERB on, and always sum unit 9's return. These are the two audible errors, and
   each is a small change in the bridge.
3. S8: move the audio through the SPORT DMA chains word by word, taking branch B's engine.
4. S9: let the tone generator own the effect sends and returns (its group-0x20 matrix), replacing the bridge's
   constants.
5. S11-S14: the memory map, the status registers, the timers and the arithmetic, each checked against the unit
   with a DSP-side probe.

**Top three experiments on the unit.**
1. E2: record a C4 with REVERB off and on (by MIDI file, no code). This settles D2.
2. E1, RETMAP: a menu app that puts a different tone on every DSP transmit slot. Four short recordings settle which
   returns reach the DAC in which panel states, and at what level.
3. E3, DSPCLK: a DSP program that reads the 21065L's timer every frame. It gives the core clock (G5) and the real
   cycle cost of each effect unit.

**Decisions for Felipe** (section 7): the bypass switch's default, adopting 60 MHz now, which side (overlay or
branch B) is the reference for the SHARC core, whether the core fixes go upstream ahead of the tone-generator PR, and
approval of the new unit apps.

## 1. Where we are

### 1.1 Which DSPs each machine has

| machine        | DSP                                                                          | role                                                               | overlay today                                                                                                                    | evidence                                                                           |
|----------------|------------------------------------------------------------------------------|--------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------|
| KN7000         | IC306 ADSP-21065L (S21065LKS240), 2x16 Mbit SDRAM IC307/IC308                | effects (10 units), host-booted by the MN10300                     | runs the firmware's kernel; SPORT data and mixing approximated                                                                   | unit passes 6-8; run (`dsp_alive.lua`: 88,200 IOSTAT writes/s)                     |
| KN6000, KN6500 | IC304 ADSP-21065L, SDRAM IC305/IC306                                         | the same; same DM blocks, older PM build                           | inherited from the KN7000; the kernel runs at the fixed 44.1 kHz tick                                                            | run (`dsp_alive.lua`); `notes/sound-cross-model-kn6000-kn6500.md:29-73`            |
| KN2400, KN2600 | not identified                                                               | -                                                                  | inherits the KN7000's SHARC, which is never released (PC `0x8004`, no frame at 30 s)                                             | run (`dsp_alive.lua`); no µPD6383 stream in its ROM (corpus scan)                  |
| KN5000         | IC311 NEC µPD6383GF "DSP1" (25 MHz), IC310 Panasonic MN19413 "DSP2" (20 MHz) | DSP1: send/return effects; DSP2: master reverbs, GEQ, the mic path | DSP1: partial core, compiled out (`KN5000_ENABLE_DSP1 0`), ISA 78.9% decoded; DSPHLE (34 hand-written effects) off; DSP2 missing | `kn5000.cpp:21-44`, `:742-755`, `:883-955`; `kn5000-docs/upd6383-decode-status.md` |
| KN1500         | IC3 µPD6383GF                                                                | effects                                                            | missing (machine does not boot: IC15 BAD_DUMP)                                                                                   | `kn1500.cpp:46-49`, `:66-96`                                                       |
| SX-WSA1/WSA1R  | IC5, IC6, IC30 µPD6383GF                                                     | effects                                                            | three cores fed by the upload, compiled out (`WSA1R_ENABLE_DSP 0`); no audio routing                                             | `wsa1.cpp:335-345`, `:1934-2010`                                                   |

The "DSP bytecode interpreter" is the KN5000 sub-CPU's two-level interpreter that feeds IC311
(`kn5000-docs/dsp-bytecode-interpreter.md`); it is firmware, not a chip. The only custom Panasonic DSP is the
KN5000's MN19413. Upstream MAME emulates none of these DSPs: its `kn7000.cpp` says "the ADSP-21065L effects DSP is
not emulated" and routes the tone generator straight to the speaker; its SHARC core has no 21065L type; the
µPD6383 exists there only as inert skeletons in `wsa1.cpp`.

### 1.2 KN7000 IC306, subsystem by subsystem

States: **emulated** (matches every unit observation we have), **partial**, **wrong** (contradicts the unit or the
manual), **missing**.

| subsystem                              | state          | what the overlay does                                                                                                                                    | evidence                                                                                                                                                                                       |
|----------------------------------------|----------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| instruction coverage                   | emulated       | all 69 instruction classes the 80 records use run in the interpreter and natively in the DRC; RND MRx unimplemented (unused)                             | code: `technics-roms-disasm/kn7000/dsp/instruction-coverage.md:7-41`; unit: DSPTONE and AW's mixer ran on the chip and in MAME (DT, AW)                                                        |
| arithmetic exactness                   | partial        | deviations C.2-C.5 from the manual (only C.3, AVG rounding, is exposed: 19 output mixes, -0.25 LSB); MR is 64-bit, not 80; no 40-bit float               | code: `notes/sharc-upstream-patch-series.md` C; `instruction-coverage.md:136-146`. Never compared with the chip instruction by instruction                                                     |
| branch B core fixes                    | missing        | multiplier MN/MV/MU flags, the dual add/subtract's AN/AZ after saturation, DRC scratch registers I8/I9, ALUSAT read at run time                          | notes: OVERLAY-GAPS G4; branch `technics-kn7000-dsp` `586094eb3db`, `38f4bca2b3a`                                                                                                              |
| DRC against the interpreter            | emulated (DRC) | the DRC finishes all 44,100 frames a second; the interpreter takes IRQ0 late and drops three frames in four (D11), hence the 22.0% of samples            | run (2026-10-21): `notes/dsp-noise-2026-10-21/` (`frames_tap.lua`); run (2026-09-23): `notes/sharc-drc-parity/README.md`                                                                       |
| timing, cycle accuracy                 | missing        | one cycle per instruction; no SDRAM latency, no PM-bus conflicts or cache, no DMA cycle stealing                                                         | code: core. Matters only when a frame overruns: the budget is about 1,360 cycles at 60 MHz and 60/66 MHz give identical audio (`notes/dsp-frame-budget/README.md`)                             |
| clock                                  | emulated       | 60 MHz since S3 (2026-10-21); was 66                                                                                                                     | 60 MHz part grade; X301 ≈ 30 MHz by part number (`notes/sound-hw-architecture.md:89`); SDRDIV (below)                                                                                          |
| internal memory map                    | partial        | PM 0x8000-0x8FFF and DM 0x8000-0x8FFF are separate RAMs; 0x9000-0x1FFFF is one flat 32-bit RAM shared by PM and DM; 0x4000-0x7FFF unmapped               | code: `sharc.cpp:164-186`; UM Table 5-2 (below); `notes/dsp-frame-budget/README.md:92-147`                                                                                                     |
| external SDRAM                         | partial        | plain RAM at DM 0x20000-0xFFFFF, no wait states                                                                                                          | code: `sharc.cpp:183-186`. Two 1M x 16 parts make 1M x 32 words: 0x20000-0x11FFFF. The firmware uses up to 0x69D3F (K:259-306), AW up to 0x99E37                                               |
| host boot, download                    | emulated       | the index/data port, the IOP register file, PM and DM blocks written straight into memory, the "go"                                                      | unit: pass 7, every downloaded word identical (probe, "The DSP's memory"); the transfer itself does not go through EPB0 and DMA channel 8 (DT, "The host DMA")                                 |
| host readback (EPB0, channel 8)        | emulated       | DMAC0 DEN+TRAN arms channel 8; host reads return internal memory 16 bits at a time; FS shows EPB0 full                                                   | unit and run: pass 7 in MAME and on the unit (probe, "What the emulator now does")                                                                                                             |
| IOP registers, host side               | partial        | a register file; reads return what was written, SYSCON packed per HBW                                                                                    | unit: pass 6 (probe, "What the chip said"): SYSTAT `0x13`, IOSTAT `0x80000000`, STCTL0 TUVF_A, IOCTL bits 31/15 reading 0 are not modelled; MSGR3 is a boot stand-in `0x1065` (chip `0`)       |
| IOP registers, DSP side                | partial        | MSGR0-7 read back (`e04a567`), SPORT DMA registers read live (`b269162`); every other register reads 0 to the kernel                                     | unit: pass 7 found the MSGR2 bug; code: `sharc.cpp:226-231`                                                                                                                                    |
| SPORT DMA registers                    | emulated       | DMASTAT, each channel's II and C move through the frame with the unit's phase                                                                            | unit and run: pass 6 and pass 8 in MAME match the unit (DMASTAT `0x33F`, IIR0A `0xC365`, CR0A 5)                                                                                               |
| SPORT TX/RX data, DMA chaining         | missing        | no word moves through a TCB; `dsp_audio_tick` reads unit returns from fixed ring words and writes the sends into fixed ring words once a frame           | code: `kn7000.cpp:1451-1543`; branch B has an 8-channel engine with per-slot callbacks (`e0c4a27c956`)                                                                                         |
| IRQ0, the frame                        | emulated       | a 44,100 Hz timer asserts IRQ0                                                                                                                           | unit: pass 8, 44,087 Hz by the firmware's tick (44,065 Hz if TM4 is exactly 2 MHz); DSPTONE heartbeat 44,087/s. What drives IRQ0 physically is unknown (the TG is the clock master, K:126-137) |
| timers                                 | missing        | TCOUNT holds what was written                                                                                                                            | unit: pass 6, TPERIOD0/1 = 0 (the kernel does not use them); needed only for DSP-side probes (E3) and homebrew                                                                                 |
| the group-0x17 handshake               | partial        | raised on the frame tick, once per frame, whatever the SHARC does; immediate during host boot                                                            | unit: pass 8, one per 22.682 us on a 0.28 us lattice; MAME 22.664 us, 0.20 us (`5dd2c40`). On the unit it presumably needs a running DSP (DT "Risks", not measured)                            |
| FLAG pins                              | partial        | FLAG3 input alternates every frame; FLAG0/1 and FLAG4-11 outputs go nowhere                                                                              | unit: pass 8, I3 steps on 0.5000 of the frames (`5dd2c40`); code: IOCTL `0x8852A05B` makes FLAG4, 5, 7, 8 and 10 outputs; their sinks (nets DSP.FLAGB, DSP.FLAGE) are unknown                  |
| mixing the unit returns into the DAC   | wrong          | the bridge (`kn7000.cpp:164-339`): REVERB's crossfade applied to the whole output, returns scaled by constants (0.60 makeup), sends are the whole TG mix | code: `kn7000_tonegen.cpp:225-249` ("routing applied globally"); see D2, D10                                                                                                                   |
| the REVERB/CHORUS return dependency    | wrong          | unit 9's return is read and mixed only while the chorus send is non-zero or the CHORUS LED is lit (`kn7000.cpp:1486-1512`)                               | unit: Another World's DSP mode is heard with REVERB off (AW, "The DSP mode", technics-anotherworld `9b1bc09`, 2026-10-21); see D1                                                              |
| units 7 (mic reverb) and 8 (EQ insert) | missing        | their inputs are never fed and their returns never read                                                                                                  | code: `kn7000.cpp:1451-1543`; notes: `dsp-unit-roles-live-capture.md`                                                                                                                          |
| save state                             | wrong          | only part of the host-boot state is saved; after a load in a new session `m_dsp_running` is false and IRQ0 never comes                                   | run: `notes/dsp-plan-2026-10-21/` (DM 0xC003: 10 distinct values in 10 before the save, 1 in 10 after the load)                                                                                |
| bypass switch (G19)                    | missing        | none; the "Effects DSP audio path" switch was removed in `2cdef9d`                                                                                       | code; OVERLAY-GAPS G19                                                                                                                                                                         |

**The memory map against the manual** (UM Table 5-2). Block 0 is 0x8000-0x9FFF and block 1 0xC000-0xDFFF in
normal words, where 48-bit instructions and 32-bit data share the same cells (the firmware's layout is the manual's
configuration B: code 0x8000-0x8FFF, data 0x9800-0x9FFF). The 16-bit short-word views are 0x10000-0x13FFF and
0x18000-0x1BFFF, and everything else below 0x20000 is reserved. The kernel touches 1,642 addresses in
0x10000-0x1FFFF, which the overlay treats as independent 32-bit words. It also hammers 0x4000-0x7FFF, 99.6% of it at
half a mapped address; mapping that changed nothing in the audio (`dsp-frame-budget`). On the chip a short-word
access reads or writes 16 bits of a block's normal word, so if any effect uses short words, the overlay gives it
more precision and no aliasing. S10a and E4 settle this.

**How SDRDIV pins the clock** (code, UM p.10-14 and Table 10-2). The manual's equation is
`SDRDIV = 2 x fCLKIN / (refresh rate) - CL - tRP - 4`, and its worked example (CLKIN 30 MHz, 4096 rows in 64 ms,
CL 2, tRP 2) gives 930. The kernel writes SDRDIV `0x3A2` = 930 and IOCTL `0x8852A05B`. That IOCTL decodes as CL 2
(bits 17:16 = 10), tRP 2 (bits 23:21 = 010), tRAS 4, 256-word pages, two banks, SDRAM on bank 0 (the KM416S1120D's
geometry), with bits 31 (SDPSS) and 15 (SDSRF) set. The manual says both of those always read 0, which is exactly
what pass 6 saw. So 2 x CLKIN = 60.0 MHz, unless the designers copied the example's number without doing the
arithmetic. E3 measures it directly.

### 1.3 The other machines

- **KN6000, KN6500.** These are the same chip and protocol, and their pools' DM blocks are byte-identical to the
  KN7000's, but the PM is an older build (K:434-439). The kernel runs in the overlay (`dsp_alive.lua`). The KN7000's
  unit map and the bridge's slot addresses are applied unchanged. Nobody has re-derived the unit walk from the
  KN6xxx PM, and the KN6000 tone generator's send matrix is not decoded (`kn6000_tonegen.cpp:168-175`). The KN6500
  is flagged NO_SOUND although it plays (G15). No unit is available, so MAME runs are the only evidence.
- **KN2400, KN2600.** The DSP is not identified. The inherited SHARC sits in reset for the whole session, which costs
  nothing but misleads anyone reading the machine config. Both are NO_SOUND.
- **KN5000.** This is a separate track with its own roadmap (`notes/dsp-next-steps-roadmap.md`, K1-K7, R1-R4). It
  needs the µPD6383 ISA decoded before the core can produce audio, and IC310 (MN19413) is not started. The overlay's
  hand-written DSPHLE effects are the only audible path, and they are off by default. Small known bugs: the 8-bit
  latch at 0x130000 and the half-applied store-gate fix (G17).
- **SX-WSA1/WSA1R.** The three µPD6383 cores are compiled out, and nothing routes their audio. One code-reading
  doubt, not run: the cores are not `set_disable()`d, so turning `WSA1R_ENABLE_DSP` on would let them execute.
  `HARDWARE-CUSTOM-DSP-PROGRAMS-WSA1R.md` plans custom microcode on Felipe's WSA1R.
- **KN1500.** Nothing exists, and the machine does not boot.

The rest of this plan is about the 21065L. Its results carry to the KN6000/KN6500 at no extra cost, provided S20
re-derives their unit map. For the µPD6383 machines the right next step is the existing decode roadmap, not an
emulation change.

### 1.4 The unit's ground truth we already have

| source                 | what it established                                                                                                                                                                    | where                                                    |
|------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------|
| pass 6 (DSPPROBE)      | the IOP set-up equals the emulator's; chip-only status bits; ring phase at the handshake (RX base+3 count 5, TX base+5 count 3)                                                        | probe, "What the chip said"; private files `pass6-run1/` |
| pass 7 (DSPMEM)        | every downloaded PM and DM word equals MAME's; the MSGR2 read-back bug                                                                                                                 | probe, "The DSP's memory"; `compare_dspmem.py`           |
| pass 8 (DSPRATE)       | one handshake per frame, 44.1 kHz nominal (44,087 by the tick), FLAG3 high on alternate frames, one ring position at every read                                                        | probe, "The unit's timing"; `check_dsp_probe.py`         |
| DSPTONE iteration 1    | our own unit-0 program loads, runs and is removed through the firmware's routines; heartbeat 44,087/s; unit 0's return is heard with REVERB on; SDRAM from 0x70000 works               | DT, "On the instrument"                                  |
| Another World DSP mode | an 8-voice mixer in units 0 and 9 plays "perfectly" with REVERB on and with REVERB off (on a little louder), at about a piano note's level; reverb and chorus come back after quitting | AW, "The DSP mode"                                       |

## 2. Known discrepancies between MAME and the unit

| #   | discrepancy                                                                                                                                                                                                                                                                                                                                                                                  | evidence                                                                                                                                                   | what fixing it takes                                                                                                         | step                      |
|-----|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|---------------------------|
| D1  | MAME mixes unit 9's (CHORUS) return only while CHORUS is on; on the unit AW's mix (written to units 0 and 9) is heard with REVERB off, and with REVERB and CHORUS both off (Felipe, 2026-10-21), so through unit 9, whatever the panel says                                                                                                                                                  | unit: AW, "The DSP mode"; code: `kn7000.cpp:1486-1512`; `effect-return-routing.md`                                                                         | always read and mix unit 9's TX pair; its level is fixed until E1 measures it                                                | S5, S6                    |
| D2  | with REVERB on, MAME's output is unit 0's return only, and the reverb programs write only wet: the dry sound is probably missing. Measured 2026-10-21: a held C4 is 7.2 dB under the same note dry (predicted 7.6), with no broadband noise                                                                                                                                                  | code: `kn7000_tonegen.cpp:225-249`; `reverb-algorithm.md` 2.5; notes: on is 2.4x quieter (`reverb-toggle-findings.md`); run: `notes/dsp-noise-2026-10-21/` | apply the pair to the reverb-return part only and keep the dry path; confirm with E2                                         | S4                        |
| D3  | the frame rate is 44,100.0 Hz in MAME, 44,087 (by the tick) or 44,065 (by TM4) on the unit                                                                                                                                                                                                                                                                                                   | unit: pass 8; DSPTONE heartbeat                                                                                                                            | none: two crystals, 0.03-0.08%; keep 44,100 (decision O8)                                                                    | -                         |
| D4  | status bits the chip shows and MAME does not: SYSTAT `0x13`, IOSTAT `0x80000000`, STCTL0 TUVF_A, IOCTL bits 31/15 read 0, MSGR3 `0` (MAME `0x1065`)                                                                                                                                                                                                                                          | unit: pass 6                                                                                                                                               | model them from the manual (IOCTL's two bits are documented as always reading 0); keep the boot probe's MSGR3 answer working | S12                       |
| D5  | the handshake comes from a timer in MAME; on the unit it presumably comes from the DSP (DT's reading, not measured), so a stalled DSP would set the dead flag                                                                                                                                                                                                                                | unit: DT "Risks"; code: `kn7000.cpp:1427-1439`                                                                                                             | raise group 0x17 from the DSP's own signal once E6 names it (FLAG4 is the candidate)                                         | S16                       |
| D6  | the clock was 66 MHz, against a 60 MHz part. Fixed by S3 (60 MHz, 2026-10-21)                                                                                                                                                                                                                                                                                                                | code (1.2)                                                                                                                                                 | done; E3 measures it                                                                                                         | S3                        |
| D7  | effects stop after a state load                                                                                                                                                                                                                                                                                                                                                              | run: `notes/dsp-plan-2026-10-21/`                                                                                                                          | save the host-boot state                                                                                                     | S1                        |
| D8  | the DSP's return levels are uncalibrated: DSPTONE's -20 dBFS tone is 13 dB louder than a C4 in MAME, while AW's mix is "about a piano note's level" on the unit                                                                                                                                                                                                                              | run (DT, "How it was checked"); unit (AW, "The DSP mode")                                                                                                  | measure return gains (E1) and set them                                                                                       | S6                        |
| D9  | host uploads land in DSP memory at once; the chip moves them through EPB0's six-word FIFO and DMA channel 8                                                                                                                                                                                                                                                                                  | code; DT "The host DMA"                                                                                                                                    | only timing; nothing observed depends on it                                                                                  | S18 (opt.)                |
| D10 | every effect send gets the whole TG mix (mono in places) at one send level; the unit sends per part through the group-0x20 matrix                                                                                                                                                                                                                                                            | code: `kn7000.cpp:1483-1488` (the comment calls it an approximation); `kn7000_tonegen.cpp:225-249`                                                         | the TG computes per-bus sends from per-part levels                                                                           | S9                        |
| D11 | DRC and interpreter disagree (22% of samples). Found 2026-10-21: the interpreter checks interrupts only at the start of each `execute_run` and not in a delay slot, so an IRQ0 that arrives while the unit chain masks it, or meets the `807A` spin in a delay slot, waits and merges with the next: about 11,800 frames a second at 60 MHz, 8,070 at 240. The DRC takes it as the chip does | run: `notes/dsp-noise-2026-10-21/` (frame counts); run (2026-09-23): `notes/sharc-drc-parity/README.md`                                                    | test pending interrupts inside the interpreter loop, as the DRC does (`sharc.cpp`); the DRC needs nothing                    | S15                       |
| D12 | "the KN7000 sound is very noisy" (Felipe, G19). Settled 2026-10-21: it is the emulation running below real time. The computed stream is clean; a live capture at 60% speed is stretched, about 8% flat, with the floor between harmonics 13-21 dB higher, DSP bypassed or not; at about 100% the live sound equals the computed stream                                                       | run: `notes/dsp-noise-2026-10-21/` (live captures with `pw-record`, `-video none` control); `notes/dsp-noise-split/README.md`                              | reach 100% on Felipe's host: measure the speed there; `-autoframeskip`; the window's render cost; then the SHARC's share     | S4 (D2, a separate error) |

PM words the firmware never writes hold power-on garbage on the chip and 0 in MAME (pass 7: 510 of 510 differ in
0x8102-0x82FF). That is not a discrepancy worth fixing.

## 3. Unknown hardware facts, and the cheapest experiment for each

Every experiment uses the proven route: a menu app on the SD card started by `KN7LOAD.CNV`, built like DSPTONE. It
uses only the firmware's own host-port routines, keeps the kernel, hooks unit slots, reads each upload back, and
puts everything back. Nothing persists past a power cycle (DT, "Risks and recovery"). Each app runs in MAME first,
and the same files come back from MAME and from the unit for comparison. Ordered by value per unit of Felipe's
time:

| #   | unknown                                                                                          | settles                       | experiment                     | Felipe's work                  | ready?                        |
|-----|--------------------------------------------------------------------------------------------------|-------------------------------|--------------------------------|--------------------------------|-------------------------------|
| E2  | is the dry sound kept with REVERB on; how TOTAL DEPTH scales the return                          | D2, S4                        | a recording, no code           | one recording, about 1 minute  | yes (we supply the .mid)      |
| E1  | which TX slots reach the DAC in which panel state, at what gain; what each RX slot carries       | D1, D8, D10; S5, S6, S9       | RETMAP app                     | four 15 s recordings, SD files | new; hook/restore code exists |
| E3  | the core clock; each unit's real cycle cost; the frame's spare budget                            | G5, S3, S13, S17              | DSPCLK app                     | run once, about 1 minute       | new; small                    |
| E4  | what the kernel's 0x4000-0x7FFF and 0x10000-0x1FFFF accesses hit; the SDRAM's extent and mirrors | S11                           | S10a (static), then DSPMAP app | run once                       | new; small                    |
| E5  | whether the arithmetic corners match the chip                                                    | G4 flags, C.2-C.5, S14, D11   | SHARCTEST app                  | run once                       | new; medium                   |
| E6  | which DSP signal raises the MN10300's group 0x17                                                 | D5, S16                       | FLAG4 pulse, timed             | run once                       | new; pass 8's timing exists   |
| E7  | whether a known effect's output matches, not only its routing                                    | the end-to-end check of S4-S9 | two recordings, no code        | two short recordings           | yes                           |
| E8  | the KN6000/KN6500 unit map                                                                       | S20                           | MAME only                      | none                           | yes                           |

- **E2, no code.** Play a supplied MIDI file four times into one line-out recording. The file holds a C4 at a fixed
  velocity, 2 s on and 3 s off, repeated. The four passes: REVERB off; on at the default depth; on at depth 0; on
  at 127. With the dry sound kept, the note's level hardly moves between off and on, and the tail grows with
  depth. With the dry sound dropped, as MAME does today, the note falls by about 7.6 dB at the default depth
  (2.4x, `reverb-toggle-findings.md`, P4).
- **E1, RETMAP.** One DSP program is hooked into all ten unit slots. It writes a different steady tone to each of
  the 24 TX words the units use (0xC342-0xC359: 1 kHz + 125 Hz x k, -30 dBFS), and copies the 32 RX words into a
  DM snapshot that the app saves to SD once a second. Felipe runs it in four panel states (REVERB on/off x CHORUS
  on/off) and holds a C4 for 5 s in each. A spectrum of each recording names the audible slots and their gains.
  The snapshots show what the tone generator sends on each RX slot. DSPTONE has the hook and restore code (one
  slot), and so does Another World (two).
- **E3, DSPCLK.** A program in the first and the last slot enables timer 0 (period at its maximum), which counts at
  the core clock (UM 3-53, 11). It stores TCOUNT at both points every frame. Frame-to-frame deltas give the cycles
  per frame: 1,361 at 60 MHz, 1,497 at 66. First-to-last gives what units 1-8 cost. It saves 4,096 frames to SD,
  for REVERB and CHORUS each set to a few types.
- **E4, DSPMAP.** First the static list (S10a). Then a program writes patterns through the normal-word addresses
  and reads them back through every other view: short-word, the reserved ranges, 0x4000-0x7FFF, and SDRAM above
  0x11FFFF. It stores the results for the host to read.
- **E5, SHARCTEST.** About 200 vectors {instruction, inputs} run in a slot, and the results and ASTAT go to DM for
  the host to read. The corners: AVG rounding, the MAC's fractional rounding and flags, the dual add/subtract's
  flags with ALUSAT, FIX overflow, pre-modify wrap, RECIPS seeds, and 40-bit float stores. MAME runs the same app,
  and the two files are diffed. It is the first instruction-level oracle we would have.
- **E6.** A program adds one extra FLAG4 pulse (IOSTAT) per frame, and the app times the firmware's accesses as pass
  8 does. Twice the handshake rate means FLAG4 drives group 0x17. If it does not, try FLAG5, 7, 8 and 10 in turn
  (the kernel's IOCTL makes them outputs).
- **E7, no code.** Line-out recordings of a staccato C4 with Concert1 (a 4 s tail) and of a held C4 with Chorus1, both
  from a supplied MIDI file.
- **E8, MAME only.** Re-derive the unit walk from the KN6xxx PM, and capture `DspEffectSelect` live, with the method of
  `dsp-unit-roles-live-capture.md`.

**Safety rules for the new apps.** These are DSPTONE's rules, plus three more for RETMAP and E6:

- Hooking all ten slots replaces every effect for the duration, so the app restores and reads back all ten,
  including on any failure.
- E6's extra FLAG4 pulse could, in the worst case, make the firmware miss a handshake and set its dead flag. A
  power cycle undoes that, and the app checks the flag after every step.
- Timer 0 in E3 raises no interrupt that matters: its vector is one of the kernel's RTI stubs (K:77-94), and the
  app leaves IMASK as it found it.

E1, E3, E4, E5 and E6 can be one app with five modes, released once, so that Felipe copies one folder.

## 4. The work plan, in short iterations

Each step is one or two commits with a light, targeted check. Full validation runs only at the four milestones.
"Oracle" means the gate's KN7000 audio oracle (`tools/gate.sh`, ORACLE_MD5 `5069aeda`; `d5205327` since 2026-10-21,
G23). When it moves, it is re-baselined in its own commit with an attribution run, as before
(`oracle_attribution_msgr.sh`).

### Phase 1: cheap correctness (no unit work needed)

**S1. Save state (G3).**
- Goal: effects survive a save state.
- Files: `kn7000.cpp` (save `m_dsp_running`, `m_dsp_mode`, `m_dsp_cur`, `m_dsp_wbuf`, `m_dsp_wcnt`,
  `m_dsp_block_open`, `m_dsp_dl_addr`; `m_dsp_flag3` and the readback state are saved already). `sharc.cpp`
  already saves `m_iop` and the SPORT phase (`:194-199`).
- Check: `notes/dsp-plan-2026-10-21/run_checks.sh OUT kn7000` shows at least 9 distinct values of 10 on its
  "G3 load" line; the oracle is unchanged.
- Risk: none.
- Effort: S.
- Depends on: nothing.

**S2. The bypass switch (G19).**
- Goal: a machine configuration "Effects DSP: Emulated / Bypassed" that keeps the code. Bypassed holds the SHARC
  halted after the download, leaves `dsp_audio_tick` before IRQ0, and lets the bridge pass the TG through. The
  core's self-ack keeps the firmware's dead flag at 0.
- Files: `kn7000.cpp` (INPUT_PORTS, `dsp_audio_tick`, the "go").
- Check: `dsp_alive.lua` gives 0 frames bypassed and 88,200 emulated; the dead flag stays 0 in both (a tap like
  DSPTONE's); the oracle is unchanged with Emulated; record the Bypassed oracle as a second md5 in `gate.sh`.
- Risk: the handshake must keep coming while bypassed, or the firmware stops uploading.
- Effort: S.
- Depends on: decision O1 for the default.

**S3. 60 MHz (G5).** Done 2026-10-21 (Felipe's decision O2), overlay commit "kn7000: the effects DSP at 60 MHz".
Checked on the new binary (md5 `7336efbe`): the gate's audio oracle alone gives `5069aeda`, unchanged, as does the
66 MHz binary by the same recipe (`notes/dsp-noise-2026-10-21/oracle_only.sh`); DSPTONE's `run_mame.sh` 10 of 10
(dead flag 0, heartbeat 44,100/s); Another World's `run_round3.sh OUT keys` gives the same event log as the committed
66 MHz reference (`technics-anotherworld` `keys-results-2026-10-21`, "|mix| max 925824, dead 0"), intro at
-41 dBFS. The frame-budget harness was not re-run: it needs a temporary counter in the driver, and the unchanged
oracle already shows no frame changed. E3 still measures the real clock.
- Goal: the part's clock.
- Files: `kn7000.cpp:2557`.
- Check: `dsp_alive.lua` 88,200/s; the frame-budget harness (`notes/dsp-frame-budget/chord_harness.lua`) gives no
  more stale frames than at 66; the oracle unchanged (expected, as on 2026-09-23) or attributed.
- Risk: a frame overrun with some effect combination that the harness does not load. E3 gives the real margin.
- Effort: S.
- Depends on: decision O2.

**M1 (milestone).** `tools/gate.sh` in full; `ab_boot.sh` on the eight cases; DSPTONE's `test/run_mame.sh` (10 of
10) and AW's `probes/cnv/run_dsp.sh` (11 of 11); passes 6, 7 and 8 in MAME (`cnv_romdump/test/run_test.sh --dsp`,
`--dspmem`, `--dsprate`, with `-bios v13`) still match the unit's files. Publish.

### Phase 2: the two audible errors (unit evidence: AW now, E2 and E1 to confirm)

**S4. REVERB keeps the dry sound (D2).**
- Goal: part 3's [direct, return] pair switches only the reverb return part. The dry TG sound always reaches the
  DAC; with REVERB on, unit 0's return is added, scaled by TOTAL DEPTH.
- Files: `kn7000_tonegen.cpp:225-249`; the bridge's mix in `kn7000.cpp:283-290`.
- Check: a new light rig, `rev_onoff.lua`, holds a C4 with REVERB off, then on. In MAME the held note's RMS must be
  within 1 dB between the two (`kn5000_wav_ab.py` per second), and against E2's recording the on/off ratio within
  1.5 dB. The oracle moves (it is "keybed + reverb"): attribute and re-baseline.
- Risk: E2 might show the unit does drop the dry level. Then S4 becomes a depth-law fix instead. Do E2 first if
  Felipe can record soon; otherwise S4 can go on the code reading and wait for E2 to confirm it.
- Effort: S.
- Depends on: E2 (preferably).

**S5. Unit 9's return always mixed (D1).**
- Goal: read unit 9's TX pair every frame and sum it at a fixed level, whatever CHORUS and REVERB are. The CHORUS
  button moves only the send (`effect-return-routing.md`). The CHORUS-LED stand-in stays only as a default for the
  send level, no longer as a gate on the return.
- Files: `kn7000.cpp:1483-1512`.
- Check: AW's `run_dsp.sh` with REVERB off gives a non-silent intro (the AW mix above -60 dBFS), as on the unit;
  DSPTONE 10 of 10; the oracle unchanged, because the chorus unit's return is silent with no send.
- Risk: low.
- Effort: S.
- Depends on: nothing; E1 sets the level later.

**S6. Return gains from E1.**
- Goal: replace the 0.60 makeups and the depth law with E1's measured gains: each return's level against the dry
  path, at default depth.
- Files: `kn7000.cpp` bridge.
- Check: RETMAP's own MAME run gives the same relative tone levels as the unit's recordings (within 1 dB per tone);
  DSPTONE's sine against a C4 matches the unit's ratio.
- Risk: the analogue path (line out) adds a constant but not per-slot differences, so only ratios are used.
- Effort: S.
- Depends on: E1.

**M2 (milestone).** As M1, plus E2 and E7 compared with MAME by `wav_shift.py` and level/spectrum (section 6).
Publish. This is the point to reconsider the bypass default (O1).

### Phase 3: the serial audio path (structural)

**S7. Converge the SHARC core with branch B (A1.14).**
- Goal: one SHARC core, B's commits as the base: the multiplier flags (`586094eb3db`), the dual add/subtract flags,
  I8/I9 as DRC scratch, ALUSAT at run time (`38f4bca2b3a`). Each is its own commit.
- Files: `sharc.cpp/.h`, `sharcdrc.cpp`, `sharcops.hxx`, `sharcfe.cpp`.
- Check: for each commit, the oracle (expected unchanged: the program never reads MV/MU,
  `measure_dsp_astat_reads.py`); the DRC parity harness; speed (`-bench 60` against the published binary,
  within 5%, since `b1028bd` credited compile-time ALUSAT for the frame rate).
- Risk: run-time ALUSAT slows the DRC.
- Effort: M.
- Depends on: decision O3.

**S8. SPORT DMA moves the words.**
- Goal: the eight channels move one word per slot through their TCB chains (B's `e0c4a27c956` engine, with the
  overlay's live-register phase from `b269162`). The board supplies 8 slots per frame and gets per-slot `sport_tx`
  / `sport_rx` callbacks (SPORT, A/B, slot). The driver stops reading and writing fixed ring words. Bit-level
  serial clocking stays unmodelled (32-bit slots at 256 fs, `notes/sound-hw-architecture.md`: 11.2896 MHz net).
- Files: `sharc.cpp/.h` (21065L), `kn7000.cpp` (`dsp_audio_tick` becomes the frame clock; the bridge takes slot
  data).
- Check: passes 6 and 8 in MAME still give DMASTAT `0x33F`, CR0A 5, IIR0A `0xC365` (unit values). The oracle may
  shift by a constant latency only: `wav_shift.py` residual below 0.5%. The `tap_c329.lua` TCB stays `0xC362`.
- Risk: a one-frame latency difference; the DRC/interpreter question (D11) may change.
- Effort: M-L.
- Depends on: S7.

**S9. The tone generator owns sends and returns.**
- Goal: model the group-0x20 per-part matrix (rows: reverb send, chorus send, multi send, level; reg 0xA:
  [direct, return] per part) in `kn7000_tonegen`. Each voice adds to its part, each part to the buses by its send
  levels, and the buses go out on the RX slots E1 identified. The TX slots come back as return parts 3, 6, 9 and
  unit 9's fixed return. The bridge becomes plumbing with no constants. Per-part sends need the TG to keep per-part
  sums, which it can, since each voice knows its part.
- Files: `kn7000_tonegen.cpp/.h`, `kn_tonegen.cpp/.h`, `kn7000.cpp`.
- Check: RETMAP in MAME gives the unit's map (E1 files, byte for byte on the RX snapshot's slot layout and within 1
  dB on levels); DSPTONE and AW as before; E7's reverb tail RT60 and spectrum within the tolerance in section 6.
- Risk: the largest change in the plan. It touches the voice engine shared with the KN6000 (`kn_tonegen`). Keep the
  KN6000 on the old path until S20.
- Effort: L.
- Depends on: S8, E1.

**S10. Units 7 and 8.**
- Goal: feed the mic reverb's input (silence until a mic input exists) and the EQ insert (u8 on the master feed, its
  return replacing the master mix, `dynamics-eq-exciter.md` 5.4).
- Files: as S9.
- Check: with the EQ flat, the output is bit-identical to before (the GUI-flat EQ is transparent); with a boosted
  band, the spectrum moves the right way.
- Effort: S.
- Depends on: S9.

**M3 (milestone).** As M2, plus RETMAP in MAME against the unit and `sharc-drc-parity/ab_run.sh` on the other SHARC
machines (gticlub, nwktr, hornet, model2: no change). Publish.

### Phase 4: chip fidelity (each closes a probe)

**S10a. Who touches 0x4000-0x7FFF and 0x10000-0x1FFFF (static).**
- Goal: list the instructions and pointer set-ups that form those addresses in the 80 records and the kernel; say
  whether they mean short-word 16-bit storage or aliasing.
- Files: `technics-roms-disasm/kn7000/dsp/` (a script beside `check_sharc_coverage.py`).
- Check: the list accounts for the 1,642 addresses `dsp-frame-budget` counted.
- Effort: S.
- Depends on: nothing (do it before writing DSPMAP).

**S11. The memory map by the manual.**
- Goal: block 0 and block 1 with their 48/32-bit overlap, the short-word views with 16-bit access, the reserved
  ranges as E4 shows them on the chip, and the SDRAM as 1M words at 0x20000 with the chip's mirroring.
- Files: `sharc.cpp/.h` (21065L maps, handlers).
- Check: DSPMAP's file from MAME equals the unit's byte for byte; the oracle attributed.
- Risk: the 2026-09-23 lesson (`dsp-frame-budget`): shrinking the map silenced the DSP. This needs E4 before any
  change.
- Effort: M.
- Depends on: S10a, E4.

**S12. Status registers.**
- Goal: SYSTAT, IOSTAT, STCTLx status bits including TUVF_A's sticky start-up underflow, IOCTL bits 31/15 read as 0,
  MSGR3 as a plain register (the boot probe's answer to come from the kernel's own write, as on the chip). The
  kernel's reads return the register file (not 0) once each status bit is modelled.
- Files: `sharc.cpp` (21065L), `kn7000.cpp` (`dsp_data_r`'s stand-ins).
- Check: pass 6 in MAME equals the unit for every register in the probe's table; boot still clears the dead flag
  check; the oracle unchanged.
- Effort: S.
- Depends on: nothing.

**S13. Timers.**
- Goal: TCOUNT counts at the core clock, TPERIOD/TPWIDTH, PWMOUT and WIDTH_CNT modes, and the timer interrupts (UM
  chapter 11).
- Files: `sharc.cpp/.h`.
- Check: DSPCLK in MAME gives exactly 60e6/44,100 = 1,360.5 cycles per frame and the units' instruction counts.
- Effort: S.
- Depends on: S3.

**S14. Arithmetic against the chip.**
- Goal: fix what SHARCTEST (E5) shows: C.3's rounding, the flags, the 80-bit MR if any vector exposes it.
- Files: `sharcops.hxx`, `sharcdrc.cpp`.
- Check: SHARCTEST's MAME file equals the unit's, in both the DRC and `-nodrc`; the oracle attributed;
  `sharc-drc-parity/ab_run.sh` on the other SHARC machines (they share the core).
- Risk: other machines' output changes. Keep each fix in its own commit with that A/B.
- Effort: M.
- Depends on: E5, S7.

**S15. DRC and interpreter agree (D11).**
- Found 2026-10-21 (`notes/dsp-noise-2026-10-21/`, "DRC and interpreter"): the interpreter is the one that is wrong.
  It tests pending interrupts once per `execute_run`, so the kernel's IRQ0 (masked during the unit chain, unmasked
  in a delay slot, then a spin whose PCs are two-thirds delay slots) waits and merges with the next tick's edge:
  11,800 of 44,100 frames a second. The DRC tests at block entry, at branches and after IMASK/MODE1 writes, and
  finishes every frame.
- Goal: the interpreter takes a pending, unmasked interrupt at the first instruction boundary outside a delay slot,
  as the DRC does.
- Files: `sharc.cpp` (`execute_run`), possibly `sharcops.hxx` (after IMASK/MODE1/IRPTL writes).
- Check: `frames_tap.lua` with `-nodrc` gives 88,200/44,100; the passage's `-nodrc` WAV equals the DRC's md5 (or
  differs only by what remains of block timing); `sharc-drc-parity/ab_run.sh` on the other SHARC machines.
- Risk: it changes every interpreter-only SHARC machine (nwktr among them, mamedev discussion #257).
- Effort: S.
- Depends on: nothing.

**S16. The handshake from the DSP.**
- Goal: raise group 0x17 from the signal E6 identifies, so that a stalled DSP behaves as on the unit.
- Files: `kn7000.cpp`, `sharc.cpp` (flag output callbacks for FLAG4-11 through IOSTAT).
- Check: pass 8 in MAME still gives verdict (b) with the unit's lattice; a deliberately stalled test program sets
  the dead flag in MAME as DT's "Risks" describes.
- Effort: S.
- Depends on: E6.

**Optional, only if a need appears.** S17 is a cycle model (SDRAM latency, PM conflicts) fitted to E3's per-unit
costs, worth doing only if an effect overruns on the unit or homebrew needs exact budgets (L). S18 runs host uploads
through EPB0 and channel 8 with their timing (M).

**M4 (milestone).** Everything in M3; all five probe modes (E1, E3-E6) in MAME equal to the unit's files. Publish.

### Phase 5: the other machines

- **S19. KN6000/KN6500 flags.** KN6500 IMPERFECT_SOUND, like the KN6000 (G15). Check: `-validate`. S.
- **S20. KN6000/KN6500 unit map** (E8). Re-derive the unit walk from their PM; check that the bridge's slot
  addresses hold, or give them their own table. Check: a live `DspEffectSelect` capture as for the KN7000, and
  `dsp_alive.lua` 88,200/s. M. Then S9 can switch them over.
- **S21. KN2400/KN2600.** Remove the inherited SHARC from their config until their DSP is identified (decision
  O7). Check: `ab_boot.sh` identical; `-validate`. S. Identifying the chip needs a service manual or a board photo.
- **The µPD6383 machines** (KN5000, KN1500, WSA1/WSA1R) follow their own decode roadmap. One small item belongs
  here: check by a run whether `WSA1R_ENABLE_DSP 1` lets the cores execute without `set_disable()`. Fix the KN5000
  latch width and store gate (G17), each S.

### Regression tests with unit ground truth

These run at every milestone (and after S4, S5, S8, S9). Each has an answer from the unit, so a change that breaks
them is wrong, whatever the oracle says.

| test                    | command                                                            | must give                                                                   | unit ground truth                                                               |
|-------------------------|--------------------------------------------------------------------|-----------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| DSPTONE iteration 1     | `technics-roms-disasm/kn7000/tools/dsptone/test/run_mame.sh OUT`   | 10 of 10; heartbeat about 44,100/s; sine at 440 Hz; reverb back after STOP  | heartbeat 44,087/s, tone and sweep heard, reverb back (DT, "On the instrument") |
| Another World, DSP mode | `technics-anotherworld/kn7000/probes/cnv/run_dsp.sh`               | 11 of 11; after S5 also heard with REVERB off                               | heard with REVERB on and off, on a little louder (AW, "The DSP mode")           |
| passes 6, 7, 8 in MAME  | `cnv_romdump/test/run_test.sh --dsp/--dspmem/--dsprate --bios v13` | 5 of 5, 4 of 4, verdict (b); `compare_dspmem.py` downloaded words identical | the unit's files (private, `real_dump_v1.3_b893/pass6..8-run1/`)                |
| G3 and liveness         | `notes/dsp-plan-2026-10-21/run_checks.sh OUT`                      | G3 load at least 9 of 10 distinct (after S1); 88,200/s on kn7000/6000/6500  | -                                                                               |
| the oracle              | `tools/gate.sh`                                                    | md5, or an attributed re-baseline                                           | - (a change detector, not a truth)                                              |

## 5. Upstreaming

Today: upstream has no DSP (`kn7000.cpp:10-11`, all five sets MACHINE_NO_SOUND). Branch B
(`technics-kn7000-dsp`, `a1c1fe1db93`, 8 commits, never pushed) is queued behind A2 (`technics-kn7000-tonegen`,
`7f7d1857e20`) in `mame-pr-queue/MAME-PR-QUEUE.md` row 4 (in `KN7000/` until 2026-10-29), held since Felipe's "Leave A2 and B for later" (PARKED.md:22-58).
B has not been rebased over upstream's four later `kn7000.cpp` commits (#16394, #16416, #16523, #16524). The cpu.lua
DRC token bug is still upstream (`technics-cpulua-drc-token`, `947b74a69f8`).

Proposed order, consistent with that queue:

| PR  | content                                                                                                                                         | from                                                         | when                                                                                             | needs                                                       |
|-----|-------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------|--------------------------------------------------------------------------------------------------|-------------------------------------------------------------|
| U1  | `scripts/src/cpu.lua`: DRC_CPUS names `ADSP2106X`                                                                                               | `947b74a69f8` (= B's `d06625a1c89`)                          | now; one line, no dependencies                                                                   | -                                                           |
| U2  | `cpu/sharc`: fixed-point fixes for every SHARC machine (compute-op fallback, multiplier/AVG/TOGGLE ASTAT, DRC ALUSAT; later C.3 and E5's flags) | B's `9682a3be5ea`, `586094eb3db`, `38f4bca2b3a`; S14         | ahead of A2 if O4 says so; with `sharc-drc-parity/ab_run.sh` results on the other SHARC machines | S7 converged                                                |
| U3  | `cpu/sharc`: the ADSP-21065L: internal memory placement, IOP register file, host port access, SPORT DMA, timers, status registers               | B's `adde78790e0`, `e0c4a27c956`, plus S8, S11-S13 ported in | after S8 and S12; S11 and S13 may follow as a separate PR                                        | a device with no driver is reviewable with a short test rig |
| U4  | `matsushita/kn7000.cpp`: the effects DSP (host boot, the frame clock, the SPORT slots into the tone generator's mix)                            | B's `a1c1fe1db93`, redone on S9                              | after A2 is open and S9 is done                                                                  | A2; rebase over #16394/#16416/#16523/#16524                 |
| U5  | KN6000/KN6500 effects                                                                                                                           | S20                                                          | after U4                                                                                         | E8                                                          |

**Stays in the overlay.**
- The KN7000-only handshake and timing glue that lives in the MN10300 core's overlay version (the self-ack, TM4's
  group, `set_dsp_handshake_selfack`), until the overlay's interrupt model (A1.1) goes upstream.
- The bypass switch, if it exists only for research.
- Probe-only conveniences: the DSP-side readback stand-ins, if any remain after S12.
- The CHORUS-LED send default, until the per-part depth gate is understood (`per-part-depth-bank.md`).
- The KN2400 SHARC, until S21.
- The KN5000 DSPHLE and the µPD6383 cores (not reviewable yet).

**What not to send.** The bridge's constants: U4 should carry the tone generator's own matrix (S9). A reviewer will
ask where 0.60 comes from, and only E1 can answer that.

## 6. Validation strategy

**Oracles, from strongest to weakest.**

1. **Unit probe files**, compared byte for byte with the same app in MAME: passes 6-8 (existing), and E1, E3, E4, E5
   and E6 (new). They test registers, memory and arithmetic exactly. They cannot test the analogue output.
2. **Unit line-out recordings**, compared by ratios, pitch and spectra, never sample by sample. The analogue path
   and the 0.03-0.08% clock difference rule out a bitwise comparison. Tools: `wav_shift.py` (align, residual),
   `kn5000_wav_ab.py` (per-second RMS), `g13-waves-2026-10-20/oracle_note.py` (pitch, level, tail).
3. **DSPTONE and AW's DSP mode** in MAME, with the unit's verdicts (section 4's table): end-to-end regression tests
   that touch the host port, the kernel, SDRAM and the return path.
4. **The gate's oracle**: a change detector. Every move is attributed.

**What to ask Felipe to record.** The aim is to keep his work low. Each item says exactly what it settles. All
recordings are taken from the line out at 44.1 or 48 kHz, 16 or 24 bit, with MAIN VOLUME at a fixed, noted position,
and kept private in `technics_roms`.

| #   | what Felipe does                                                                                                     | length      | settles                                                                                                                   |
|-----|----------------------------------------------------------------------------------------------------------------------|-------------|---------------------------------------------------------------------------------------------------------------------------|
| R0  | done 2026-10-21 without Felipe, by live captures in MAME: the noise is the speed (D12). Optional: his host's speed % | 10 s        | D12: whether the noise is the DSP path, the TG, the floppy hum, or D2's wet-only output                                   |
| R1  | E2: the supplied MIDI file four times (REVERB off; on at default depth; on at 0; on at 127)                          | about 1 min | D2 and the TOTAL DEPTH law (S4)                                                                                           |
| R2  | E1: the RETMAP app in four panel states, holding C4 for 5 s in each                                                  | 4 x 15 s    | which returns reach the DAC and at what gain (D1, D8, S5, S6); the RX slots' contents (S9), from the SD files             |
| R3  | E7: a staccato C4 with Concert1 (4 s tail) and a held C4 with Chorus1, both via MIDI file                            | 2 x 6 s     | whether the effects compute as on the chip: RT60 per octave band within 10%, chorus LFO rate within 2%, depth within 1 dB |
| R4  | the same app's other four modes (E3-E6): one run, no listening                                                       | about 3 min | clock, cycle costs, memory map, arithmetic, handshake source                                                              |

R1 and R3 need no code on the unit. R2 and R4 are one release folder. If only one recording session is possible,
the order is R1, then R2.

## 7. Open decisions for Felipe

| #   | decision                                             | options                                        | recommendation                                   |
|-----|------------------------------------------------------|------------------------------------------------|--------------------------------------------------|
| O1  | the bypass switch's default (G19)                    | Bypassed (the 2026-10-20 plan) / Emulated      | Bypassed in S2 as asked; Emulated once S4 is in  |
| O2  | the DSP clock (G5)                                   | 60 MHz now / wait for E3                       | decided: 60 MHz now (done, S3)                   |
| O3  | the reference for the SHARC core and the 21065L      | the overlay / branch B                         | B as the base, the overlay's additions ported in |
| O4  | send the core fixes (U2) ahead of A2                 | yes / keep the queue order                     | yes; U1 now                                      |
| O5  | the tone generator's matrix (S9), or keep the bridge | S9 / the bridge with calibrated constants (S6) | S9, after E1; S4-S6 first                        |
| O6  | the new unit apps (RETMAP; the five-mode probe)      | approve / not now                              | approve                                          |
| O7  | the KN2400/KN2600 SHARC                              | remove until identified / keep halted          | remove                                           |
| O8  | the frame rate                                       | 44,100 exact / the unit's 44,087               | 44,100                                           |
| O9  | the priority of the KN5000 DSP track                 | after the KN7000 / in parallel                 | after phase 2                                    |

Why:

- **O1.** The "noise" turned out to be speed, not the DSP's arithmetic (D12, 2026-10-21): bypassing the DSP does not
  remove it on a host that is slow anyway, and it makes DSPTONE and Another World's DSP mode silent. D2 (wet-only
  with REVERB on) is real but makes the sound quieter and distant, not noisy. Emulated as the default is the better
  choice once the host runs at 100%.
- **O2.** Three independent readings agree: the part grade, X301's part number, and SDRDIV with the kernel's IOCTL
  (1.2). The 2026-09-23 harness gave identical audio at 60 and 66 MHz. E3 confirms it later.
- **O3.** B is already split for review. The overlay's additions each have a unit pass behind them: the MSGR
  read-back, the live SPORT registers, the host IOP file and the EPB0 readback. After the port, the overlay
  re-converges onto B (A1.14).
- **O4.** U2 helps every SHARC machine and does not need the KN7000 driver.
- **O5.** S9 is the only version upstream would take, and the only one that gets per-part sends right. S4-S6 are
  small and audible, so they come first.
- **O6.** The apps are volatile, like DSPTONE, and one release covers them. While it runs, RETMAP replaces all ten
  effects. In the worst case E6 sets the dead flag. A power cycle restores everything.
- **O7.** The SHARC never runs on these machines (`dsp_alive.lua`), and its presence suggests a chip nobody has seen.
- **O8.** The 0.03% gap is between two crystals on one board, and the firmware's tick already runs on TM4.
- **O9.** The KN5000 track needs ISA decoding before any audio, and it has no unit probe route yet.

## 8. What this plan could not determine

- **D2 rests on code reading.** That rec51/rec56 write wet only, and that part 3's pair belongs to the reverb return
  part, are both read from the firmware and the TG capture. Nobody has measured either on the unit; R1 does.
- **What physically drives IRQ0, the handshake and FLAG3** (the TG's frame clock is presumed for IRQ0). E6 covers
  the handshake; the others need a schematic page this plan did not read.
- **The SDOE/SDIE index-to-pin order, and so which TX words the TG takes as which return.** E1 measures the
  behaviour, not the wiring.
- **The KN2400's DSP.** No service manual is in the tree.
- **Whether `WSA1R_ENABLE_DSP 1` runs the three cores freely.** That is from code reading only (section 1.3).
- **The cause of the DRC/interpreter divergence** (S15). It is open upstream too.
- **Whether the service manual states X301's frequency.** The 30 MHz figure is by part-number pattern
  (`notes/sound-hw-architecture.md:89`).

## 9. 2026-10-29: D1 done; D8 calibrated from the owner's volume settings

- **D1.** Unit 9's return is now mixed whatever CHORUS says, and unit 9's input is 0 while the chorus send is 0
  (`kn7000.cpp`, the bridge and the DSP frame). On the unit Another World's mix through unit 9 is heard with REVERB
  and CHORUS off; in MAME, ProTracker with REVERB off is now heard, 6.3 dB below REVERB on (it was silent).
- **D8.** The bridge's `TG_TO_DSP` puts the tone generator's samples at 1/4 of the DSP words' full scale, both ways.
  The factor cancels for everything the firmware's effects do to the tone generator's sound, and raises what the
  DSP makes itself by 12.0 dB against it. The evidence is the owner's MAIN VOLUME on the unit: the instrument is
  comfortable at 40-50 %, ProTracker (kn5000_homebrew `demos/kn7000_protracker`, DSP_GAIN 2) at 70 %. On the v^2
  taper that is 7.7 dB apart (5.8-9.7 dB over the ranges). The same taper also fits the owner's earlier two
  settings: DSP_GAIN 16 at 25 % is 17.9 dB on it, and the gain step was 18.1 dB. In one MAME session
  (`tests/mame/native_vs_pt.py`, `PT_NATIVE=1`: four notes and a chord on the power-on panel, then ProTracker):

  | build                                   | ProTracker - the instrument | CHORUS on - off (a chord) |
  |-----------------------------------------|-----------------------------|---------------------------|
  | before (unit 9 gated, scale 1)          | -25.9 dB                    | (not measured)            |
  | unit 9 always, its makeup 4.48          | -7.5 dB                     | +16.8 dB: rejected        |
  | unit 9 always at 0.60, `TG_TO_DSP` 1/4  | -7.8 dB                     | +4.6 dB                   |

  A return gain alone could not fit: matching ProTracker made CHORUS turn a chord 7 times louder. The files are in
  kn5000_homebrew `demos/kn7000_protracker/tests/results/native-vs-pt-mame-*.txt`. Unconfirmed: which bit width the
  tone generator's words really have. E1 (RETMAP) measures the return gains directly and supersedes this.
