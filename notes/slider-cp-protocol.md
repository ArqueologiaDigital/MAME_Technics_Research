# Volume sliders / pots are delivered via the CP serial protocol (TYPE 2 frames) — NOT a raw ADC

**2026-07-12.** Correcting the earlier "find the ADC read address" hypothesis: the 4 volume sliders
(MAIN/APC-SEQ/MIC/LINE-IN), the data wheel, pitch-bend/mod and the expression pedal are **digitised by a
panel sub-CPU and delivered to the main CPU as TYPE 2 frames on the control-panel serial link**
(0x34000800), which the driver ALREADY models (`panel_queue` / the RX ring). So making a slider functional =
emit the right TYPE 2 frame when the ioport adjuster changes — no ADC modelling, no CPU-core change.

## The mechanism (see notes/panel-serial-protocol.md §c)
- Panel→main frames are 2 bytes `[ADDR, DATA]`. ADDR bit layout `[b7 b6 = bank | b5 b4 b3 = TYPE | b2 b1 b0 = sub]`.
- **TYPE 2 (`010`) = "latched / rotary control update (data wheel, sliders, pedal)"**, handler chain
  `0x484AD25F` → dispatch **`0x484AD680`** (32-entry table @ **0x48613108**).
- Dispatch index = `((ADDR & 0xC0) >> 3) | (ADDR & 0x07)`; only bank 00 and 11 are valid.

## The 6 real continuous controls (rest of the table = no-op handler 0x484AD7A7)
| wire ADDR byte (TYPE2) | dispatch idx | handler | latch RAM | scaling | remap table |
|---|---|---|---|---|---|
| **0x10** (bank00 sub0) | 0  | 0x484AD6B0 | 0x5006BEA0 | —              | 0x48613188 |
| **0x17** (bank00 sub7) | 7  | 0x484AD6A0 | 0x5006BE9F+0x5006BEA8 | — (raw, no remap) | — |
| **0xD0** (bank11 sub0) | 24 | 0x484AD740 | 0x5006BEA3 | asr 1 (÷2)     | 0x48613488 |
| **0xD1** (bank11 sub1) | 25 | 0x484AD6DE | 0x5006BEA1 | not (invert)   | 0x48613288 |
| **0xD2** (bank11 sub2) | 26 | 0x484AD772 | 0x5006BEA6 | not + asr 1    | 0x48613508 |
| **0xD3** (bank11 sub3) | 27 | 0x484AD70F | 0x5006BEA2 | not (invert)   | 0x48613388 |

(The "wire ADDR byte" is what a frame carries: `(bank<<6) | (2<<3) | sub`. The dispatch strips the TYPE
bits, so its index only sees bank+sub.) Each handler latches DATA (scaled) to its RAM byte, remaps through a
256-entry taper table, and diffs against a shadow (0x5006BEA8..0x5006BEAC) to emit a change event only when
the value moves. The **`0xD0-D3` group (÷2 / invert scaling) are the 4 analog VOLUME pots**; `0x10`/`0x17`
(bank00) are the data-wheel / pitch-mod family.

## NEXT — identify which ADDR is APC/SEQ VOLUME, then wire the driver
Identification is the only open piece. Two ways:
1. **Lua live-probe (no rebuild!):** the frame decoder `0x484AD111` reads the 92-byte RX ring at base
   **0x5006BDB4**, tail **0x5006BDB0**, head **0x5006BDB2** (wrap 0x5C). Inject a frame from Lua by writing
   `[header, DATA]` into `ring[head]`/`ring[head+1]` and advancing head by 2 (mod 92). Sweep DATA for each
   candidate header (0xD0/D1/D2/D3) and watch the effect.
   To know which is APC/SEQ: MUTE UP/DOWN 9 edits the SAME setting (sliders.txt). Press MUTE UP 9 (SEG09
   0x10) N times and tap RAM writes to find the APC/Seq-volume setting byte (the press-count method), then
   inject each 0xDx header and see which one moves that same byte.
2. **Driver implementation (once ADDR known):** on VOL_APCSEQ (PORT_ADJUSTER) change, emit `[0xDx, value]`
   through the existing panel frame path (panel_queue / the RX ring). Scale the 0..100 adjuster to the pot's
   raw 8-bit range, honouring the handler's invert/÷2 so the remap lands on the intended volume. Also light
   `apcseq_vol_led` when the slider position matches the current value (the soft-takeover the LED wants).
   The same pattern makes MAIN/MIC/LINE-IN functional too (their ADDRs come out of the same probe).

