# KN5000 IC303 HLE audit — dimension: VOICE LIFECYCLE

Author: autonomous audit pass, 2026-07-26. Requested by Felipe Sanches.
Scope: note-on gate detection, note-off signalling, the 0x100000 status poll, hold/release
counters, voice allocation & stealing, the synthesised unison partial, multi-partial patches.

Evidence labels: **MEASURED** (read from the disassembly bytes, the ROM, or a live capture),
**INFERRED** (deduction from measured facts), **SPECULATIVE** (unproven).

Sources
* sub-CPU disasm `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`
  (`LABEL_02XXXX` = runtime address; the code runs decompressed in sub RAM).
* HLE `kn7000_mame/src/mame/matsushita/kn5000_tonegen.{cpp,h}`, driver `kn5000.cpp`.
* **NEW live captures made for this audit** (isolated nvram copy, never `kn7000-emulator/nvram`):
  * `voicelife_probe.lua`  → `voicelife_trace.txt` — every SubCPU access to 0x100000/0x100002
    around one held C4 (press 12.002 s, release 14.007 s). 662 events, all reads at 0x100000.
  * `voicelife_probe2.lua` → `voicelife_alloc.txt` — gate (+0x000) and wave-select (+0x040)
    writes plus status reads, from power-on through 5 single notes and a 3-note chord.
  * `voicelife_probe3.lua` → `voicelife.wav` — the same single note rendered to audio, for the
    amplitude measurements in gap 1.
  (scratchpad `/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/c6cf97f4-…/scratchpad/`)

---

## 1. What the FIRMWARE does (MEASURED, cited)

### 1.1 The six register writers — the complete inventory

Every IC303 register write in the sub-CPU goes through one of these (asm L29565-L30330):

| routine | asm line | registers written, **in order** | struct offsets |
|---|---|---|---|
| `ToneGen_WriteVoiceParams` | L29565 | +040, **+080 \|bit15**, +0C0, +100, +140, +180, +400, +440, +480, +4C0, +500, +800, **+000 = 0x8100**, +840, +880, +8C0, +900, +940, +980, +9C0, +A00, +A40, **+080 &~bit15** | +02…+2a, +04 twice |
| `ToneGen_WriteSingleReg` | L29919 | one register (address = WA) | — |
| `LABEL_02D436` | L29936 | **+840, +940, +A00, +800, +900, +9C0** (6 writes, no gate, no +080) | +2e,+32,+36,+2c,+30,+34 |
| `LABEL_02D50E` | L30035 | +840, +800 | +2e, +2c |
| `LABEL_02D5D0` | L30091 | +840, +880 | +1a, +1c |
| `LABEL_02D620` | L30130 | +840, +880 | +2e, +2e |
| `LABEL_02D68F` / `LABEL_02D73F` | L30188 / L30288 | +800, **+000 = 0x8100**, +840, +080 &~bit15, **+000 = struct[+2d]** | +3c, +3e, +2d |
| `LABEL_02D670` | L30169 | +180 only | BC |
| `LABEL_02D0BA` | L29539 | +400 only (pitch bend) | +0e |

Two facts fall straight out and are the backbone of everything below:
* the note-on burst is **bracketed** by +0x080 with bit15 SET (`SET 0fh,WA`, L29594) and bit15
  CLEAR (`RES 0fh,WA`, L29907);
* `LABEL_02D436` — the EG-stage / release burst — writes **+0x840 immediately followed by
  +0x940**, a two-write adjacency that no other writer produces (the note-on burst puts +0x880,
  +0x8C0 and +0x900 between them).

### 1.2 The group-0/bank-0 "gate" register is `{command[15:9], flag[8], magnitude[7:0]}`

`LABEL_025589` (L18856-18906) builds the word the firmware later writes to +0x000:

