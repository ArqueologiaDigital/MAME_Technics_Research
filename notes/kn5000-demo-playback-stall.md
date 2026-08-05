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

## UPDATE 9 — ★ REFRAME: general playback bug, NOT demo/f86fff-specific ★

Two experiments corrected the story:
- **Rhythm START/STOP** (select POP&BALLAD, press START/STOP): `0x41E=0x420=0x04` (running) SUSTAINED
  for 27 s, `0x417` ticking — the transport CAN idle without dying. BUT `AccPlayMode (0x22FC)=00`
  the whole time and `0x41B`/`0x41C`=0: the rhythm was **idling, never actually PLAYING** (my
  START/STOP didn't reach play mode). So this is NOT a working-playback comparison.
- **Force-arm `0x41E`** (poke `0x41E=0x01` whenever `0x420` is armed, + reset the ef0f52 counters):
  **NO effect** — the demo stays dead exactly as before. A force-armed `0x41E` just gets measure-
  synced/parked and dies too. So the **`f86fff` / `0x41E`-re-arm (ef0f52) angle is a RABBIT HOLE.**

**Corrected root framing:** the transport dies whenever the sequencer ACTUALLY PLAYS
(`AccPlayMode 0x22FC == 3`) and reaches a measure boundary — the `0x0C` measure-sync → INTTR4 park
(`0x10`) → f3ecd4 clear (`0x00`) has **no `0x0C → running` recovery**. The demo reaches
`AccPlayMode=3` and dies at measure 1; a truly-playing rhythm would almost certainly die the same
way (untested — couldn't get one to reach AccPlayMode=3). So this is a **GENERAL KN5000
sequenced-playback defect at the measure boundary**, likely affecting demo + rhythm + song playback
alike. It is NOT specific to demo song 18 or `f86fff`.

**The ONE unresolved question (unchanged, now correctly scoped):** what clears the measure-sync
`0x0C` back to a running value on real hardware, in the window between f5afb2 setting `0x0C` and
INTTR4's next 24-tick beat-park? No such path exists in the traced code. Candidates: (a) an
emulation TIMING/phase error so the park (`ef0f81`, at `0x417 ∈ {0,24,48,72}`) fires while `0x0C`
is set when on HW `0x0C` is cleared first — check Timer4 tick rate/phase vs the sequencer; (b) the
sequencer's measure-advance is supposed to rewrite the lane to running as part of processing the
`0x0C`, and that step is gated on something the emulation doesn't satisfy. STRONGEST METHOD remains
the **KN7000 comparison** (its demo plays continuously through measures). ⚠ Do NOT chase `f86fff`.

## UPDATE 10 — ★ DEEPEST ROOT: a DEMO-CONDITIONAL section-end clears 0xf19e ★

Traced the re-arm block to the end. The beat dispatcher `f5ae1c` routes to the re-arm handler
`f5ae77`→`f5af5f`→`f5af8f` (`ld (0x420),0x01`) ONLY when `0xf19e != 0`. A write-tap on `0xf19e`
caught exactly two writes during the demo:
```
f19e <- FFFF  @PC=F43BF6   (setup, before playback)
f19e <- 0000  @PC=F3A194   (right after the stop — THIS blocks the re-arm)
```
The clear is `f3a18e: ld (0xf19e),0x0000`, inside a "section-end" handler (function entry `f3a09a`),
and it is **GUARDED BY `f3a187: cp (0x8d34),0x13; jr NZ`** — i.e. it fires **ONLY in the DEMO
state (`0x8d34==0x13`)**. In normal playback that clear is SKIPPED, `0xf19e` stays non-zero, the
beat dispatcher keeps hitting `f5ae77`, and the transport re-arms every measure (run→sync→park→
stop→**re-arm**→run). In the demo, `0xf19e` is cleared → dispatcher routes to `f5ae9b` instead →
NO re-arm → the transport stays stopped → song dies → slideshow frozen. And it fires after just
**one beat** (24 ticks).

**So the transport IS designed to die-and-re-arm each measure; the demo-specific `0xf19e` clear at
`f3a18e` breaks the re-arm.** The confirmed lifecycle: `f5af8f` (per-measure re-arm) NEVER fired in
the demo (only the once-per-song `f43cf8` arm did).

**THE REMAINING QUESTION (precise, deepest):** why does the demo's section-end handler (`f3a09a`,
reaching `f3a18e`) fire after one beat and clear `0xf19e`? Is that a premature end-of-section
detection (the sequencer thinks the demo song's section ended when it shouldn't), or is it correct
and the demo is meant to CYCLE via the demo timer `0xD2F` (which froze at 0 and never reloaded for
the next song)? Trace: the caller of `f3a09a` and the end-of-section event that reaches it; and
separately why `0xD2F` doesn't reload after the section ends. Key addrs: section-end handler
`f3a09a`/`f3a18e`, re-arm gate `0xf19e` (set `f43bf6`, cleared `f3a18e`), beat dispatch `f5ae1c`,
re-arm `f5af8f`, demo timer `0xD2F`/`f86bf3`.

## UPDATE 11 — keeping 0xf19e non-zero does NOT fix it → deeper re-arm DEADLOCK (timing)

Decisive test: a write-tap that FORCES `0xf19e` to stay `0xFFFF` (returns 0xFFFF whenever anything
writes 0). Result: `0xf19e=FFFF` the whole run, but the **transport still dies** (`0x420=00`,
`0x417` frozen at 24, `0x41C=0`) — the re-arm `f5af8f` still never fires. (It also knocked
`AccPlayMode` 3→1, i.e. the poke was disruptive.) So **preventing the `f3a18e` clear is NOT the
fix.**

**Why:** the re-arm path (`f5ae1c`→`f5ae77`→`f5af5f`→`f5af8f`) is a BEAT-boundary handler, but the
beat clock `0x417` only increments while `0x420` bit2 is set (`ef0e70` gate). When the transport
stops (`0x420=0x00`), `0x417` STOPS → no more beat boundaries → the beat handler that would re-arm
is never called again. A genuine **deadlock**: the re-arm needs a beat, the beat needs the transport
running. It must therefore fire in the exact tick where the park/clear happens — and in emulation it
loses that race.

**All state-level pokes now REFUTED:** force `0x420=0x06` (breaks handshake), force `0x420=0x04`
surgically (stopped), arm `0x41E` (dies too), keep `0xf19e` non-zero (still dies). None sustain the
transport. This is strong evidence the defect is a **TIMING/ORDERING issue in the tick ISR**, not a
single wrong cell: the sequence per tick is fixed (`f4e635..f4e656`: …`f3ecd4`(clear park)…
`f43ca9`(re-arm-countdown)… + the beat handler), and the ORDER/PHASE at which the park (INTTR4
`ef0fa0`), the clear (`f3ecd4`), and the beat-re-arm (`f5af8f`) execute in the same tick decides
whether the transport survives. On real HW they interleave so it survives; in emulation the re-arm
misses.

**STRONGEST REMAINING LEADS (need a new angle — state-poking is exhausted):**
1. **Timer4 rate/phase vs the sequencer.** If INTTR4's tick rate/phase (prescaler, TREG5 reload,
   the 24-tick beat) is subtly off, the park catches the sync at the wrong moment. Verify the KN5000
   Timer4 clock/prescaler + the `0x417∈{0,24,48,72}` beat math against the TMP94C241 datasheet and
   the firmware's tempo programming (analogous to the KN7000 tempo-timer fix's 1,250,000/BPM).
