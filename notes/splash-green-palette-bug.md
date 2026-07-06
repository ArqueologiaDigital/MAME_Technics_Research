# Why the boot screen is solid green: a palette-load bug (not a missing image)

The KN7000 boot fills the LCD with bright green before the home screen appears,
and the central "picture box" on normal screens is the same green. This traced
to a **CLUT (palette) load failure**, NOT a missing or mis-addressed image.

## Measured chain (probes in the MN10300 core, boot to ~t=7-9 s)

1. The framebuffer at workram 0x500D4080 is first **cleared to 0x00 (black)** by a
   32-bit fill loop at PC 0x48410039 (writes 0x00000000 sequentially).
2. The splash **image's pixels ARE then drawn** into the framebuffer: during the
   green phase it is dominated by palette **indices 0xD0-0xD8** (0xD0 alone =
   ~100k of the 153600 pixels). So the picture blit works and real pixel data is
   present -- this refutes "the image data fails to load".
3. But **every CLUT entry the image uses maps to the same green**: CLUT[0xD0..D8]
   all = 0x0080FF80 (R80 G FF B80). So whatever the pixel indices are, they all
   resolve to green -> the image renders as a solid green block.

## Root cause: the image palette is never loaded over the ROM placeholder

The CLUT is seeded at boot from the program-ROM palette table at file 0x32573C
(address 0x4872573C), 256 entries of 0x00BBGGRR. That seed is:
- indices 0x00-0x1C: the real UI palette (black, blue title-bar, grays -- these
  render correctly, which is why the text UI looks right);
- **indices 0x1D-0xF3: ALL 0x0080FF80 green** (215 of 256 entries) -- a
  deliberate placeholder for the "image palette" range;
- indices 0xF4-0xFF: a few real values (0xFF = 0xC8C8C8).

On real hardware, displaying a picture loads that picture's own palette into the
CLUT[0x1D..0xF3] slots, replacing the green. **In MAME that overwrite never
happens**: instrumenting all three write widths (write_mem8/16/32) over the CLUT
image range 0x500314D0-0x50031890 for the whole boot logged **zero writes**. The
green placeholder is never touched, so the image stays green.

