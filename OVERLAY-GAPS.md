# What the overlay does not have yet

**A living list. Keep it current.** Whenever overlay work ports one of these items, finds a new one, or
shows one to be wrong, update this file **in the same commit**: change the item's state, name the commit
and the evidence, and add a line to the history at the bottom. An item is `done` only when the published
folder runs it and the evidence is committed.

It started as the answer to "is there any research work we did not include in the overlay yet?" on
2026-10-19. Four read-only sweeps ran against the overlay at `5e0a58a`:

- the 80 local MAME branches with unmerged Technics commits;
- upstream MAME itself;
- the notes in the research repos (`KN7000`, `technics-roms-disasm`, `technics_roms`, this repo);
- a second pass over the KN7000 and KN5000 findings.

Nothing was built or run in the sweeps, so an item they report is "read from source", not measured,
unless it says otherwise. File and line references are as of `5e0a58a`, and move as the files change.
The five PRs carried on 2026-10-19 (#16517, #16520, #16523, #16524 and the floppy-list rebuild) are not
listed: they are in (`notes/pr-port-2026-10-19/`).

States: `open`, `planned` (sequenced in a plan, not started), `in progress`, `done` (with the commit),
`decision` (needs Felipe's call before any work), `blocked`, `wontfix` (with the reason).

| #   | item                                                   | area               | size         | state       |
|-----|--------------------------------------------------------|--------------------|--------------|-------------|
| G1  | KN6000 expansion: CN105 connector + HD-SX6, PR #16220  | KN6000 driver      | ~230 lines   | done        |
| G2  | Main CPU core fixes upstream has                       | mn10300 core       | ~200 lines   | done        |
| G3  | Effects DSP save state freezes the effects             | KN7000 driver      | trivial      | open        |
| G4  | Effects DSP branch B fixes                             | SHARC core         | small-medium | open        |
| G5  | Effects DSP clock, 60 or 66 MHz                        | KN7000 driver      | one line     | decision    |
| G6  | IC23 battery-backed SRAM (panel memories) as NVRAM     | KN7000 driver      | small        | done        |
| G7  | 0x90000000-0x97FFFFFF is the uncached view of 0x5xxx   | KN7000 driver      | small        | in progress |
| G8  | Interrupt vectors through IVAR, not per-BIOS addresses | mn10300 core       | small-medium | open        |
| G9  | Real power-on path from IC18, and the flash updater    | KN7000 driver      | small/large  | open        |
| G10 | CS5 mirrors and open-bus reads                         | KN7000 driver      | small        | open        |
| G11 | IC21 custom data probably halfword-swapped             | KN7000 driver      | small        | open        |
| G12 | IC414 NO_DUMP, KN6000/6500 Initial Data preload        | ROM records        | small        | open        |
| G13 | Voices on the real wave ROMs                           | tone generator     | large        | in progress |
| G14 | SD SPI with the card deselected reads 0x00             | KN7000 driver      | small        | open        |
| G15 | Smaller KN7000 items                                   | KN7000 driver      | small        | open        |
| G16 | KN5000 branch work                                     | KN5000             | mixed        | open        |
| G17 | KN5000 research findings                               | KN5000             | mixed        | open        |
| G18 | Notes and comments that newer findings contradict      | docs               | small        | open        |
| G19 | Effects DSP bypass switch (noisy sound)                | KN7000 driver      | small        | planned     |
| G20 | Probe the DSP and TG on the real unit via .CNV         | tools / RE         | medium-large | in progress |
| G21 | SD sub-CPU IC401: SDMODE switch, untried read commands | KN7000 driver / RE | medium       | open        |

## Work already written on branches, not in the overlay

### G1. KN6000 expansion, PR #16220 (v5) — done 2026-10-19

**Done** (`c2d6666`): `kn7000-base` reverts the August draft and carries v5's four commits (`892c985aa55`,
`722f483beca`..`81132bf65c8`); the overlay's `kn7000.cpp` fits CN105 on kn6000/kn6500; the publish step ships
the card's firmware as `roms/hdsx6/hd-sx6_v1_1_rev3.bin`. Run it with
`./run.sh kn6000 -window -exp hdsx6 -harddisk2 disk.chd` (`harddisk1` is the SD slot the overlay's KN6000
inherits). From the published folder both machines send IDENTIFY, read the 512-word block and draw the
card's splash at 6.0 s (2.6 s later than upstream's KN6000; why is not investigated). Evidence and recipe:
`notes/hdsx6-port-2026-10-19/`.

What the sweep found:


Branch `technics-kn6000-expansion-v5` (`d497bed5caf`), four commits: the CN105 connector
(`57ea86e858a`, `kn6000_expansion.{h,cpp}`), the HD-SX3 card (`b7004fd1726`), its rename to the HD-SX6
(`d497bed5caf`, `hdsx6.{h,cpp}`) and the atahle SET FEATURES 0x55 fix (`745ebc0f9c7`, 2 lines).

- The connector maps the card's two windows: ISOROM at 0x97800000-0x97FFFFFF (a 2 MiB window repeated
  4 times) and HDDCS at 0x98060000.
- The HD-SX6 holds its firmware in a real flash device, 1 MiB of SRAM and an ATA interface at HDDCS
  +0x10/+0x20. The PR's runs show the board code running from first boot, its own splash at
  3.15-3.30 s, then IDENTIFY and READ MULTIPLE (`KN7000/tools/mame-pr-planning/kn6000-expansion-pr/`).
