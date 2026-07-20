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
(RLS 0 vs 100 identical, no burst at all). ~~Interpretations (open)~~ **RESOLVED
STATICALLY (RESULT 5): RLS lives in the firmware's key-off COMPUTATION** — it is the
part-FX +0x48 term of h1's rate sum (h1/h2/h3 0x4C031949/0x4C031F07/0x4C032490 +
curve tables), never a TG register; the second/third hypotheses fall away. The release rate the driver can trust remains: managed
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

## ~~What r4..rA are NOT (and might be)~~ → RESULT 4 (2026-07-20): r4..rB DECODED — the PITCH and FILTER envelopes

The follow-up sweeps (a1.lua / a1b.lua in kn7000-emulator/, logs a1_run.log /
a1b_run.log; every edit pixel-verified per snapshot — the earlier "inconclusive
filter probe" was a wrong-column artifact) drove the FILTER EDIT page 3/4 (FILTER
ENVELOPE) and PITCH EDIT page 2/3 (PITCH ENVELOPE) column-by-column on the Concert
Grand and captured the note-on block after each edit. Column map on both pages:
ON/OFF=PART2, START=PART3, ATK=PART4, PEAK=PART5, DCY1=PART6, SUS1=PART7,
DCY2=PART8, SUS2=PART9, RLS=PART10, STOP=PART11, ADJUST/DEPTH=PART12.

| screen edit | register moved | verdict |
|---|---|---|
| PITCH ATK (PART4) | r4 hi AE→62 | r4 = pitch [ATK rate \| PEAK level] |
| PITCH DCY1 (PART6) | r5 hi AE→62 | r5 = pitch [DCY1 \| SUS1] |
| PITCH SUS1 (PART7) | r5 lo 00→48 | ✓ level in the low byte |
| PITCH DCY2 (PART8) | r6 hi AE→62 | r6 = pitch [DCY2 \| SUS2] |
| PITCH TOTAL DEPTH (PART12) | **r7 hi 2C→7F** | r7 hi = pitch-EG TOTAL DEPTH |
| FILTER ATK (PART4) | r8 hi 99→4D | r8 = filter [ATK \| PEAK] |
| FILTER PEAK (PART5) | r8 lo 00→0A | ✓ |
| FILTER DCY1 (PART6) | r9 hi 35→00 | r9 = filter [DCY1 \| SUS1] |
| FILTER SUS1 (PART7) | r9 lo E8→0A | ✓ |
| FILTER SUS2 (PART9) | rA lo B0→FE | rA = filter [DCY2 \| SUS2] |
| FILTER START POINT (PART3) | **rB lo 00→0A** | rB lo = filter START POINT |
| FILTER CUTOFF ADJUST (PART12) | r8/r9/rA/rB LOW bytes all shift (00→48, E8→14, B0→FE, 0A→70) | ADJUST is folded into every filter level byte host-side |
| FILTER RLS (PART10) | nothing | like amplitude RLS: never reaches the TG at note-on |
| FILTER page 1/4 MODE/CUTOFF/RESO (drastic: LPF+EQ→BPF, 21.1K→392 Hz) | nothing in group 0 | the STATIC filter is programmed elsewhere (not in this bank) |

