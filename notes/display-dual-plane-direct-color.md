# The KN7000 display: UI palette plane + a dual-plane direct-colour picture

This resolves the long-running "green screen" (see splash-green-palette-bug.md, whose
palette-load framing was a red herring). The KN7000 LCD does NOT show pictures through
a palette at all. It composites **two kinds of pixel**:

## 1. UI / text pixels — 8bpp, palettized
Palette index in the framebuffer byte, resolved through the work-RAM CLUT at
`0x50031490` (0x00BBGGRR, seeded by `InitPaletteRGB` 0x4842D9AD). Indices `0x00..0x1C`
are the real UI colours; these render correctly. (A parallel RGB565 copy the firmware's
own compositor uses lives at `0x50122AAC`.)

## 2. Picture pixels — 12-bit (4:4:4) DIRECT colour, two byte-planes
A decoded JPEG/bitmap is NOT palettized. Its colour is split across two work-RAM planes
at the same `y*640+x` offset:

| Plane | Address | Byte layout |
|-------|---------|-------------|
| framebuffer | `0x500D4080` | `0xD0 | red4` — high nibble `0xD` **tags a picture pixel**, low nibble = 4-bit red |
| companion   | `0x500F9880` | `(green4 << 4) | blue4` — 4-bit green (high) + 4-bit blue (low) |

(`0x500F9880 = 0x500D4080 + 0x25800`, i.e. one 640×240 buffer later.)

**Writer** (verified by disassembly, `0x484870C8` inner loop): a per-pixel YCbCr→RGB
converter (AM33 DSP muls: Cr·1.402 for R at 0x484870E3, Cb·1.772 for B at 0x48487104,
etc.), each channel rounded (`+0x2000`, `asr 14`), clamped 0..255, reduced to 4 bits.
Then `add 0xd0,d1` (0x48487144) tags red; `movbu d1,(a3)` to `0x500D4080` (0x48487199)
and `movbu d2,(a3)` to `0x500F9880` (0x484871A3), same `a3` offset for both.

**Firmware compositor** (`~0x48414D9A`): for a byte with `(fb & 0xF0)==0xD0` it builds
RGB565 = `((fb&0x0F)<<12) | ((comp&0xF0)<<3) | ((comp&0x0F)*2)` (R=red4, G=green4,
B=blue4) and writes it to the LCD VRAM window `0x9CE00000`; otherwise it looks the UI
colour up in `0x50122AAC[fb]`. So the LCD is driven from `0x9CE00000`, and the CLUT
never has anything to do with picture colour.

## Why it was green, and the driver fix
`screen_update` only read plane `0x500D4080` and resolved **every** byte through the
CLUT. Picture bytes `0xD0..0xDF` therefore indexed the CLUT's unused (green-placeholder)
range → solid green. Fix (kn7000.cpp `screen_update`): for `(idx & 0xF0)==0xD0` read the
companion plane `0x500F9880` and emit `rgb_t(red4*17, green4*17, blue4*17)`; otherwise
keep the CLUT path. UI pixels are untouched, so the text UI is unaffected.

## Status / caveats
- Verified: writer format + alignment (disassembly), and the driver now emits picture
  colour instead of green. Runtime per-channel spatial roughness is ~equal (red 2.86 /
  green 2.88 / blue 2.75), ruling out a plane misalignment.
- The boot-splash picture region reads as high-frequency at 1:1 pixels (the
  notes-in-space frame is a dense starfield + fine dither), so a raw MAME snapshot looks
  speckled; the physical 640×240 LCD blends it. Matching that appearance (dither-aware
  downscale, or reading the composited `0x9CE00000` RGB565 directly if that window is
  modelled) is a fidelity refinement, not a correctness issue.
- The `0xD0` tag means only 0x_D_ picture bytes are affected; if any non-picture use of
  0xD0..0xDF exists it would be miscoloured (none seen — UI uses 0x00..0x1C).

## Future refinement: read the firmware's composited buffer 0x9CE00000 directly
Confirmed at runtime: the firmware's compositor DOES run and writes the final RGB565 image
to `0x9CE00000` (which the driver already maps: `map(0x9c000000,0x9cffffff).ram()`). At
t=8s it is ~50% non-zero with real colours (e.g. 0x1400=green, 0x9000=red). Since
`0x9CE00000` is what the real LCD controller scans, the most faithful `screen_update` would
present it directly (RGB565 → rgb_t) instead of re-compositing the two planes — that would
also pick up the firmware's gamma-corrected UI colours (`0x50122AAC`) for free. Caveats to
resolve first: the compositor stores the image **flipped** (dest offset
`((0xef-row)*0x280+(0x27f-col))*2`), so it must be read with the inverse transform; and the
formula/flip must be verified against a STATIC screen (a plane-vs-0x9CE00000 comparison
during the boot animation is confounded because the planes are being rewritten while
0x9CE00000 holds the compositor's previous frame). The current two-plane `screen_update`
composite is correct and simpler; 0x9CE00000 is the higher-fidelity option for later.