(The picture flash at 0x57800000 is also never read during boot -- see
boot-performance-and-clock.md -- so the palette isn't coming from there either.)

## The splash is very likely a palettized BMP

The asset extraction (../kn7000_extraction) found a 160x100 **palettized BMP**
"program_345718.bmp" at program offset 0x345718 (plus JPEGs of the keyboard and
world-music art). A palettized BMP carries its own color table; displaying it
should load that table into CLUT[0x1D+] and blit the indexed pixels. The pixel
blit half works in MAME; the palette-table load half does not.

## Open questions / next step

Why does the pixel blit run but the palette load not write the CLUT? Candidates
to chase next tick:
- The palette-load code path may not execute at all (gated on a flag/state MAME
  doesn't provide), OR
- it writes the palette to a HARDWARE palette register (e.g. an LCD-controller
  port in the 0x90000000 window or an I/O reg) that MAME doesn't model, while
  screen_update only reads the workram CLUT seed at 0x50031490 -- in which case
  the fix is to model that palette port and have screen_update honour it, OR
- the load executes but via an aliased address / an instruction the core
  mis-runs (watch for the unidasm 0xF4 desync in that routine).
Find the routine that SHOULD write CLUT[0x1D+] (search for code that reads a BMP
color table / the picture resource and stores 4-byte entries at 0x50031490+idx*4
or an alias), and trace why it is skipped or mis-targeted.

## Follow-up: the CLUT seed mechanism located (2026-07-05, tick pp+1)

Directly instrumented the CLUT writer (the last-tick "0 writes" was a broken
probe -- header edits weren't recompiling + a silent ENFILE build failure).

- The CLUT is seeded by a 256-entry loop at **0x4842D9D7** (per-color routine
  0x4842D9F6; the actual store is `mov d3,(d0,a0)` at **0x4842DB1E**, a0 =
  0x50031490, index = a3, colour = d3). The seed source is the ROM table at
  file 0x32573C (0x4872573C).
- The writer runs at boot and writes ALL 256 entries: idx 0x00-0x1C = real UI
  colours, **idx 0x1D-0xF3 = green 0x0080FF80** (the placeholder), idx 0xF4-0xFF
  = misc (some 0x00FFFFFF white, etc.). Confirmed by logging every execution of
  0x4842DB1E through boot: idx 0x1D+ receives ONLY the green seed and is never
  re-written with real colours within the whole ~14 s boot.
- 0x4842DB1E is the ONLY code in the image that writes 0x50031490 (the CLUT), so
  ANY palette load must go through it -- and it only ever writes green to the
  image range. Therefore the picture/background palette overwrite simply does
  not execute during boot in MAME.

### Assessment

The full-screen green at boot is the framebuffer background/picture plane cleared
to index 0xD0 (and neighbours 0xD1-0xD8), which resolve through the green
placeholder; the home-screen UI then draws over most of it in indices 0x00-0x1C,
leaving the central picture box green. Because 0x4842DB1E is the sole CLUT writer
and it only writes green to idx 0x1D+, MAME appears to *faithfully* run what the
firmware does: the firmware seeds a green placeholder and does not overwrite the
image-palette range at boot.

So this is most likely NOT a MAME rendering bug -- the real KN7000 very probably
also shows the green picture area until content with its own palette is loaded.
IF the real machine instead shows a coloured splash/logo at power-on, then the
firmware's boot-picture display is GATED on state MAME doesn't provide (NVRAM
settings, or a picture-flash/SmartMedia resource -- note the picture flash at
0x57800000 is never read at boot). The image-display path itself works (it runs
through library-ROM routines that decode the embedded BMP/JPEG assets, e.g. the
palettized BMP 0x48745718 handled at 0x48496FC0); it is simply not invoked for a
boot splash. Resolving "intended green vs missing splash" needs a reference for
the real machine's power-on screen. Open: find the gate/config that would trigger
a boot-picture palette load (search callers of 0x4842D9D7 / the picture-display
entry and their enabling conditions).

## CORRECTED / AUTHORITATIVE (runtime-verified): the splash animation is never played
A deeper runtime trace supersedes the "picture blit works, only the CLUT is green"
conclusion above. The 215-green CLUT placeholder (indices 0x1D..0xF3 = 0x0080FF80, seeded
by `InitPaletteRGB` 0x4842D9AD from ROM table 0x4872573C) is GENUINE -- it is meant to be
overwritten by a displayed picture's own palette. The real defect is upstream: **the boot-
splash JPEG is never decoded at all**, so nothing ever overwrites the green.

### The boot-splash display path
- `OpeningFrameDraw` **0x4848A931** is the power-on "opening" screen's draw callback,
  installed by `InitializeBlock04` 0x4848A4D8 (boot class table 0x487270BC; the install is
  `0x4848A851: mov 0x4848a931,d0`). It renders the animation frames from the **seg05 JPEG
  archive** (table-ROM directory entry [5] -> 0x4805667C, the music-notes/logo JFIFs) by
  calling `DrawJpegFile` **0x48424EC2** at `0x4848A988`.
- It is a timed sequencer over a 7-entry frame table `0x485E68B8` = {00,10,12,14,16,20,42,
  FFFF}, using frame-index `0x5006B5A8` and a target counter `0x5006B5A4` that increments on
  each redraw (0x4848A9A7).

### Why green (evidence)
- Read-taps: the splash JPEG bytes are **never read** (seg05 opening / seg09 "Welcome" /
  seg14 mountains = 0 reads each; seg06 fonts = 207 reads, so taps work). The 0x90000000
  V-RAM window is empty. So the decode is simply never invoked.
- CLUT write-tap over [0x1D..0xF3]: 430 writes, **zero non-green** for the whole boot
  (0x4842DB1E only ever writes the green placeholder there). screen_update presents the 8bpp
  plane 0x500D4080 through that CLUT; at t=17 the box is idx 0xE0 -> green.
- `OpeningFrameDraw` gates the JPEG draw at `0x4848A966: cmp d0,d1 / bne 0x4848A9A7`
  (d0=frametbl[frame_index], d1=[0x5006B5A4]=target). The callback runs only **~once** (t~3s),
  so the sequencer never steps target 0x00->0x42 and no frame ever matches -> DrawJpegFile
  skipped.

### The fix (a boot-timing/scheduling gap, NOT palette or blit)
The opening animation exists to cover the multi-second hardware/resource init that the
emulator finishes near-instantly, so the boot leaves the opening screen without holding on
it and pumping its ~66 redraws. Fixing green = making the boot stay on the opening screen and
redraw it during the init window (advancing 0x5006B5A4 0x00->0x42) so DrawJpegFile runs -- a
display/task-scheduling issue. screen_update and the CLUT seed are both correct as-is.
NOTE: boot splash = seg05 (music notes 0x480566E8 + KN7000 logo 0x48066517) ONLY; "Welcome"
(seg09 0x48139EF0) is demo mode, mountains (seg14 0x48162C14) separate -- both 0 reads at boot.
