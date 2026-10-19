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

States: `open`, `in progress`, `done` (with the commit), `decision` (needs Felipe's call before any
work), `blocked`, `wontfix` (with the reason).

| #   | item                                                   | area           | size         | state    |
|-----|--------------------------------------------------------|----------------|--------------|----------|
| G1  | KN6000 expansion: CN105 connector + HD-SX6, PR #16220  | KN6000 driver  | ~230 lines   | done     |
| G2  | Main CPU core fixes upstream has                       | mn10300 core   | ~200 lines   | done     |
| G3  | Effects DSP save state freezes the effects             | KN7000 driver  | trivial      | open     |
| G4  | Effects DSP branch B fixes                             | SHARC core     | small-medium | open     |
| G5  | Effects DSP clock, 60 or 66 MHz                        | KN7000 driver  | one line     | decision |
| G6  | IC23 battery-backed SRAM: panel memories lost          | KN7000 driver  | small        | open     |
| G7  | 0x90000000-0x97FFFFFF is the uncached view of 0x5xxx   | KN7000 driver  | small        | open     |
| G8  | Interrupt vectors through IVAR, not per-BIOS addresses | mn10300 core   | small-medium | open     |
| G9  | Real power-on path from IC18, and the flash updater    | KN7000 driver  | small/large  | open     |
| G10 | CS5 mirrors and open-bus reads                         | KN7000 driver  | small        | open     |
| G11 | IC21 custom data probably halfword-swapped             | KN7000 driver  | small        | open     |
| G12 | IC414 NO_DUMP, KN6000/6500 Initial Data preload        | ROM records    | small        | open     |
| G13 | Voices on the real wave ROMs                           | tone generator | large        | blocked  |
| G14 | SD SPI with the card deselected reads 0x00             | KN7000 driver  | small        | open     |
| G15 | Smaller KN7000 items                                   | KN7000 driver  | small        | open     |
| G16 | KN5000 branch work                                     | KN5000         | mixed        | open     |
| G17 | KN5000 research findings                               | KN5000         | mixed        | open     |
| G18 | Notes and comments that newer findings contradict      | docs           | small        | open     |

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
  tick to feed slots. The audio oracle would need a re-baseline. Whether the effect kernel reads an
  IOP register back was not checked.
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

### G6. IC23, the 256 KB battery-backed SRAM at 0x44000000 — open

`technics-roms-disasm/kn7000/tools/cnv_romdump/README.md:149`; the service SRAM test walks exactly 256 KB.
The overlay maps 16 MB of plain RAM there with no NVRAM (`kn7000.cpp:884-885`), so panel memories are
lost on every restart. Small, and the most noticeable item here.

### G7. 0x90000000-0x97FFFFFF is the uncached view of 0x50000000-0x57FFFFFF — open

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
  consistent with the research, but they read 0x00 where open bus elsewhere reads 0xFF. The windows
  themselves were never surveyed, so what an empty slot reads is undetermined. The boot ROM updater
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

### G13. Voices on the real wave ROMs — blocked

The format is settled: 16-bit samples, low byte first, Y and X interleaved as even and odd samples
(`technics_roms/roms/kn7000/real_dump_v1.3_b893/wave-analysis/README.md:15-28`). How a voice selects its
sample start is not decoded, so the voice engine still plays the synthetic pack (`kn7000_tonegen.cpp:65-72`);
only the wave ROM test reads the dumps. Large.

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
  `:2494-2495` ("nothing written below 0x20000"). `kn7000_tonegen.h:19,45,82` and `kn_tonegen.h:173` say
  the wave ROMs are undumped; `kn_tonegen.h:93` has main and sub swapped.
- **KN5000 notes**, about 20, the main ones: `kn5000-port-census-2026-09-03.md:275-277` (ADREG never read),
  `:104-170`, `:213-225`; the kn5000-30 revert (done in `83264d1`); IC14 "must be re-dumped";
  `kn5000-dsp-reverb.md:216-221` (reverb lengths at half their value); the 48 kHz assumption.
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

| date       | change                                                                     |
|------------|----------------------------------------------------------------------------|
| 2026-10-19 | created from the sweep at `5e0a58a`; G1 and G2 started at Felipe's request |
| 2026-10-19 | G1 done (`c2d6666`), G2 done (`faee3de`)                                   |
