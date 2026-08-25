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

## Model-variant detection: is there a WSA1 / WSA1R strap?  (2026-08-25)

Three ROM-side probes, no emulator needed.  They exist because the question
"does one firmware serve both the keyboard and the rack?" can only be answered
against the WHOLE image -- `wsa1-roms-disasm` is 23% substantive, so grepping
the `.s` files would have missed the answer, which lives in `.incbin` regions.

| script | question it answers |
|---|---|
| `wsa1_port_strap_census.py` | every TMP95C061 port-SFR access in all four images, and which reads feed a conditional branch |
| `wsa1_directpage_census.py` | which RAM byte behaves like a mode flag -- few writes, many `cp (a),#imm` tests, wide spread.  `--wide` / `--wide24` repeat it for the 16- and 24-bit-direct forms |
| `wsa1_dis.sh` | disassemble a window of any image, to check a byte-pattern hit is really an instruction |

```
python3 wsa1_port_strap_census.py --gated       # port reads that gate a branch
python3 wsa1_port_strap_census.py --null        # the false-positive floor
python3 wsa1_directpage_census.py --image prom_a --addr 0xc4
python3 wsa1_directpage_census.py --wide24 --all
sh wsa1_dis.sh a 0xF82882 40 0
```

**Both scanners are byte-pattern scanners and both have a measured noise floor**
(`--null`: prom_d is data only, plus byte-shuffled copies of each image).  For
the port census the floor is only ~3x below signal, so nothing from it may be
quoted until `wsa1_dis.sh` has shown it decoding from an earlier instruction
boundary.  22 of the 110 `(0xC4)` sites were checked that way; all 22 were real.

**Answer: yes.**  `prom_a 0xF82882`

```
F82882  21 01        ld A,0x01
F82884  f0 1f c8     bit 0,(PB)        ; PB = SFR 0x1F
F82887  6e 02        jr NZ,0xF8288B
F82889  21 02        ld A,0x02
F8288B  f0 c4 41     ld (0xC4),A       ; the ONLY write to (0xC4) in 512 KiB
F8288E  0e           ret
```

PB bit 0 is an **input**: RESET writes `PBCR = 0x0C` (0xF826xx), and this
firmware's own usage settles the convention -- P7CR = 0x33 makes exactly the two
P7 bits it drives (`set`/`res 1,(P7)`) outputs and the two it only reads
(`bit 2`, `bit 3`) inputs.

`(0x0000C4)` is then compared against **0x01 (37 sites) or 0x02 (72 sites)** and
nothing else, at 109 sites in 17 clusters spanning 89.4% of prom_a.  Nothing
else in the machine has that shape: across all three direct-addressing forms on
both CPUs, no other RAM location has one producer and >100 consumers.  The
runner-up in prom_a's direct page, `(0xC6)`, has 212 tests but 23 writes and is
a bit-0 lock flag.  **prom_c has no mode flag at all**, in any addressing form.

What the two arms do, verified by disassembly:

| site | (0xC4)=1 | (0xC4)=2 |
|---|---|---|
| `0xF8DC25` | calls all four A/D channel scans, then the two software ones | **skips the four A/D scans** |
| `0xF898AD` +6 more | table lookup into `0xF89BB4` | forces the value to a constant `0x40` |
| `0xFF42EE` | display list `0xF580B0..0xF58127` -- MIDI FILE LOAD, MIDI FILE SAVE, LOAD SINGLE SOUND, LOAD SINGLE COMBI. | display list `0xF58127..0xF58162` -- **only** LOAD SINGLE SOUND, LOAD SINGLE COMBI. |
| `0xF90B9F` | descriptor pair `0xF286B8`/`0xF286E4` | descriptor pair `0xF28724`/`0xF28750` |
| `0xF8294C` | requires `(0x2B32) & 7 == 7` | requires `(0x2B30) & 0x70 == 0x70` |

The identification of which arm is which model is **corroboration, not decode**:
the SX-WSA1R service manual's own specification page lists the rack's disk menu
as "DISK LOAD, DISK SAVE, MIDI FILE DIRECT PLAY, DISK FORMAT, LOAD SINGLE SOUND,
LOAD SINGLE COMBINATION" -- no MIDI FILE LOAD or SAVE -- and its continuous
controls as VOLUME plus the DATA ENTRY DIAL, which is two, not six.  Both match
the `(0xC4)=2` arm.  Nothing in the ROM spells either model name.

⚠ MAME's unbound port read returns 0, so the emulated machine reads PB bit 0 low
and **is already running as `(0xC4)=2`**.  That is a testable prediction, not a
setting: a `PORT_CONFNAME` on PB bit 0 would switch the machine between the two.

### Ruled out, with the evidence

* **P5 bit 4** (`0xF95137`) -- a genuine input (P5CR = 0x2C), but it gates one
  call chain of four routines: the diagnostic blinker at `0xF95158`, which
  shifts eight bits out on P5 bit 3.  One branch is not a model strap.
