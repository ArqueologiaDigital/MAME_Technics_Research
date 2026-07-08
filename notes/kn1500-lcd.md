# KN1500 — getting the boot to drive its LCD

Goal: emulate the SX-KN1500 far enough to observe what its boot code writes to the LCD
(a dedicated segment/dot-matrix panel, preserved as `kn1500_lcd.svg`, not a framebuffer).

## Driver is now buildable + runs (bundled)
Created `src/mame/matsushita/kn1500.cpp` (standalone, from the `mame-pr` draft): TMP95C061
(TLCS-900) @ 24 MHz, `SCREEN_TYPE_SVG` panel, IC15 program+rhythm halves. Per the user's
request it is **bundled into the single `kn7000` binary** (not a separate binary):
`build.sh` now symlinks it, registers it in `mame.lst`, and builds
`SOURCES=…/kn7000.cpp,…/kn1500.cpp`. The one `kn7000` binary now lists 6 drivers:
kn1500, kn2400, kn2600, kn6000, kn6500, kn7000. `verifyroms kn1500` = OK; it runs.

## Boot trace (MAME lua, robust `-seconds_to_run` + file-write)
The crt0 (`0xfe5f4f`, reached via reset `0xffff00`→`0xfffee0`) is a clean TMP95C061 SFR
setup. Then the boot enters a **RAM self-test** and stays there:
- Stall loop at **`0xfa047f`–`0xfa04a1`** (prog ROM, ic15 offset `0x1a047f`). Disassembled: a
  marching-pattern test — `ld D,(XIX); ld (XIX),0x5a; cp (XIX),0x5a; jr Z; (fail)or L,(XWA+8);
  ld (XIX+),D;` then the same with `0xa5`, `dec XBC`, loop while `XBC!=0`. Descriptor at `XWA`
  = `{+0: base, +4: count, +8: errflag}`.
- **It runs away:** the test pointer `XIX` has climbed to **`0x011fb0ad`** at t≈25s — *past* the
  24-bit (16 MB) address space. The driver maps a **7.5 MB placeholder RAM** (`0x000000–0x77ffff`)
  and the test size/region is wrong for it, so the test grinds for tens of seconds (or never
  terminates), and no reads/writes land in `0x000000–0xbfffff` after ~t=20.
- **Consequence:** the boot never reaches the LCD-drawing phase, so nothing is written to the
  display yet. (One long run also SEGFAULTED MAME — likely the boot hitting an unmodeled state if
  it does escape the test; to revisit.)

## LCD panel (SVG)
`kn1500_lcd.svg` (600×232) has 142 paths, **40 with `<title>` grid coordinates `0.0.X.Y`**
(X=0–4, Y=0–7 → a 5×8 dot block = one dot-matrix character-cell template). These are meant to be
driven as dynamic segments (the hh_sm510 pattern); the driver currently renders the SVG
**statically** and does not yet toggle segments from CPU output.

## NEXT
1. **Fix the RAM map** to the real KN1500 layout so the RAM self-test terminates and the boot
   proceeds. Decode the TMP95C061 chip-select/memory-controller config the crt0 writes
   (`ld (0x1a..0x2d),…` = block CS / start-address / wait regs), or use the service manual, to
   size RAM correctly (7.5 MB is a placeholder). Also check the segfault when the boot escapes.
2. Once past the test, find how the LCD is addressed — memory-mapped controller VRAM (a
   T6963C-style chip on a chip-select) vs on-chip SIO/ports — by tapping writes in the post-test
   window, then map its output to the SVG's `0.0.X.Y` segments so we can *see* the display.

## Service manual obtained (2026-07 — user-provided `technics_sx-kn1500_sm.pdf`)
Authoritative hardware map (block diagram II-3 + MAIN(A) schematic II-9 + crt0 chip-select setup):
- **Work RAM = IC21 `M5M4417AJ7S`, 4 Mbit = 512 KB DRAM** at **CS3 = 0x000000** (crt0 sets MSAR3=0x00,
  MAMR3=0x0f → ~1 MB CS window; the 512 KB chip mirrors within it). **The driver's 7.5 MB RAM was wrong.**
- ROMs: **IC15** (16 Mbit=2 MB program mask ROM `QSIGT3C16072`) at **CS2 = 0xe00000**; **IC17** (2 MB
  rhythm/accomp data) at **CS1 = 0xc00000**; **IC18/IC19** (4 Mbit=512 KB EPROMs); **CS0 = 0x780000** (MSAR0=0x78).
- Wave ROMs: IC25 (32 Mbit) + IC26 (8 Mbit) `QSIGU…` — undumped.
- crt0 MSAR/MAMR (SFRs 0x3c-0x3f, 0x5c-0x5f): MSAR0=0x78/MAMR0=0x3f, MSAR1=0xc0/MAMR1=0x7f,
  MSAR2=0xe0/MAMR2=0x3f, MSAR3=0x00/MAMR3=0x0f.
- **LCD = HYBRID** (custom icons + a pixel-grid region, per the user + the SVG's `0.0.X.Y` 5×8 dot cells).
  Interface = **HD44780-style 8-bit parallel bus** (user's read of the schematic): RS/command-data (`DSP0/CDR`),
  R/W, E, D0-D7 (`D80-D87`), chip-select `LCDCS`/`DSPCS` (connector CN7). MAME has an `hd44780` device to try.
- Self-diagnostic (I-11): RAM(IC21)+ROM(IC15,17-20) check needs a CHECKING DEVICE on CN12; **LCD test #5 =
  "all dots light"** → confirms a dot-matrix pixel area.

**Driver fix (committed):** RAM map corrected to `map(0x000000,0x07ffff).ram().mirror(0x080000)` (512 KB in
the 1 MB CS3 window) + ROM comments. CS0/LCD still TODO.

## Remaining blocker: RAM-test runaway is NOT a size issue
Even with the correct 512 KB RAM, the boot still spins forever in the marching-pattern loop `0xfa047f`. The
test reads its descriptor via `XWA0` (`ld XIX,(XWA); ld XBC,(XWA+4)`), but `XWA0`=`0xf38b24` points at a
**table of small negative 16-bit values (`0xffXX`, every odd byte 0xff)** — not a `{base,count}` — so
base=`0xffdefff2`, count huge → runaway. So `XWA0` is set WRONG before the test. Likely a TLCS-900 CPU-core
issue (tmp95c061 register-bank / addressing mode) or a missing early setup step. **NEXT:** trace the caller
of the RAM-test function to see where `XWA0` is (mis)computed; compare against the KN5000 (tmp94c241) which
shares the core. Once the boot clears the test, wire the LCD (HD44780 device at the LCDCS address — likely a
sub-decode near CS0 `0x780000`) and map its output to the SVG icons + pixel grid.
