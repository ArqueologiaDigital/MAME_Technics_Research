# HANDOFF — KN5000 Feature Demo / Presentation playback (updated 2026-08-05, update 30)

**Goal:** make the KN5000 Feature Presentation play, like the KN7000's does (commit `60d5392`).
**Status: ROOT CAUSE SOLVED (§4). The bug is in the ROM DUMP, not the firmware and not the
emulation: `kn5000_rhythm_data_rom.ic14` has address lines A19 and A21 TRANSPOSED.**
De-swapping them makes the demo play — watchdog `0x20 -> 0x00`, transport `0x00 -> 0x04`,
audio rms `0.0 -> 1543.9`. The service-manual schematic (page 32) shows IC14's address
lines run straight, so the BOARD is not at fault: **IC14 must be RE-DUMPED** (see §4).
Nothing is shipped — a de-swapped image we synthesised is not an honest dump.
Roughly two thirds of ALL factory rhythms are affected, not just the demo.
One real bug WAS fixed and shipped along the way (§8). Blow-by-blow: `kn5000-demo-playback-stall.md`.
**This file is the pick-up point — start at §4.**

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

**ORIGIN OF THE SECTION REQUEST — MEASURED:** `(0x3305)` has exactly ONE writer,
`f53409`, inside a panel-sampling routine:

```
f533ff:  A = (0xFC61) ; A &= 0x30 ; A >>= 4 ; (0x3305) = A
```

so the request is **bits 4-5 of the control-panel mirror byte `0xFC61`** (that routine
also samples 0xFC5E/0xFC60/0xFD99/0xFDAD). Measured timeline at demo engage:

```
t=24.40393  0xFC61 <- 0x30   PC=FF0DBC     <-- origin, both bits set
t=24.51675  0x3305 <- 03     PC=F5340D
t=24.51879  0x32E5 <- 48     (style)
t=24.51883  0x3338 <- 03     (section request)
t=24.51888  0x3285 <- 1A     (bank)
```

`FF0DBC` is a **bulk copy routine** -- the same PC seen in the pool-writer bucket
writing `0x044000..0x056000` -- so `0xFC61=0x30` arrives as part of the demo loading a
panel/registration snapshot. The demo therefore *legitimately* asks for variation 4 /
section 7. Nothing here looks like a stray write.

**ROOT CAUSE — SOLVED (2026-08-05).** The record lookup is CORRECT; the ROM DUMP is not.

`f53d9a` is the style-record lookup. Fully decoded:

```
f53d77  H &= 7 ; H <<= 1 ; W = 0 ; WA <<= 2 ; L = 0 ; HL = H*256 + A*4
        XIY = 0xE45142                       ; style directory, 4 bytes/entry
        WA  = (XIY+HL)                       ; word0: low byte = 64K bank
        IY  = (XIY+HL+2)                     ; word1: offset within that bank
f53d9a  calr f53d77 ; call f590b4 ; extz XIY ; add XHL,XIY ; ld XIY,XHL
f590b4  if A > 0x3F: A = 0
        XHL = f590d1[A] + (0x3277)           ; f590d1 = 0x400000,0x410000,... (LINEAR,
                                             ; all 64 entries verified)
```

so `record = 0x400000 + (0x3277) + bank*0x10000 + offset`, indexed
`(H&7)*512 + style*4` — i.e. **8 groups x 128 styles**. With `H=(0x32E6)=4`,
`style=(0x32E5)=0x48` this yields `0x407800`, exactly the measured `(0x32CE)`.
`(0x32E6)` is the style GROUP; the 7 compare sites `f54692..f54af4` bound it to 0..6.

**ORIGIN OF THE STYLE AND GROUP — MEASURED.** The same panel sampler that produces
the section request also produces these, from adjacent mirror bytes:

```
f53367:  A = (0xFC5A)              -> (0x32F5)   pending STYLE
f5336F:  A = (0xFC5B) & 0x7F & 7   -> (0x32F7)   pending GROUP
f533FF:  A = (0xFC61) & 0x30 >> 4  -> (0x3305)   section request
f55EA4:  (0x32E6) = (0x32F7) ; (0x32E5) = (0x32F5)     ; commit
```

```
t=24.40393  0xFC5A <- 48  0xFC5B <- 04  0xFC61 <- 30   PC=FF0DBC   (demo's snapshot)
t=24.51879  0x32E6 <- 04  0x32E5 <- 48                 PC=F55EB2/F55EBE
t=24.51888  0x3285 <- 1A                               rec=407800
```

