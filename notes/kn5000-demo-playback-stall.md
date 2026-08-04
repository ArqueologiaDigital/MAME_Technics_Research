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

## UPDATE 3 — arm-poke test + where this stands

Poking the four transport bytes to the ARM value `0x01` (to let INTT1 promote them to `0x06`)
FAILS: `0x41F` promotes to `0x06` and survives, but `0x41E/0x420/0x421` are immediately zeroed by
the stop-guard **`f59c91`** (which fires from the `0x01`-arm substate). So "arm instead of sync"
is not the fix — the demo's intended path is genuinely the SYNC/count-in (`0x0C`), and only its
**completion trigger** is missing. Forcing free-run (`0x06`) from outside also fails to make the
demo play (it breaks the handshake; the transport disarms/stops). So no external poke reproduces
correct behaviour — the fix must let the firmware complete the count-in *its own way*.

## UPDATE 4 — ★ the transport STARTS RUNNING (0x06), then is CONVERTED to sync ★

Felipe (hardware ground truth): the real demo plays music **immediately, NO count-in**. A
full-frame-rate capture of the transition shows the transport is *correct at first*:

```
t=26.218  420=06 421=06   RUNNING (free-run), sub-tick 417: 02→05→07
t=26.278  420=04 421=04   still bit2 (running), 417=0A
t=26.298  420=0C 421=0C   ← FLIPPED TO SYNC (0x0C), 417=0D..16
t=26.377  420=10 421=10   PARKED
t=26.675  420=00 421=00   STOPPED (frozen at 417=18)
```

So the demo does NOT arm sync at start (my earlier framing was wrong) — it **starts in free-run
`0x06`, running correctly**, then ~80 ms later a transport command **converts the running
transport to sync `0x0C`** (`f5af3c` sets `0x0C` only when `0x420` already has bit2 set & bit3
clear — i.e. it takes a RUNNING transport to sync). The `0x0C`→park→stop death follows. Context
at the flip: `8d34=13 8d36=E4 28b2=00 fd50=10 fd56=FA 348a=09` (fd50 bit2 = internal clock; note
`348a` climbs 05→08→09 across the start).

**Revised bug statement:** the demo transport starts running as it should; the defect is that
**something dispatches a SYNCHRO/measure transport command (`f5af3c`) that flips the running
transport to sync `0x0C`**, which then parks and stops. On real HW that command is either not
issued or is harmless. Find what posts/dispatches it and the emulated condition it depends on.

## UPDATE 5 — runtime-verified flip source (RULES OUT the accompaniment diagnosis)

Felipe (hardware): real demo = music immediately, NO count-in. Confirmation probes + a
full-frame flip capture RULE OUT the earlier static hypotheses and pin the real source:

- **Auto-accompaniment is NOT the cause.** `0x3283=00` (auto-accomp NOT armed) and the six voice
  tables `0x3094/0x30C4/0x30F4/0x313C/0x3184/0x31CC` are ALWAYS empty (never bit7) — but the
  handler `f591D1` that a prior pass blamed is *gated on `0x3283` bit2*, so it never runs. The
  "fix the style/accompaniment engine" diagnosis is WRONG for this stall.
- **`f5af3c` / `f5ace5` are NOT the flip either.** Through the whole flip `0x41E`/`0x41F` stay
  `00` and `0x346d` stays `00`. `f5af3c` would set `0x41E=0x0C`; `f5ace5` needs `0x41E` running
  and sets `0x346d` bit4 — neither happened.
- **The real flip is `f5afb2`** (it sets BOTH `0x420` and `0x421` to `0x0C` and leaves `0x41E`
  alone — exactly what the capture shows). `f5afb2`'s in-function callers are guarded by
  `0x41E` running (false here), so it is reached via the **transport-command jump table**
  (`f59ac7: jp 0xf5afb2`) — i.e. a **queued "sync" transport command dispatched against the
  running demo transport**. State at the flip: `379b=00 28aa=0000 f19e=FFFF 28a7=01 346d=00`.