```
p    = partial_block[0]                  ; voice_struct[+0x17][0]
mag  = 0x00FF - ((p & 0x3F) << 2)        ; bits 7:0
if p != 0:  SET bit8                     ; L18869  "SET 8, BC"
word = mag | 0xFE00  or  mag | 0xF000    ; L18885/18891/18897  (mode 0x04134C)
word = LABEL_02552A(part, word)          ; L18813-18855: ORs 0x0E00 / sets bit9 /
                                         ; ORs 0x7000 / sets bit12 from part flags 0x04138D
struct[+0x2d] = word
```
So bits 15:9 are a 7-bit **command/routing** code, bit 8 is a **flag**, bits 7:0 are the
**amplitude magnitude**. Observed commands: 0x40 = `0x8100` (note-on strobe, bit8 set, mag 0),
0x78 = `0xF0xx`, 0x7F = `0xFExx`, 0x3F = `0x7E00` (voice free), 0x09 = `0x1200` (boot self-test).

### 1.3 Note-ON — MEASURED live, exactly as the disassembly predicts

`voicelife_trace.txt`, one C4 press (the patch has **two partials** → two channels):

```
12.005590  +0840 ch00 = FF00      <-- pre-silence of the channel about to be reused
12.005593  +0800 ch00 = FF80
12.005976  +0040 ch00 = 7007      <-- ToneGen_WriteVoiceParams begins
12.005979  +0080 ch00 = 8E52      <-- ARM (bit15 set)
   … +0C0=7400 +100=2466 +140=6FDA +180=0000 +400=34C1 +440=0000 +480=0000
     +4C0=4400 +500=2C72 +800=E57F …
12.006012  +0000 ch00 = 8100      <-- the gate, in the MIDDLE of the burst
   … +840=484C +880=4000 +8C0=00B0 +900=AE00 +940=AE00 +980=AE00 +9C0=FF00
     +A00=40E8 +A40=30B0 …
12.006043  +0080 ch00 = 0E52      <-- DISARM (bit15 clear), burst ends
12.006049 … 12.006571             <-- the whole thing again for ch01 (+040 = 7017)
12.006603  +0000 ch00 = F0FF      <-- struct[+0x2d]: command 0x78, magnitude 0xFF
12.006615  +0000 ch01 = F0FF
```

### 1.4 Note-OFF — there is **no 0x7E00 at key-up**; the release is `LABEL_02D436`

```
14.007354  # key released
14.013433  +0840 ch00 = 8B00      <-- LABEL_02D436, its exact 6 writes in its exact order
14.013436  +0940 ch00 = AE00
14.013440  +0A00 ch00 = 4FB0
14.013443  +0800 ch00 = 8B80
14.013454  +0900 ch00 = AE00
14.013457  +09C0 ch00 = 4FB0
14.013542 … 14.013558             <-- the same 6 for ch01
```
Reached through `LABEL_02CD71` (L29178) → `LABEL_02D436` (call at L29227) when the voice's
pending-event word `struct[+0x2f]` fires; the service loop that fires it is `LABEL_027A46`
(L22618) / `LABEL_027AC4` (L22673), which chooses between the **immediate** path (free the voice
now: `LABEL_022587` + `LABEL_02CD71`, L22703-22711) and the **delayed** path (`LABEL_026E5B`,
L21467, a per-tick countdown in `struct[+0x2f]`) according to `part_struct[+0x0a] bit15`.

### 1.5 Teardown is driven **by the chip's own status readback** — this is the whole game

`LABEL_02219F` (L13273), the voice manager, runs one bank of 16 per audio tick:

```
b   = ++(0x1128) & 3
HL  = DAC_Write_Sample(b)            ; L13280 — write b to 0x100000, READ 0x100000 back
DE  = cmd_bitmap[0x2936 + 2b] | HL   ; L13284-13288
tmp = (DE ^ prev[0x292E + 2b]) & prev; L13291-13302   "was set, is now clear"
prev[0x292E + 2b] = DE               ; L13304-13308
for i in 0..15:  ch = 16b + i
    if tmp bit i and !(node[+0x22] bit0):
        LABEL_021E31(node)           ; L13324  retire the node
        LABEL_02B4A1(ch)             ; L13327  -> +0x0C0+ch = 0x0000 (L26780)
                                     ;         -> +0x000+ch = 0x7E00 (L26793)
        LABEL_02150D(ch)             ; L13330
    else if !(node[+0x22] & 0x81):
        node[+0x25] = (READ(0x0180+ch) & 0x3FFF) >> 5   ; L13337-13344
        if node[+0x25] < 0x80 and node[+0x22] bit2: LABEL_021E83(node)  ; L13345-13350
```
`DAC_Write_Sample` (L11479) is misnamed: it is `write 0x100000 = WA; read HL = 0x100000`.

