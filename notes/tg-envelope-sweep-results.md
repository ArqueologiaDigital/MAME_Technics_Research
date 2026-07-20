# TG amplitude-envelope SWEEP — AMPLITUDE EDIT -> ENVELOPE screen (2026-07-20)

Felipe's requested sweep: drive each of the 7 on-screen envelope params (ATK PEAK DCY1 SUS1
DCY2 SUS2 RLS, users-manual p172-173) min/mid/max on the real edit screen and capture which
TG register moves. Result: the 7-param amplitude EG is encoded in group-0 regs r0/r1/r2 as
[rate hi | level lo] byte pairs — this FALSIFIES the old presumption that r4..rA are the EG,
and finds the per-sound ATTACK (it is r0's high byte, exactly where the old notes suspected
"r0-r3 vary per sound").

## Method (reusable recipe)
- Screen path: PROGRAM MENUS (CPR_SEG0 0x04) -> SOUND EDIT = LCDR1 (CPR_SEG5 0x10) ->
  AMPLITUDE = LCDL3 (CPL_SEG0 0x20) -> PAGE UP (CPC_SEG11 0x10) = page 2/3 ENVELOPE.
  Default sound = Concert Grand, tone "1st" row edited (tone 2 = untouched control, its
  block never moved: perfect within-run control).
- Value editing: the on-screen up/down chevrons ARE the BALANCE (MUTE) button columns
  under the LCD: ON/OFF=PART2, ATK=PART3 (CPC_SEG8 0x01 up/0x02 down), PEAK=PART4
  (0x04/0x08), DCY1=PART5 (0x10/0x20), SUS1=PART6 (0x40/0x80), DCY2=PART7 (CPC_SEG9
  0x01/0x02), SUS2=PART8 (0x04/0x08), RLS=PART9 (0x10/0x20), SUSTAIN PEDAL=PART10
  (0x40/0x80). Single tap = +-1; HOLD auto-repeats ~12.7 steps/s. The DATA dial does NOT
  edit this screen. Params range 0..100.
- Note trigger: C4 by PORT+MASK — :KEYS1 mask 0x0100 (PORT_GM_NOTE renames the fields to
  'C4' style, so name lookup 'Key C4' fails silently — match by mask).
- Capture: write tap on 0x98040000/0x98050000 (addr write = mem_mask 0x0000FFFF, data
  write = mem_mask 0xFFFF0000).
- ★ GOTCHA 1: taps installed at Lua t=0 DIE during boot (later handler installs kill the
  passthrough). Install taps AFTER boot/navigation (t>=25 s). A dead tap looks exactly
  like "no writes".
- ★ GOTCHA 2: never run two MAME instances on the same SD image: the second boots into a
  degraded state (TG idle refresh frozen, keybed dead) that masquerades as a driver bug.
- Runners: env9.lua (7-param sweep), env10.lua (full-class RLS diff), env11.lua (organ +
  filter probe), all in kn7000-emulator/ with logs env*.log; screen values pixel-verified
  per snapshot.

## RESULT 1: the amplitude EG = r0/r1/r2, [rate | level] byte pairs

Swept values (edited tone-1 voice block; control tone-2 always D27F/3900/4500):

| param | screen | r0     | r1     | r2     | changed byte            |
|-------|--------|--------|--------|--------|-------------------------|
| ATK   | 0      | `D27F` | 3900   | 4500   | r0 hi = ATK rate  0xD2  |
| ATK   | 52     | `417F` | 3900   | 4500   | r0 hi 0x41              |
| ATK   | 100    | `007F` | 3900   | 4500   | r0 hi 0x00              |
| PEAK  | 0      | `D201` | 3900   | 4500   | r0 lo = PEAK level 0x01 |
| PEAK  | 51     | `D24D` | 3900   | 4500   | r0 lo 0x4D              |
| PEAK  | 100    | `D27F` | 3900   | 4500   | r0 lo 0x7F              |
| DCY1  | 0      | D27F   | `F600` | 4500   | r1 hi = DCY1 rate 0xF6  |
| DCY1  | 51     | D27F   | `7B00` | 4500   | r1 hi 0x7B              |
| DCY1  | 84*    | D27F   | `3900` | 4500   | r1 hi 0x39 (baseline)   |
| DCY1  | 88*    | D27F   | `3100` | 4500   | r1 hi 0x31 (restored)   |
| DCY1  | 100    | D27F   | `0000` | 4500   | r1 hi 0x00              |
| SUS1  | 0      | D27F   | `3100` | 4500   | r1 lo = SUS1 level 0x00 |
| SUS1  | 52     | D27F   | `314E` | 4500   | r1 lo 0x4E              |
| SUS1  | 100    | D27F   | `317F` | 4500   | r1 lo 0x7F              |
| DCY2  | 0      | D27F   | 3100   | `F600` | r2 hi = DCY2 rate       |
| DCY2  | 51     | D27F   | 3100   | `7B00` | r2 hi 0x7B              |
| DCY2  | 78*    | D27F   | 3900   | `4500` | r2 hi 0x45 (baseline)   |
| DCY2  | 81*    | D27F   | 3100   | `3F00` | r2 hi 0x3F (restored)   |
| DCY2  | 100    | D27F   | 3100   | `0000` | r2 hi 0x00              |
| SUS2  | 0      | D27F   | 3100   | `3F00` | r2 lo = SUS2 level      |
| SUS2  | 51     | D27F   | 3100   | `3F4D` | r2 lo 0x4D              |
| SUS2  | 100    | D27F   | 3100   | `3F7F` | r2 lo 0x7F              |
| RLS   | 0/100  | D27F   | 3100   | 3F00   | NOTHING (see below)     |

