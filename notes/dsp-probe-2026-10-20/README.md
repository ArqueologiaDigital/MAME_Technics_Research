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
- the DSP probe in MAME, `-bios v13`, with no test-side stand-ins (`cnv_romdump/test/run_test.sh --dsp`, then
  `--dspmem`): phase 1 gives 5 of 5 files as expected and decodes SYSCON as `0x410`, 16-bit host bus, LSW first.
  Phase 2 passes its pre-check, finds FS full at the first look for every word (0 repeat polls), and reads PM `0x8000`-`0x8DFF` (3,584 words,
  all equal to the SHARC's memory) and DM (3,317 of 3,328 equal; the kernel's variables move). It leaves DMAC0
  `0xA0`, IIEP0 `0x8093`, IMEP0 1 and CEP0 1, as found. `check_dsp_probe.py` says "everything checks out" for
  both, with phase 2 compared against the kernel record in the v1.3 program dump.
