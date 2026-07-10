# TG pitch pipeline — CORRECT demo/style pitch (SOLVED, 2026-07-10)

Felipe's ask: properly compute the correct pitches of the DEMO note events, then fix.
**STATUS: FIXED (commit de4fc88).** Musical pitch is resolved from the library's
per-slot VOICE RECORD at 0x500AF940 + slot*0xB4 (128 slots; 0x00-0x3F = 0x98050000,
0x40-0x7F = 0x98040000): field **+0x0C notePitch16 = (note<<8)+0x80+partTranspose+
masterTune+scaleStretch** = the intended musical pitch in 1/256-semitone units,
populated race-free BEFORE the note's first TG pitch write. Other key fields: +0x08
byte = active(bit7)|internal note(0-6); +0x07 part; +0x10 velocity; +0x0A base
pitch16; +0x3C/40/44 element descriptor ptrs. Unpitched exp-7 drums leave
notePitch16 at the constant 0x4280 -> legacy fallback. Held-voice pitch rewrites =
RELATIVE bends (dPitch18/0x400 semitones). Class 0x2400 writes (pitch18 bit16=0,
previously DROPPED note-ons) now handled. KEYBED FIFO is a KEY INDEX (internal note
= index+36; low key = C2 = MIDI 36) -> KN_KEY codes shifted -36 (C4 = 0x18).
Validated: keybed C4/C5 exact; demo bass line == sequence blob verbatim;
**CHORD FINDER FIXED as a side effect (C-Maj ear -> G3+C4+E4 exact)** — its notes
were always right, and the record resolve bypasses the NULL-descriptor pitch math.
RE chain adversarially verified (voice-record + note-sources agents CONFIRMED).

## The core discovery: 0x2401 is NOT absolute pitch

The tonegen currently decodes register class 0x2401 as absolute log-pitch
(note = 60 + (data-0xC838)/1024, verified for the keybed's Concert Grand). That is
only correct for that patch: the value is really **sample-zone-relative log pitch**.
Each tone's element descriptor (center key, key-scale exponent, coarse/fine tune)
offsets the value; different demo parts sit at different constant offsets from the
keybed map (e.g. the Overture's G3-riff part plays MIDI 55 as pitch 0x19510 =
7.8 semitones BELOW the keybed map's value for note 55 — same 0x400/semitone slope,
different anchor). Our sine synthesis therefore plays every non-piano part at the
wrong absolute pitch (melodies transposed by arbitrary per-part offsets).

Encoding detail (verified): the "class" low bit is pitch bit16 —
pitch18 = ((class&1)<<16) | data16, register class is 0x2400. The transform from the
lib's internal pitch16: pitch18 = ((pitch16 + 0x1800) << 2) & 0x3FFFF.
**The demo writes 68 class-0x2400 (bit16=0) note-ons (e.g. 0x0DF10 percussion) that
the tonegen currently DROPS entirely (its switch only handles 0x2401).** Fix required
regardless of the rest.

## Empirical anchors (this session, all reproduced)

- Overture ground truth: sequence blob (zlib @ prog 0x4879811C for song 0) opens with
  F3(53) then a repeated G3(55) riff, A#3(58), B3(59) on ch0. Captured: the riff =
  pitch18 0x19510 repeating at the riff rhythm; A#3 = 0x1A110 (= +3*0x400) — slope
  confirmed, offset per part.
- **Voice-record array: base 0x500CA0B0, stride 0x84** (lib-side voice records).
  RAM-scan proof: records holding pitch18 0x00019510 at **rec+0x48** sit at indices
  7/13/25/35/45 (exact multiples). Keybed C4 lands in records 0,1 (dual layer) with
  +0x48 = 0x0001C838.
- Record index == lib slot == our driver voice v-64 for the 0x98050000 TG (lib
  primitive 0x4C036F98: slot<0x40 -> 0x98050002, else 0x98040002; C4 wrote v=64,65 =
  records 0,1 ✓). A second bank for slots 0x40+ presumably at 0x500CC1B0 (unverified).
- Records populate EVEN WITH THE TG GATE CLOSED (no CONFIG bits; C4 record complete
  at 96% speed, silent) — lib voice machinery always runs, so RAM-snooping is robust.
- C4 record contents (idx 0): +0x04=0xFF005400 (byte+5=0x54=84=60+24 — note-like,
  but rec7's byte+5=0x62 doesn't fit a naive note+24 reading for its G3; field
  semantics need the static RE), +0x40 layer word, +0x44=0x00095FFF (level cache),
  +0x48=pitch18, +0x54=the class-0x3000 value (0x0BE8/0x0B52 per layer).
- Part tone blocks (0x500CE404 + part*0x130) during the demo are POPULATED with
  table-ROM descriptor pointers (word0 = 0x480A24F6 etc.; keyboard default
  0x48127508) — the demo's program changes WORK; descriptors are in the DUMPED
  table ROM. (Unlike the chord finder's NULL part-0x21 block.)

## Fix strategy (pending the static results)

Preferred: at note-on (first pitch write for a voice), the driver reads the lib voice
record for that slot -> true MIDI note (+ the record's cached pitch18 as reference);
tonegen plays the true note; subsequent pitch rewrites on the same voice are applied
as RELATIVE semitone deltas (Δpitch18/0x400) from the note-on reference — preserving
pitch bend / vibrato / portamento semantics. Alternative (more faithful, no RAM
snoop): invert the lib pitch formula using the element-descriptor fields (center,
exp, tunes) read from the dumped table ROM via the part tone block — the static RE
is establishing the exact formula + field offsets + a validated inverse.

Static RE in flight (3 finders + adversarial verify): (1) voice-record layout (note/
part/slot field offsets, write order vs first TG write, steal lifecycle); (2) exact
pitch formula + inverse validated on the anchors; (3) note path event-ring -> record
(transposes) + the demo setup blob's track->part->program map + whether per-tone
octave offsets are musically intended (bass sounds an octave down NORMALLY).