* **P7 bit 1** -- an **output** (P7CR = 0x33 bit 1 set).  It cannot be a strap.
  It is the link's receiver-busy line: `INT0_LinkByte` clears it at `0xF8E4CD`,
  `0xF8E4EC` and `0xF8E522`, each right after `ldio DMA3V,0x0A`, and only
  `INTTC3_LinkDmaDone` restores it (`0xF8E5A8` sel 1, `0xF8E5D6` sel 3,
  `0xF8E5EB` sel 4) plus `Link_ServiceTask`'s abort path at `0xF8E663`.
  Selector 2 deliberately does not restore it.  So it stays low iff INTTC3
  never completes -- a stuck handshake, not a decision.  **There is not one
  `cp (0xC4)` anywhere in `0xF8E000-0xF8FFFF`**, so the link is variant-blind
  and "CPU 1 decided it is a rack and is refusing keybed traffic" is refuted.
* **P8 bit 5 / P9 bit 3** on CPU 2 -- P8 bit 5 is the Microwire EEPROM's data
  line (`0xFC8AE6` reads it inside a 16-iteration loop clocked by `set`/`res
  3,(P8)`, framed by `res 5,(P6)`), i.e. the path this README already documents.
* **prom_d and the EEPROM** -- prom_d is data only and is this project's null
  control; the EEPROM's 62 bytes are per-key velocity trim, read by CPU 2 only,
  and no code branches on any byte of it.

## The control panel: SC1 is the panel link, and the KN5000 is its twin  (2026-08-25)

Three ROM-side scripts, no emulator needed.  Together they answer "which of
CPU 1's two unclaimed subsystems is the front panel, and what does it carry?"

| script | question it answers |
|---|---|
| `wsa1_kn5000_panel_bytediff.py` | does the WSA1's SC1 module share BYTES with the KN5000's control-panel driver, and how many? |
| `wsa1_kn5000_panel_map.py` | do the two agree ROUTINE FOR ROUTINE, or only in scattered idioms?  Gates on the two packet dispatchers being the same instruction |
| `wsa1_panel_tables.py` | every table the panel protocol is decoded from, read out of the ROMs rather than typed, with a self-test |

```
python3 wsa1_kn5000_panel_bytediff.py
python3 wsa1_kn5000_panel_map.py          # exits non-zero if the dispatchers stop matching
python3 wsa1_panel_tables.py --selftest   # exits non-zero if any table moves
```

**Answer: the panel is SERIAL CHANNEL 1**, prom_b `0xF5A800-0xF5B44D`.  Take
that 3,150-byte module and the whole 2 MiB of the KN5000 v10 main program ROM
and list every common substring of 16 bytes or more.  There are **eight, 154
bytes in all, and all eight land inside the KN5000's control-panel driver**
`0xFC3E65-0xFC4C33` — 2,767 bytes, 0.13% of that ROM.  Both machines carry the
same Mitsubishi M37471M2196S panel MCU and both hang it off SERIAL CHANNEL 1.

The correspondence is routine for routine, at the same offset *inside* the
routine (`wsa1_kn5000_panel_map.py` prints all 29 runs ≥ 8 bytes):

| WSA1 | KN5000 | bytes |
|---|---|---|
| `SC1_RxOp6_Run` 0xF5B179 | `CPanel_RX_MultiBytePacket` 0xFC4A40 | 22 of 22 from both entry points |
| `SC1_RxOp6_Run+0x22` | `CPanel_RX_MultiBytePacket+0x22` | 15 |
| `SC1_RxOp0_ThreeByte+0x2E` | `CPanel_RX_ButtonPacket+0x2E` | 12 |
| `SC1_State20_RxFirstByte+0x2F` | `CPanel_SM_RXByte1+0x2F` | 10 |
| `SC1_State04_TxByte1+0x1F` | `CPanel_SM_StartTX+0x1F` | 8 |
| `INTTX1_SC1_Dispatch+0x10` | `INTTX1_HANDLER+0x10` | 8 |
| `SC1_Spin2/6/10/100/500` | `DELAY_{2,6,10,300,1500}_LOOPS` | 10-12 each |
| `SC1_WaitTicks2/6/51` | `DELAY_{2,6,51}_TICKS` | the same 2/6/51 constants |

and the two packet dispatchers are **the same ten-byte instruction sequence
with a different table pointer** — the four immediate bytes are the only
difference, and each names the other machine's table:

```
WSA1  0xF5B0AB: eb c8 b5 b0 f5 00 a3 23 b3 d8   add XHL,SC1_RxOpTable   (0xF5B0B5)
KN5K  0xFC4959: eb c8 65 49 fc 00 a3 23 b3 d8   add XHL,CPanel_RX_PacketHandlers
WSA1  0xF5B28F: eb c8 99 b2 f5 00 a3 23 b3 d8   add XHL,SC1_TxOpTable   (0xF5B299)
KN5K  0xFC4B79: eb c8 85 4b fc 00 a3 23 b3 d8   add XHL,CPanel_LED_PacketHandlers
```

