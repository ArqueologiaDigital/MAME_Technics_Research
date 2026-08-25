# SX-WSA1R probes

MAME Lua autoboot scripts.  Each answers one question about the development
driver in `src/mame/matsushita/wsa1.cpp`, and each produced a number quoted in
that file's comments.  Run them against the focused build:

```
cd ~/compartilhado/kn7000_mame_build
DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str <sec> -window \
    -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/<script>
```

⚠ The ROM filenames in `technics_roms/roms/wsa1/` are `wsa1_os_v2.icNN`, but the
driver's `ROM_LOAD` names are the factory part numbers.  Stage a `roms/wsa1r/`
with these four links (CRC32s verified to match the driver):

| link name          | file             | CRC32    |
|--------------------|------------------|----------|
| `qsigcwsa1ax.ic12` | `wsa1_os_v2.ic12`| 5f34af46 |
| `qsigcwsa1bx.ic13` | `wsa1_os_v2.ic13`| f3f84441 |
| `qsigcwsa1cx.ic28` | `wsa1_os_v2.ic28`| 855c8ac4 |
| `qsigcwsa1dx.bin`  | `wsa1_os_v2.ic21`| 735ae465 |

⚠ MAME's Lua GC silently collects a tap or a notifier that is not held in a
global.  Every script here keeps its handles in `_G`.

⚠ Taps on these 16-bit spaces must START ON A WORD BOUNDARY.  A tap on an odd
single byte throws `start address has low bits set`; cover the containing word
and select the half you want with `mask`.

## ⚠ Give it TIME: boot takes about 90 seconds of emulated time

This is the single most important thing to know before running anything here.
The 8-bit timer tick that every firmware delay is written against runs 16x slow
in MAME (see below), so a short run measures nothing.  **A 6 second run stops
before the LCD is even initialised.**  Use `-str 120` or more.

An earlier revision of this file drew exactly that wrong conclusion — it
reported "0 LCD accesses, the boot never reaches the display" from a 6 second
run and called a blank window the expected state.  That was a measurement
artefact.  It is corrected below, and the lesson is the general one: on this
machine, a null result from a short run is not a null result.

## `wsa1_boot_milestones.lua` — how far along the boot does it get?

Read/write taps on the data addresses that identified boot steps touch: the
tick counter (0x0080), the two checksum blocks (0x7620, 0x617800), the verdict
flags (0x7FD0-0x7FD5) and the SED1330 ports (0x790000-0x790001).  Data accesses
are used deliberately — opcode fetches go through the CPU cache and are not
reliably tappable.

**Result, 2026-08-25, 90 s run:**

```
tick/w   t= 0.0000  pc=F82797     boot clears the counter
tick/r   t= 0.0328  pc=F82D14     INTT1 is running
flags/w  t= 3.1347  pc=F82C88     checksum pair starts
cksum1/r t= 3.1347  pc=F82CDB
cksum2/r t= 3.1348  pc=F82CDB
LCD/w    t=10.3877  pc=F8E822     SED1330 initialised
LCD/r    t=75.4035  pc=F8F2FE     SWI7 text services drawing
```

ending at 33623 LCD writes and 821 reads, with **`ALL INITIAL SETTING!`
legible on the panel**.

## `wsa1_checksum_result.lua` — do the battery-RAM checksums pass or fail?

Watches the verdict byte at 0x7FD1.  The helper at 0xF82CD3 returns carry clear
on a match (`rcf` at 0xF82CE6) and its callers only `set` a verdict bit on that
path (0xF82C97, 0xF82CA8), so **a SET bit means PASS**.

**Result: `(0x7FD1) <= 0x00` at t=3.1347 from pc=F82C88 — both checksums FAIL.**
Correct for a machine with no battery-backed contents; 0xF82CAB then takes its
bit-0-clear arm at 0xF82CBD.

## `wsa1_tick_counter.lua` — is the millisecond tick advancing, and how fast?

Samples the counter at RAM 0x0080 and counts writes to it.

**Result: it advances, at 30.4 Hz.**  The firmware is written against
**488.28 Hz** (TREG1 = 0x1C at 0xF826F4, counts of phiT256 selected by
T01MOD = 0x0D at 0xF826EB, at fc = 28 MHz with
phiT256 = fc/2048).  MAME's `tmp95c061` implements that tap as
`m_timer_pre >> 15` = fc/32768 (`tmp95c061.cpp:726-728`), i.e. 28e6/32768/28 =
30.5 Hz — matching the measurement, and **16x slow**.  All four taps carry the
same factor of 16 (`tmp95c061.cpp:682-690, 720-728`).

