# KN7000: PMUT, the IC25 sound-control latch and the D/A converter IC311, modelled (2026-11-06)

Closes the driver gap in technics-roms-disasm `kn7000/notes/audio-mute-probes/README.md` section 5 (the
service manual trace, firmware writers and MAME watch are there).  Every result here is **observed in
emulation**; the unit has not been asked.

## What the driver does now (`src/mame/matsushita/kn7000.cpp`)

| part                      | where in the driver                                                            | what it does                                                                                                                                                       |
|---------------------------|--------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| IC311, D/A converter      | `kn7000_dac_device` (tag `dac`), between the DSP bridge and the speakers       | the PCM1738 mode port and the mode bits that act on the output (below)                                                                                             |
| IC25, sound-control latch | `kn7000_state::ic25_w`, mapped at 0x98060000 (byte, write only)                | bit 1 SPSW to the speaker gate; bits 3 / 4 / 5 (DAC.ML = CS, DAC.MC, DAC.MDI) to IC311's mode port on each change; bit 0 USB.WAITM and bit 2 SDMODE kept, not used |
| PMUT                      | the 0x36008004 write handler, bit 2                                            | to the speaker gate                                                                                                                                                |
| speaker gate              | `kn7000_state::speaker_gate_update`                                            | IC311's output gain: -1 while PMUT and SPSW are both 1, else 0 (`set_output_gain`, so the change lands on the sample)                                              |
| save states               | `m_gpio8004`, `m_ic25`; the device's registers, attenuators and shift register | `m_gpio8004` was not saved before; the output gain saves itself with the stream                                                                                    |

**The converter.**  IC311 is printed only as C0FBBK000025 "D/A CONVERTER" (MAIN 3/5, p. 110), but its 28
pin names are the TI (Burr-Brown) **PCM1738**'s, pin for pin: RST 1, ZEROL 2, ZEROR 3, LRCK 4, DATA 5,
BCK 6, SCKI 7, DGND 8, VDD 9, SCKO 10, MDO 11, MDI 12, MC 13, CS 14, MUTE 15, IOUTR- 16, IOUTR+ 17,
AGND1 18, VCOM1 19, VCOM2 20, IREF 21, VCOM3 22, VCC1 23, VCC2 24, IOUTL+ 25, IOUTL- 26, AGND2 27,
VCC3 28 (data sheet SBAS174C, Table 1; the schematic prints SCKI / SCKO as "SCK1" / "SCK0" and MC as
"NC").  The data sheet is dated February 2002, the KN7000's year.  On the board MDO (11) is open and
MUTE (15) is grounded.  The mode port takes 16-bit words MSB first while CS is low, MDI sampled on MC
rising, the word acting when CS rises; bit 15 is read / write, bits 14..8 the register, 7..0 the data.

The firmware's two words (`DacModeInit`, 941 0x4854D152; `DacModeWordWrite` shifts MSB first exactly as
above), decoded by the device (`runs/ic311_log_after.txt`) and by the probe from the bus
(`runs/gates_after.txt`, `DACWORD`):

| word   | register | data | meaning (data sheet)                                                                                                                    |
|--------|----------|------|-----------------------------------------------------------------------------------------------------------------------------------------|
| 0x1220 | 18       | 0x20 | ATLD 0 (attenuators keep 0 dB), FMT 010 = 24-bit standard (right-justified) data, de-emphasis off, soft mute off                        |
| 0x1380 | 19       | 0x80 | REV 1: output phase inverted; ATS 00 (attenuator rate LRCK), OPE 0 (DAC on), SCKO on at full rate, sharp roll-off, zero-detect mute off |

Modelled from the data sheet: the attenuators (registers 16 / 17, loaded while ATLD = 1, 0.5 dB a step,
mute below step 15), soft mute stepping the attenuator one step every 1, 2, 4 or 8 samples (ATS), OPE,
REV, MONO / CHSL and MRST.  Logged and not modelled: the data format (the driver hands the converter
samples, not its serial stream), de-emphasis, roll-off, zero-detect mute, SCKO, filter bypass,
oversampling rate and SRST.  The firmware sets none of the modelled bits but REV.

