# IC23, the KN7000's battery-backed SRAM, modelled (2026-10-20)

Item G6 of `OVERLAY-GAPS.md`. Felipe asked whether modelling IC23 properly would let us test Another World in
MAME and check that a later session is still intact, before trying anything on his unit.

## What IC23 is

- C3BBJG000011, a 2 Mbit ×16 SRAM on A1-A17: 256 KB (`notes/table-rom-structure.md:40`). Its chip select, CS1
  (CPU pin 52), goes to IC23 alone, through the power-fail transistor Q3
  (`technics-roms-disasm/kn7000/tools/cnv_romdump/probes/cs1_trace.py`). With only A1-A17 wired it repeats
  every 256 KB through the window; that is inferred, and the SURVEY2 dump (`cnv_romdump`, releases/2026-10-20-survey2)
  reads 2 MB there to confirm it.
- The firmware addresses it at 0x44000000 and through the uncached view 0x84000000. Its RAM DEVICE TEST walks
  exactly 256 KB (`BackupSramTest`, 0x484A0055 in 941).
- Layout (`technics-roms-disasm/kn7000/kn7000_manual.sym` ~2423-2440, 941): a 0x7A0-byte header holding the live
  panel settings at 0x20-0x76F; the PANEL MEMORY store, 104 records (13 banks × 8) at 0x824-0x30173; the
  checksum at 0x30174.
- **The checksum covers only the header.** `SumU32Words(0x84000000, 0x7A0)` sums the u32 words at offsets 4..0x7A0
  (its loop counts the index down from 0x1E8 to 1) and takes the one's complement. At boot,
  `BackupSramChecksumVerify` (0x484D78C3) compares it with the stored value and leaves 0 (valid) or -1 in
  0x5006CC80 (941; 0x5006CC90 in sp7001).
- **The checksum is written only at power-off.** The stamp is in the firmware's power-fail handler, 0x484D77CF in
  941, entered through the NMI: IC18's NMI vector 0x40000008 is `mov 0x50000006,a0 ; jmp (a0)`, and the firmware
  puts `jmp 0x484D77CF` at 0x50000006, writing it through 0x90000006. The handler stops the hardware, stamps the
  checksum if byte 0x5006CC81 is 0x80, waits 7000 TM5 counts, sets GPIO 0x36008004 bit 3 (the power latch) and
  spins.

## What changed in the overlay

| change                                                                                                                                                                                    | where                                    |
|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------|
| IC23 as a 256 KB `nvram_device` on the KN7000, installed at 0x44000000 and 0x84000000, repeating every 256 KB through both 16 MB windows (file `nvram/kn7000/ic23`)                       | `kn7000.cpp` `machine_start`, `kn7000()` |
| the KN6000/KN6500/KN2400 keep the 16 MB RAM placeholder: their backup SRAM is not identified                                                                                              | `kn6000()`, `kn2400()`                   |
| an edge-triggered NMI in the CPU core: PC and PSW pushed, IE cleared, PC = 0x40000008                                                                                                     | `mn10300.cpp` `take_nmi`                 |
| a POWER OFF machine control (KN7000 only), as the KN5000 has: it pulses NMI, gives the firmware 100 ms, then exits so MAME writes the NVRAM                                               | `kn7000.cpp` `power_switch`              |
| 0x90000000-0x903FFFFF is the +0x40000000 view of work RAM on the KN7000 too (it was on the KN2400 only); without it the NMI stub at 0x50000006 read zero and POWER OFF ran into empty RAM | `kn7000()` `m_ram90_workram`             |
| the gate gives its runs a throwaway copy of `nvram/` without `kn7000/ic23`, so IC23 starts blank as the RAM did when the baselines were measured                                          | `tools/gate.sh`                          |

**For Felipe:** panel memories and settings now survive a restart **when the session ends with POWER OFF**
(Input settings for this machine > "POWER OFF (run the firmware's power-down, then exit)"; not bound to a key by
default, as on the KN5000). Closing the window skips the power-down. If nothing changed in the session that is
harmless, but after any change the next boot finds the checksum stale and resets **everything to factory, panel
memories included** (runs 7-8 below). The file is `nvram/kn7000/ic23`, or `nvram/kn7000_<n>/ic23` with a
non-default `-bios` (MAME keeps one NVRAM folder per BIOS: v13 is `kn7000_4`, sp7001 `kn7000_0`). Delete it to
start blank.

## Results

`check_ic23.sh BINARY OUT [BIOS]` (with `ic23_probe.lua` and `ic23_file.py`), -bios v16, eight boots on one
`-nvram_directory`:

