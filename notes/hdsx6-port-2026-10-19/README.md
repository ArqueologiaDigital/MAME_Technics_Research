# KN6000 expansion, PR #16220 (v5), carried in the overlay (2026-10-19)

Item G1 of `OVERLAY-GAPS.md`. Felipe asked for it on 2026-10-19, before the PR merges.

## What was done

**Base tree** (`~/compartilhado/mame`, branch `kn7000-base`), five commits:

| commit        | what                                                                                         |
|---------------|----------------------------------------------------------------------------------------------|
| `892c985aa55` | reverts the August HD-SX3 draft (`473fb321714`, `e31a226b4a8`, `61e91b50e69`, `599f077cc6a`) |
| `722f483beca` | v5 `745ebc0f9c7`: machine/atahle accepts SET FEATURES 0x55 (disable read look-ahead)         |
| `795c8944b09` | v5 `57ea86e858a`: the CN105 connector, `bus/technics/kn6000/kn6000_expansion.{h,cpp}`        |
| `a1b8459fc90` | v5 `b7004fd1726`: the HD-SX3 hard disk unit                                                  |
| `81132bf65c8` | v5 `d497bed5caf`: renamed to the HD-SX6, `hdsx6.{h,cpp}`                                     |

The draft named the wrong connector (CN106), had no HDDCS window or ATA interface, created its RAM at run
time, and nothing installed it. After the revert, v5's four commits cherry-picked without conflicts; the
card files and the atahle change are byte-identical to `technics-kn6000-expansion-v5`
(`git diff technics-kn6000-expansion-v5 kn7000-base -- src/devices/bus/technics/kn6000 src/devices/machine/atahle.*`
prints nothing). v5's hunk in the base copy of `kn7000.cpp` is hidden by the overlay's own file.

**Overlay** `src/mame/matsushita/kn7000.cpp`, by hand (its single `kn7000_state` is not upstream's class
split): the include, an `optional_device<kn6000_expansion_connector> m_exp`, `KN6000_EXPANSION(config,
m_exp, kn6000_expansion_intf, nullptr)` in `kn6000()` (so `kn6500()` inherits it), and
`m_exp->program_map(...)` at the end of `machine_start()`. The card's windows (ISOROM 0x97800000-0x97FFFFFF,
HDDCS 0x98060000-0x9806FFFF) are installed over the overlay's vram share and `io_r`/`io_w` there. With the
slot empty, nothing changes (`notes/core-port-2026-10-19/`: kn6000 and kn6500 screens identical).

**Publish** (`tools/publish-binary.sh` step 2e): the card's flash image is
`technics_roms/roms/hdsx3/hd-sx3_v1_1.bin` (CRC 83b8a6f1, the bytes v5's `ROM_START` names). The device asks
for `hdsx6/hd-sx6_v1_1_rev3.bin`, so it is published under that name. The generated `run.sh` documents the
command line.

**`tools/sync-check.sh`** expected the HD-SX3 files and a `technics-kn6000-expansion` branch in `mame-pr`; it
now checks the HD-SX6 files, the atahle marker and branch `technics-kn6000-expansion-v5` (override with
`MAME_PR_BRANCH`), and reports IN SYNC.

## Running it

    cd ~/compartilhado/kn7000-emulator
    chdman createhd -o disk.chd -chs 4161,16,63 -ss 512 -c none     # once: a blank 2 GB disk
    ./run.sh kn6000 -window -exp hdsx6 -harddisk2 disk.chd

The disk goes in `-harddisk2`: the overlay's KN6000 and KN6500 inherit the KN7000's SD card slot, which
takes `-harddisk1`. Upstream's KN6000 has no SD slot, so the PR's own instructions say `-hard`. The firmware
wants a disk of at least about 641 MiB (PR README).

## Checks

`check_hdsx6.sh BINARY OUT [ROMPATH]` boots kn6000 and kn6500 with the card and a blank 700 MiB disk for 30 s,
under the PR's own probe (`KN7000/tools/mame-pr-planning/kn6000-expansion-pr/probes/hdsx3_tap.lua`).

| run                                   | kn6000                                       | kn6500     |
|---------------------------------------|----------------------------------------------|------------|
| build tree, published ROMs + `hdsx6/` | IDENTIFY once, 512 data-port reads           | the same   |
| ATA commands, in order                | ef ef ef ef c6 ec c4 94                      | the same   |
| published folder (`7ee415f7…`), 6.0 s | the splash (byte-identical to the PNG below) | the splash |
| published folder, ATA                 | IDENTIFY once, 512 reads, same 8 commands    | the same   |

`tools/gate.sh` on the same published binary: 17 passed, 0 failed, 1 skipped (kn1500, no screen device).

The ATA sequence is the PR's own (`runs/v4-hdsx6-disk.txt`): SET FEATURES four times (features 03, 66, 55, 55), SET
MULTIPLE, IDENTIFY, READ MULTIPLE, STANDBY IMMEDIATE.

The overlay's KN6000 reaches the card later than upstream's: board code first runs at 5.68 s (3.12 s in the
PR's runs) and IDENTIFY goes out at 5.85 s (3.26 s). So the splash is not at the PR's 3.2 s. A snapshot sweep
(2.9-4.5 s and 5.5-6.7 s, every 0.05 s) finds it from 5.85 s to 6.35 s:

- `hdsx6-splash-kn6000-6.00s.png`: the board's own "HD-SX6 First edition / Start-up ... please wait!"
  screen, drawn into the host's RGB565 LCD image at 0x9CE00000;
- `hdsx6-fitted-kn6000-29s.png`: the play screen afterwards, with the card fitted.

Why the overlay's KN6000 boot is 2.6 s slower to that point than upstream's was not investigated.

## Not modelled (as in the PR)

HDDINT (IRQ1) and PP.INT (IRQ4); the HD-SX6's USB, parallel port and separate-output DACs; the upper half of
the flash, which A20 hides. Format, save and load were never exercised: the KN6000 table ROMs (IC13/IC14) are
undumped. PR #16220's driver hunk also carries a misleading `FIXME` about DRQ (`OVERLAY-GAPS.md`, side
findings); the overlay does not take that hunk.