Verified data (all from kn7000_program.rom @ base 0x48400000): dispatch table dump + handler disasm above.

## ★ MECHANISM CONFIRMED LIVE (2026-07-12, /tmp/ringprobe.lua, no rebuild)
Injected a frame `[0xD0, 0xAA]` by writing it into the RX ring (RING[head]=0xD0, RING[head+1]=0xAA,
then head=(head+2)%92 at 0x5006BDB2) at t=8 on the home screen. Result: **0x5006BEA3 became 0xAA** — the
0xD0 handler (0x484AD740) ran and latched the raw DATA exactly as disassembled. So: (1) the RX-ring stuffing
DOES drive the decoder task (it polls head!=tail); (2) the ADDR→handler map is correct; (3) sliders are
injectable end-to-end from Lua. head/tail are u8 offsets (0..91); the ring had head=tail=4 idle at boot.

NEXT is now purely: (a) ID which of 0xD0-D3 is APC/SEQ (press MUTE UP 9 = SEG09 0x10, find the setting byte
it moves, then inject each 0xDx and see which moves the same byte); (b) implement in the driver: on
VOL_APCSEQ change, emit `[0xDx, scaled_value]` through panel_queue (or, minimally, the same RX-ring write).
The probe already proves (b) will work.

### Identification attempt 1 (2026-07-12, /tmp/idprobe.lua) — CONFOUNDED by the demo screensaver
Injected each of 0xD0-D3 (low+high swing) on the "home" screen and snapshotted. But the KN7000 auto-starts
its DEMO slideshow after a few seconds of no input, so by t=9 the LCD already showed demo graphics (not the
PMEM home screen), and all snapshots diff against that moving demo -> unreadable. Consecutive-diff signals
were noisy (D0 large, D2 small localized @ (505,218)-(537,268), D1/D3 lo->hi = 0) but not trustworthy under
the demo. FIX for the next attempt: keep the machine active (tap EXIT / a harmless button every ~1 s to
suppress the demo) OR navigate to a stable settings screen, THEN inject; better still, use the RAM
correlation (MUTE UP 9 finds the APC/Seq setting byte; inject each 0xDx to see which moves it) which is
demo-immune. Injection itself is proven (ring-probe PASS above).

## ★★ IMPLEMENTED & VERIFIED (2026-07-12) — APC/SEQ slider is functional
Identified 0xD2 = APC/SEQ by RAM write-correlation: its write-set overlaps MUTE UP 9's (SEG09 0x10, which
edits the same setting) by 44 addresses vs exactly 20 for 0xD0/D1/D3 (the 20 = shared CP-processing path).
Driver: panel_scan emits [0xD2, DATA] via panel_queue on VOL_APCSEQ change; DATA = 255 - adjuster*2.55
(handler 0x484AD772 inverts + remaps through the monotonic ramp 0x48613508, so lower DATA = louder).
Verified: the 0xD2 latch 0x5006BEA6 tracks the slider (vol 100->0xFF, 0->0x00, 50->0x80).

### ★ GOTCHA (cost a debugging cycle) — do NOT emit a panel frame before the firmware services the panel
The panel_queue delivery is a handshake: panel_queue kicks an ATN edge (group 0x1A) ONLY when the response
queue was_idle (fully drained). If you emit a frame during early boot (before the firmware runs the panel
handshake), it sits undelivered forever, so was_idle stays false and NO later ATN kicks fire -> ALL panel
delivery stalls (buttons included). Fix: a 'synced' flag records the pot's initial value on the first scan
WITHOUT emitting; only emit on a real change. Applies to any future sub-CPU-frame emission from the driver.

### NEXT (optional refinements)
- LED soft-takeover: light apcseq_vol_led when the slider position matches the current value; off when MUTE 9
  diverges it (needs an output finder + tracking the firmware value vs the last-emitted slider value).
- MIC / LINE-IN / MAIN pots: identify 0xD0/D1/D3 individually (same MUTE-correlation method against their
  MUTE partners, or a demo-suppressed display probe) and bind them the same way.