2. **ISR call-ordering.** Trace the EXACT order the park (`ef0fa0`), `f3ecd4` clear, and the beat
   handler run within one INTTR4 tick, and whether MAME's interrupt-servicing timing shifts it.
3. **KN7000 comparison** (its demo plays through measures) — different CPU, but the run→sync→park→
   re-arm concept is shared; see how it avoids the deadlock.

## UPDATE 12 — timer/ISR-timing analysis: architecture + the demo-specific re-arm skip

Started the timing/ISR analysis. Findings:
- **Tick/beat processing is MAIN-LOOP driven, not interrupt-driven.** The tick sequence `f4e635`
  (which contains `f3ecd4`, `f43ca9`, and reaches the beat/sync handlers) is called from a
  free-running main event loop at `ef1245..ef1385` (`ef1372: call f4e635`; `ef1385: jrl ef1245`).
  INTTR4 (`ef0e21`) independently increments the beat clock `0x417`. So the two are decoupled and
  their relative rate matters — but see below, the decisive block is firmware-logical, not a rate.
- **★ The per-measure re-arm is DEMO-DISABLED.** The beat dispatcher `f5ae1c` (its `f5ae77`→`f5af5f`
  →`f5af8f` path is the only per-measure re-arm) has EXACTLY ONE caller: `f59ca3`, inside the
  transport-service function `f59c70`. That function RETURNS EARLY when `f59ca9` returns 1, and
  `f59ca9` returns 1 for **`0x8d34==0x13` (demo state)**. So **in the demo, `f5ae1c` is never called
  → the per-measure re-arm never runs** (confirms `f5af8f` never fired). Normal playback
  (`0x8d34!=0x13`) reaches `f5ae1c` and re-arms every measure.
- **The sync that kills it is dispatched by the sequencer engine.** The flip stack shows
  `f5adca`←`f59ab9`(trampoline: call f5adca)←`f568ba`←…←`f53347`←the main-loop tick. So the sequencer
  engine, during playback, calls the sync trampoline `f59ab9` → `f5adca` → `f5afb2` (0x420/0x421 =
  0x0C) at the measure boundary.

**Net:** in the demo the transport is **synced by the sequencer** at the measure boundary but the
**per-measure re-arm is firmware-disabled** (`0x8d34==0x13`), and the only other re-arm is the
once-per-song demo-timer path (`0xD2F` → `f43cf8`), which requires `0xD2F` to reload/cycle (it
froze at 0). So the demo transport has **no recovery** from the measure-sync. Two possibilities
remain, same as before but now precisely grounded:
1. **The sequencer should NOT sync (or the sync should be harmless) in the demo** — i.e. the demo
   song is meant to play as one continuous run and the measure-sync (`f59ab9`→`f5adca`) is the
   anomaly. Find what makes the sequencer post it and whether that's timing/state-driven.
2. **The demo is meant to CYCLE via `0xD2F`** and the reload (`f86d86`, callers `f86bc7`/`f86cb6`)
   is gated on the song completing, which never happens because #1 kills it first.

Both are demo-conditional firmware behaviors (`0x8d34==0x13`), so they apply on HW too — meaning the
emulation must be feeding the demo path a wrong INPUT (a timing, a state byte, or a sub-CPU/tone-gen
signal) that makes the sequencer sync-and-die instead of playing through. Distinguishing this
cleanly now genuinely needs the **KN7000 comparison** or Felipe's description of the real demo
(one continuous song vs. cycling short clips).

## UPDATE 13 — cycle hypothesis REFUTED; KN5000-alone avenues exhausted

Forced `0xD2F` to reload whenever it hit 0 (simulating "song complete → next"). Result: the demo
timer cycles (reloads 1→8), but **`entry(0x28a4)` stays 18** — the FEATURE PRESENTATION is LOCKED to
demo song 18 (`f86b74: ld (0x1158),0x12`), it does NOT cycle songs — and **`0x251D8` stays 0** (the
slideshow never advances). So the demo-cycle path is not the fix either.

**Every hypothesis is now experimentally refuted:** timer (already fixed), sync-park recovery
(force 0x06/0x04, arm 0x41E, keep 0xf19e — all die), and demo-cycle (force 0xD2F reload — song
locked, slideshow frozen). And crucially, in NO experiment does `0x251D8` (the SSF slideshow latch)
advance — not with a forced-running clock, not with a forced cycle. So the slideshow advancement is
gated by something none of these reach.

**Honest state:** the direct KN5000 trace+poke avenue is EXHAUSTED. The bug is genuinely multi-layer
(the transport dies at the first measure with no demo re-arm; AND the SSF slideshow latch never
advances even when the clock is forced). Resolving it requires a NEW reference:
1. **KN7000 comparison** — its demo plays continuously through measures AND advances its slideshow
   ("slideshow pacing = song position", commit 60d5392). Trace how the KN7000 demo drives both the
   sequencer survival and the slideshow, and map the concept back. This is now the primary path.
2. **Felipe's hardware observation** — precisely: on the real KN5000 Feature Presentation, does the
   globe (FTBMP01) advance to the next pictures (subwoofers, discs…) automatically, and is there a
   continuous backing song or short clips? That disambiguates the intended slideshow model.

⚠ Do not spawn more KN5000 force-pokes — they are exhausted and all fail.

## UPDATE 14 — Felipe: LONG song, slides advance ⇒ transport must sustain; sync trigger found

Felipe (hardware): the real Feature Presentation plays ONE LONG continuous song and the picture
slides advance autonomously over it. So the transport MUST sustain many measures — the emulation
dying after ~one beat (0x417: 0→24) is the bug, and (since the slideshow is song-paced) fixing the
transport fixes the slides.