- Without the atahle fix the firmware gets an abort and never identifies the drive (`runs/r5-ata.txt`).
- `kn7000-base` held the August draft instead (`473fb321714`..`599f077cc6a`): the wrong connector
  (CN106), no HDDCS window, no ATA, and RAM created too late. Nothing installed it.
- Not modelled on any branch: HDDINT (IRQ1) and PP.INT (IRQ4); the HD-SX6's USB, parallel port and
  separate-output DACs; the upper half of the flash, which A20 hides. Format, save and load were never
  exercised, because the KN6000 table ROMs (IC13/IC14) are undumped.

### G2. Main CPU core fixes upstream has and the overlay lacks — done 2026-10-19

**Done** (`faee3de`): every item below is ported into the overlay's `mn10300.cpp`, as upstream wrote it. Before and after
the port, all 8 machine/BIOS cases (kn7000 v16, v15, v13, sp7001; kn6000; kn6500; kn2400; kn2600) draw
identical screens at 9 times through 45 s, and the gate's audio oracle is unchanged (`bd02a9c1`). No boot
executes a newly decoded opcode; each divides by zero twice in its library, which the old core only logged.
Evidence and recipe: `notes/core-port-2026-10-19/`.

What the sweep found:


The overlay replaces upstream's `mn10300.cpp`. Upstream's merged core (#16250, #16394) fixed these after
review; the overlay never took them. All are in the instruction decoder, the timer, save state or the
serial port, so none conflicts with the overlay's own interrupt model (A1.1 in
`notes/overlay-upstream-sync/UNSUBMITTED-2026-10-18.md`).

- **Opcodes skipped as no-ops** (B.2 in the UNSUBMITTED inventory), so their stores never happened:
  - `mov`/`movbu`/`movhu` to and from absolute 16-bit addresses (0x01-0x0F, 0x30-0x3B);
  - FA 80-8C `mov Am,(abs16)`;
  - FA F0/F4/F8 `bset`/`bclr`/`btst imm8,(d8,An)`;
  - `mulqu imm` (F9/FB/FD, op2 0x14-0x17).
- **Flags that disagree with the GNU simulator** (A1.5):
  - `addc`/`subc` must keep Z only if it was already set;
  - `bset`/`bclr`/`btst` also set N and clear C and V;
  - `mul`/`mulu` clear C and V;
  - `rol`/`ror` clear V, and op2 0x88 and up is illegal;
  - `sat16`/`sat24` set Z and N;
  - `getx` sets Z and N from MDRQ and clears C and V. The overlay deliberately left the flags alone,
    citing the ISR context save; the hardware pushes PSW before the handler runs.
  - `bsch` (F6 7x): upstream takes the AM33 form (search below bit Dn, C if found); the overlay's
    16-bit search was empirical. Upstream's review found the firmware's calls give the same results.
- **`div`/`divu`**: a zero divisor or a quotient that does not fit sets V. The overlay could crash the
  host with SIGFPE on INT64_MIN / -1.
- **Timer 5 count read** (`tm45_count_r`): `(base + 1) * remaining-attoseconds` overflows 64 bits for any
  reload above about 6074 and reads back out of order. Whether any firmware reads it is not known.
- **Timer 5 base write** ignores the byte mask.
- **`m_irq_level`** is not in save state, though `check_irq` reads it every instruction.
- **SIO receive** ignores the receiver-enable bit (config bit 14), and reset does not tell the peer the
  receiver went off (upstream review round 3).
- Also differs, found while porting: `udf20 imm` (F9/FB/FD op2 0x08-0x0B) ran as `mulq`; setlb's LAR
  held the loop top instead of the loop top + 4.
- None of the skipped opcodes had shown up on the KN7000 boot or demo paths
  (`notes/mn10300-udf-instructions-unimplemented.md`). KN6000, KN2400, floppy and SD paths were not
  measured.

### G3. Effects DSP save state — open

The overlay saves only `m_dsp_index` and `m_dsp_dl_words` of the DSP host-boot state. After a state
load `m_dsp_running` is false, so `dsp_audio_tick` returns before raising IRQ0 and the effects freeze.
Branch B (`technics-kn7000-dsp`) saves all of it. A real overlay bug; trivial fix.

### G4. Effects DSP branch B (`technics-kn7000-dsp`, `a1c1fe1db93`) — open

All SHARC/DSP-side; none touches the MN10300 interrupt model.

- **SPORT DMA engine** (`e0c4a27c956`; `sharc.cpp/.h`, driver `dsp_audio_tick`): eight serial-port DMA
  channels with chained transfer blocks and per-slot `sport_tx`/`sport_rx` callbacks; IOP registers
  read back. The overlay only caches each block's buffer address, IOP reads return 0, and the driver
  reads and writes fixed DSP addresses (0xC342…/0xC362…). Medium: take B's SHARC hunks, rewrite the
  tick to feed slots. The audio oracle would need a re-baseline. **The effects do read an IOP register
  back** (answered 2026-10-20 by pass 7 on the unit, `notes/dsp-probe-2026-10-20/README.md`): effects
  58-61 save I3 to MSGR2 and restore it with `I3 = DM(0x0A)`. In the overlay that read gives 0, so the
  ring-3 effects run on a zero pointer and the kernel's ring-3 scrub zeroes DM 0xC329 (a SPORT TCB). On
  the chip the TCB survives and MSGR2 moves. **Done for the MSGR registers** (2026-10-20): the kernel's
  reads of MSGR0-7 return the stored value; the oracle moved only through that (attribution run) and was
  re-baselined. The other IOP registers still read 0 to the kernel (several hold status bits not
  modelled). FLAG3 is driven too (2026-10-20): high on every other frame, as pass 8 measured, so ring 3
  scrolls at half rate.