### LED soft-takeover probe (2026-07-13) — NOT firmware-driven via the panel LED shadow (in home/demo state)
Tapped the panel LED shadow (bank A 0x50150A3C, bank B 0x50150A7C) while moving VOL_APCSEQ and pressing MUTE
UP 9 (/tmp/ledprobe.lua). Moving the slider wrote only LED register 0 (0x50150A3C) = 0x00 (nothing lit);
MUTE 9 wrote nothing. So the apcseq_vol_led soft-takeover is NOT driven through the normal panel LED frames
in the home/demo state -- the firmware likely only runs the slider-vs-value comparison on a specific
volume/settings screen (or the indicator is hardware-only). apcseq_vol_led stays added-but-dark for now.
NEXT if pursued: repeat the probe on the accompaniment-volume settings screen, or model it driver-side
(compare VOL_APCSEQ's emitted value to the firmware's current setting -- needs the setting RAM address).

## ★ TEMPO/PROGRAM knob = 0x17 (RELATIVE encoder); DATA dial = 0x10 (2026-07-13, /tmp/tempoknob.lua)
Identified the two bank-00 rotary controls by injecting on the **home screen** and reading the on-screen
tempo (crotchet = NNN). KEY TIMING NOTE: the "musical-notes-over-Earth" image at t=8-11 is the **boot
splash**, NOT the inactivity demo -- the PMEM home screen appears at **t≈13**. Inject after t=13.

- **0x17 = TEMPO/PROGRAM knob** (the small center knob, not the big right-hand DATA dial). Injecting 0x17
  changed the tempo; injecting 0x10 (sweep 0x10..0xF0) left the tempo at 120 (unchanged).
- **0x17 is a RELATIVE (incremental) encoder, NOT an absolute pot.** Injecting distinct ABSOLUTE values
  gave non-monotonic tempos: 0x40→184, 0x80→56, 0x20→88, 0xF0→72, 0x10→88 (0x20 and 0x10 both →88; 0x40
  gives a HIGHER tempo than 0x80). The tempo moves by the DIFF between consecutive positions (with apparent
  velocity/acceleration -- big diffs jump further), exactly like a physical detented encoder. So its raw
  handler (0x484AD6A0, no remap, latch 0x5006BE9F/0x5006BEA8) feeds a downstream diff.
- **0x10 = the big DATA dial** (navigates / edits the focused field; no tempo effect on the home screen).
  Its handler 0x484AD6B0 diffs vs shadow 0x5006BEA9 -> EV_DIALUP/DOWN, consistent with a nav encoder.

### DO NOT wire either as an absolute PORT_ADJUSTER -- it would be a wrong-mapping guess (erratic tempo).
Correct wiring for the relative encoder (future task): a draggable knob whose adjuster DELTA (adj_now -
adj_prev) is accumulated into a driver-side uint8 position that wraps, emitting `[0x17, position&0xFF]` each
time it changes. The firmware diffs consecutive positions -> rotation = the delta, so dragging up = tempo up,
down = tempo down, continuously (the bounded 0..100 adjuster is fine because only deltas matter). Emit only
SMALL deltas per scan (scale≈1) to avoid the velocity jump. Same handshake gotcha as the APC/SEQ slider
(record the first scan without emitting). This needs a draggable KNOB element (vertical-drag hit area over
tempo_knob, like the volume sliders) + the delta-accumulator in panel_scan. Left unshipped deliberately:
a half-modelled relative encoder is worse than none, and faithful-first forbids the erratic absolute mapping.

## ★★ DATA dial WIRED & event-generation CONFIRMED (2026-07-13, commit 14ed7cb)
The panel already declared an `IPT_DIAL` port ("DATA DIAL") and `seg_to_addr[0x1A]=0x10` labelled
"VALUATOR wire -- DATA dial", but nothing read `m_dial` -> the big value wheel was dead. panel_scan now
forwards the IPT_DIAL accumulator as a CP TYPE-2 frame **[0x10, POSITION]** on change (handshake-poison
guard: record the initial position silently, emit only on a real move). MAME's IPT_DIAL is a relative
accumulator (0..255, wraps) = exactly what wire 0x10's handler expects (it diffs successive positions).

**Identification is conclusive (not a guess):**
- Handler 0x484AD6B0 does a RELATIVE diff: remap DATA through 0x48613188, compare vs shadow 0x5006BEA9,
  return **0xFFFF when unchanged** else the new value (and update the shadow). A relative ENCODER -- which
  RULES OUT an absolute pitch-bender (pitch bend sends absolute values, no diff).