**MEASURED causality in the capture** (`voicelife_alloc.txt`):
```
12.419099  # key released
12.481481  R latch=0000 -> 0000     <-- our status_r finally returns 0 for bank 0
12.481537  W 0000 7E00              <-- 56 us later: teardown of ch0
12.481599  W 0001 7E00              <-- and ch1
```
The 0x7E00 teardown is emitted **immediately after, and only after, the status read returns 0**.
So *the HLE's `status_r()` return value is the sole thing that decides when the firmware
reclaims a voice.* On real hardware the chip drops that bit when its own envelope reaches zero —
i.e. at the end of the release tail, not at key-up.

Voices whose node flags are 0x88 (`LABEL_022340` L13534) additionally have their bit set in the
firmware's own `cmd_bitmap` at 0x2936, so `cmd | chip` keeps them alive regardless; ordinary
voices get flags 0x08 and **no** cmd bit (L13551-13580), so their whole lifetime after the gate
is dictated by the chip's bitmap.

### 1.6 Per-voice ENVELOPE-LEVEL readback at latch 0x0180+ch — MEASURED, and unimplemented

The `else` branch above reads register address **0x0180 + ch** through the same
`0x100000` port and keeps bits 12:5 as an 8-bit level in `node[+0x25]`; `< 0x80` means "this
voice has decayed" and moves the node down the stealing priority list (`LABEL_021E83` L12946,
`LABEL_021EA1` L12960, called from the free routine `LABEL_022587` L13694). The allocator seeds
`node[+0x25] = 0xFF` at allocation (L13523).

MEASURED in the capture: the firmware issued 20 such reads per voice during the 2-second held
note, at latches 0x0180/0x0181 (single note) and 0x018A…0x018F (the chord).

### 1.7 Voice allocation / stealing lives entirely in the FIRMWARE

`LABEL_022340` (L13451) walks per-part pool descriptors and doubly-linked priority lists of
64 nodes at `0x148D + ch*0x27` (`LABEL_021C83`/`021D59`/`021E02`/`021E15`, L12850-12915); the
channel number *is* the node index. `Voice_Allocate` (L29099) and friends are query builders
(`0x2A5E` = {mode, key, mask} → a list of matching channels), not allocators.

MEASURED allocation order over 5 single notes + a chord: C4→ch0,1  D4→ch2,3  E4→ch4,5
F4→ch6,7  G4→ch8,9  chord→ch10…15 — a monotone march with a FIFO free list. Nothing about
that is a defect; the earlier "marches up 64 channels without freeing" observation is just the
free list being FIFO.

### 1.8 The synthesised UNISON partial is produced **inside the firmware**, before the registers

`LABEL_032B1E` (L35233) builds the per-part partial-enable mask into `part_struct[+0x02]`
(0x04136A + part*0x11F):

```
DE = part_struct[+0x02] & 0xFFFF3FF0
if hdr[+0x11] bit0:  DE |= 0x0001                      ; partial 1 really exists
elif part_struct[+0x0a] bit15 and hdr[+0x11] bit2 and (hdr[+0x5d]&0x0F) <= 8:
     DE |= 0x4001                                      ; SYNTHESISE partial 1  (L35285)
if hdr[+0x11] bit2:  DE |= 0x0002                      ; partial 2 really exists
elif part_struct[+0x0a] bit15 and hdr[+0x11] bit0 and (hdr[+0x5d]&0x0F) <= 8:
     DE |= 0x8002                                      ; SYNTHESISE partial 2  (LABEL_032C0F L35317, L35344)
if hdr[+0x11] bit4:  DE |= 0x0004      ; partial 3
if hdr[+0x11] bit6:  DE |= 0x0008      ; partial 4
```
and `LABEL_032D58` (L35445; the swaps at L35457/L35482) makes the synthesised partial **read the OTHER partial's tone
record** (zone-slot pointer 0x0413D6 ↔ 0x0413FB swapped when bit14/bit15 is set). The enabled
mask is then consumed per partial by `LABEL_02BD87` (L27622), which builds an ordinary note-on.