- **MODE1.ALUSAT read at run time in the recompiler** (`38f4bca2b3a`). The overlay compiles it in
  (`b1028bd`) and only invalidates on immediate MODE1 writes. Latent for this firmware (set once,
  RTI restores the same MODE1). Trade-off: `b1028bd` credits this, with the 66 MHz clock, for the
  kernel finishing 44,100 frames/s. Needs a speed measurement.
- **Multiplier flags** (`586094eb3db`): MN from bit 63 in fractional forms; MV/MU in the recompiler's
  single-function MAC. The overlay's own comment says the reverb is bit-identical either way. Trivial.
- **Dual add/subtract**: the add half's AN/AZ corrected after saturation. Trivial.
- **Recompiler scratch registers I8/I9 instead of I6/I7.** Latent while `DISABLE_FAST_REGISTERS=1`.
  Trivial.
- **Converging fully onto B (A1.14) would lose:** the DSP self-test handshake on group 0x17, pitch from
  the voice record and the one-shot mode (A2.3), the wave pack, flushing the bridge rings on reset, and
  the 66 MHz frame-rate result.

### G5. Effects DSP clock — decision

The overlay runs the ADSP-21065L at 66 MHz (`kn7000.cpp` near 2287, `b1028bd`, to stop frame
overruns); the part is marked S21065LKS240, a 60 MHz grade, and the overlay's own comment says ~60.
Branch B uses 60. Same trade-off as the ALUSAT item in G4.

### G16. KN5000 branch work — open

- **HD-AE5000 parallel port** (`kn5000_pr6_hdae5000` `554e89a0542`): ports A, B, C with A floating at
  0xFF, saved. The overlay's PPI callbacks are commented out (`hdae5000.cpp:139-146`). Small.
- **HD-AE5000 hard disk slot empty by default** (same branch, `ba066e6eb5f`): with a default `hdd` and
  no image the drive-ready timeout hangs the boot for minutes. One word, but an empty default means
  naming the disk on the command line: **decision**.
- **TechManager5000 PC link** (`kn5000_research_techmanager` `0681c0f0009`): the KN5000 driver as a
  device wrapped as a parallel-port peripheral. Large: redo the refactor on the 1,956-line overlay
  driver.
- **Real TLCS-900 instruction timings** (`tlcs900-real-timings` `b0b13e1eb20`, parked): 185 cycle
  counts to the databook and every prescaler shift lowered by one. Medium; 11 of 15 table hunks fail
  against upstream's #16480 table, and it halves the CPUs' speed relative to their timers, a risk for
  the KN5000 inter-CPU handshake.
- **Key-map read bound** (B.20; `c3f95c18ece` / `8da4107905a`): 64-bit `ptr_a + 4 + 0xff`. Only a
  crafted ROM overruns. Trivial.
- **Faster period detection** (`3a603a8e8a6` / `0270605b231`): speed only. Trivial.
- **64-bit sample position and loop counter** (`110de5031e7` / `1a612013fd6`): the overlay's 16.16
  position would wrap past 65,535 samples; the longest IC307 recording is 37,520
  (`notes/overlay-gaps/ic307_chunk_lengths.py`). Matters once IC304-306 are dumped. Small.
- **`tlcs900-prescaler-per-device` `08638c7d908`**: no effect on the overlay's machines (deliberate
  divergence A1.7). The branch itself has a defect: its `tmp95c061.cpp:697` comment says the TMP95C063
  is left for later, yet the same commit changes it; and it is 484 commits behind.

## Research findings the overlay does not reflect yet

### G6. IC23, the 256 KB battery-backed SRAM at 0x44000000 — done 2026-10-20

**Done** (`notes/ic23-nvram-2026-10-20/`): IC23 is a 256 KB nvram device on the KN7000, repeating every 256 KB
through 0x44000000 and 0x84000000; the CPU core takes the NMI; a POWER OFF machine control runs the firmware's
power-fail handler (which stamps IC23's checksum) and then exits; 0x90000000-0x903FFFFF became the work-RAM view
the handler's RAM stub needs (part of G7). Panel memories survive a restart **when the session ends with POWER
OFF**; after a plain exit following any change, the next boot resets everything to factory, panel memories
included. The checksum covers only the 0x7A0-byte header, so a damaged byte in the PANEL MEMORY store goes
unnoticed and stays (`check_ic23.sh`). Today's Another World SP7001 build, run once under this model, overwrote
1,945 header bytes and 65,676 panel-memory bytes, hung in its loader (its own data aliases through the repeat),
and POWER OFF then stamped the damage valid (`aw_ic23_check.sh`). The KN6000/KN6500/KN2400 keep the placeholder (their backup SRAM is not
identified). **Confirmed on the unit on 2026-10-20** (SURVEY2, pass 5): IC23 repeats every 256 KB, so the Another
World hazard is real. Felipe's own IC23 boots in this emulator (`-bios v13`, `nvram/kn7000_4/ic23`) without a
factory reset.

What was known before:


`technics-roms-disasm/kn7000/tools/cnv_romdump/README.md:149`; the service SRAM test walks exactly 256 KB.
The overlay maps 16 MB of plain RAM there with no NVRAM (`kn7000.cpp:884-885`), so panel memories are
lost on every restart. Small, and the most noticeable item here.

- The firmware's `BackupSramTest` (0x484A0055) walks exactly 256 KB from 0x44000000, and the region carries a
  one's-complement checksum (`SumU32Words`, 0x484D78A6) (`technics-roms-disasm/kn7000/kn7000_manual.sym`).
  Whether the chip repeats across the rest of the 16 MB window has not been measured on the unit; a read-only
  dumper pass over 0x44000000 would answer it and back up Felipe's settings at the same time (2026-10-20).
- **Another World depends on today's wrong model.** Both of its KN7000 builds (`kn5000-anotherworld/kn7000`,
  the SP7001 ride-along and AW.CNV) keep their VM state and page buffers at 0x44050000-0x4413FFFF
  (`src/vm.inc:43-73`, `src/platform.inc:51-60`, which calls the window "scratch the firmware does not use").
  On the real unit that is IC23, so the game would overwrite the panel memories or crash. Modelling IC23
  properly here will make the game fail in the emulator, which is what it would do on the instrument.

