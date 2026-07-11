# TG envelope (ADSR) implementation — plan + findings (2026-07-11)

Felipe: the placeholder TG uses a HARDCODED envelope (fast attack, ~1.8s held-decay, ~100ms
release; kn7000_tonegen_device sound_stream_update). The firmware programs the REAL per-voice
envelope on each note, but tg_write only parses pitch (0x2400/1), mute (0x0001=0xC000), and level
(0x2009) -- the envelope registers are dropped. Task: capture the firmware's envelope parameters
and render a per-voice envelope from them, so a piano decays, an organ sustains, etc. Verified:
the claim is TRUE (envelope is hardcoded).

## What we already know (notes/tg-voice-register-semantics.md capture)
Per-voice register address = `group[15:10] | voice[9:4] | index[3:0]` (voice stride 0x10). The
note-on block (captured for C4, default Concert Grand) includes a **group-0 envelope/level block**:
  0000=D27F  0001/0002 (key-scaled)  **0004..000A = AE00 AE00 AE00 2C00 9900 35E8 25B0** (envelope)
  000B=0000  000C=7F00  000D=0F10  ... 2009=5FFF (level)
So the envelope lives in group-0 registers ~0x0004..0x000A (and maybe 0x0000..0x000D), key-scaled.
Values are rate/level fields, NOT yet decoded to times.

## Plan
A. [DONE] Verify envelope is hardcoded.
B. Capture the full group-0 block live for the DEFAULT sound; confirm registers 0x00-0x0D.
C. Capture the same block for CONTRASTING sounds (piano vs organ vs strings) -> confirm the
   envelope registers VARY per sound (a decaying vs a sustaining envelope look different).
D. Find the SOUND EDIT / TONE EDIT screen(s) where ATTACK/DECAY/SUSTAIN/RELEASE are edited; change
   one parameter at a time and capture which TG register moves -> map register -> ADSR stage.
E. Decode the rate/level encoding (register value -> time constant / level). Two routes:
   (1) disassemble the firmware routine that converts the user's ADSR setting into the register
       (search the SOUND EDIT handler), and/or
   (2) empirically sweep one parameter min..max on the screen, capture the register values, fit.
F. Implement a multi-segment (or ADSR) envelope generator in kn7000_tonegen_device keyed off the
   captured registers, replacing the hardcoded atk/dhld/drel. Keep pitch/level behaviour intact.
G. Verify: piano note decays, organ note sustains until release, editing attack on-screen audibly
   changes the attack. (Character judged by envelope shape since timbre is still a placeholder.)

## Findings
### The envelope is a 7-stage amplitude EG (register r4..rA, group 0, per voice)
- Live capture (default Concert Grand, C4 note-on, main TG voices 0+1 identical = the dual layer):
  `r4=AE00 r5=AE00 r6=AE00 r7=2C00 r8=9900 r9=35E8 rA=25B0`. (r4-r8 are 0xXX00 = 8-bit in the high
  byte; r9/rA are full 16-bit.)
- The GUI AMPLITUDE EDIT -> ENVELOPE screen (manual p172-173) has exactly 7 params:
  **ATK, PEAK, DCY1, SUS1, DCY2, SUS2, RLS** -- a two-stage decay/sustain amplitude envelope.
  So r4..rA are the TG's form of that 7-param EG (rates: ATK/DCY1/DCY2/RLS; levels: PEAK/SUS1/SUS2).
- CAPTURE MECHANICS (for reuse): the TG addr+data both go to program addr 0x98040000 as one 4-byte
  unit distinguished by MASK -- addr write has mem_mask 0x0000FFFF (value in bits[15:0]), data write
  has mem_mask 0xFFFF0000 (value in bits[31:16]). Register addr = group[15:10]|voice[9:4]|index[3:0];
  group-0 envelope regs are index 0x4..0xA. Sub TG = 0x98050000.
- Note-OFF / voice-clear zeroes r4..rA and writes 0x0001/0x0002 = 0xC000.

