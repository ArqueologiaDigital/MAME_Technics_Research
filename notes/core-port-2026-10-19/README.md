# MN10300 core: the fixes upstream has, ported into the overlay (2026-10-19)

Item G2 of `OVERLAY-GAPS.md`. The overlay replaces upstream's `src/devices/cpu/mn10300/mn10300.cpp` with its
own (the interrupt model, A1.1 in `notes/overlay-upstream-sync/UNSUBMITTED-2026-10-18.md`, ties the drivers
to it). Upstream's copy, merged from this one through #16250 and #16394, picked up a round of fixes in
review that the overlay never took. This ports every one of them that is not part of upstream's different
interrupt, timer and serial-port design. Where the GNU simulator is cited, it is
`KN7000/binutils-gdb/binutils-gdb/sim/mn10300/mn10300.igen` (and `am33.igen` for `bsch`).

## What changed

| area            | before                                                          | now (as upstream)                                                        |
|-----------------|-----------------------------------------------------------------|--------------------------------------------------------------------------|
| 0x01-0x0F       | `mov`/`movbu`/`movhu Dm,(abs16)` skipped: the store never ran   | decoded                                                                  |
| 0x30-0x3B       | `mov`/`movbu`/`movhu (abs16),Dn` skipped                        | decoded                                                                  |
| FA 80-8C        | `mov Am,(abs16)` skipped                                        | decoded (op2 low bits non-zero: illegal)                                 |
| FA F0/F4/F8     | `bset`/`bclr`/`btst imm8,(d8,An)` skipped                       | decoded                                                                  |
| F9/FB/FD 14-17  | `mulqu imm,Dn` (udfu01) skipped                                 | unsigned multiply by the sign-extended immediate, high word to MDRQ      |
| F9/FB/FD 08-0B  | `udf20 imm,Dn` ran as `mulq`                                    | skipped as unimplemented: only op2 0x00-0x03 is `mulq` (udf00)           |
| `addc`/`subc`   | Z from this word alone                                          | Z kept only if it was already set (multi-word results)                   |
| bit ops         | `bset`/`bclr`/`btst` set Z only                                 | Z and N from the tested bits, C and V cleared                            |
| `mul`/`mulu`    | C and V left alone                                              | C and V cleared                                                          |
| `div`/`divu`    | divide by zero logged; INT64_MIN / -1 could SIGFPE the host     | zero divisor or a quotient wider than 32 bits sets V, Dn and MDR kept    |
| `rol`/`ror`     | V left alone; op2 0x88-0x8F ran as `ror`                        | V cleared; op2 0x88 and up illegal                                       |
| `sat16`/`sat24` | flags left alone                                                | Z and N from the 16-/24-bit result                                       |
| `getx`          | flags left alone (the ISR context save was said to need it)     | Z and N from MDRQ, C and V cleared                                       |
| `bsch` (F6 7x)  | Dn = top set bit of Dm's low 16 bits                            | AM33 form: top set bit of Dm below bit Dn (from 31 if Dn is 0), C found  |
| setlb / Lcc     | LAR = the loop top                                              | LAR = the loop top + 4; Lcc and lra branch to LAR - 4                    |
| TM5 count read  | `(base + 1) * remaining-attoseconds`: overflows above base 6074 | counted in IOCLK ticks: base just after a reload, 0 before the underflow |
| TM5 base write  | byte mask ignored                                               | a byte write changes only its half                                       |
| save state      | `m_irq_level` missing, though `check_irq` reads it every insn   | saved                                                                    |
| SIO receive     | a byte arriving with the receiver off was latched               | dropped unless config bit 14 (receive enable) is set                     |
| SIO reset       | receive-enable cleared silently                                 | the peer is told (`sio_rx_enable_cb(0)`)                                 |

The last row needed a driver change: `kn7000.cpp` binds channel 0's callback to the panel's `rx_enable()`,
which clocks out the next reply byte, so the binding now ignores the falling edge. The firmware sets bit 14
on both MIDI channels and on channel 0 before each panel reply (upstream's
`research-scratch/kn7000-pr16250-fixes/probe_sio_rx_enable.lua`), so the gate drops nothing the firmware
wants.

Kept as they were, because they are the overlay's design rather than fixes: the group-callback interrupt
controller (upstream: pins, EXTMD and IVAR, B.1; G8 in `OVERLAY-GAPS.md`), TM5 only with TM4 reading 0
(A1.4), the instant SIO transmit and 64-byte receive FIFO (A1.2), the AM33 E0-E7 registers (A1.3), the DMA
moving count + 1 bytes (A2.17), the length table that skips unimplemented opcodes (A1.6), and the
hard-coded reset PC and SP (G9).

