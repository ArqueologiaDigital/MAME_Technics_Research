# KN7000 firmware panel-button dispatch table (2026-07-07)

Found while locating EXIT statically. This is the firmware's master map of every panel switch
to its event — a huge lead for finishing the panel, but with an UNRESOLVED index-alignment
caveat (below), so treat the raw table with care.

## PanelButtonDispatch 0x484ADB59
Receives a 2-byte switch frame `[normSeg][bitmap]` (normSeg 0..0x20). Indexes a **per-SEG table
at 0x48614978** (33 pointers, one per normSeg; alt table 0x486149FC when flag 0x5006BFB2==1):
```
a2 = *(0x48614978 + normSeg*4)   // per-SEG entry array
```
Each per-SEG array is 8 entries × 12 bytes `{ f0, mask, type }`, terminated by f0==-1:
- **f0**: low 16 bits = the button EVENT (0x2xxx music / 0x1xxx system); high bits 0x0070.. = class.
- **mask**: low byte = bit mask (0x01..0x80), byte1 = bit index; high 16 bits = arg (undecoded).
- **type**: 0..4, selects the action handler (0x484adcd2 / 0x484add1b / 0x484add86 / ...).

## Event grid (event = f0 & 0xFFFF; from dump_disp)
- normSeg 01, 02 = **all 0x2005** (16 genres)
- normSeg 05, 08, 09, 0A, 0B = **0x2001/0x2000 pairs** (part ON/OFF = mutes)
- normSeg 00 = transport (0x2020 START/STOP, 0x2022/0x2021 INTRO&ENDING)
- normSeg 03/04/06/07 = rhythm/APC/pads controls (0x2030-0x20B4, 0x2084/0x2085 fade/variation)
- normSeg 0C-13 = sounds + effects (0x2086 category, 0x2004 selector, 0x2008-0x20BD)
- **normSeg 16-1A, 20 = the 0x1xxx SYSTEM buttons** (0x1004,1005,1009,1010,1011,1020).
  normSeg 1B-1F have NO wire path (not panel-serial buttons, per the driver).

## EXIT — NOT YET FOUND (earlier SEG20 0x01 claim was WRONG)
The 0x1xxx class = system/nav buttons; the 6 candidates were normSeg 16-1A,20 bit0. An emulator
test (open HELP modal, press each, watch the screen hash) showed **only SEG20 0x01 closes HELP** —
SEEMED to close HELP -- but SEG20 0x01 is actually a TEMPO control; the HELP screen shows the tempo digit, so the hash changed without closing HELP. EXIT is NOT SEG20 0x01. (Also: the normSeg 0x1xxx candidates relied on the unresolved normSeg==layout-SEG assumption, which is false.) Find EXIT via the HELP-info method (the bit that turns HELP mode OFF). IvExitProc 0x4841EAE3 is the *screen*
handler it ultimately reaches (references the "EXIT" string 0x4859F234 on GUI msg 0x6003a).

## UNRESOLVED: normSeg vs layout-SEG alignment
The driver assumes m_seg[i] == firmware normSeg i (seg_to_addr is the inverse of PanelWireNormTable
0x486135A0). But EMPIRICAL findings contradict the raw table at some segs:
- layout SEG09 0x01 → PADS BANK (snapshot), but the table's normSeg09 0x01 = 0x2001 (a mute).
- layout SEG00 b2-b7 → genres (snapshot), but normSeg00 = transport.
Yet SEG05 mutes DO line up (user: layout SEG05 = parts 7,8; table normSeg05 = mute pairs).
So there is a partial remap between layout-SEG and firmware-normSeg that is NOT yet pinned. Also
PanelWireNormTable[0xC0..0xCB] = 0xFF (the grp3 addresses the driver emits for SEG00-0B don't
reverse-normalize to 0-0x0B) — so either that table isn't the whole story or grp3 is normalized
elsewhere. **Next tick**: pin the remap (disassemble the panel-serial receiver that builds the
[normSeg][bitmap] frame, or read PanelWireNormTable's real structure) — once aligned, this table
maps EVERY remaining panel button in one shot. Until then, verify each binding empirically.
EXIT stands on the empirical HELP-close test, independent of this caveat.