**The sync trigger (runtime + disasm).** The sequencer counts events in `0x32ed` (`f568a8: inc
0x32ed`) and dispatches the measure SYNC only when **`0x32ed == 0x20` (32)**: `f568b6: call f59ab9`
→ `f5adca` → `f5afb2` sets `0x420/0x421 = 0x0C`. INTTR4 (`ef0fa0`) then parks `0x0C→0x10`, and
`f3ecd4` clears `0x10→0x00`. `0x32ed` is NOT reset at `f568b6`, so the sync fires once and the dead
transport freezes everything (`0x417` stops → no more events → `0x32ed` stuck at 32).

**The continuation is BACK-TO-BACK with the sync (so it's LOGIC, not a timing race).** Immediately
after the sync, the SAME main-loop iteration runs `f568ba: call f5e931` (→ `f5ce20`, `f5f444`) and
sets markers `0x32f5=0xFF`, `0x32f4 |= 0x21`. So the measure-continuation runs right after the sync
— there is no window/race. If the transport isn't re-armed/continued, it's because that
continuation's LOGIC doesn't do it in the demo, not because of CPU-cycle/timer timing.

**Emulation timing model (checked, likely NOT the bug):** TLCS-900 is per-instruction timed
(`tlcs900.cpp:314 m_cycles += inst->cycles`; timers advance by `m_cycles`); maincpu = 16 MHz
(`2*8_MHz_XTAL`). Per-instruction cycle counts are real (not a fixed constant), and since sync+
continuation are adjacent, the CPU-cycle-to-timer ratio is not the deciding factor. Timing angle
de-prioritised.

**⇒ The fix is in the measure-CONTINUATION path** `f5e931 → f5ce20 / f5f444` (+ the markers
`0x32f4`/`0x32f5`/`0x34cd`/`0x34d1`): it must re-arm/continue the transport for the next measure of
the long song, and in the demo it doesn't. A fully-briefed disassembly pass is tracing exactly
which continuation step should re-arm and the emulated condition that makes it fail (to be verified
at runtime). This is the live lead.

## UPDATE 15 — subagent's "f86fb7==0 / 0x2314==0" claim REFUTED at runtime

Verified the re-arm cell `0x2314` directly. Result: **`0x2314 = 0xFFFF` (non-zero) the ENTIRE run**
(and `*(0x6981e) = 0xFFFF`, so `f86fb7` returns valid data — the presentation data IS loaded). So
the subagent's prediction (`f86fb7==0 → 0x2314==0 → no re-arm`) is WRONG. The re-arm GATE
(`f3a0b3: ld WA,(0x2314); jr Z`) PASSES, and **AccPlayMode reaches state 3** (`0x22FC=3`, correct
for playing). Yet `0x420` stays `0x00` (clock dead). So: gate passed + engine "playing" + clock
still not sustained ⇒ the block is DOWNSTREAM of both the `0x2314` gate and AccPlayMode.

New anomaly: **`0x32ed` is already `0x20` (32) BEFORE playback starts** (t=25.0, `0x420=00`) — the
sync threshold is pre-tripped, not counted up during the measure. So the sync (`f568b6`, fires at
`0x32ed==0x20`) trips immediately when the sequencer runs, rather than after a real measure of
events. Who sets/leaves `0x32ed=32` (vs the reset `f5675b: ld (0x32ed),0x00`) is a new open thread.

**Every hypothesis is now refuted at runtime** (timer, sync-park recovery, arm-0x41E, keep-0xf19e,
force-0xD2F-cycle, and the f86fb7/0x2314 continuation). The demo reaches AccPlayMode=3 with a valid
next-segment pointer, yet the transport clock is never sustained and `0x251D8` never advances.

## UPDATE 16 — 0x32ed is a red herring; sync arrives as a QUEUED command

Tapped `0x32ed` writes: **none during playback** (t=23–30). So `f568a8` (which `inc`s `0x32ed` and
whose `f568b6` calls the sync trampoline `f59ab9`) is NOT called during playback — it is not the
sync source, and `0x32ed`'s pre-set 32 is irrelevant. The flip-stack frames (`f568ba`/`f56834`/…)
are the sequencer→command-QUEUE dispatch chain; the sync (`f59ab9→f5adca→f5afb2`) is reached via a
COMPUTED jump from the command dispatcher, i.e. a **queued transport command**, not a direct call.
So the true producer is whatever POSTS that sync command to the queue during demo playback — a layer
I did not reach.

## ★★★ UPDATE 17 — UPDATE 16 WAS A TAP ARTIFACT. 0x32ed IS THE ROOT: A RUNAWAY EVENT READER ★★★

**Retraction.** Update 16 ("0x32ed is a red herring, not written during playback") was WRONG — a
MEASUREMENT ARTIFACT. The tap was installed as `install_write_tap(0x32ed, 0x32ed, ...)`: an ODD,
SINGLE-BYTE, NON-WORD-ALIGNED range on a 16-bit space, so it never fired. Re-installed correctly as
`(0x32ec, 0x32ed)` (word-aligned pair, `0x32ed` = the HIGH byte lane, so test `mask & 0xFF00` and
read `data >> 8`) it fires immediately — **150 captures vs 0**. The stack dump had said so all
along: `00F568BA` is the return address of `f568b6: call 0xf59ab9`.
★ RULE: on this 16-bit space, taps MUST be word-aligned pairs, and you must select the correct
byte lane. An odd single-byte tap silently never fires and looks like "never written".

**THE ROOT CAUSE (measured):** `0x32ed` is a **RUNAWAY / EVENT-BUDGET WATCHDOG**, and it is
tripping constantly. Captured during playback:
```
t=25.85953  32ed<-00  PC=F56765   <- pattern restart (f5675b); 0x33d4 0x20 -> 0x01
t=25.85955  32ed<-01  PC=F568AF
   ... 32 increments in 0.00082 s (~25 us apart), 0x417 == 0 THROUGHOUT ...
t=25.86037  32ed<-20  PC=F568AF   <- hits 0x20 -> f568b6 SYNC -> transport parked/stopped
t=25.92835  32ed<-00  PC=F56765   <- restart, and the whole 32-burst REPEATS (~68 ms period)
```
So the sequencer **consumes 32 events back-to-back with NO time advance**, trips the guard at 32,
and the guard's action (`f568b6: call f59ab9` -> `f5adca` -> `f5afb2`, lanes := 0x0C) is what parks
and kills the transport. This repeats every ~68 ms. When the transport finally arms and runs
(t≈26.2), the very next burst's guard trip (t≈26.29) kills it — which is the "dies after one beat"
symptom. **The transport machinery was never the bug; it is collateral damage from a runaway
event reader.**

`0x33d4` is the track/part selector bitmask (values 1,2,4,8,0x10,0x20 = 6 tracks, dispatched at
f56837+); `f5675b` restarts the pattern (resets `0x32ed`, sets `0x33d4=0x01`, reloads the read
pointers). Each burst = one full restart-and-runaway cycle.

**⇒ The real question is now narrow and concrete:** why does the event reader consume 32 events
with no time advance? Two sub-cases, being measured: (a) the pattern READ POINTER does not advance
(the same event is re-read forever) = a decode/pointer defect; or (b) the pointer does advance
through 32 genuine zero-delta events = the song's event stream is misdecoded/wrong data. Either
way this is an **event-stream decode** problem, NOT a transport/timer problem.

## ★★★ UPDATE 18 — CONFIRMED ROOT CAUSE: the song EVENT BUFFER is never loaded (all zeros) ★★★

Measured the buffer the runaway reader walks:
```
bases: 3287=675A  3297=0000  32A3=2323  32AB=0000  32B5=0000  33EB=0000
ptr   33D8 = 0x677A, advancing +1 per "event" from base 0x675A
@0x6740 .. @0x67C0 : 00 00 00 00 ... ALL ZEROS
@0x69800           : 5A 5A 5A 5A 01 01 08 00 ...  <- the song HEADER/setup IS loaded
```
**The demo song's NOTE-EVENT STREAM is never loaded into the sequencer event buffer (~0x675A).**
The reader walks a zero-filled buffer, consumes each null byte as a zero-delta event, hits 32 of
them in ~0.8 ms, trips the `0x32ed` runaway guard, and the guard's action (`f568b6` -> sync ->
park -> stop) kills the transport. It repeats every ~68 ms forever. Also most per-track bases
(`0x3297`, `0x32AB`, `0x32B5`, `0x33EB`) are **0x0000** — the per-track event pointers were never
bound either. Only track 1's base (0x675A) is set, pointing into the empty buffer.