and the two tables have the same size **and the same handler grouping**:

| table | [0] | [1] | [2] | [3] | [4] | [5] | [6] | [7] |
|---|---|---|---|---|---|---|---|---|
| WSA1 RX | ThreeByte | ThreeByte | RxOp2 | Discard | Discard | Discard | Run | Run |
| KN5000 RX | Button | Button | Encoder | Sync | Sync | Sync | MultiByte | MultiByte |
| WSA1 TX | TwoByte | TwoByte | TwoByte | Run | | | | |
| KN5000 TX | LED pkt2 | LED pkt2 | LED pkt2 | LED pktN | | | | |

That names all four WSA1 receive handlers and both transmit handlers, closes
**gap E** of `WSA1-EMULATION-DISASM-GAPS.md`, and settles the one thing
`wsa1-roms-disasm/notes/FINDINGS-prom_b-sc1-link.md` said would settle it:
the module's only external call, prom_a `0xF89800` through thunk `T_F405F0`,
is a 32-entry analogue-control dispatcher indexed by
`((addr & 0xC0) >> 1) | ((addr & 7) << 2)` — the same slot the six on-CPU
analogue controls report through, which is the cross-note lead the gaps doc
flagged as unfollowed.

### and that closes gap B by its own evidence, not by elimination

The ten direction codes `Dev7A_StartDma` (prom_a `0xFE596A`, verified by
disassembly) selects on are **uPD765 command bytes with their MT/MFM flags**,
ten for ten, with exactly the flags each command legitimately takes:

```
RAM -> device  0x4D = MFM|0x0D FORMAT TRACK   0xC5 = MT|MFM|0x05 WRITE DATA
               0xC9 = MT|MFM|0x09 WRITE DELETED DATA
device -> RAM  0xC6 = MT|MFM|0x06 READ DATA   0xCC = MT|MFM|0x0C READ DELETED DATA
               0x42 = MFM|0x02 READ A TRACK   0x4A = MFM|0x0A READ ID
               0xD1/0xD9/0xDD = MT|MFM| 0x11/0x19/0x1D SCAN EQ / LOW-EQ / HIGH-EQ
```

and `INT5_Dev7B_Receive` spins until `status & 0xF0 == 0x80` — RQM=1, DIO=0,
EXM=0, CB=0, "ready for a command" — and then writes **0x08**, SENSE INTERRUPT
STATUS, which is what an FDC interrupt service routine does and nothing else
does (prom_a `0xFE6894`-`0xFE689F`).  The parts list has a **uPD72070GF3BE**.
So `0x7B0004/5` is the floppy controller's MSR/FIFO pair and `0x7A0000` its
DACK data window, with INT7 as DRQ.

⚠ One thing does not fit and is recorded rather than smoothed: the three SCAN
commands need a CPU→FDC data phase, but the firmware puts them in the
device→RAM group.  Ten of ten opcodes match; one of ten directions does not.

### the wire format

```
len = ((first & 0x3F) >= 0x30) ? (first & 0x0F) + 3 : 2     prom_b 0xF5ADD7 / 0xF5AF41

address byte:  bits 7:6 panel id (always 11 on this machine)
               bits 5:3 type  0/1 buttons  2 analogue  3/4/5 sync  6/7 run
               bits 3:0 button SEGMENT 0..15, or, with bit 4 set, analogue SUB 0..7
               => 0xC0..0xCF are segments, 0xD0..0xD7 are analogue controls
```

★ **That reconciles the open warning in `FINDINGS-prom_b-sc1-link.md` sec.6.**
`SC1_TxOp3_Run` emits header + `(n & 0x0F) + 2` = **n+3** bytes; `SC1_RxOp6_Run`
consumes header + address + `(n & 0x0F) + 1` = **n+3**; and the length counter
`(0x2A81)` is set to `(n & 0x0F) + 3` by both state machines.  Three
independent witnesses, one number: the two codecs ARE inverses.

Buttons arrive as `[0xC0|seg][bitmask]`; `SC1_RxOp0_ThreeByte` XORs the mask
against a 32-byte shadow at RAM `0x2B20 + ((addr & 0x0F) + 0x10)` and hands the
foreground three bytes — address, mask, **changed bits**.  Analogue controls
arrive as `[0xD0|sub][value]`; the firmware appends its own `0xFF` third byte.
LEDs go the other way as `[0xC0|reg][bits]`: `Panel_RefreshLeds` (prom_a
`0xF8C456`) walks eight registers, comparing a want-buffer at RAM
`0x20D0..0x20D7` with a sent-shadow at `0x20F0..0x20F7` and sending only what
changed, through `Panel_SetLedRegister` (`0xF8C84A`) into the outbound queue at
`0x2BA0`.  `Panel_DrainInboundQueue` (`0xF8A088`) is the consumer on the other
side, appending `{group, data, changed}` triples to an event array at RAM
`0x2000` with the count at `(0x219A)`, max 7.

