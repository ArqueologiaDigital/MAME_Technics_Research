# HANDOFF — KN5000 Feature Demo / Presentation playback (2026-08-05)

**Goal:** make the KN5000 "Feature Presentation" demo play like the KN7000's does (commit 60d5392
made the KN7000 demo play music + advance its slideshow). **Status: NOT fixed** — completely
diagnosed, every state/logic fix experimentally refuted; the one unreached layer is named below.
Full blow-by-blow: `notes/kn5000-demo-playback-stall.md` (16 stages). This file is the clean
pick-up point.

---

## 1. Ground truth (Felipe, hardware owner — outranks all inference)

On the real KN5000, the Feature Presentation plays **ONE LONG continuous song** and the picture
slides **advance autonomously over it** (no count-in, music starts immediately). So: the transport
MUST sustain many measures, and the slideshow is **song-paced** — fix the transport and the slides
follow.

## 2. Current emulated behaviour (Aug-2026 build)

Navigate **DEMO (`CPL_SEG3` 0x01) → LEFT 4 (`CPL_SEG9` 0x02) → LEFT 2 (`CPL_SEG10` 0x01)**. Then:
the demo activates, renders slide 1 (**FTBMP01, the Technics world-globe**), the transport starts
running for ~one beat, then **dies**; no music, slideshow frozen on slide 1. (This is already far
better than the March-2026 notes, which wrongly concluded "SSF never triggers / 0xB80A tag
mismatch" — that is STALE, do not chase it.)

## 3. The death mechanism (runtime-verified, exact)

```
demo timer 0xD2F == 1  → f86c1f sets 0x2966=0x85
  → per-tick f43ca9 arms transport (f43cf8: 0x420/0x421 = 0x01)   [once per song]
  → INTT1 ef0cac promotes 0x01 → 0x06 (RUNNING)                    ✓ matches HW
  … runs ~one beat (0x417: 0→24) …
  → a QUEUED transport SYNC command is dispatched (f59ab9 → f5adca → f5afb2 sets 0x420/0x421 = 0x0C)
  → INTTR4 handler ef0fa0 PARKS 0x0C → 0x10  (at 0x417 ∈ {0,24,48,72})
  → main-loop tick f3ecd4 (from f4e63f, res 4,(0x420)) clears 0x10 → 0x00  = STOP
  → 0x417 stops (it only increments while 0x420 bit2 set, gate ef0e70) → everything freezes
```

The transport is **designed** to cycle run→sync→park→stop→**re-arm** each measure. The per-measure
re-arm exists (`f5ae1c → f5ae77 → f5af5f → f5af8f: 0x420←0x01`) **but is DEMO-DISABLED**: its only
caller is `f59ca3` inside transport-service `f59c70`, which returns early because `f59ca9` returns 1
for **`0x8d34 == 0x13`** (the demo state). So in the demo the normal re-arm never runs; the demo is
supposed to continue via a demo-specific path — which is where it's broken.

## 4. ★ ROOT CAUSE — SOLVED (2026-08-05). Sections 3's "death" is the firmware behaving CORRECTLY.

Established by runtime measurement AND an independent 11-agent analysis that agreed on every point:

- **`0x32ed` is a CORRUPT-STREAM WATCHDOG** — it counts consecutive bytes the pattern reader could
  not recognise as any event opcode. Recognised events never touch it; end-of-track is a different
  opcode.
- **Lane value `0x0C` is a quantized "STOP at the next beat boundary", TERMINAL BY DESIGN.** Nothing
  ever converts `0x0C` back to running; `0x10` (park) then `0x00` (stop) are its intended
  successors. So the transport dying is the correct response to a corrupt stream.
- **The KN7000 has NO per-measure re-arm** — it starts the transport once and runs until an explicit
  stop. The whole "re-arm" line of enquiry (sections 3/5) chased a mechanism that does not exist.

**THE CHAIN (every link measured):**
```
SSF presentation engine never starts   (0x251D8 == 0 always)
 -> the SSF script's SONG directive never runs
  -> the song event stream is never loaded
     (event buffer @0x675A is ALL ZEROS; exactly ONE write ever = a boot-time clear at PC EF0B9B)
   -> the reader walks zeros; 0x00 is not a valid opcode -> every byte "unrecognised"
    -> 32 unrecognised bytes in ~0.8 ms trip the watchdog (0x32ed == 0x20)
     -> watchdog issues the quantized STOP (f568b6 -> f59ab9 -> f5adca -> f5afb2, lanes := 0x0C)
      -> INTTR4 parks 0x0C->0x10; f3ecd4 clears ->0x00. Transport dead. Repeats every ~68 ms.
       -> no music, and no slides (SSF slides ride on SysEx events INSIDE the song stream)
```
**Only the first line is a defect. Everything below it is correct firmware behaviour.**

**Why the presentation never starts (measured):** in state `0x8d38 == 0xE4` a sweep of ALL TEN soft
keys (LEFT 1-5, RIGHT 1-5) left `0x251D8 == 0`, the event buffer unwritten and `0x8d38` unchanged —
even though presses ARE delivered (LEFT 2 demonstrably starts the demo timer). So the chain
`key in 0xE4 -> event 0x1C00038 -> GroupBoxProc_StartSSFPresentation (0xF9A273) -> 0xB80A workspace
-> AcPresentCtrl_CheckSSFStart (0xF84625) -> 0x251D8 := 1` never fires.

★ This **REINSTATES the March-2026 target** (the `0x1C00038` / `0xB80A` chain). March's *mechanism*
("the automated path builds a 0x82xx tag") was wrong, and my own dismissal of March as "stale" was
ALSO wrong — I inferred "the demo starts" from the Technics-globe image, which is the STATIC
submenu image, not a running presentation. Correct attribution: right target, wrong mechanism.

**THE FIX TARGET:** make the SSF presentation start — i.e. find why a delivered key press in state
`0xE4` does not produce the `0x1C00038` broadcast via `UIState_KeyScan_Dispatch (0xF98697)` ->
`FA9945` (the gate-table entry for `0xE4` is the unconditional marker `0xFFFE`, so ANY key should
do it). Prime suspect: the KN5000 UI/control-panel event-delivery path — note the KN5000 has a
KNOWN control-panel serial defect family whose residue was characterised as **LOSS** (see
`notes/kn5000-cpserial-INDEX.md`). "Press reaches the menu logic but never reaches the widget
handler chain" is exactly the observed signature.

## 5. REFUTED — do NOT re-chase (all tested at runtime)

| Hypothesis | Result |
|---|---|
| Timer emulation bug | Already fixed; INTTR4 fires correctly, transport DOES arm+run |
| force `0x420=0x06` every frame | clock runs (0x41C advances) but demo doesn't play; breaks handshake |
| surgical `0x0C→0x06` once | firmware immediately STOPs it (0x00) |
| arm `0x41E` (simulate f86fff≠0) | 0x41E dies too; no effect |
| keep `0xf19e` non-zero (tap-return) | still dies — re-arm f5ae1c is demo-disabled regardless |
| force `0xD2F` cycle reload | song LOCKED to 18 (no cycling), 0x251D8 stays 0 |
| f86fff / 0x41E-lane theory | refuted (song data present; arming 0x41E doesn't help) |
| f86fb7 → 0x2314 "continuation" | refuted: `0x2314=0xFFFF`, AccPlayMode=3, clock STILL dead |
| 0x32ed "safety-sync" | refuted: `0x32ed` not written during playback (f568a8 not the source) |

In **no** experiment did `0x251D8` (slideshow latch) ever advance — consistent with it being
song-paced (needs the sustained transport).

## 6. Address / cell map (verified)

**CPU / interrupts**
- maincpu = **TMP94C241 @ 16 MHz** (`2*8_MHz_XTAL`), TLCS-900, little-endian.
- Active sequencer tick interrupt = **INTTR4**, handler **`0xEF0E21`** (NOT INTTR5 — `0xEF086A` is an
  empty `reti`; the March notes had this backwards). Runtime `INTET45=0x83` = INTTR4 pri 3 enabled,
  INTTR5 pri 0 disabled.
- Tick/beat PROCESSING is main-loop driven: loop `ef1245..ef1385` (`ef1372: call f4e635`), decoupled
  from INTTR4 which only increments the beat clock. (So it's not a CPU-cycle/timer race — the sync
  and its continuation `f568ba: call f5e931` are back-to-back in one iteration.)

**Transport state machine** (lanes `0x41E 0x41F 0x420 0x421`; values: 00=stop, 01=arm, 06/04=run,
0C=sync, 10=park)
- arm: `f43cf8` (via `f43ca9`, from `0xD2F==1 → 0x2966=0x85`); promote 01→06: INTT1 `ef0cac`.
- sync (→0C): `f5afb2` (via `f5adca` via trampoline `f59ab9`, **dispatched as a queued command**).
- park (0C→10): INTTR4 `ef0fa0` at `0x417∈{0,24,48,72}`.
- stop (10→00): `f3ecd4` `res 4,(0x420)` (main-loop tick, caller `f4e63f`).
- per-measure re-arm (DEMO-DISABLED): `f5ae1c→f5ae77→f5af5f→f5af8f`; caller `f59ca3` in `f59c70`
  skipped when `f59ca9`→1 for `0x8d34==0x13`.
- beat clock `0x417` increments only while `0x420` bit2 set (gate `ef0e70`).

**Demo / presentation**
- demo state `0x8d34==0x13`; `0x8d38` (0xE4 = Feature Presentation submenu; SSF screen id 0xEA).
- demo timer `0xD2F` (`f86bf3`: 10=load `f87189`, 3=start `f86d3d`, 1=arm); reload `f86d86` (=0x0F,
  callers `f86bc7`/`f86cb6`).
- song index `0x28a4` = **18**, LOCKED for the Feature Presentation (`f86b74`).
- demo re-arm gate `0x2314` (set by `f3ecd4→f3ed22→f3ed2a→f86fb7`; AccPlayMode init `f3a0b3`
  re-arms if ≠0). Runtime = **0xFFFF (passes)**.
- AccPlayMode `0x22fc` (reaches 3 = playing). Dispatch table `0xE444E2`.
- song data bank `0x69800` ("ZZZZ" magic + part-type array; `f86fb7` reads `+0x1e = 0xFFFF`); script
  ptr table `0x9C4000[songidx]` (entry 18 = 0x8E0000). Data IS loaded (not a load bug).
- SSF slideshow latch `0x251D8` (boolean; owner obj dispatcher `f86694`, under
  AcPresentationControlProc `0xF8450B`; start gate `f84625` needs a `0xB80A` block, fed by SSF SysEx
  events in the song stream via router `f0e92f`). Advances on song EVENTS, not the beat counter.

## 7. Reproduce it

Build tree: `~/compartilhado/kn7000_mame_build`, binary `kn7000`. Run:
```
cd ~/compartilhado/kn7000_mame_build
DISPLAY=:0 timeout 200 ./kn7000 kn5000 -rompath ./roms -skip_gameinfo -autoboot_delay 0 \
  -autoboot_script <probe.lua> -snapshot_directory <dir>
```
Reusable Lua idioms (all verified to work; probes were in the session scratchpad, ephemeral —
re-derive from these):
- DRAM/SFR read: `local sp = mach.devices[":maincpu"].spaces["program"]; sp:read_u8(a)` /
  `read_u16`. SFRs live at 0x00–0xFF (T8RUN 0x80, T16RUN 0x9E, INTET01 0xE4, INTET45 0xE6).
- Buttons: `mach.ioport.ports[":cpanel:CPL_SEG3"].fields[..]:set_value(1)`.
- **Write-tap that FORCES a value**: `sp:install_write_tap(a,a,"n",function(off,data,mask) if
  (data&0xffff)==0 then return 0xFFFF end return data end)` — the RETURN modifies the write (a
  separate `write_u16` inside the callback is overwritten by the original store). Write-taps coexist
  with `register_frame_done`; read-taps do not.
- **Stack dump** (catch a caller): in a write-tap, `cpu.state["PC"].value`, and dump the SYSTEM stack
  `cpu.state["XSSP"].value` (XNSP is unused on this box) via `sp:read_u32(xssp+i*4)`.
- Nav timing: boot ~20 s, then DEMO / LEFT4 / LEFT2 with ~0.3 s press + ~1.5 s gaps.

## 8. NEXT STEP (single, well-defined — the root cause is known)

**Make the SSF presentation start.** Concretely, find why a *delivered* key press in state `0xE4`
never produces event `0x1C00038`:
1. Trace `UIState_KeyScan_Dispatch (0xF98697)` at runtime — is it called at all after boot? (March
   measured ~900 boot-time calls, all with `0x8d38 == 0x00` -> the empty gate array, then never
   again.) A word-aligned execution/read tap or a debugger BP will settle it.
2. If it is never called post-boot, the gap is upstream in **UI event delivery**: the widget handler
   chains are walked by the event-buffer dispatcher (`FDB3D1` fills a circular buffer at DRAM
   `0xBD3C`; `FDB328` dispatches from handler-chain table `EE7CA7`). Find why a panel key press does
   not enqueue there, while still reaching the demo-menu logic.
3. Cross-check against the known KN5000 control-panel serial defect family
   (`notes/kn5000-cpserial-INDEX.md` — residue characterised as **LOSS**). If key events are lost
   between the panel HLE and the UI event buffer, fixing that fixes the demo *and* a class of other
   UI bugs.
Once `0x251D8` flips to 1, the SSF script runs its `SONG` directive, the event stream loads, the
watchdog stops tripping, and (per the KN7000 model) the transport simply runs to the end of the
song with the slides paced by song position.

⚠ Do NOT resume the "per-measure re-arm" hunt — that mechanism does not exist (see §4).

## 9. Method lessons (cost real time here)

- **Runtime measurement repeatedly REFUTED static disassembly analysis** (3 subagent passes each
  produced a plausible-but-wrong path: f591D1/accompaniment, f5af3c, f86fb7/0x2314). ALWAYS verify a
  static claim with a tap/probe before building on it.
- The March-2026 "0xB80A workspace-tag mismatch" conclusion is STALE and WRONG — the demo does
  start; do not reopen it.
- INTTR4 (not INTTR5) is the active tick; `INTET45` nibble layout: INTTR5 = high (pri 6:4, req bit7),
  INTTR4 = low (pri 2:0, req bit3).