**This explains EVERYTHING consistently:** no music (no events), transport dies (guard trip),
slideshow frozen (`0x251D8`=0 — the SSF slides ride on SSF SysEx events *in the song stream*, so
with no events there are no slides), AccPlayMode sits at 3 (it is "playing" an empty stream), and
every transport-level poke failed (they treated the symptom; the guard re-trips within ~68 ms).

**⇒ THE FIX TARGET: the demo song LOADER.** The demo main-op calls the song loader at
`0xD2F == 10`: `f86c06: ld A,(0x28a4)` (song index 18) `; f86c0c: calr 0xf87189`. Determine what
`f87189` does, whether it runs, and why the event stream does not reach ~0x675A / the per-track
bases. (Sibling reference: on the KN7000 the demo songs are **zlib blobs inflated into RAM** — 10
setup blobs + 10 SEQUENCE blobs + 10 sound blobs; see notes/demo-and-sequencer-engine.md. The
KN5000 equivalent is presumably an LZSS/compressed blob in table_data ROM that must be decompressed
into the event buffer.) The KN5000 song data source is the "ZZZZ" record at 0x69800 (loaded) plus
the pointer table at `0x9C4000[songidx]` (entry 18 = 0x8E0000).

## ★★★ UPDATE 19 — the loader is the SLIDESHOW loader; the SONG is gated behind 0x8d38 != 0xE4 ★★★

**What `f87189` actually loads (decoded end-to-end):**
```
f87189: XWA = *(0x9C4000 + songidx*4)      ; songidx 18 -> 0x008E0000
        or XWA,XWA ; ret Z                  ; bail if null
        XBC = 0x00069800                    ; destination
        call 0xef41e3                       ; format dispatcher
ef41e3: memcmp(src, template@0xE00032, 5)   ; template bytes = "SLIDE"
        mismatch -> return 0xFFFF (loads NOTHING)
        match -> A = src[5]:  '4'(0x34) -> decompressor ef3fab ; '8'(0x38) -> ef40c5 ;
                              anything else -> loads NOTHING
```
ROM at CPU `0x8E0000` (= table_data region offset 0x0E0000, map `0x800000-0x9FFFFF`) reads:
`53 4C 49 44 45 34 4B 00 ...` = **"SLIDE4K"**. So the blob is the **SLIDESHOW / presentation**
data, format '4', and it **decompresses correctly** into `0x69800` (verified: output matches the
compressed stream sensibly — "ZZZZ" header, part-type array, 16 `80 xx 00` records at 0x698C8,
`5F` filler, then zeros). **The slideshow data is fine and IS loaded. `f87189` is NOT the song
loader.**

**★ The song is gated behind the UI sub-state.** The demo's start-playback step (demo timer
`0xD2F == 3` -> `f86d3d`):
```
f86d3d: cp (0x8d34),0x13 ; ret NZ       ; demo mode
f86d4c: ld (0x1157),(0x28a4)            ; target song := current entry
f86d52: cp (0x8d38),0xe4                ; UI sub-state == FEATURE PRESENTATION submenu?
f86d57: ret Z                           ; ★ YES -> RETURN, song never started ★
f86d59: call 0xf22a37                   ; (the actual "start playback")
```
Runtime: `0x8d38` is **stuck at 0xE4 forever**, so `f22a37` is NEVER called. Many other demo
branches are likewise gated on `0x8d38 != 0xE4` (f86b62, f86b9d, f86bcf, f86c46). Forcing
`0x8d38 := 0xE1` is NOT a valid test (it flips those other branches too; AccPlayMode fell 3->1 and
the buffer still never filled) — so the song is **not** meant to be started by the demo-timer path
while in the presentation submenu.

