# KN1500 LCD — element inventory and why the artwork cannot yet be driven

*2026-08-14. Written from the MAME render of `kn1500_lcd.svg` (all elements lit, because none
are bound) plus structural analysis of the SVG itself.*

## The blocker, first

`screen_svg_device` binds an SVG element to an emulator output when the element carries a
**`<title>`** whose text is the output name — MAME's `hh_sm510` convention. The artwork has:

| | count |
|---|---|
| `<title>` elements | **40** — all named `0.0.X.Y`, X=0–4, Y=0–7 |
| `<path>` | 142 |
| `<use>` | **0** |
| `<rect>` / `<ellipse>` | 9 / 2 |

So exactly **one 5×8 dot-matrix character cell** is prepared for driving. Everything else in the
panel — every annunciator, every seven-segment digit, the whole chord block — is untitled and
renders unconditionally. That is why the screenshot shows the entire display lit at once.

**And it is worse than "just add titles".** Count what the panel contains: 3 tempo digits, 2 × 3
part/measure digits and 8 × 3 track digits is already 42 seven-segment characters ≈ 294 segments,
against **142 paths in the whole file**. The digits must therefore be drawn as *compound* paths —
one path holding many subpaths — so individual segments are **not separately addressable**. There
is nothing to attach a title to.

⚠ Consequence for planning: making this display live is **an artwork rebuild**, not an annotation
pass. Each drivable element has to become its own path. Budget it that way.

## What the panel contains

Read off the render, left to right, top to bottom. Names below are a *proposal* for the
`<title>` values, not anything the firmware is known to use yet.

### Top row — three boxed panels

**TEMPO** (`tempo.*`)
- `tempo.label` — the word TEMPO
- `tempo.note` — the ♩ glyph and `=`
- `tempo.d0 … tempo.d2` — three 7-segment digits

**Chord / General MIDI** (`chord.*`, `gm.*`)
- `gm.logo` — GENERAL / midi / MODE (the General MIDI mark, three stacked parts)
- `chord.root` — root-note character, plus `chord.root.sharp` and `chord.root.flat`
- quality modifiers, each its own element: `m`, `M7`, `6`, `sus4`, `aug7`, `dim7`, `add9`
- alteration cluster: `#`, `+`, `−`, `5`, `9`, `13`, `11`
- `chord.on` — the word **on** (slash-chord separator)
- `chord.bass`, `chord.bass.sharp` — the bass-note character right of **on**

**Menu / Transpose** (`menu.*`, `transpose.*`)
- `menu.label`, `page.label`, `page.down` ▼, `page.up` ▲
- `transpose.label` — drawn as an inverted/filled box, so it is a highlight state
- `transpose.note` — the ♩ glyph, with `transpose.up` ↗ and `transpose.down` ↙

### Left margin
- `prog.up` ∧, `prog.label` (PROG), `prog.down` ∨

### Middle boxed panel — part, rhythm, and text
- `part.right1`, `part.right2` (RIGHT 1 2), `part.left` (LEFT), `part.keyboard` — keyboard icon
- `rhythm.label` (RHYTHM), `rhythm.icon` — drummer icon, `measure.label` (MEASURE)
- `part.d0 … part.d2` — upper 3-digit numeric (program / part number)
- `measure.d0 … measure.d2` — lower 3-digit numeric
- **two rows of 5×8 dot-matrix character cells** — the only part already prepared. The existing
  cell is titled `0.0.X.Y`; the convention extends naturally to `<row>.<col>.<x>.<y>`, which is
  presumably why it starts `0.0.`. **The cell count per row is not yet established** — it must be
  counted from the artwork geometry, not from the render, and I did not trust my own bounding-box
  extraction (the paths use relative commands with nested transforms, which smeared every element
  across the canvas when parsed naively).

### Bottom band — the 8-column track/part matrix
- `track.label` (TRACK), `part.label` (PART)
- per column *n* = 0…7: `track.n.a` / `track.n.b` — the two numbers (1 9, 2 10, … 8 16)
- `rec.label`, `play.label`, and their dashed rules
- per column: `bar.n.0 … bar.n.k` — the stacked horizontal bars (a level/activity meter drawn as
  a trapezoid of lines; the number of steps needs counting from the artwork)
- per column: `val.n.d0 … val.n.d2` — a 3-digit numeric, showing a leading `−` on columns 0–4 in
  the render, so the sign is very likely its own element: `val.n.sign`
- per column: `cursor.n` ▼ — the marker under each column

## How to map firmware writes to elements — the honest route

Semantic guessing from this image can propose *names*; it cannot establish which
controller (COM, SEG) pair drives which element. Two real sources:

1. **The service manual.** `KN1500/technics_sx-kn1500_sm.pdf` is a 38-page scan with **no text
   layer** (`pdftotext` yields 38 bytes total), so it needs OCR or page-by-page reading. The LCD
   connector pinout and the COM/SEG matrix are the ground truth and would settle the mapping
   without any emulation.
2. **Empirical, from the running firmware** — currently **blocked**: the boot never reaches the
   display phase. It stalls in a RAM marching test whose pointer runs past the 24-bit address
   space, and IC15 is a `BAD_DUMP` with a badly asymmetric byte lane (8.5 % vs 54.3 % `0xFF`
   against a known-good ROM's 0.8 %/1.9 % — see `technics_roms/tools/byte_lane_census.py`).
   Re-dumping IC15 is a prerequisite for this route, so it is a hardware-lane item.

**Recommended order:** read the manual's LCD pages first (desk work, no hardware), because it also
tells us the controller type — which decides whether the panel is driven by a memory-mapped
controller, a bit-banged serial link, or direct COM/SEG pins, and that in turn decides what the
driver has to model at all.