### DECODED via piano-vs-organ contrast (2026-07-11) + IMPLEMENTED
Register-write mechanism (disassembled, library 0x4C03741A): the note-on copies r4..rA DIRECTLY from
the voice's tone-data structure at a2 (reg0x04=*(a2+0xC), 0x05=+0x10, 0x06=+0x14, 0x07=+0x16,
0x08=+0x18, 0x09=+0x1C, ...). So r4..rA ARE the raw EG params; only the chip's rate/level scale is
unknown. Live contrast, same C4 note:
```
        r4    r5    r6    r7    r8    r9    rA
PIANO   AE00  AE00  AE00  2C00  9900  35E8  25B0     (Concert Grand -- DECAYS)
ORGAN   AE00  AE00  AE00  7F00  AE00  AE00  AE00     (JazzOrganSoloist -- SUSTAINS)
STRINGS AE00  AE00  AE00  7F00  AE00  AE00  AE00     (also a sustaining sound)
```
=> r4/r5/r6 are CONSTANT across sounds (fast attack / peak / decay1). The sound-specific fields are
r7..rA, and **r7 = SUS1 (the sustain LEVEL): 0x2C (~35%) for the decaying piano, 0x7F (max) for the
sustaining organ/strings.** r8=DCY2 rate, r9=SUS2, rA=RLS (rise together for sustaining sounds).
Mapping to the AMPLITUDE-EDIT 7-param EG: r4=ATK r5=PEAK r6=DCY1 r7=SUS1 r8=DCY2 r9=SUS2 rA=RLS.

### IMPLEMENTED (kn7000_tonegen_device): a firmware-driven amplitude envelope
tg_write caches r4..rA (group-0 regs 0x04-0x0A) per voice; the note-on resolves them into: attack
(~6 ms) -> exponential decay toward SUS1 (r7, normalised /127) -> hold at that sustain while gated ->
exponential release on mute. The decay time is scaled from DCY2 (r8) and calibrated so the Concert
Grand keeps its ~1.8 s decay. VERIFIED by tapping the TG output (DSP input 0xC378) directly (the
reverb tail masks it in the final mix): PIANO held decays 1.09M -> 837k -> 671k; ORGAN held ramps up
and HOLDS 522k -> 1.10M -> 1.11M. So pianos decay and organs/strings sustain, per the sound.
### REFINEMENT (2026-07-11): rA = release rate (a 3rd sound confirms it)
Adding a SOUND PAD capture (SEG0D 0x20) to the piano/organ set:
```
        r4  r5  r6  r7    r8  r9    rA
PIANO   AE  AE  AE  2C00  99  35E8  25B0   decays, medium release
ORGAN   AE  AE  AE  7F00  AE  AE00  AE00   sustains, FAST release (organ stops on key-up)
PAD     AE  AE  AE  7F00  AC  0400  0400   sustains, SLOW release (long fade on key-up)
```
=> r4/r5/r6 are CONSTANT for every sound tried (piano/organ/strings/pad) -- NOT the per-sound attack;
they are a fixed attack/peak/decay1 preset (so attack stays a fixed ~6 ms in code). **rA = RELEASE
rate: HIGHER = faster** (organ 0xAE -> fast; pad 0x04 -> slow ~1.5 s fade; piano 0x25 -> ~0.15 s).
Confirmed the firmware DOES write the TG voice mute (reg 0x01/0x02 = 0xC000) on key release, so the
release phase triggers. IMPLEMENTED: release coefficient from rA, `rlsT = 0.15 * 2^((0x25 - (rA>>8))/10)`
clamped [0.02, 5] s -- calibrated to piano=0x25 -> 0.15 s. So organs stop, pads fade slowly, per sound.
MEASUREMENT LIMIT: the dry TG envelope can only be read on the DSP-input tap during a held note; the
final WAV is dominated by the reverb tail (rings ~steady) so it can't show the release fade, and the
DSP-input address moves with the effect's I4 so post-mute buckets are sparse. The held decay + sustain
(piano decays, organ/strings/pad sustain) is cleanly verified; the release rate itself is evidence-
based (per-sound rA) + code-correct rather than re-measured through the reverb.
STILL PROVISIONAL (labelled): exact chip rate CURVE (register->time), and SUS2/DCY2 (r9/r8) as a true
2-stage decay (only r8 feeds the single decay time today). Amp-edit sweep blocked on menu soft-key
routing; chip datasheet unknown.
