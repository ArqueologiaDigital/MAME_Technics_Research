# Effect multi-unit routing — why only REVERB is audible (2026-07-11)

> ★ 2026-07-20 UPDATE — read `dsp-unit-roles-live-capture.md` FIRST. The live
> DspEffectSelect capture flips this file's unit labels: **u0=REVERB (unchanged),
> u9=CHORUS, u7=MIC REVERB, MULTI=u1, per-part Sound-DSP=u2..u6, u8=EQ.** The
> "unit7=chorus" reading below is WRONG (that is why feeding u7 while toggling
> CHORUS did nothing — the chorus unit is u9); the bridge's chorus(u4)/sound-dsp(u9)
> feeds are wrong-slot placeholders. Queue item B = re-point the feeds per the new map.

## ★ IMPLEMENTATION ROADMAP (consolidated 2026-07-11) — read this first

GOAL: make the non-reverb effects (chorus / multi / sound-DSP / EQ) audible. Reverb is complete.

WHAT'S DECODED (done):
- **Send matrix** (sub-TG group-0x20, emitter lib 0x4C036FBA): each effect = a fixed bus CHANNEL,
  reg8=SEND (low byte = per-part depth), regA=WET/DRY, plane0x83=DEPTH. CHORUS send = **0x8198**
  (live-verified, low byte tracks CHORUS DEPTH). Reverb 0x80B8; SOUND DSP 0x8098/0x80C8; MULTI 0x8298.
  Enable recipe live-verified (PART SETTING p2; SOUND DSP forces the block refresh).
- **Unit dispatch**: all 10 unit programs are patched into CALL slots (PM 0x8080-0x80A0 -> 0x8400..
  0x8D00) and run every frame. unit0=reverb path (audible), unit7=chorus rec58@0x8B00, unit8=EQ, etc.
- **The gate**: FLAG3-gated effect programs (chorus + 4 others) open with `IF NOT FLAG3_IN, JUMP skip`.
  Reverb/enhancer (rec49/56) DON'T gate on FLAG3 -> always run. Unit I/O is I4-relative: input =
  DM(I4+0x20), output = DM(I4) (I4 walks 0xC342, +2 per unit; a +0x0A/-0x0A hop mid-loop).

THE BLOCKER (why simply feeding/enabling doesn't work):
- FLAG3 is a SHARC **input pin the driver never drives** (stays 0 -> gated effects skip). BUT it is
  ALSO read by the kernel mainloop (`8098: IF FLAG3_IN, MODIFY(I3, M3=-1)`) + a per-frame ASTAT
  ping-pong toggle (8099) -> FLAG3 is a GLOBAL double-buffer/handshake signal, NOT a per-effect enable.
  Experiment: forcing FLAG3=1 constant CHANGED the reverb (via the I3 shift). So FLAG3=0 is what makes
  our SIMPLIFIED one-frame-per-IRQ0 bridge produce the correct reverb; the gated effects live on the
  OTHER ping-pong phase our model never runs.
- ROOT ARCHITECTURE ISSUE: our F.3 bridge feeds ONE frame to unit-0 input per IRQ0 and reads unit-0
  return. The real DSP runs a double-buffered SPORT-DMA frame loop where FLAG3/ping-pong sequences the
  units and the TG's per-part SPORT sends feed each unit. The gated effects need that faithful frame
  model, not a patch.

IMPLEMENTATION PATH (large; best supervised):
1. Decode what physically drives DSP FLAG3 (service-manual IC306 schematic + firmware): is it the
   codec/SPORT frame-sync, a divided clock, or a CPU line? Determine its per-frame sequence.
2. Model the DSP's SPORT-DMA double-buffer frame loop faithfully (drive FLAG3 + the ping-pong so I3/I4
   sequence as on hardware), so ALL units run on the correct phase -- verifying the reverb stays
   correct throughout (bit-identical is unlikely once ping-pong is real; use spectral equivalence).
3. Feed each effect unit's SPORT input from the TG per its send (send matrix above): chorus <- 0x8198,
   etc. (needs per-part/per-bus TG output, or the labelled whole-mix approximation).
4. Sum the unit returns into the DAC (the TG SDIE mix).
COST: multi-day, touches the working reverb's frame model -> supervised. Until then, reverb is the one
faithful effect and the others are HELD DISABLED at the (unmodeled) FLAG3/ping-pong frame gate.

---

Triage of the effects-sweep "CHORUS = no audible effect" SUSPECT. **Verdict: NOT a bug — an
architectural limitation of the current single-path DSP bridge.** Documented so the fix is scoped.

