# The effects DSP's host port, emulated for the DSP probes (2026-10-20)

Plan step 5 of `notes/PLAN-2026-10-20-sound-and-hardware-probes.md` (OVERLAY-GAPS G20): probes that run on
Felipe's KN7000 through the cnv_romdump .CNV route (`technics-roms-disasm/kn7000/tools/cnv_romdump/`, DSP
probe builds) read the ADSP-21065L's IOP registers and memory back through the host port, measure its timer
and SPORT rates, and record the self-test handshake. Every probe runs in MAME first. Until now the overlay
answered only three host reads, with constants, so a probe could check its mechanics in MAME but not its
values. This change makes the emulator answer like the chip for everything the probes read.

## The host port

From the firmware (941 addresses; `notes/dsp-host-interface.md`) and the ADSP-21065L Technical Reference:

- The 16-bit index written to `0x98000000` is the SHARC's IOP register address (Table E-15); the data port is
  `0x9C000000`. A 32-bit register goes through it as two 16-bit halves, **low half first** (the firmware's
  32-bit read `0x4840531E` returns `(second << 16) + first`).
- The firmware's data-port accessor (`0x48404E50`) locks (`0x48404D2A`), saves the bus timing at `0x32000026`,
  sets `0x924`, reads `0x9C000000`, restores the timing and unlocks (`0x4C03D6BC`).
- Its boot probe (`0x48405028`) writes SYSCON `0x91919191` then `0x20` as four bytes each (`0x4840528A`) and
  reads register 0 back with a four-read, 8-bit primitive (`0x48405229`), requiring `0x20` (SYSCON's reset
  value, HBW `10`: an 8-bit host bus). That primitive returns `(b1 << 8 | b2 << 16 | b3 << 24 | 0xFF) & b0`, b0
  sign-extended, so only the first byte counts. Then `0x48407A56` writes SYSCON `0x410` (HBW `01`, a 16-bit
  host bus, LSW first) as four bytes and again as two halves, and reads it back without checking. The TRM
  (Table E-25, HBW): a host changes HBW by writing four 8-bit words; host accesses to IOP registers other than
  EPBx are always 32 bits, moved in as many pieces as the host bus width needs.
- Register `0x0B` (MSGR3) is the ID readback after each probe record; `0x37` (DMASTAT) bit 7 is polled as busy.
- DMAC0 (`0x1C`): bit 0 DEN, bit 2 TRAN (1 = transmit, internal to external), bit 5 DTYPE (48-bit)
  (Table E-16). The firmware's uploads use `0xA1` (PM) and `0x41` (DM) and close with `0xA0`; it never
  transmits.

## What the emulator now does

| part                        | before                                                                               | now                                                                                                                                                                               |
|-----------------------------|--------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 21065L IOP registers        | reads 0, writes dropped (except the SPORT chain pointers, cached for the audio glue) | a register file: every write kept; reset values from Table E-15 (SYSCON `0x20`, VIRPT `0x8014`, WAIT `0x21AD6B5A`)                                                                |
| the kernel's own IOP reads  | 0                                                                                    | still 0, deliberately: returning the stored value can change what the effects compute (G4)                                                                                        |
| host reads, regs 0x0B/0x37  | `0x1065` / `0`                                                                       | unchanged: the boot protocol was brought up against them                                                                                                                          |
| host reads, SYSCON (0x00)   | `0x20`                                                                               | from 2026-10-20 (2nd build): the register file like the rest; after boot `0x410`, what the firmware wrote                                                                         |
| host reads, other registers | 0                                                                                    | the register file, counted from the last index write: two halves, low first, or four bytes while SYSCON's HBW is 8-bit (taken at the index write)                                 |
| host writes to registers    | decoded only for the download (0x40, 0x1C)                                           | also copied into the register file, packed the same way                                                                                                                           |
| EPB0 readback               | none                                                                                 | DMAC0 with DEN and TRAN arms channel 8 from IIEP0/IMEP0/CEP0; host reads of EPB0 return internal memory, 16 bits at a time, low first; IIEP0 and CEP0 advance; DEN clear stops it |
| DMAC0 FS (bits 14-15)       | 0                                                                                    | from 2026-10-20 (2nd build): `11` (EPB0 full) while the readback has words left, else as stored (`00`)                                                                            |

