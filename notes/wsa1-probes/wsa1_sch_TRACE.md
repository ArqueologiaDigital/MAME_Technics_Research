# Re-deriving the SX-WSA1R panel switch matrix from the service manual

These three probes are what turned "I looked at the schematic" into coordinates.
They do not read the PDF; they read a *rendered page* and report the black runs, so
every net claim below can be re-checked by anyone with the manual.

Source (never leaves the machine):
`~/compartilhado/KN7000/service_manual/SX-WSA1R Service Manual.pdf`

Render recipe (the PNGs are regenerable, so they are NOT committed):

    pdftoppm -f 32 -l 32 -r 400 -png -gray "SX-WSA1R Service Manual.pdf" hi32   # CP1/CP2 P.C. Diagram  (II-29/30)
    pdftoppm -f 31 -l 31 -r 400 -png -gray "SX-WSA1R Service Manual.pdf" hi31   # CP1/CP2 P.C. Board    (II-27/28)
    pdftoppm -f 19 -l 19 -r 400 -png -gray "SX-WSA1R Service Manual.pdf" hi19   # MAIN(A)/MB2 Diagram   (II-7/8)
    pdftoppm -f  5 -l  5 -r 500 -png -gray "SX-WSA1R Service Manual.pdf" hi05   # ARRANGEMENT OF CONTROL PANEL (I-4/5)

| script | question it answers | command |
|---|---|---|
| `wsa1_sch_hscan.py` | which x does this horizontal wire START and END at? (runs >=15 px of black in one scanline) | `python3 wsa1_sch_hscan.py hi32-32.png <x0> <x1> <y0> <y1>` |
| `wsa1_sch_vscan.py` | which y does this vertical wire span? (runs >= minlen) | `python3 wsa1_sch_vscan.py hi32-32.png <x0> <x1> <y0> <y1> [minlen]` |
| `wsa1_sch_crop.py` | cut a window out for visual reading of a symbol/legend | `python3 wsa1_sch_crop.py hi32-32.png out.png <x0> <y0> <x1> <y1> [scale]` |

The page has ~5 px of skew over its height, so a "vertical" wire drifts about
-0.0024 px of x per px of y; `wsa1_sch_vscan.py` reports one run per x column and
the drift shows up as overlapping runs at adjacent x. Endpoints, not x values, are
the identity of a net.

## Key coordinates on `hi32-32.png` (400 dpi, page 32)

IC1 M37471M2196S right edge x=1580.

    SEG0..SEG10 leave at y = 3389 3419 3449 3478 3507 3537 3566 3596 3625 3655 3684
    run ends at x = 2582 2932 2669 2756 3633 3896 [1615] 4099 2845 3020 [1614]

SEG6 (pin 40) and SEG10 (pin 33) stop 35 px out: that is the pin-number underline,
not a wire. Nine of eleven strobes survive past x=1620.

    row buses SW0..SW7 at y = 1064 1197 1330 1462 1595 1729 1861 1994
    right ends       at x = 4047 4076 4017 3988 4346 3681 3681 3680
    (SW5/6/7 stop at the column-6 cell; only SW0..SW4 leave CP1)

    switch column buses at x = 2585 2848 3110 3372 3634 3898  (cols 1..6, y 1002 down)
    IC3 HD74LS07P input pins  x = 2582 2669 2756 2845 2932 3020  = pins 1 3 5 9 11 13
    IC3 output verticals      same x, carrying R1 R3 R4 (none) R2 (none)

Joins proved by isolated horizontals (each is a single run with a gap either side):

    y=2794  x 2844..2934   col-2 bus  -> R2  -> IC3 pin10/11 -> SEG1
    y=2891  x 2667..3109   col-3 bus  -> R3  -> IC3 pin4/3   -> SEG2
    y=2934  x 2754..3371   col-4 bus  -> R4  -> IC3 pin6/5   -> SEG3
    col-1 bus runs straight down x=2585 into R1 -> IC3 pin2/1 -> SEG0
    SEG4 -> x3633 = col-5 bus ; SEG5 -> x3896 = col-6 bus  (direct, unbuffered)

Cross-board:

    SW0 -> vertical x4043 (y1061..2664) -> CN3.5  B5
    SW1 -> vertical x4073 (y1194..1507) -> CN2.3  A3
    SW2 -> vertical x4013 (y1327..2781) -> CN3.9  B9
    SW3 -> vertical x3984 (y1460..2811) -> CN3.10 B10
    SW4 -> straight to CN2.6 A6 at y1595
    SEG7 -> vertical x4100 (y1475..3597) -> CN2.2 A2
    SEG8 -> vertical x4158 (y2630..2979) -> CN3.4 B4
    SEG9 -> vertical x4186 (y2689..3023) -> CN3.6 B6
    CM1 Q2 collector y2324 -> x4160 -> CN2.7 A7
    CM2 Q3 collector y2441 -> x4073 -> CN2.5 A5
    CM3 Q5 collector y2558 -> x3953 -> CN3.7 B7
    CM4 R17          y2750 -> straight to CN3.8 B8 (-> CP2 Q6 base)

On CP2: A2 -> x5010 (y1475..1537) -> y1534 -> column-A bus x5273 (SW57..SW60);
B4 -> x4833 (y2256..2634) -> y2257 through R5 -> column-B bus x5535 (SW65,SW66);
B6 -> x5059 (y2301..2693) -> y2301 -> column-C bus x5797 (SW73..SW77).
R6 is NOT in the B6 strobe path: the vertical at x5795 breaks only at y2343..2388,
below the point where B6 joins, so R6 feeds the D139/D141/D161/D163 cathodes alone.
R5 by contrast sits in the B4 feed and is in series with SW65/SW66 as well.

## Independent cross-check that the strobe map is right

The six SEG lines that carry LEDs are exactly {0,1,2,3,8,9} and exactly those six are
buffered by IC3's six open-collector gates; {4,5,7} carry switches only and go straight
from IC1. A hex buffer with six LED-bearing columns is not a coincidence, and any
off-by-one in the column mapping breaks the pattern.

## Orientation anchor for the P.C. Board page (hi31-31.png)

The board drawing is a component-side view in the SAME orientation as the panel, in
BOTH axes, and this is fixed by silkscreen text rather than by inference:

* the keypad legends read 7 8 (9) left-to-right and 7 / 4 / 1 / 0 top-to-bottom,
  identical to I-4;
* the PAGE pair is silkscreened with the up arrow on SW22 (upper row) and the down
  arrow on SW21 (lower row), identical to I-4;
* IC1's pin 1 is top-left with numbering running counter-clockwise (1..22 down the
  left, 23..44 up the right) = a top view.

That anchor is what licenses reading the 29 unlabelled positions (SW25-29, SW30-32,
SW33-48, SW73-77) off the board page.