| run            | firmware's verdict at boot | what happened                                                                                      |
|----------------|----------------------------|----------------------------------------------------------------------------------------------------|
| 1 blank        | invalid                    | IC23 initialised; POWER OFF stamps 0x6E1E9DD0 in 33 ms (power latch set)                           |
| 2 again        | **valid**                  | the saved IC23 is accepted                                                                         |
| 3 header-hit   | invalid                    | byte 0x100 flipped in the header: detected, header back to factory, stamped again                  |
| 4 after-header | valid                      |                                                                                                    |
| 5 store-hit    | **valid**                  | byte 0x30000 flipped in the PANEL MEMORY store: not covered by the checksum, not noticed           |
| 6 after-store  | valid                      | the flipped byte (0x93, was 0x6C) is still there                                                   |
| 7 change-plain | valid                      | BRASS pressed at 30 s (the header's checksum moves to 0xB3E4B1D0), then a plain exit: no stamp     |
| 8 after-plain  | **invalid**                | factory settings: the header **and the PANEL MEMORY store** are reset (byte 0x30000 is 0x6C again) |
| 9 change-power | valid                      | BRASS pressed, then POWER OFF: stamped 0xB3E4B1D0                                                  |
| 10 after-power | **valid**                  | the change is kept: 6 header bytes differ from run 8's factory image                               |

All ten boots see the 256 KB repeat (0x44040000 reads as 0x44000000) and the 0x84000000 alias.

`aw_ic23_check.sh BINARY OUT` (with `aw_power.lua`, `ic23_diff.py`): the Another World SP7001 build on its card,
`-bios sp7001`, POWER OFF at 60 s, then a second boot that reads the firmware's verdict; the control run has the
card in the slot but does not start the game:

| image                    | header+settings 0x000-0x7A3 | 0x7A4-0x823 | PANEL MEMORY store 0x824-0x30173 | checksum cell | 0x30178-0x3FFFF |
|--------------------------|-----------------------------|-------------|----------------------------------|---------------|-----------------|
| game vs control (differ) | 1,945 of 1,956              | 127 of 128  | 65,676 of 194,896                | 4 of 4        | 0               |

- **Control** (card in, game not started): POWER OFF stamps 0x6E1E9DD0; the next boot finds IC23 valid.
- **Game**: SD CARD LOAD starts the module. Its loader never finishes: its pack-loop index at 0x44080050 is IC23
  offset 0x50 through the 256 KB repeat, and the resource copies to 0x44200000 and up land on offsets
  0x0000-0xF834 too, so the index keeps being overwritten (`aw_tap44.lua`: 77,568 writes and reads of
  0x44080050 from the loop at 0x502B4FFC-0x502B5004, 15,886 writes to 0x44200000-0x4420F834 in 18 s). The screen
  stays on "Initializing PLUG-iN System". POWER OFF then **stamps the checksum over the damaged header**, and the
  next boot reports IC23 **valid** (stored 0x0888B217): the instrument would carry on with overwritten settings
  and the first third of the panel memories, without a word.
- So on a unit whose IC23 repeats every 256 KB (the SURVEY2 dump will say), today's Another World builds do not
  merely fail: they corrupt the stored settings and memories in a way the firmware accepts. If it does not
  repeat, the game reads open bus and still cannot run. The design that keeps the game out of IC23 is in
  `research-scratch/aw-memory-plan/` (see `OVERLAY-GAPS.md` G6).

Before and after this change (`notes/core-port-2026-10-19/ab_boot.sh` and `oracle_ab.sh`, the published
binary `7ee415f7…` against this build):

| case          | snapshots (2 3 4 5 6 8 12 20 45 s) |
|---------------|------------------------------------|
| kn7000 v16    | 9 of 9 identical                   |
| kn7000 v15    | 9 of 9 identical                   |
| kn7000 v13    | 9 of 9 identical                   |
| kn7000 sp7001 | 9 of 9 identical                   |
| kn6000        | 9 of 9 identical                   |
| kn6500        | 9 of 9 identical                   |
| kn2400        | 9 of 9 identical                   |
| kn2600        | 9 of 9 identical                   |

The gate's KN7000 audio oracle gives `bd02a9c15b580d6b4b4c0a42f78a1fcb` on both binaries. `tools/gate.sh` on the
published build: 17 passed, 0 failed, 1 skipped (kn1500, no screen device). The binary built
from the commit (`ed41d01b5f443b0ddba4b30264631d71`) is byte-identical to the one these runs used.

## Scripts

| script             | question it answers                                                                                                                                             |
|--------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `check_ic23.sh`    | does IC23 survive a POWER OFF and a reboot, and what does the firmware do with a damaged header or store?                                                       |
| `ic23_probe.lua`   | (used by the above) the firmware's verdict, the stored and computed checksums, the 256 KB repeat; then POWER OFF or a plain exit, and when the power latch sets |
| `ic23_file.py`     | does a saved `ic23` file carry a valid checksum? (`--corrupt OFFSET` flips one byte)                                                                            |
| `aw_ic23_check.sh` | what does a session of the Another World SP7001 build do to IC23?                                                                                               |
| `aw_power.lua`     | (used by the above) start the game, POWER OFF at 60 s                                                                                                           |
| `ic23_diff.py`     | which regions of two saved IC23 images differ                                                                                                                   |
| `aw_tap44.lua`     | who reads and writes the IC23 window above its 256 KB while the Another World module loads, per PC                                                              |
| `nmi_trace.lua`    | what the CPU does after POWER OFF (how the missing work-RAM view was found: the NMI stub read zero)                                                             |
