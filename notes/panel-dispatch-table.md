# KN7000 firmware panel-button dispatch table (decoded 2026-07-07)

The firmware's master map of every panel switch → its event. FULLY DECODED this pass (read live from
the emulator ROM; raw dump in `panel-dispatch-dump.txt`). This resolves several earlier open items.

## PanelButtonDispatch 0x484ADB59
Receives a 2-byte switch frame `[ADDR][bitmap]`. The ADDR is normalized to a `normSeg` (0..0x20),
then a **per-normSeg table at 0x48614978** (33 pointers) is indexed:
```
a2 = *(0x48614978 + normSeg*4)   // per-normSeg entry array
```
Each array is up to 8 entries × 12 bytes `{ f0, mask, type }`, terminated by f0==-1:
- **f0**: low 16 = EVENT. 0x2xxx = music/panel, 0x1xxx = system/UI.
- **mask**: byte0 = bit mask (0x01..0x80), byte1 = bit index, **high 16 = ARG**.
- **type**: 0..4 → action handler.

## Event classes (event = f0 & 0xFFFF)
- **2000/2001 = part OFF/ON (mute pairs)** — arg high byte = firmware part id.
- 2005 = genre select (arg = style id). 2004 = sound/tone selector. 2086 = sound category.
- 2020 START/STOP, 2021/2022/2023 INTRO&ENDING/COUNT, 2030-2033 APC, 2084/2085 FADE/VARIATION,
  2040 = a sound/bank selector (many), 2060-2069/208x/20Ax-20Bx = effects/DSP/pads/misc.
- **1004,1005,1009,1010,1011,1020, 1000 = the SYSTEM buttons** (normSeg 16-1B, 20; type 2/3/4).

## RESOLVED: the mute matrix, cross-validated
The 2001/2000 pairs decode to clean firmware part ids in `arg`'s high byte:
```
nS08: parts 02,03,04,05   nS09: parts 06,07,08,09
nS0A: parts 0A,0B,0C,0D   nS0B: parts 0E,0F,18,17 (+ 20A0)   nS05: 19,1D08,00,01 (messy/other)
```
This MATCHES the empirically-mapped mute matrix (press-count method, see panel-button-map.md):
ioport **SEG04→nS08, SEG05→nS09, SEG06→nS0A, SEG07→nS0B**, same bit positions, and
**mixer part N = firmware part (N+1)**. The firmware table independently confirms all 16 part mutes.

## CAUTION: the ioport→normSeg map is NOT PanelWireNormTable (disproven this pass)
`PanelWireNormTable` at **0x486135A0** (read live) maps wire ADDR → normSeg:
```
ADDR 0x00-0x09 -> nS0C-15   0x10 -> nS1A   0x17 -> nS20
ADDR 0x60-0x6B -> nS00-0B   0x70-0x73 -> nS16-19    0x80-0x8A -> nS0A-13(alt)   0x97 -> nS1D
```
Combined with the driver's `seg_to_addr[]` this SUGGESTS SEG0C-15/1A/20 are identity (ioport SEGi→nSi)
and SEG00-0B/16-19 go through a board-decode. **But an empirical cross-check DISPROVES the identity
half**: ioport **SEG15 0x04 = SYNCHRO & BREAK** (HELP-info, re-confirmed) whereas dispatch **nS15 0x04
= ev 2004 (a sound selector)**. So ioport SEG15 does NOT hit nS15 — PanelWireNormTable is not the
operative wire path for the CPL-group ioports the driver actually emits (0xC0-0xCB etc.). The real
routing is the 4-board frame decoder (0x484AD111 → 32-entry jump table 0x48613108 = CPL/CPC/CPR/CPSD),
still un-pinned. **Do NOT name ioport buttons from this table until the board-decode is traced** —
the empirical HELP-info / press-count maps remain ground truth.

## What IS solid
- The full per-normSeg event+arg decode (firmware-internal view) — see `panel-dispatch-dump.txt`.
- The mute part-id structure: nS08-0B carry firmware parts 02..0F as clean 2001/2000 on/off pairs.
  The empirical mute matrix (ioport SEG04-07 = mixer parts 1-16) matches this part-for-part
  (mixer part N ↔ fw part N+1) — a strong, specific 16-part correspondence, though NOT a proof of
  the general ioport→normSeg map (see the SEG15 counterexample above).
- EXIT = SEG08 0x20 (empirical; unchanged).

## Still open
- **Pin the board-decode** (disassemble 0x484AD111 + jump table 0x48613108). Only then can the
  dispatch table safely name grp3 buttons (incl. the LCD RIGHT soft-keys). Until then: empirical.
