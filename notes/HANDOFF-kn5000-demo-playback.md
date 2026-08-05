# HANDOFF — KN5000 Feature Demo / Presentation playback (updated 2026-08-05)

**Goal:** make the KN5000 Feature Presentation play, like the KN7000's does (commit `60d5392`).
**Status: NOT fixed, but narrowed to one concrete defect with a defined next probe (§4).**
One real bug WAS fixed and shipped along the way (§8). Blow-by-blow: `kn5000-demo-playback-stall.md`
(28 updates). **This file is the pick-up point — start at §4.**

---

## 1. Ground truth (Felipe, hardware owner — outranks all inference)

- The Feature Presentation plays **ONE LONG CONTINUOUS SONG** with the picture slides advancing
  autonomously over it. Music starts **immediately, no count-in**.
- The backing music is **its own distinct piece**, not one of the selectable demo songs.
- **The Technics globe IS the demo's first slide** — the static submenu shows no globe. So the
  presentation *does* start; it is the music that never plays.

## 2. Current emulated behaviour

Navigate **DEMO (`CPL_SEG3` 0x01) → LEFT 4 (`CPL_SEG9` 0x02) → LEFT 2 (`CPL_SEG10` 0x01)**.
The demo activates and renders slide 1 (the globe) correctly. Then: no music, slides frozen,
transport dead within ~1 s. Repeats internally every ~68 ms forever.

## 3. The verified failure chain (every link measured)

```
4 of the 6 accompaniment LANES have raw-zero track data in the pattern buffer
 -> the reader walks a lane whose bytes are all 0x00 (not a valid opcode)
  -> f568a8 skips one byte and bumps the watchdog 0x32ed for EACH unrecognised byte
   -> at 32 (0x20) f568b6 -> f59ab9 -> f5adca -> f5afb2 writes lanes 0x420/0x421 = 0x0C
    -> 0x0C is a quantized "STOP at next beat", TERMINAL BY DESIGN
     -> INTTR4 ef0fa0 parks 0x0C->0x10 ; main-loop f3ecd4 (res 4) clears 0x10->0x00 = STOP
      -> beat clock 0x417 freezes (it only counts while 0x420 bit2 is set, gate ef0e70)
       -> no music; and no slides either (slides are paced by song position)
```
**Only the first line is a defect. Everything below it is the firmware behaving CORRECTLY** — it
detected a corrupt stream and stopped playback.

## 4. ★ THE OPEN QUESTION + THE EXACT NEXT PROBE ★

Six-lane dump taken during the demo (offset bases `0x3287/89/8b/8d/8f/91`, cell bases
`0x3297/99/9b/9d/9f/a1`, `phys = bank[cell>>12] + (cell & 0xFFF)*256 + off`):

```
lane1 off=675A phys=09C35A first=00  ZEROS
lane2 off=675A phys=09C35A first=00  ZEROS   (same offset as lane 1 => zero length)
lane3 off=6BE0 phys=09C7E0 first=00  ZEROS
lane4 off=7109 phys=09CD09 first=81  VALID:  81 81 81 81 81 81 81 81 81 81 81 81 81 83 00 …
lane5 off=76C1 phys=09D2C1 first=00  ZEROS
lane6 off=7D2F phys=09D92F first=81  VALID:  81 90 00 43 40 03 00 81 90 00 43 40 03 00 …
```
- The offsets are **sane and sequential** (~0x500-0x670 apart) ⇒ the pointer computation (`f56cd0`)
  is FINE. This is a **content** problem, not a pointer problem.
- **Lane 4 is the control**: an *empty* track is supposed to look like `81 81 … 81 83` (beat markers
  + explicit end-of-track). Lanes 1/2/3/5 have **raw zeros and no terminator at all**.
- `f55fd8: or (0x332c),0x3f` **enables all six lanes unconditionally**, and the dispatcher gates
  lane 1 on `bit 0,(0x332c)` (`f5683e`) — so the firmware always reads lane 1, which nothing filled.