**Polarity.**  IC311's currents go to the I/V converters IC313 / IC314 and the balanced stage IC315 wired
as the data sheet's Figure 40 (IOUT- to the stage's inverting side, IOUT+ to the other), then through
R339 into IC316's inverting input (R347 47K feedback): an inverting mixer, whose outputs are MIXOUTL /
MIXOUTR.  REV = 1 and IC316 cancel, so MIXOUT carries the samples' own sign.  The driver keeps IC316's
inversion as the sign of the gate's gain, so its output is bit-identical to before (table below).  The
stages after MIXOUT on the FAJ / ASUB boards are not traced for sign.

**Outputs.**  On FAJ 1/2 (p. 120) SUML / SUMR, after C505 / C506, feed bus lines d / e, which go to MAIN
OUT (JK508 / JK509 through IC511, FAJ 2/2, p. 122), and, through the 39K / 100K dividers, the series
FETs Q502 / Q503 (SPSW) to IC506, which drives both the headphone amplifier IC509 and the speakers'
equaliser IC502 / IC503.  The power amplifiers are biased from +15PM, on only while PMUT is high.  So:

| output     | PMUT  | SPSW  |
|------------|-------|-------|
| speakers   | gates | gates |
| headphones | -     | gates |
| MAIN OUT   | -     | -     |

The driver has one stereo output (`lspeaker` / `rspeaker`), taken to be the speakers: both lines gate
it.  Headphones and MAIN OUT have no output of their own in the driver and are not modelled.  The SPSW
switch's gate ramp (R677 1M, C539 0.047 uF: 47 ms) and +15PM's switching are modelled as instant.

IC25's RESET is tied high (R35), so nothing clears it: its power-on content is undefined and the
driver starts it at 0; the firmware writes 0xFF at 0.0 s.

## Siblings

The KN6000 / KN6500 (one `kn6000()` config) have a PCM1728 converter (IC307) and 0x98060000 is their
CN105 unit's HDDCS; the KN2400 / KN2600 converter and sound lines are not traced.  Their configs remove
the `dac` device and route the DSP bridge to the speakers as before, and do not map IC25; their
0x36008004 handler was already separate (KN6000) or keeps no PMUT use (KN2400).  Unchanged, measured by
`run_siblings.sh` (table below).

## Probes

| file               | question it answers                                                                                                                       | run                                                                                                                |
|--------------------|-------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
| `audio_gates.lua`  | does the speaker output follow PMUT, SPSW and the NMI, what words reach IC311 and what the device decoded, with a key held in six windows | via `run_gates.sh`                                                                                                 |
| `run_gates.sh`     | runs `audio_gates.lua` on one build from a fresh run directory with `-wavwrite`, then `gate_windows.py`                                   | `sh run_gates.sh BINARY $TMPDIR/RUNDIR` (893: `SHADOW=0x5000520C sh run_gates.sh BINARY $TMPDIR/RUNDIR -bios v13`) |
| `gate_windows.py`  | RMS / peak of each window of a capture; with a second run, the dB ratio and the largest per-sample difference over the normal windows     | `python3 -I gate_windows.py LOG WAV [LOG_B WAV_B]`                                                                 |
| `sibling_boot.lua` | does a sibling machine boot and sound as before: 25 s, snapshot, exit                                                                     | via `run_siblings.sh`                                                                                              |
| `run_siblings.sh`  | runs `sibling_boot.lua` on kn6000, kn6500, kn2400, kn2600 with two builds, compares snapshot and capture md5                              | `ROMS=~/compartilhado/kn7000-emulator/roms sh run_siblings.sh BUILD_A BUILD_B $TMPDIR/RUNDIR`                      |
| `dac_crops.sh`     | renders the service manual crops the converter identification and output reading above come from, and the data sheet's Figure 40          | `sh dac_crops.sh [MANUAL] [PCM1738_PDF] [OUTDIR]`                                                                  |

