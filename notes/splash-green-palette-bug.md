# Why the boot screen is solid green: a palette-load bug (not a missing image)

> **STATUS — RESOLVED & FIXED. It was a DUAL-PLANE DIRECT-COLOUR display, not a palette bug.**
> The picture is NOT palettized: colour is split across two work-RAM byte-planes — framebuffer
> `0x500D4080` = `0xD0|red4` (the `0xD` high nibble tags a picture pixel), companion plane
> `0x500F9880` = `(green4<<4)|blue4`. The driver read only the first plane through the CLUT, so
> picture bytes hit the green placeholder → green. FIXED by compositing both planes in
> `screen_update` (commit b3ba4bb). **Full architecture: `notes/display-dual-plane-direct-color.md`.**
> Everything below (this file's "palette-load", the "never decoded", and the "boot-sequencing"
> sections) is superseded investigation history — the frame indices 0xD0–0xDC were red nibbles,
> not palette indices.

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

## Redraw mechanism (deeper trace) -- the fix is a periodic-redraw / scheduling gap
Disassembling OpeningFrameDraw 0x4848A931 end-to-end:
- Reads OpeningFrameIndex 0x5006B5A8; if 0xFFFF (done) -> skip.
- d0 = OpeningFrameTable[index] (the target value for this frame).
- Gate 0x4848A966: if OpeningFrameTable[index] == OpeningFrameTarget(0x5006B5A4) -> DrawJpegFile
  0x48424EC2 for this frame, then OpeningFrameIndex++ (0x4848A999/A1).
- Tail 0x4848A9A7: OpeningFrameTarget++ ; then `ret` (0x4848A9B5).
So each invocation bumps the target by 1 and RETURNS -- it does NOT self-request another
redraw. The animation (target 0x00->0x42, i.e. ~66 steps) therefore requires the FRAMEWORK to
redraw the opening view ~66 times. The agent measured ~1 invocation, so the framework redraws
it ~once.

Where the redraws must come from: the driver models a 60 Hz screen (kn7000.cpp:1306) but
generates **no vblank/display interrupt** to the CPU (IRQ groups are only TIMER 0x06 / PANEL
0x1A / MIDI 0x12,0x14). So the opening view's periodic redraws have to be driven by the RTOS
draw task on the system tick.

**Ruled out -- it is NOT a disabled-tick / F6 issue.** The AM33 F6 ops ARE now implemented
(execute_f6, mn10300.cpp:500) and the 1 kHz system tick is active (m_sys_timer->adjust,
machine_reset ~line 1267) -- so the driver's "HELD until F6" comment there is STALE. The RTOS
ticks, yet the opening view is still drawn only ~once. That points to a **boot-SEQUENCING**
issue, not the tick/graphics path: the opening (splash) view appears to be active only briefly
(~t=3 s), after which the boot advances to a phase whose background is the placeholder green,
and that green persists unrepainted until the home screen -- rather than the splash view being
held and animated for its full 0x00->0x42 run. NEXT: trace the opening-view lifecycle (what
activates/deactivates it, and what would keep it active + redrawing through the init window)
and identify what paints the persistent green after it. A UI-flow / boot-mode-sequencer
question.

## DEFINITIVE / RESOLVED (runtime-verified) -- it IS a palette-load failure after all
Direct RAM polling (kn7000, autoboot Lua) settles this and supersedes BOTH the boot-splash
agent's "JPEG never decoded / animation never played" AND my "boot-sequencing / redraw" theory
above. All three of the following are measured facts:

1. **The frame sequencer runs fully.** Polling OpeningFrameTarget 0x5006B5A4 / OpeningFrameIndex
   0x5006B5A8 each frame: target climbs 0x00 -> 0x42 and index steps 0 -> 6 over t=4..13 s. So
   OpeningFrameDraw is invoked ~66x and every frame is matched -> DrawJpegFile IS called. (The
   agent's "callback ran ~once / sequencer never steps" was simply wrong.)
2. **The JPEG is decoded into the framebuffer.** Histogram of the 8bpp plane 0x500D4080 at t=8:
   13 distinct indices, ALL in the contiguous range 0xD0..0xDC (0xD0 ~40% = image background,
   the rest = the notes) -- a real decoded image, not a flat fill. DrawJpegFile's decode guard
   *0x5002a01c = 1 during the splash (not skipped).
3. **The image palette is never loaded.** CLUT dump at t=8: entries [0xD0..0xDC] are ALL
   0x0080FF80 (the green placeholder), whereas a UI entry CLUT[0x02]=0x00008000 (real). The
   firmware fills the work-RAM CLUT (0x50031490) with the UI colors (0x00..0x1C) + the green
   placeholder for 0x1D..0xF3, but the decoded splash image's own palette (the 13 colors for
   0xD0..0xDC) is never written there.

=> The splash renders as solid green because its pixels index CLUT slots 0xD0..0xDC that hold
the green placeholder. The decode/blit/sequencer are all fine. THE FIX is the image-palette
load: find where the JPEG's palette (for 0xD0..0xDC) should be written to the work-RAM CLUT at
0x50031490+idx*4 and why it isn't -- either a gated work-RAM CLUT write, or (more likely) a
HARDWARE image-palette the real LCD controller latches that the driver doesn't model/read (the
driver presents everything through the single work-RAM CLUT). NEXT: trace the JPEG decoder
0x48424F28's palette output + how a displayed picture's palette normally reaches the CLUT.