Not modelled: timers do not count (TCOUNT holds what was written), DMASTAT and the SPORT DMA counts do not
move, reading the SPORT data buffers pops nothing. On the real chip all of these move; the probes' time
series is there to measure exactly that. The value the emulator returns for MSGR3 (`0x1065`) is the boot
protocol's stand-in, not register contents. FS is modelled as a DMA that keeps EPB0 full: on the chip it fills
the six-deep buffer at its own pace, which is why the probe polls FS before every word.

## Checks

`host_iop_selftest.lua` (run as `-autoboot_script`, default 40 s into a session):

| check                                     | result                                                                                                                                                          |
|-------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| SPORT DMA chain pointers through the host | `0x73`/`0x53`/`0x7B`/`0x5B`/`0x63`/`0x33`/`0x6B`/`0x3B` = `0x4309`, `0x4311`, `0x4319`, `0x4321`, `0x4329`, `0x4331`, `0x4339`, `0x4341`: what the kernel wrote |
| PM readback, DMAC0 `0xA5`                 | PM `0x8004`-`0x8007` through EPB0 = the words in the SHARC's program space (`IDLE` `0x008000000000`, `JUMP 0x8071` `0x063E00008071`, two zero slots)            |
| DM readback, DMAC0 `0x45`                 | DM `0x9800`-`0x9803` = `0x404CCCCC`, `0xC04CCCCC`, 0, 0, as stored                                                                                              |
| SYSCON through the host (2nd build)       | `0x410`, what the firmware wrote at `0x48407A56`; this also shows the boot probe passed, since its guarded writes stop once the dead flag is set                |
| DMAC0 FS during the PM readback (2nd)     | `11` before each of the four words, `00` after the last                                                                                                         |
| verdict                                   | PASS (0 problems), on `-bios v16` and `-bios v13`                                                                                                               |

Before and after (`notes/core-port-2026-10-19/ab_boot.sh` and `oracle_ab.sh`, the published binary `ed41d01b…`
against this build `889b6f48…`): kn7000 v16, v13 and sp7001, kn6000 and kn2400 each give 9 of 9 identical
snapshots over 45 s, and the gate's audio oracle stays `bd02a9c15b580d6b4b4c0a42f78a1fcb`. The firmware never
reads the registers that changed, so nothing it does changes.

**The 2nd build (SYSCON and FS)**, binary md5 `97d2f383a8695d766e257b3e6fb4d07e`, against the published `889b6f48…`:

- the self-test above passes on v16 and v13;
- the gate's audio oracle (`oracle_ab.sh`) gives `bd02a9c15b580d6b4b4c0a42f78a1fcb` on both;
- `ab_boot.sh`: kn7000 v16, v15, v13 and sp7001, kn6000, kn6500, kn2400 and kn2600 each give 9 of 9 identical
  snapshots over 45 s, with no unimplemented-opcode or divide-by-zero lines on either binary;
- published (`tools/publish-binary.sh`, `kn7000-emulator/kn7000` md5 `97d2f383…`), `tools/gate.sh` gives 17
  passed, 0 failed, 1 skipped (kn1500);
- the DSP probe in MAME, `-bios v13`, with no test-side stand-ins (`cnv_romdump/test/run_test.sh --dsp`, then
  `--dspmem`): phase 1 gives 5 of 5 files as expected and decodes SYSCON as `0x410`, 16-bit host bus, LSW first.
  Phase 2 passes its pre-check, finds FS full at the first look for every word (0 repeat polls), and reads PM `0x8000`-`0x8DFF` (3,584 words,
  all equal to the SHARC's memory) and DM (3,317 of 3,328 equal; the kernel's variables move). It leaves DMAC0
  `0xA0`, IIEP0 `0x8093`, IMEP0 1 and CEP0 1, as found. `check_dsp_probe.py` says "everything checks out" for
  both, with phase 2 compared against the kernel record in the v1.3 program dump.

## What the chip said (pass 6 on Felipe's KN7000, 2026-10-20)

Phase 1 of the probe ran on the unit (files private: `technics_roms` `roms/kn7000/real_dump_v1.3_b893/pass6-run1/`;
decoded by `technics-roms-disasm` `kn7000/tools/cnv_romdump/check_dsp_probe.py`, `88c15e9b6`). Against this
emulator (`-bios v13`, the same probe in MAME):

