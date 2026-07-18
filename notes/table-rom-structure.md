# KN7000 table ROM structure — see notes/table-rom-format.md

The table ROM's resource-archive format was already decoded in **`notes/table-rom-format.md`**
(directory of u32 chunk offsets; `TCMP` code/style container; `TPAD` / "Technics Pads"; 119 embedded
standard JFIF JPEGs; TCMP per-record + rhythm-pattern event grammar). That file is authoritative —
this one is a stub to avoid duplication.

An independent re-derivation (2026-07-08, walking the de-interleaved 4 MB image) reproduced the same
85-entry directory and confirmed all 117–119 JPEG streams decode with an ordinary JFIF decoder
(reinforcing that the boot-splash "garbage" is a firmware/emulation decoder bug, not a bad format).

**One small correction to note:** directory entry **[83] @0x483E828C** reads `"Technics Rhythms"`
in the ROM (`54 65 63 68 6e 69 63 73 20 52 68 79 74 68 6d 73`), i.e. a rhythm resource — not
"Technics Pads" as an earlier draft listed it. Named `TechnicsRhythmsTable` in kn7000_manual.sym.

## Name-resource probe windows -> physical ICs (Phase A, 2026-07-18)

Deliverable of Phase A in `notes/sequenced-playback-and-style-data-rootcause.md`: map the
"Technics Rhythms" prober's windows (prober 0x4843D6DC / selector 0x4843385E) to physical
chips using the KN7000 service manual (`KN7000/service_manual/technics_sx-kn7000_keyboard.pdf`,
160 pp; page numbers below are PDF pages).

### The complete CPU-bus memory inventory (service manual)

Sources: block diagram **p.79** ("SX-KN7000 BLOCK 1/2 DIAGRAM (1/2)"), MAIN 1/5 schematic
sheet 1 **p.100** (CPU + decoders) and sheet 2 **p.102** (all memory chips, part numbers,
widths, address pins; duplicate scan p.103/p.141), replacement parts list **p.54**, FLASH
servicing section 9 **pp.37-40**.

| IC | part number | schematic label | organization | role |
|---|---|---|---|---|
| IC4 | MN103002A | 32bit MICRO CONTROLLER | — | main CPU (p.100) |
| IC12, IC13 | C3ABMG000166 | 16M DRAM ×2 | 16 Mbit each, D16-31 / D0-15, A(2)-A(13) mux | 4 MB work DRAM pair (RAS/CAS) |
| IC14, IC15 | C3BBHG000048 | 1M FAST SRAM×16 ×2 | 1 Mbit ×16 each, A(2)-A(17) | 256 KB fast SRAM pair |
| IC16, IC17 | C3FBNG000016 (service kit RFKFXKN7000) | 32M FLASH ×2 | 32 Mbit = 4 MB each, ×16, D16-31 / D0-15, A(2)-A(22) | **PROGRAM ROM pair** (sec. 9.4.1) — 8 MB as a 32-bit interleaved pair |
| IC18 | C3CBND000046 | 64M ROM | 64 Mbit = 8 MB, ×16 on D16-31, A(1)-A(21) + top pin AD21 via **JP7** | **CUSTOM DATA ROM**, *second production lots* (sec. 9.4.2) |
| IC20 | C3FBMD000050 | 32M FLASH | 32 Mbit = 4 MB, ×16 on D16-31, A(1)-A(21) | **CUSTOM DATA position, *first* lots** — alternate population of the same site (dashed box + jumper table on p.102: "first: IC20+JP, no IC18 / second: IC18, no IC20+JP"; "*We do not supply IC20 as replacement parts*") |
| IC19 | C3CBMD000098 | 64M ROM | 64 Mbit = 8 MB, ×16 on D16-31, A(1)-A(21)+AD21, WE site via JP13 | factory-programmed data ROM |
| IC21 | C3FBMD000050 | 32M FLASH | 32 Mbit = 4 MB, ×16 on D16-31, A(1)-A(21) | factory-programmed data flash (same part as IC20) |
| IC23 | C3BBJG000011 | 2M SRAM×16 | 2 Mbit = 256 KB, ×16, A(1)-A(17) | battery-backed backup SRAM (battery switch Q3 UN5216 nearby) |

Key structural facts:

- **IC16/IC17 hold BOTH the table AND the program.** Each chip is 32 Mbit (4 MB); the pair is
  8 MB wide-word (A(2)-A(22)) = exactly table 0x48000000-0x483FFFFF + program
  0x48400000-0x487FFFFF on CS2. Our dumps agree perfectly: per chip 2 MB table half + 2 MB
  program half = 4 MB = 32 Mbit. This also explains why TABLE update floppies (JKT1/JKT2.SLD)
  exist for a "ROM": the table is just the lower half of the program flash pair. There is **no
  separate table-ROM chip** on the KN7000 (unlike KN5000 IC1/IC3).
- **The custom-data chip is one 16-bit device** (8 MB IC18 on late units, 4 MB IC20 on early
  units). Section 9 (p.37-40) is explicit: *"The CUSTOM DATA ROM stores RHYTHM & ACCOMP data
  for the RHYTHM GROUP/CUSTOM function. The initial RHYTHM & ACCOMP data is factory-set in
  the CUSTOM DATA ROM at the time of shipping"*, and it is re-defaulted with the INITIAL DATA
  DISK (CTMINI) — i.e. factory rhythm data and user COMPOSER data share this flash.