Not fixed here: `tmp95c061` is shared with `ngp`, `namcos10` and three other
drivers, and no databook is in these trees to settle the tap numbering.  The
only consequence for this driver is that boot takes ~90 s instead of ~6 s.

Related, found the same way: MAME never counts the **16-bit timers 4-7** at all
— `m_t16_reg` is written by `treg45_w`/`treg67_w` and read by nothing
(`tmp95c061.cpp:1012-1063`), and nothing sets `INTET54` — so `INTTR4`, this
machine's musical clock (vector 0x50 -> 0xF82EA2), cannot fire.

## `wsa1_retry_loop.lua` — is a spin a wedge, or a delay being re-entered?

Counts writes to the delay routines' snapshot word 0x2A8E (one per ENTRY) and
histograms the PC with the delay's own instructions excluded.

**Result:** the count rises steadily, so prom_b's 51-tick delay at 0xF5AA90 is
being **re-entered by a caller**, not stuck.  With the delay excluded, CPU 1 is
seen moving on to 0xF8E671 — `Link_WaitBlockDone`, which waits on bit 7 of RAM
0x8A with a 500-tick timeout (0xF8E67D).  This is the probe that showed the
machine was progressing rather than hung.

## `wsa1_screen_series.lua` — what does the panel show over time?

Snapshots every 15 emulated seconds into `snap/wsa1r/`, printing the LCD access
counts alongside so a finished screen can be told from one still being drawn.

**Result:** LCD writes reach 32801 by t=15 s and stop; the text pass runs
between t=75 s and t=90 s, taking the count to 33623; from t=90 s to t=240 s
the counts do not move while CPU 1's PC keeps changing — a live system idling
on a finished screen.

## `wsa1_pc_sample.lua` — where is each processor spending its time?

Per-frame PC histogram for both processors.

**CPU 2** sits in the uPD6383GF microcode upload's READY poll on P9 bit 3
(0xF9A19F and seventeen siblings, each bounded at 0x1F40 iterations).  With no
callback bound MAME's port read returns 0, so every byte of the upload runs the
poll to its bound.  The driver deliberately does NOT fake that line — see the
block in `wsa1r(machine_config &)`.

**CPU 1** in the first ~3 s sits at 0xF95184/0xF951A7, which is *not* a stall
either: it is the diagnostic blink at 0xF95158, entered because P5 bit 4 reads
back 0 (an unbound input). It emits an 8-bit code as long/short pulses on P5
bit 3 and then returns. Also deliberately not faked; see the same block.

## `wsa1_cpu2_tick_and_keyscan.lua` — can the key scanner ever arm?

`KeyScan_ReadEvent` (prom_c 0xF9973D) refuses to touch the port at 0x00108000
until the one-shot latch at RAM 0x00F329 is set, and it only sets that once the
INTT1 tick counter at RAM 0x00F2F3 has passed 1000 (0xF9974E `cp XBC,0x3E8`).
This probe prints the counter, the latch, TRUN, and how often each half of the
port has been read.

**Result (2026-08-25, `-str 130`):** the counter advances at 30.5 Hz — the
16x-slow prescaler again — so it passes 1000 at about t=33 s; the latch turns 1
the moment CPU 2 reaches MAIN, at **t=70.5 s**, and from then on the status word
at 0x108002 is read about **34,500 times per second** of emulated time.  Before
MAIN the only traffic is **16** reads of 0x108000, which is
`KeyScan_InitKeyStateBitmap`'s boot drain and its `cp (XIZ-7),0x10` bound.

This is also the run that settles a question the disassembly tree lists as open:
CPU 2 **does** program T01MOD, at `0xFFF06C  08 24 0d`, so timer 1 is clocked
from phiT256 exactly as on CPU 1.

## `wsa1_keybed_note.lua` — does a key press reach the firmware?

Presses middle C (ioport `KEY2` bit 0 = key 24 = MIDI 60) at t=78 s and releases
it at t=80 s, tapping the event port and the two parameter devices.