So the full group-0 note-on block is three parallel 7-param EGs in one layout:
```
r0=[amp ATK|PEAK] r1=[amp DCY1|SUS1] r2=[amp DCY2|SUS2]   r3=GATE 87FF/8000
r4=[pit ATK|PEAK] r5=[pit DCY1|SUS1] r6=[pit DCY2|SUS2]   r7=[pit TOTAL DEPTH|? (lo E8/0A values seen per sound: START/STOP PITCH candidates, untested)]
r8=[flt ATK|PEAK] r9=[flt DCY1|SUS1] rA=[flt DCY2|SUS2]   rB=[? (STOP POINT candidate, untested)|flt START POINT]
rC=7F00, rD=0F10 (constants across all sweeps -- untested)
```
Filter/pitch LEVEL bytes are SIGNED offsets around 0 = screen 40 (curve-mapped:
SUS2 0→0xB0, 38→0xFE; PEAK 50→0x0A), unlike the absolute 0..0x7F amplitude levels.
Rate bytes use curve tables like the amplitude EG (higher = faster; filter ATK 30→0x99,
68→0x4D — a different table than the amplitude ATK's 210-at-0).

Re-readings this forces:
- **The rA-hi "release rate" correlation = the filter-EG DCY2 rate.** Organs (0xAE)
  close the filter instantly at key-up, pads (0x04) sweep it shut over seconds —
  which is why it tracked the audible release character across the 11 families. The
  driver keeps rA hi as its release heuristic (audibly validated) with the semantics
  now documented (kn7000.cpp comment updated; no behavior change, no re-baseline).
- **The managed key-up burst** (+0x14/15=0xAE00, +0x18/19=0x22B0) rewrites the pitch
  ATK/DCY1 pairs to instant-zero and the filter [ATK|PEAK]/[DCY1|SUS1] pairs to
  rate 0x22 toward level −0x50: the piano damper = a slow filter closure to fully
  dark, alongside the r3 amplitude gate-off.
- Multi-sound survey (16 group defaults + 8 piano variants, a1_run.log): r4/r5/r6 =
  AE00 (flat pitch EG) on almost everything — exceptions guitar tone-1 (B508/8200:
  a pluck pitch-drop), synth (BAF6 9A00 9A00: pitch sweep), drum kits / drawbar
  percussive tones (FF00 everywhere + r7=0000: all EGs instant, depth 0). r7 hi
  2C (piano) / 7F (sustainers) / 00 (drums) = per-sound pitch-depth defaults.

Still open: r7 lo / rB hi / rC / rD assignment (START PITCH, STOP PITCH, STOP
POINT candidates; TOUCH & KEY FOLLOW pages untested), and where the STATIC filter
(MODE/CUTOFF/RESO) is programmed — its drastic edits leave the whole a<0x400
note-on block byte-identical.

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

## RESULT 5 (2026-07-20, STATIC RE — the disassembly answers the sweep's open questions)

Source: the CONVERT pass in kn7000_disassembly (commits 935b614/83fdb4b/b321b2f) that
converted the library's TG note path to real source. Everything below is read from the
code (STATIC), cross-checked against the measured RESULTS above; the filter/pitch
attribution of the two descriptor blocks is taken FROM the a1 live decode (RESULT 4) —
statically the two blocks were unlabeled, and the first naming pass had them swapped.

**The shadow register cache.** The 0x84-byte record `0x500CA0B0 + slot*0x84` caches
every group-0 register as a 4-byte entry `[lo16 = note-on value | hi16 = release
value]`: +0 r0, +4 r1, +8 r2, +0xC r4, +0x10 r5, +0x18 r8, +0x1C r9 (+0x0A also holds
the r3 gate-off value; +0x78/+0x7A/+0x7C/+0x80 are dirty masks).

**The managed key-up burst is `TgVoiceEgBurstWrite` (lib 0x4C0376E3)**: it flushes the
RELEASE halves of r0,r1,r4,r5,r8,r9 — exactly the observed 6-write burst (the wire's
regs 0x10/0x11/0x14/0x15/0x18/0x19 = the odd element's bank at +0x10). The release
values are computed at key-off by the h1/h2/h3 trio and packed by their caller
(0x4C0115xx et al: h1 out -> +0x02/+0x06, h2 -> +0x0E/+0x12, h3 -> +0x1A/+0x1E):
- h1 `TgKeyOffAmpRelease` 0x4C031949 -> r0/r1: rate index = **clamp(desc2+0x2E base +
  part-FX record (0x500B5340+n*0x54C) +0x48 RELEASE offset + key-off arg + key
  scaling (desc2+0x31..0x33 breakpoints vs the note), 0..100) -> curve ROM
  0x486D2649**; emits [rate|0x80],[rate|0x00] = the piano's 0x9180/0x9100.
  **This resolves RESULT 2's open**: the screen RLS param DOES act at normal key-off —
  it is the part-FX +0x48 term of this sum (a COMPUTATION input, never a TG register),
  which is why RLS edits move no register at note-on.
- h2 `TgKeyOffPitchRelease` 0x4C031F07 -> r4/r5: desc2+0x11/+0x12, flat
  [rate|0]x2 — the 0xAE00/0xAE00 pitch rewrite of RESULT 4's re-reading.
- h3 `TgKeyOffFilterRelease` 0x4C032490 -> r8/r9: desc2+0x46 rate, signed level
  clamp(desc2+0x47 + desc2+0x3E, -50..50) via 0x486D2713 — **desc2+0x3E is the folded
  CUTOFF ADJUST** RESULT 4 saw in every filter level byte (0x22B0 = sweep shut).
The running-voice (attack/decay) programs come from the same descriptor blocks:
pitch EG = desc2+0x0B..0x12 (0x4C031C50/0x4C031D9B), filter EG = desc2+0x3E..0x4C
(0x4C0321BF/0x4C03231F); amp EG bytes live in the tone descriptor read by
`TgElemNoteOnStd` 0x4C030A9D.

**r3 gate, statically**: `TgVoiceGateOn` 0x4C037398 writes r3 := 0x87FF and
class-0x3000 := (rec+0x54 & 0x18000)|0x4000 at note-on (RESULT 3's values);
`TgVoiceGateOff` 0x4C0376A5 writes class-0x3000 := rec+0x54 & ~0x4000 then r3 := the
cached +0x0A value at key-up — the per-note "~0x0Bxx-0x0Cxx" RESULT 3 measured is
that cached per-note value, not a timestamp.

**The sustain-pedal path**: `TgPartKeyEvent` 0x4C036EA4 (velocity==0 branch) queries
the hold state (0x4C02E0F9): 0xFF/0xFE -> release the note's voices NOW (voice list
0x4C010047, per slot 0x4C03B0CD + slot service(slot,0)); **0 -> mark-only via
0x4C02E2C7 and NO voice release — the pedal-held note keeps sounding and is released
later by the slot-service pass**. Both flavours then run `TgKeyOffSample` 0x4C036573
(key-off retrigger, only for class-0x80 kits whose zone flags 1|2|4 request it).

**Bonus**: the hi-hat-style cutoff is `TgExclGroupChoke` 0x4C0309A5 — descriptor
+0x0E bit7 marks an exclusive group; same-group voices get their r0/r1 release
halves set to a damp rate from table 0x48586EA4, then the same burst writer fires.