### the strap has a panel side, and it agrees

`PB bit 0` — already found from the port census above — reaches the panel
twice: the wire-address→group map is `0xF8A109` for `(0xC4)=1` and `0xF8A189`
for `(0xC4)=2`, and the LED-register→wire-address map is `0xF8C8AC` / `0xF8C8B7`.

| | `(0xC4)=1` | `(0xC4)=2` |
|---|---|---|
| button segments | eleven, 0xC0-0xCA | **nine** — 0xC6 and 0xCA absent |
| analogue over the link | four pots 0xD0-0xD3 + encoder 0xD7 | **one pot 0xD3** + encoder 0xD7 |
| LED registers | eight: C0 C1 C2 C4 C5 C9 CC CD | **seven**: C1 C2 C9 CA CB CC C3 |
| version-LED chord | segment 2 bits 0-2 | segment 0 bits 4-6 |
| factory-clear chord | segment 8 bits 0-2 | segment 8 bits 0-1 |
| third service chord | segment 10 bits 5-7 | segment 3 bits 5-7 |

Two independent confirmations of the identification this README already made
from the manual's specification page:

* the `(0xC4)=2` panel sends **exactly two** analogue addresses, `0xD3` and
  `0xD7`, and the rack's only continuous controls are VOLUME and the DATA
  ENTRY DIAL;
* the variant-1-only channel `0xD1` is the one of the ten whose curve
  (`0xF89CB4`) is a full 8-bit 0..255 map with an **eighteen-entry flat dead
  zone at 0x80** (raw 120..137) and a power-on default of `0x80` — a
  centre-detented bipolar wheel, i.e. a bender, which a rack does not have.

`0xD7`'s dispatch slot (`0xF89825` entry 31) is a bare `scf`: no curve, no
previous-value compare, so every packet is accepted.  A control that must never
be de-duplicated is a RELATIVE encoder, and the KN5000's twin protocol uses the
**same wire address 0xD7** for its endless wheel, as `[0xD7, signed detents]`.
⚠ The signed-step reading is inference from those two facts; the group-0x0F
consumer in prom_a has not been read.

### and one gap the SERVICE MANUAL closes, for free

`WSA1-EMULATION-DISASM-GAPS.md` gap L asks what CPU 1's P5 bit 4 is.  The
manual's self-diagnostic section answers it: *"Connect the CHECKING DEVICE to
CN4 on the MAIN P.C.B. and turn on the CHECKING DEVICE switch … the LED of the
CHECKING DEVICE flashes 8 times.  The first 4 flashes are for the RAM check and
the latter 4 for the ROM check."*  That is exactly `0xF95137`: return at once if
bit 4 is 1, otherwise blink an 8-bit code as **two nibbles** on P5 bit 3.
**P5.4 = the CHECKING DEVICE switch (active low), P5.3 = its LED.**  One
inference remains — the active-low polarity — but the 4+4 nibble structure is
not a coincidence.

### wiring it up

`wsa1-panel-integration.patch` beside this file is the whole job: the HLE device
is `src/mame/matsushita/wsa1_cpanel.{h,cpp}`, and it needs three edits — two of
them to add a byte-level SC1 path to `tmp95c061`, because that core has no
serial engine and **INTRX1 cannot be raised from a driver**: `inte_w()` refuses
to set INTES1 bit 3 from a register write, INTRX1 is not a `TLCS900_*` input
line, and the receive turn puts INTTX1 at level 0 where `tlcs900_check_irqs()`
will not dispatch it.  INT6, P8 and PB need no core work.

⚠ **Today the emulated machine cannot transmit at all**, and this is why:
`SC1_WaitTxDrain` (prom_b `0xF5AB7B`) and `SC1_TxFlush_Body` will not touch the
link unless **P8 bit 5 reads HIGH and PB bit 4 reads LOW**.  MAME's unbound port
read returns 0, so P8.5 reads low, the four-way test never passes, the 200
retries burn and no command and no LED frame ever leaves CPU 1.

---

## Adversarial re-check of the panel report — `wsa1_panel_report_refutation.py`

```
python3 wsa1_panel_report_refutation.py --selftest   # non-zero if any measurement moves
```

Re-derives the load-bearing numbers of the "SC1 is the control panel" report
(`d2f173b`) from the ROM bytes without importing the report's own probes.
The central claim survives and gets **stronger**; four numbers do not.