`audio_gates.lua` signals: PMUT = bit 2 of the byte written to 0x36008004; SPSW = bit 1 of the byte
written to 0x98060000, the firmware's shadow of it being 0x50005214 in program 941 and 0x5000520C in
893 (`SHADOW=0x5000520C` with `-bios v13`; with 941's address the 893 firmware rewrites SPSW to 1 within
0.4 ms); IC311's words
are reassembled from bits 3 (CS), 4 (MC), 5 (MDI) of the same writes.  W2 forces PMUT low with a
read-modify-write of 0x36008004 (as the firmware's `bclr`), W4 forces SPSW low in the shadow and the
latch (as the M3 0x600009 handler does with a 0).  ROMs `~/compartilhado/technics_romsets`, BIOS v16 =
program 941, SD slot a fresh copy of `technics_roms/media/sdcard_from_real_kn7000.img`, `-sound none
-nothrottle`, visible video.  Captures are 3 channels at 48 kHz; channels 0 / 1 are measured.

## Results (`runs/`)

Builds: before = the overlay at 04d33ed (md5 `8b9865bd2e3849bea134c97315c9781e`, the published binary
until this change), after = this change (md5 `20455440aa8db9739bf9f930e6066dec`); `runs/md5.txt` also
holds the two captures' md5.

`runs/windows_after_vs_before.txt` (A = after, B = before; RMS in 16-bit sample units):

| window          | from s | to s   | after L rms | after R rms | before L rms | before R rms | after / before |
|-----------------|--------|--------|-------------|-------------|--------------|--------------|----------------|
| boot-pmut-low   | 0.050  | 6.628  | 0.0         | 0.0         | 0.0          | 0.0          | n/a            |
| boot-after-pmut | 6.628  | 8.628  | 0.0         | 0.0         | 0.0          | 0.0          | n/a            |
| W1-normal       | 20.100 | 20.900 | 386.9       | 325.8       | 386.9        | 325.8        | +0.000 dB      |
| W2-pmut-low     | 23.100 | 23.900 | 0.0         | 0.0         | 329.2        | 277.1        | -inf           |
| W3-normal       | 26.100 | 26.900 | 389.9       | 326.5       | 389.9        | 326.5        | +0.000 dB      |
| W4-spsw-low     | 29.100 | 29.900 | 0.0         | 0.0         | 386.9        | 325.8        | -inf           |
| W5-normal       | 32.100 | 32.900 | 389.7       | 326.4       | 389.7        | 326.4        | +0.000 dB      |
| W6-before-nmi   | 35.100 | 35.500 | 499.3       | 368.4       | 499.3        | 368.4        | +0.000 dB      |
| W6-after-pmut   | 35.534 | 35.633 | 0.0         | 0.0         | 291.2        | 308.8        | -inf           |

- A note in normal operation is unchanged: the largest per-sample difference over the four normal
  windows is **0** over 268,798 samples (tolerance asked: equal RMS; measured: identical samples).
- The probe sees the failure: the build before plays the key with PMUT forced low (W2), SPSW forced low
  (W4) and after the NMI handler cleared PMUT (W6-after-pmut); the build after is silent in all three
  (peak 0) and the sound is back in the next window (W3, W5).
- Boot: PMUT goes 0 -> 1 at 6.6283 s (`BootPanelResetCheck`) in both builds, but nothing sounds before
  the home screen in either, so the boot windows measure 0 with and without the gate.  That the output
  is silent during boot follows from the gate being closed while PMUT is 0 (W2) and PMUT being 0 from
  0.0000 to 6.6283 s; a capture cannot show it.
- IC311 receives 0x1220 and 0x1380 at 1.1481 / 1.1482 s and nothing else; the device's registers read
  back FF FF 20 80 00 (16..20) at the home screen and at the NMI.
- The parameter 0x600009 = 0 case is reproduced by W4 (its handler's effect forced by the probe); no
  firmware path that sends a 0 was reached.

**Program 893 (BIOS v13)**, `runs/windows_after_vs_before_v13.txt`, `runs/gates_after_v13.txt`: the same
words at 1.1509 / 1.1510 s, PMUT 0 -> 1 at 6.2345 s, and W2, W4 and W6-after-pmut silent after the change
(peak 0) where the build before plays the key (RMS 331.9 / 277.7, 389.9 / 326.6, 291.2 / 308.8).  The
normal windows are not sample-identical under 893, and the build before is not identical to itself
either: two runs of it differ in W5 by -0.005 dB, largest per-sample difference 1,175
(`runs/windows_before_vs_before_v13.txt`), the same figures as after against before; two runs of the
build after are identical (`runs/windows_after_vs_after_v13.txt`).  So under 893 a note's level is
unchanged within the build's own run-to-run spread (0.005 dB in W5, 0.000 dB in W1, W3 and W6).

**Siblings** (`runs/siblings_before_vs_after.txt`, 25 s of emulated time from power-on): kn6000, kn6500,
kn2400 and kn2600 give the same capture md5 and the same snapshot md5 with both builds; the KN6000 /
KN6500 snapshots show their play screen.

`-validate` passes with the build after (exit 0, no output).