| register                                  | chip                                                                 | emulator                    | for the emulator                                                                     |
|-------------------------------------------|----------------------------------------------------------------------|-----------------------------|--------------------------------------------------------------------------------------|
| SYSCON                                    | `0x410`                                                              | `0x410`                     | as the chip (this build)                                                             |
| chain pointers, `DMAC0`, `WAIT`, `SDRDIV` | as the kernel wrote them                                             | the same                    | as the chip                                                                          |
| `STCTLx` / `SRCTLx`                       | `0xF93CB173`, `0xD93CB173` / `0x013C3173`                            | `0x013CB173` / `0x013C3173` | the top byte of `STCTLx` holds status bits the emulator does not set                 |
| `DMASTAT`                                 | `0x33F`: all eight SPORT DMA channels                                | `0`                         | not modelled (F.3)                                                                   |
| SYSTAT                                    | `0x13`                                                               | `0`                         | not modelled                                                                         |
| IOSTAT                                    | `0x80000000`                                                         | `0` (`1` after a probe run) | not modelled                                                                         |
| `IOCTL`                                   | `0x0852205B`                                                         | `0x8852A05B`, as written    | bits 31 and 15 read 0 on the chip                                                    |
| MSGR3                                     | `0`                                                                  | `0x1065` (boot stand-in)    | the stand-in is not the chip's run-time value                                        |
| MSGR2                                     | `0x686EB`, then `0x6867C`: it moves                                  | `0x656F0`, fixed            | I3, the ring-3 pointer; moves only if the kernel's frames and FLAG3 do               |
| SPORT rings (`IIxxx`, `Cxxx`)             | receive base + 3, count 5; transmit base + 5, count 3, at every read | counts 0                    | the DMA is not modelled; on the chip every read lands at the same point of the frame |
| `TPERIODx`, `TCOUNTx`                     | 0                                                                    | 0                           | the kernel does not use the timers                                                   |

**The frame rate was still open after pass 6** (pass 8 settled it: 44.1 kHz, one handshake per frame, below). The firmware's DSP accesses ran at 24.15 us each (41.4 per ms): every one
waits for the DSP's handshake. MSGR2 (I3, stepped once per frame while FLAG3 is high) moved 111 words in about
4.93 ms, 22.5 per ms. Either frames at about 22.5 kHz with FLAG3 always high, or 41.4 kHz or more with FLAG3 high
on about half of them. The first would put about two accesses in each frame, 24 us apart, and those would find the
8-word rings at different positions; every one of about 2,000 reads found them at the same place. So the data
favours one handshake per frame and frames of 41.4 kHz or more (44.1 kHz, with about 6% of handshakes missed,
fits), FLAG3 high on alternate frames and ring 3 stepping at half rate. That is an argument, not a measurement: the
overlay's IRQ0 tick (`kn7000.cpp`, the provisional frame rate) stays a placeholder until pass 8 (cnv_romdump,
in preparation) times the handshakes with the main CPU's TM4 (2,000 counts per ms).

## The DSP's memory, chip against emulator (pass 7, 2026-10-20)

Phase 2 ran on Felipe's unit (files private: `technics_roms` `real_dump_v1.3_b893/pass7-run1/`, report
`pass7-check-2026-10-20.txt`). Every word came back (3,584 PM, 3,456 DM), FS showed data at the first look each
time, the four channel-8 registers were left as found, and the dead flag stayed 0.

`compare_dspmem.py CHIP_DIR MAME_DIR` compares it with the same probe in MAME. The MAME side ran with
`cnv_romdump/test/run_test.sh --dspmem --bios v13` and, as its NVRAM, a copy of the unit's IC23 (pass 5,
`R8400000.BIN`, first 256 KB), so that the firmware loads the same effects:

| range            | what                                   | words | equal | differ, MAME 0 |
|------------------|----------------------------------------|-------|-------|----------------|
| PM 0x8000-0x8077 | interrupt vectors, reset handler       | 120   | 120   | 0              |
| PM 0x8078-0x80A5 | main loop, the host-patched CALL slots | 46    | 46    | 0              |
| PM 0x80A6-0x82FF | kernel                                 | 602   | 92    | 510            |
| PM 0x8300-0x83FF | shared filter helpers                  | 256   | 64    | 192            |
| PM 0x8400-0x8CFF | effect programs, nine slots            | 2304  | 653   | 1651           |
| PM 0x8D00-0x8DFF | boot-init, recycled by slot 9          | 256   | 147   | 109            |
| DM 0x9800-0x9C3F | per-unit state                         | 1088  | 124   | 962            |
| DM 0x9C40-0x9FFF | scrub countdown table and the rest     | 960   | 20    | 940            |
| DM 0xC000-0xC301 | per-unit parameters                    | 770   | 489   | 271            |
| DM 0xC302-0xC341 | slot I/O descriptors, SPORT TCBs       | 64    | 63    | 1              |
| DM 0xC342-0xC381 | SPORT DMA rings                        | 64    | 64    | 0              |
| DM 0xC382-0xC4FF | the rest                               | 382   | 376   | 6              |

