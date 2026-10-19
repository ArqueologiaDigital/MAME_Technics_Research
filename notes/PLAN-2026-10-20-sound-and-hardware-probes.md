# Plan: real wave ROMs, a DSP bypass, and probing the sound chips on the real unit (2026-10-20)

Felipe's three next tasks, noted on 2026-10-20 and **not started**. This file is the sequence and the
reasoning; `OVERLAY-GAPS.md` tracks the items themselves (G13, G19, G20) and is updated as they move.

1. **Use the dumped KN7000 wave ROMs in the tone generator** instead of the synthetic placeholder. Other
   machines keep a placeholder: the KN5000, and also the KN6000/KN6500/KN2400, whose wave ROMs are not dumped.
2. **Temporarily disable the effects DSP without deleting its code**: the overlay's KN7000 sound is very noisy,
   and the DSP is the prime suspect. It must be easy to turn back on for DSP research.
3. **Use the .CNV loader to run probes on the real unit** that read the DSP (and, if still needed, the tone
   generators) and log to the SD card, to ground the reverse engineering.

## What is already known

- **The audio path.** The tone generator feeds `kn7000_dsp_bridge_device`, which feeds the speakers
  (`kn7000.cpp`, `kn7000()` routes). The bridge is transparent when the SHARC is not running: until the DSP's
  first output frame, the TG passes straight through. So a bypass only has to keep the SHARC halted; the bridge,
  the kernel download and every DSP line of code stay.
- **The firmware's view.** The DSP self-test handshake on interrupt group 0x17 is answered by the CPU core
  itself (`mn10300.cpp` `intc_w`), so with the SHARC halted the firmware still finds the DSP "present" and keeps
  uploading kernels; the uploads land in the host port and go nowhere.
- **The wave ROMs.** IC203/IC204 (main TG) and IC207/IC208 (sub TG) are dumped from Felipe's unit and verified
  against the firmware's own checksums. Format settled: 16-bit samples, low byte first, the Y and X chips are
  the even and odd samples of one stream (`technics_roms/roms/kn7000/real_dump_v1.3_b893/wave-analysis/`).
  Not settled: the order of whole 32 KB banks (only the hardware could permute them), and **how a voice's
  registers select its sample start, loop and end**: the blocker recorded as G13. Today only the wave-ROM test
  port reads the dumps; voices play the synthetic pack (`kn7000_tonegen.cpp`).
- **The probe route.** `technics-roms-disasm/kn7000/tools/cnv_romdump/` runs our code on the main CPU of
  Felipe's unit (program 893) through STYLE CONVERT and writes SD files; four passes ran clean on 2026-10-19.
  It finds the firmware's routines by search, so it does not depend on 941 addresses. Its proven operations are
  plain memory reads and the wave-ROM test port; a DSP or TG probe would add I/O writes (host-port index,
  TG registers). Those only change volatile state: the DSP is re-booted by the host at every power-up and the
  TG is re-initialised, so a power cycle restores both. Persistent state to stay away from: the program and
  table flash, IC21, **IC23** (the panel memories; see G6) and the SD card's other files.
