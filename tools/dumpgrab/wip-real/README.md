# Work in progress: adapting dumpgrab to real composite captures

**Stopped 2026-08-10 at Felipe's request** — the agent-driven image analysis was burning
tokens too fast. Everything here is *code*, salvaged from an interrupted run. From now on
this work happens by **running scripts locally** and reporting numbers, not by having a
model look at pictures.

## Ground rule for resuming

**No model reads images.** The loop is: run a script → it prints numbers → act on the
numbers. Images are opened only by `cv2`/`PIL` inside the scripts. If a decision genuinely
needs a human eye, the script writes a PNG and *Felipe* looks at it.

## What is here

Salvaged from four workers; only one (`r4-capture-side`) reported before the stop, so the
rest is unreviewed code of unknown quality. Treat it as raw material, not as a result.

| dir | intent |
|---|---|
| `r1-psf/` | fit panel geometry sub-pixel; estimate the blur kernel from the address column (known content); glyph confusion-distance at the measured PSF; extract exact font bitmaps from emulator frames |
| `r2-atlas/` | decode in the *blurred* domain — convolve templates with the measured PSF, fit whole rows jointly rather than cell-by-cell |
| `r3-ascii/` | decode the ASCII column as an independent channel and fuse the two posteriors |
| `r4-capture-side/` | PSF measurement, MTF comparison of capture paths, chroma channel, page identification — the one worker that completed |

## Test material (in the parent directory)

| file | page | oracle |
|---|---|---|
| `real-NTSC-48019000.png` | table 0x48019000 | ★ **all 256 bytes known** — panel ~539×290 |
| `real-PAL-48019000.png` | table 0x48019000 | ★ **all 256 bytes known** — panel ~433×199 |
| `pal-frame-48000000.png`, `pal-frame-48019000.png` | RAM 0x84xxxxxx | none — hand-cropped previews |
| `../../..//KN7000/photos/1st-frame-grabbed.png` | RAM 0x84000000 | none |

The known page is 71 % the byte `0x77`, so **always report accuracy twice**: overall, and
over the 75 non-`0x77` cells. A decoder that always guesses `77` scores 71 % and is useless.
`0x77` is ASCII `'w'`, so the hex and ASCII columns are independently checkable there.

Expected content: rows 0–1 are `77`×16; row 2 is `00 00 00 00 07 77 77 77-77 77 77 70 00 00
00 00`; row 3 is `B0 77 77 77 77 77 77 00-00 00 00 00 0B 07 77 77`.

## Settled by measurement

* **NTSC beats PAL on this instrument.** Same page, same VLC snapshot path, same 720×576
  frame: NTSC panel 539 px wide, PAL 433 px. The KN7000 centres its picture inside PAL's
  taller raster instead of using the extra lines. Two earlier predictions of ours were
  wrong in opposite directions; this is the measured answer.
* **Native VLC snapshots beat hand-cropped preview grabs**, clearly and by a lot.
* The shipped `dumpgrab.py` **refuses** all real frames so far (atlas trained on 640×240
  emulator output; 4/16 address rows on the ladder, 237/256 cells below confidence). That
  refusal is correct behaviour — it declines rather than inventing bytes.

## Next step, when resumed locally

Run `wip-real/r1-psf/fit_real.py` and friends against `real-NTSC-48019000.png`, print the
byte accuracy against the known page, and iterate on the numbers. No image should reach a
model context.