**⇒ REFRAME (important): the SSF PRESENTATION ENGINE NEVER STARTS.** `0x251D8` (presentation-active
latch) is 0 the whole time. Therefore the Technics-globe image on screen is almost certainly the
**static FEATURE PRESENTATION submenu image, NOT a running presentation**. In the real machine the
presentation engine runs the SSF script, and the SSF vocabulary includes a **`SONG` tag** ("play a
song / MIDI sequence") with a dedicated event `EV_READSONG` — i.e. **the SCRIPT starts the song**.
So: presentation never starts -> no SONG directive -> song never loaded -> event buffer stays zero
-> runaway guard trips -> transport dies. One root, everything downstream.

This puts the March-2026 "the SSF presentation never starts / needs a 0xB80A block at
`AcPresentCtrl_CheckSSFStart 0xF84625`" theme BACK IN PLAY — but now with the whole downstream
chain understood and measured, and with the knowledge that the slideshow DATA is present and
correctly decompressed. (My earlier "the demo does start, March is stale" claim was based on the
globe being on screen; that inference was wrong if the globe is the menu image.)

**NEXT (in progress):** per the docs, in state `0xE4` the SSF gate table entry is the unconditional
marker `0xFFFE`, so ANY key press in `0xE4` should broadcast event `0x1C00038` ->
`GroupBoxProc_StartSSFPresentation (0xF9A273)` -> 0xB80A workspace -> `f84625` -> presentation
starts. A soft-key sweep in state 0xE4 (LEFT 1-5, RIGHT 1-5) is running to find which key actually
starts it, watching `0x8d38`, `0x251D8` and writes to the event buffer `0x675A`.

## ★★★★ UPDATE 20 — ROOT CAUSE ESTABLISHED (measurement + independent multi-agent RE agree) ★★★★

A 11-agent workflow (5 independent analyses, each adversarially verified) landed on exactly the
same picture as the runtime measurements. Triangulated conclusions:

- **`0x32ed` is a CORRUPT-STREAM WATCHDOG.** It counts consecutive BYTES that the realtime
  pattern reader could not recognize as any event opcode, within one lane pass. Recognized events
  never touch it; the legitimate end-of-track is a *different* opcode. (Independent agent finding,
  adversarially verified — and it explains the measurement exactly: the buffer is zero-filled,
  `0x00` is not a valid opcode, so every byte is "unrecognized" and 32 of them trip the watchdog.)
- **The `0x0C` lane state is a quantized "STOP at the next beat boundary", and it is TERMINAL BY
  DESIGN.** Nothing in the firmware ever converts `0x0C` back to `0x06`; its designed successors
  are exactly what we measured: `0x10` (INTTR4 park at a multiple of 24) then `0x00` (main-loop
  `f3ecd4`). **So the transport death is CORRECT firmware behaviour** — the watchdog detected a
  corrupt stream and deliberately stopped playback.
- **The KN7000 has NO measure-boundary re-arm at all** — it starts the transport once (engine
  command 0x8002 latches a RUN bit) and runs until an explicit stop. So the entire "per-measure
  re-arm" line of enquiry was chasing a mechanism that does not exist; the transport is simply
  supposed to keep running.

### THE ROOT CAUSE (single chain, every link measured)
```
SSF presentation engine never starts        (0x251D8 == 0 always)
  -> the SSF script's SONG directive never runs
    -> the song event stream is never loaded (event buffer @0x675A: ALL ZEROS, never written -
       verified: exactly ONE write ever, a boot-time clear at PC EF0B9B)
      -> the pattern reader walks zeros; every 0x00 is an unrecognized opcode
        -> 32 unrecognized bytes in ~0.8 ms trip the corrupt-stream watchdog (0x32ed == 0x20)
          -> watchdog issues the quantized STOP (f568b6 -> f59ab9 -> f5adca -> f5afb2: lanes=0x0C)
            -> INTTR4 parks 0x0C->0x10, f3ecd4 clears 0x10->0x00: transport DEAD (by design)
              -> no music; and since SSF slides ride on SysEx events IN the song stream,
                 no slides either. Repeats every ~68 ms forever.
```
**Everything downstream of the first line is the firmware behaving CORRECTLY.** The one and only
defect is that **the SSF presentation never starts.**

### Why it never starts (measured)
In state `0x8d38 == 0xE4` (FEATURE PRESENTATION submenu) a soft-key sweep of **all ten** soft keys
(LEFT 1-5, RIGHT 1-5) produced: `0x251D8` stays 0, event buffer never written, `0x8d38` never
leaves 0xE4. Yet the presses ARE delivered (LEFT 2 demonstrably starts the demo timer). So key
presses reach the firmware but **the SSF-start event chain never fires**:
`key in 0xE4 -> event 0x1C00038 -> GroupBoxProc_StartSSFPresentation (0xF9A273) -> 0xB80A workspace
-> AcPresentCtrl_CheckSSFStart (0xF84625) -> presentation starts (0x251D8 := 1)`.

★ **This REINSTATES the March-2026 finding that I earlier declared "stale".** March was RIGHT that
the SSF presentation never starts and that the `0x1C00038` / `0xB80A` chain is the blocker; what was
stale/wrong was only its *explanation* (the "automated demo path builds a 0x82xx tag" story) and my
own counter-claim that "the demo does start" (I inferred that from the Technics-globe image, which
is the STATIC submenu image, not a running presentation). Correct attribution: **March's target was
right, its mechanism was wrong, and my dismissal of it was wrong.**

### THE FIX TARGET (now unambiguous)
Make the SSF presentation actually start: the `0x1C00038` UI-event chain in state `0xE4`. Per the
docs the gate-table entry for `0xE4` is the unconditional marker `0xFFFE`, so ANY key press there
should broadcast `0x1C00038` via `UIState_KeyScan_Dispatch (0xF98697)` -> `FA9945`. Determine why
that broadcast does not happen for a delivered key press. Prime suspect: the KN5000 control-panel /
UI event-delivery path (note the KN5000 has a KNOWN, documented control-panel serial defect family
— see `notes/kn5000-cpserial-INDEX.md`, where the residue was characterised as **LOSS**, not
misframe). If some presses are delivered to the menu logic but never reach the widget handler
chain that runs `UIState_KeyScan_Dispatch`, that is exactly the observed signature.

## ★★★★ UPDATE 21 — FELIPE CORRECTION: the globe IS slide 1; the presentation DOES start ★★★★

**Felipe (hardware owner, GROUND TRUTH):** *"On a real KN5000 the static submenu does not show any
globe image. That globe is only shown when the DEMO starts playing. The globe is the first slide of
the demo."*

⇒ **RETRACT Update 20's framing "the SSF presentation never starts".** The presentation DOES start
and correctly renders slide 1. Therefore **`0x251D8` is NOT the presentation-active latch** that a
static-analysis pass claimed it was (that identification was never verified — and static analysis
has now been wrong on this investigation four times). Do not treat `0x251D8 == 0` as evidence of
anything. The March-2026 `0x1C00038`/`0xB80A` chain is NOT the blocker either.

**Corrected picture:** the demo starts → shows slide 1 (correct) → then freezes because **the SONG
never plays**, and the slides are song-paced. Everything about the watchdog chain from Update 20
still stands (it is measured), but its FIRST link changes:

```
the SONG is never loaded  (NOT "the presentation never starts")
 -> song event buffer @0x675A stays all zeros
  -> reader sees unrecognised opcode bytes -> 32 of them trip the corrupt-stream watchdog (0x32ed)
   -> watchdog issues the quantized STOP (lanes := 0x0C, terminal by design) -> park -> stop
    -> no music; slides never advance past slide 1 (they are paced by song position)
```

### ROM STRUCTURE (decoded from the dumps — new, solid)
- **"SLIDE" is the SLIDING-WINDOW (LZSS) COMPRESSION MAGIC, not "slideshow".** Variants
  `SLIDE4K` (4 KB window) and `SLIDE8K` (8 KB). 26 blobs in table_data. `ef41e3` memcmps the 5-byte
  magic (template at `0xE00032`) and dispatches on the window char: `'4'` -> `ef3fab`,
  `'8'` -> `ef40c5`, anything else -> loads nothing.
- **The decompressor WORKS.** Hand-decoded the entry-18 stream against the emulated output:
  `5A EE F0` -> `ZZZZ`; `E0 FB` -> 14 zero bytes; `FF` flag byte -> 8 literals
  (`01 2E 00 20 05 00 00 FF`), all matching RAM exactly. Flag-byte LZSS, decompressing correctly.
- **Entry table at CPU `0x9C4000` = 19 entries + null terminator:**
  `[0]..[17]` -> blobs at `0x9C4050, 0x9C9018, 0x9CE17C, 0x9D16F2, 0x9D645C, 0x9DA016, 0x9DE072,
  0x9E0CE2, 0x9E2358, 0x9E61C2, 0x9E72E8, 0x9EA1F2, 0x9EDFFC, 0x9EEC62, 0x9F0E72, 0x9F1C70,
  0x9F3B52, 0x9F494E` (all `SLIDE4K`), and **`[18]` -> `0x8E0000`** (`SLIDE4K`), `[19]` = 0.
  ⇒ `[0]..[17]` are the **18 demo SONGS**; **`[18]` is the FEATURE PRESENTATION descriptor**.
- Entry 18 decompresses to only ~0x110 bytes: a "ZZZZ" header, a part-type array, then **16
  `80 xx 00` script records** at `0x698C8` (`xx` = 32,2E,20,42,4C,53,55,5A,5D,62,64,16,6A,6D,70,25)
  and 16 `0x5F` bytes at `0x69900`. That is a **presentation SCRIPT**, not a song.
- Six **`SLIDE8K`** blobs at `0x983B3A, 0x988690, 0x98BB3A, 0x98F0DA, 0x992A0C, 0x9963FA` — larger
  payloads, not referenced by the 19-entry table; candidates for the presentation's own song/asset
  data. **Worth identifying next.**

**⇒ NEW FIX TARGET:** the presentation script runs (slide 1 shows) but **never causes a song to be
loaded**. Find the script opcode/step that should load+start a song (the SSF `SONG` directive) and
why it does not fire — i.e. which entry (`[0]..[17]`, or one of the six 8K blobs) the presentation
should pull in, and what consumes the `80 xx 00` records. Runtime check in flight: count how many
blob loads into `0x69800` occur during the demo (prediction: exactly ONE — entry 18 — proving no
song is ever loaded).

## ★★★★★ UPDATE 22 — BANKED-CELL READER + THE DISCRIMINATING TRAP (IC19 ruled out) ★★★★★

An 11-agent workflow (5 analyses, ALL surviving adversarial verification) supplied the mechanism I
was missing, and a runtime trap then discriminated its three candidates.

**The reader uses a BANKED CELL system** (so my earlier "event buffer @0x675A is all zeros" reading
was of the WRONG address — retract that specific inference; the conclusion "data supply is broken"
survives):
```
cell# = (0x33D6), offset = (0x33D8)
physical = bank[cell>>12] + (cell & 0xFFF)*256      ; resolver f59069, bank table f59089
bank[0..7] = 0x095C00 (DRAM pool),
             0x301400 0x31AC00 0x331400 0x34AC00 0x361400 0x37AC00 0x391400  (IC19 custom_data)
```
Event grammar recognised by the reader: `0x81` beat, `0x83` end-of-track, `0x87` cell-link,
`0x90`/`0x91` events, `0xD1..0xD5`. Anything else falls into `f568a8`, which skips ONE byte and
increments the watchdog `0x32ed`; 32 of those in one pass -> `f568b6` -> the quantized stop.

**TRAP RESULT (at the trip):**
```
cell=0000  off=675B  region=0  bank=095C00  phys=095C00      32E5=48 3285=1A 3277=00000000
@phys     : 80 FF FF 96 00 87 90 00 24 70 08 00 90 00 3A 6C 08 00 90 19 3A 3E 06 00 90 30 ...
@phys+off : 00 91 45 40 44 0D 00 00 11 D3 4B 00 81 83 00 00 00 00 00 00 00 00 00 00 00 ...
                                                ^^^^^ end-of-track, then ALL ZEROS
```
1. **region == 0 -> the DRAM pool, NOT IC19.** ⇒ the workflow's rank-1 candidate (custom_data mapped
   read-only / donor-dump content) is **RULED OUT** for this failure.