`part_struct[+0x0a]` bit15 is set by `LABEL_033557` (L36280) — unconditionally when
`hdr[+0x5d] & 0x0F == 7`, otherwise only when bit14 of the same word is set by the per-part
parameter setter `LABEL_0289AE` (L23558). Bit0 of the same word is the **sustain pedal**
(`Voice_CC_Sustain` L25111 → `LABEL_028962` L23528), so this word is the per-part mode/pedal
register. *The exact identity of bit14 is NOT PINNED* (its setter is reached through a computed
dispatch I did not resolve) — I am not going to guess it.

**Consequence for the HLE: there is nothing to synthesise.** The extra partial arrives at the
chip as an ordinary, separately-gated voice on its own channel with its own +0x040 and +0x400.

---

## 2. What the HLE does (file:line)

* `data_w` `kn5000_tonegen.cpp:205-226` — group0/bank0: `0x7E00` → `process_key_off`;
  `(data & 0xFF00) == 0x8100` → `process_key_on`; else `data & 0x8000` →
  `env_level = min(data & 0x1FF, 0xFF)`.
* `data_w:246-251` — **the release heuristic**: any write to group 9 / bank 0 (+0x900) on a
  keyed-on voice more than **1 ms** after the note-on gate → `process_key_off`.
* `data_w:255-256` — group0/bank2 with bit15 set → `resolve_waveform` (the note-on burst's ARM
  write; the DISARM write is not acted on).
* `status_r:290-316` — ignores everything in the latch except **bits 1:0**, returns
  `bit i = m_voice[bank*16+i].key_on`.
* `data_r:271-287` — returns 0x8100/0x7E00 from `key_on || hold_counter`.
* `process_key_on:1325-1357` — `key_on = active = true`, `wave_offset = 0`,
  `release_counter = hold_counter = 0`, `env_level = 0xFF`, resolve waveform/pitch/level.
* `process_key_off:1360-1376` — `key_on = false`, `release_counter = 2400` (50 ms),
  `hold_counter = 4800` (100 ms).
* `sound_stream_update:1410-1418, 1458-1461, 1524-1543` — the hold/release counters and the
  `active` teardown.

---

## 3. THE DELTA — numbered gaps

### GAP 1 — `process_key_off()` is called TWICE per note and **restarts the release fade**
**What is wrong.** The firmware's release burst and its later teardown are two separate events
(MEASURED 41 ms and 62 ms apart in the two captures). The HLE calls `process_key_off` on the
first (heuristic, cpp:250) and again on the second (`0x7E00`, cpp:210). `process_key_off`
unconditionally sets `release_counter = 2400` (cpp:1369), so the second call resets a fade that
was already ~80 % complete back to 1.0.
**Audible consequence.** A second onset after the note has faded. **MEASURED** in
`voicelife.wav`: RMS 1.6 at t=14.045 → **5.0 at t=14.055** (+10 dB), exactly at the 0x7E00
timestamp 14.054487 from the register trace. Predict-then-check: predicted from the code before
rendering, confirmed by the audio. On this patch the absolute level is tiny (the level register
had already collapsed, see gap 6) so it is not loud — on any patch whose release level stays up
it is a click on every key release.
**Firmware-derived fix.** Make `process_key_off` idempotent: never *restart* a release. Model the
two events as what they are — the EG-stage burst starts the release ramp, the `0x7E00` is the
chip-teardown command that ends the voice (`active = false`, wave pointer cleared), not another
release.
**Confidence: MEASURED.**

