> **CORRECTION (2026-07-14) — "CPR FULL firmware scramble" below is WRONG; PHYS_MAP eliminated.**
> The claim that CPR's physical columns repack across normSegs (needing a 2-D PHYS_MAP) does not
> hold. The firmware's ADDR->normSeg is a **whole-column rename** (the driver emits one [ADDR,DATA]
> frame per normSeg via the 1:1 `seg_to_addr` table), so each normSeg IS exactly one sub-CPU scan
> column (CPR wire ADDR 0x00-0x09). A single scan column cannot scatter its bits across four
> normSegs — so the `CPR_SEG0..9` "physical" grouping (bridged by function/label, never by schematic
> position) was the artifact, not the firmware. `PHYS_MAP[22][8]` was in fact a **pure permutation**
> (116 identity + 30 cells in small within-board cycles), i.e. a relabeling. It has been **removed**
> (commit "eliminate PHYS_MAP"): INPUT_PORTS are now organized directly by normSeg (= the scan
> matrix the KN5000 style documents), the device uses a 1-D `PORT_SEG` identity, and the layout
> relabel is a trivial `SEGxx->CP{board}_SEG{col}` at the same bit. Behavior is identical (verified
> live). The physical-column transcription below is retained only as schematic provenance; the
> `panel-physical-scan-map.json` map is no longer consumed by the build.
> Still-wrong bindings to chase separately (NOT fixed by this refactor): conductor L/R1/R2, the SD
> transport keys (unbound in layout), CUSTOM PANEL (unbound), FAVORITES (dubious).

# KN7000 physical panel scan matrix -> CP{board}_SEG{col} port rename (2026-07-13)

Adopts the KN5000 naming: each ioport = a physical (board, SEG-column) of that board sub-CPU's
scan matrix; the port BITS = the SW rows. Transcribed from the service-manual schematics
(CPL DIAGRAM-15 p128, CPC DIAGRAM-16 p130, CPR DIAGRAM-17 p132, SD panel DIAGRAM-20) by workflow
kn7000-panel-board-transcribe (wf_470473c9), adversarially verified. Full machine-readable map:
`notes/panel-physical-scan-map.json`.

## Board topology (from the schematics)
- **CPR** IC1001 (p132): own sub-CPU, SCAN MASTER, direct drop on the CP serial bus (ping 0xE0).
  Wire bank 00, subaddr 0x00-09 -> driver SEG0C-15. Sounds/effects/part-select/conductor/transpose/
  sound-groups/customize/favorites. FULL firmware scramble (physical col repacks across driver normSegs).
- **CPL** IC1101 (p128): own sub-CPU, CHAINED (MAIN->CPR->CPL, ping 0x20). Wire bank 11, ADDR 0xC0-C7
  -> driver SEG00-07. Rhythm/style/genre/variation/fill/pad/LCDL + volume pots (VR1101-05) + BEND/MOD.
  Mostly identity (bit==SW); genre columns SEG1/SEG2 scrambled.
- **CPC** (p130): NO sub-CPU -- passive matrix SCANNED BY CPL's IC1101. Columns SEG5,SEG8-11
  (ADDR 0xC5,0xC8-CB) -> driver SEG05,SEG08-0B. Part-mute rocker (MUTE UP/DOWN 1-16) + HELP/CONTRAST/
  PAGE/DISPLAY HOLD/EXIT/OTHER PARTS-TG. Identity.
- **CPSD** (p130 DIAGRAM-20): NO sub-CPU, NO scan matrix. 6 transport switches read as a MAIN-CPU GPIO
  byte 0x9CC00008 (active-low), NOT on the CP link. -> driver SDSW (renamed CPSD_SDSW).

## Rename = FAITHFUL (behavior preserved)
Every one of the 146 bridged buttons keeps firing its exact current wire frame; the port just moves to
its physical (board,SEG,SW) slot with the silk-screen label. Verified: 4 physical anchors hold
(GUITAR=CPR SEG3.SW4, MALLET=CPR SEG0.SW4, BRASS=CPR SEG1.SW4, START/STOP=CPL SEG0.SW4); no button
double-bound; none dropped; every bit = 1<<SW. Driver-side panel_scan translates physical ports ->
per-wire-ADDR bytes via a PHYS_MAP table, emitting the identical frames.

## OPEN ISSUES (pre-existing, NOT changed by the rename -- flagged per Felipe "leave for later")
1. SOUND-CATEGORY BINDINGS: the current driver binds GUITAR/PIANO/... to a bit-0x10 column pattern
   (GUITAR=SEG0F.0x10 -> wire ADDR 0x03 = physical SEG3); an older probe (panel-board-decode.md) put
   them on SEG0C bits0-5. The notes disagree on which normalize table is active. Needs a live per-bit
   probe. The rename follows the CURRENT driver+layout.
2. CPC MUTE 11-16 + PAGE + DISPLAY HOLD + EXIT ride driver SEG0A/SEG0B, which some notes mark as
   firmware no-ops (possibly dead). Unresolved -- verify the events reach the firmware.
3. 8 physical buttons are UNBRIDGED (no confident driver binding): CPL ORGANIST, 60s & 70s
   (RETRACTED per Felipe: earlier transcribed here as "BIG BAND & SWING, GOSPEL & BLUES" -- those two
   genre buttons are NOT on the KN7000 panel; the two orphan CPL RHYTHM-GROUP genre cells are really
   ORGANIST = driver SEG01/CPL_SEG1 and 60s & 70s = driver SEG02/CPL_SEG2);
   CPR CUSTOM PANEL; CPR LCDR 1-5 (LCD-right soft-keys). Included as named IPT_KEYBOARD "[unbound]" bits.
4. PART SELECT (L/R1/R2) + CONDUCTOR (L/R1/R2) + TRANSPOSE R2 +/- : driver bits undifferentiated, so
   the L/R1/R2 and +/- assignment within each is a best-effort guess.
