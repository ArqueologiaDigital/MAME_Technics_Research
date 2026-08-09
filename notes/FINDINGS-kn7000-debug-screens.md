# KN7000 hidden factory debug screens — MEMORY DUMP, SOFT VERSION, DEBUG TOOLS

Date: 2026-08-09. All addresses are MN10300 CPU addresses; program-flash file offset =
CPU address − 0x48400000. Evidence base: `roms/kn7000/kn7000_program.rom` (PROGRAM 941),
`roms/kn7000/kn7000_table.rom` (TABLE 84), and a MAME session with the stock driver.

## 0. Answer

**YES — the KN7000 has the equivalent of the KN5000's hidden hex viewer, and it is reachable at
runtime on a stock instrument.** It is not nested inside the Panel Simulator: on our ROM the chord
opens the viewer directly as a first-class title, `_TT_MEMDUMP` (title id 0xF2).

**The chord is: hold UP+DOWN together on balance columns 1, 4, 5 and 8** (the manual's own MUTE
gesture, applied to four parts at once). Not 1/5/8 — see §3.

## 1. The runtime chord dispatcher (proven from ROM bytes)

`0x48414735` is the balance-button ("index switch") handler. It maintains two 32-bit held-masks and
their AND:

| Cell | Meaning |
|------|---------|
| `0x50021FD8` | set of columns whose **UP** button is currently held (panel event 0x702001) |
| `0x50021FDC` | set of columns whose **DOWN** button is currently held (event 0x702000) |
| `0x50021FE0` | `FD8 & FDC` — the set of columns with **both** buttons held |

```
48414842: fc a6 e0 1f 02 50   mov  (0x50021fe0), d2
48414848: fc a4 dc 1f 02 50   mov  (0x50021fdc), d0
4841484e: fc a5 d8 1f 02 50   mov  (0x50021fd8), d1
48414856: f2 01               and  d0, d1
48414858: fc 85 e0 1f 02 50   mov  d1, (0x50021fe0)
```

Bit N of that word is **column N+1**: the index→mask table at `0x4859E1A0` is a plain `1 << N`
(verified: entries 0..11 read 1,2,4,8,10,20,40,80,100,200,400,800). The calibration is anchored on
Felipe's own hardware result — columns 1/6/8 → SOFT VERSION → bits 0,5,7 → 0xA1.

The dispatcher at `0x484148C0` tests **exactly three constants** and nothing else:

```
484148c0: mov  (0x50021fe0), d0
484148c6: cmp  0x99, d0      ; beq 0x484148dc  -> gate -> mov 0xf2,d0 ; call 0x4842b4a0   (TT_MEMDUMP)
484148cc: cmp  0xa1, d0      ; beq 0x48414919  ->         mov 0xf0,d0 ; call 0x4842b4a0   (TT_SOFTVER)
484148d2: cmp  0x110000, d0  ; beq 0x48414926  -> gate -> call 0x48415680                 (LCD capture)
484148da: bra  0x48414939    ; anything else: return
```

A byte scan for the absolute address `0x50021FE0` finds only five references in the whole 4 MB
image: `0x48414844`, `0x4841485A`, `0x484148C2` (this block) and `0x48414C07` / `0x48414CAA`
(two `mov d1,(abs)` resets). **There is no second comparison site anywhere.**

| Accumulator | Columns (both buttons held) | Result |
|---|---|---|
| `0x000000A1` | 1, 6, 8 | SOFT VERSION (`_TT_SOFTVER`, 0xF0) — no gate |
| `0x00000099` | 1, 4, 5, 8 | **MEMORY DUMP** (`_TT_MEMDUMP`, 0xF2) — gated, see §2 |
| `0x00110000` | LCD soft-key rows 1 and 5, left+right (bits 16 and 20) | LCD screen-capture to `LCDCAP%02d.BMP` — gated inversely |

The compare is an **equality**, not a mask test: one extra column in the both-held state silently
kills the chord (measured — cols 1,2,4,5,8 → 0x9B → nothing).

## 2. The configuration-byte gate at 0x4840000F

```
484d7928: fc a8 0f 00 40 48   movbu (0x4840000f), d0
484d792e: de 00 00            retf  0, 0
```

`0x4840000F` is a lone data byte in the flash header (`dc 7e ff 00 00 cb cb cb cb cb dc c5 77 0d 00
**16**`). In our PROGRAM 941 image it is **0x16**.

