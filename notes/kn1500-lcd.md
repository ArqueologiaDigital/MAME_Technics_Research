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

## Remaining blocker: RAM-region descriptor table reads as garbage (8-bit-data ROM region)
Even with the correct 512 KB RAM, the boot spins forever in the marching-pattern loop `0xfa047f`. Corrected
diagnosis (earlier "XWA0 is set wrong" theory was mistaken):
- This is **early crt0 RAM-init code**, reached at **t=0 with SP=0 via a jump** from the crt0 — NOT a called
  service-mode self-test (so the CN12/held-keys input theory is out too).
- The pointer is computed **correctly**: `0xfa0460` does `A=E(region#); WA=E*0x0a; lda XBC,0xf38b24;
  XWA=exts(WA)+XBC; base=*(XWA); count=*(XWA+4)` — a table at **`0xf38b24`, stride 0x0a/entry**.
- The real problem is the **ROM data** there. The prog ROM (IC15) has a clear region split:
  - **8-bit-data** `0xe00000-0xe7ffff` + `0xf00000-0xf7ffff`: every ODD byte is `0xff` (8-bit values padded
    to 16-bit with `0xff`).
  - **16-bit code/data** `0xe80000-0xefffff` + `0xf80000-0xffffff` (the crt0 lives here): both lanes real.
  The descriptor table `0xf38b24` sits in an **8-bit region**, so a long read yields `base=0xffdefff2,
  count=0xfff2ff00` → the test walks off into unmapped space forever.
- On real hardware a long read there would ALSO pick up `0xff` high bytes — so either **(a) the ROM dump is
  wrong** for these 8-bit regions (the ICs are `BAD_DUMP`; the descriptor's high bytes should be real data),
  or **(b)** IC15 is physically a byte-organized/dual-die part that the raw `ROM_REGION16_LE` de-interleaves
  wrongly. (`ic15.rest` also shows `{byte,0xff}` here — `01 ff 00 ff…` — but it is the separate rhythm ROM,
  not IC15's high-byte lane. Note bus width does NOT explain it: a long read is 4 consecutive byte fetches
  either way.)

**NEXT:** this is a **dump / ROM-organization question**, not a RAM-size or pointer bug. Verify IC15's 8-bit
regions against a fresh read of the physical chip, or determine IC15's true byte organization from the chip
datasheet/markings. LCD work (HD44780 device on Port 7 → SVG) stays gated on the boot clearing this table.

## CONFIRMED (patch experiment): the dump is pervasively bad in the 8-bit regions
Injected a valid descriptor into the loaded ROM image at boot (MAME lua:
`regions[":prog"]:write_u32(0x138b24,0)` [base=0] + `write_u32(0x138b28,0x1000)` [tiny count]) and re-ran:
- **The boot PROCEEDS past the RAM test** — the PC leaves the `0xfa047f` marching loop. So the `0xf38b24`
  descriptor genuinely was the stall, exactly as diagnosed.
- **…then it immediately derails to `PC=0x000003`** (running garbage in low RAM). The crt0 keeps reading more
  tables/jump-vectors from the same 8-bit-data regions (`0xe00000-e7ffff`, `0xf00000-f7ffff` — ~half the
  program ROM), and they are ALL `{byte,0xff}` garbage, so the next computed jump target is garbage.

**Conclusion:** the SX-KN1500 cannot boot in emulation because **~half of IC15's program ROM (the 8-bit-data
regions) is unusable in this dump** — every 16-bit word reads as `{data_byte, 0xff}`, so any table/pointer
the firmware reads as a word/long is garbage. On real hardware those reads must return real data (the machine
works), so the dump ≠ the chip. This is a **BAD_DUMP that needs a verified physical re-read of IC15**
(`technics_qsigt3c16079…9649eai.ic15`), NOT a driver/emulation fix. (`ic15.rest` is the separate rhythm ROM
and shows the same `{byte,0xff}` pattern, so it is not IC15's missing high-byte lane.) Everything else is
ready: memory map correct, LCD path fully specified (HD44780 on CN7, Port-7 control → MAME `hd44780` device →
SVG). **Recommend: obtain a fresh IC15 dump; then the boot + LCD should come up with the work already done.**

## LCD interface pins (2026-07 — user schematic snippet)
The LCD/DSP control signals are the alternate functions of **CPU Port 7 (P70-P77, "PG" group)**, i.e. the
CPU **bit-bangs Port 7** to drive them (they are NOT MSAR/MAMR chip-selects):
`DSPCS, LCDCS, DSPC0, DSPWR, DSPRD, DSP0/CDR (=RS command/data), DSPRST, DSPRST2` on P70..P77.
So the LCD is an **HD44780-style parallel interface, port-driven**: `LCDCS` (chip-select/E), `DSPWR`/`DSPRD`
(write/read strobe), `DSP0/CDR` (RS), with the byte on the `D80-D87` data lines. Emulation plan: watch the
Port-7 writes (on-chip port register) + the data path, decode E/RS/RW into an `hd44780`-style controller,
then render its DDRAM/CGRAM + the custom icons onto the SVG. (Still gated on the RAM-test boot blocker.)

## LCD connector CN7 pinout (2026-07 — user schematic) — HD44780 CONFIRMED
CN7 is a standard **HD44780 parallel-LCD header** (14 pins): `1=E, 2=+5V, 3=VO (contrast, via Q12/R133),
4=RS, 5=R/W, 6=CS, 7..14=DB0..DB7`. Control lines are driven by the Port-7 DSP/LCD signals
(`LCDCS`, `DSPWR`, `DSPRD`, `DSP0/CDR`=RS/enable), and `DB0-DB7` come from a data latch (`Q0-Q7`). So the
first-attempt emulation is clear: instantiate MAME's **`hd44780` device**, feed it RS/E/R/W decoded from the
Port-7 writes and the data byte from the latch, and render its output onto the SVG (character/pixel area +
the custom icons). Blocked only by the RAM-test boot issue above.
