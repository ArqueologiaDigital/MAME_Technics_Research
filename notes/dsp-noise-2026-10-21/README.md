# The effects DSP at 60 MHz, and what the KN7000's "noise" is (2026-10-21)

Two pieces of work from `notes/PLAN-2026-10-21-dsp-emulation.md`: step S3 (the clock, OVERLAY-GAPS G5) and the
noise Felipe hears in MAME (G19, D12, D2).

## The scripts

| script                 | question it answers                                                                                                                                                                       |
|------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `oracle_only.sh`       | does a binary still give the gate's KN7000 audio oracle (`tools/gate.sh` ORACLE_MD5), without running the gate?                                                                           |
| `passage.lua`          | the test passage: C4, then C4 E4 G4, with REVERB as at boot (on), then the same with it toggled off; logs emulation speed per second, the LEDs and the dead flag                          |
| `run_passage.sh`       | runs `passage.lua`: `wav` mode (`-nothrottle -wavwrite`, the computed stream) or `live` mode (throttled, real sound, `pw-record` of the sink monitor: what a listener hears)              |
| `bypass-scratch.patch` | NOT for the overlay: a scratch build in which `KN7000_DSP_BYPASS_SCRATCH=1` keeps the SHARC halted and the bridge passes the tone generator through (G19's switch does not exist yet; S2) |
| `clock-scratch.patch`  | NOT for the overlay: a scratch build whose DSP clock comes from `KN7000_DSP_CLOCK_SCRATCH` (Hz)                                                                                           |
| `frames_tap.lua`       | how many frames a second does the kernel finish (IOSTAT and unit 0's return writes)? Loaded by `passage.lua` through `EXTRA=`                                                             |
| `wavstats.py`          | does the computed stream carry noise, part by part (level, HF share, floor between harmonics, clicks, held samples, clipping)?                                                            |
| `firstnote.py`         | is the first note the listener hears the note MAME computed (pitch, floor, level), in any recording?                                                                                      |
| `livestats.py`         | how stretched and broken up is a recording (span, dropouts, exact zeros)?                                                                                                                 |

Every run's scratch goes under `~/compartilhado/tmp/dsp-noise/`, never `/tmp`.

## S3: 60 MHz

`kn7000.cpp` now runs the ADSP-21065L at 60 MHz (it was 66). The evidence for 60 is in the plan (section 1.2, "How
SDRDIV pins the clock"). Checked on the new binary, md5 `7336efbe70796a0e7de82ac3f8aed1c1`, against the published
66 MHz binary, md5 `3077b137f86844bbb8515d25c2d19008`:

| check                                             | 66 MHz                    | 60 MHz                            |
|---------------------------------------------------|---------------------------|-----------------------------------|
| `oracle_only.sh EMU OUT` (gate's audio oracle)    | `5069aeda`, = ORACLE_MD5  | `5069aeda`, = ORACLE_MD5          |
| DSPTONE `test/run_mame.sh` (technics-roms-disasm) | 10 of 10 (its README)     | 10 of 10; dead flag max 0         |
| Another World `probes/cnv/run_round3.sh OUT keys` | `keys-results-2026-10-21` | the same event log, line for line |

The two binaries' oracle WAVs are identical byte for byte, so the gate needs no re-baseline. In Another World's
run the DSP mode's intro is at -41 dBFS and the event log reports "|mix| max 925824, dead 0" as at 66 MHz. The
dead flag is 893's `0x500066D8` in both the DSPTONE and the Another World runs (`-bios v13`).

Run:

```sh
notes/dsp-noise-2026-10-21/oracle_only.sh ~/compartilhado/kn7000-emulator ~/compartilhado/tmp/dsp-noise/gor
EMU=<emu dir> technics-roms-disasm/kn7000/tools/dsptone/test/run_mame.sh ~/compartilhado/tmp/dsp-noise/dsptone
EMU=<emu dir> technics-anotherworld/kn7000/probes/cnv/run_round3.sh ~/compartilhado/tmp/dsp-noise/aw keys
```

`oracle_only.sh` repeats the gate's recipe exactly: the published `nvram/` minus IC23, the kn7000 liveness run
(which writes nvram the oracle run then reads), IC23 cleared again, then `money.lua` for 22 s. Without the liveness
run first the same binaries give `3f7a5dd2` instead (both clocks alike): the oracle depends on that nvram.

## The noise (G19, D12): performance, not the DSP's arithmetic

**Verdict.** What Felipe hears in a live MAME session is the emulation running below real time. MAME's computed
stream (`-wavwrite`) is clean and does not depend on host speed. When the emulation is slower than 100%, the sound
the listener gets is stretched, about 8% flat and has a noise floor between the harmonics 13-21 dB higher. At about
100% the live sound equals the computed stream. The effects DSP adds to the problem only through its cost: it makes
the emulation slower. On this VM the window's video rendering costs more than the DSP does, and with the DSP
bypassed the machine still runs at only 78-92% in a window. Separately, and not as noise, the computed stream with
REVERB on (the boot state) is D2's wet-only output: 7.9 dB quieter than the dry note, with no dry sound in it.

All runs: the VM (8 cores), overlay `4f7b9c7`, binary `7336efbe` (60 MHz, DRC on by default), `-bios v13`, the real
card image, the passage as above (A1/A2 with REVERB on as at boot, B1/B2 with it off; LEDs logged).

### Speed, and where host time goes

`run_passage.sh EMU OUT wav [args]`, mean of the per-second `pct` over t = 27-48 s (the notes), each run alone:

| configuration                        | window (`-window`) | `-video none` |
|--------------------------------------|--------------------|---------------|
| DSP emulated, DRC (the default)      | 67.1%              | 153.6%        |
| DSP emulated, interpreter (`-nodrc`) | 40.9%              | 68.3%         |
| DSP bypassed (`BYPASS=1`)            | 91.7%              | 234.4%        |

Throttled with sound (`live` mode) the same configurations run a little slower: DRC 59.7% (t >= 20), bypassed 78.3%;
with `-video none`, DRC 98.5% and bypassed 100%; DRC in a window with `-autoframeskip` 91.6%.

Wall time per emulated second, by difference: the SHARC under the DRC 0.22 s (no video) to 0.40 s (window), under the
interpreter 1.04 s; the window's video 0.66-0.84 s; everything else (MN10300, tone generator, the rest) 0.43 s. In a
window under the DRC (1.49 s per emulated second) that is about 56% video, 27% SHARC, 29% the rest (the parts do not
add exactly: they come from different runs). No profiler is installed (no `perf`, and this build has no
`-profile`), so the split is by these differences, not by sampling.

The DRC is on: `kn7000.cpp` calls `enable_recompiler()`, `build.sh` patches `cpu.lua` so the SHARC DRC backend links,
and `-nodrc` makes the machine 1.6x (window) to 2.2x (no video) slower. Nothing to switch on.

### Computed against live

The computed stream is the same whatever the host does: `-wavwrite` gives md5 `5436b3a6` (DSP emulated) in
`-nothrottle`, throttled with sound, and `-video none` runs alike, and `2e79fde8` bypassed in all three.

`firstnote.py` on the first note (A1, a held C4, REVERB on as at boot) and `livestats.py` on the whole passage:

| recording                                     | speed | C4 pitch | floor     | level      | span    |
|-----------------------------------------------|-------|----------|-----------|------------|---------|
| computed, DSP emulated (`p-drc/run.wav`)      | -     | 261.5 Hz | -93.3 dB  | -49.4 dBFS | 21.20 s |
| live, DSP emulated, window (`l-drc/live.wav`) | 59.7% | 241.0 Hz | -80.5 dB  | -44.8 dBFS | 36.98 s |
| live, DSP emulated, `-autoframeskip`          | 91.6% | 261.5 Hz | -84.6 dB  | -48.6 dBFS | 23.26 s |
| live, DSP emulated, `-video none`             | 98.5% | 261.5 Hz | -93.2 dB  | -49.4 dBFS | 21.70 s |
| computed, DSP bypassed (`p-byp/run.wav`)      | -     | 261.5 Hz | -102.2 dB | -41.5 dBFS | 21.24 s |
| live, DSP bypassed, window (`l-byp/live.wav`) | 78.3% | 242.4 Hz | -80.7 dB  | -38.6 dBFS | 27.97 s |
| live, DSP bypassed, `-video none`             | 100%  | 261.5 Hz | -102.1 dB | -41.4 dBFS | 21.28 s |

(Live levels read 3-5 dB high in the slow runs because the window holds more of the note's loud start.) The two
runs at about 100% are the control: the live capture then matches the computed stream in pitch, floor and length.
Below 100% the passage plays stretched to the emulation's speed (36.98 s for 21.20 s at 60%), the pitch falls by
about 8% (241 Hz for 261.5) and the floor between the harmonics rises by 13 dB (DSP) to 21 dB (bypassed). That is
the "noise": it is there with the DSP bypassed too, whenever the speed is short of 100%.

### The computed stream itself

`wavstats.py` on the -wavwrite files (instrument channels; the third channel is the floppy drive):

| part, DRC                       | rms        | floor     | > 5 kHz  | clicks | held runs >= 4 | clipped |
|---------------------------------|------------|-----------|----------|--------|----------------|---------|
| silence before the notes        | digital 0  | -         | -        | 0      | -              | 0       |
| A1 C4, REVERB on (boot)         | -49.3 dBFS | -93.3 dB  | -52.1 dB | 0      | 1,433          | 0       |
| A2 chord, REVERB on             | -45.3 dBFS | -95.5 dB  | -57.3 dB | 13     | 489            | 0       |
| B1 C4, REVERB off               | -43.4 dBFS | -100.2 dB | -53.8 dB | 37     | 562            | 0       |
| B2 chord, REVERB off            | -38.7 dBFS | -100.3 dB | -55.9 dB | 19     | 110            | 0       |
| bypassed, A1 C4 (REVERB LED on) | -42.1 dBFS | -102.2 dB | -56.0 dB | 106    | 536            | 0       |

- **No broadband noise, no clipping, no periodic artefact.** The floor between the harmonics is 93-102 dB under the
  peak; the silence is exact zero. The "clicks" are the note's own attack transients (the bypassed run, which has
  no DSP, shows more). The held runs are 12-20 samples at most, as in the dry note; there are more of them because the wet signal is
  quieter and repeats values more often at 16 bits.
- **REVERB on is D2.** A1 is 7.2 dB under the bypassed A1, the same note dry (7.9 dB by `firstnote.py`'s window,
  5.9 dB under B1); the plan predicted 7.6 dB if the dry sound is dropped. With REVERB off the DSP is not heard at all: B1/B2
  are identical, statistic for statistic, in the DRC, the interpreter and the bypassed runs. The wet-only sound has
  a floor 7-9 dB higher than the dry note (the reverb's diffuse tail) and a stereo image (L-R at -2 to +2 dB against
  the dry path's mono). It is quieter and distant, not noisy.
- **Sample-rate conversion is not a factor.** The bridge's stream runs at 44,100 Hz and MAME converts to 48,000
  (`-samplerate` default, the "lofi" resampler): the dry path keeps a floor of -102 dB through it.

### DRC and interpreter (D11): the interpreter drops three frames in four

With REVERB on the interpreter's output is noise: floor -47 dB (DRC: -93), energy above 5 kHz at -25 dB of the total
(DRC: -52 dB), 7,866 runs of held samples in A1 (DRC: 1,433). `frames_tap.lua` (`EXTRA=frames_tap.lua`) counts the frames
the kernel finishes:

| run                         | DSP clock | IOSTAT writes / s | unit 0 return writes / s |
|-----------------------------|-----------|-------------------|--------------------------|
| DRC                         | 60 MHz    | 88,200            | 44,100                   |
| DRC (`clock-scratch.patch`) | 30 MHz    | 45,110            | 22,555                   |
| interpreter                 | 60 MHz    | about 23,600      | about 11,800             |
| interpreter                 | 240 MHz   | about 16,140      | about 8,070              |

The DRC finishes every frame at 60 MHz. At 30 MHz it finishes 22,555 a second, so the kernel's work is about 1,330
cycles a frame against a budget of 1,360 at 60 MHz (with the boot's effects; E3 measures it on the chip). The
interpreter finishes only a quarter of the frames, and fewer with four times the clock. So it is not short of
cycles: it is taking the interrupt late. The code says why (`sharc.cpp` `execute_run`): the interpreter calls
`check_interrupts()` once, at the start of each `execute_run`, and refuses when the PC is in a delay slot. The kernel
masks IRQ0 for the whole unit chain and unmasks it in the delay slot of its loop-back jump (`80A4`), then spins on
`807A: IF EQ JUMP 807A (DB)`, where two of the three PCs are delay slots (`kernel-architecture.md` 5). An IRQ0 that
arrives while masked, or finds the spin in a delay slot, waits for a later `execute_run`; the next tick's edge then
merges with it, and a frame is lost. The DRC tests pending interrupts at block entry, at the loop-back of every
branch and after IMASK/MODE1 writes (`sharcdrc.cpp` `generate_update_cycles`, the jump epilogue), so it takes IRQ0 as
the chip does. The 22% of samples by which the two differed (`notes/sharc-drc-parity/`) is the interpreter's bug, not
the DRC's: the DRC is the faithful mode here, and it is the default.

### Fixes, by cause

| cause                                          | fix                                                                                                                                                                                                                                       | effort |
|------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------|
| live speed below 100% (the "noise")            | run at 100%: measure the speed on Felipe's host first; `-autoframeskip` (91.6% here); find why the window costs 0.66-0.84 s per emulated second (layout render)                                                                           | S-M    |
| the SHARC's share of host time (0.22-0.40 s/s) | only after the above: the DRC is on; its fast registers are off (`DISABLE_FAST_REGISTERS=1`, OVERLAY-GAPS G4), worth measuring                                                                                                            | M      |
| REVERB on drops the dry sound (D2)             | plan S4: keep the dry TG path, add unit 0's return scaled by TOTAL DEPTH; confirm with E2 on the unit                                                                                                                                     | S      |
| the interpreter takes IRQ0 late (D11)          | `sharc.cpp`: test pending interrupts inside the interpreter loop (after each instruction outside delay slots, or after IMASK/MODE1/IRPTL writes), as the DRC does; check with `frames_tap.lua` at 44,100 and the DRC/interpreter md5 pair | S      |
| sample-rate conversion                         | none needed                                                                                                                                                                                                                               | -      |

### Reproducing

```sh
N=notes/dsp-noise-2026-10-21; T=~/compartilhado/tmp/dsp-noise
# EMU60: a folder with the 60 MHz binary (the published one), roms, plugins, the card image
# EMUBYP: the same with a binary built with bypass-scratch.patch applied (BYPASS=1 uses it)
$N/run_passage.sh EMU60 $T/p-drc wav                      # computed, DRC
$N/run_passage.sh EMU60 $T/p-nodrc wav -nodrc             # computed, interpreter
BYPASS=1 $N/run_passage.sh EMUBYP $T/p-byp wav            # computed, bypassed
$N/run_passage.sh EMU60 $T/l-drc live -wavwrite $T/l-drc/run.wav     # what a listener hears, plus the computed
$N/run_passage.sh EMU60 $T/l-drc-novid live -video none              # the ~100% control
EXTRA=$N/frames_tap.lua $N/run_passage.sh EMU60 $T/f-nodrc wav -nodrc
python3 -I $N/wavstats.py $T/p-drc/run.wav
python3 -I $N/firstnote.py $T/p-drc/run.wav $T/l-drc/live.wav
python3 -I $N/livestats.py $T/p-drc/run.wav $T/l-drc/live.wav
```

The recordings are the instrument's own notes, kept in scratch only (`~/compartilhado/tmp/dsp-noise/*/run.wav`,
`live.wav`). `live` mode needs PipeWire's `pw-record`; the default sink may be muted, its monitor is not.
