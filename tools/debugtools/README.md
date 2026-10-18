# DEBUG TOOLS probes: DEBUG MODE and BITMAP LOAD

MAME harnesses behind the 2026-10-18 findings on the hidden DEBUG TOOLS screen
(notes/FINDINGS-kn7000-debug-screens.md section 12; kn5000-docs kn7000-memory-dump-screen.md).
All run on PROGRAM 941 with the gate byte `0x4840000F` poked to `0xFF` from Lua after boot
(`manager.machine.memory.regions[":maincpu"]:write_u8(0x0F, 0xFF)`), then the 1/4/5/8 chord fed one
panel segment at a time (CPC_SEG5 0x30, CPC_SEG8 0x3C, CPC_SEG9 0x0C; wait for `0x50021FE0` = 0x01,
0x19, 0x99), then LCDR5. Launchers hard-code the emulator binary and scratch paths; edit them first.

| file               | question it answers                                                                                       |
|--------------------|-----------------------------------------------------------------------------------------------------------|
| `run_mame.sh`      | Launch `kn7000` with a scratch cfg/nvram/snapshot directory and one of the Lua scripts below.             |
| `rt_lib.lua`       | Shared helpers: wait for the LCD, press panel fields, read RAM, snapshot.                                 |
| `dm1.lua`          | Which balance column/direction changes DEBUG MODE (`u32 0x5015080C`), and is it a flip-flop?              |
| `dm2.lua`          | Effect 3: does the blank LCDL2 of REVERB & EFFECT open EFFECT DEBUG (title 0x3E) only with DEBUG MODE ON? |
| `dm3.lua`          | Effects 4 and 5: the APC SELECT wait-time window and the HELP page-number window.                         |
| `dm4.lua`          | Effects 1 and 2: the PART SETTING list and the APC REVERB SETTING extra DEPTH column.                     |
| `dm5.lua`          | Effect 4 reached through the mode/title enumerator (column 11, LCDR5 jumps).                              |
| `dm7.lua`          | Does DEBUG MODE survive a reset?                                                                          |
| `dm9.lua`          | Who zeroes `0x5015080C` on reset (write tap: crt0's .bss clear at pc `0x48410039`)?                       |
| `bl1.lua`          | BITMAP LOAD with real media: is a floppy (or SD) file listed and read?                                    |
| `gen_bmp.py`       | Write the BMP test set (8/4/1 bpp, taller than 240, top-down, 700 wide, 24 and 2 bpp to be rejected).     |
| `verify_probe.lua` | BITMAP LOAD: which columns step the file index, LOAD's open backend, and what Draw2BpFile draws per file. |
| `run_verify.sh`    | Launch `verify_probe.lua` headless.                                                                       |
| `check_dumps.py`   | Compare the dumped planes and palettes with the expected pixels of each test BMP.                         |

Results (2026-10-18): balance column 2 or 3 UP sets DEBUG MODE ON, DOWN sets OFF (columns 1 and 4 do
nothing); ON shows the five effects listed in the findings note; crt0 clears it on every reset. BITMAP
LOAD steps files with columns 5 or 6, LOAD is LCDR4; `Draw2BpFile` drew every accepted test file
pixel-exact (index + 0x20 in `0x500D4080`, palette slots 0x20..0xCF), rejected 24 and 2 bpp, cut a
taller image at 240 rows and an 8-bpp 640x240 file at 0x18000 bytes. The floppy listing stays empty in
MAME (its floppy reads no sectors), so the files were injected into RAM, or read from SD by forcing the
drive byte; neither is a user route.