**Runtime-verified failure chain:** demo transport starts RUNNING (`0x420/0x421=0x06`, ticks
advancing — matches real HW) → ~80 ms in, a queued transport **sync** command (`f59ac7→f5afb2`)
flips both lanes to `0x0C` → INTTR4 parks `0x0C→0x10` at the 24-sub-tick boundary → transport
stops (`0x00`) → song never continues → SSF SysEx events never dequeue → slideshow latch
`0x251D8` stays 0.

**NEXT TARGET (precise):** find the PRODUCER of that sync transport command — what posts the
jump-table command that reaches `f59ac7/f5afb2` ~80 ms after the demo transport starts, and why.
On real HW it is either not posted or the resulting `0x0C` sync **releases back to running** each
measure (the demo plays continuously). The park (`0x0C→0x10`, INTTR4 `ef0fa0`) never releasing is
the emulator-visible symptom. Strong method: compare against the **KN7000** (its demo plays; its
transport-command posting for the same measure boundary does NOT wedge — diff the two paths).
Also worth a debugger breakpoint on `f5afb2` with a stack dump to capture the actual command
dispatcher and its poster in one shot.

## UPDATE 6 — ★ COMPLETE lifecycle traced (debugger write-tap + stack) ★

A Lua write-tap on `0x420` (with PC + TLCS-900 stack dumps; system stack = XSSP, XNSP unused)
captured the full transport lifecycle and its exact instructions. The demo transport works, then
the first measure-boundary sync KILLS it:

```
0xD2F (demo timer) counts down; at ==1  → f86c1f: ld (0x2966),0x85           [arm request]
  → per-tick f43ca9 counts 0x2966 0x85→0x80, then f43cf8: ld (0x420),0x01     [ARM]
  → INTT1 ef0cac: ld (0x420),0x06                                            [RUNNING ✓]
  ... runs ~1 measure (0x417: 0→24) ...
  → measure boundary: ISR ef1376 → … → f5adca (lane dispatcher, index from which lanes run)
      with 0x420+0x421 running but 0x41E NOT (index 0x18) → f5afb2: ld (0x420),0x0C  [SYNC]
  → INTTR4 ef0fa0: ld (0x420),0x10  at 0x417==24                             [PARK]
  → per-tick f3ecd4 (called unconditionally from f4e63f in the ISR tick seq)
        f3ece5: res 4,(0x420)  → 0x10 becomes 0x00                          [★ STOP ★]
  → transport dead; armed only ONCE per song (0xD2F==1), never resumes → song dies after 1 measure
```

**Key facts:**
- `f3ecd4` (clears park bit4 + bit1 of `0x420`/`0x41E`) is normal per-tick housekeeping — so the
  park `0x10` is meant to be transient. The transport is armed **once per song** and is supposed to
  **stay running (`0x06`) for the whole song**; the per-measure sync `0x0C` should return to `0x06`.
- Nothing traced returns `0x0C → 0x06`. The sync `0x0C` sits until INTTR4's 24-tick beat-park
  (`0x0C→0x10`) then f3ecd4 clears it to `0x00`. So **the first measure-boundary sync is caught by
  the beat-park and killed** instead of resuming. THAT is the precise defect.
- The `0x41E` lane never runs (routes the dispatch to `f5afb2`), but `f5af9d` (the 0x41E-running
  path) falls through to `f5afb2` anyway — so it sets `0x420=0x0C` regardless; the 0x41E lane is
  not the deciding factor for the 0x420 kill.
- `f43cf8` (arm) exact PC confirmed: `F43CFD`; INTT1 promote `EF0CB1`; sync `F5AFC8`(=f5afb2);
  park `EF0FA5`(=ef0fa0); stop `F3ECE9`(=f3ece5 res 4). `f3ece9` earlier "FLIP#2/3" were false
  tap hits (a `res 1` RMW writing 0x0C back).