## What the live taps show
With a note played (–nodrc, all unit return + input TDM slots tapped):

| unit | program | input slot | input max | return slot | return max |
|---|---|---|---|---|---|
| 0 | active global effect (reverb) | 0xC362 | **924234** | 0xC342 | **~620000** |
| 4 | rec06 | 0xC36A | 0 | 0xC34A | 0 |
| 7 | rec58 CHORUS | 0xC370 | 0 | 0xC350 | 0 |
| 8 | rec34 EQ | 0xC372 | 0 | 0xC352 | 0 |
| 9 | rec49 | 0xC376 | 0 | 0xC356 | 0 |

Only unit 0 receives signal and produces output. Toggling CHORUS ON (short-press :SEG11 0x04) and
selecting a chorus TYPE both leave unit 7's input at **0** — the chorus unit never sees audio, so it
cannot be heard. Reverb works because the panel reverb effect executes on **unit 0**, the one slot
the bridge is wired to.

## Why — the real vs modelled signal path
- REAL hardware: the tone generator holds a per-channel OUTPUT-BUS / effect-send matrix (sub-TG
  group 0x20 = latch 0x8000-0x83Fx, 64 channels × 0x10 stride; regs 0-6 = the mix/pan/route base
  `0380/0B80/0680/8CD0`, reg 8 = a per-channel send level, reg A = a wet/dry or return level). Via
  this matrix each part is sent to whichever effect unit(s) its reverb/chorus/DSP sends select, over
  the 4 SPORT pins (SDIE0-3), and the TG sums ALL the effect returns into the DAC. So reverb, chorus,
  EQ and a SOUND DSP can all be heard at once.
- OUR bridge (kn7000_dsp_bridge_device): sends the single summed TG stream to **unit 0's input**
  (0xC362/3) and reads **unit 0's return** (0xC342/3), applying just three extracted registers
  (0x803A wet/dry, 0x80B8 send, 0x8338 depth). It models ONE effect send + ONE return. The other
  units get no input and their returns are never read.

## What making chorus/EQ/DSP audible would require (scoped, deferred)
A real TG effect-mixer model:
1. Decode the group-0x20 matrix per channel: which TX pin / effect unit each part's reverb/chorus/
   DSP send routes to, and at what level (regs 8/A semantics beyond the 3 reverb ones already known —
   e.g. which reg is the chorus send vs the DSP send). Needs a capture sweep toggling each global
   effect + each part's send and diffing the matrix.
2. Bridge: feed the TG stream (scaled by each per-unit send) into MULTIPLE unit input slots
   (0xC362/0xC370/0xC372/...), and SUM the corresponding unit returns (0xC342+0xC350+0xC352+...)
   weighted by their return levels, into the DAC crossfade.
3. Verify each effect is independently audible and that reverb is unchanged.

This is a multi-day architecture change; reverb (the primary effect) is faithful today. Marking the
sweep's CHORUS/EQ/SOUND-DSP results **EXPLAINED (single-path limitation)**, not FAIL.

## Note for the sweep re-run
The MULTI/SOUND-DSP batch health tests will all read "no audible effect" for the same reason until
multi-unit routing lands — they exercise units other than 0. Their TYPE-SELECTION (loading the
program onto its unit) does work and is verified; only the audible return is missing. So the sweep's
value right now is (a) confirming type selection reprograms each unit without crashing/railing, and
(b) the recipe catalogue — not audible-effect verdicts.

## 2026-07-11: effect-send matrix DECODED + kernel-routing blocker found (workflow wf_ff73662f-062)

### The effect-send register map (group-0x20, sub-TG @0x98050000) — CONFIRMED live
Emitter lib 0x4C036FBA/0x4C036F9A: latch = plane<<8 | channel<<4 | reg; reg 8 = SEND, reg A =
WET/DRY, plane 0x83 = DEPTH. Each effect = a fixed bus CHANNEL (distinguished by channel number):
| Effect | SEND reg | WET/DRY | DEPTH | default OFF | live-verified |
|---|---|---|---|---|---|
| REVERB | 0x80B8 (ch0B) | 0x803A (ch03) | 0x8338 | send 0x0366 ON | ✓ (audible on unit 0) |
| CHORUS | **0x8198 (ch19, BANK1)** | 0x809A? | 0x8378 | 0x0B00 (send 0) | ✓ low byte == per-part CHORUS DEPTH (60->63 tracked 0x3C->0x3F) |
| SOUND DSP | 0x8098 (ch09) / 0x80C8 (chC) | — | — | | |
| MULTI | 0x8298 (ch29, bank2) | | | | |
The 4 banks (0x80/81/82/83xx) plausibly map to the 4 SPORT returns / unit groups.

