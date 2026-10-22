# Why the KN6000's boot screen is garbled (2026-10-22)

**Symptom.** From 3.8 s to 4.9 s of a KN6000 boot, the LCD shows a white line along the top, a black band, a
white area and a strip of coloured noise along the bottom. From 7.3 s the play screen is normal.

**Cause.** The boot screen is a 640x240 picture that the firmware copies out of the table ROM (IC13/IC14), which
has never been dumped. The driver loads a generated placeholder instead (`kn6000_table_fontph.rom`, CRC
`bb2a0e7f`), which holds only the KN7000's fonts. So the firmware finds no picture and draws the placeholder's
own bytes as one. The play screen needs only the fonts, which the placeholder supplies; its icons and pictures
are empty boxes, as the comment above `ROM_START(kn6000)` says.

## What the firmware does

The routine at `0x4C078055` (program `0x48478055`) draws the boot picture:

1. It reads `0x480000EC`, a table-ROM offset to an image directory, adds the table base `0x48000000`, and reads
   the directory's words at `+0x90` and `+0x94`. The source is the directory plus the word at `+0x90`.
2. On its first call (frame counter `0x50033A06` = 1), it calls the byte copy at `0x48404248` four times,
   `0x9600` bytes each: 153,600 bytes, one 640x240 8-bit picture, into the picture plane at `0x50225C2C`. Then
   it sets CLUT entries `0x20`-`0xCF` (`0x484202BF`). Later calls (`0x484780F6`) animate it.

In the placeholder, `0x480000EC` and the directory words read `0xFFFFFFFF`. The source then comes to
`0x48000000 - 1 - 1 = 0x47FFFFFE`, so the firmware copies the placeholder's first 153,600 bytes, from two bytes
before the table.

## The measurements

| question                                                  | probe                                           | result                                                                                                                                                                                                                               |
|-----------------------------------------------------------|-------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| when does the screen change during boot?                  | `snap.lua` (a snapshot every 0.1 s)             | 16 distinct frames to 12 s: blank to 3.7 s, the garbled picture changing every 0.1 s from 3.8 s to 4.9 s, the play screen from 7.3 s                                                                                                 |
| what does the firmware read from the table ROM, and when? | `tabtap.lua`                                    | at 3.6 s, 153,601 reads covering `0x48000000`-`0x480257FF` (640 x 240 = 153,600); otherwise header words and, from 6.9 s, the fonts (`0x48023000`-`0x48033FFF`)                                                                      |
| is the boot picture those bytes?                          | `planes.lua` at 4.5 s, then `compare_planes.py` | the UI index plane matches the table ROM at a shift of -2 in 153,598 of 153,600 bytes; the picture plane is identical to the index plane                                                                                             |
| which placeholder bytes make which part of the screen?    | `compare_planes.py`                             | rows 0-6: the `0xFF` header (white, CLUT `0xFF` = RGB555 240,240,240); rows 6-108: the zero block at `0x1000` (black, CLUT `0x00`); rows 108-227: `0xFF` fill (white); rows 227-239: the KN7000 font data from `0x237A4` (the noise) |
| which code reads the table ROM around the copy?           | `copypc.lua`                                    | `0x4C07805B`/`6E`/`71` read `0x480000EC`, `0x48000090`, `0x4800008C` at 3.6546 s; the copy loop `0x4C004252` then reads from `0x48000000`                                                                                            |

Binary: the published `kn7000`, md5 `7f1205b746cde8c45781ba9eed5a2565`. Runs use a copy of the published NVRAM.

## What would fix it

- **The real fix is a dump of IC13 (QSIGX3C16008) and IC14 (QSIGX3C16007).** They hold the boot picture, its
  directory (located through `0x480000EC`), and the KN6000's own fonts, icons and pictures.
- **A stopgap (not done):** give the placeholder a header word at `0xEC` that points to an empty directory, so
  the boot draws a blank screen instead of the placeholder's bytes. Like the fonts, it would be fabricated data
  and must stay marked as such.

The KN6500 was not checked. Its firmware reads the table ROM at `0x40010000`.

## Reproducing

```sh
N=~/compartilhado/kn7000_mame/notes/kn6000-boot-picture-2026-10-22
E=~/compartilhado/kn7000-emulator; R=~/compartilhado/tmp/kn6000-boot-gfx/run3   # scratch
mkdir -p $R/nv $R/cfg $R/snap && cp -r $E/nvram/kn6000 $R/nv/
cd $E && OUT_DIR=$R T_DUMP=4.5 DISPLAY=:0 ./kn7000 kn6000 -rompath ./roms -pluginspath ./plugins -skip_gameinfo \
    -window -nothrottle -sound none -nvram_directory $R/nv -cfg_directory $R/cfg -snapshot_directory $R/snap \
    -autoboot_script $N/planes.lua
python3 -I $N/compare_planes.py $R
```

`tabtap.lua` and `copypc.lua` run the same way (no `OUT_DIR`); they print `TABTAP` and `CP` lines to stderr.
`snap.lua` needs `-snapshot_directory DIR -snapname '%i'`. The program image for disassembly is
`../tg-release-kn6000-2026-10-22/mkprog6.py` (`dis6.sh prog.bin 0x4c078055 0x60`).