**Survives, and is understated.** Over the whole 512 KiB of prom_b there are
**4,399** common substrings ≥ 16 bytes with the KN5000 v10 ROM (126,327 bytes).
Exactly **8** of them land in the KN5000 panel driver, and **all 8** come from
the SC1 module. That is a bijection between the two objects, not a cluster, and
it is a much better argument than "8 of 8 landed in 0.13 % of the ROM".
⚠ The count 8 is window-sensitive: a 9th run ≥ 16 B begins at the module's
*last* byte (`0xF5B44D` → KN5000 `0xFC3E4E`) and ends exactly where the panel
driver begins.

**Corrections.**

| the report says | the ROM says |
|---|---|
| panel driver = 2,767 bytes, 0.13 % | `0xFC3E65-0xFC4C33` = **3,535 bytes, 0.169 %** — and `wsa1_kn5000_panel_bytediff.py` already prints 3535 |
| Dev7A_StartDma: 10/10 opcodes, **9/10 directions** | 10/10 opcodes, **7/10 directions** — there are THREE SCAN commands (0xD1/0xD9/0xDD) in the device→RAM group, not one. Null added: only 59 of 256 byte values are legal uPD765 command bytes, so P(ten arbitrary bytes all legal) ≈ 4.2e-7 |
| shadow at `0x2B20 + (addr&0x0F) + 0x10` | `0xF5B0FD` is `and W,0x4F / bit 6,W / jr Z / sub W,0x30 / add L,W`: index = `(addr&0x0F) \| ((addr&0x40)>>2)`. The `+0x10` is **conditional on address bit 6** — true for 0xC0..0xCF, not a rule |
| 0xD1 is "**the one** curve with a dead zone" | 0xD1's 256-entry table has an 18-entry plateau at 0x80 (as reported) **and** 0xD2's 128-entry table has a 13-entry plateau at 0x40, its own midpoint. Variant 1 has **two** centre-detented controls |

**Confirmed exactly, byte for byte:** the eight-run diff (8 / 154 B); the variant
group tables (11 vs 9 button segments, 0xC6 and 0xCA absent in V2; D0-D3+D7 vs
D3+D7); the LED wire tables (`C0 C1 C2 C4 C5 C9 CC CD` vs `C1 C2 C9 CA CB CC C3 00`);
the length rule at `0xF5ADD7`; the RX/TX handler grouping 2/1/3/2 and 3/1 on both
machines; the 10-byte dispatchers; 22 / 12 / 10 / 8 leading bytes at the claimed
offsets; the 2/6/51 tick constants on both machines; the P8.5-HIGH/PB.4-LOW idle
test at `0xF5AB7B`; `SENSE INTERRUPT STATUS` at `0xFE6894`.

| address byte `7:6` = "panel id (always 11 here)" | bits 7:6 pick one of **four banks** of the curve dispatcher at `0xF89800`, and bank 00 is live: six prom_a callers (`0xF8DC63`/`0xF8DC96`/`0xF8DCC9`/`0xF8DCFC`/`0xF8DD54`/`0xF8DD69`) pass `W = 0..5`, the on-CPU A/D channels. Nothing in either ROM compares those two bits against a constant. They select the SOURCE, not an identity |

**What the report did not say, and should have.** CPU 1's ports 5, 8, 9, A and B
are all unbound in `wsa1.cpp` (only `port7_read/write` is set at :1498), so they
read 0. That means PB bit 0 reads 0, `(0xC4)` becomes **2**, and the emulated
machine is today running the **rack** code path through 111 strap gates — not
just failing to transmit on SC1. P5.4 reads 0 for the same reason, so the
CHECKING-DEVICE self-test blink at `0xF95137` runs on every boot.

---

## `wsa1_sc1_handshake.lua` and `wsa1_panel_link.lua` — ★ the panel link, wired and measured (2026-08-25)

These two answer the question the panel HLE had to be judged on: **with
`wsa1_cpanel` wired to CPU 1, does serial channel 1 actually carry traffic in
both directions, and does the machine still boot to the same screen?**

```
cd ~/compartilhado/kn7000_mame_build
DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 40 -window \
    -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_sc1_handshake.lua
DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 200 -window \
    -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_panel_link.lua
```

`wsa1_sc1_handshake.lua` taps SC1BUF (SFR `0x54`), INTE67 (`0x72`) and the SC1
state byte (RAM `0x2A80`). ⚠ `0x54` and `0x55` share one 16-bit word, so both
scripts separate the byte lanes by the access mask — `0x00FF` is SC1BUF, `0xFF00`
is SC1CR. Entering **state `0x20` is the proof that INT6 was dispatched**: that
state is only ever written by `INT6_SC1_PeerRequest` (prom_b `0xF5AC0A`).

### What they found, and the two bugs they found first

**The result (40 emulated seconds, `-str 40`):** CPU 1 clocks out exactly the
seven command frames the disassembly says the SC1 module sends first, **in ROM
order**, with nothing else in between:

```
DF D2   DF 1A   DD 03   DE 80   E3 00   E2 08   E3 10
```