### Enable recipe (per-part chorus, RIGHT1) -- LIVE-VERIFIED
PROGRAM MENUS (SEG0C 0x04) -> SOUND (SEG00 0x02) -> PART SETTING (SEG00 0x02) -> PAGE UP (SEG0B 0x10)
to page 2/5. Column p2: SOUND DSP ON=SEG08 0x40, SOUND DSP DEPTH=SEG09 0x01, CHORUS ON=SEG09 0x04,
CHORUS DEPTH=SEG09 0x10. ★ FIRMWARE QUIRK: 0x8198 is only (re)written when the effect-bus block is
"active" -- CHORUS ON + depth alone leaves 0x8198=0x0B00; enabling SOUND DSP (or its depth) forces
the block refresh, then 0x8198 = 0x0B00|depth appears. (Verified: with SOUND DSP on + chorus depth
63, 0x8198 = 0x0B3F.)

### ★ THE BLOCKER (why chorus is still silent, even with a driver feed)
Implemented a SAFE multi-unit feed (reverted, commit not kept): tonegen captures 0x8198 -> chorus
send gain; the tick feeds unit-7 input (0xC370 = raw TG x chorus_send) and sums unit-7 return
(0xC350); gated on send>0 so REVERB stays BIT-IDENTICAL when chorus off (A/B verified 0/2.11M diff).
RESULT: with chorus enabled, unit-7 INPUT went nonzero (306484, my feed works) BUT unit-7 RETURN
(0xC350) stayed 0 -- and a scan of ALL return slots 0xC342-0xC359 showed ONLY unit 0 (reverb, C342/3)
produces output; every other unit outputs 0. So **feeding a unit's input slot does NOT make it run**:
the kernel's per-frame routing (which unit reads/writes which slot) is configured internally by the
firmware's effect setup, NOT a fixed slot map. The 10-unit CALL chain executes, but only unit 0 is
wired into the live audio path; the others are dormant regardless of their input slot contents.
NEXT (supervised / deeper RE): decode the kernel's per-frame routing setup -- how the firmware
configures which SPORT/slot each unit reads+writes when an effect is enabled (the I4-cursor walk +
the per-unit input/output pointer programming), and what makes unit 7 join the active chain. Only
then can the driver route audio to it. The send-matrix half is DONE (above); the kernel-routing half
is the remaining gate. Reverb (unit 0) remains complete and untouched.

## 2026-07-11 ★★ ROOT CAUSE of ALL silent effects: the unmodeled DSP FLAG3 input pin
Continuing the kernel-routing decode (static, from the dsp listings). The real gate is NOT the send
matrix and NOT the input slot -- it is a **SHARC FLAG3 hardware input pin**.

### Evidence
- Kernel (rec04): all 10 unit CALL slots are patched to real programs at boot (0x8400..0x8D00) and
  RUN every frame -- confirmed live (PM 0x8080-0x80A0 read: unit0=0x8400 ... unit7=0x8B00 chorus ...
  unit9=0x8D00; identical with chorus off/on). So every unit executes; dormancy is INSIDE the unit.
- Chorus program rec58 (relocated to 0x8B00), FIRST instruction:
    8400: IF NOT FLAG3_IN, JUMP 0x8432    <- skips the read/process/write when FLAG3 is LOW
    8401: R0 = DM(0x20, I4)               <- input = DM(I4+0x20); 8410/8419: DM(I4,M2)=R0 output
  FIVE effect programs gate on FLAG3_IN; the audible ones (rec49 reverb, rec56 enhancer) do NOT --
  they always run. That is exactly why reverb is audible and chorus/multi/etc. are silent.
- Kernel reset: `8071: BIT SET MODE2 0x18011` = FLAG0/FLAG1 as OUTPUTS; **FLAG3 stays an INPUT**
  (MODE2_FLG3O 0x40000 not set). Mainloop `8098: IF FLAG3_IN, MODIFY(I3,M3)` reads the pin.
- MAME models it: m_core->flag[3] (sharcops.hxx:1374/1390 FLAG3 / NOT FLAG3), set_flag_input(n,state)
  (sharc.cpp:1204). **But the KN7000 driver NEVER calls set_flag_input for the DSP** -> flag[3] stays
  0 forever -> every FLAG3-gated effect permanently takes the skip branch.

