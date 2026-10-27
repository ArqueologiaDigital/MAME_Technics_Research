# The KN7000's chip-select windows, as the owner's unit reads them (2026-10-27)

**Question:** after `machine_start` models the chips' copies and the open bus, does MAME's KN7000 read every window
as the owner's instrument does?

The unit's evidence:
- **CS0, CS5, IC23:** the cnv_romdump ROM survey, passes 4 and 5 (technics_roms
  `real_dump_v1.3_b893/README.md`).
- **CS3, CS4:** Pinball PFT18 (`Pinball/kn7000/notes/ram-inventory-2026-10-27/pfram-unit-893.txt`).

| window                                 | on the unit                                                          |
|----------------------------------------|----------------------------------------------------------------------|
| CS0 `0x40000000`-`0x407FFFFF`          | IC18's 4 MB, twice                                                   |
| CS0 `0x40800000`-`0x43FFFFFF`          | open bus, 0xFF (empty expansion slots at 0x41000000, 0x41800000 too) |
| CS3 `0x4C000000` (uncached `0x8C`)     | the library SRAM's 256 KB, repeating through 64 MB                   |
| CS4 `0x50000000` (uncached `0x90`)     | the work DRAM's 4 MB, repeating through 64 MB                        |
| CS5 `0x54800000`-`0x54FFFFFF`          | IC21's 2 MB, four times                                              |
| CS5 `0x55800000`-`0x55FFFFFF`          | IC19's 2 MB, four times                                              |
| CS5 `0x56xxxxxx`, `0x57xxxxxx`         | the same as `0x54`, `0x55` (CS5 ignores A25)                         |
| CS5 elsewhere (uncached `0x94`-`0x97`) | open bus, 0xFF (empty slots at 0x56000000, 0x57000000 too)           |

`bus_check.lua` reads each of these in MAME after 30 s of boot. It also sums IC19's 2 MB at `0x97800000` as
little-endian halfwords, the service ROM test's way (`0x4849FD9E`, OVERLAY-GAPS G7), and wants 0x21D8:

    cd ~/compartilhado/kn7000-emulator && ./kn7000 kn7000 -bios v13 -rompath ./roms -pluginspath ./plugins \
      -skip_gameinfo -window -nothrottle -autoboot_script <here>/bus_check.lua

`bus_check.out` is the run of the build of 2026-10-27 (the CS3/CS4 mirrors, `4fe2f1f`, and the CS0/CS5 windows):
9 of 9 pass. Before, CS3 was 16 MB of plain RAM and the uncached CS5 view 64 MB of RAM. The empty windows read 0x00,
and IC21 and IC19 were at one address each.
