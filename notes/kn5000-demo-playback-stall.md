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
