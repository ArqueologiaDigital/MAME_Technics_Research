# KN5000 Feature Demo playback — current state + stall root-cause (2026-08-04)

Task: "fix the DEMO presentation playback in KN5000, similarly to how we fixed it in the
KN7000 driver." The KN7000 fix (commit 60d5392) modeled an unmodeled on-chip 16-bit
**tempo/pacing timer**; once it ticked, demo songs AND the visual slideshow played (slideshow
pacing = song position). See notes/demo-and-sequencer-engine.md.

## HEADLINE — the March-2026 conclusions are STALE and partly WRONG

Measured on the current build (binary 2026-08-03, source has the INTTR5 16-bit-timer fix that
was imported 2026-07-20 in f1b605d — the "final fix" from the March timer-bug research log).
Navigation: DEMO (`CPL_SEG3` 0x01) → LEFT 4 (`CPL_SEG9` 0x02) → LEFT 2 (`CPL_SEG10` 0x01).

- ✅ **The Feature Demo now ACTIVATES and renders its first SSF slide** — FTBMP01, the
  "Technics" world-globe opening image, is on the LCD (snapshot captured). The March doc claim
  "SSF never triggers in automated mode / tag 0x82xx vs 0xB80A" is a **red herring**, exactly
  like the KN7000 "which gate holds?" question that the tempo-timer fix dissolved. Do not chase
  the 0xB80A workspace-tag theory.
- ✅ **INTTR5 fires**: sequencer sub-ticks 0x417/0x41B advance 0→0x18 (were frozen at 0 forever
  in March). PlaySong returns (0x8F4E: 0x04→0x06). AccPlayMode (0x22FC) advances 0→1→3.
- ❌ **Then it STALLS** after a ~0.3 s burst and freezes for the rest of the run (t≈27→84 s):
  the demo is stuck on slide 1, silent, `8D38` never reaches 0xE1 ("playing"), SSF state
  `0x251D8` never leaves 0.

## The stall, measured (3 MAME runs, high-rate sampling through the transition)

Timeline once LEFT 2 is pressed (demo song auto-selected = entry 0x12 = 18, the last song):
demo countdown `0xD2F` 0x0E→0 (works; main-loop driven) → song loads (`parts 0x10420`
2500→044A) → PlaySong returns → AccPlayMode 1→3 → promotion `0x420/0x421` 0→06→10 → sub-ticks
`0x417/0x41B` 0→0x18 (burst) → **promotion collapses 0x10→0x00** → sub-ticks FREEZE at 0x18 →
dead.

Decisive SFR / DRAM readings **held constant through and after the stall**:

| signal | value | meaning |
|---|---|---|
| `T16RUN` (0x9E) | **0x81** | Timer4 (bit0) running + prescaler (bit7). The pacing timer is NOT stopped. |
| `T8RUN` (0x80) | **0x0A** | Timer1 (bit1) + Timer3 (bit3) running. **Timer1 is clocking.** |
| `INTET01` (0xE4) | **0x30** | INTT1 enabled at priority 3, pending bit (0x80) clear → INTT1 *can* fire. |
| `INTET45` (0xE6) | **0x83** | INTTR5 priority 3, pending bit set. |
| `0x41A` (internal clock) | **0x00 ALWAYS** | never advances — even during the burst. ← the anomaly |
| `0x41E` (seq enable, bit2) | **0x00 ALWAYS** | sequencer never fully enables |
| `0x417`/`0x41B` (sub-ticks) | 0→0x18 then frozen | INTTR5-driven, gated off when promotion collapses |
| `0x41C` (alt-seq TICK) | **0x00 ALWAYS** | the counter AccPlayMode state-3 waits on — never moves |
| `0x420`/`0x421` (promotion) | 0→06→10→**0** | enables then tears down in lockstep with the freeze |
| `0x22FC` (AccPlayMode) | 0→1→**3 frozen** | wedged in state 3 |
| `0x251D8` (SSF demo state) | 0x0000 ALWAYS | visual presentation never advances past slide 1 |

## Diagnosis (measurement-established, causal firmware map in progress)

- The pacing timer (Timer4/INTTR5) is fixed and runs continuously — this is NOT the KN7000 bug
  repeated. The sub-ticks it drives run in a burst then get **gated off** when the higher-level
  "promotion/enable" (`0x420/0x421`) collapses to 0.
