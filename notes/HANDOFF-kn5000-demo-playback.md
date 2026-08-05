# HANDOFF — KN5000 Feature Demo / Presentation playback (updated 2026-08-05, update 29)

**Goal:** make the KN5000 Feature Presentation play, like the KN7000's does (commit `60d5392`).
**Status: NOT fixed. Root cause LOCATED (§3/§4): the style reader walks BLANK rhythm ROM.**
One real bug WAS fixed and shipped along the way (§8). Blow-by-blow: `kn5000-demo-playback-stall.md`
(29 updates). **This file is the pick-up point — start at §4.**

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
the style reader resolves into the RHYTHM ROM (IC14) at a spot that is BLANK (all 0xFF)
 -> 0xFF is not a valid opcode
  -> f568a8 skips one byte and bumps the watchdog 0x32ed for EACH unrecognised byte
   -> at 32 (0x20) f568b6 -> f59ab9 -> f5adca -> f5afb2 writes lanes 0x420/0x421 = 0x0C
    -> 0x0C is a quantized "STOP at next beat", TERMINAL BY DESIGN
     -> INTTR4 ef0fa0 parks 0x0C->0x10 ; main-loop f3ecd4 (res 4) clears 0x10->0x00 = STOP
      -> beat clock 0x417 freezes (it only counts while 0x420 bit2 is set, gate ef0e70)
       -> the DEMO SONG PLAYER dies too: it gates on the same transport (f86f2e: bit 2,(0x0420))
```
**Only the first line is a defect. Everything below it is the firmware behaving CORRECTLY** — it
detected a corrupt stream and stopped playback.

## 4. ★ WHERE IT ACTUALLY BREAKS + THE EXACT NEXT PROBE ★

**The reader never touches DRAM.** `f58ff9` takes `f59035` whenever `(0x32e5) < 0x80` (0x60 idle,
0x48 in the demo), and `f590a9`/`f590b4` resolve through the table at `f590d1` =
`0x00400000, 0x00410000, …` — the **rhythm ROM IC14**. `(XHL+IY)` is a **signed** 16-bit index and
`f56cd0` returns `ptr-0x8000+6`, so the `0x8000` cancels:

```
read = 0x400000 + (0x3285)*0x10000 + ptr + 6      ; +6 skips the cell header 80 FF FF FF FF 87
```

| | idle (control) | demo |
|---|---|---|
| `(0x32e5)` / `(0x3285)` bank | 0x60 / 0x23 | 0x48 / **0x1A** |
| record `XIY=(0x32ce)` | 0x402800 | **0x407800** |
| resolved read | 0x647BA4 → `00 90 00 30 42 0C …` | **0x5AE75B → `FF FF FF …`** |
| valid opcodes / 32 | 6 | **0** |

Bank 0x1A's last non-`FF` byte is `0xE230`; the demo reads `0xE75B`. **It walks blank ROM.**

The style record lives in the rhythm ROM. Per lane, `A=(0x32a3+i)` → `f5657e` → `HL=tbl[A]` →
`ptr = (XIY + HL + 0x118 + 0x26*lane)`. `f5669a` = `0000 0002 … 000E 0400 0402 0404 …`, so A≤7 is a
variation block at `+0x118` and A≥8 a second block at `+0x518`. Measured: **idle used A=0**
(offsets `118…1D6`), **the demo used A=10** (offsets `51C…5DA`, HL=0x404) on all six lanes.
The record's bank array at `+0x3D1` is `1A 3D 3D 0D 3D 3D 3D 3D 3D` — banks 0x38-0x3F are entirely
`0xFF`, so **`0x3D` is a "no data" sentinel** — and `f55fde` reads `(XIY+0x03D1)` with **no index**.

**MEASURED (2026-08-05), correcting the note above:** the per-lane variation bytes
`0x32a3..0x32a8` are all set to **`0x23`** at `f56382`, just before the bank is set:

```
32e5(style) <- 48   PC=F55EBE
32a3..32a8  <- 23   PC=F56382      <-- all six lanes
3285(bank)  <- 1A   PC=F55FE7
```

`0x23` is **not** a bank number (its resemblance to the pre-demo bank 0x23 is
coincidence). The table at `f5646e` is `00 05 0A 0F 14 19 1E 23` -- **8 sections,
stride 5** -- so `0x23` = section 7. **Idle runs section 0; the demo runs section 7.**
That is the differentiator. `f56373` computes it: `W=(0x32d8)`, `A=(0x3338)`,
`calr f563a2` -> `f563e1`/`f56402` -> `A = f5646e[A]`, then stores it to all six lanes.

⚠ My earlier "variation A=10" was WRONG: `f5657e` double-shifts `W` (`f5659b` shifts
once and clobbers W with a byte read from the style record, then `f56592` shifts
again), so the index into `f5669a`/`f566aa` comes from the RECORD, not from `A`.
One step still does not reconcile -- I compute HL=0x400 where the firmware used
0x404 -- so treat the exact index chain as UNVERIFIED.

**SECTION-SELECT CHAIN — NOW FULLY RESOLVED (measured 2026-08-05):**

```
f55f87:  A = (0x3305) & 3        ; 2-bit section REQUEST
         (0x3338) = A            ; measured: 0 at idle, 3 at demo engage (PC F55F92)
