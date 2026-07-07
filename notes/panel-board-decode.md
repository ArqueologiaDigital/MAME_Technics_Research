# KN7000 panel board-decode — PINNED (2026-07-07)

The full path from a wire ADDR byte to a button event, recovered by static disassembly of
`full.bin` (program flash @0x48400000) + live reads. **This resolves the long-standing
normSeg↔ioport puzzle** and corrects last tick's dispatch dump.

## The panel runs in ONE of TWO modes, chosen by RAM flag 0x5006BE94
There are TWO complete panel interpretations. A single flag byte `0x5006BE94` selects between them
(read live: **its value is 1** = the KN7000 mode). Almost certainly the shared KN5000/KN7000
codebase supporting both instruments' panels; the flag=0 tables are the *other* model.

| flag 0x5006BE94 | normalize table            | dispatch table  |
|-----------------|----------------------------|-----------------|
| 0 (INACTIVE)    | PanelWireNormTable 0x486135A0 | 0x48614978  |
| **1 (KN7000)**  | **table2 0x48613620**      | **0x486149FC**  |

⚠️ Last tick I dumped 0x48614978 (the flag=0 table) and got mismatches (e.g. "nS15=sound selector"
vs empirical SYNCHRO). That table is NOT the KN7000's. The KN7000 map is `panel-dispatch-active.txt`.

## Normalizer (0x484ADA16) — ADDR → normSeg
```
index  = ((ADDR & 0xC0) >> 1) | (ADDR & 0x1F)      # bit5 of ADDR is dropped
normSeg = activeNormTable[index]                    # 0xFF = no button
```
Selector `0x484abafd` just returns `*(0x5006BE94)`. Dispatch (0x484ADB59) then indexes the active
dispatch table by normSeg: `entry_array = activeDispatch[normSeg]` (each = ≤8 × {event,mask,type}).

## Resulting ioport → normSeg map (driver seg_to_addr[] → index → table2)
| ioport | ADDR | idx | normSeg | button family (from altS dispatch) |
|--------|------|-----|---------|-----------------------------------|
| SEG00-09 | c0-c9 | 60-69 | **00-09** (identity) | genres/rhythm/APC + **MUTES SEG04-07=parts 0-15** |
| SEG0A,0B | ca,cb | 6a,6b | **0xFF invalid** | (no-op — matches empirical!) |
| SEG0C-13 | 00-07 | 00-07 | **0A-11** | sounds (SEG0C-0E) + effects/one-offs |
| SEG14 | 08 | 08 | **0xFF invalid** | (no-op) |
| SEG15 | 09 | 09 | **12** | 2040/20AE/2021/2011-2016 |
| SEG16-19 | d0-d3 | 70-73 | **14-17** | 1xxx system (1011/1004/1010/1005) |
| SEG1A | 10 | 10 | **0xFF invalid** | (no-op) |
| SEG20 | 17 | 17 | **1D** | 1020 system |
So the driver's "SEGnn" names equal normSeg only for SEG00-09; SEG0C-13→nS0A-11 (offset −2), etc.

## Reconciliation — the active table CONFIRMS all empirical work
- altS04/05/06/07 = 2001/2000 pairs, args 00-0F = **parts 0-15 = mixer PT1-16** → the press-count
  MUTE matrix (SEG04-07) is firmware-confirmed (mixer part N = fw part N−1).
- altS0A = 2004 sound selectors args 004F.. → SEG0C = PIANO etc. (matches).
- SEG0A/0B/14/1A map to 0xFF → firmware-confirmed no-ops (matches the LCD-RIGHT sweep dead-ends).

## Unblocked next steps
1. Name EVERY button: cross the altS event per (ioport,bit) with the HELP-info names + a 0x20xx
   event→name legend (HELP-text pool @0x48394D06). Fix the stale driver PORT_NAMEs from this.
2. LED map: PanelSwitchClassTable is switch#=normSeg*8+bit — now normSeg is known per ioport.
3. LCD RIGHT: the LEFT soft-keys are SEG03 b3-b7 = parts 0x10-0x14 OFF (altS03). Find the ADDR
   whose normSeg carries the right-column-select events (likely an ADDR the driver doesn't emit yet
   = a CPR-board wire address; candidates are indices table2 maps that no current seg_to_addr hits).