### G7. 0x90000000-0x97FFFFFF is the uncached view of 0x50000000-0x57FFFFFF — in progress

Partly done 2026-10-20 with G6: on the KN7000, 0x90000000-0x903FFFFF is now the work-RAM view, as on the KN2400,
because the NMI's RAM stub is written there. The rest of the window (the IC21 and IC19 views at 0x96800000 and
0x97800000, the expansion windows) is still the separate share, and the KN6000/KN6500 keep it whole.

The overlay maps it as one 128 MB "vram" share that nothing reads (`kn7000.cpp:850`); the work-RAM alias
is enabled only for the KN2400.

- The interrupt stubs written through 0x90000000 never reach 0x50000000.
- The updater's expansion windows 0x96000000/0x97000000 are RAM.
- The service ROM test (0x4849FD9E, called from `MainRomTestFunc`) sums 2 MB at 0x97800000 as
  little-endian 16-bit words and compares with 0x21D8. IC19's sum is exactly 0x21D8
  (`notes/overlay-gaps/ic19_rom_test_sum.py`), so that is IC19's test read through the uncached view; it
  also confirms the dump's byte order. In the overlay that row fails (error 4).
- On the KN6000/KN6500, 0x97800000 is CN105's ISOROM window (G1), not a mirror.
- Small.

### G8. Interrupt vectors through IVAR, not per-BIOS addresses — open

The program clears IVAR0..6 (0x20000000-0x20000018) at 0x484100A3, right after setting 0x20000070
bit 7. Its only stubs are RAM+0 = `jmp 0x4C03DE26` and RAM+6 = `jmp 0x484D77CF`
(`technics-roms-disasm/kn7000/notes/work-ram-map.md:110-111`). No literal 0x4C03DDA0, the "quick"
vector the overlay uses, occurs anywhere in the 941 image (checked as a 32-bit literal only).

- The overlay sends device levels to the quick handler and level 6 to the scheduler, per BIOS
  (`kn7000_bios_info`). It works (`notes/pr-port-2026-10-19/`), but it is not the hardware.
- The NMI keeps entering at 0x40000008 and is forwarded to RAM+6, which settles the "+6 vs +8" loose
  end. Data reads of 0x40000000 after boot still return IC18, so bit 7 of 0x20000070 moves only the
  maskable vector base, not the CS0 bus. What the bit actually does is undetermined.
- Upstream's core already models IVAR (`mn10300.cpp:56,104,366`) and its driver calls
  `set_vector_base(0x50000000)` (`kn7000.cpp:889-890`). Porting it retires the quick/sched columns of
  `kn7000_bios_info`. Small to medium. Pairs naturally with G7.

### G9. Real power-on path — open

The CPU really starts in IC18's boot code: 0x40000000 is `jmp 0x40000594`; 0x40000008 is
`mov 0x50000006,a0 ; jmp (a0)`; the init at 0x400005C5 is byte-identical to the program flash's own reset
code at 0x4840FF7E (`technics_roms/roms/kn7000/real_dump_v1.3_b893/README.md:141-153`). The overlay
hard-codes PC 0x48400000 and SP 0x50021CF8 (`mn10300.cpp:200-207`).

- A normal boot loses nothing, because the program repeats the init. Moving the reset PC is small.
- What is missing is the power-on flash updater (the device switch at 0x4000A307). It also needs IC16/IC17
  as flash devices behind 0x88000000/0x88400000 and the CS0 write window at 0x80000000/0x81000000. Large.

### G10. CS5 mirrors and open-bus reads — open

From the ROM survey (`technics_roms/roms/kn7000/real_dump_v1.3_b893/README.md:98-108`):

- IC21 answers at 0x54800000 (2 MB, 4 times) and so at 0x56800000; IC19 answers at 0x55800000.
- 0x40800000-0x40FFFFFF, 0x54000000-0x547FFFFF and 0x55000000-0x557FFFFF are open bus, about 99% 0xFF.
- The overlay maps none of these: 0x56800000 reads 0 (`kn7000.cpp:939`), unmapped space reads 0, and the
  IC21 mirrors at 0x96A00000-0x96FFFFFF are missing.
- The expansion windows 0x41000000, 0x41800000, 0x56000000 and 0x57000000 are empty slots in the overlay,
  consistent with the research, but they read 0x00. **Measured 2026-10-20** (SURVEY2, pass 5, 64 KB of each):
  an empty slot reads 99.9% 0xFF, with a few residue bytes at the start (`5A F8 5A F8 5A ...`). The same run
  read IC21 at 0x56800000 byte for byte, and the library at 0x4C000000 as program flash from 0x487B76B1. The boot ROM updater
  writes through 0x96000000/0x97000000 (and 0x81000000), which the "zero stores" scan did not cover.
- Impact low: the firmware only names 0x54E00000/0x54E10000, and its rhythm probe matches 0x40010000
  first. Small.

