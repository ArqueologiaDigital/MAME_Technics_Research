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