each is answered by the panel, the state machine enters `0x20` **seven times**,
and INTRX1 hands back both reply bytes each time — `tx=49 rx=14`, `state-0x20
entries = 7`. Later in the boot the firmware's LED want-buffer at RAM
`0x20D0..0x20D7` stops being all-zero and its sent-shadow at `0x20F0..0x20F7`
follows it (`wsa1_panel_link.lua`, `ledwant=0401000000000000
ledsent=0401000000000000` from t≈75 s). ⚠ The shadow updating only proves the
firmware QUEUED those frames; what proves they were clocked out is that the
SC1BUF write count steps from 49 to 63 in the same five-second window — two
registers changed, so two frames, and 14 register writes is what two frames cost
once the dummies are counted.

**Before the fixes, the same probe printed `tx=14 rx=0`, `state-0x20 entries=0`
and this, seven times:**

```
5.2757  SC1 state <- 04
5.2757  TX 21   (pc=F5AC06)      <- SC1_StartWordTx's write
5.2757  TX 01   (pc=F5ACFF)      <- SC1_State04_TxByte1's write
5.2757  SC1 state <- 08
5.2757  SC1 state <- 00          <- ABORT
```

Two separate defects, both now fixed, and neither would have been visible
without the byte-level log:

1. **P8 bit 5 read LOW.** `cpu1_p8_r()` merged the unwired bits as `0xD6`, which
   has bit 5 CLEAR, and then only ever *cleared* bit 5 again — it never set it.
   `SC1_State04_TxByte1` samples that pin at `0xF5AD09` having just made it an
   input, and takes `0xF5AD0E` — state and count zeroed, `INTES1 = 0xFF`,
   `(0x2A84) |= 2` — when it reads low. Every frame aborted after two bytes.
2. **Nine of the eleven SC1BUF writes are DUMMIES.** Only
   `SC1_State08_TxFromRing` (`0xF5ADC2`) and `SC1_State10_TxFromRing`
   (`0xF5AE27`) load a byte from the tx ring; the other nine write whatever the
   routine last had in `A`, which is its own P8CR or P8FC shadow (hence the
   `21` and `01` above), purely to step the INTTX1 state machine. The two real
   ones do `or (0x2A87),0x28` — assign TXD1 and SCLK1 — immediately before, and
   the dummies happen with SCLK1's pin function DESELECTED, so on real hardware
   no clock is generated and nothing reaches the peer. The overlay
   `tmp95c061.cpp` now gates its `sc1_txd()` callback on exactly that condition
   in synchronous mode, which is why the panel sees `DF D2` and not
   `21 01 DF 01 D2 01 01`.

★ **The lesson worth carrying:** "the CPU wrote SC1BUF" is not "a byte left the
chip". In I/O-interface mode the clock pin decides, and this firmware uses that
deliberately — it writes SC1BUF with the clock pin parked to advance its own
state machine without transmitting.

---

## The floppy controller: wired, answering, and never used by the firmware  (2026-08-25)

Three scripts, written when `wsa1.cpp` gained a real `upd765a_device` after
`wsa1-roms-disasm/notes/FINDINGS-prom_a-fdc.md` identified the device at
`0x7B0004`/`0x7B0005` + `0x7A0000` as a uPD765-family floppy disk controller.
Run them from `~/compartilhado/kn7000_mame_build` with
`DISPLAY=:0 ./kn7000 <wsa1r|wsa1> -rompath ./roms -skip_gameinfo -window` and
the `-str` given in each row.

| script | question it answers | `-str` |
|---|---|---|
| `wsa1_fdc_probe.lua` | does the FIRMWARE ever touch the FDC?  Counts every access to both register windows, prints each control-register write with its value, and separately watches `Fdc_Request`'s own footprints in work DRAM.  Also snapshots the panel every 15 s | 200 |
| `wsa1_fdc_selftest.lua` | is the controller REACHABLE and does it answer the firmware's own reset sequence?  Replays `Fdc_ResetAndIdentifyMedia` (prom_a `0xFE558B`) byte for byte from Lua through CPU 1's address space, then SPECIFY and SENSE DRIVE STATUS.  Prints PASS/FAIL per step | 20 |
| `wsa1_fdc_button_sweep.lua` | can any single panel button make the firmware use the disk drive?  Presses each declared panel position in turn for half a second after boot, and reports which one (if any) was held when an FDC register was touched | 260 |

**What they measured on the build of 2026-08-25:**

* `wsa1_fdc_probe.lua`, both variants, 200 emulated seconds:
  **`msr_r=0 fifo_r=0 fifo_w=0 ctrl_w=0 dma_r=0 dma_w=0`**.  The firmware never
  touches the floppy controller during boot.  ⚠ The `guard=1 reqblk=8` the probe
  also reports are NOT `Fdc_Request` — they are the boot block's DRAM clear loop
  at `0xF827AF` writing through `0x605A08` and `0x605A30`, which is why the
  probe prints the PC (`F827BC`) with them.