2. **The song data IS present and valid** at `0x95C00`: real pattern bytes full of `0x90` note
   events and an `0x87` cell link. Loading and LZSS decompression work.
3. **The reader has walked off the end of the populated data**: at offset `0x675B` only a short tail
   remains (`… 81 83`) followed by nothing but zeros -> 32 unrecognised bytes -> watchdog -> stop.
   (Corroborating: several per-track base cells read `0x0000` — `0x3297`, `0x32AB`, `0x32B5`,
   `0x33EB`.)

⇒ **The surviving candidate is the workflow's (c): the CELL CHAIN walks into an unpopulated cell**
(either a `0x87` link pointing at a cell that was never filled, or a start-cell/section record that
points past the loaded extent). The data that IS there is fine; the chain leaves it.

**NEXT (single, concrete — the workflow's own rank-3 probe):** tap **PC `0xF585A7`** and log `HL`
(the link word) on every `0x87` follow from demo start until the trip, reconstruct the full cell
chain, and find the first link that leaves populated data. Then fix whichever end is wrong (the link
value, or the loader that should have populated that cell). Provenance chain for the start cell:
`(0xFC5A)/(0xFC5B)` -> `0x32F5/0x32F7` -> `0x32E5-0x32E8`, section record
`XIY = regionBase_f53d57[region] + styleDir_0xE46312[style] + 0x60`, start cell = word at `(XIY+0)`
(setup `f58843`/`f5886f`/`f58873`; link follow `f585a7`/`f585ac`; resolvers `f58ff9`/`f59059`).

## ★★★★★ UPDATE 23 — THE READER IS UNPACED: it races the whole song in <1 ms ★★★★★

Link-chain probe (write tap on the cell number `0x33D6`, word-aligned):

- **The cell number NEVER advances — it is `0x0000` on every write**, rewritten constantly from
  `PC=F56A20` (and `F56773` at pattern restart), lane `0x33d4`=01 throughout. So there is **no cell
  chain traversal at all**; the workflow's candidate (c) "a link points at an unpopulated cell" is
  therefore **NOT** what happens — the reader never follows a link.
- The **offset** (`0x33D8`) instead walks ~26 KB forward inside cell 0's pool: real pattern data all
  the way to ≈`0x9C368`, where the stream ends with `… 81 83` (beat, end-of-track) and is followed
  by zeros.
- **★ The decisive detail: the whole 26 KB traversal happens between t≈25.337 and t≈25.86 — under
  ONE MILLISECOND of emulated time — and it finishes BEFORE the transport even arms (≈26.2 s).**

⇒ **NEW LEADING HYPOTHESIS (fits every observation): the pattern reader is NOT BEING PACED by the
beat/clock.** Normally the reader consumes only the events due at the current beat and blocks on the
`0x81` beat marker; here it consumes the ENTIRE song instantly, runs off the end of the data into
the zero fill, and 32 unrecognised bytes trip the corrupt-stream watchdog — which then issues the
quantized stop that kills the transport as soon as it does arm. The song is destroyed before it ever
gets a chance to play.

This finally explains, coherently, why EVERY transport-level intervention failed: by the time the
transport is armed the reader has already blown past the end of the song, so forcing lane values
(`0x06`/`0x04`/arm `0x41E`/`0xf19e`/`0xD2F`) can never help — the watchdog re-trips within ~68 ms
because the reader keeps racing the (already exhausted) stream.

**NEXT:** find the reader's pacing gate — the `0x81` beat-marker handler and whatever "is this event
due yet?" comparison it makes against the beat/tick counters (`0x417`/`0x41B`/`0x41C`, master tick
`0x0460`). Determine why that comparison always says "due" while the transport is stopped and the
beat clock is frozen at 0. Prime suspects: (i) the due-test compares against a counter that is 0 on
both sides (0 >= 0 always true) so everything is "due"; (ii) the pump (`ef13a5` -> `f532e1`/`f53318`
-> `f5804f` -> `f56751`) should not run at all while the transport is stopped, and its run-gate is
mis-evaluated. Probe idea: tap the beat/tick cells and log the reader's due-comparison inputs at the
first few event consumptions (t≈25.33), i.e. BEFORE the transport arms.