Every value in the chain is what the demo asks for. Nothing is a stray write.

**THE DEFECT IS IN `kn5000_rhythm_data_rom.ic14`: ADDRESS LINES A19 AND A21 ARE
TRANSPOSED.**

Every accompaniment track begins with the cell header `80 FF FF FF FF 87`, and the
reader starts 6 bytes past it (`f56d47: WA -= 0x8000 ; WA += 6`, then `f590a9` adds the
0x8000 back). So a correct lane pointer must land exactly 6 bytes after that pattern.
Over all 202 records in the directory x 48 lane reads each:

| image | lane reads correctly framed | reads landing on 0xFF |
|---|---|---|
| as dumped | 3439 / 9696  (35.5%) | 409 |
| A19<->A21 de-swapped | **9696 / 9696 (100.0%)** | **0** |

The declared-bank -> actual-bank relation is a clean deterministic bit swap, never a
scatter: `0x08-0x0F <-> 0x20-0x27`, `0x18-0x1F <-> 0x30-0x37`, all others identity.
That is bank bits 3 and 5 = ROM address lines **A19 and A21**. The record area
(banks 0x00-0x07) has both bits clear, so the records themselves are unaffected —
which is why the directory, the style names and the record contents all looked sane
and only the pattern reads were garbage.

**Emulator confirmation** (identical runs, only the ROM file differs):

| | as dumped | de-swapped |
|---|---|---|
| watchdog `(0x32ED)` | 0x20 = tripped, pegged | **0x00, never trips** |
| transport `(0x0420)` | 0x00 stopped | **0x04 = bit 2 running** |
| audio ENGAGE+5..13s | peak 0, rms 0.0 | peak 32768, rms 1543.9 |

```
as dumped   crc32 76d11a5e  sha1 e4b572d318c9fe7ba00e5b44ea783e89da9c68bd
de-swapped  crc32 aa4917ce  sha1 fef7f1927935d8fdada2afbdbfac29aac56e1c3c
```

**SCOPE.** This is not a demo-only bug. 132 of 202 style records sit in banks where
bit 3 != bit 5, so roughly two thirds of the factory rhythms read the wrong 64 KB bank.
The home-screen default style (bank 0x23) is among them. This is very likely the whole
of "the KN5000 automatic rhythms are completely messed up".

**SETTLED BY THE SCHEMATIC: the BOARD is straight, so the DUMP is wrong.** Service
manual page 32 ("CPU SECTION (A) P.C. Diagram") shows IC14 = `QSIGX3C23011`, 32M BIT
RHYTHM DATA ROM, with a perfectly monotonic address connection:

```
net A21 -> pin 44 = AD20      net A16 -> pin 35 = AD15
net A20 -> pin 43 = AD19      net A15 -> pin 36 = AD14
net A19 -> pin  2 = AD18      net A14 -> pin 37 = AD13
net A18 -> pin  3 = AD17      net A13 -> pin 38 = AD12
net A17 -> pin 34 = AD16      net A12 -> pin 39 = AD11  ... AD0 <- net A1
```

i.e. device bit `AD_k` <- board net `A(k+1)` throughout — the identical regular pattern
as IC19 (`QVIGFKN5KAX1`, custom data ROM) immediately to its right. Nothing crosses.
File byte-offset bit 19 is `AD18` <- net `A19` and bit 21 is `AD20` <- net `A21`, so
there is no board-level permutation for the driver to model.

==> **`kn5000_rhythm_data_rom.ic14` MUST BE RE-DUMPED.** Note that `AD18`/`AD20` are
pins **2 and 44** — physically adjacent, separated only by pin 1, which IC14 leaves
**NC**. That is exactly the neighbourhood where a socket adapter configured for a
different 44-pin part mis-maps. Only one copy of this dump exists (every rom dir in
`~/compartilhado` has the same sha1 `e4b572d3...`), so there is nothing to cross-check
against.

Until a real re-dump exists, do NOT check the de-swapped image in as if it were a dump
— under the MAME integrity policy an image we synthesised is not an honest dump. The
test image is at `<scratchpad>/ic14_deswapped.bin`. If the driver needs to run in the
meantime, mark the existing ROM `BAD_DUMP` rather than silently substituting.

NEXT: check whether the other 4 MB mask ROM, the waveform ROM `ic307`, carries the same
transposition — it is the same size and presumably came off the same rig, and an A-line
swap in wave data would be far harder to notice by ear than in sequencer data.

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