## Does anything change on screen or in the audio?

Three binaries, kept in `~/compartilhado/tmp/kn7000-core-port/` while this was measured:

| binary                 | md5                                | source                                             |
|------------------------|------------------------------------|----------------------------------------------------|
| `kn7000-before`        | `c663ae8838866c8c8b691cf6b2041fe7` | the published binary before this (`5e0a58a`)       |
| `kn7000-corefix`       | `3a164f51cf6d8f1ee55eeebfab7f07d1` | + this core port                                   |
| `kn7000-corefix-hdsx6` | `7ee415f77f9ee9d68fa606d45da14d7d` | + the HD-SX6 port (`notes/hdsx6-port-2026-10-19/`) |

`ab_boot.sh kn7000-before kn7000-corefix OUT` boots each machine with no media for 45 s and compares
snapshots at 2, 3, 4, 5, 6, 8, 12, 20 and 45 s (the KN7000's splash is the JPEG whose Huffman decoder uses
`bsch`, at 3 s), and counts the opcode lines in `error.log`:

| case          | snapshots (2 3 4 5 6 8 12 20 45 s) | opcode log lines, before      | after |
|---------------|------------------------------------|-------------------------------|-------|
| kn7000 v16    | 9 of 9 identical                   | 2 × `divu` by zero @ 4C023B66 | 0     |
| kn7000 v15    | 9 of 9 identical                   | 2 × `divu` by zero @ 4C023B66 | 0     |
| kn7000 v13    | 9 of 9 identical                   | 2 × `divu` by zero @ 4C023B51 | 0     |
| kn7000 sp7001 | 9 of 9 identical                   | 2 × `divu` by zero @ 4C023BC0 | 0     |
| kn6000        | 9 of 9 identical                   | 2 × `divu` by zero @ 4C046EDD | 0     |
| kn6500        | 9 of 9 identical                   | 2 × `divu` by zero @ 4C04704D | 0     |
| kn2400        | 9 of 9 identical                   | 2 × `divu` by zero @ 50152283 | 0     |
| kn2600        | 9 of 9 identical                   | 2 × `divu` by zero @ 50152283 | 0     |

So no machine executes any of the newly decoded opcodes, or `udf20 imm`, in its first 45 s: neither binary
logged an unimplemented or illegal opcode. Every machine does divide by zero twice in the same library
routine; the old core logged it and left the flags, the new one sets V, and the screens do not change.
`bsch` gives the same splash with both forms (the 3 s frame). The paths these runs do not cover (floppy,
SD, HD-SX6, MIDI, menus beyond the boot) are covered only as far as the gate goes.

`oracle_ab.sh OUT kn7000-before kn7000-corefix kn7000-corefix-hdsx6` runs the gate's KN7000 audio oracle on
each:

| binary                 | WAV md5                            | peak RMS |
|------------------------|------------------------------------|----------|
| `kn7000-before`        | `bd02a9c15b580d6b4b4c0a42f78a1fcb` | 48.2     |
| `kn7000-corefix`       | `bd02a9c15b580d6b4b4c0a42f78a1fcb` | 48.2     |
| `kn7000-corefix-hdsx6` | `bd02a9c15b580d6b4b4c0a42f78a1fcb` | 48.2     |

The gate's baseline (`ORACLE_MD5`) is unchanged. `tools/gate.sh` on the published `kn7000-corefix-hdsx6`
(`7ee415f7…`): 17 passed, 0 failed, 1 skipped (kn1500 has no screen device, as before); liveness as before on
every model, both audio oracles at their baselines.

## Scripts

| script         | question it answers                                                                    | run                                                             |
|----------------|----------------------------------------------------------------------------------------|-----------------------------------------------------------------|
| `ab_boot.sh`   | do two binaries draw the same screens on every MN10300 machine, and which opcodes log? | `./ab_boot.sh BIN_A BIN_B OUT [ROMPATH]` (env `CASES`, `TIMES`) |
| `snaps.lua`    | (used by `ab_boot.sh`) snapshot at each time in `$SNAP_TIMES`, then quit               | `SNAP_TIMES="3 45" kn7000 ... -autoboot_script snaps.lua`       |
| `oracle_ab.sh` | what does the gate's KN7000 audio oracle give for each binary, before publishing?      | `./oracle_ab.sh OUT BIN...`                                     |

Each `ab_boot.sh` run writes about 200 MB of `error.log` (mostly DSP and I/O traces); the script keeps only
the opcode lines (`opcodes.log`) and deletes the rest.