**NEXT PROBE (do this first):** the buffer is refilled by a tight copy loop at **`PC F5CF95` /
`F5CFA1`** (it sweeps the whole 42 KB every ~68 ms). **Tap that loop's writes and bucket them by
destination offset against the six lane bases.** That answers directly:
- does the fill **write** lanes 4 and 6 but **skip** 1/2/3/5 (⇒ it should be emitting a minimal `83`
  terminator for empty lanes and doesn't), or
- does it **write all six** but its **SOURCE** for 1/2/3/5 is zeros (⇒ chase the source: the
  decompressed song only carries some parts, or the part→lane mapping is wrong)?

Then follow whichever branch it indicates. Useful extra: dump the fill's source pointer at the same
time (the loop reads from somewhere — capture that address and dump it).

## 5. REFUTED — do NOT re-chase (all tested at runtime)

| Hypothesis | Result |
|---|---|
| Timer/INTTR emulation bug | Timers verified correct; the transport does arm and run |
| force `0x420=0x06` / `0x04` / arm `0x41E` / hold `0xf19e` / force `0xD2F` cycle | all fail; watchdog re-trips within ~68 ms |
| "per-measure re-arm is broken" | **no such mechanism exists** — KN7000 starts once and runs to an explicit stop |
| "the SSF presentation never starts" / `0x1C00038`/`0xB80A` chain | REFUTED by Felipe: the globe IS slide 1. `0x251D8` is NOT the presentation latch |
| "the song is never loaded" (only entry 18 loads) | superseded: entry 18 is the presentation descriptor; the music data IS in the buffer for lanes 4/6 |
| "stale end-of-song read pointer" | REFUTED: the bases are **computed** by `f56cd0` every cycle |
| producer/consumer overrun | REFUTED: `F5CF95` is a whole-buffer fill loop; the consumer is already frozen when it runs |
| f86fff / `0x41E` lane arming | forcing `0x41E` has no effect |
| "the pool data comes from the saved nvram" | REFUTED: the firmware regenerates it at boot (PC ≈ `0xF5CF95`), byte-identical |

## 6. Address / cell map (verified)

**CPU/interrupts** — maincpu = TMP94C241 @ 16 MHz, TLCS-900, LE. Active tick = **INTTR4**, handler
`0xEF0E21` (INTTR5 `0xEF086A` is an empty `reti`; the March notes had this backwards). Tick/beat
PROCESSING is main-loop driven (`ef1245..ef1385`, `ef1372: call f4e635`), decoupled from INTTR4
which only advances the beat clock.

**Reader / watchdog** — dispatcher `f567cd`; fetch `f567f0: A=(XHL+IY)`; opcodes `0x81` beat →
`f568ee`, `0x83` end-of-track → `f56a25`, `0x87` cell-link, `0x90/0x91/0xD1..0xD5` events →
`f568c9`, anything else → `f568a8` (skip 1 byte, `0x32ed`++). Watchdog trip at `0x32ed==0x20` →
`f568b6`. Pause flag = `0x32f4` bit0. Pacing gate `f568ee` uses `f570bb` (read-ahead window 24).

**Cell resolver** — `f59069`; bank table `f59089` = `0x095C00` (DRAM pool), then IC19 pools
`0x301400 0x31AC00 0x331400 0x34AC00 0x361400 0x37AC00 0x391400`.
`phys = bank[cell>>12] + (cell & 0xFFF)*256 (+ offset)`.

**Lane state** — lane selector `0x33d4` (bitmask 1/2/4/8/0x10/0x20); lane-enable mask `0x332c`
(`f55fd8: or (0x332c),0x3f`); live read position: cell `0x33d6`, offset `0x33d8`, bar `0x33da`,
beat `0x33db`. Per-lane bases: offsets `0x3287/89/8b/8d/8f/91`, cells `0x3297/99/9b/9d/9f/a1`,
params `0x32a3..0x32a8`. Base initialiser = `f55fde` (unrolled ×6, calls `f5657e` then **`f56cd0`**);
position save = `f567ac`. Pattern restart = `f5675b` (resets `0x32ed`, sets `0x33d4=1`, reloads
pointers from the bases). Buffer fill loop = **`F5CF95`/`F5CFA1`**, extent `0x95C00..0x9FFFE` (42 KB).

**Transport lanes** `0x41E/0x41F/0x420/0x421`: 00=stop, 01=arm, 06/04=running, 0C=sync(terminal),
10=parked. Arm `f43cf8` (via `f43ca9`, from `0xD2F==1 → 0x2966=0x85`); promote 01→06 INTT1 `ef0cac`.

**Demo/presentation** — `0x8d34==0x13` demo, `0x8d38==0xE4` submenu; demo timer `0xD2F`
(`f86bf3`; ==10 load `f87189`, ==3 start `f86d3d`, ==1 arm); song index `0x28a4` = 18 (locked,
`f86b74`). Loader `f87189(idx)` → `ef41e3` → `ef3fab`, dst `0x69800`. `"SLIDE"` = **sliding-window
LZSS magic** (`SLIDE4K`/`SLIDE8K`), signature template at `0xE00032`, decompressor **verified
working**. Entry table `0x9C4000` = 19 entries: `[0]..[17]` demo songs, `[18]`=`0x8E0000` the
presentation descriptor. Six unreferenced `SLIDE8K` blobs at `0x983B3A/0x988690/0x98BB3A/0x98F0DA/
0x992A0C/0x9963FA`, indexed by a table at `0x988018` (identity still unknown).

## 7. Reproduce / tooling

```
cd ~/compartilhado/kn7000_mame_build
DISPLAY=:0 timeout 200 ./kn7000 kn5000 -rompath ./roms -skip_gameinfo -autoboot_delay 0 \
  -autoboot_script <probe.lua> -snapshot_directory <dir>
```
Lua idioms (all verified):
- Memory: `local sp = mach.devices[":maincpu"].spaces["program"]; sp:read_u8/u16/u32(addr)`.
  SFRs live at 0x00-0xFF (T8RUN 0x80, T16RUN 0x9E, INTET01 0xE4, INTET45 0xE6).
- Buttons: `mach.ioport.ports[":cpanel:CPL_SEG3"].fields[..]:set_value(1)`.
- ⚠ **`install_write_tap` ranges MUST be word-aligned pairs on this 16-bit space, and you must pick
  the right byte lane** (mask `0x00FF` = byte X, mask `0xFF00` = byte X+1). An odd single-byte tap
  **silently never fires** and looks exactly like "never written" — this caused a false retraction.
- A tap can **modify** the write by RETURNING a value (a separate `write_u16` inside the callback is
  overwritten by the original store).
- ⚠ **Filter/window your taps.** Several hot idle loops rewrite these cells at ~1 kHz and will eat a
  naive capture budget before the interesting moment. Log only on value CHANGE or inside a time window.
- Stack dump (catch a caller): `cpu.state["PC"].value` + walk `cpu.state["XSSP"].value` (XNSP unused).
- Write taps coexist with `register_frame_done`; **read taps do not**.
- Nav timing: boot ~20 s, then DEMO / LEFT4 / LEFT2 with ~0.3 s press and ~1.5 s gaps.

## 8. Shipped this session

**`86aae9e` — kn5000: stop persisting the volatile work DRAM as NVRAM.** `map(0x000000,0x0fffff)`
had `.share("nvram1")` + an `NVRAM` device, so the whole 1 MB of work RAM was saved and restored
between runs. Real HW: IC9/IC10 are volatile; only the IC21 SRAM (`nvram2`) is battery-backed.
Effects: (a) **the spurious `<Db>` transpose is GONE** — persisting the DRAM made every boot resume
from a half-finished power-down state (MAME's exit never lets the power-down NMI handler run);
(b) RAM measurements no longer inherit the previous session's contents. ⚠ Any older KN5000
conclusion about RAM provenance should be re-verified on clean DRAM.

## 9. Method lessons (cost real time here)

- **Runtime measurement repeatedly REFUTED static disassembly analysis** — four separate passes
  produced plausible-but-wrong causal chains. Always verify a static claim with a tap before
  building on it.
- **Check your instrument before believing a null result** (the non-firing tap above).
- Felipe's hardware answers twice redirected the whole investigation in one sentence. **Ask him
  early** when a question is about observable instrument behaviour.