* `wsa1_fdc_selftest.lua`: **5 checks, 0 failures.**  MSR reads `0x80`, not the
  `0xFF` the firmware treats as "no controller" (error `0xFC`); the post-reset
  SENSE INTERRUPT STATUS drain terminates on `ST0 = 0x80` exactly as `0xFE563A`
  requires; SPECIFY consumes its two parameter bytes; SENSE DRIVE STATUS returns
  `ST3 = 0x18`.
* `wsa1_fdc_button_sweep.lua`, `wsa1r`: **88 panel positions swept, 0 FDC
  accesses.**

★ **`ST3 = 0x18` is the honest failure and it is worth knowing by sight.**  RY is
clear, i.e. the drive is not ready, because nothing in the driver turns the
motor on: what does it on the real board is CPU 1's PA bit 3, and that pin's
function is NOT ESTABLISHED (`FINDINGS-prom_a-fdc.md` sec.9), so the driver logs
it and refuses to act on it.  The firmware would report its own error `0x31`.
See gap T in `../WSA1-EMULATION-DISASM-GAPS.md`.

### The control that isolates the motor: attach a disk and nothing changes

The drive slot is real -- `./kn7000 wsa1r -listmedia` reports a `floppydisk
(flop)` accepting `.img`/`.ima` among others, and `-listslots` shows
`fdc:0 -> 35hd`.  So "the firmware would see nothing anyway" is testable
directly, and it was:

```
python3 -c "open('/tmp/blank144.img','wb').write(b'\xe5'*1474560)"
cd ~/compartilhado/kn7000_mame_build
DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 20 -window \
    -flop /tmp/blank144.img \
    -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_fdc_selftest.lua
```

The image loads without complaint and **`SENSE DRIVE STATUS -> ST3` is still
`0x18`** -- byte for byte what it reads with an empty drive.  That is the
control: the "not ready" is NOT "no disk", it is "no motor", so gap T is the
whole of what is missing.  (The image itself is disposable, which is why only
the one-line recipe is committed; 1,474,560 bytes of `0xE5` is the conventional
format filler and any raw 720 KB or 1.44 MB image would do.)

## `tlcs900_16bit_timer_evidence.py` — what does the firmware ask timer 4 for?

Answers the question the INTTR4 work turns on: MAME's `tmp95c061.cpp` never
counts the 16-bit timers, so `INTTR4` can never fire — what exactly is the
firmware programming, and what rate must a correct implementation produce?

```
python3 notes/wsa1-probes/tlcs900_16bit_timer_evidence.py
```

41 byte-level assertions against the two original images, **0 failures**.
Nothing is read out of the emulator.

**WSA1** (IC12 / prom_a): the boot block at `0xF82703`–`0xF8272A` writes
`T4MOD = 0x05` (clock select 01), `T4FFCR = 0x00`, `T45CR = 0x00`,
`TREG4 = 0x0001`, `TREG5 = 0x3D09` = 15625, then `TRUN = 0xB7` (bit 7
prescaler, bit 4 T4RUN, bit 5 T5RUN).  `0xF827CE ldio INTET54,0x03` enables
**INTTR4 at priority 3 and leaves INTTR5 at 0**.  Vector 0x50 → `0xF82EA2`, the
sequencer tick, whose beat length is `0xF82EB1 cp (XHL),0x60` = 96.
Vectors 0x54/0x58/0x5C all point at `0xF82D09`, which is `jr T,0xF82D09` — a
deliberate hang — so **a spurious INTTR5/6/7 would freeze the machine**; they
are safe only because `INTET76` is never written (the single `08 76 xx` byte
hit in the whole image, at `0xFA0C71`, is the middle of `and C,0x08` /
`jrl z,…`, and the script pins those six bytes).

**KN1500** (IC15): `0xFE5FB5`–`0xFE5FCC` programs the *same* registers with the
*same* values — including `ldw (TREG5),0x3D09` — and `0xFE6078` writes the same
`INTET54 = 0x03`.  Its INTTR4 handler at `0xFE6515` is the same routine down to
the direct-page slots (`(0x94)`, `(0x95)`, `cp …,0x60`).

★ **The cross-machine check on the tap.**  One register value, two clocks:

| | fc | φT1 = fc/8 | ÷ TREG5 | ÷ 96 PPQN |
|---|---|---|---|---|
| WSA1 | 28 MHz | 3.5 MHz | 224.0 Hz | **140.0 BPM** |
| KN1500 (`kn1500.cpp:56`, 24 MHz) | 24 MHz | 3.0 MHz | 192.0 Hz | **120.0 BPM** |

Both land exactly on a round default tempo, and only do so if `T4MOD` bits[1:0]
= 01 means φT1 = fc/8 and the counter's period is TREG5.  With MAME's present
`m_timer_pre >> 7` the same registers give 14.0 Hz = 8.75 BPM.