* `0x99` chord: `cmp 0xff,d0 / bne → open TT_MEMDUMP`. Non-0xFF (ours) → **hex viewer**.
  0xFF → `ChangeMode(0,0)` → **Panel Simulator 2.1**.
* `0x110000` chord: requires the byte to **be** 0xFF, so LCD capture is **dead** on our ROM.

The two outcomes are mutually exclusive, which makes the chord a **one-press probe of that byte on
any unit**. (The same byte is compared against 0x77 at `0x484A508C` and printed as two hex nibbles
at `0x4848A8E1`, so it is a configuration/destination code, not a debug-only flag.)

## 3. Why the KN5000 chord (columns 1+5+8) does nothing on a KN7000

Columns 1,5,8 = bits 0,4,7 = **0x91**. That is the KN5000's Panel Simulator constant. The KN7000
dispatcher has no case for 0x91: it falls through `bra 0x48414939` and returns. Reproduced in the
emulator — the accumulator reached exactly `0x00000091` (so the instrument *saw* the input) and the
screen never changed. **Wrong constant for this firmware — not timing, not panel mapping, not an
absent screen.**

## 4. The viewer itself (`DbMemoryDumpProc` @ 0x484878AC)

* 16 rows × 16 bytes, `%04X%04X` address, `%02X` hex pairs with a `-` after byte 8, ASCII column
  with `.` substituted for bytes < 0x20. Header ` DUMP ADR%d = %04X%04X `, footer
  `Aqua = F0  Yellow = F7  Lime = FF  Fuchsia = XX`.
* Four independent address slots at `0x500012EC/F0/F4/F8`, slot selector u16 at `0x5006B524`.
  First-open defaults: 0x84000000, 0x84000770, 0x84000814 (0x84000000 = the `ram44` work-RAM alias,
  `kn7000.cpp` `map(0x84000000,0x84ffffff).ram()`), so it opens somewhere harmless.
* Step handler `0x48487E60`: control index i∈0..7 → `±(1 << (4*i))`; `if addr >= 0xC0000000: addr &=
  0x0FFFFFFF`. Controls 9..12 step the four highlight bytes, control 13 the slot.
* **Measured button mapping** (the operationally useful form, and the *reverse* of the internal
  control index): balance column 1 = **leftmost** hex digit (+0x10000000) … column 8 = rightmost
  (+1); column 9 inert; columns 10-13 = Aqua/Yellow/Lime/Fuchsia; column 14 inert; column 15 =
  ADR0..ADR3 slot selector; column 16 inert. The on-screen rocker row in the screenshot sits at
  exactly those column positions, which corroborates the measurement.
* **Read-only.** Every store in the handler set targets the stack frame or the widget's own cells
  (`0x500012EC..0x500012FC`, `0x5006B524`, `0x5006B528`); the inspected address is only ever read
  with `movbu (dN,aN),dM`. A write tap over the whole `0x96xxxxxx` flash window counted **zero**
  writes across a full open→drive-every-control→EXIT session.

Verified byte-exact against the ROM file at four addresses dialled with the panel buttons:
`0x48400000` → `DC 7E FF 00 00 CB CB CB CB CB DC C5 77 0D 00 16`; `0x4873660C` →
`AD 03 00 00 B9 AF 47 48-50 00 04 00 34 00 04 00`; `0x487F6E00` →
`4E 0C F6 DF 4E 08 F6 CF 4E 04 F2 E7 4E 00 FC AF`; `0x487F7000` → all FF (our image ends at
0x487F6F00).

## 5. DEBUG TOOLS is reachable after all — via the Panel Simulator

With the gate byte patched to 0xFF the same 1/4/5/8 chord opened **"Technics / Panel Simulator
2.1"** with a DEBUG TOOLS button bottom-right; the bottom-right LCD soft key (LCDR5) then opened
**DEBUG TOOLS** (`_TT_DEBUG`, 0xFF): MEMORY DUMP / MEMO LOG on the left soft keys, ICON LIST /
COLOR LIST / BITMAP LOAD on the right, a `DEBUG MODE : OFF` toggle, an `015 : _MD_SONG` mode
enumerator, and a **`--- SOFTWARE VERSION ---` box with four fields: PROGRAM, TABLE, RHYTHM,
PICTURE**. LCDL1 from there opens the same hex viewer.

RHYTHM and PICTURE read 0 in the emulator (synthetic/undumped ROMs) — on real hardware they should
show real numbers we hold from no source at all.

## 6. Version cells