### G11. IC21 custom data probably halfword-swapped — open

The overlay uses `ROM_REGION16_BE` and loads `ctmini` with a plain load. Upstream's round-6 probe
(`research-scratch/kn7000-pr16250-fixes/probe_customdata_order.lua`) read `wSni gnA diJev` for "Swing And
Jive" with that region type through the same `intelfsh` path. The overlay already word-swaps the other
three Initial Data files (`ROM_GROUPWORD|ROM_REVERSE`), which fits the same cause; its comment claims the
opposite. Fix: a byte-wide region, drop the REVERSE flags, delete the stale `nvram/*/customflash`.
Not run in the overlay.

### G12. IC414 NO_DUMP and the KN6000/6500 Initial Data preload — open

The remainder of B.6 in the UNSUBMITTED inventory: upstream has a `NO_DUMP` record for the SD sub-CPU
IC414 (`c3fbkd000162`, unreachable from the main CPU) and a `custom_data` region for the KN6000/KN6500
(`01ctmini.ic18`, BAD_DUMP, CRC f108e4c7). The overlay has neither. Small.

### G13. Voices on the real wave ROMs — in progress (decoded and built, not published)

Felipe asked for this on 2026-10-20 (KN7000 only; the other machines keep a placeholder). Plan:
`notes/PLAN-2026-10-20-sound-and-hardware-probes.md`, step 3. Decoded offline the same day, with no
real-unit run; evidence and scripts: `notes/g13-waves-2026-10-20/README.md`.

- **Sample select.** Each TG plays its own ROM pair (0x98050000: IC203/IC204; 0x98040000: IC207/IC208).
  The firmware writes a 20-bit select to plane 0x1C (the old "aux word"; index nibble = bits 19:16):
  bits 19:12 the ROM page, 11:0 the entry of that page's directory. Each 1 Mi-word page starts with
  its own directory {record, P, start/16, -}; P holds the pitch exponent E, the 8-bit flag and the
  loop granule; the record holds the segments and the loop flags. Nothing about addresses or loops
  crosses the bus.
- **Pitch.** rate = 2^((pitch18 - 0x1E200)/0x3000 + E - 9) x C7/44100. With the select rule it puts
  478 of 556 traced voices at the firmware's own note; the rest are footage and noise layers whose
  note is not the key (`pitchcheck.py`).
- **The driver's strap was wrong.** 0x98070000 bits 11:10 gave hardware subtype 5, under which the
  firmware remaps every wave page onto the expansion range and assigns voices to the TGs by a table:
  none of 488 traced selects named an internal sample. The driver reported subtype 1 for the
  KN7000 (subtypes 1 and 2 behave alike in the firmware), and every voice lands on its own pair.
  Since pass 9 read Felipe's unit (`0xF8F7`, subtype 2) it reports that halfword, live bits aside.
- **Built** on the build tree (binary md5 `ed65537d`), KN7000 only; without the four ROM regions the
  voices keep the synthetic pack. Gate on that binary: 16 passed, 1 skipped, 1 failed: the KN7000
  audio oracle, now `dbe3683b25d0e26f823ddbb1fa78bb56` (the held C4 at 262.31 Hz, +4.5 cents, 3.4 dB
  louder, no clipping; README "The gate, the audio oracle, the boot"). `ab_boot.sh` against the
  published binary: all nine snapshots identical for the four KN7000 BIOSes, kn6000, kn6500, kn2400
  and kn2600. Not published, `ORACLE_MD5` not re-baselined: both wait for review.
- **Open**: the 8-bit sample gain law, fitted as 3 dB per code step (a line-out recording of STRINGS would settle it);
  the split lists and the post-loop data are not modelled.

### G14. SD SPI with the card deselected — open

Upstream returns 0xFF and samples per bit; the overlay builds the byte from MISO callbacks, which gave
0x00 in the same measurement. Driver-side, small.

### G15. Smaller KN7000 items — open

From the sweep, not re-checked:

- The wave test port masks the bank to 0x1FF (`kn7000.cpp:1041`), but the expansion-board variant uses
  banks 0x400 and up.
- The IC21 file name is `kn7000_custom_data.rom` where upstream uses `01ctmini.ic21`.
- The KN2400 "separate table ROM" comment (`kn7000.cpp:2626-2631`) disagrees with upstream's schematic
  notes.
- Release years differ (overlay kn6000 2000, kn2400 1998; upstream 1999, 2000); the 2026-09-23 review
  found no source for the overlay's values.
- kn6500 is marked NO_SOUND while it plays a sine; branch A2 marks it IMPERFECT_SOUND.

### G17. KN5000 research findings — open

- **Fitting the HD-AE5000 probably hangs the boot.** The overlay returns PE.0 = 0 when the card is fitted
  (`kn5000.cpp:1458`); the firmware then calls `HDAE5000_Parport_Setup`, which goes on to the factory
  reflash path and fails against the `.rom()` table data. Traced in the code, never run. Small.
- **The ATA soft reset is dropped.** The card writes 0x130020; the overlay sends that to CS1 register 0,
  and its comment puts device control at 0x13002C (`hdae5000.cpp:113-115`). Small.
- **The main CPU's A/D converter is not emulated** (`tlcs900_handle_ad()` is empty, `tmp94c241.cpp:1455`),
  but the firmware reads ADREG04H/15H. Medium.
- **Two flash chips are still ROM:** the table data at 0x800000 and the HD-AE5000's IC4. Medium.
- **The uPD6383 decoder only half-applied the store-gate fix** (`upd6383d.h:814-815`). Small.
- **Percussion is silent by default** (`m_handoff_ctrl = false`, `kn5000_tonegen.h:447`); the overlay's own
  note recommends flipping it: **decision**.