f56373 -> f563a2 -> f56402:  idx = f56413[req]   ; table 00 03 04 07
                    f563e1/..:  A = f5646e[idx]  ; table 00 05 0A 0F 14 19 1E 23
         -> written to (0x32a3..0x32a8), all six lanes
```

Request 3 -> index 7 -> section byte `0x23`. **That reconciles the arithmetic
exactly** and closes the HL=0x400-vs-0x404 gap flagged above. `(0x32d8)` stays 0
throughout and is NOT involved. Measured: idle = request 0 / section 0 (valid data);
demo = request 3 / section 7, whose pointers `0xE754..0xFD29` are past bank 0x1A's
data end `0xE230`.

**THE REMAINING QUESTION** is now sharp and is the next probe: **why is `(0x3305)`
3 during the demo, and does style 0x48 legitimately have no section 7?** Either
(a) the style->bank mapping `(0x32e5)=0x48 -> (0x3285)=0x1A` is wrong, or (b) the
firmware should clamp/fall back when the selected style has no data for the
requested section. Tap `(0x3305)` across the engage and find its writer; then check
whether other styles in bank 0x1A do have section-7 pointers in range.

**RESOURCE (new):** `~/compartilhado/kn5000-roms-disasm` has semantic labels and a
symbol table (`symbols/maincpu_symbols_reference.txt`) for this exact ROM. Every
routine in this chain -- `F55FDE F56373 F56CD0 F5657E F58FF9 F590A9 F567CD F568A8
F568C9 F56E71 F59AB9 F5E931 F5CE20` -- is still an unnamed `LABEL_*` there, i.e. the
accompaniment/style reader is UNDOCUMENTED in the disassembly. The findings in this
file are the first semantic account of it and are worth contributing back as names.

**The demo SONG is not the problem** — see §6; its data is intact at `0x69800`.

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
| "`F5CF95` is a song-fill loop; 4 of 6 lanes hold zeros" | **RETRACTED (update 29).** `F5CF95` is the WATCHDOG's own pool wipe (`f568ba`→`f5e931`→`f5ce20`→`f5cf7e`), memsetting from ROM templates `f5d340/f5d440/f5d540`. The dump was post-wipe: lane 4's `81 81 … 83` is literally `f5d440[9..]`, lane 6's `81 90 00 43 40 03 00` is `f5d340[0x2F..]`. An artifact of the failure, not its cause |
| "the pattern reader reads the DRAM pool at `0x95C00`" | REFUTED: it resolves into the **rhythm ROM IC14**; all `0x95C00 + cell*256 + off` arithmetic in updates 26-28 was fiction |
| "the demo song is never loaded / the blob is empty" | REFUTED: `0x8E0000` decompresses 34 KB to `0x69800`, 96% non-zero, a valid 16-track sequence (§6) |

## 6. Address / cell map (verified)

**CPU/interrupts** — maincpu = TMP94C241 @ 16 MHz, TLCS-900, LE. Active tick = **INTTR4**, handler
`0xEF0E21` (INTTR5 `0xEF086A` is an empty `reti`; the March notes had this backwards). Tick/beat
PROCESSING is main-loop driven (`ef1245..ef1385`, `ef1372: call f4e635`), decoupled from INTTR4
which only advances the beat clock.

**Reader / watchdog** — dispatcher `f567cd`; fetch `f567f0: A=(XHL+IY)`; opcodes `0x81` beat →
`f568ee`, `0x83` end-of-track → `f56a25`, `0x87` cell-link, `0x90/0x91/0xD1..0xD5` events →
`f568c9`, anything else → `f568a8` (skip 1 byte, `0x32ed`++). Watchdog trip at `0x32ed==0x20` →
`f568b6`. Pause flag = `0x32f4` bit0. Pacing gate `f568ee` uses `f570bb` (read-ahead window 24).

**Resolvers** — `f58ff9` chooses. `(0x32e5) < 0x80` → `f59035`: `A=(0x3285); f590a9` → **rhythm ROM**
via table `f590d1` (`0x400000 + n*0x10000`, 0x40 entries) `+ (0x3277) + 0x8000`; `(XHL+IY)` is a
**signed** index. Otherwise → `f59059`/`f59069`, banked: table `f59089` = `0x095C00` (DRAM pool),
then IC19 pools `0x301400 0x31AC00 0x331400 0x34AC00 0x361400 0x37AC00 0x391400`,
`phys = bank[cell>>12] + (cell & 0xFFF)*256 (+ offset)`. **The demo takes the rhythm-ROM path.**

**Style record** (in the rhythm ROM, `XIY=(0x32ce)`): bank byte array at `+0x3D1` (`0x3D` = empty
sentinel; banks 0x38-0x3F are all `0xFF`); lane pointers at `+0x118 + 0x26*lane` (variation block 0)
and `+0x518 + 0x26*lane` (block 1), selected by `HL = f5669a[(0x32a3+lane)]`. Wipe templates:
`f5d340` / `f5d440` / `f5d540`.

**Demo song blob** — `f87189(18)` → `ef41e3` decompresses `[18]=0x8E0000` (`SLIDE4K`, uncompressed
size u16 at `+8` = `0x9500`) to **`0x69800`**. Layout: `+0x1E` u16 track-enable mask, `+0x20` 16×u8
track type, `+0xD0` 16×{u8 flags, u16 start-cell}, `+0x800` cell area. Cell walk (`f8712b`):
`addr = base + (cell-1)*256 + 5 + idx`, 250 payload bytes/cell, u16 next-cell link at `+3`,
`0xFFFF` = end. `f86f48/6d/92/b7/dc` pick `0x69800` (ROM demo song) vs **`0xAB000`** (user song).
⚠ `ROM_LOAD32_WORD` = **4-byte** interleave (ic3 → bytes 0,1; ic1 → bytes 2,3); a 2-byte interleave
yields "SILDEK4" and bogus pointers.

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
- ⚠ **Filter/window your taps.** Several hot idle loops (`F567AC`, `F56765`, `F572BC`) rewrite these
  cells at ~1 kHz and will eat a naive capture budget before the interesting moment. Log only on
  value CHANGE — a time window alone was not enough (it failed three runs in a row).
- ⚠ **Hold taps in a GLOBAL** (`_G.__taps[#_G.__taps+1] = sp:install_write_tap(...)`). Kept in a
  local, they are garbage-collected and silently stop firing — an empty writer bucket then looks
  exactly like "nothing ever writes here". Second instrument defect to nearly cause a retraction.
- ⚠ `sed -n '/^addr:/,/^addr2:/p'` on the disassembly runs to EOF (11 MB) if the end label does not
  exist. Use `grep -n` for the line number then a bounded `sed -n 'N,+Mp'`.
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
