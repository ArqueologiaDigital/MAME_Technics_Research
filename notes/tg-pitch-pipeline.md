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

---

## Appendix: the FULL pitch/tone architecture (formula finder, adversarially CONFIRMED)

All three pitch-workflow investigations were independently re-derived and CONFIRMED
(wf_a8b4db86-02c). The shipped fix reads the firmware's own result (notePitch16), so
it does not depend on this formula — but this is the reference for (a) a future
descriptor-based implementation, (b) REAL-SAMPLE synthesis once the wave ROMs are
dumped (the tables below map each voice to its wave sample number + per-sample pitch
correction), and (c) tuning features (master tune, scale tuning, portamento).

### Forward formula (init 0x4C030FB9; runtime adds modulation via 0x4C031127)
- note16 = (rec[8]&0x7F)<<8 + 0x80 + partBase   [stored at rec+0x0C = what the fix reads]
- partBase (0x500AD5A8+part*0x10C, writer 0x4C02BF40) = partTranspose(sbyte
  part_rec+0x1A)<<8 + masterTune(h 0x500C075E) [+ per-pitch-class table
  part_rec+0x4A[(note%12)*2] when part flag bit14] [+ per-note scale-stretch via
  0x48449CB2 when part flag bit15 && zone+0xF != 0xFF]
- melodic: pitch16 = ((note16 - (zone[0xB]<<8 + 0x80)) asr exp) + 0x4280, where
  exp = (descriptorHW0>>11)&7 (key-follow divisor; 7 = fixed pitch from zone+0xC)
  + coarse(desc+7)<<8 + 2*fine(desc+8) + tone-edit coarse/fine (toneblock
  +elem*0x34+0x8E/0x8F) + multisample corr (subrec+6, modal 2756) + part offset
  (part_rec+0x18) + mod matrix (part_rec+0x64) + LFO + portamento; clamp 0..0x7FFF
- bus value: pitch18 = ((pitch16+0x1800)<<2)&0x3FFFF, register class
  0x2400|(pitch18>>16), data16 = pitch18&0xFFFF. 1 semitone = 0x400 in pitch18 /
  0x100 in pitch16; neutral 0x4280 (pitch18 0x1E200) = zone center at native rate.

### The tone/zone/sample data (all in the DUMPED table ROM, bank 0)
- bank pointers (RAM): 0x5003A554[5] data base (bank0 = 0x4806EA98),
  0x5003A5A4[5] header (bank0 = 0x48120CD8); banks 1-4 = the 0x56/0x57 flashes.
- zone records: 16 bytes @ 0x48131DF0, 864 entries: +9/+0xA low/high key,
  +0xB centerKey (66 internal in 851/864 zones), +0xC fixed pitch16 for exp==7,
  +0xF scale-tune idx; +0 -> tableA (multisample remap), +4 -> subrec table.
- multisample: tableB = per-semitone byte map (128 entries indexed by
  basePitch>>8) -> remap -> subrec {+2 SAMPLE NUMBER, +6 sh16 per-sample pitch
  correction} — the future wave-ROM playback path.
- wave-key hash (bank0): 891 buckets, entry {next, key, zoneIdx|bit15-invalid};
  keys from descriptor bytes +4/+5/+6 (b1 gets a per-part wave offset 0x4C0109E5).
- part pitch struct +0x46 h = current/target note16 -> TG class 0x2000
  (&0x1FFF|0x4000, |0x8000 when multisample) — the "within-octave companion"
  register from the old notes, now explained (portamento/multisample tracking).

### Nuance: the internal note scale (flagged, not load-bearing)
The formula finder's offsets line says "internal note = MIDI+24 on keybed"; the
shipped fix treats internal == MIDI (keybed FIFO = key index, internal = index+36).
The bed-range argument favors the latter: 61 keys -> internal 36..96 = C2..C7 =
exactly the real KN7000's compass; the demo blob's notes (internal scale) then read
as standard MIDI and the music lands in sensible registers; the chord finder's
C-Maj sounds around middle C matching its screen. If an absolute-pitch reference
for real hardware ever disagrees (e.g. a recording of the real Overture), revisit
the global anchor by a constant offset — a one-line change in tg_pitch_resolve().

Verifier corrections recorded: scale-tune byte range is wider than first claimed
(PIANO stretch spans about -88..+86); demo setup-blob full per-part records start
at +0x154 (not +0x140) and are interleaved with compact records; several cited
addresses are movm-prologue addresses (call targets are entry+prologue) — none
load-bearing.
