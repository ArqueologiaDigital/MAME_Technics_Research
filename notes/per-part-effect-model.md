# KN7000 per-part effect model — the group-0x20 send/depth decode is INCOMPLETE (2026-07-13, night 21)

## How this was found
Added a temporary `logerror("[FXSEND] ch=%02X reg=%X data=%04X")` in the tonegen's group-0x20 decode
(`(addr & 0xFC00) == 0x8000`, kn7000.cpp ~line 331) firing on every tg1 reg-0x08 (SEND) / reg-0x0A (RETURN)
write with a nonzero low-7 payload, ran with `-log` (logerror only reaches error.log with `-log`!), and
pressed the effect toggles (REVERB, CHORUS SEG11 0x04, MULTI SEG10 0x04, SOUND DSP SEG0F 0x08).

## The data (error.log, ~141 send/return writes across boot + toggles)
SENDS (reg 0x08), nonzero low7, by channel:
- **0x03xx family (send level in low byte)** on ch **0x06 (0328/0366), 0x07 (0366), 0x09 (0328), 0x0B
  (0366/0328), 0x29 (0650), 0x2C (082D)**.
- **0x85xx/0x8Cxx family (0x85 base + low byte = DEPTH)** on ch **0x30,0x31,0x32,0x33,0x34,0x35,0x36,0x37,
  0x39,0x3B** (values 8550/857F/8C7F).
RETURNS (reg 0x0A) = 0x007F on ch 0x03, 0x06, 0x07, 0x09, 0x0B.

## What the emulator currently decodes (kn7000.cpp tonegen)
ONLY: ch 0x03.rA (reverb direct/return), 0x0B.r8 (reverb send), 0x33.r8 (reverb TOTAL DEPTH), 0x19.r8
(chorus send), 0x09.r8 (sound-dsp send), 0x29.r8 (multi send), 0x06.rA (multi return), 0x09.rA (sound-dsp
return). So it handles a HANDFUL of channels and MISSES the rest (0x07 sends, the whole 0x30-0x3B depth bank
except 0x33, 0x2C, etc.). => **the effect model is PER-PART (one send + one depth channel per part/bus) and
the driver only models a few "global" ones.** The reverb works because its global send (0x0B) IS decoded.

## Two concrete consequences (reframes the chorus/multi "blocked" story)
1. **MULTI toggle SEG10 0x04 DOES write ch 0x29 = 0x0650** => m_gain_multi = 0x50/127 = 0.63 (SEND set), AND
   dsp_audio_tick DOES feed unit 1 (0xC364 = rawTG*mulsend, line ~1803) and read its return -- yet the multi
   output 0xC344 stays 0 even with proper settle timing. So it is NOT a feed bug. ROOT CAUSE: the multi DSP
   ALGORITHM isn't loaded. MULTI is a TYPE-selectable effect (many types); enabling the send + feeding the
   unit is not enough -- the kernel needs a MULTI EFFECT TYPE selected (the "MULTI EFFECT PAGE n/8" screen,
   Felipe's P2 scenario) to upload the unit-1 microprogram. Without a type, unit 1 runs null -> 0 out. This
   is why REVERB works (its algorithm is always loaded) and SOUND DSP works (SEG0F 0x08 loads a default type)
   but MULTI/CHORUS don't (no default type). NEXT to make MULTI/chorus audible: reach the effect-TYPE-select
   screen (MULTI EFFECT / CHORUS TYPE) and pick a type, so the DSP loads the algorithm; THEN the already-
   correct send+feed path produces output. That is the real gate, not a driver bug -- the driver models the
   send/feed correctly; the missing piece is user-side effect-type selection (a panel-navigation flow).
2. **CHORUS toggle SEG11 0x04 writes NO ch 0x19** (the decoded chorus-send channel) at all => SEG11 0x04 is
   NOT the chorus send toggle (or chorus is enabled by a different path). The layout's GLOBAL-EFFECT CHORUS
   binding is suspect; the real chorus enable needs finding (watch for a ch 0x19 write while sweeping panel
   buttons with this same [FXSEND] log).

## Why factory sounds showed only reverb
A normal boot + sound-select writes NO group-0x20 sends during selection -- the reverb is active via the
driver's DEFAULT m_gain_send=0.80, not a per-sound write. The per-part sends/depths above are written at BOOT
and by the effect TOGGLES, not by choosing a sound. So sounds don't carry chorus in this model.

## Verdict / next
This is a real DECODE GAP (per-part effect model incompletely modeled), NOT "effects unused". Fixing it is a
sizeable but high-value task: (a) map channels 0x30-0x3B (per-part depths) + 0x06/0x07 (per-part sends) to
parts/buses; (b) feed the chorus/multi/sound-dsp DSP unit INPUTS when their send>0 (fixes MULTI first, it's
already decoded); (c) find the real CHORUS enable (no ch 0x19 write from SEG11 0x04). The reverb (global,
decoded) is unaffected and stays correct. Debug `[FXSEND]` logerror was TEMPORARY (removed after this run).