**Result (2026-08-25, `-str 95`):** the firmware read **0x5C98** and then
**0x5C18** off 0x108000 — touch 0x5C (the "Key touch" adjuster's default of 64,
inverted: 255 - 64*255/100 = 92 = 0x5C), key 0x18 = 24, bit 7 set for the press
and clear for the release.  That is exactly the word `keybed_push()` queued, so
the port model and the firmware's decode agree.  ⚠ Writes to the tone generator
at 0x10C000 did **not** jump measurably after the press (about 2-3 per second
before and after), so this probe shows the event was *taken*, not that a note
reached the synthesis registers.

## `wsa1_link_traffic.lua` and `wsa1_link_handshake.lua` — ★ the link only sends ONCE

`wsa1_link_traffic.lua` counts every byte written to 0x007C0000 (CPU 1 -> CPU 2)
and 0x00100000 (CPU 2 -> CPU 1), and presses the same key at t=78 s.
`wsa1_link_handshake.lua` then shows why the counts are what they are.

**Result (2026-08-25, `-str 85` and `-str 82`):** CPU 1 -> CPU 2 works, 56 bytes
over a boot.  CPU 2 -> CPU 1 sends **exactly two bytes, once, at t=72 s**, and
never again — including after a key press, which should put a four-byte channel-5
packet on the wire.

The handshake probe pins it: `Link_SendChunk` (0xF999BE) refuses to write its
header until PA bit 3 reads 1, and PA bit 3 is CPU 1's P7 bit 1.  CPU 1 writes
P7 = 0xE7 (bit 1 set, idle) up to t=70, and from t=72 onwards P7 = 0xC5 with
bit 1 **clear** — so every later send spins its full 0x4E20 bound and is dropped.
Measured as 20000-and-more consecutive PA reads of 0xF5 / 0xF7.

⚠ **Not a keybed problem and not a P6-fix problem.** Every CPU 1 port write the
probe sees lands in the high byte of the 0x12/0x13 word, i.e. on P7 and never on
P6, so CPU 1 makes no runtime P6 write at all.  The thing to look at is CPU 1's
`INT0_LinkByte` (0xF8E47F) / `INTTC3_LinkDmaDone` (0xF8E54F): one of them arms
micro-DMA channel 3, drops the busy line, and never raises it again.

## `make_wsa1_eeprom.py` + `wsa1_eeprom_calibration.lua` — is the serial EEPROM wired?

A blank EEPROM cannot answer that question: the firmware's checksum fails and it
zeroes all 61 velocity trims, which is what an unwired device would also give.
`make_wsa1_eeprom.py` writes a *valid* 64x16 image whose 62 calibration bytes are
`0x4B + n`, so the trims sweep the whole of `ToneGen_VelCurve_Trim51`.

```
python3 make_wsa1_eeprom.py <build-tree>/nvram/wsa1r/eeprom
./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 80 -window \
    -autoboot_script .../wsa1_eeprom_calibration.lua
```

**Result (2026-08-25):** 66 chip-select edges and 1650 clock edges before t=5 s,
and RAM 0x0084DA reads

```
-12 -12 -11 -10 -10 -9 -9 -8 -8 -7 -7 -6 -5 -5 -4 -4 -3 -3 -2 -2 -1 -1
0 0 0 0 0 1 1 2 2 3 3 4 4 4 5 5 6 6 6 7 7 8 8 8 9 9 10 10 10 ... 10
```

byte for byte what `Trim51[min(n,50)]` predicts from the ROM at 0xFCC5C9.  So
the Microwire path P6.5/P8.3/P8.4/P8.5 -> `EEPROM_LoadCalibration` (0xFC8B0B) ->
`NoteTrim_BuildFromCalibration` (0xF997FA) works end to end.

⚠ **Delete that nvram file afterwards.**  It is a test fixture, not a dump: a
real SX-WSA1R's EEPROM has not been read, and leaving a seeded one in the build
tree would silently make every later run behave like a calibrated machine.

## Not reproduced here

The `spinscan` that produced the census of unbounded wait loops in prom_c lives
in another session's scratchpad and was not available to copy.  Its findings are
quoted in the driver comments; the script itself is **not** preserved, and that
census should be treated as unreproducible until it is rerun and committed.

A `wsa1_ram_census.py` was cited by an earlier revision of the driver's memory
map comment as the evidence for sizing the CS1 RAM and the CS3 DRAM.  **That
script was never written.**  The citations have been removed; the map now rests
on the runtime milestones above and on the disassembly tree's committed
`scripts/analysis/mamr_reading_elimination.py`.
