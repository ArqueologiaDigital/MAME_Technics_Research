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