## ★★★★★★ UPDATE 24 — THE READ-POINTER BASES ARE NEVER REWOUND TO THE PATTERN START ★★★★★★

**The pacing gate (decoded):**
```
f567cd loop: bit 0,(0x32f4) -> set = stop reading           ; the pause flag
f567f0: A = (XHL+IY)   [XHL = resolve(cell 0x33d6), IY = offset 0x33d8]
        0x83 -> f56a25 end-of-track   0x81 -> f568ee BEAT   0x90/91/D1..D5 -> f568c9 event
        else -> f568a8 (skip 1 byte, watchdog 0x32ed++)
f568ee (BEAT): A = f570bb(reader bar 0x33da/beat 0x33db vs PLAYBACK bar 0x32b4/tick 0x327d)
        cp A,0x18 (24) ; ULE -> advance beat, set (0x32f4) bit1, KEEP READING
                        ; else -> or (0x32f4),0x01 = PAUSE  (read-ahead window = 24)
f570bb: returns (reader position - playback position), 0 if not ahead, capped 0x60
```

**Measured at runtime (word-aligned tap on 0x33DA-0x33DB):**
```
READER bar(0x33da)=00 beat(0x33db)=00   <- NEVER advance
PLAYBACK bar(0x32b4)=00 tick(0x327d)=0  <- never advance
gate (0x32f4)=00                        <- NEVER set
writes to 0x33da/0x33db come only from PC=F56783/F5678B = the pattern RESTART (f5675b)
```
⇒ **`f568ee` is NEVER CALLED**: the reader meets **no `0x81` beat marker** in the entire 26 KB it
consumes. With no beat marker there is nothing to pause it, so it races the whole song and falls off
the end. The pacing gate itself is fine — it never gets the chance to run.

**★ ROOT CAUSE: the persistent read-pointer BASES point at the END of the pattern data, not its
start.** `f5675b` ("restart pattern") reloads the live pointers `0x33D6/0x33D8/0x33DA/0x33DB/
0x33D5/0x33EA` **from** the bases `0x3287/0x3297/0x32B5/0x32AB/0x32A3/0x33EB`. Measured bases:
```
0x3287 = 0x675A   0x3297 = 0x0000   0x32A3 = 0x2323
0x32AB = 0x0000   0x32B5 = 0x0000   0x33EB = 0x0000
```
The pattern data occupies offsets `0x0000..0x6768` in cell 0 of the DRAM pool
(phys `0x95C00..0x9C368`, starting `80 FF FF 96 00 87 90 …` and ending `… 81 83`).
**Base `0x675A` is 14 bytes before the END of that data** — a stale end-of-song position — and the
other lanes' bases are `0x0000`/garbage. So every "pattern restart" rewinds to the END: the reader
consumes the last few bytes, walks into the zero fill, accumulates 32 unrecognised bytes and trips
the corrupt-stream watchdog, which issues the quantized stop that kills the transport. Loop repeats
every ~68 ms.

**⇒ THE DEFECT: whatever should initialise the per-lane read-pointer bases to the pattern START when
the demo song is engaged never runs (or writes the wrong value).** Everything else in the chain —
decompression, the pool contents, the resolver, the pacing gate, the watchdog, the transport — is
correct. Earlier base writes were captured at t≈18.83 (`PC=F55FFB`) and t≈19.03-19.07 (`PC=F567AC`),
i.e. all BEFORE the demo starts; nothing sets them during demo engage.

**NEXT:** tap the base cells (`0x3286-0x3287` etc., word-aligned) across the demo-engage moment and
find the writer that should set them to the pattern start; compare with what a normal
(non-demo) style engage does, since ordinary rhythm playback presumably rewinds correctly.

## ★★★★★★ UPDATE 25 — ⚠ THE DRIVER PERSISTS ALL 1 MB OF WORK DRAM AS NVRAM ⚠ ★★★★★★

Chasing "who sets the read-pointer base to 0x675A" led to a **separate, genuine emulation-fidelity
defect that contaminates RAM-based measurements project-wide**:

```cpp
// src/mame/matsushita/kn5000.cpp
map(0x000000, 0x0fffff).ram().share("nvram1");   // 1 Mbyte = 2 * 4Mbit DRAMs @ IC9, IC10 (CS3)
NVRAM(config, "nvram1", nvram_device::DEFAULT_ALL_0);
```
**The entire main work DRAM is saved to `nvram/kn5000/nvram1` and restored on the next run.** On real
hardware IC9/IC10 are ordinary **volatile DRAM**; only the SRAM at `0x1e0000-0x1fffff` (IC21, the
"back-up SRAM") is battery-backed (`nvram2`, which also has a factory-defaults init handler — that
one is legitimate). Proof from the saved file itself:
```
nvram1 @0x3287  : 5A 67          -> 0x675A   (the "stale end-of-song read pointer")
nvram1 @0x95C00 : 80 FF FF 96 00 87 90 ...   (the entire "pattern pool" I had been analysing)
```
and at t=0.047 s the boot RAM-clear tap reported `before 3287=675A` — i.e. the value was already
there **before the firmware ran a single relevant instruction**.

### ⚠ CONSEQUENCE — RETRACTION of Update 24
Update 24 concluded "the read-pointer bases point at the END of the pattern data". That conclusion
was drawn from **contaminated state**: both the base value `0x675A` and the pool contents at
`0x95C00` came from the *previous session's* leftover DRAM, not from anything this run did. The
observation was real but its provenance was wrong, so the inference does not stand. (Likewise the
"the song data IS present at 0x95C00" claim in Update 22 — that data was leftover.)

### The clean-DRAM control run
Deleted `nvram/kn5000/nvram1` (backed up first) and re-ran the demo from clean DRAM:
**the demo fails IDENTICALLY** — sub-ticks freeze at 0x18, no music, `0x251D8`=0, transport dead
(only `0x22FC` differs: 01 instead of 03). So **the persisted DRAM is NOT the demo's root cause** —
it is an independent defect. Both need fixing, separately.

### ★ Why this matters far beyond the demo
Every KN5000 investigation in this project that reads work RAM (0x000000-0x0FFFFF) may have been
reading state inherited from earlier sessions rather than state produced by the run under test.
That includes this whole investigation's RAM dumps, and potentially other KN5000 work (the
control-panel/cpserial analyses, boot-state studies, any "is this buffer populated?" question).
**Re-verify any RAM-provenance conclusion with `nvram1` deleted.**

**FIX (emulator-side, faithfulness):** stop persisting the volatile DRAM — make `0x000000-0x0FFFFF`
a plain `.ram()` region with no `share("nvram1")`/`NVRAM()` device, keeping `nvram2` (IC21 SRAM) as
the only battery-backed store. ⚠ Check first whether anything depends on the current behaviour: the
driver has comments about a "virgin NVRAM" growing a spurious `<Db>` and there is a
`nvram/kn5000_fresh_boot_error/` directory from an earlier session, so a fresh boot may surface the
known power-down-NMI defect. That interaction must be understood before shipping the change.

## ★★★★★★ UPDATE 26 — clean-DRAM re-baseline + the buffer is a PRODUCER/CONSUMER STREAM ★★★★★★

The DRAM-persistence defect is FIXED and shipped (`86aae9e`, see UPDATE 25), so everything below is
measured on honest cold-boot RAM.

**1. The earlier trap findings SURVIVE.** Re-run on clean DRAM reproduces byte-identically: same
`cell=0000 off=675B/677A`, same `phys=095C00`, same `@phys+off` bytes, same timing. The firmware
regenerates this state deterministically, so contamination did not change the failure.

**2. ✅ The pool is NOT dependent on the saved nvram — the firmware GENERATES it.** With volatile
DRAM the pattern pool at `0x95C00` is written during boot by code at **PC ≈ `0xF5CF95`** and matches
the old saved-nvram content **byte-for-byte** by t≈22 s. (The pool data appears in **no ROM**
verbatim — searched program/table/custom/rhythm/subcpu down to 8-byte prefixes — so it is
LZSS-decompressed/assembled at runtime. The nvram file was only a snapshot of that.)

**3. ★ The buffer is a continuously-refilled STREAM, not a static song image.** Write-extent probe:
```
extent = 0x095C00 .. 0x09FFFE  (≈42 KB)      writes = 12,091,392 in ~16 s
```
That is **235 full rewrites of the whole 42 KB buffer** in 16 s = one complete refill per ~68 ms —
exactly the pattern-restart period. The reader's address `0x9C35A` is INSIDE this buffer
(12,096 writes landed next to it).

**4. ★ The read pointer sits 14 bytes behind the END of the written data.** The refill writes real
pattern data from offset 0 to ≈`0x6768` (`… 81 83` = beat, end-of-track) and leaves the rest of the
42 KB as zeros; the read base is `0x675A` — i.e. **the consumer has all but caught up with the
producer.**

⇒ **NEW LEADING HYPOTHESIS: this is a PRODUCER/CONSUMER STREAM and the consumer overruns the
producer.** The refill (producer) streams pattern bytes into the buffer; the reader (consumer)
follows behind. When the consumer reaches the producer's write frontier it finds not-yet-written
ZEROS, treats them as unrecognised opcodes, and 32 of them trip the corrupt-stream watchdog — which
stops the transport. The producer's advance is presumably clock/transport-paced, so once the
watchdog stops the transport the producer cannot advance either: a **deadlock**, restarting every
~68 ms. This finally makes sense of the "reader races 26 KB in <1 ms" observation — it is not racing
a finished song, it is draining the buffer faster than the producer refills it.

**NEXT:** identify the producer (the refill writer, entry point near `PC 0xF5CF95` for the boot fill;
find the per-cycle refill) and the "data available" gate the consumer should honour — i.e. what
tells the reader "the producer has not written this far yet, wait" instead of consuming zeros.
Compare producer frontier vs consumer position over time (tap both, plot the gap).

## HONEST BOTTOM LINE (after 16 stages, ~23 runs, 4 disasm passes)

This is a genuinely intractable, deeply multi-layer demo-playback defect. I have COMPLETELY mapped
the mechanism and experimentally REFUTED every state-level and continuation-level fix. The remaining
question — why the transport clock (`0x420`) is not sustained even though the re-arm gate (`0x2314`)
passes and AccPlayMode reaches state 3 — sits below everything I've traced. It is very likely a
**decoded-song-data / sequencer-event-stream issue** (the `0x32ed=32` pre-trip suggests the event
stream isn't being consumed as a normal measure), which would be a fresh, large investigation into
the demo song's SEQUENCE data (the note-event blob and its decode), NOT the transport state machine.

Recommended: treat this as a documented deep issue. The two viable fresh angles are (a) the demo
SONG SEQUENCE data decode (why `0x32ed` starts at 32 / whether the event stream is misdecoded), and
(b) the KN7000 comparison. Both are multi-session efforts. All 15 stages are committed for whoever
picks this up.

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