**THE OPEN QUESTION (precise):** what returns the measure-sync `0x0C` to running `0x06` on real
hardware before INTTR4's beat-park catches it? Candidates: (a) a per-tick sync-processing step that
resets `0x0C→0x06` after the measure transition (not yet found — check the rest of the ISR tick
sequence f4e635..f4e656: f39290, f4e66f, f3ecb8, f4e699, f437cb, f2057d, f43ca9, f3639c); (b) a
timing/phase issue — on HW the `0x0C` is set and cleared within the same beat so `0x417` never
coincides with a park boundary while `0x0C` is set (the INTTR4 park `ef0f81` may be firing when it
should not, e.g. Timer4 tick phase vs the sequencer). Felipe: real demo plays continuously, no
count-in, so the transport MUST stay at `0x06` through measures.

**BEST NEXT METHODS:** (1) trace the remaining ISR tick calls (above) for a `0x0C→0x06` reset;
(2) compare against the **KN7000** (its demo plays continuously through measures — same architecture,
different CPU) to see how its transport survives the measure sync; (3) verify the INTTR4 beat-park
(`ef0f81`/`ef0fa0`) is even correct for this path — it may be a count-in-only behaviour wrongly
applied. Do NOT ship a poke.

## UPDATE 7 — ★ THE LINCHPIN: 0x41E lane never arms because f86fff(song 18)==0 ★

The INTTR4 handler DOES have a pattern-end **re-arm** path: `ef0f52: ld (0x0420),0x01` (+ 0x421),
reached when the transport is stopped but conditions met — GATED on **`0x41E` running**
(`ef0f30: bit 2,(0x041e)`, plus counters 0x415≥0x5f, 0x434≥1, 0x416≥0x433-1). This is what would
restart the transport for the next pattern/measure. It never fires because **`0x41E` is never
armed.**

`0x41E` is armed in the re-arm handler `f43ca9` ONLY conditionally:
```
f43cd1: ld A,(0x28a4)          ; demo song index (=0x12=18 for the FEATURE PRESENTATION, set at f86b74)
f43cd7/f86fff: call 0xf86fff   ; returns L = count of qualifying parts in the song
f43cdb: cp L,0 ; jr Z f43cf3   ; if 0 → SKIP arming 0x41E
f43cdf: ld (0x041e),0x01       ; arm 0x41E only if f86fff != 0
```
Runtime confirms `0x41E` stays 0 all run ⇒ **`f86fff(18) == 0`.**

`f86fff` (0xF86FFF) iterates the song's parts via song-data accessors `f86fb7`/`f86fdc`/`f86f92`
(indexed by the song index), counting parts whose type ∈ {0x0D,0x0E,0x0F,0x10}, that pass a mask
from table `0xEA00DA`, and have bit7 set in the third accessor's record. For song 18 it finds none.

**PRECISE ROOT (as far as traced):** the FEATURE PRESENTATION runs demo song **18**; `f86fff(18)`
returns 0 → the `0x41E` accompaniment/melody lane is never armed → the INTTR4 pattern-end re-arm
(`ef0f52`) is disabled → after the first measure-sync parks+clears `0x420` to 0x00, nothing
restarts it → song (and thus the SSF slideshow) dies.

**THE NEXT QUESTION (fixable-defect candidate):** is `f86fff(18)==0` correct, or does song 18's
data / the accessors (`f86fb7`/`f86fdc`/`f86f92`) return empty/wrong in emulation? If song 18
SHOULD have a qualifying part (so `0x41E` arms on HW), the defect is in the song-data those
accessors read (loading/decoding) — check what `0x28a4=18` resolves to and whether its part
records are populated. If `f86fff(18)==0` is genuinely correct, then the FEATURE PRESENTATION is
not supposed to use the 0x41E lane and the survival mechanism is elsewhere (re-examine — but note
`ef0f52` is the only pattern-end re-arm found). This is the single most promising lead for the fix.

## UPDATE 8 — song data IS loaded; f86fff fails on the part-qualification sub-checks

