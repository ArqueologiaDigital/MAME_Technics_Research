# Slide-show probes: FEATURE.PRE / .ACT presentations running in MAME (2026-10-18)

Committed from the research lane's scratch (kn5000-docs page kn7000-slideshow.md quotes these runs).
Paths inside the scripts and below point at that scratch layout (samples/, mamerun/); adjust them before
re-running. The large SD and floppy images were not kept: their recipes are below. Every script names the question it answers in its
header. Python tools run from anywhere with `python3 -I`; MAME runs are started from
`mamerun/` (cwd) with the overlay build `/home/fsanches/compartilhado/kn7000_mame_build/kn7000`
(md5 30a3d132381e3b8bd0dabb7cf2a0c9fe, the 04:09 build) and ROM path
`/home/fsanches/compartilhado/technics_romsets` (kn7000.zip md5 358573de0e9a9827d228ca8ae91d7855).
The Python tools read `kn7000_disassembly/baserom/kn7000_program.rom`
(md5 38079d4c334c46dca061a6339739dbbf).

## Scripts

| script                   | question it answers                                                                                                      | run                                                                                    |
|--------------------------|--------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| `demo_song_extract.py`   | record + pages + sounds of built-in demo song N as func_48457355 inflates them; which 0x8A picture events the pages hold | `python3 -I demo_song_extract.py ROM 1 demosongs`                                      |
| `sqt_jkd.py`             | read/write KN7000 'J KD' .SQT exactly as the decoder func_48533F61 reads them (LZSS, ring 0x2000, r0 = 0x1FF6)           | `python3 -I sqt_jkd.py info F.SQT [prefix]`, `build OUT REC PAGES [TEMPLATE_PART1]`    |
| `build_presentation.py`  | the minimal change that turns CA-6FP01 "Weserbergland" into a set the KN7000 accepts                                     | `python3 -I build_presentation.py ../samples/extract/ca6fp01 demosongs presentation`   |
| `make_fat12.py`          | 1.44 MB FAT12 image from files (copy of featurepre/make_fat12.py)                                                        | `python3 -I make_fat12.py weserl_floppy.img NAME=path ...`                             |
| `build_seq_sd.py`        | SD image for the sequencer route: real KN7000 card copy, TFLD001/01001KN7.SQT/.ACT replaced, PIC01..08.JPG added         | see header                                                                             |
| `pres_probe.lua`         | does the KN7000-form FEATURE presentation load on the DEMONSTRATION screen, and do its pictures change as the song plays | see header (env PROBE_TAG, FEATURE_IMG, FORCE_PRESENCE, FORCE_SD, RUN_END, SNAP_DELAY) |
| `seq_probe.lua`          | does an ordinary SD song load bring <song>.ACT + pictures into the main pool, and do they show at PIC points             | see header (env PROBE_TAG, SKIP_SEQPLAY, SEQ_RESET, T_PLAY, RUN_END)                   |
| `render_fb.py`           | what picture work RAM holds for the LCD, independent of MAME's renderer (re-implements LcdOut 0x48414D71)                | `python3 -I render_fb.py FB.bin PLANE2.bin PAL565.bin OUT.png`                         |
| `make_contact.py`        | LCD crops (640x240 at (180,78) of a 1000x750 snapshot, or a 640x240 render as is), captioned, in one PNG                 | `python3 -I make_contact.py OUT.png COLS img.png=caption ...`                          |
| `identify_frames.py`     | which source JPEG is on the LCD in a snapshot or RAM render (mean abs grey difference, best and second best)             | `python3 -I identify_frames.py PICDIR img.png ...`                                     |
| `kn6000_sqt_pic_scan.py` | do the KN6000 'I KD' presentation songs carry KN7000-style 0x8A,n,0x00/0x40 picture events (answer: none found)          | `python3 -I kn6000_sqt_pic_scan.py ../samples/extract/ca6fp0*/*.[sS][qQ][tT]`          |
| `repad.py`               | re-align the Markdown tables of a file (copy of featurepre/repad.py)                                                     | `python3 -I repad.py README.md`                                                        |

## Runs

