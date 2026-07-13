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
So the dial's actual consumer screen (a value-entry / SEQUENCER mode) was NOT reached. The
seg->function button map is unreliable (SEG13 0x02 opened OCTAVE, which the map calls "TRANSPOSE"), so
guessing the path is unproductive headlessly. The event-generation proof
(0x484AD2CD -> 0x484AD519 emits [0x10,value,0xFF]) + the relative-encoder handler are the substitute
evidence; the wiring is grounded + additive (was a dead port) with no regression.

### UPDATE 2026-07-13 night(18): SOUND-SELECT hypothesis DISPROVEN; 5 screens tested; UI is soft-key/PAGE driven
Reached the PIANO sound-select correctly (SOUND GROUP PIANO = SEG10 0x10 per the LAYOUT, not the stale
notes' SEG0C 0x01) and drove the IPT_DIAL there: the 0x10 latch followed (00->0x28->0x50 = events fired) but
0 px changed on screen. The sound-select selects sounds via the LCD-flanking SOFT-KEYS (◄► arrows, e.g.
Vintage E.P.1 = SEG11 0x20) and pages via the PAGE badge (PAGE 1/3, SEG0B 0x10/0x20), NOT the dial. So the
"sound/style-select is the dial's consumer" guess is WRONG. Across FIVE screens now -- home, DISK MENU, R1/R2
OCTAVE, DEMO menu, SOUND-SELECT -- the data dial is FAITHFULLY INERT: the KN7000 UI is entirely soft-key +
PAGE driven. The dial's events are consumed only in a specific value-entry/SEQUENCER context. CONCLUSION:
the wiring is correct and the inertness is FAITHFUL; a visible demo requires the SEQUENCER (the remaining
untested consumer) -- reach it via the SEQUENCER section buttons, then turn the dial while a numeric field
(measure/step/value) is focused. Not a defect; just an unreached demo context.

### UPDATE 2026-07-13 night(19): SEQUENCER tested too (inert); 0x10 affects NEITHER screen NOR sound; KN5000 cross-ref
Tested SEQUENCER PLAY (SEG0D 0x08) and EASY RECORD (SEG0C 0x08): dial inert there too (7 screens total).
Then the DECISIVE sound test (/tmp/dial_tg.lua): played a sustained note, let the envelope settle, drove
0x10 across its full range, and counted TG register writes (0x98050000-0f) settled-vs-driving = **42 vs 42**
(no spike) with no reverb-output change. So **0x10 modulates the SOUND either -- it is NOT a MIDI-CC
controller (modwheel/pitch/etc.).** Net: 0x10 generates events (latch follows; queued to 0x5006bcf8, same as
the working APC/SEQ pot) that affect NEITHER the screen NOR the sound in any tested context.

**KN5000 CROSS-REFERENCE (kn5000-docs/data-wheel-investigation.md) -- the sister product's design pattern:**
the KN5000's data wheel is a NAVIGATION control that ends up posting a UI event (0x1C0001F); crucially, its
transport is SEGMENT-0x0B BUTTON PACKETS (bit7=CW, bit6=CCW), and that doc's "Previous Approaches (Failed)"
explicitly records that TYPE-2 encoder packets were the WRONG system there (the firmware treated them as MIDI
CC). The KN5000 is TLCS-900 (different CPU/addresses), so its code doesn't port directly, BUT the DESIGN is
instructive: (1) a data wheel posts a UI-navigation event when it works; (2) in this product family Type-2 is
for MIDI CC, and the nav wheel may be button-style. For the KN7000 the schematic says the wheel's ROTA/ROTB
-> AD0/AD1 -> the panel digitises it, and 0x10 = bank00 sub0 = AD0, so 0x10 IS plausibly the wheel's
transport -- but my exhaustive tests show it drives nothing observable. TWO live possibilities remain:
 (a) 0x10 IS the wheel, its consumer posts a nav event, but no reachable screen's focus acts on it (faithful);
 (b) the KN7000's real nav wheel is a BUTTON-STYLE CW/CCW mechanism (like the KN5000) on some segment, and
     0x10 is a vestigial/unused Type-2 line.
DECISIVE NEXT (the KN5000 doc's own method, ported): in the MAME debugger, drive 0x10 and watch the input
event queue's consumer / the UI-navigation event write -- if a nav event fires, it's (a); if nothing, hunt a
button-style CW/CCW wheel. The wiring stays (schematic-grounded, harmless, no regression) pending that or
real-hardware confirmation. This is now a well-scoped deep-RE task, not a headless screen-guessing chase.

### ★ RESOLUTION toward FAITHFUL (2026-07-13 night(20), /tmp/ram_diff.lua): the dial IS processed, not inert
Broad RAM diff of the CP/UI area (0x50060000-0x50070000, u32) on the idle home screen while driving 0x10
full-range: **45 words changed**, well beyond the latch -- the dial's events are actively CONSUMED and
PROCESSED. Concretely: the event queue buffer fills at 0x5006BC78+ ([0x10, remapped_pos, 0xFF] frames; the
raw dial 24,48,72.. is REMAPPED via table 0x48613188 to 0D,1A,27,34,40,4C,5E,72,8F,C5), head/tail advance
(0x5006BD00/04), a per-turn dial-position LOG accumulates at 0x5006BF44+ (one u32 per position), and CP-layer
state at 0x5006BEEC/0x5006BEF0 updates. Searching the firmware for those addresses: ALL references
(0x5006BEEC x2, 0x5006BEF0 x8, 0x5006BF44 x2) live in the CP/dial handler range 0x484AD8xx-0x484AE2xx -- i.e.
the input layer, NOT any display/UI code. CONCLUSION: 0x10 is a FUNCTIONAL relative encoder -- its handler
processes each position and posts change events -- so this is possibility (a) (faithful), NOT (b) a delivery
gap and NOT vestigial. The wiring is CORRECT and CONFIRMED working at the CP/event layer. The only thing
still unfound is the VISIBLE UI consumer (a focused screen whose cursor/value the posted events move); none
of the 7 tested screens has one. That is a UI-event-routing question (which screen contexts subscribe to the
dial event), separate from the now-settled "does the dial work" question -- it does. (Corrects the earlier
"inert/does-nothing" framing: the dial does nothing VISIBLE on these screens, but it is fully processed.)

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

## ★★ RESOLVED 2026-07-13 — APC/SEQ null LED (driver-side) + TEMPO/PROGRAM knob draggable (shipped)
Workflow RE (dispatch/handler traces, adversarially re-verified, both HIGH confidence):

**APC/SEQ VOLUME "null"/soft-takeover LED — now BOUND driver-side.** The main CPU NEVER emits a frame
for it: byte-grep of the whole image shows the slider latch 0x5006BEA6 has exactly ONE reference (the
0xD2 handler's own write @0x484ad779) and NO reader — the firmware literally cannot compare slider-vs-
value; the real panel sub-CPU does it in hardware. Faithful driver model (kn7000.cpp panel_scan):
`led = ( remap[(RAM 0x5006BEA6 >>1)&0x7F] == RAM 0x5006BEAD )`, remap = ROM ramp 0x48613508 (identity
0..125, then 127,127). The 0xD2 handler forces setting 0x5006BEAD = remap[slider>>1] on every slider
move (LED on); MUTE UP/DOWN 9 edit 0x5006BEAD via ptr-table 0x48613098[22] WITHOUT moving the slider
(LED off). VERIFIED live: after driving VOL_APCSEQ, setting=0x20==remap=0x20 and output apcseq_vol_led=1.
(The 4 pots: MAIN=0xD0 latch 0x5006BEA3 remap 0x48613488, MIC=0xD1 latch 0x5006BEA1 remap 0x48613288,
APC/SEQ=0xD2 latch 0x5006BEA6 remap 0x48613508 setting 0x5006BEAD, LINE-IN=0xD3 latch 0x5006BEA2 remap
0x48613388; only 0xD2's setting addr is confirmed — MAIN/MIC/LINE-IN null LEDs would need their setting
bytes traced.)

**TEMPO/PROGRAM knob 0x17 — now DRAGGABLE.** Handler 0x484AD6A0 (dispatch tbl 0x48613108[7]) latches the
raw wire uint8 verbatim to 0x5006BE9F + control-record 0x5006BEA8 (ptr tbl 0x48613088[7]); NO remap/scale;
a downstream tempo routine DIFFS consecutive positions (bigger diff = accel). Driver: PORT_ADJUSTER
"TEMPO_KNOB" + layout clickarea "tempo_click" (appended LAST in right_block so it doesn't shift nudge
indices) registered via add_simplecounter_knob; panel_scan slews the adjuster into [0x17, pos&0xFF] at
±1 PER SCAN (stays in the linear region — a big single diff rails the tempo). VERIFIED live: driving
TEMPO_KNOB 50→95 stepped 0x5006BE9F 0x00→0x2C (44 clean +1 steps) → tempo moves. Same first-scan-silent
handshake guard as the sliders. Tunable: raise the per-scan step cap or add_simplecounter_knob scale for
faster response; widen the adjuster range for more continuous rotation.

**TEMPO/PROGRAM knob LED — LEFT UNBOUND (undetermined).** RE found NO firmware signal dedicated to the
knob's green_led (164,336 in the layout). The tempo-STATE indicators are the already-bound 4 BEAT LEDs
(cpl_led24/32/40/48); SetDialLed(idx4)=cpr_led97 is a distinct "Dial" LED of unconfirmed physical
identity — binding it to the knob would be a guess. Left dark per "better dark than wrong". NEXT if
pursued: live LED-shadow probe while interacting with the knob, or the service-manual PANEL SW&LED list.

## ★★ CORRECTION 2026-07-13 — APC/SEQ VOLUME LED is a REAL matrix LED = cpl_led20 (RAM-probe hack removed)
The earlier "synthesize it driver-side from RAM 0x5006BEA6/BEAD" approach was a hack (Felipe rejected it).
The LED is a genuine CPL matrix LED with a definite (reg,bit), found from the service-manual CPL schematic
(DIAGRAM-15, p128): **LED D1179 "APC/SEQENCER"**, GREEN (LNJ382GKGX02), in the **SEG4 column, reg2 row** ->
**cpl_led20** (reg2*8 + bit4). Calibration: the reg2 row is D1115/D1131/D1147/D1163/D1179 = SEG0..4;
SYNCHRO & BREAK = D1115 = cpl_led16 (firmware-validated), so the row = cpl_led16..20. EMPIRICALLY confirmed
in the Panel SW&LED self-test (flag 0x5006BFB2=1): pressing ROCK&POP (SEG02 0x20) lights **cpl_led18** (reg2
bit2, its button LED) while cpl_led20 stays dark -> cpl_led20 is the NON-button LED in that row = APC/SEQ.
It is one of only two non-button CPL LEDs (the other is a split-point LED, D1157 "SPLIT POINT" = reg0 bit3 =
cpl_led3); per the manual §8.5, only DEMO (all-CPL) lights the non-button ones in the test.
FIX: layout binds the APC/SEQ green_led to name="cpl_led20"; panel_led_frame drives it the normal way. The
driver-side RAM synthesis + m_apcseq_led output are DELETED. LED-test handler = 0x484A0CB0 (per-switch LED
from PanelSwitchClassTable), special classes 0xF0-0xF7 for multi-LED buttons (0xF0 = the 4 START/STOP LEDs =
reg3-6 bit0 = the "no dedicated LED" fallback). Disasm helper: tools/dis.sh.
LIMITATION (honest): in the emulator's reachable states the MAIN CPU never commands cpl_led20 (the RE showed
the slider latch 0x5006BEA6 has no reader -> the soft-takeover "does the slider match the value" compare is
done by the panel SUB-CPU, which we model only at the protocol level, not its internal LED logic). So the LED
stays dark in normal use for now -- but the binding is faithful (it lights whenever cpl_led20 is driven, e.g.
a real unit's DEMO-lights-all-CPL). Restoring the *visible* soft-takeover faithfully would need modelling the
sub-CPU's pot-vs-target comparison, not a main-CPU RAM peek.