- On a real change, the dispatch caller (0x484AD2CD, after `call 0x484AD680`) stores the value to
  0x5006BDA8 and **emits a [control_id, value, 0xFF] event** via the enqueue routine 0x484AD519, which
  pushes each byte into the event queue **0x5006bcf8** (push helper 0x484AD5B0; queue initialised from
  template 0x48613060). So turning 0x10 generates a genuine panel event; the consumer routes it by
  control-id/focus.
- ★ PROOF THE QUEUE IS LIVE: the APC/SEQ volume pot (0xD2) reaches this SAME queue via this SAME
  0x484AD2CD -> 0x484AD519 path, and that slider is already VERIFIED to drive the firmware's accompaniment
  volume (tick night(12g)). So the continuous-control event queue 0x5006bcf8 is proven-functional; the data
  dial rides the identical delivery path -- only the consumer's per-id ACTION differs (0xD2 -> volume set,
  0x10 -> data-dial EV_DIALUP/DOWN navigation). The dial is therefore delivered to a real, working consumer.
- Schematic CN1102 ROTA/ROTB -> AD0/AD1 = a rotary encoder (the data wheel); by elimination the other
  bank-00 rotary 0x17 = TEMPO/PROGRAM (confirmed) and 0xD0-D3 = the four volume pots.

**Verified live (driver path, NO ring injection):** driving the IPT_DIAL field from Lua
(`dialf:set_value(3,6,..30)`) makes the firmware's 0x10 latch 0x5006BEA0 track it exactly (00,03,..1E,
one-scan lag) -- so panel_scan reads m_dial and emits [0x10,pos] itself. Buttons still deliver (DISK MENU
still opens; no panel regression). seg_to_addr[0x1A] neutralised to 0xff so the dial solely owns wire 0x10.

**Honest scope:** the on-screen navigation effect depends on a FOCUSED value-edit field. Tried three
reachable screens; NONE visibly responds to the dial, each for a faithful reason:
- HOME (PMEM) -- no dial-focus by default -> dial does nothing (correct).
- DISK MENU -- navigated by the side SOFT-KEYS (the on-screen ◄► arrows), not the dial (0 px change).
- R1/R2 OCTAVE value-edit screen (reached via SEG13 0x02) -- the "OCTAVE : -2" value is edited by its ˅
  soft-key; the dial left it unchanged across a +2..+12 sweep while the screen stayed open.
So the dial's actual consumer screen (sound/style select, or a value-entry mode) was NOT reached. The
seg->function button map is unreliable (SEG13 0x02 opened OCTAVE, which the map calls "TRANSPOSE"), so
guessing the path to the sound-select is unproductive headlessly. The event-generation proof
(0x484AD2CD -> 0x484AD519 emits [0x10,value,0xFF]) + the relative-encoder handler are the substitute
evidence; the wiring is grounded + additive (was a dead port) with no regression. NEXT (optional): an
INTERACTIVE turn of the dial on a sound/style-select screen (Felipe, or a reliable menu path), or trace the
0x484AD519 event consumer to map EV_DIALUP/DOWN -> which screens' focus actually consume it.

### De-risk (2026-07-13, /tmp/temposmall.lua) — HIGH GAIN / ACCELERATION, so naive wiring would rail instantly
From a settled 0x40 (tempo 184), stepping the position by only **+4 per event at ~4 Hz** ran the tempo
184 → 252 → **300 (max)** in TWO steps and then saturated. So a single detent (+4) ≈ +68 BPM here, i.e. the
encoder is strongly velocity/acceleration-sensitive (consecutive same-direction events accelerate). CONSEQUENCE
for wiring: a delta-accumulator driven at frame rate (~60 Hz) would fire a burst of same-direction events →
instant acceleration → the tempo slams to the 300 rail on the smallest drag. To feel right the driver must
RATE-LIMIT emitted encoder events (e.g. ≤1 per N ms) AND scale the adjuster delta down hard (many adjuster
units per emitted +1), then tune visually. That tuning is the bulk of the work and why this is a focused
future task, not a tail-of-session rush. (The acceleration itself is faithful to a real detented TEMPO knob —
turn slow = fine, turn fast = coarse; the challenge is only mapping a mouse DRAG onto that without a burst.)
