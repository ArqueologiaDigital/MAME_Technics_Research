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

### Still to decode (next steps)
- Which register = which stage (order), and the RATE encoding (register value -> time constant) and
  LEVEL encoding. Routes: (1) capture r4..rA for a CONTRASTING sound (sustained organ vs decaying
  piano) -- rate regs will differ predictably; (2) disassemble the note-on envelope-programming code
  / the AMPLITUDE-EDIT param->register conversion; (3) sweep ATTACK/DECAY/RELEASE TIME on a reachable
  screen (EASY EDIT p165 / PART SETTING p116 pg4 / EDIT MIXER) and watch which reg moves + how.