(* = baseline / drifted-restore points, extra samples for the curve.)

So the EG block is:
```
r0 = [ATK rate  | PEAK level(0..0x7F)]
r1 = [DCY1 rate | SUS1 level]
r2 = [DCY2 rate | SUS2 level]
r3 = GATE: 0x87FF at note-on, 0x8000 at KEY-UP (see RESULT 3)
```
Rate bytes: HIGHER = FASTER (screen 0 = fastest). Screen->rate is nonlinear (a curve
table): ATK 0/52/100 -> 210/65/0; DCY 0/51/84/88/100 -> 246/123/57/49/0 (region slope
~-2/step mid-scale, steeper at the ends). DCY1 and DCY2 share the same encoding; ATK's
differs slightly at the fast end (210 vs 246). Level bytes are 0..0x7F, linear with the
0..100 screen scale (0->0x01(PEAK)/0x00(SUS), ~51->0x4D/0x4E, 100->0x7F).

Cross-check with a SECOND sound (TAB ORGAN default, env11): r0/r1/r2 = D27F/727F/727F =
fast attack to full peak, slow-ish DCY1 (0x72) toward SUS1=MAX, same DCY2 toward
SUS2=MAX -> the organ SUSTAINS, exactly the behavior; the piano's 3900/4500 (SUS1=SUS2=0)
= genuine two-stage decay to silence. The per-sound story the old r4..rA reading told
audibly was real but the causal registers are r1/r2.

## RESULT 2: screen RLS (and SUSTAIN PEDAL type) do NOT reach the TG in the audition path
Full-class captures (every TG write, any group) for RLS=0 vs 44 vs 100 and SUSTAIN
LONG/HOLD are BYTE-IDENTICAL (112/112 writes) on the Concert Grand — including the key-up
6-write release burst (odd-block r0=9180 r1=9100 r4/5=AE00 r8/9=22B0). Same on the organ
(RLS 0 vs 100 identical, no burst at all). Interpretations (open): the edit-screen
audition may use a fixed release, or RLS lives entirely in the firmware's key-off
COMPUTATION for normal play (h1/h2/h3 0x4C031949/0x4C031F07/0x4C032490 + curve tables),
or in the chip-side damp bank pre-loaded per sound (r4..rA, which the sweep proves are
NOT the 7-param amplitude EG). The release rate the driver can trust remains: managed
burst rate byte (0x91 for the piano damp) and the rA-hi correlation for chip-side
releases (organ 0xAE fast / pad 0x04 slow — audibly validated across 11 families).

## RESULT 3: r3 is the GATE register — the organ DOES get a key-up write
Every note-on writes r3=0x87FF right before the EG block; every KEY-UP writes r3=0x8000
— on the piano (managed class) AND on the TAB ORGAN (aux bit15 gate-follow class, which
the 2026-07-11 sweep recorded as "ZERO key-up TG writes": that finding is FALSIFIED for
r3/class-0x3000 — the old sweep must have filtered these). Class 0x3000 (group 0x0C)
writes 0x4000 at note-on and ~0x0Bxx-0x0Cxx at key-up (varies per note; key-off
velocity/timestamp?). This gives the driver a UNIVERSAL, class-independent release
trigger: r3 data hi-byte 0x80 = key released.

## What r4..rA are NOT (and might be)
None of the 7 amplitude-EG params nor SUSTAIN PEDAL move r4..rA (always AE00 AE00 AE00 /
sound-specific r7..rA). They are a SECOND per-voice parameter bank. A FILTER ENVELOPE
probe (filter edit page 3/4, PART3 column sweep) produced no register change either
(inconclusive — the column mapping on that page is unverified). Hypothesis consistent
with all data: r4..rA = the chip-side key-off/damp parameter bank (+ possibly key-scaled
rate set): the managed key-up burst REWRITES r4/r5/r8/r9, and the rA-hi release-speed
correlation (organ fast / pad slow) is real. Left open.

## Encoding notes for the driver (rate byte -> time, PROVISIONAL)
The chip's rate->time law is not observable in-emulator (our own envelope would be
circular). Provisional exponential law calibrated to the shipped sound anchors:
  T(rate) = 13.0 * 2^(-rate/20) seconds   (clamped [1 ms, 30 s])
- piano ATK 0xD2=210 -> 9 ms (matches the known ~6 ms fast attack)
- piano DCY1 0x39=57 -> 1.8 s (preserves the shipped Concert Grand decay feel)
- screen-0 DCY rate 0xF6=246 -> 2.5 ms (instant, as the GUI graph shows)
- mid ATK 0x41=65 -> 1.4 s audible swell; ATK=100 (rate 0) -> very slow crescendo
- managed damp burst rate 0x91=145 -> 85 ms (plausible piano damper)
- organ rA 0xAE=174 -> 31 ms stop; pad rA 0x04 -> ~11 s fade
All four anchors stay within audible-plausibility of the previously shipped calibration.