### GAP 2 — `status_r()` reports `key_on`, but the chip reports **"still sounding"**
**What is wrong.** cpp:307-315 sets bit i from `m_voice[…].key_on` only. The firmware's teardown
edge detector (§1.5) fires the instant that bit drops, and the capture proves the causality
(`R 0000 0000` at 12.481481 → `W 0000 7E00` at 12.481537). On hardware the bit stays set until
the chip's own envelope reaches zero, i.e. through the whole release tail.
**Audible consequence.** (a) The teardown arrives during our release fade and triggers gap 1.
(b) The channel is returned to the firmware's free pool ~40-60 ms after key-up instead of after
the tail, so under polyphony pressure a channel can be re-gated while the HLE is still rendering
its release — `process_key_on` zeroes `wave_offset` (cpp:1334) and the tail is cut mid-decay.
**Firmware-derived fix.** Return "this voice is still producing sound":
`v.active && (v.key_on || v.release_counter > 0 || v.env_level > 0 …)` — i.e. exactly the
condition under which the HLE still writes nonzero samples for that voice. That is the chip's own
`active` flag, it needs no new information, and it makes the firmware's reclaim timing correct by
construction. `hold_counter` then becomes unnecessary (gap 4).
**Confidence: MEASURED** (mechanism + causal timing); the polyphony-cut consequence is INFERRED
(the capture never exhausted the pool).

### GAP 3 — the per-voice EG-level readback at latch **0x0180+ch** returns a bank bitmap
**What is wrong.** `status_r` masks the latch to 2 bits (cpp:307), so a read at 0x0180+ch is
answered with the key-on bitmap of bank `ch & 3`. MEASURED: latch 0x0180 → 0x0003, latch 0x0181 →
0x0000, latch 0x018C → 0xFC00. The firmware turns that into `node[+0x25] = (v & 0x3FFF) >> 5`
(L13341-13344), so it read level 0 ("decayed") for most voices and level 0xE0 ("loud") for the
one whose channel index happened to alias a bank containing sounding voices.
**Audible consequence.** The firmware's voice-stealing priority is fed noise: still-ringing
voices are demoted into the "finished" list (`LABEL_021E83`) and become the preferred steal
victims, while an unrelated voice looks loud and is protected. Symptom: notes cut off in dense
passages / arbitrary voices surviving instead of the newest ones.
**Firmware-derived fix.** Decode the latch properly in `status_r`: `group = latch >> 8`,
`bank = (latch >> 6) & 3`, `ch = latch & 0x3F`. For `latch < 4` return the 16-voice active
bitmap (as now, but from the gap-2 condition); for `group == 1 && bank == 2` return
`(level8 << 5)` where `level8` is that voice's current envelope magnitude scaled 0..0xFF
(0 when idle). The firmware only ever compares it against 0x80, so the scale needs to be
monotone, not exact.
**Confidence: MEASURED** (the wrong values were captured); the stealing consequence is INFERRED.

### GAP 4 — `hold_counter` does not do what its comment says
**What is wrong.** cpp:1372-1375 says the 100 ms hold "ensures at least a few poll cycles see the
voice as active", but `status_r` never consults `hold_counter` — only `key_on`. The only reader is
`data_r` (cpp:283), and **MEASURED: the firmware never reads 0x100002** (263 reads in the
capture, 100 % at 0x100000). So `hold_counter` is a pure internal lifetime timer with a
misleading rationale, and `data_r` is dead code.
**Audible consequence.** None directly; it is a correctness/maintenance hazard that hides gap 2.
**Fix.** Fold the "still sounding" condition into `status_r` (gap 2) and delete the hold hack, or
re-document it as a pure deactivation delay.
**Confidence: MEASURED.**