---

## What stands between `ALL INITIAL SETTING!` and a real UI  (2026-08-25)

Five probes, one answer, and the answer is a MISSING CPU CONTROL REGISTER.

| script | question it answers | `-str` |
|---|---|---|
| `wsa1_ui_blockers.lua` | where does each processor spend its time, and does anything ever repaint? PC histogram for both CPUs, plus the tick counter, INTT1/INTT3/INTTR4 dispatch counts (taken at the vector fetch), the LCD, both link directions, the key scanner and the tone generator | 120-200 |
| `wsa1_link_wait_callers.lua` | is `Link_WaitBlockDone` (0xF8E66D) spinning or exiting at once? Separates the `jr Z` fast exit at 0xF8E676 from the 500-tick deadline loop, and prints both screen-id pairs | 200 |
| `wsa1_ui_press_sweep.lua` | can any of the 88 panel positions make the firmware repaint? Per press: LCD writes, SC1BUF writes (transmit only), INT6 dispatches (RAM 0x2A80 <- 0x20) and writes to the panel's button shadow at 0x2B20 | 130-230 |
| `wsa1_draw_task.lua` | are the screen's display lists POSTED, and are they TAKEN? Watches the callback ring at 0x600416 -- read index 0x60040E, write index 0x600412, free count 0x600414 (⚠ the listing's +0xF8/+0xFC/+0xFE are SIGNED displacements, i.e. -8/-4/-2) | 60 |
| `wsa1_kernel_state.lua` | is prom_a's RTOS running at all? Task states at 0x02F4+n*12+9, the eight semaphore counts at 0x035C and their wait queues at 0x033C, and the kernel's pending-tick counter at 0xBE. Snapshots every 10 s | 45 |

**The message.** `ALL INITIAL SETTING!` is prom_a ROM `0xF9422C`, drawn by
`ShowAllInitialSetting` (0xF94210) through SWI7 service 8. It is a
**factory-reset notice on the success path**, not an error: `sub_F82CAB`
(0xF82CAB) reads the two power-fail checksum verdict bits at (0x7FD1) and, when
block 1 at 0x007620 fails, sets `(0x97) |= 0x01` and runs boot PHASE 2
(0xF8283A) over all 25 modules instead of phase 1 (0xF82836). Screen 0xAA's
enter method tests exactly that bit at 0xF94112 and prints the message instead
of its normal content. Measured: `(0x0097)` goes 0x20 -> 0x21 -> 0x03, and
0x7FD1 stays 0x00 -- both checksums fail, correctly, on a machine with no
battery-backed RAM.

**And the machine does NOT stay on it.** A dwell counter at (0x2073) runs down
and the firmware moves family-B screen (0x207C) from 0xAA to 0x01 by itself --
measured at t≈115 s without the timer fixes and t≈23 s with them, in runs where
nothing was pressed.

**Screen 0x01 posts its two display lists and nobody draws them.**
`0xF90D58` enqueues 0x00F90DDB and 0x00F90E4B on the callback ring and signals
semaphore 1 twice; the consumer is the draw task at 0xF8DA00 (task record 2 of
`EntryPoint_Records`, 0xF85E96). Measured: ring write index 0x0008, **read index
0x0000**, free 0x01F7, semaphore 1's count climbing to 02 with its wait queue
EMPTY, task 2 stuck at state 04, and the kernel's pending-tick counter at 0xBE
wrapping at 253 Hz and never drained.

**Because the scheduler is never entered.** `IRQ_Epilogue` (0xF857B7) reads
control register **0x3C** and enters the kernel only if it reads exactly 1;
`Kernel_Dispatch` (0xF85715) reads it again and refuses to reschedule unless it
is 0. MAME has no such register -- `900tbl.hxx`'s `p_CR16` decodes 0x20/0x24/
0x28/0x2C plus the TMP94C241 aliases and sends everything else to
`&m_dummy.w.l` -- and nothing increments it on interrupt acceptance or
decrements it on RETI. Both CPUs' kernels use it: 10 accesses in prom_a, 9 in
prom_c. `wsa1_intnest_experiment.patch` supplies the missing increment and the
machine draws **SOUND MODE** (`screens/wsa1r_intnest_after_sound_mode.png`);
the patch is NOT applied to the source.

**With that patch in, the panel already works.** 72 of 88 positions produce
2 INT6 dispatches and 2 writes to the button shadow per press-and-release -- the
16 that do not are SEG6 and SEG10, which the variant-2 wire map omits. None of
the 88 causes an LCD write on the SOUND MODE screen, which is gap O (no legend
is known for any position), not a transport failure. ⚠ `dSC1` is 0 for every
press and means nothing: that tap counts SC1BUF WRITES, i.e. transmits, and a
button arrives on the receive side.