| tag  | media                                          | forcing                                               | result                                                                                                                          | log                |
|------|------------------------------------------------|-------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|--------------------|
| FL1  | weserl_floppy.img (FAT12) at t=25              | DSKCHG cleared (FORCE_PRESENCE) only                  | insert event reaches MdDemo, title 0xF00CF ok, floppy media probe func_4854DAA5 = 0xFFFFFFF9 (-7): stops, nothing read          | pres_probe_FL1.log |
| SD1  | floppy + sd_weserl.img (same files, SD root)   | + floppy gates forced, drive byte 0x5007125A = 1 (SD) | full load; demo song 0xD; 18 PIC events n = 0..17; n = 1..17 show ACT n; n = 0 shows NO PICTURE DATA                            | pres_probe_SD1.log |
| SD2  | same as SD1                                    | same                                                  | SD1 repeated: SswDrawImage_entry per event, snapshots 2.8 s after each event, FB + PICTURE_PLANE2 + RGB565 dumps, song RAM dump | pres_probe_SD2.log |
| SEQ1 | sd_seq.img (real card copy, TFLD001 replaced)  | none                                                  | SD LOAD loads .SQT, .ACT, 8 pictures to the main pool; my SEQUENCER PLAY press then turned SEQ PLAY off: no playback            | seq_probe_SEQ1.log |
| SEQ2 | sd_seq2.img (songs 2..10 = real empty records) | none                                                  | same press mistake; SeqActFileLoad -> SswSongActLoad -> SswActOpen order; records/pages in RAM == file; stopped early           | seq_probe_SEQ2.log |
| SEQ3 | sd_seq2.img                                    | none                                                  | LOAD ends on SEQUENCER PLAY; START/STOP plays song 1; PIC 1..8 draw PIC01..08 from the main pool; 0 and 9..17 NO PICTURE DATA   | seq_probe_SEQ3.log |

Pictures: `SD1_contact.png` (MAME LCD, one frame per event), `SD2_ram_render_contact.png`
(work-RAM renders 2.8 s after each event), `SEQ3_contact.png` (sequencer route).
`identify_SD1.out`, `identify_SD2_ram.out`: identify_frames.py output for those frames.

## Recipes for the deleted SD images (126 MB each, regenerable)

    R=/home/fsanches/compartilhado/tmp/kn7000-act/runtime
    A=/home/fsanches/compartilhado/kn7000_disassembly/tools/sd_addfile.py
    # sd_weserl.img (SD1, SD2): empty card + the presentation/ files in the root
    cp /home/fsanches/compartilhado/technics_roms/media/empty_sdcard.img $R/sd_weserl.img; chmod u+w $R/sd_weserl.img
    args=""; for f in $R/presentation/*; do args="$args $(basename $f) $f"; done
    python3 -I $A $R/sd_weserl.img $args
    # sd_seq.img (SEQ1) and sd_seq2.img (SEQ2, SEQ3)
    REAL=/home/fsanches/compartilhado/technics_roms/media/sdcard_from_real_kn7000.img
    H=/home/fsanches/compartilhado/tmp/kn7000-act/samples/extract/ca6fp03
    python3 -I $R/build_seq_sd.py $REAL $R/sd_seq.img $H $R/presentation $A
    python3 -I $R/sqt_jkd.py build $R/demosongs/SEQ2_01001KN7.SQT $R/demosongs/demo1_record.bin \
        $R/demosongs/demo1_pages.bin $R/demosongs/real01001_part1.bin
    python3 -I $R/build_seq_sd.py $REAL $R/sd_seq2.img $H $R/presentation $A $R/demosongs/SEQ2_01001KN7.SQT

| image                       | md5 when built (unchanged after the runs) |
|-----------------------------|-------------------------------------------|
| sd_weserl.img (deleted)     | f72d5e28c3129107475511ffd6bb583e          |
| sd_seq.img (deleted)        | 436b8b7bed86ef191e95d451ed0f35df          |
| sd_seq2.img (deleted)       | e9aa126dcad8f9116b58b0933d349849          |
| weserl_floppy.img (kept)    | 97ce6a44132ec375ae833cd6a1206066          |
| presentation/WESERL.SQT     | 60efd39e4924fc4bb02d32cfc9be3cff          |
| demosongs/SEQ2_01001KN7.SQT | a4147558d1e985122e3afd1cd7b7d7fd          |

`real01001_part1.bin` is part 1 of 01001KN7.SQT decoded from the real card
(`sqt_jkd.py info ../featurepre/sdB_files/HANDY.SQT demosongs/real01001`).
The real card image itself (md5 c3bcea2346cb3bb7d803e8c48aebce78) was only copied, never written.