- **Everything the firmware downloads is identical.** That covers the kernel (0x8000-0x8101), the helpers
  (0x8300-0x833F), boot-init (0x8D00-0x8D92), the ten CALL slots, and the nine effect programs at 0x8400 + 0x100·k,
  each for exactly its downloaded length. Every differing PM word is one MAME never wrote: 0 in MAME, power-on SRAM
  contents on the chip (0x8102-0x82FF: 510 distinct values in 510 words, 60% one-bits).
- **DM**: besides never-written words, 12 differ with both sides non-zero: run-time state and parameters easing
  toward their targets (0x9AD1/2, 0xC003, 0xC058, 0xC0A5, 0xC0EB, 0xC138, 0xC2B9-0xC2BE).
- **One emulator bug: DM 0xC329**, the first receive channel's TCB index (II), is 0xC362 on the chip and 0 in MAME.
  `tap_c329.lua` (run with `-nodrc` for exact PCs) shows the host's download writing 0xC362 there at 0.98 s. Then the
  kernel's ring-3 scrub stub (PC 0x80CC, reached from CALL slot 0x8097) writes 0 with I3 = 0xC329, R4 (the saved I3) =
  0, M7 = 0x3688. `tap_i3.lua` samples I3 at every frame boundary (the kernel's IOSTAT writes): it is 0x656F0 (B3)
  until t = 1.990 s, then 0. The cause:
  - Effects 58-61 save I3 into MSGR2 at their entry (`DM(0x0A) = I3`, 0x8403) and take it back with
    `I3 = DM(0x0A)` (0x845E).
  - The overlay's 21065L returns 0 for the kernel's own IOP reads (`iop65l_r`, held back as G4), so I3 becomes 0.
  - The scrub's hop and the circular-buffer wrap (B3 0x656F0, L3 0x4650) then send its 41-word zero-fill to 0x7CD8,
    0xC329, 0x1097A, and on in steps of 0x4651.

  On the chip MSGR2 reads back what was written (pass 6 saw it move: 0x686EB, then 0x6867C), so I3 stays in ring 3
  and the TCB survives. **So G4 has chip evidence now: at least the MSGR registers must read back their stored value**,
  or the ring-3 effects run on a zero pointer.
- **A second gap in the same trace: FLAG3.** In MAME I3 never moves before t = 1.990 s (0x656F0 at every frame), so
  the emulated FLAG3 input is always low. On the chip I3 steps (pass 6), about once per two frames if the frame rate
  is 44.1 kHz. Ring 3 does not scroll in the emulator.

## The fix: the kernel's MSGR reads return the stored value (2026-10-20)

`sharc.cpp` `iop65l_r`: the 21065L's own reads of MSGR0-7 (IOP 0x08-0x0F) return what was written. The message
registers are plain storage on the chip. Every other IOP register still reads 0 to the kernel, because several carry
status bits the chip sets and this model does not (the table above). Build md5 `b2d669c2c9be254fd3ea4ecea0442198`,
against the published `97d2f383…`:

| check                                                                     | before (`97d2f383…`)                     | after (`b2d669c2…`)                             |
|---------------------------------------------------------------------------|------------------------------------------|-------------------------------------------------|
| `tap_i3.lua`, 8 s, `-nodrc`, `-bios v13`, blank IC23                      | I3 leaves ring 3 (0 from t = 1.990 s)    | in ring 3 at all 284,759 frame-boundary samples |
| the same, the unit's IC23                                                 | the same                                 | in ring 3 at all 293,194 samples                |
| `tap_c329.lua`, the same two cases                                        | 0xC362 written at 0.98 s, then zeroed    | one write (0xC362), kept                        |
| pass 7 in MAME with the unit's IC23, `compare_dspmem.py`                  | DM 0xC302-0xC341: 63 of 64 = the chip    | 64 of 64; downloaded PM still identical         |
| gate audio oracle (`oracle_ab.sh`)                                        | `bd02a9c15b580d6b4b4c0a42f78a1fcb`, 48.2 | `028bb1dbead8b06d04f565cb30dc9a32`, 48.1        |
| `oracle_attribution_msgr.sh`: new binary, MSGR reads forced to 0 by a tap | -                                        | `bd02a9c15b580d6b4b4c0a42f78a1fcb`, bit for bit |

The oracle's capture differs only in seconds 16-17, the held note (`tools/kn5000_wav_ab.py`): 3.89% of samples,
peak delta 176, difference RMS 25.6 against a signal RMS of about 180 in second 16. The ring-3 effect now reads
its own delay memory. Peaks are 971/957 against 972/954 before, with no sample at full scale in either. The
attribution run shows the read-back is the only thing that moved it, so the oracle is re-baselined to
`028bb1db…` (tools/gate.sh, in its own commit).

`ab_boot.sh` (published `97d2f383…` against this build): kn7000 v16, v13 and sp7001, kn6000 and kn2400 each give 9
of 9 identical snapshots over 45 s, with no unimplemented-opcode or divide-by-zero lines. Published as
`kn7000-emulator/kn7000` md5 `b2d669c2…`; `tools/gate.sh` with the new oracle: 17 passed, 0 failed, 1 skipped
(kn1500).

## The unit's timing in the emulator: TM4, the per-frame handshake, FLAG3 (2026-10-20)

Pass 8 measured three things the overlay did not model. All three are now modelled, for the KN7000 only
(`m_kn7000_timing`; the KN6000/KN6500/KN2400 keep the fixed tick and the immediate handshake, as nothing on them is
measured):

| change                                                                                                   | where                                                                     |
|----------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------|
| TM4 counts like TM5 (IOCLK/8, period reload + 1, live TM4BC); its underflow asserts a board-chosen group | `mn10300.cpp` `tm4_*`, `tm45_*`; `set_tm4_irq_group`                      |
| the KN7000's 1 kHz tick is TM4 as the firmware programs it (0x7D0, 0x81: 1.0005 ms), not a fixed timer   | `kn7000.cpp` machine_start/machine_reset (`sys_tick` kept for the others) |
| the group-0x17 handshake: immediate during host boot, then once per DSP frame, raised on the frame tick  | `mn10300.cpp` `set_dsp_handshake_selfack`; `kn7000.cpp` `dsp_audio_tick`  |
| FLAG3 high on every other frame                                                                          | `kn7000.cpp` `dsp_audio_tick`                                             |

The handshake is raised on the frame tick (a timer), not at the kernel's FLAG4 edge. A first build raised it at the
FLAG4 fall (IOSTAT, end of each compute). The main CPU then saw it only at its next timeslice, and pass 8 in MAME
found no lattice (spread 15-21 us). The scheduler ends every CPU's timeslice at a timer, so on the tick the stamps
lie on a 0.20 us lattice, as on the unit.

**Checks.** `tm4_check.lua` (`-bios v16`): the firmware programs TM4MD 0x81 and TM4BR 0x7D0, TM4BC reads live, and the
firmware's counter at 0x50151BFC runs 499.80 per s (500.00 with the fixed timer), the 1.0005 ms period. Pass 8 in
MAME (`cnv_romdump/test/run_test.sh --dsprate --bios v13`, the released binary `c8334f68…`), against the unit:

| measurement                         | unit (pass 8) | MAME, this build           |
|-------------------------------------|---------------|----------------------------|
| handshake period, in tick units     | 22.68231 us   | 22.66440 us                |
| frame rate, tick taken as 1 ms      | 44,087.2 Hz   | 44,122.1 Hz                |
| frame rate, TM4 at exactly 2 MHz    | 44,065.2 Hz   | 44,100.0 Hz                |
| spread of the stamps on the lattice | 0.28 us       | 0.20 us                    |
| accesses taking one frame           | 96.8%         | 98.0%                      |
| commonest access pair               | 45.34 us      | 45.33 us                   |
| I3 steps per ms                     | 22.04361      | 22.06102                   |
| FLAG3 share                         | 0.5000        | 0.5000                     |
| ring position at every read         | one (CR0A 5)  | 0 (SPORT DMA not modelled) |
| verdict                             | (b)           | (b)                        |

The emulator's clocks are exact, so its 2 MHz figure is 44,100.0 Hz. Against its own tick, the unit's DSP runs
0.08% slower; the two clocks come from separate crystals.

**The audio oracle**, one build per step (`oracle_ab.sh`), and `wav_shift.py` against the published `028bb1db…`:

| build                 | oracle md5                         | the held note against `028bb1db…`                       |
|-----------------------|------------------------------------|---------------------------------------------------------|
| + TM4 tick            | `3c2f89d60213a9e58f6a9b8452e33048` | starts 0.271 ms earlier; aligned, 0.01% residual energy |
| + per-frame handshake | `f99f85219598b58c743c31e6ef72cd4f` | the same shift, 0.01% residual                          |
| + FLAG3 (this build)  | `8a1fe2a44e064f94ff935242fd717cb4` | starts 0.188 ms earlier; aligned, 0.21% residual        |

So TM4 and the handshake only move the note's start by a quarter of a millisecond: the firmware runs on the
slightly slower tick. FLAG3 changes the sound itself a little: ring 3 now scrolls, as on the chip. Peaks and
per-second levels are unchanged (`tools/kn5000_wav_ab.py`: 179.0 against 179.0 in second 16).

`ab_boot.sh` (published `b2d669c2…` against this build), 9 snapshots over 45 s per case: kn6000, kn6500, kn2400 and
kn2600 identical at every time; kn7000 v16, v15, v13 and sp7001 identical except at 6 s. There the boot splash's
notes (rows 110-316) are caught at another point of their dithered fade-in, which the firmware's timers pace. No
unimplemented-opcode or divide-by-zero lines in either. Passes 6 and 7 in MAME on this build: 5 of 5 (with MSGR2
counted as live, cnv_romdump `dda79f943`) and 4 of 4. Published as `kn7000-emulator/kn7000` md5 `2a8e2fce…`;
`tools/gate.sh` with the new oracle: 17 passed, 0 failed, 1 skipped (kn1500).

## The SPORT DMA registers, live (2026-10-20)

`sharc.cpp` (21065L): DMASTAT, each SPORT DMA channel's index (IIxx) and count (Cxx), and the transmit
buffer status in STCTLx now read the channels' live state, for the host and for the kernel (which never reads
them). The board calls `sport_frame()` at each frame tick (`kn7000.cpp` `dsp_audio_tick`). A channel runs when its
control half has SPEN, SDEN and SCHEN set and its chain pointer names a TCB (at 0x8000 | CP: II, IM one below, C two
below). Each frame moves one whole ring (8 words) evenly across the frame. The phase is the unit's: at the
handshake, receive rings at base + 3 and transmit rings at base + 5. The data itself still moves through the
driver's fixed ring slots, as before. The host's DMASTAT reads lose their constant 0 stand-in, and EPB0 (bit 6)
shows while a probe readback is armed.