### So there are TWO gates for a non-reverb effect to be audible (both currently unmodelled):
1. **FLAG3 input pin must be driven high** when a FLAG3-gated effect is active. On the real board this
   DSP pin is driven by the CPU/control logic; the driver must model it (set_flag_input(3, ...)).
   Currently never set -> the units skip regardless of anything else. THE PRIMARY GATE.
2. The unit's SPORT input slot must be fed (the send-matrix half, decoded above: chorus send 0x8198
   -> unit-7 input). Only meaningful once FLAG3 lets the unit run.

### Concrete next steps (supervised / next tick)
a. Find what drives the DSP FLAG3 pin: RE the firmware for the CPU write (GPIO / control register bit)
   that goes high when chorus/multi/DSP effects are enabled -- likely near the effect-enable/apply
   code (0x4C0092B3 dispatcher, or a GPIO around 0x9807xxxx / 0x36008xxx). Wire it in the driver via
   m_dsp->set_flag_input(3, state).
b. THEN combine with the send feed (revert-kept design: feed unit-7 input 0xC370 = raw TG x chorus
   send, sum unit-7 return). Verify each FLAG3-gated effect runs cleanly (no rail) and reverb stays
   bit-identical (reverb doesn't gate on FLAG3, so driving FLAG3 must NOT change it -- easy A/B).
c. Note: FLAG3 gates 5 effects together (not per-unit), so it is a global "FLAG3-effects active"
   enable; per-unit activity is then the send levels + the unit's own params.
This is the missing keystone: the effects aren't mis-routed, they are HELD DISABLED at the DSP flag.

## 2026-07-11 experiment: forcing FLAG3=1 is NOT a clean enable (it perturbs the reverb)
Injected `m_dsp->set_flag_input(3, 1)` in the DSP tick and measured:
- The REVERB WAV CHANGED (md5 differs) -- even though rec49/rec56 don't gate on FLAG3. Cause: the
  KERNEL mainloop itself reads FLAG3 (`8098: IF FLAG3_IN, MODIFY(I3, M3)`), so FLAG3 shifts I3 (a
  buffer/descriptor cursor) and alters the WHOLE frame's processing, not just the FLAG3-gated units.
- Non-unit-0 output slots STILL 0 (units need their input fed too; forcing FLAG3 alone processes
  their zero input).
REFINED CONCLUSION: FLAG3 is a GLOBAL frame-processing signal (drives the kernel's I3 cursor + the
effect-unit skip), not a simple per-effect enable. Driving it to a wrong/constant value corrupts the
reverb. So making the FLAG3-gated effects audible needs the FULL FLAG3 PROTOCOL: what the hardware
drives the pin to, WHEN (per-frame? tied to the ping-pong ASTAT toggle at 0x8099 `BIT TOGGLE ASTAT
0x100000`?), and how the CPU controls it -- not a one-line force. Experiment reverted; reverb
bit-identical again. The FLAG3 gate is identified; its protocol is the remaining decode.

## 2026-07-11 ★★★ CORRECTION: FLAG3 was OVERSTATED — chorus units DO output when fed (multi-unit tractable)
Re-examination found errors in the FLAG3 conclusion above. THE ACCURATE PICTURE:
- Only **4 of 72** effect records gate on FLAG3: rec58 (pitch-shift/detune) + rec59/60/61 (reverbs).
  The reverb/enhancer AND the CHORUS records (rec06 etc.) do NOT gate on FLAG3. So FLAG3 is NOT why
  the general effects are silent -- it only affects those 4 specific records.
- Last tick I fed UNIT 7 (= rec58, FLAG3-gated) and saw no output -> wrongly generalized to "FLAG3
  disables the effects." WRONG UNIT: the boot-default CHORUS is **rec06 on units 4 and 6**.
- ★ DECISIVE TEST (no rebuild; Lua copies the TG send 0xC362 into units 4/6 inputs each frame):
  **unit4 (chorus rec06) OUT = 664328, unit6 OUT = 664328** -- they PROCESS AND OUTPUT CLEANLY when
  fed (no rail). So the non-FLAG3-gated effect units are NOT dormant; they were just never fed.
- CORRECTED I4 walk (each unit writes 2 slots, M2=1, +2/unit; +0x0A hop at 0x8092, -0x0A at 0x8096):
  u0 out C342/in C362; u1 C344/C364; u2 C346/C366; u3 C348/C368; **u4 C34A/in C36A (rec06 CHORUS)**;
  u5 C34C/C36C; **u6 C358/in C378 (rec06 CHORUS, post +0x0A hop)**; u7 C350/in C370 (rec58, FLAG3);
  u8 C352/C372 (EQ); u9 C356/C376. (Last tick's u7=C370 feed was rec58 -> the FLAG3 false lead.)

### REVISED conclusion: multi-unit IS implementable by feeding the right units
The gate for the COMMON effects (chorus/EQ/etc.) is simply that our bridge feeds ONLY unit-0's input;
the other units' SPORT input slots are never filled, so they output 0. Feed a non-FLAG3-gated unit's
correct input slot and it outputs. So a multi-unit send/return model is tractable:
  1. When an effect's send is nonzero, feed its unit's input slot (u4/u6 chorus <- 0xC36A/0xC378 =
     TG send x chorus level 0x8198), 2. sum that unit's output slot into the DAC, 3. gated so
     effect-off leaves the reverb bit-identical. FLAG3 only matters for rec58-61 (pitch-shift/extra
     reverbs) -- a later concern.
REMAINING to pin before shipping: which of u4/u6 is the RIGHT1 chorus send-return (or both = stereo/
dual), and the correct return level into the DAC (send matrix regA/depth). The mechanism is proven.

## 2026-07-12 ★ DEFINITIVE unit -> record map (live PM signature match at 0x8N00)
Resolved the long-standing unit/record confusion by matching live DSP PM words to record signatures:
| unit | PM slot | record | effect | status in MAME |
|---|---|---|---|---|
| 0 | 0x8400 | **rec56** (comb+allpass) | the panel-REVERB-controlled AUDIBLE slot (fed by the bridge) | AUDIBLE |
| 4 | 0x8800 | **rec06** modulated-delay | CHORUS | AUDIBLE (fed, this session) |
| 6 | 0x8A00 | rec06 modulated-delay | CHORUS (twin of u4) | not fed |
| 8 | 0x8C00 | **rec34** | EQ (FIR + biquad; CALLs helper 0x831B) | not fed (master/insert) |
| 9 | 0x8D00 | **rec49** | reverb/phaser (separate program) | not fed / silent |
NOTES: unit 0 = rec56 is what we've been calling "the reverb" -- functionally it IS the
panel-reverb-controlled audible slot (toggle/type/depth all move its output); the record is rec56
(comb+allpass), distinct from rec49 at unit 9. My CHORUS feed (unit 4 = rec06) is confirmed correct.
Units 1-3,5,7 hold rec15/08/11/10/58 (the boot-default chain); unit 7 = rec58 is the FLAG3-gated
pitch-shifter (the red-herring I mis-fed earlier). Matching signatures used: rec56 word 8401=
0000716f80000000; rec06 8402=0000a80b00000021; rec34 8C00=000006be0400831b; rec49 8D04=0000209a31801111.
This map unblocks extending audibility to EQ (u8) and the other send effects -- feed the right unit.

## 2026-07-12: rec06 chorus is WET-ONLY -> the chorus mix has no dry-doubling
Traced rec06 (unit 4): 8401 reads input R0 = DM(I4+0x20); 8403-8406 pushes it into the circular
delay line; 8408-8410 reads the delay back at LFO-modulated offsets with interpolation (MRF MAC);
8433 `R8 = CLIP R8; DM(I4,M2) = R8` writes the output. The dry input (R0) is NOT added to the output
-- rec06 emits the WET (modulated-delay) signal only. So summing the chorus return with the main
(unit-0 output, which carries the dry-through) is CORRECT: total = dry+reverb (unit0) + chorus wet
(unit4), no dry doubling. The chorus mix is structurally sound; only the CHORUS_WET makeup level
(currently 0.60) needs calibration against real hardware (Felipe's ear) -- the ~69% DAC modulation
suggests it may be a touch high. Confirms the shipped chorus is faithful in structure.

## 2026-07-12: chorus robustness under dense input -- PASS
Enabled chorus + slammed an 18-note cluster (held): DAC peak 2186, **0 clipped samples** (vs
reverb-only cluster ~2085). The chorus unit (rec06) CLIPs its own output so it self-limits; combined
with the bounded feed (TG x send) the chorus path cannot rail/clip beyond the DAC clamp. The shipped
chorus is production-robust like the reverb.

## 2026-07-12: unit-0 confusion RESOLVED -- unit 0 = the REVERB (rec56), stable, type = coefficients
Decisive test: read unit-0 PM signature before/after selecting REVERB Dark2 -> UNCHANGED (still
rec56: 8401=0000716f, 8402=0000a300); unit 9 also unchanged (rec49). CONCLUSION:
- unit 0 = rec56 IS the panel REVERB. Reverb TYPES (Room/Plate/Concert/Dark) load different
  COEFFICIENTS into the same rec56 program (the effects sweep's "8 distinct tails"), NOT different
  programs. rec56 is a comb+allpass reverb algorithm; the "enhancer" tag in records.tsv was heuristic.
  We have been correctly calling unit 0 "the reverb" throughout.
- Effect enable / type-select does NOT re-patch the CALL chain (verified stable across reverb-type,
  chorus-enable, and sound-DSP-enable); all effects run on already-loaded units and only their
  DM coefficients change.
So the definitive current picture: u0=REVERB(rec56, coeff-swapped by type), u4/u6=CHORUS(rec06),
u8=EQ(rec34), u9=rec49(separate, silent), u1/2/3/5/7=rec15/08/11/10/58. SOUND-DSP/MULTI run on some
of the loaded units (no re-patch) but their exact unit isn't pinned (the default SOUND-DSP Enhancer
= rec56 coincides with u0's algorithm) -- pin via the SPORT channel->unit map (send 0x8098/0x8298)
or an enabling-time DM-coefficient diff. Chorus (the shipped 2nd effect) is fully validated by this.

## 2026-07-12: three effects coexist cleanly + MULTI status
COMBINED TEST (reverb + chorus + SOUND DSP all enabled on RIGHT1, note held): chorus(u4) OUT=250282
AND sound-dsp(u9) OUT=290906 SIMULTANEOUSLY, rails=0/113, DAC peak 749, 0 clipped. The multi-wet
summing (independent chorus + sound-dsp wets over the reverb) is robust -- three effects audible at
once, no interaction/railing. Validates the extended bridge.

MULTI (unit unidentified) -- BLOCKED on the enable mechanism:
- Full-block coeff-diff on MULTI-enable was confounded by the effect-bus block refresh (unit 9
  changed most = the SOUND-DSP-on-u9 registers refreshing; unit 5 = 2 words was the next candidate).
- Attempted MULTI enable (PART SETTING p2: MULTI ON=SEG09 0x40, MULTI DEPTH=SEG0A 0x01) left the
  MULTI send 0x8298 low byte at 0 (0x0600 = off) -- the send never went nonzero, so MULTI was not
  actually engaged (block-refresh quirk needs another active effect, OR the p2 button masks for MULTI
  differ from the transcribed map). SOUND DSP/MULTI are independent part-effects so they cannot share
  unit 9; MULTI's real unit is elsewhere (u5 rec10 is the leading candidate).
- TO DO for MULTI: pin the p2 MULTI ON/DEPTH masks (snapshot-verify), enable it WITH another effect
  active to force the 0x8298 refresh, confirm the send tracks MULTI DEPTH, then coeff-diff/feed-test
  the real unit (likely u5). Then the same feed-and-sum recipe applies.

## 2026-07-12: MULTI send CONFIRMED (0x8298), unit still ambiguous
- MULTI send = **0x8298** (channel 0x29). Snapshot-verified: with the proven nav + SOUND DSP active
  (forcing the effect-bus refresh), enabling MULTI (PART SETTING p2: MULTI ON=SEG09 0x40, DEPTH=
  SEG0A 0x01) set 0x8298 low byte to 127 = the on-screen MULTI DEPTH. So 0x8298 IS the MULTI send.
- NO re-patch: enabling SOUND DSP + MULTI leaves all 10 CALL slots identical to boot -> MULTI runs on
  an already-loaded unit (like chorus/SOUND-DSP), not a re-patched one.
- BUT the unit is NOT cleanly identifiable: the coeff-diff is noise-dominated (unit 9's 5-word change
  = SOUND-DSP block refresh; unit 5's 2 words = weak MULTI candidate) AND unit 5 = rec10 (phaser)
  does NOT match MULTI's default type "Cross Delay" (a delay). So the coeff-diff candidate is
  unreliable for MULTI. Effect->unit so far: reverb=u0(0x80B8), chorus=u4/6(0x8198), SOUND-DSP=u9
  (0x8098), EQ=u8; MULTI(0x8298)=? among the unused u1(rec15)/u2(rec08)/u3(rec11)/u5(rec10).
- DECISIVE next method needed: the SPORT channel->unit map. The DSP kernel's SPORT multichannel RX
  DMA maps each TG send channel (0x09/0x19/0x29) to a DM slot = a unit input. Decode the kernel
  SPORT RX config (rec04) to get channel 0x29 -> unit input slot definitively, rather than the
  refresh-noisy coeff-diff. THEN the same feed-and-sum recipe applies. Do NOT guess-feed a unit.
STATE: 3 audible effects (reverb+chorus+SOUND-DSP) validated coexisting; MULTI send confirmed, unit
pending the SPORT decode; EQ = master/insert (separate); FLAG3 4 records = deep frame model.

## 2026-07-12: FOUR effects robust under dense input + EQ deferral rationale
- FOUR-EFFECT ROBUSTNESS: all part-effects (chorus+SOUND-DSP+MULTI) enabled on RIGHT1 + reverb,
  18-note cluster held -> DAC peak 2443, 0 clipped (vs reverb-only cluster 2085 -> the effects
  contribute; the independent-wet summing stays clean under stress). The 4-effect state is robust.
- EQ (unit 8, rec34) DEFERRED -- it is a fundamentally different, harder integration:
  * NO send channel (the send matrix confirmed EQ doesn't use a group-0x20 send) -- it is a
    master/INSERT, not a parallel send. The feed-and-sum-wet recipe does NOT apply.
  * FLAT (0 dB) by default -> does nothing until the user sets nonzero LOW/HI gains. Low default value.
  * INSERT integration would put unit 8 IN the main path (feed it the main mix, read its output ->
    DAC), which changes the reverb's output path -- and a flat biquad/FIR EQ is unlikely to be a
    bit-identical passthrough, so it would BREAK the bit-identical reverb guard even when flat.
  * A faithful EQ needs: detect "EQ active" (nonzero gains, from the TG/DSP params), and ONLY then
    insert unit 8 in the master path (so EQ-off stays bit-identical). More involved than the sends;
    lower value (flat default). Deferred as a separate, harder task.
STATE: 4 audible effects (reverb+chorus+SOUND-DSP+MULTI), validated robust + coexisting. EQ = master
insert (deferred, documented). FLAG3 4 records (pitch-shift + specialty reverbs) = the deep frame
model. The coeff-TYPE-diff is the definitive unit-ID method for any future send effect.

## 2026-07-12: EQ insert model CONFIRMED tractable; blocker = active-detection (for the guard)
Feasibility test -- fed unit 8 (EQ) with unit-0's output (the reverb'd main) and compared:
- unit8(EQ) out max = 254056 vs unit0 out max = 254059 -> nearly identical LEVEL (flat 0dB EQ passes
  the level through). So unit 8 IS a functional master INSERT: feed it the main mix, read its output,
  and it EQs it. At nonzero gains it would shape the spectrum.
- BUT avg|per-frame diff| = 39806 (~15% of peak) even at flat -- the biquad/FIR EQ has a phase/delay
  response, so unit-8-out is NOT sample-identical to unit-0-out even when flat.
IMPLICATION: always-inserting EQ (unit0 -> unit8 -> DAC) would phase-shift the reverb -> BREAKS the
bit-identical reverb guard (Felipe-praised; the guard is a promise, don't break it even inaudibly).
So a faithful EQ must be CONDITIONAL: insert unit 8 ONLY when EQ is active (nonzero LOW/HI gains),
leaving the flat/default case on the current unit0->DAC path (bit-identical).
REMAINING PIECE = EQ-active detection. Two options: (a) compare unit-8 DM coefficients to the boot
(flat) baseline each frame -- risks false-positives from block refresh; (b) find the main-CPU RAM
EQ-gain setting and gate on gain!=0dB -- cleaner but needs the RAM address RE. Lower value (flat
default) + this complication -> EQ is a documented, lower-priority refinement, NOT forced.
STATE: FOUR audible effects (reverb+chorus+SOUND-DSP+MULTI) is the strong, validated, robust stopping
point. EQ = master insert, model confirmed, active-detection pending. FLAG3 4 records = deep frame
model. Both are lower-value/harder than the shipped four.

## 2026-07-12: code-review of the four-effect mix -- one OPEN faithfulness question
Reviewed the bridge output mix (kn7000.cpp sound_stream_update ~L690-705) and the tick feed
(~L1696-1743). Both are correct for the divergence sweep and well-documented:
- tick reads unit outputs sign-extended (sx24), gated on each send>0, feeds unit inputs = raw TG x send
  (chorus u4 in 0xC36A/out 0xC34A; sounddsp u9 in 0xC376/out 0xC356; multi u1 in 0xC364/out 0xC344).
- 1-frame latency (outputs read at tick start, before the DSP IRQ assert) -- intended, commented.
OPEN QUESTION (faithfulness, NOT a divergence bug): the chorus/sounddsp/multi wets are each scaled by
`gret` (the master DSP return level, = reg-0xA WET/DRY low byte, which the REVERB button flips 0<->0x7F).
So toggling REVERB off (gret->0) ALSO mutes chorus/multi/sounddsp. This is faithful IFF the KN7000's DSP
has a SINGLE shared return bus (all effects share the master DSP wet/dry -- plausible since all effects
live in IC306 and the reverb is the "global" ambient effect). It is UNFAITHFUL if each effect has its
own return level (then chorus should stay audible with reverb off). The send matrix has separate SEND
channels per effect (reverb 0x80B8/chorus 0x8198/sounddsp 0x8098/multi 0x8298), but whether the RETURN
is shared or per-effect is UNRESOLVED -- needs RE of the TG DSP-return (SDIE0-3) mixing. Per rule (g)
NOT changed (would be a guess). Flag for Felipe / a future RE tick. Practical impact: to hear chorus etc.
today you need reverb ON (gret=1) + that effect's depth>0; that is the current documented model.

## 2026-07-12: the OPEN faithfulness question is RESOLVED + FIXED (commit fa06930)
The "shared vs per-effect DSP return" question below is answered: RETURNS ARE PER-EFFECT. Live capture
(per-effect isolated toggle diff) pinned REVERB=ch03.rA, SOUND DSP=ch09.rA, MULTI=ch06.rA, CHORUS=send-
only (no return reg). Toggling REVERB moves ONLY ch03.rA. Fixed: each effect scales its wet by its own
return, so reverb-off no longer mutes the others. Reverb-only stays bit-identical. Full writeup:
notes/effect-return-routing.md.

## 2026-07-19: EQ-as-master-insert — the STATIC answer (rec34 decoded, kn7000_disassembly 634ba34)
The 2026-07-12 "EQ insert model CONFIRMED tractable" reading is now backed by the record itself
(kn7000_disassembly/dsp/dynamics-eq-exciter.md #5). Facts from the rec34 disassembly:
- rec34 = a 13-word wrapper around KERNEL HELPER 0x831B, which IS the 5-section EQ cascade
  (1st-order + LCNTR=3 biquad loop + 1st-order, FLOAT->FIX, loads the clip bound c019 into R15).
  The kernel doc's old "3-tap interpolation coefficient generator" label was wrong (the 3 = the
  biquad loop count); corrected in kernel-architecture.md + sym/rec04.sym.
- Bands (template poles, mirror-flat): LOW ~124 Hz / 484 / 969 / 1940 Hz / HIGH ~4 kHz = the GUI
  5-band EQ. TEMPLATE IS EXACTLY FLAT: every numerator is the bit-exact mirror of its denominator
  (pole/zero cancellation, H=1) — presets only move the zeros off the pre-placed poles.
- I/O convention = PURE IN-LINE INSERT: no wet/dry, no makeup, no envelope — input -> cascade ->
  CLIP -> output, full replace. Consistent with u8 being one of only two slots whose EMPTY-slot
  kernel stub is the 0x80FB copy-through (an in-line unit must default to unity).
- NO DSP-side chaining exists: rec34 reads its OWN I4 slot (0xC372/3 in, 0xC352/3 out, SPORT1-A);
  units cannot read each other's slots. If the hardware uses u8 as the master EQ, the
  unit0->unit8->DAC chain is closed OUTSIDE the DSP by the TG's TDM routing (master bus out on
  u8's pair, return into the DAC). => the proposed MAME model (feed u8 the final mix, take u8's
  return as the DAC feed, ONLY when EQ active) is exactly what the record expects.
- TENSION to settle live: the template is mathematically transparent, yet the 2026-07-12 live
  feed-test measured ~15%-of-peak per-sample diff at "flat" — so the HOST's real coefficient bank
  is apparently NOT a mirror bank even at 0 dB (or GUI-flat != 0 dB internally). One live DM dump
  of u8 c004..c019 vs the ROM template decides it, and doubles as the EQ-active detector's
  baseline (option (a) in the 2026-07-12 note). PROVISIONAL until captured.