- The promotion collapses because the **internal clock `0x41A` never advances**, even though
  Timer1/INTT1 are live and enabled. So either (a) `0x41A` is not INTT1-driven, or (b) its
  INTT1-handler increment is gated by a condition that is never met.
- Strong hypothesis (from the KN7000 sibling): the sequencer is effectively in **external /
  MIDI-clock mode** (KN7000 gate: "transport start refuses silently if clock-source byte
  0x50149662 != 0"). In that mode the internal clock waits for external clock pulses that never
  come in the demo, so `0x41A` stays 0, the promotion tears down, and AccPlayMode state 3 waits
  forever on `0x41C`. The KN5000 clock-source byte + its check is being located in the
  disassembly.

## UPDATE (same day) — corrected interrupt map + poke tests

**Interrupt-map correction (verified 3 ways).** The active 16-bit tick interrupt is **INTTR4**
(TREG4/low-register match, vector 0xFFFF60 → handler **0xEF0E21**), NOT INTTR5. `0xEF086A`
(INTTR5, vector 0xFFFF64) is an empty `reti`. Runtime confirms: `INTET45=0x83` decodes as INTTR4
priority 3 (enabled, low nibble) + INTTR5 priority 0 (disabled, high nibble, pending bit stuck).
The March research log had this BACKWARDS (it "corrected" from INTTR4 to INTTR5 — that was the
mistake). The MAME timer_16bits fix is still correct: TREG4 match sets the INTTR4 flag (0x08),
TREG5 match resets the counter — so INTTR4 fires each interval. No timer bug remains.

**The stall mechanism (disassembly, INTTR4 handler 0xEF0E21).** Sub-ticks `0x417`/`0x41B`
increment only while `0x420`/`0x421` bit2 = 1; `0x41C` (beat) increments only when `0x41B` wraps
at 0x60 (96). The demo's transport reaches the **sync/count-in value `0x0C`** (bit3 set), and the
handler **parks** `0x420`→`0x10` (bit2 clear) at the first multiple-of-24 sub-tick (`ef0f81`..
`ef0fa0`), freezing the sub-ticks before `0x41B` ever reaches 96. Free-run is `0x06`
(bit2 set, bit3 clear, no park); the *internal-clock* path (INTT1 handler `ef0cac`, after a
`0x41A` dwell) promotes `0x01`→`0x06`. So the fork is **internal free-run (0x06) vs a SYNC
transport command (0x0C)**. `0x0C` setters: `f5af48`/`f5afc3` (transport helper `f5af3c`) and the
MIDI external-clock handler `fcf6..`; `0x06` setters: the INTT1 internal-clock path `ef0c..` and
the internal MIDI path `fcf5..`.

**Poke tests (runtime causal proof).**
- *Crude* (force `0x420/0x421=0x06` every frame): the tick engine runs continuously — `0x41C`
  advances `0x0D→0x1D` at a musical rate. Confirms the park was the clock block. **But** `acc`
  stayed 3, `0x41E` stayed 0, and **`0x251D8` (SSF slideshow) stayed 0** — the demo did NOT
  visibly play. Forcing the clock is not sufficient and clobbers firmware state.
- *Surgical* (convert `0x0C→0x06` only when it appears, once): the firmware then drove `0x420`
  to `0x00` (a **transport STOP**) and everything stayed frozen. So after the sync-park the
  transport is actively STOPPED, not merely parked.

**Consequences / revised diagnosis.**
1. The sequencer-clock stall (sync-park → stop) is real, but **fixing the clock does NOT advance
   the visible presentation** — `0x251D8` never leaves 0 in either poke. The user's "presentation
   playback" == the **SSF slideshow state machine at `0x251D8`**, which is the piece still to map.
   Whether it is song-position-paced (like the KN7000 slideshow) or independently timed is the
   open question that decides the fix.
2. Why the demo takes the SYNC (0x0C) path instead of internal free-run (0x06 via arming 0x01),
   and what STOPS the transport, are still open (transport-command caller `f5af3c` not yet traced
   to the demo start).

This is a **multi-layer** issue (as March suspected "two independent bugs"), not a one-line fix.

## UPDATE 2 — the two layers are ONE dependency chain (single root)

Second disassembly pass mapped the SSF slideshow and the transport handoff:

- **`0x251D8` is a boolean "presentation-active" latch (0/1), not a slide counter.** Writers:
  `f86313` set=1, `f86625` clear. Owned by an SSF-player GUI object (dispatcher `0xF86694`,
  child of AcPresentationControlProc `0xF8450B`). It flips 0→1 only on message `0x01E10007`,
  produced downstream of **AcPresentCtrl_CheckSSFStart `0xF84625`** whose gate is a data-block
  header `== 0x0000B80A` (`f84636`) — a value that only ever arrives **in a delivered SSF data
  block**, never written by an instruction. So the presentation start is **event/data-gated**.
- **Slides advance on SSF SysEx EVENTS in the song stream, not on any position cell.** The SSF
  decoder `f84b6f` is driven from the SysEx/SMF router `f0e92f` (screen id `0x8D38` must be
  `0xEA`); it parses opcodes 0x82/0x83 and calls `f83cea`, which broadcasts `0x01C0001C` →
  CheckSSFStart. **This is exactly why poking the beat counter `0x41C` did nothing** — the
  slideshow is keyed to the sequencer DEQUEUING the next SSF event, which requires the song to
  actually play.
- **The demo deliberately arms SYNC/count-in (`0x0C`)** — `f71f04: ld (0x041f),0x0c` at demo
  entry, and the `f5af..` transport helpers set `0x41E/0x420/0x421 = 0x0C`.
- **Handoff analysis (INTT1 handler `0xEF0BF9`).** The ONLY promotion to free-run `0x06` is from
  the ARM state (`0x01`): `ef0c61` tests `0x420` bit0, then after a `0x41A` dwell `ef0cac` sets
  `0x420=0x06` (and `ef0cbb/ef0cca` do the same for `0x41E/0x421` if they hold bit0). The SYNC
  state `0x0C` (bit3) is only ever **parked to `0x10`** (`ef0d3a` for `0x41F`; `ef0fa0` in
  INTTR4 for `0x420`). **There is NO `0x0C → 0x06` path in the timer handlers** — completing the
  synchro/count-in (0x0C → arm 0x01 → free-run 0x06) must come from an external trigger the
  accompaniment engine expects (a synchro-start note-on and/or a count-in completion).

**SINGLE ROOT:** the demo arms a synchro/count-in transport; the timer parks it and nothing
completes the handoff to free-run → the song never plays past the count-in → the medley's SSF
SysEx events are never dequeued → CheckSSFStart never sees a `0xB80A` block → `0x251D8` stays 0
and the globe never advances. **Fixing the one handoff un-sticks BOTH the audible sequencer and
the slideshow.** The missing thing the emulation must provide is whatever completes the
synchro/count-in — most likely a **synchro-start trigger** (the song's first chord note-on) or a
count-in-complete signal — routed to the transport dispatch (`f59a..`/`f5af..`).

Open sub-thread the 2nd pass flagged: `f83cea` has a second caller cluster near `f83c25` in the
demo module (possibly a direct SSF-file parser, not the song-event path) — worth checking as an
independent slideshow route.

## What "fixing it like the KN7000" means here

NOT another timer-modeling change (Timer4 already fixed). The remaining defect is the
**internal-clock / clock-source gate**: find the cell that drives `0x41A` and the condition the
firmware checks before letting the internal sequencer clock run, and make the emulation satisfy
it (a missing internal-clock tick source, or a default clock-source/sync byte the emulation
leaves in the wrong state). Once `0x41A` advances, per the KN7000 analogy both the music and the
slideshow (`0x251D8`) should follow.

## Repro / tooling

- Probes: scratchpad `kn5000_demo_probe.lua` (state), `_probe2.lua` (enable chain + T16RUN),
  `_probe3.lua` (8-bit timer + interrupt SFRs). Run:
  `cd kn7000_mame_build && DISPLAY=:0 timeout 260 ./kn7000 kn5000 -rompath ./roms -skip_gameinfo
   -autoboot_delay 0 -autoboot_script <probe> -snapshot_directory <dir>`
- DRAM/SFR read from `:maincpu` "program" space (LE); SFRs live at 0x00–0xFF (T8RUN 0x80,
  T16RUN 0x9E, INTET01 0xE4, INTET45 0xE6).
- Disassembly: `kn5000-roms-disasm/v10/maincpu/kn5000_v10_program.s` (labeled) and
  `kn7000_mame_build/roms/kn5000/kn5000_v10_program.asm` (hex addrs). INTTR5 handler 0xEF086A.