Pass 6 in MAME on this build (`run_test.sh --dsp --bios v13`), against the unit:

| register(s)                   | unit (pass 6)                       | MAME, this build                                                |
|-------------------------------|-------------------------------------|-----------------------------------------------------------------|
| DMASTAT                       | `0x33F`                             | `0x33F`                                                         |
| IIR0A / IIR0B / IIR1A / IIR1B | `0xC365` `0xC36D` `0xC375` `0xC37D` | the same                                                        |
| CR0A, CR0B, CR1A, CR1B        | 5                                   | 5                                                               |
| IIT0A / IIT0B / IIT1A / IIT1B | `0xC347` `0xC34F` `0xC357` `0xC35F` | the same                                                        |
| CT0A, CT0B, CT1A, CT1B        | 3                                   | 3                                                               |
| SRCTL0, SRCTL1                | `0x013C3173`                        | `0x013C3173`                                                    |
| STCTL1                        | `0xD93CB173`                        | `0xD93CB173`                                                    |
| STCTL0                        | `0xF93CB173`                        | `0xD93CB173`: TUVF_A, a sticky start-up underflow, not modelled |

Pass 8 in MAME: the phase check finds CR0A 5 and IIR0A `0xC365` on all 240 samples, as the unit did, and the verdict
stays (b). The audio oracle stays `8a1fe2a44e064f94ff935242fd717cb4` (`oracle_ab.sh`): the kernel never reads these
registers.