- Also: the DSP1 latch keeps only 8 bits; sub-CPU port writes are not wired; the 0x100004/0x110002 holes;
  no way to select region 4; the data-wheel clamp should be ±16.
- `tmp94c241.h:126-131` still describes the /INT0 re-assertion the overlay removed.

### G19. Effects DSP bypass switch — planned

The overlay's KN7000 sound is very noisy, and the DSP is the prime suspect. Felipe wants it off for now without
losing the code: a machine-configuration switch (Bypassed by default, Emulated for DSP research) that keeps
the SHARC halted, so the bridge passes the tone generator through. The gate keeps a DSP-path oracle with the
switch on. Plan step 1.

### G20. Probe the DSP (and the tone generators) on the real unit — in progress

Started 2026-10-20. Emulator side done: the 21065L keeps an IOP register file, host reads return it, host
writes land in it, and an external-port transmit DMA hands internal memory back through EPB0
(`notes/dsp-probe-2026-10-20/`). SYSCON reads back what the firmware wrote (`0x410` after boot, packed per its
HBW bits), and DMAC0's FS bits show EPB0 full while a readback has words, so the phase-2 probe runs in MAME
without test-side stand-ins. The probe builds themselves are in `technics-roms-disasm`
`kn7000/tools/cnv_romdump/` (releases `2026-10-20-dspprobe`, pass 6, and `2026-10-20-dspmem`, pass 7).

**Pass 6 ran on the unit (2026-10-20).** The set-up matches the emulator's (SYSCON `0x410`, chain pointers, SPORT
control bits). The chip also shows state the emulator lacks: DMASTAT `0x33F`, SYSTAT, IOSTAT, the STCTLx status bits,
IOCTL bits 31/15 reading 0, MSGR3 `0`, the rings' positions (`notes/dsp-probe-2026-10-20/README.md`, "What the chip
said"). The timers are unused; the SPORT counts are frame-locked to the firmware's handshake. After pass 6 the frame rate
was still open: about 22.5 kHz, or 41.4 kHz or more (pass 8 settled it, below). Pass 7 ran (the downloaded DSP code matches;
see G4 for the bug it found). Pass 8 (cnv_romdump `releases/2026-10-20-dsprate/`) times the handshakes with the
MN10300's timer 4 to settle the rate. It showed two emulator gaps that keep it from measuring anything in MAME:
- TM4 was not modelled (the core modelled TM5 only; the 1 kHz tick came from a driver timer), so TM4BC read 0;
- the group-0x17 handshake was answered at once instead of once per DSP frame.

**Pass 8 ran on the unit (2026-10-20): verdict (b).** One handshake per DSP frame, every 22.682 us of the firmware's
tick: 44.1 kHz nominal. FLAG3 is high on every other frame. All three are now modelled for the KN7000: TM4 drives
its 1 kHz tick, the handshake comes once per frame, FLAG3 alternates. Pass 8 in MAME gives verdict (b) at
44,100.0 Hz (`notes/dsp-probe-2026-10-20/README.md`, "The unit's timing in the emulator"). The SPORT DMA registers
are live too (2026-10-20, "The SPORT DMA registers, live"): DMASTAT `0x33F`, the eight rings' indexes and counts and
STCTL1 read as on the unit; the phase check in MAME finds the unit's ring position. Not modelled: STCTL0's sticky
start-up underflow (TUVF_A), and the transfers themselves (the driver still reads and writes fixed ring slots).

The .CNV route can run probes on Felipe's unit and log to the SD card: read back the SHARC's memory and IOP
registers through the host port, its frame rate, the group-0x17 handshake; for the TG, only what offline
decoding leaves open. Emulator first on `-bios v13`, same probe files from MAME and the unit, compared byte for
byte. Volatile I/O writes only. Plan steps 4-6; it feeds G3, G4, G5 and G13.

### G21. IC401, the SD sub-CPU: the SDMODE switch and the commands nobody sends — open

From the 2026-10-20 study of dumping the SD and USB processors (`research-scratch/sdusb-dump-viability/`,
service manual p.116, p.118). **No software route to IC414 (IC401's program flash), IC403 (its EEPROM) or the USB
MCUs IC407/IC408 is known.** The main CPU can reset IC401 (SD PON, `0x9CC00009` bit 1, through C476 to its RST) but
not set its MODE pin; IC414 and IC403 sit on IC401's private bus; both USB MCUs have CNVSS grounded and no
main-CPU reset line. The hardware routes (clip or reader on IC414/IC403 with IC401 held in reset) are for when
the unit is opened; the parts probably hold SD-Jukebox CPRM keys, so keep any dump private.

- **The one software lead:** IC401's command dispatcher handles letters the firmware never sends: 0x41 (block
  read), 0x48, 0x49, 0x4D, 0x4E (variable-length reads). Never 0x44 (block write) or 0x50-0x7F. Emulator first.
- **What the overlay gets wrong:** `0x98060000` bit 2 is SDMODE, which switches the card between the main CPU's
  SPI (1) and IC402's native bus with the main CPU talking to IC401 (0). `cpsd_mbx_write` shifts every byte into
  the card model whatever SDMODE says, so the firmware's IC401 frames (0x40, 0x42, 0x45, 0x7C, playback control)
  hit the emulated card. A stub IC401 with the SD.BUSY handshake (`0x9CC00009` bit 0) and SDMODE routing would
  model the SD-AUDIO path and give the probe something to be debugged against.