* PROGRAM: u16 LE at `0x4873660C` = 0x03AD = **941** in our image; format `PROGRAM : %4d`.
* TABLE: **not** the program-ROM cell at 0x48736614. The loader at `0x48414376` reads
  `u32 @0x4800001C` (= 0x00139EE8), adds 0x48000000, and parses the ASCII decimal string there:
  table ROM file offset 0x139EE8 = `38 34 0a 00` = **"84"**. `AcTableVerBoxProc 0x484888FB` prints
  it. The emulator's SOFT VERSION screen reads TABLE : 84.

**Consequence: Felipe's unit (PROGRAM 893 / TABLE 80) has TWO undumped flashes, not one.** Earlier
notes that said "TABLE 80 matches ours" were wrong.

Our `kn7-16` update disks give PROGRAM 941; `kn7-14` is a TABLE-only update set (`JKT1/JKT2.SLD`,
`TECHNICS.TB1/TB2`). Neither yields 893/80.

## 7. Danger (primary sources, NOT emulator-verified — no power-on combo was executed)

From `KN7000/kn7-16/install.pdf` (CA-Software) and service manual §9.4.1:

* ⛔ **PANEL MEMORY 1-2-3-4 held during power-on = "Flash Memory Update": erases and reprograms
  IC16/IC17.** On Felipe's instrument this would destroy PROGRAM 893 irreversibly.
* ⛔ PANEL MEMORY 2-3-4 held during power-on = the same updater in verify-only mode. One button away
  from the destructive one.
* ⛔ RHYTHM `[60s & 70s] + [MODERN DANCE] + [SOUL & R&B]` at power-on = post-update re-init;
  install.pdf: "ACHTUNG: Dadurch gehen alle gespeicherten Daten (außer Custom-Speicher) verloren!"
* ⛔ Factory service/test menu: entered by holding keyboard notes during power-on
  (`notes/service-diagnostic-mode.md` records C#3+D#3+C#4, internal indices 0x0D/0x0F/0x19, and that
  the combo is NOT read through the note FIFO — do not re-attempt FIFO injection). It contains a RAM
  DEVICE TEST covering the battery-backed IC23 user SRAM and an FD SAVE/LOAD TEST that writes to the
  floppy in the drive.
* ✅ Safe read-only power-on combo: SOUND GROUP `[PIANO]+[GUITAR]+[MALLET & ORCH PERC]` → version
  bottom-right.
* An earlier pass in this investigation concluded "no KN5000-style Flash Memory Update exists on
  KN7000" from a string sweep. **That conclusion is wrong and is retracted here.** The updater lives
  in the un-shipped top 0x90FF of the flash (`notes/rom-backup-and-update-format.md` §2.2), which is
  precisely why no updater strings appear in our image.
* Runtime hazard inside the viewer: it repaints continuously, so a parked address is re-read over
  and over. Keep it in ROM (0x48000000-0x487FFFFF) or RAM (0x50000000+, 0x84000000). Avoid
  0x9680xxxx (flash command window), 0x98000000-0x9807FFFF (TG/FDC), 0x9C000000 (DSP port),
  0x9CC00008 (SD), 0x20000000/0x34000000 (CPU internal I/O incl. MIDI TX).

## 8. Open / to confirm on real hardware

1. Does the 1/4/5/8 chord work on PROGRAM 893, and which branch does it take (hex viewer vs Panel
   Simulator)? Either answer reads out the byte at 0x4840000F on his chip.
2. If he lands on Panel Simulator, his gate byte is 0xFF, which also means the **LCD screen-capture
   chord is live on his unit** — memory-dump screens could then be written to disk as BMPs instead
   of photographed.
3. RHYTHM and PICTURE version numbers from the DEBUG TOOLS software-version box.
4. An exhaustive 4-column chord sweep was not run behaviourally (only 0x99 and the 0x9B negative);
   the disassembly says three constants exist and that is byte-proven, so this is a completeness gap
   only. All 56 three-column chords over columns 1..8 *were* swept, with exactly one positive (0xA1).
5. `notes/panel-dispatch-table.md` names 0x486149FC as the active panel dispatch table; the evidence
   in this pass points at **0x48614978** (its ev2001/ev2000 arg layout reproduces the driver's mute
   matrix and yields cols 1/6/8 → 0xA1, matching hardware). Not changed here.

## 9. Emulator artifact worth knowing

The MAME CP serial HLE delivers panel changes one segment at a time, so pressing 6-8 caps in a
single frame never converges. Press one button at a time and wait for its bit to appear in
`0x50021FD8`/`FDC` before the next. On real hardware Felipe's 1/6/8 chord fires normally.