- **Open DSP questions** that real-hardware data would settle (G3, G4, G5 and "Undetermined" in
  `OVERLAY-GAPS.md`): the clock (60 MHz part, the overlay runs 66 to keep up); whether the effect kernel reads
  IOP registers back; how the SPORT DMA chains are really set up (branch B models them, the overlay does not);
  the group-0x17 handshake (upstream measured no G17ICR writes, the overlay's notes say there are).

## The sequence

| step | what                                                   | why at this point                                                                                | size   |
|------|--------------------------------------------------------|--------------------------------------------------------------------------------------------------|--------|
| 0    | finish the work in flight                              | IC23 as NVRAM (G6), the one-run survey dump, the SD/USB and Another World memory answers         | -      |
| 1    | DSP bypass switch, default bypassed                    | cheapest step, and every later listening test needs a clean TG path to judge                     | small  |
| 2    | reference recordings from the real unit, by MIDI       | the ground truth for steps 3-5, with no code on the unit                                         | small  |
| 3    | decode the sample selection offline, then use the ROMs | the data and the firmware's register writes are both in hand; try this before any hardware probe | medium |
| 4    | a general probe app on the .CNV route                  | one tool for every later hardware question; emulator-first, same files from MAME and the unit    | medium |
| 5    | DSP probes on the unit, then the DSP emulation fixes   | answers the open DSP questions; then G3, G4, G5 with evidence, and the DSP switched back on      | large  |
| 6    | TG probes on the unit, only if step 3 leaves gaps      | e.g. read back what a voice really plays                                                         | medium |

### Step 1 — DSP bypass

- A machine-configuration switch on the KN7000 (and KN6000/KN2400, which share the bridge): **Effects DSP:
  Bypassed / Emulated**, default Bypassed. Bypassed keeps the SHARC halted at the kernel's "go" and makes
  `dsp_audio_tick` return early; the bridge then passes the TG through. Nothing is deleted, and turning it back
  on is one click in the machine configuration menu (or a line in the cfg file).
- Check first that the bypass removes the noise: capture the same performance with the switch each way
  (`tools/rigs/money.lua`), compare RMS and spectra, and listen. If the noise survives the bypass, it is in the
  tone generator (the synthetic pack, pitch, envelopes), and step 3 matters more than the DSP.
- The gate's audio oracle (`ORACLE_MD5`) tests "keybed + reverb", so it measures the DSP path. Keep it, with
  the rig turning the switch to Emulated, and add a second oracle for the default Bypassed path. Re-baseline
  in its own commit, with the attribution recorded as before.

### Step 2 — reference recordings from the real unit

The safest ground truth needs no code on the unit at all: play the same MIDI file into the real KN7000 (MIDI IN)
and into MAME (`-midiin`), record the real unit's line out, and compare with MAME's `-wavwrite`. A short set of
files does most of the work: single sustained notes on a handful of voices across the keyboard (sample start,
loop, pitch), the same with each reverb and chorus type (DSP), and one demo-like passage. Felipe records; we
commit the MIDI files and the comparison script, keep the recordings private.

### Step 3 — the real wave ROMs in the tone generator

1. **Static.** Collect what the firmware writes for each voice: the per-slot voice record (`tg_recbase`, 0xB4
   bytes) and the register writes the overlay already logs. Find the sample boundaries in the dumps (onsets,
   silent gaps, any directory at a bank start) and fit a mapping: register value to word address, bank and
   chip select, loop and end. The Y/X interleave and 16-bit LE format are settled.
2. **In MAME.** Implement the mapping in `kn7000_tonegen.cpp` behind a switch (wave source: dumped ROMs /
   synthetic pack), on for the KN7000 only, so the KN5000, KN6000, KN6500 and KN2400 keep their placeholders.
   Judge it against step 2's recordings (pitch of each note, attack, loop points) with the DSP bypassed.
3. **If gaps remain**, step 6 asks the hardware.

### Step 4 — a probe app on the .CNV route

Generalise the dumper's SD application into a small interpreter of a probe table: read a memory range to a
file; read an I/O register N times with a delay; write a register sequence; wait; log. Rules:

- Every probe runs first in MAME on `-bios v13` (Felipe's firmware), and the same probe file is then run on the
  unit; MAME's output and the unit's are compared byte for byte. A difference is an emulation bug, located.
- Firmware routines are found by search, as the dumper does; nothing assumes 941 addresses.
- Writes only to volatile I/O (DSP host port, TG registers, INTC/timer registers) and to new SD files; never
  flash, IC21, IC23, or raw SD sectors. Each probe documents what it writes and how a power cycle undoes it.
- Releases follow the dumper's convention (`releases/<date>-<name>/` with a README.txt procedure).

### Step 5 — DSP probes on the unit

| probe                  | reads                                                                                  | settles                                                     |
|------------------------|----------------------------------------------------------------------------------------|-------------------------------------------------------------|
| P1 kernel readback     | the SHARC's internal program and data memory through the host port, after boot         | whether the download reaching the DSP is what MAME receives |
| P2 IOP and SPORT state | the IOP registers: SPORT control, DMA TCB chain, after a reverb is selected            | the SPORT DMA design (G4); whether IOP reads matter         |
| P3 rate                | a DSP-side counter (or the kernel's frame flag) against an MN10300 timer over a second | the clock and whether the kernel keeps up (G5)              |
| P4 handshake           | GxICR 0x3400015C at boot milestones                                                    | the group-0x17 question                                     |
| P5 state under signal  | data memory (delay lines, coefficients) while a note plays, at fixed intervals         | what the effect really computes, frame by frame             |

What the host port can read back (internal memory, IOP registers, external SDRAM IC307/IC308) has to be
established from the ADSP-21065L manual first; P5 depends on it. Then the emulation work (G3 save state, G4
branch B items, G5 clock) proceeds against these files, and the switch from step 1 goes back to Emulated once
the DSP path matches the recordings.

### Step 6 — tone-generator probes, if needed

Only if step 3 leaves questions: e.g. whether any TG register reads back a voice's current address, or a probe
that writes chosen start/loop values to an idle voice and plays it, while Felipe records the line out, to pin
the address mapping directly.

## Not decided here

- The default of the DSP switch on the KN6000/KN2400 (they share the bridge; their wave ROMs are not dumped).
- Whether the wave-source switch stays once the dumped ROMs work (probably not: placeholders only where no dump
  exists).
