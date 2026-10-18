# LCD-capture probes (`CaptureLcd`, `LCDCAPnn.BMP`)

Harnesses behind the LCD-capture findings of 2026-10-18 (notes/FINDINGS-kn7000-debug-screens.md
section 11; kn5000-docs kn7000-memory-dump-screen.md). They answer: which chords run `CaptureLcd`,
whether the gate byte at CPU `0x4840000F` really decides it, and what file it writes.

| file                 | question it answers                                                                                                 |
|----------------------|---------------------------------------------------------------------------------------------------------------------|
| `patch_gate.py`      | Make a scratch `kn7000_program_odd.rom` whose byte `0x4840000F` is `0xFF` (odd-file offset 7).                      |
| `split_even_odd.py`  | Split a linear program image into the even/odd pair the MAME set loads (used for the 942 image).                    |
| `mkfat12.py`         | Build a blank formatted 1.44 MB FAT12 floppy image (mtools is not installed).                                       |
| `run_runtime.sh`     | Run `lcdcap_runtime.lua` headless on the `stock`, `ff` or `942` ROM path, with floppy/SD media attached.            |
| `lcdcap_runtime.lua` | Press the four-corner chord and the DISPLAY HOLD + pads chord; log the masks, the capture counter and the file I/O. |
| `verify_chord.lua`   | Independent re-check: key order, extra held pairs, re-firing, the pads chord (cases A-E in its header).             |
| `verify_screens.lua` | Does the corner chord work on six different screens, and what do the four soft keys do there?                       |
| `run_verify.sh`      | Run `verify_chord.lua` headless.                                                                                    |
| `fat16_ls.py`        | List the root directory of the SD image after a run.                                                                |
| `check_bmp.py`       | Validate an `LCDCAPnn.BMP` header (640x240, 24 bpp, 460,854 bytes).                                                 |
| `cmp_snapshot.py`    | Compare a captured BMP with MAME's own snapshot, row by row at each vertical shift.                                 |

Setup: the scripts expect a ROM path built in a scratch directory (`roms_stock/kn7000`,
`roms_ff/kn7000` with the patched odd ROM, `roms_942/kn7000`); `run_runtime.sh` hard-codes the
emulator binary (`kn7000-emulator/kn7000`, built 2026-10-08) and `DG_DIR` (this repo's
`tools/dumpgrab/capture`, for `memdump_lib.lua`). Point them at your own paths before running.

Results on PROGRAM 941 (2026-10-18):

- Stock byte `0x16`: holding LCDL1 + LCDL5 + LCDR1 + LCDR5 brings the both-held accumulator
  `0x50021FE0` to `0x00110000`, and nothing is captured. The 1/4/5/8 chord opens MEMORY DUMP.
- Byte patched to `0xFF` (MAME warns WRONG CHECKSUMS; the firmware does not check): the 1/4/5/8 chord
  opens "Panel Simulator 2.1"; the corner chord fires `CaptureLcd` when the fourth key goes down
  (counter `0x50021FC8` +1, written at pc `0x484156C4`); so does DISPLAY HOLD, then PAD 1, then PAD 2.
- The floppy write fails in MAME (fmmopen -3; the floppy emulation moves no sector data). With the
  file API steered to the SD backend by a Lua tap (emulator-only), the firmware writes
  `C:\LCDCAP00.BMP`: 460,854 bytes, 640x240, 24 bpp, BI_RGB; it equals the screen shifted up by one
  row (BMP row y = framebuffer row y+1, 240 of 240 rows). The pads chord writes `LCDCAP01.BMP`.
  Numbering restarts at 00 on every boot and an existing file is replaced.
- The SP7001 build 942 image (byte `0xFF` natively) does not boot in this driver build.