Dumped the current-song RAM buffer at `0x69800` during the demo (the accessors `f86fb7`/`f86fdc`/
`f86f92` read `table[songidx]` at `0x9C4000`, and when non-null use the fixed RAM buffer `0x69800`;
`table[18]=0x008E0000` non-null → uses `0x69800`):
```
0x69800: 5A 5A 5A 5A 01 01 08 00 0C 00 ...            "ZZZZ" magic — song IS loaded
0x69820: 00 02 01 0B 0F 09 0A 03 04 05 06 07 11 12 13 0C 10 10 10 ...   part-type array (has 0F,10)
```
So the demo song data loads correctly — **this is NOT an emulation data-loading bug.** `f86fff`'s
FIRST check (part type ∈ {0x0D..0x10}) passes for the `0x0F`/`0x10` parts, yet `f86fff(18)` still
returns 0 (0x41E never arms). So every part fails one of the two FURTHER checks in `f86fff`:
`f87059` (mask `0xEA00DA[type*2]` AND the 16-bit value from `f86fb7`=`*(0x69800+0x1e)`=0xFFFF here)
or `f87071` (bit7 of the per-part record from `f86f92`, 3 bytes/part).

**Consequence:** either (a) `f86fff(18)==0` is CORRECT and this song's transport is NOT meant to
use the `0x41E` lane / `ef0f52` re-arm — so its per-measure survival mechanism is something else not
yet found (but `ef0f52` is the only pattern-end re-arm located); or (b) one of the two sub-check
inputs (`f86f92`'s per-part bit7, or the mask table vs `0x69800+0x1e`) reads differently than on
hardware. Distinguishing these needs the semantics of those part records — best obtained by the
**KN7000 comparison** (its demo plays continuously through measures; find its equivalent survival
path) or Felipe confirming whether the KN5000 demo's backing is a full multi-part arrangement.

## STATUS / RECOMMENDATION (what "fixing it like the KN7000" needs here)

The KN7000 fix was a clean *driver-side timer model*. This is NOT that — the KN5000 timers work.
The single root is a **synchro/count-in transport that never completes** (`0x0C` → parked `0x10`,
no `0x0C→0x06` path in the timer handlers), which starves both the song and the SSF slideshow.

To finish the fix, the next investigation must find **what completes the synchro/count-in on real
hardware** and provide it in emulation. Leading candidates, in priority order:
1. **A synchro-start trigger** — the style/accompaniment is armed to start on a chord-section
   note-on; the demo song's first chord should fire it. If the emulated note→synchro path drops
   the trigger, the count-in never completes. (Trace the synchro-start detector: reads of the
   `0x0C` state + the note-on hook in the accompaniment engine, `f59a..`/`f5af..` and callers.)
2. **A count-in-complete signal** driven by a second timer or the sub-CPU/tone-gen that the HLE
   doesn't emit.
3. The `f83c25` direct SSF-file parser cluster (2nd-pass caveat) as an independent slideshow route.

⚠ Do NOT ship a poke/force of `0x420=0x06` — it is not faithful and does not actually play the
demo (proven above). Fix the real completion path.

★ HARDWARE QUESTION FOR FELIPE (ground truth, decides direction): on the real KN5000, when the
Feature Demo / Feature Presentation runs, **does it play music under the slides, and is there an
audible count-in (a few metronome beats) before the music starts — or do the picture slides just
cycle on their own with no accompaniment?** That distinguishes "provide the count-in/synchro
completion" from "the slideshow should run independently of the sequencer."

## Repro / tooling

- Probes: scratchpad `kn5000_demo_probe.lua` (state), `_probe2.lua` (enable chain + T16RUN),
  `_probe3.lua` (8-bit timer + interrupt SFRs). Run:
  `cd kn7000_mame_build && DISPLAY=:0 timeout 260 ./kn7000 kn5000 -rompath ./roms -skip_gameinfo
   -autoboot_delay 0 -autoboot_script <probe> -snapshot_directory <dir>`
- DRAM/SFR read from `:maincpu` "program" space (LE); SFRs live at 0x00–0xFF (T8RUN 0x80,
  T16RUN 0x9E, INTET01 0xE4, INTET45 0xE6).
- Disassembly: `kn5000-roms-disasm/v10/maincpu/kn5000_v10_program.s` (labeled) and
  `kn7000_mame_build/roms/kn5000/kn5000_v10_program.asm` (hex addrs). INTTR5 handler 0xEF086A.