### GAP 5 — the release detector is a 1 ms timing heuristic; a **deterministic** signature exists
**What is wrong.** cpp:246-251 fires on any +0x900 write >1 ms after the gate. That is a timing
constant, and +0x900 is written by *both* `ToneGen_WriteVoiceParams` and `LABEL_02D436` — so any
mid-note EG-stage advance (which `LABEL_026E5B`'s countdown legitimately schedules while the key
is still down) is misread as a note-off.
**Audible consequence.** For the patch I captured there are **zero** register writes between
12.006615 and 14.013433 — 2 s of held note — so this patch never triggers the false positive.
A patch with a real multi-segment hardware EG would be force-released at its first segment
boundary (note dies early / loses its sustain segment).
**Firmware-derived fix, exact and timing-free.** `LABEL_02D436` is the **only** writer that emits
**+0x940 immediately after +0x840 on the same channel** (verified against all nine writers in
§1.1: the note-on burst interposes +0x880/+0x8C0/+0x900; `LABEL_02D50E` follows +0x840 with
+0x800; `02D5D0`/`02D620` with +0x880; `02D68F`/`02D73F` never write +0x940). So:
per channel, remember the previous per-voice register written; treat "+0x940 whose predecessor
was +0x840" as the EG-stage/release burst. No time constant, no data-value matching.
*(A `+0x080` arm/disarm bracket is tempting — cpp:255 already hooks the ARM — but it is NOT
sufficient on its own: `LABEL_02D68F`/`02D73F` write the DISARM without a matching ARM.)*
**Confidence: MEASURED** for the signature (all writers enumerated from the disassembly);
INFERRED for the false-positive consequence (not yet exhibited by a captured patch).

### GAP 6 — the release is applied as an instantaneous level, so notes end in a 3 ms CLIFF
**What is wrong.** `update_voice_params` (cpp:462-521) turns +0x800's high byte into a gain
immediately. The release burst writes +0x800 = 0x8B80 in one go, so the voice jumps from its
sustain gain to the release gain in one sample.
**Audible consequence. MEASURED** in `voicelife.wav`: RMS 2522 at t=14.010 → **4.7 at t=14.015**.
A −54 dB step in 3 ms; the note is fully gone 110 ms after key-up. There is effectively no
release tail on any sound.
**Firmware-derived fix (cross-dimension — belongs with the ENVELOPE audit, flagged here because
it is what the lifecycle model rests on).** The three "silence this voice" commands in the
firmware are, MEASURED:
```
channel pre-reuse (Voice_NoteOff L28663/28677) : +0x840 = FF00   +0x800 = FF80
all-notes-off / panic  (LABEL_021F08 L13013/13027): +0x840 = A200   +0x800 = A280
key release            (LABEL_02D436, captured)    : +0x840 = 8B00   +0x800 = 8B80
note-on                (captured)                  : +0x840 = 484C   +0x800 = E57F
```
Under the HLE's current reading (+0x800 high byte = level, higher = louder) the *pre-silence*
command 0xFF80 decodes as **maximum volume** — the HLE momentarily blasts the previous occupant
of a channel to full scale 380 µs before the new note-on (MEASURED at 12.005593). Under the
opposite reading (higher = attenuation) the panic value 0xA2 would not be silence either.
The only self-consistent reading of all four is **+0x800 = {rate[15:8], signed target[7:0]}**:
target `0x7F` = full at note-on, `0x80` (= −128) = silence for all three silencing commands, with
the high byte the **ramp rate** (0xFF = instant for the pre-reuse mute, 0xA2 for panic, 0x8B for a
musical release). Supporting evidence from the same capture: the two partials of one key press
carry **identical** +0x800 (0xE57F both) but **different** +0x080 (0x8E52 vs 0x8E64) — so the
per-voice loudness is in +0x080, not +0x800, which is what the model note already says
(§2 of `kn5000-voice-pipeline-MODEL.md`: "+0x080 = output level").
**Confidence: MEASURED** for the four register values and the audio cliff; **INFERRED** for the
{rate, signed target} decode. This one wants the velocity/envelope auditor's calibration data
before it is acted on — I am flagging it, not changing it.