- **The first, harmless real-unit step:** after an SD-AUDIO session, a .CNV saves the RAM the firmware fills from
  IC401's replies (0x5016066C-0x5016068F, 0x50093400-0x50093497, 0x5008291C-0x5008291F, 0x50007EFC): the first
  bytes ever seen from IC401, possibly a version string.

## Notes and comments that newer findings contradict

### G18 — open

- **Reset target** "jmp 0x48407EFF" in `kn7000.cpp:83,824`, `mn10300.cpp:203`,
  `notes/FINDINGS-kn5000-splash-restored.md:87`, `notes/rom-backup-and-update-format.md:98,214`,
  `notes/sound-subsystem-plan.md:567` and `tools/interleave_roms.py:20,70`. The CPU sees
  `jmp 0x4840FF7E`. Commit `142655e` "corrected" the right value into a wrong one.
  `technics-roms-disasm/kn7000/src/program.s:18` and `notes/irq-vector-probes/README.md:191` have it
  right.
- **`tools/interleave_roms.py`** weaves the two chips byte by byte instead of in 16-bit halves (the even
  half starts `dc 7e 00 cb`, the odd half `ff 00 cb cb`), so its output is wrong for any use.
- **`notes/FINDINGS-updater-location-2026-08-09.md`**: `:22` H5 "which device is UNDECIDED" is answered
  (IC18's boot ROM); `:84-86` "the only part nobody has read" (the whole table flash was read in pass 1);
  `:115-116` reset PC "never checked" (it is 0x40000000). No correction banner.
- **`notes/table-rom-structure.md`**: the custom chip as IC18/IC20 at 0x56000000 (`:36-37,50-54`), the
  1Y1 quadrant / 0x54800000 unconnected (`:63-65,77`), nothing in CS0 (`:74-76`),
  0x56000000/0x57000000 as custom flash and IC21, IC19 as 8 MB (`:79-81`), the rhythm resource's home
  (`:87-105`): all superseded by `technics_roms/roms/kn7000/real_dump_v1.3_b893/README.md:154`. `:39`
  gives IC21 as 32 Mbit; the survey shows a 2 MB image and the driver models 16 Mbit (undetermined).
- **`notes/HARDWARE-QUESTIONS-PENDING-FELIPE.md`** `:217-219` and `notes/irq-vector-probes/README.md:208-209`
  say the program flash answers 0x40000000 at reset; it is IC18. The "+6 loose end" (`:243-246`,
  README `:238-241`) is explained (G8). README `:233-235` says the driver uses `set_vector_base`: true of
  upstream only.
- **`notes/FINDINGS-expansion-buses-and-code-exec.md:177-189`**: the 0x97800000 checksum is IC19's ROM
  test (G7), not an XAPR/HD-SX3 fossil.
- **0x56000000/0x57000000 called custom/factory flash**: `notes/sound-bank-classes.md:43-44`,
  `notes/initial-data-disk-and-custom-flash.md:107,138,144`, `notes/rom-backup-and-update-format.md:201-202`.
- **`notes/FINDINGS-kn7000-debug-screens.md:134`**: RHYTHM/PICTURE "read 0"; they read 33 and 7
  (`notes/pr-port-2026-10-19/`).
- **No firmware-mediated dump**: `notes/FINDINGS-program-rom-version-and-dump-paths.md:16-23` and
  `notes/HANDOFF-rom-archival-and-external-data.md:41` say none exists; the STYLE CONVERT dumper made one
  on 2026-10-19. `HANDOFF…:47` also calls IC18/19 "table mask-ROM".
- **Stale `kn7000.cpp` comments**: `:55-57,86,908-911,2448-2450` (the 0x4C000000 library or boot ROM as
  "undumped"), `:61-62` (0x8C/0x90 as video windows), `:878-879` (0x44000000 "TODO identify": IC23),
  `:2494-2495` ("nothing written below 0x20000"). `kn7000_tonegen.h:19,45,82` and `kn_tonegen.h:173` said
  the wave ROMs are undumped (corrected with G13); `kn_tonegen.h:93` has main and sub swapped.
- **KN5000 notes**, about 20, the main ones: `kn5000-port-census-2026-09-03.md:275-277` (ADREG never read),
  `:104-170`, `:213-225`; the kn5000-30 revert (done in `83264d1`); IC14 "must be re-dumped";
  `kn5000-dsp-reverb.md:216-221` (reverb lengths at half their value); the 48 kHz assumption.
- **SD board** (2026-10-20, from the service manual, `research-scratch/sdusb-dump-viability/`):
  `notes/sd-card-emulation-plan.md:4-21` (a "CPSD" panel sub-CPU on SIO channel 0, mask-ROM claims: there is no
  SD panel CPU; the SD PLAY/VOL board is switches and LEDs on the LCD controller's GPIO at 0x9CC00008);
  `kn7000.cpp` near 735 ("LEDs are not CPU outputs": the firmware sets 0x40/0xC0 at 0x9CC00008); the names of the
  `0x9CC00009` and `0x98060000` bits in `technics-roms-disasm/kn7000/kn7000_manual.sym` ~384-405, ~484-501 (bit 1
  is SD PON, which also resets IC401; 0x98060000 bit 2 is SDMODE).
- **Outside the overlay**: `technics_roms/…/ic19-analysis/README.md`,
  `technics-roms-disasm/kn7000/src/picture.s:124` and `tools/gen_picture_s.py:92` say SOFT VERSION shows
  PICTURE. It is a DEBUG TOOLS row; the overlay's comment at `kn7000.cpp:1862` is right.

## Nothing to port (checked)

- **Tone generator branch A2** (`technics-kn7000-tonegen` `7f7d1857e20`): a strict subset of the overlay.
- **FDC IRQ2 branches** (`technics-kn-fdc-irq2` `88ab985e31b`, v3 `9b24e40b0e7`, v4 `803d5042f98`): replaced
  by upstream #16394; the overlay goes further than all of them (`fdc-irq2/OVERLAY-AND-LOAD-SUMMARY.txt`).
- **WSA1**: #16414 and #16204 merged; the other branches are old skeletons.
- **`technics-sharc-21065l`, `technics-mn10300-core`**: nothing that is in neither the overlay nor upstream.
- **`technics-kn7000-initial-data-card`, `backup-firmware-bios-*`, `backup/kn7000-{dsp,tonegen}-pre-rework*`**:
  review iterations of #16394, superseded.
- **HD-SX review branches** (`technics-kn6000-expansion-review-fixes`, v1-v4, `clean-r1`..`r4`, the
  `pushed-2026-10-02` branch and tag): nothing v5 lacks.
- **KN5000 research branches** (March/July), the data wheel, the power-off NMI, the `/INT0` and latch
  changes: in the overlay, done differently, or superseded.
- **`~/compartilhado/mame_driver`**: a February KN5000 sketch, superseded.

## Side findings

- PR #16220 carries a misleading comment: `// FIXME: connect DRQ; the firmware services it in interrupt
  group 0x0f, whose source is not emulated` (v5 `kn7000.cpp:1014`, added in the rebase). `fdc_add()`
  already connects DRQ; only "group 0x0f is not emulated" is still true upstream.
- `tlcs900-prescaler-per-device` has a comment that contradicts its own change (G16).
- `tools/sync-check.sh` still expected the HD-SX3 files and a `technics-kn6000-expansion` branch in
  `mame-pr`, and had no atahle marker. Fixed with G1; it reports IN SYNC.
- `KN7000/MAME-PR-QUEUE.md` said v5 was not pushed, but the reflog of `origin/technics-kn6000-expansion`
  shows `d497bed5caf` "update by push" at 2026-10-16 07:22. Corrected with G1.

## Undetermined

- What 0x20000070 bit 7 does; whether the rhythm site holds IC18 or IC20; what empty expansion slots read;
  IC21's real part size; the DSP clock (G5).
- Whether B at 60 MHz with run-time ALUSAT still finishes 44,100 DSP frames/s; whether the effect kernel
  reads IOP registers back.
- The group-0x17 handshake: upstream review round 1 measured zero G17ICR writes in 45 s on all five sets;
  the overlay's notes say the firmware writes it at 0x48404d25. B and upstream lack the handshake.
- KN5000: PE.0 wiring, the AN0/AN1 assignment, whether `/INT0` is a level or a pulse, whether the
  `"hdd"` default really hangs the HD-AE5000 boot.

## Suggested order

1. G6, IC23 battery RAM: you would notice it.
2. G7 with G8, the 0x9xxxxxxx mirror and the IVAR vectors: together they fix the ROM test and retire the
   per-BIOS vector workaround.
3. G3, the DSP save-state bug: cheap correctness.
4. G18, the clean-up pass over stale notes and comments.

## History

| date       | change                                                                                                       |
|------------|--------------------------------------------------------------------------------------------------------------|
| 2026-10-19 | created from the sweep at `5e0a58a`; G1 and G2 started at Felipe's request                                   |
| 2026-10-19 | G1 done (`c2d6666`), G2 done (`faee3de`)                                                                     |
| 2026-10-20 | G6: IC23's extent and checksum; Another World keeps its data in that window                                  |
| 2026-10-20 | G19, G20 added and G13 planned: `notes/PLAN-2026-10-20-sound-and-hardware-probes.md`                         |
| 2026-10-20 | G6 done, G7 in progress (work-RAM view), G21 added, G18: SD-board notes                                      |
| 2026-10-20 | pass 5 on the unit: IC23's 256 KB repeat confirmed (G6), empty slots read FF (G10)                           |
| 2026-10-20 | G20 in progress: the emulator answers host IOP reads and EPB0 readback (`notes/dsp-probe-2026-10-20/`)       |
| 2026-10-20 | G20: SYSCON and DMAC0 FS answer like the chip; the DSP probe's passes 6 and 7 are built and tested in MAME   |
| 2026-10-20 | G20: pass 6 on the unit: set-up as emulated, chip-only state listed, frame rate narrowed to two readings     |
| 2026-10-20 | G20: pass 7: downloaded DSP code identical to the chip; G4 answered (MSGR2 read-back), FLAG3 never high      |
| 2026-10-20 | G4: the DSP kernel reads MSGR0-7 back (chip evidence, pass 7); audio oracle re-baselined to 028bb1db         |
| 2026-10-20 | G20: pass 8 on the unit (44.1 kHz, verdict b); TM4 tick, per-frame DSP handshake and FLAG3 modelled (KN7000) |
| 2026-10-20 | G13 in progress: wave ROM format and select decoded (`c3999e8`); voices play the ROMs, strap = subtype 1     |
| 2026-10-20 | G13: boot unchanged on all eight cases (`ab_boot.sh`); Felipe's firmware 893 plays the same (`849db8b`)      |
| 2026-10-20 | G20: SPORT DMA registers live (DMASTAT, ring indexes and counts, TX status), as the unit reads them          |
| 2026-10-20 | G13: the strap reports the unit's 0xF8F7 (pass 9: subtype 2, bit 0 set, bits 7:4 = 0xF); oracle e415cb0c     |
