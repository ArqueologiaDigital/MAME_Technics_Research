# KN7000 panel — RHYTHM GROUP genre map + real-machine feedback (2026-07-07)

Source: user real-machine testing of the published binary (commit 34cc23b) +
snapshot-probe verification in the emulator. This is GROUND TRUTH for the panel wiring.

## RHYTHM GROUP — genre → input-bit map (VERIFIED, FIXED)
The 16 genre-select buttons are wired to **SEG00 / SEG01 / SEG02, bit b2..b7** → genres
0..15 in order (SEG02 stops at b5). Physical layout position i = genre i (2 rows × 8).
Verified by snapshot (pressing the bit opens that genre's RHYTHM screen):

| genre | name              | bit        | how verified |
|-------|-------------------|------------|--------------|
| 0     | 8&16 BEAT         | SEG00 0x04 | snapshot     |
| 1     | ROCK & POP        | SEG00 0x08 | snapshot     |
| 2     | BALLAD            | SEG00 0x10 | user (START/STOP=SEG00 0x10 → BALLAD) |
| 3     | JAZZ & SWING      | SEG00 0x20 | snapshot     |
| 4     | BALLROOM          | SEG00 0x40 | snapshot     |
| 5     | MOVIE & SHOW      | SEG00 0x80 | user (SYNCHRO=SEG00 0x80 → MOVIE&SHOW) |
| 6     | ENTERTAINER       | SEG01 0x04 | snapshot + user |
| 7     | ORGANIST          | SEG01 0x08 | user |
| 8     | 60s & 70s         | SEG01 0x10 | user |
| 9     | MODERN DANCE      | SEG01 0x20 | user |
| 10    | SOUL & R&B        | SEG01 0x40 | user |
| 11    | COUNTRY & WESTERN | SEG01 0x80 | user |
| 12    | MARCH & WALTZ     | SEG02 0x04 | user |
| 13    | LATIN & WORLD     | SEG02 0x08 | user |
| 14    | CUSTOM            | SEG02 0x10 | user |
| 15    | MEMORY            | SEG02 0x20 | user |

Genre order = GenreStyleTable @0x48735EE4. b0/b1 of each SEG are NOT genres
(the old layout's MEMORY/LOAD, SOUL & FUNK on SEG01 b0/b1 lit nothing — consistent).

**FIXED**: RG list rebuilt to this map (gen_lay.py). The old binding was SEG01/SEG02
b0-b7 (off-by-bits) and collided with START/STOP (SEG00 0x10) etc.

## Collision cleanup (FIXED this pass)
Because SEG00 b2..b7 are the genre bits, buttons the layout wrongly put on those bits were
spuriously opening genres. Unbound (made decorative) until their real bits are found:
- **START/STOP** (was SEG00 0x10 = BALLAD) → unbound
- **SYNCHRO & BREAK** (was SEG00 0x80 = MOVIE & SHOW) → unbound
- **LCD-LEFT soft-keys** (LCDPARTS OFF column, was SEG00 0x04/0x08/0x20 = genres 0/1/3, plus
  0x01/0x02) → unbound

## Confirmed WORKING (do NOT change — user)
- DISK, PROGRAM MENUS (buttons).
- Whole SOUND GROUP button+LED: PIANO, GUITAR, MALLET & ORCH PERC, WORLD, STRINGS & VOCAL,
  BRASS, SAX & WOODWIND, ORGAN & ACCORDION, DIGITAL DRAWBAR, ORGAN TABS, ACCORDION REGISTER,
  PAD, SYNTH, BASS, DRUM KITS.

## REMAINING mis-bindings / TODO (from user feedback — follow-up ticks)
`current_button (layout bit) => what it really triggers` — so the real bit for the *target*
function is the one currently on `current_button`:
- FADE IN/OUT (SEG03 0x20) => **LCD LEFT 3**  ⇒ LCD LEFT 3 soft-key = SEG03 0x20
- VARIATION 4 (SEG03 0x40) => **LCD LEFT 4**  ⇒ LCD LEFT 4 = SEG03 0x40
- SPLIT POINT (SEG03 0x80) => **LCD LEFT 5**  ⇒ LCD LEFT 5 = SEG03 0x80
  → inferred: **LCD LEFT 1..5 = SEG03 b3..b7** (0x08/0x10/0x20/0x40/0x80). Rebinding the
  left soft-keys there conflicts with FADE/VAR4/SPLIT, whose real bits are then unknown.
- MUTE UP 10 => DEMO ; MUTE UP 7 => PADS BANK SELECT (PERFORMANCE PADS BANK) ;
  MUTE UP 4 => OTHER PARTS & FR ; MUTE DOWN 4 => HELP ; MUTE DOWN 8 => MUSIC STYLE ARRANGER
  → the MUTES[] seg/bit table is partly wrong; these give real bits for DEMO/BANK/OTHER
  PARTS/HELP/MSA.
- LCD LEFT 2 => ROCK & POP, LCD LEFT 3 => JAZZ & SWING, LCD LEFT 5 => 8&16 BEAT
  (already resolved by the genre map + unbinding the left column).

## Other observations (TODO)
- **SOUND EXPLORER**: opens its screen but lights PIANO+BASS LEDs instead of its own
  (LED map issue; EXPLORER only hit shared cpr48 in the sweep — see OPLED note).
- **No visual feedback** (button not associated with any input, or no LED): SOUND GROUP
  MEMORY & EW EXPANSION; all PART EFFECT + GLOBAL EFFECT; all BANK VIEW / NEXT BANK / PANEL
  MEMORY; all CUSTOM PANEL / CUSTOMIZE / FAVORITES; SEQUENCER PLAY & EASY REC; SD LOAD
  (orange); APC MODE/SET/OFF-ON (lower); DISPLAY HOLD; EXIT; PAGE UP/DOWN.
  → these need their input bits found (many may be dedicated events, not in the scanned segs).

## Genre LEDs (TODO)
The RHYTHM GROUP LEDs use OPLED, but its entries were swept against the OLD (wrong) bit
assumptions, and the SEG00 genres (0,1,3,4) have no entries. A fresh genre-LED sweep against
the verified bits above is needed (press each genre bit, record which cpl_led lights).