- **Only two factory-programmed data chips exist besides it**: IC21 (4 MB flash) and IC19
  (8 MB mask ROM). Note IC19's 8 MB = exactly the driver's `0x800000` "picture" NO_DUMP
  region size.
- **Chip selects** (p.100): CPU pins 51-54 = CS0, RAS1/CS1, RAS2/CS2, RAS3/CS3; pins 33/34/36/39
  = A26/CS4/RAS4, **A27/CS5**, A28/CS6, A31/CS7. Firmware addresses put the data flashes in the
  CS5 region 0x54000000-0x57FFFFFF (and I/O at 0x98xxxxxx = CS6 via the 0x40000000 uncached
  mirror; IC1 74VHC138 decodes A(16-18) into 64 KB peripheral selects there — its Y1=FDC.CS
  matches FDC@0x98010000). A 74VHC139 half (IC3, p.100) decodes **A(23)/A(24)** quadrants for
  the data-chip selects; notably its **1Y1 output (A24=0, A23=1 quadrant) is drawn NOT
  CONNECTED**. The custom chip must answer at BOTH 0x56000000 (read view, A23=0) and
  0x56800000 ≡ 0x96800000 (AMD command window, A23=1), so its CE ignores A(23) (coarser gate,
  not a single 139 output). Full CE gate equations were not traced (dense two-sheet wire maze);
  everything below marks that residual uncertainty.

### Window -> chip table

| probe window | what decodes there (service-manual evidence) | confidence | evidence |
|---|---|---|---|
| 0x48010000 (table+0x10000) | IC16/IC17 program-flash pair, table half. In our dump this offset is erased fill (0xF7). | HIGH | p.102 + p.54 + sec 9.4.1; dump geometry match |
| 0x40010000 | CS0 region 0x40000000: **no KN7000 chip decodes here** — the p.79/p.102 inventory is complete and fully assigned elsewhere. Presumed sibling-model window (shared codebase; KN6500 SM shows the same architecture: program IC11/IC12 flash, custom IC18, factory mask ROMs IC13 C3FBMD000069 / IC14 C3FBMD000068). | HIGH that nothing is there on KN7000; sibling attribution = inference, unverified | p.100 (CS pins), p.79/p.102 (inventory) |
| 0x40610000 | same as 0x40010000 (image base +0x600000, header +0x10000) | same | same |
| 0x40810000 | same as 0x40010000 (image base +0x800000, header +0x10000) | same | same |
| 0x54E00000 | CS5 region. **No plausible KN7000 aperture** for the FULL resource: every candidate chip is a 4/8 MB device on an 8/16 MB-aligned select, so a base at +0xE00000 leaves at most 2 MB of contiguous chip before a boundary, but the real container's subtable references records out to **+0x22B434 (~2.3 MB)** — it overruns/wraps under every decode variant (incl. the "alias of the custom flash at in-chip 0x600000/0x200000" reading). Also IC3's 1Y1 (the 0x54800000-0x54FFFFFF quadrant select) is N.C. | MEDIUM-HIGH (negative) | p.102 chip sizes + resource-size arithmetic; p.100 IC3 |
| 0x54E10000 | = 0x54E00000 image probed at header +0x10000; same verdict | same | same |
| 0x56000000 (read) + 0x96800000 (AMD cmd) | **CUSTOM DATA flash: IC18 (8 MB, late units) / IC20 (4 MB, early units)** — the one field-writable data chip; factory-set RHYTHM & ACCOMP + user COMPOSER data | HIGH identity (sec. 9 explicit); address from firmware RE (not in SM) | pp.37-40, p.102 dashed box, p.54 |
| 0x57000000 (kn7000.sym "factory") | **IC21, 32 Mbit factory flash** — by elimination the only remaining flash; size-class twin of KN5000's rhythm_data IC14 (32 Mbit @0x400000) | MEDIUM | p.102/p.54 + elimination + KN5000 analogy |
| 0x57800000 (firmware "picture") | **IC19, 64 Mbit mask ROM** (8 MB = the driver's picture region size) | MEDIUM | p.102/p.54 + elimination |

Probe-list pattern worth noting: the six probes are "resource header at image base or
base+0x10000" over historical layouts (0x40000000/0x40600000/0x40800000/0x48000000/
0x54E00000) — a shared-codebase sweep across model generations, not six KN7000 apertures.

### Verdict on 0x54E00000

**It is a software last-resort constant, not a credible physical KN7000 aperture.** The
prober returns it unconditionally, but (a) no documented chip/select combination yields
>= 2.3 MB contiguous from a +0xE00000 base, and (b) the quadrant select covering it is
unconnected on the schematic. The KN7000's real "Technics Rhythms" home is on one of the
three data chips, most plausibly **IC21 (0x57000000 factory flash — the KN5000 rhythm_data
analogue)** or the **factory-set portion of the custom flash IC18/IC20 (0x56000000)**, per
the service manual's own description of the custom chip's contents.

Consequences:
- **Phase C (real-HW dump) targets**: 0x56000000 (custom, full chip), 0x57000000 (IC21),
  0x57800000 (IC19) — and a live read of 0x54E00000/0x54E10000 on real hardware to record
  what (if anything) answers there; that single read settles the alias question for good.
- **Emulator fix**: installing the **labeled-SYNTHETIC** name resource at 0x54E00000 remains
  the honest interim (Phase D): it is the address the firmware itself elects unconditionally,
  it collides with no dumped or dumpable chip mapping, and it must be labeled synthetic per
  the integrity policy. A faithful fix later = map the real IC21/custom dumps and let the
  earlier probes hit.