### GAP 7 — the channel-reuse pre-silence pair is rendered as a full-volume blip
**What is wrong.** The 380 µs `+0x840 = 0xFF00 / +0x800 = 0xFF80` pair that precedes every note-on
(§1.3, from `Voice_NoteOff` L28663/L28677) is the firmware telling the chip *"kill whatever is on
this channel before I reprogram it"*. The HLE runs it through `update_voice_params`
(`data_w` cpp:266) and sets `volume_l = volume_r = 32767`.
**Audible consequence.** If the channel's previous occupant is still ringing (which it will be as
soon as gap 2 is fixed and release tails become real), it is slammed to full scale for 380 µs and
then cut — a click on every voice reuse. Today the effect is masked because gap 2 frees channels
so early that they are nearly always already silent.
**Firmware-derived fix.** Same decode as gap 6: `+0x800 = 0xFF80` must mean "ramp to silence at
maximum rate", i.e. an immediate mute of that channel.
**Confidence: MEASURED** (the register pair and the HLE code path); the click is INFERRED.

### GAP 8 — the gate register's magnitude field is decoded 1 bit too wide
**What is wrong.** cpp:224 does `env_level = min(data & 0x1FF, 0xFF)`. Per `LABEL_025589`
(L18856-18869) the magnitude is `0xFF - 4*(partial_block[0] & 0x3F)` in **bits 7:0**, and **bit 8
is an independent flag** set whenever `partial_block[0] != 0`. So whenever that flag is set the
HLE computes `data & 0x1FF >= 0x100` and clamps to **0xFF — full amplitude** — discarding the
firmware's commanded magnitude entirely.
**Audible consequence.** Every voice whose partial block byte 0 is nonzero renders its software
envelope at full level instead of the commanded one: wrong per-voice balance, no soft envelope
segments. The captured patch writes 0xF0FF (flag clear, magnitude 0xFF) so it is unaffected —
this is a latent systematic error, not a symptom of this capture.
**Firmware-derived fix.** `env_level = data & 0xFF`; treat bit 8 as a separate flag (its meaning
is not yet decoded — say so rather than folding it into the level).
**Confidence: MEASURED** from the disassembly; INFERRED that real patches set it (the firmware
sets it for any nonzero `partial_block[0]`, and the same byte's low 6 bits are what scales the
magnitude, so nonzero values must be common).

### GAP 9 — nothing needs to synthesise a unison partial, and the HLE must not
**What is wrong (in the framing, not the code).** `LABEL_032C0F`'s `DE |= 0x8002` runs entirely
on the sub-CPU side: it enables a second *partial*, which then goes through the ordinary note-on
path and reaches IC303 as a **separate channel with its own full register burst**. Adding a
unison oscillator inside the HLE would be a chip-boundary violation.
**So if Honky-Tonk does not beat, the loss is downstream, in the HLE's pitch resolution.** The
detune does reach the chip: `LABEL_023A05` (L15996) adds `partial_block[+0x05] * 2` to the pitch
word, i.e. ±6 → a 24-unit (9.4 cent) split in +0x400 between the two channels. In
`resolve_note_group` (cpp:584-713) a unison pair shares one chunk, so (a) the *learning* branch is
skipped by design (`distinct` is false, cpp:623-628) and (b) the pair is only separated if that
chunk's trim was already learned, or by the mean-centred fallback at cpp:703-709. Any voice that
fails `wave_real / regs[8] != 0 / pitch_period_q16 != 0` (cpp:598) is dropped from the group
entirely and keeps `pitch_offset = 0` — **two dropped voices render bit-identical**, which is the
reported symptom.
**Fix.** Do not add a unison feature. Instrument `resolve_note_group` for the Honky-Tonk case and
find which of the three exits it takes; if it is the `pitch_period_q16 == 0` (aperiodic chunk)
exit, both voices also fall to `pitch_step = 0x10000` in `update_pitch` (cpp:743-747) and no
detune of any kind can survive.
**Confidence: MEASURED** for the firmware mechanism; **INFERRED** for the HLE-side loss point —
I could not select Honky-Tonk from the automated harness, so this is a diagnosis to confirm, not
a confirmed cause. Reporting it as unproven rather than guessing.

