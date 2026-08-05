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
the presentation runs and shows slide 1, but NEVER LOADS A SONG
   (verified: exactly ONE blob load during the whole demo — entry 18, the presentation
    DESCRIPTOR, at t=24.19; entries [0]..[17] = the 18 demo songs are never loaded)
 -> the song event stream is never loaded
     (event buffer @0x675A is ALL ZEROS; exactly ONE write ever = a boot-time clear at PC EF0B9B)
   -> the reader walks zeros; 0x00 is not a valid opcode -> every byte "unrecognised"
    -> 32 unrecognised bytes in ~0.8 ms trip the watchdog (0x32ed == 0x20)
     -> watchdog issues the quantized STOP (f568b6 -> f59ab9 -> f5adca -> f5afb2, lanes := 0x0C)
      -> INTTR4 parks 0x0C->0x10; f3ecd4 clears ->0x00. Transport dead. Repeats every ~68 ms.
       -> no music, and no slides (SSF slides ride on SysEx events INSIDE the song stream)
```
**Only the first line is a defect. Everything below it is correct firmware behaviour.**

★ **FELIPE (hardware, GROUND TRUTH):** *"the static submenu does not show any globe image; the globe
is only shown when the DEMO starts playing — it is the first slide of the demo."* So the
presentation **does start and renders slide 1 correctly**. Consequently **`0x251D8` is NOT the
"presentation-active" latch** a static-analysis pass claimed (never verified; static analysis has
been wrong four times in this investigation) — do not treat `0x251D8 == 0` as evidence. The
March-2026 `0x1C00038`/`0xB80A` chain is **NOT** the blocker, and the soft-key sweep result (no key
changes `0x251D8`) is therefore irrelevant, not a finding.

**ROM structure (decoded, solid):** `"SLIDE"` is the **sliding-window (LZSS) compression magic**
(`SLIDE4K` / `SLIDE8K`), NOT "slideshow"; `ef41e3` memcmps it (template `0xE00032`) and dispatches
on the window char (`'4'`->`ef3fab`, `'8'`->`ef40c5`). The decompressor **works** (hand-verified
against RAM: `5A EE F0`->`ZZZZ`, `E0 FB`->14 zeros, `FF` flag->8 literals). Entry table at
`0x9C4000` = **19 entries**: `[0]..[17]` = the **18 demo SONGS**, `[18]` = `0x8E0000` = the
**FEATURE PRESENTATION descriptor** (decompresses to ~0x110 bytes: "ZZZZ" header, part-type array,
**16 `80 xx 00` script records** at `0x698C8`, 16 `0x5F` bytes at `0x69900`). Six extra unreferenced
`SLIDE8K` blobs at `0x983B3A/0x988690/0x98BB3A/0x98F0DA/0x992A0C/0x9963FA` — identity unknown,
worth checking.

**THE FIX TARGET:** the presentation script runs (slide 1 shows) but **never loads a song**.
Measured: during the entire demo there is exactly **ONE** blob load into `0x69800` — entry **18**
(the descriptor) at t≈24.19 (`PC=EF4039/EF409B`); entries `[0]..[17]` are never loaded. So find
which script step should load+start a demo song (the SSF `SONG` directive), what consumes the 16
`80 xx 00` records, and why that step never issues the load. Once a song is loaded the event buffer
fills, the corrupt-stream watchdog stops tripping, and (per the KN7000 model: start once, run to an
explicit stop) playback should run the whole song with the slides paced by song position.

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

**Find why the running presentation never loads a demo song.**
1. **Decode the presentation script.** Entry 18's decompressed descriptor at `0x69800` holds 16
   `80 xx 00` records at `0x698C8` (`xx` = 32,2E,20,42,4C,53,55,5A,5D,62,64,16,6A,6D,70,25) and 16
   `0x5F` bytes at `0x69900`. Find the interpreter that walks these (it is running — slide 1 shows)
   and which opcode means "play song N" / "show slide N".
2. **Find the song-load call site.** The loader is `f87189(idx)` -> `ef41e3` -> `ef3fab`, dst
   `0x69800`. Something must call it (or a sibling) with an index in `0..17`. Tap `0x69800` writes
   (proven idiom) and/or BP `f87189` to see who calls it and with what — currently only entry 18.
   Note dst `0x69800` is shared, so a song load may need a different destination: check whether a
   second buffer (the event buffer near `0x675A`, or one of the per-track bases
   `0x3287/0x3297/0x32A3/0x32AB/0x32B5/0x33EB`) is the real song destination.
3. **Identify the six unreferenced `SLIDE8K` blobs** (`0x983B3A`, `0x988690`, `0x98BB3A`,
   `0x98F0DA`, `0x992A0C`, `0x9963FA`). They are not in the 19-entry table; if one of them is the
   presentation's backing song, find the table//pointer that selects it.
Once a song is loaded the event buffer fills, the corrupt-stream watchdog stops tripping, and (per
the KN7000 model: start once, run to an explicit stop) playback runs the whole song with the slides
paced by song position.

⚠ Do NOT resume the "per-measure re-arm" hunt — that mechanism does not exist (§4).
⚠ Do NOT chase the `0x1C00038`/`0xB80A` SSF-start chain or `0x251D8` — the presentation DOES start
(Felipe, hardware); `0x251D8` is not the latch it was claimed to be.

## 9. Method lessons (cost real time here)

- **Runtime measurement repeatedly REFUTED static disassembly analysis** (3 subagent passes each
  produced a plausible-but-wrong path: f591D1/accompaniment, f5af3c, f86fb7/0x2314). ALWAYS verify a
  static claim with a tap/probe before building on it.
- The March-2026 "0xB80A workspace-tag mismatch" conclusion is STALE and WRONG — the demo does
  start; do not reopen it.
- INTTR4 (not INTTR5) is the active tick; `INTET45` nibble layout: INTTR5 = high (pri 6:4, req bit7),
  INTTR4 = low (pri 2:0, req bit3).