### GAP 10 — `resolve_waveform` runs on the ARM strobe *and* again on the gate
Minor: cpp:255-256 resolves on the +0x080 ARM write (first-but-one of the burst, when +0x040 has
just been written) and `process_key_on` resolves again on the gate (cpp:1344). Both see the same
+0x040, so the result is identical — but the stale comment at cpp:1341-1343 justifies the second
call with "it has already written the wave number (regs[9]/regs[10])", and regs[9]/regs[10] are
+0x440/+0x480, the per-note-on **slot counters** (both 0x0000 in the capture), not wave numbers.
**Fix.** Delete the redundant resolve or the misleading comment. **Confidence: MEASURED.**

---

## 4. Audited and found CORRECT (explicitly)

1. **Note-on gate detection.** `(data & 0xFF00) == 0x8100` on group0/bank0 is right: the firmware
   writes the literal `0x8100` at L29757, L30213, L30294, L30667, L30891, L31071, L31086 and
   nowhere else, and the capture shows exactly one per voice per note-on. (Pedantically the
   command field is bits 15:9 so the exact test is `(data >> 9) == 0x40`, but no other value in
   that command ever occurs.)
2. **`0x7E00` = voice free.** Correctly identified: `LABEL_02B4A1` L26793, the global panic loop
   L13066, and the boot self-test L31188 are its only sources.
3. **Not retriggering on the per-tick `0xF0xx` writes.** The discrimination added in cpp:218-225
   is correct and necessary — `struct[+0x2d]` really is written to the same register as the gate
   (`ToneGen_WriteSingleReg`, called at L21486/L29210/L29243), and treating it as a note-on would
   restart the wave pointer.
4. **The gate is written in the MIDDLE of the note-on burst**, so `process_key_on` runs before
   +0x840…+0xA40 are updated. The HLE's ordering (resolve waveform → pitch → level at the gate)
   is nonetheless correct, because +0x040, +0x400 and +0x800 are all written *before* the gate
   (asm L29578/L29674/L29737).
5. **Voice allocation and stealing are not the HLE's job.** They are firmware-side list surgery
   over `0x148D + ch*0x27`; the HLE correctly does not model them. Its only obligations are the
   two readbacks the policy consumes (gaps 2 and 3). The observed monotone channel march is
   normal FIFO free-list behaviour, not a defect.
6. **Multi-partial patches need no special handling.** MEASURED: a 2-partial patch arrives as two
   independent, fully-programmed channels 528 µs apart (ch0 +0x040 = 0x7007, ch1 = 0x7017,
   different +0x180, same +0x400); a 3-note chord of the same patch occupied ch10…ch15. The HLE's
   per-channel model handles this correctly as-is.
7. **The permanently-gated voice 0 is the firmware's own doing, not a stuck HLE voice.** MEASURED
   at t=5.859: `+0x040 = 0x0000`, gate `0x8100`, gate `0xF000` (magnitude 0) on channel 0, with no
   matching `0x7E00`. `env_level = 0` so it renders silence. Correct as-is.
8. **The boot self-test sequence is handled safely.** For all 64 channels the firmware writes
   `+0x040 = 0x0002`, gate `0x8100`, gate `0x1200`, gate `0x7E00` (t≈4.07 s). `0x1200` falls
   through every branch in cpp:205-226 and is ignored; the channels end up off. No defect.

---

## 5. Reproduction

```
S=<scratchpad>
cd ~/compartilhado/kn7000-emulator
VLDIR=$S timeout 420 ./kn7000 kn5000 -rompath roms -window -nomaximize -skip_gameinfo \
  -nvram_directory $S/nvvl -autoboot_script $S/voicelife_probe.lua -autoboot_delay 0 \
  -video opengl -sound none
```
The probes install `install_write_tap` / `install_read_tap` on `":subcpu"` `program`
0x100000-0x100003. **The returned passthrough handler MUST be stored in a global** (`_G._vl_wtap`)
or Lua garbage-collects it and the tap silently never fires — the first run of this audit
returned 0 events for exactly that reason.

Disassembly anchors: `grep -n 'ToneGen_WriteVoiceParams\|LABEL_02D436\|LABEL_02B4A1\|LABEL_02219F\|LABEL_025589\|LABEL_032C0F\|LABEL_022340' <v142.asm>`.
