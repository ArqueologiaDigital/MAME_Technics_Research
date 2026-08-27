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
is 0. MAME had no such register -- `900tbl.hxx`'s `p_CR16` decoded 0x20/0x24/
0x28/0x2C plus the TMP94C241 aliases and sent everything else to
`&m_dummy.w.l` -- and nothing incremented it on interrupt acceptance or
decremented it on RETI. Both CPUs' kernels use it: 10 accesses in prom_a, 9 in
prom_c.

## ★ cr 0x3C is NOW IMPLEMENTED, and the experiment patch is SUPERSEDED  (2026-08-25)

`wsa1_intnest_experiment.patch` was the hypothesis test. **It is history now, kept
only so the measurement below can be re-derived; do not apply it.** The register is
implemented for real, in the shared CPU core:

| where | what |
|---|---|
| `src/devices/cpu/tlcs900/tlcs900.h` | `uint16_t m_intnest`, and `tlcs900_intnest_accept()` |
| `src/devices/cpu/tlcs900/tlcs900.cpp` | `save_item`, and the clear in BOTH `device_reset()` bodies |
| `src/devices/cpu/tlcs900/900tbl.hxx` | the `p_CR16` decode (0x3C and 0x7C, p1 AND p2) and the `op_RETI` decrement |
| `tmp95c061.cpp`, `tmp95c063.cpp`, `tmp94c241.cpp` | the increment at each interrupt-acceptance site |

Why the experiment was not good enough, point by point:

* it hijacked `m_dummy.w.l`, the shared **"illegal register reference"** scratch word
  (`tlcs900.h:122`), so ANY other undecoded control-register access clobbered the count;
* it had **no decrement** -- it inferred the depth from SR's IFF field at acceptance
  time, because `op_RETI` lives in the shared base class and is unreachable from
  `tmp95c061.cpp`;
* so it was correct only while nothing else touched an undecoded CR.

The real one counts, in both directions, and **saturates at both ends**. Underflow is
not an error to trap: RETIs with no matching acceptance are NORMAL here, because the
firmware forces the register to a value of its own choosing all the time --
`IRQ_Epilogue` writes 0 at 0xF857C3 and then jumps into the scheduler instead of
returning, and `SWI7_ServiceCall_Dispatch` writes 0 at 0xF8E9A8 and leaves by
`pop SR / ret`. Wrapping 0 -> 0xFFFF would make a task-context read look like a deeply
nested interrupt, which is the one answer that breaks these kernels. SWI/TRAP are
deliberately NOT counted, for the same reason: on this firmware they do not return
through RETI, so counting them would be a one-way leak.

**Measured with the real implementation, `-str 45`** -- every row equals the
experiment's, and the final screenshot is **byte-identical** to it
(md5 `491b27987a25e894eb44e322d72b465a`):

|              | no register (`m_dummy`)          | experiment patch          | IMPLEMENTED               |
|--------------|----------------------------------|---------------------------|---------------------------|
| `(0xBE)`     | wraps at 253 Hz, never drained   | `00`                      | `00`                      |
| sem 1        | count `02`, wait queue EMPTY     | count `00`, queue OCCUPIED| count `00`, queue OCCUPIED|
| task 2       | state `04`, never runs           | state `03`, blocked       | state `03`, blocked       |
| ring         | rd=`0000` wr=`0008`              | rd=`0008` wr=`0008`       | rd=`0008` wr=`0008`       |
| LCD writes   | 33623, frozen from t=20          | 80460                     | 80460                     |
| screen       | `ALL INITIAL SETTING!`           | SOUND MODE                | SOUND MODE                |

`screens/wsa1r_intnest_implemented_sound_mode.png`. Reproduce it with:

```
cd ~/compartilhado/kn7000_mame_build
DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 45 -window \
    -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_kernel_state.lua
```

⚠ The implemented run reaches that state **earlier** than the experiment's table
suggests -- LCD 80460 and ring rd=wr=0008 by t=25, not t=45. Same values, sooner.

### ★ The KN5000 is NOT affected, and that is a measurement, not a symmetry argument

The register decode is harmless everywhere, but the INCREMENT changes behaviour for any
machine whose firmware READS cr 0x3C/0x7C. `tlcs900_intnest_evidence.py` scans every
`ldc` in all four SX-WSA1R ROMs and in the KN5000's, and answers it from the bytes:

```
python3 notes/wsa1-probes/tlcs900_intnest_evidence.py
```

```
wsa1_prom_a.ic12   cr 0x3C   4 reads, 6 writes
wsa1_prom_c.ic28   cr 0x3C   4 reads, 5 writes     (the same kernel, second CPU)
wsa1_prom_b / _d   cr 0x3C   none
kn5000 v7/v9/v10   cr 0x7C   0 reads, 6 writes     ** WRITE-ONLY **
kn5000 subprogram  cr 0x7C   0 reads, 6 writes     ** WRITE-ONLY **
kn5000 subcpu/hdae cr 0x7C   none
```

The 10-and-9 counts are exactly the ones the disassembly gives, which is what makes the
scan trustworthy on the KN5000 side too. **The KN5000 runs the same RTOS but keeps the
nesting depth in a RAM word at `(1475)` and only MIRRORS it into cr 0x7C** --
`TaskSched_Init` seeds both, `TaskSched_TimerTick` increments the RAM word and writes the
register, `INTT3_CheckNesting` compares the **RAM word** against 1, and
`INTT3_EnterScheduler` zeroes both (`kn5000-roms-disasm/v10/maincpu/boot/system_handlers.s`).
Nothing on that machine ever reads the register back, so a hardware increment cannot
change what it does. That is also positive evidence for the number: 0x7C is where the /H1's
eight-channel DMA register map leaves INTNEST, and the KN5000 uses 0x7C and never 0x3C
while the SX-WSA1R uses 0x3C and never 0x7C.

### ★ The SX-WSA1 (non-R) reaches SOUND MODE too, with its OWN layout

`screens/wsa1_intnest_sound_mode.png`, captured the same way with
`tools/rigs/snap_at.lua`. It draws **two** parameter panes side by side where the
SX-WSA1R draws one, which is the first screen-level confirmation that the two
systems really are different machines and not a cosmetic split.

### Regression: what this change was checked against

The four files touched are shared by every tlcs900 driver in MAME, so the whole
standing gate was re-run on the built binary (`./tools/gate.sh`):

```
17 passed, 0 failed, 1 skipped
  liveness  kn7000 distinct=12   kn5000 distinct=20   kn6000 distinct=9
            kn6500 distinct=8    kn2400 distinct=4    kn2600 distinct=4
  oracle    kn7000 audio md5 780de131e33a4a0c99d092b57a074247   (unchanged)
  oracle    kn5000 demo  md5 4c8671b68f446cd3f6c10c8784e7748f   (unchanged)
  SKIP      liveness kn1500 -- no screen device
```

Every liveness figure equals the per-model value recorded on 2026-08-14, and the
**KN5000 demo-audio capture is byte-identical to its pinned baseline** -- that is
90 emulated seconds of the tone generator playing, i.e. tens of thousands of
interrupts and RETIs on the TMP94C241, producing exactly the same wav as before.

Machines not covered by the gate, checked by hand:

| machine | CPU | result |
|---|---|---|
| `wsa1`, `wsa1r` | TMP95C061 | verifyroms OK; both now draw SOUND MODE |
| `kn1500` | TMP95C061 | runs 30 s at 99% speed, exit 0, no new warning. MAME gives it no screen device, so there is no visual check -- and note its ROM DOES read cr 0x3C |
| `kn2400`/`kn2600`/`kn6000`/`kn6500`/`kn7000` | MN10300 | not tlcs900 at all (confirmed from `-listdevices`), so these files cannot reach them |

**With that in, the panel already works.** 72 of 88 positions produce
2 INT6 dispatches and 2 writes to the button shadow per press-and-release -- the
16 that do not are SEG6 and SEG10, which the variant-2 wire map omits. None of
the 88 causes an LCD write on the SOUND MODE screen, which is gap O (no legend
is known for any position), not a transport failure. ⚠ `dSC1` is 0 for every
press and means nothing: that tap counts SC1BUF WRITES, i.e. transmits, and a
button arrives on the receive side.

---

# The TMP95C061 timer fixes, and the databook that settles them (2026-08-25, night)

★ **THE DATABOOK EXISTS.** Every note in these trees, this one included, said no TLCS-900
databook was available and derived the timer scale, the 16-bit timer semantics and control
register 0x3C from firmware alone. Toshiba's *TLCS-900 Series CMOS 16-bit Microcontrollers
TMP95C061*, 192 pages, is on bitsavers with an intact text layer.

`tlcs900_datasheet_quotes.py` — **what does the part's own databook say?**

Re-checks 13 quotes against the PDF and prints the six register bit-maps that live in scanned
figures, with their page numbers so a human can re-read them. The PDF is not committed (7.4 MB,
and not ours to redistribute); the script carries its URL, byte size and sha256.

```
python3 notes/wsa1-probes/tlcs900_datasheet_quotes.py /tmp/TMP95c061-ds.pdf
=> 13 PASS, 0 FAIL
```

| question | answer | where |
|---|---|---|
| prescaler taps | `oT1 (8/fc) · oT4 (32/fc) · oT16 (128/fc) · oT256 (2048/fc)` | Table 3.8 (1) p.81 |
| do the 16-bit timers share that prescaler? | yes — one 9-bit prescaler for "8-bit Timer 0/1, Timer 4/5 and Serial Interface 0/1" | 3.8 (1) p.73 |
| `T4MOD` bit 2 | `CLE`: 0 = clear disable, 1 = clear by match with TREG5 | Figure 3.9 (3) p.95 |
| one comparator or two? | two, each generating its own interrupt | 3.9 (5) p.103 |
| TRUN bits 4/5 | T4RUN/T5RUN, "0: Stop & Clear" | Figure 3.9 (10) p.101 |
| which TREG is INTTR4? | "INTTR4 : 16-bit timer4 (TREG4)", V = 0050H | Table 3.3 (1) p.12 |
| is INTNEST hardware-maintained? | "(4) The CPU increments the INTNEST" and RETI "decements" it | 3.3.1 p.11 |
| is the baud tap really fc/4? | `φT0 = fc/4` | 3.11 p.135 |

★ **Why the tap quote closes the argument and the firmware never could.** Three passes derived
`φT1 = fc/8` from ROM constants and each was left with a residual factor of two, because every
firmware constant fixes only the product `fc / D` — the tempo dividend, TREG5 = 15625, TREG1 = 28,
the 1750 multiplier. The databook states the taps as **ratios to fc**, so the shift is 3 whatever
the crystal is, and the remaining `×2` question belongs entirely to `wsa1.cpp`'s `clock()` line.

⚠ **Two arguments that were used for this and must not come back.** "MAME's sibling tmp94c241
already uses 3/5/7/11" is this project's own earlier reading of the same question (MAME
`2905f85348f`), i.e. one derivation counted twice. And the 1750 tempo multiplier is a ratio
between **two taps of one prescaler**, 2048/8 = 256 on the databook scale and 32768/128 = 256 on
upstream's — the same prediction either way. The published "16.4× off" came from pairing this
part's `oT256` with the TMP94C241's `oT1`.

## `tlcs900_timer_control.sh` — the NULL BUILD

**Question it answers:** how much of what was measured is the fix and how much is the machine?
It puts `tmp95c061.cpp` back to upstream timer behaviour and nothing else, so the same probe runs
against the same binary lineage with only the timer model changed.

```
notes/wsa1-probes/tlcs900_timer_control.sh null   && ./build.sh   # measure
notes/wsa1-probes/tlcs900_timer_control.sh fixed  && ./build.sh   # put it back
notes/wsa1-probes/tlcs900_timer_control.sh check                  # which am I in?
```

⚠ It edits the overlay source in place. Always finish with `fixed`; `git diff --stat` on that file
must come back empty, and the rebuilt binary must have the md5 it had before the null cycle (it
did: `c995056d80549b32eb62f6f99ce4212f`, twice).

## `wsa1_inttr4_dispatch.lua` — is INTTR4 dispatched, and into what?

Watches the **acceptance**, not the request flag: `tlcs900_check_irqs()` ends with
`m_pc.d = RDMEML(0xffff00 + vector)`, so a read of 0xFFFF50 happens only when the CPU has accepted
INTTR4, and the data it reads is the handler PC.

```
                        NULL (upstream)          FIXED
  INTT1   FFFF44        30.5 Hz  -> F82D0B       488.3 Hz -> F82D0B
  INTT3   FFFF4C        never in 45 s            first t=19.65 s -> F42D64
  INTTR4  FFFF50        NEVER DISPATCHED         192.0 Hz -> F82EA2   <- the musical clock
  INTTR5/6/7            0                        0     (must stay 0: those vectors are
                                                        jr T,self hang loops at F82D09)
```

⚠ On the KN1500 the same trick is **contaminated** — its boot walks the ROM, so the vector
addresses get read as plain data. The tell is that INTTR5, INTTR6 and INTTR7 all report their
"first dispatch" at the identical timestamp and all resolve to one INTT0 stub. Those three rows are
therefore a read-out of the contamination rate, and INTTR4 minus INTTR5 is the honest number. The
SX-WSA1R has no such scan, which is why its INTTR5/6/7 rows sit at exactly 0.

## `wsa1_boot_milestones.lua` re-run — boot got 4× shorter

| milestone | NULL | FIXED |
|---|---|---|
| SED1330 first write (`pc=F8E822`) | t = 7.2095 s | **t = 0.5003 s** |
| SWI7 text services drawing (`pc=F8F2FE`) | t = 72.2382 s | **t = 19.6181 s** |

⚠ **One earlier claim is corrected by this.** "LCD writes 33623, frozen from t=20" was read as an
INTNEST signature. It is not a clean one: this NULL build has INTNEST implemented and still ends at
33623 LCD writes, because with the slow timers the drawing simply has not happened yet. Both
explanations produce that number, so it does not discriminate.

## `kn1500_timer_regression.lua` — the machine the gate cannot see

`tools/gate.sh` SKIPs kn1500 ("no screen device"), so a timer change could break it silently.
30 s, both builds: **same crt0 RAM test at 0xFA047F-0xFA04A3, same top PCs, same ~99.5% speed**, and
its INTTR4 now dispatches into 0xFE6515 — the sequencer routine its own ROM names, with
`cp (XHL),0x60` at 0xFE6522 for 96 PPQN, the same idiom as the SX-WSA1R's 0xF82EA2.

## `kn1500_ic15_dump_defect.py` — why that machine never boots, and it is not the CPU

Chasing the RAM test found it writing 0xA5/0x5A over the CPU's **own internal I/O registers**. The
cause is in the ROM image: four of IC15's eight 256 KiB blocks are 0xFF in every odd byte, and each
one's even stream is exactly the odd stream of the block 512 KiB above it — 131072/131072, four
pairs, 4 PASS / 0 FAIL. The crt0 region table at 0xF38B24 is inside one of them, so the memory test
walks the whole 24-bit space. Naive reassembly does not repair it. **IC15 needs a re-dump.**

## `tlcs900_16bit_unmodelled_use.lua` — implement it, or write it down?

Watches every 16-bit-timer feature still unmodelled, so the choice is measured rather than assumed:
capture-register reads, software capture, pin capture mode, external clock select, non-zero
`T*FFCR` and non-zero `T45CR`. On the SX-WSA1R over 60 s the only hit is **3 software captures**,
both a side effect of the boot's own `ldio T4MOD,0x05` / `T5MOD,0x02` (bit 5 always reads 1; writing
0 captures), and nothing ever reads CAP1-CAP4 back. Every KN1500 hit is the runaway RAM test above.
So the capture path stays **documented, not invented** — see gaps-doc appendix items 7 and 8.

---

## `wsa1_tg_lifecycle.lua` — is the tone generator's busy model observable at all?  (2026-08-25)

Answers the question a modelled `tg_status_r()` has to answer before anyone believes it: **does
any code path ever GATE a channel**, and does the one risk the model carries ever materialise?
Taps the `0x0010C000` port itself, so it is independent of `VERBOSE`.

```
cd ~/compartilhado/kn7000-emulator
DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 120 -window -nomax \
    -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_tg_lifecycle.lua
WSA1_TG_PRESS=1 DISPLAY=:0 ./kn7000 wsa1 ... -str 90 ...      # also holds C4 from t=60 to t=70
```

**Result, `wsa1r`, 120 emulated seconds:**

| counter | value | what it is |
|---|---|---|
| block-0 writes | 192 | 64 `0x8100` GATE + 64 `0x7E00` FREE + 64 computed |
| gates | 64, all at **t = 0.02** | the boot reset, channels 0..63 in order |
| computed block-0 words | 64, **every one with high byte `0x18`** | `voicerec[+0x29]` |
| **collisions with a lifecycle literal** | **0** | the bound on the model's one risk |
| other per-channel writes | 2118 | |
| globals | 7 | |
| reads, select 0..3 (bank) | 1999 | the poll runs continuously |
| reads, select `0x0180+chan` | 0 | no channel stays busy, so query 2 never fires |

So the busy latch is **live and exercised** — and it ends the boot at zero, which is why the SOUND
MODE screen is byte-identical to the pre-change reference.

**Result, `wsa1`, 90 s, C4 held t = 60..70:** *identical counters*. **Zero additional gates.** A
held key still does not reach a voice — a second, independent instrument for gap C, taken from the
tone-generator end rather than from the link end, and not subject to gap C's own quarantine.

---

## `wsa1_service_entry.lua` — does a power-on SERVICE-MODE chord reach the dispatcher?  (2026-08-25)

Holds the chord for whichever system it is running on from t = 0, releases and re-presses it after
the boot, and reports **four stages** of the panel chain rather than "did the LCD change":

1. `0x2B20..0x2B3F` the per-wire value shadow — did the press reach CPU 1 at all
2. `0x2082` the control byte, `(pressed ? 0x80 : 0) | index` (prom_a `0xF8618F`)
3. `0x2070`/`0x2071` was a screen REQUESTED
4. `0x207C` is the dispatcher on it

★ Using the right instrument is the whole point: 459 of the 654 dispatch-matrix handler slots are
`0xFF42B1`, a bare `ret`, so a position that does nothing on the play screen is *expected*, and an
LCD-write probe cannot tell that apart from a press that never arrived.

```
WSA1_SERVICE_SCREEN=D9 DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo \
    -str 80 -window -nomax -autoboot_script .../wsa1_service_entry.lua
```

**Result (`wsa1r`, SEG1 bit 2 = PANEL CPU CHECK): FAIL, and the failure is informative.** The press
and the release each produce exactly one store, at the right instants — so the link and the panel
HLE both work — but the store lands at `0x2B20` carrying `0xC1` instead of at `0x2B31` carrying
`0x04`. One byte out of position, deterministically. That is **gap Y** in
`../WSA1-EMULATION-DISASM-GAPS.md`, and it is now the top item on that list.

**Result (`wsa1`, keybed D4+D5 = PANEL CPU CHECK): FAIL, and it CONFIRMS the ROM decode on the way.**
The script also prints CPU 2's 61-key state bitmap, because the chord's own criterion is a popcount:

```
cpu2 keybitmap 0x0000FFF0 = 00 00 00 04 40 00 00 00  popcount=2 (the chord needs 2)
```

Byte +3 bit 2 = key 26 = D4 and byte +4 bit 6 = key 38 = D5 — **exactly** the pair `sub_F9530B`
tests for screen `0xD9`, held steadily from t = 5 s. So the keybed model, the scanner, CPU 2's
bitmap builder and the whole bit -> key decode are right, measured against a criterion that could
have failed. `(0x2070)` is nonetheless never written with `0xD9`, which puts the failure on CPU 1's
side of the link remote read — see the `KEY0..KEY5` comment in `wsa1.cpp` for the two candidates
that are ruled out and the one that is not.

---

## `screens/tgmodel/` — the four regression snapshots for the 2026-08-25 tone-generator work

Captured with `tools/rigs/snap_at.lua` at `SNAP_AT=45`:

```
cd ~/compartilhado/kn7000-emulator
SNAP_AT=45 DISPLAY=:0 ./kn7000 <machine> -rompath ./roms -skip_gameinfo -window -nomax \
    -snapshot_directory ~/compartilhado/kn7000_mame/notes/wsa1-probes/screens/tgmodel \
    -autoboot_script ~/compartilhado/kn7000_mame/tools/rigs/snap_at.lua
```

| machine | md5 | verdict |
|---|---|---|
| `wsa1r` | `491b27987a25e894eb44e322d72b465a` | **byte-identical** to `screens/wsa1r_timerfix_t45_sound_mode.png` |
| `wsa1`  | `7ea521458d71732a9360f65611782a06` | **byte-identical** to `screens/wsa1_intnest_sound_mode.png` |
| `kn5000`| `d015011bdc084fa1225eeb167b2dcdde` | **byte-identical** to `screens/kn5000_timerfix_t45_play_screen.png` |
| `kn7000`| `7b8912d36fc43655866ad2fbbe15eed5` | LCD identical; **the four layout faders sit differently** |

⚠ The kn7000 difference is NOT a driver change — `kn7000.cpp` was not touched, the md5 is stable
across three consecutive runs, and the pixels that differ are the physical slider widgets in the
bottom-left of the layout, which come from the cfg directory. The standing gate is the authority
here and it passed 17/0/1 with the recorded `kn7000` liveness hash `316cd785` and the audio oracle
md5 `780de131e33a4a0c99d092b57a074247` unchanged.

---

## `wsa1_rack_service_chord.py` — the four SX-WSA1R service entries, byte by byte  (2026-08-25)

The four `CP_SEG1` `PORT_NAME`s in `wsa1_cpanel.cpp` are the first (position → function) pairs any
panel bit on this machine has, so they get a script rather than a reading. 25 checks, 0 failures:

```
python3 notes/wsa1-probes/wsa1_rack_service_chord.py
```

It asserts the whole chain: RESET reaches the test (`call 0xF40148` at `0xF827F8`, thunked to
`0xF952FC`); the strap splits rack from keyboard (`cp (0xC4),0x02`); `sub_F953CD` reads `(0x2B31)`
and compares it for equality against `02/04/08/10/20`; the four `ld (XIX),0xD9..0xDC` stores and the
two `ld (0x2071),0x80`; that `(0x2B31)` really is wire `0xC1` = SEG1 under the shadow-index formula;
and the RESET **order** — this chord is the second of four, and the ROM-VERSION test that follows it
never returns once matched (`jr T` backwards at `0xF829A3`), so a held ROM-version chord pre-empts a
service screen this test already latched.

| SEG1 bit | value | screen | title |
|---|---|---|---|
| SW1 | `0x02` | — | recognised, no screen |
| SW2 | `0x04` | `0xD9` | PANEL CPU CHECK |
| SW3 | `0x08` | `0xDA` | SINE WAVE CHECK |
| SW4 | `0x10` | `0xDB` | PANEL SW&LED CHECK |
| SW5 | `0x20` | `0xDC` | screen cycler |

---

## SX-WSA1R panel switch matrix: schematic trace, and its ROM cross-check

`wsa1_sch_TRACE.md` records the coordinates every net claim about the CP1/CP2
schematic rests on, and `wsa1_sch_hscan.py` / `wsa1_sch_vscan.py` /
`wsa1_sch_crop.py` are the three probes that produced them. They read a page
rendered by `pdftoppm` and report black runs, so the manual stays the source and
nothing is taken on eyeball.

`wsa1_sch_vs_rom_matrix.py` then checks that reading against prom_a, and this is
the part that could have failed:

```
python3 notes/wsa1-probes/wsa1_sch_vs_rom_matrix.py
```

The variant-2 switch->LED word table at prom_a `0xF95088` is 9 segments x 8 bits;
a switch that does not exist stores `0x0000`. Relabelling its nine rows as the nine
wired segments (0-5, 7-9; 6 and 10 are the dead stubs on IC1 pins 40 and 33), its
zero pattern is **exactly** the schematic's empty cells:

* `SEG2` bit 7 alone is zero -- the one missing cell in CP1's 6x8, `SW24`/`D24`,
  absent from the parts list too (`S1~23, 25~48`);
* `SEG7` keeps bits 0-3, `SEG8` bits 0-1, `SEG9` bits 0-4 -- CP2's three columns
  of 4, 2 and 5 switches;
* 58 populated positions = 47 on CP1 + 11 on CP2, the parts-list counts exactly.

Those three also fix the **bit order**, which the four power-on service keys cannot:
keys 2/3/4/5 sit on rows SW2..SW5, a set that survives reversal unchanged, whereas
`SEG8`'s two switches at bits 0,1 would have to be at bits 6,7 and `SEG2`'s hole at
bit 0. So `packet bit b = IC1 SWb`, from the ROM, against the paper.

The table's two catch-all words split the panel exactly where the schematic's own
printed legends change: `0x0608` covers keys 0-7, 8, 9, +/-, ENTER **and SEG3 bits
5-7**, while `0x0604` covers PAGE v/^, COMPARE, both five-key LCD columns and the
sixteen under-LCD keys. That is an independent ROM-side witness that SEG3 SW5-7 are
the numeric-entry trio (-1, +1, EXIT) and SEG3 SW0-4 the LCD soft keys, which the
board layout II-27 shows and the schematic does not label.

It references 18 distinct lamp bits -- the rack's lamp count (D116-119, D120-123,
D130, D131, D138-141, D160-163). `SEG0` splits 4+4 across two lamp registers,
matching D116-119 (green, PLAY/EDIT MODE) against D120-123 (red, BANK); `SEG7`'s
four MENU keys take reg4 bits 0-1 and reg5 bits 0-1, matching D160/D161 against
D162/D163. `reg6 bit 3` is the lamp of the whole numeric group, i.e. the
MIDI/NUMBER PAD indicator D131.

---

## ★ THE CONTROL PANEL, drawn and wired -- 2026-08-26

`src/mame/layout/wsa1r.lay` is the SX-WSA1R's front panel: all 58 switches bound, 14 of its 18
lamps bound, the emulated 320x240 SED1330 panel placed inside the drawn bezel at 1:1. It is
GENERATED from Felipe's artwork (`~/compartilhado/KN7000/wsa1r_artwork/wsa1r_cpanel.svg`, which
reproduces the service manual's ARRANGEMENT OF CONTROL PANEL drawing, PDF page 5) by
`tools/gen_wsa1r_lay.py`; do not hand-edit it.

```
python3 tools/wsa1_svg_geometry.py --selftest    # 9 landmark bounds, incl. the 320x240 LCD
python3 tools/gen_wsa1r_lay.py                   # write src/mame/layout/wsa1r.lay
python3 tools/gen_wsa1r_lay.py --check           # fail if the .lay OR wsa1_cpanel.cpp's
                                                 #   PORT_NAMEs have drifted from the table
python3 tools/gen_wsa1r_lay.py --preview p.svg   # compose the art + the label boxes, to eyeball
```

### The three probes the bindings rest on

| script | question it answers | run |
|---|---|---|
| `wsa1_lamp_identification.py` | which `led#` output is which panel lamp? Proves from the INSTRUCTIONS that prom_a's switch->LED word at `0xF95088` is `(register << 8) \| bit mask` -- `sub_F94E1C` does `ld WA,(XHL)` and calls `0xF40670` = `jp 0xF8C846`, whose `ld W,(XIX+W)` indexes the register->wire table -- then reads off the 14 one-to-one lamps. 25 checks | `python3 notes/wsa1-probes/wsa1_lamp_identification.py` |
| `wsa1_sc1_ring_phase.lua` | is CPU 1's SC1 receive ring in phase? Logs every write to the read index `(0x2A90)` and write index `(0x2A92)` with the PC, so a mid-frame rewind at `0xF5AC4A` names itself | `-autoboot_script .../wsa1_sc1_ring_phase.lua` |
| `wsa1_softkey_columns.sh` | which five-key column beside the LCD is SEG3 and which is SEG9? Puts the DISK menu up (4 entries left, 2 right) and presses all ten soft keys | `sh notes/wsa1-probes/wsa1_softkey_columns.sh` |

and `tools/rigs/wsa1r_layout_button.lua` drives ONE button end to end, reading the `inputtag` /
`inputmask` **out of the .lay** so a wrong binding shows up as a wrong result:

```
cd ~/compartilhado/kn7000-emulator
BTN="MENU DISK" SNAP_AT=45 DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -window \
    -nomax -resolution 1600x520 -snapshot_directory /tmp/o \
    -autoboot_script ~/compartilhado/kn7000_mame/tools/rigs/wsa1r_layout_button.lua
```

`BTN2="LEFT column, 3rd"` adds a second press after the first has settled -- that is the form that
settled the soft-key columns.

### What it measured

| press | shadow while held | family-B screen | lamps |
|---|---|---|---|
| MENU DISK (`CP_SEG7` 0x08) | `(0x2B37) = 08` | `01 -> 40`, the DISK menu | `led8` off, `led41` **on** |
| BANK USER 1 (`CP_SEG0` 0x10) | `(0x2B30) = 10` | `01 -> A1` | `led0` **on**, `led2` off |
| PLAY MODE COMBI (`CP_SEG0` 0x02) | `(0x2B30) = 02` | `01 -> 02` | `led9` **on**, `led8` off |

Three independent agreements per row: the schematic's printed legend, the ROM's lamp map, and what
the firmware actually does. `screens/wsa1r_layout_disk_menu.png` is the DISK menu;
`screens/wsa1r_layout_t45_sound_mode.png` is the panel at t = 45 s.

⚠ **None of this worked before the attention-line guard** in `wsa1_cpanel.cpp`'s `request_tick()`
-- see gap Y in `notes/WSA1-EMULATION-DISASM-GAPS.md`, now closed. Regression after that change:
`kn5000`, `kn7000` and `wsa1` t=45 snapshots are byte-identical to their recorded baselines, and
`wsa1r`'s 320x240 LCD region (at 633,85 inside the 1600x500 layout) is byte-identical to
`screens/wsa1r_timerfix_t45_sound_mode.png`.

### Drawn but NOT bound, and why

* the four REALTIME CREATOR ring lamps -- the ROM fixes the SET (`led16`, `led17`, `led24`,
  `led25`) but not the order;
* the floppy activity lamp and eject button -- they belong to the FDD, which exposes neither;
* CONTRAST (VR2 is an LCD bias pot whose wiper goes back to MAIN as `VO`, not a panel-MCU input),
  POWER, PHONES -- no ioport exists for any of them;
* the REALTIME CREATOR ball itself -- board MB2's triple-gang VR2 reports JOYX/JOYY to MAIN's own
  A/D (PDF p.19), so it is not a panel control at all.

### The SX-WSA1 keyboard gets NO layout

Its panel is a different board -- two more scan columns (SEG6, SEG10) and three more pots, two of
them centre-detented -- and no SX-WSA1 document exists in these trees. Reusing the rack's artwork
would be a fabrication, so `wsa1r(machine_config&)` sets the layout and `wsa1(machine_config&)`
deliberately does not.

## `wsa1_name_path.lua` — why the SOUND MODE screen shows `Sound Name *****`

**Question:** the screen shows a placeholder where a sound name belongs. Is that a
failed inter-CPU exchange, or something else?

    cd ~/compartilhado/kn7000-emulator
    ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 95 \
        -autoboot_script wsa1_name_path.lua -autoboot_delay 1

Counts CPU 2's reads of `prom_d` (0xF00000-0xF7FFFF), and every write to each
side's link port, tallied by command byte.

**Two things had to be true, and only one of them was.**

1. `Sound Name *****` is **not corruption** — it is a literal string in
   `prom_a` at `0x41C54`, with `Combi Name *****` at `0x41CCC`. It is the
   firmware's own "no name available" fallback, so the machine is *choosing* to
   print it. `R1-001` is displayed alongside, so a sound IS selected.
2. The tone database `prom_d` was **never mapped** into either address space --
   only declared as a `ROM_REGION`. Fixed: it is 512 KiB at `0x00F00000` on
   CPU 2's bus, and this probe now measures **616 reads** of it, so that half is
   live.

**What still blocks it: the link.** Measured 2026-08-27, 95 s boot:

    promd_reads = 616      CPU 2 is reading the database
    cpu1_link_writes = 46  CPU 1 is talking
    cpu2_link_writes = 2   CPU 2 answers twice, then nothing
    CPU 1 commands include E2 x4 -- remote block read -- and E1 x1

CPU 1 issues **four `0xE2` remote block reads** and CPU 2 never returns the
blocks. That is emulation **gap C**: CPU 1 stops asserting P7 bit 1 (the
receiver-busy line) after its first exchange, so CPU 2 is locked out for the rest
of the run.

⚠ So the name is downstream of gap C, not of a missing ROM. Mapping `prom_d` was
necessary and is not sufficient; the same wedge also drops keybed notes.

✅ **Gap C's cause was found on 2026-08-27 and it was in the CPU core** —
`tmp95c061_device::tlcs900_check_irqs()` dispatched to the CPU an INT0 that
micro-DMA channel 3 was armed for, so the payload byte was thrown away and
`INTTC3` never fired at all. The sentence that used to stand here, "because
`INTTC3` never completes", was built on an aliased tap. See the
`wsa1_udma3_audit.lua` section below.

---

## `wsa1_udma3_xref.py`, `wsa1_udma3_audit.lua`, `wsa1_int0_race.lua`, `wsa1_int0_steal.lua` — the link wedge, cause found

**Question:** `wsa1_link_stage.lua` reported that micro-DMA channel 3 "completed twelve times"
while no link message was in flight, each completion seeing selector `(0x6007DA) == 0` and doing
nothing. Why?

**Answer: it never completed at all. All three of that probe's counters were aliased.**

### ⚠ The measurement lesson, first, because it is the reusable part

A read tap placed on a routine's **entry address** is not a counter of that routine's entries.
`tlcs900_device::RDOP()` keeps a four-byte prefetch queue and reads `m_pc + 3` on every opcode
byte (`../mame/src/devices/cpu/tlcs900/tlcs900.cpp:81-99`), and all of those go through
`m_program->read_byte()`, so **a tap fires while the CPU is still three bytes short of the
address**. `INTTC2_uDMA2Done` ends with `reti` at `0xF8E54E` and `INTTC3_LinkDmaDone` begins at
`0xF8E54F`: a tap on `0xF8E54E-0xF8E54F` counts two reads per INTTC2 *return*. Six INTTC2s ⇒
"twelve INTTC3 entries".

Same trap twice more in the same script: `0xF8E47E-0xF8E47F` names INT0's entry but `0xF8E47E` is
the previous routine's `ret`, and `0x7E-0x7F` names DMA3V but `0x7E` is **DMA2V**, which the
transmit block arms from nine sites.

`wsa1_udma3_xref.py` is the byte census that fixes the counters, and it is the thing to run before
trusting any of these numbers again:

```
python3 wsa1_udma3_xref.py
```

* every reference to `0x6007DA` in prom_a, prom_b and prom_c — **twelve, of which exactly one is a
  read**, `ldw_da bc,(0x6007da)` at `0xF8E555` inside INTTC3. So a read tap on that word is an
  exact INTTC3-entry counter with no prefetch shadow;
* every `ldio DMAnV,imm8` site, DMA2V and DMA3V told apart. Inside the converted link block the
  set is exact: **DMA3V at `0xF8E24F 0xF8E4CA 0xF8E4E9 0xF8E51F 0xF8E5BD 0xF8E65A 0xF8E683`**
  (four arms with `0x0A`, three aborts with `0x00`) and **DMA2V at nine sites, all
  `ldio DMA2V,0x12`**;
* the `07 39` boundary bytes at `0xF8E54E/0xF8E54F` that make the aliasing concrete.

The script exits non-zero if any of that drifts.

### What is actually happening (`wsa1_udma3_audit.lua`, 100 s boot)

```
EXACT   DMA0V=0 DMA1V=0 DMA2V=5 DMA3V=5
        arms: DMA2V=0x12 x5  DMA3V=0x00 x4  DMA3V=0x0A x1
EXACT   INTTC3 entries (reads of 0x6007DA) = 0
LEGACY  0xF8E47E-7F reads=2   0xF8E54E-4F reads=10   0x7E-7F writes=10
PORT    cpu1 reads of 0x7C0000 = 1   cpu1 writes = 41
PORT    cpu2 writes to 0x100000 = 2 (= INT0 asserts on cpu1)   cpu2 reads = 1
DMAC3   12 samples via (0x6007DF): 1 1 1 1 1 1 1 1 1 1 1 1     (armed with 1, never decremented)
ERRCNT  0x6007DC=1 0x6007E1=3
```

The legacy counters are printed **in the same run** as the exact ones, which is what pins the
aliasing: `0xF8E54E-4F reads=10` against `INTTC2 dispatched 5 times` = two prefetch reads per
INTTC2 return, and `0x7E-7F writes=10` = 5 DMA2V + 5 DMA3V.

One message is received in the whole boot, at t = 70.843 s:

```
t= 70.843  CPU2  -> 0xC0          header, link channel 6
t= 70.843  RD    port -> 0xC0     INT0_LinkByte reads it
t= 70.843  SEL:= 1                (0x6007DA) = 1, "general command"
t= 70.843  ARM   DMA3V=0x0A       DMAC3=1 DMAD3=6007B3 DMAS3=7C0000 DMAM3=00
t= 70.843  P7:=  0xC1  (bit1=0)   receiver-busy asserted
t= 70.843  CPU2  -> 0xFB          the payload byte ... and nothing ever reads it
   ... twelve Link_ServiceTask samples, DMAC3 stuck at 1 ...
t= 72.012  ARM   DMA3V=0x00       the eleven-equal-samples watchdog aborts
t= 72.012  P7:=  0xCF  (bit1=1)   0x6007DC := 1
```

### Which of the two possible causes it is (`wsa1_int0_race.lua`)

`tlcs900_process_hdma()` moves a byte only when the channel's trigger flip-flop is set; for
`DMA3V = 0x0A` that is **INTE0AD bit 3**, INT0's own request bit. INTE0AD is readable at SFR
`0x70` (`inte_r`, `tmp95c061.cpp:184`), and across the whole wedge it reads **`0x81` — bit 3
clear**. So the request was raised and then *consumed by something that was not the DMA engine*.
The driver's queued `set_input_line(CLEAR_LINE)` is exonerated: the byte is still in the latch and
nothing ever reads it.

### The cause (`wsa1_int0_steal.lua`)

An interrupt dispatch is the only thing that reads the vector table
(`m_pc.d = RDMEML(0xffff00 + vector)`), so a read tap on `0xFFFF28` counts INT0 dispatches to the
CPU **exactly**, with no prefetch shadow. Measured:

```
t= 70.8434  CPU2 -> latch 0xC0   (#1)
t= 70.8434  DISPATCH INT0   #1   P7=0xC3(b1=1 b2=0) INTE0AD=0x89(req=1) DMAC3=0
t= 70.8434  CPU1 reads latch -> 0xC0   (#1)
t= 70.8434  DMA3V := 0x0A        DMAC3=1
t= 70.8434  CPU2 -> latch 0xFB   (#2)
t= 70.8435  DISPATCH INT0   #2   P7=0xC5(b1=0 b2=1) INTE0AD=0x89(req=1) DMAC3=1
======== dispatch totals ========
  INT0     2      INTTC2   5      INTTC3   0      c1r 1      c2w 2
```

**The CPU took the interrupt that micro-DMA channel 3 was armed for.** On a TLCS-900/H, writing
`DMAnV` hands one vector to a DMA channel and the CPU stops seeing it — which is exactly what
prom_a's own comment at `INT0_LinkByte` assumes ("once this handler arms the DMA, the same
interrupt goes to the DMA engine instead"). And because `INT0_LinkByte` opens with
`bit 2,(P7)` / `jrl nz,return` at `0xF8E489`, and CPU 2's strobe had bit 2 set by then, that second
entry returned **without reading the port at all**: the byte was neither delivered to the DMA nor
consumed by the CPU. `DMAC3` sticks at 1, `INTTC3` never fires, `P7` bit 1 never rises, and every
later CPU 2 → CPU 1 packet — the `0xE2` block answer that carries the sound name, and every keybed
note — is dropped by `Link_SendChunk`'s wait at prom_c `0xF999D0`.

### The fix: OVERLAY FIX 6 in `tmp95c061.cpp`

`tmp95c061_device::tlcs900_check_irqs()` had no idea micro-DMA existed. It runs at the **top** of
`execute_run()`'s loop while `tlcs900_check_hdma()` runs at the **bottom**, so the CPU won every
race. The fix skips any interrupt a micro-DMA channel is currently armed for, with the trigger
vector computed the way `tlcs900_process_hdma()` computes it, `(DMAnV & 0x1F) << 2`.

**This is not a new idea and not a driver workaround — MAME already does it for the sibling
part.** `tmp94c241_device::tlcs900_check_irqs()` carries the same loop under the comment "HDMA
priority: skip interrupts targeted by active HDMA channels". `tmp95c061.cpp` was the odd one out,
exactly as it was for `m_check_irqs` (OVERLAY FIX 4 and 5).

### A/B, same probe, same 100 s boot

| counter | before FIX 6 | after FIX 6 |
|---|---|---|
| `INTTC3` entries (reads of `0x6007DA`) | **0** | **1**, selector **2** |
| CPU 1 reads of `0x7C0000` | 1 | **21** |
| CPU 2 writes to `0x100000` | 2 | **71** |
| `DMA3V := 0x0A` arms | 1 | 2 |
| bytes landed in the `0xE1` header buffer | 9 | 16 |
| `LEGACY 0xF8E54E-4F reads` | 10 (= 5 INTTC2 x 2) | 13 (= 6 INTTC2 x 2 + 1 real INTTC3) |

and the exchange that used to die after two bytes now runs the protocol:

```
t= 70.843  CPU2  -> 0xE1        the remote-block ANSWER to CPU 1's 0xE2
t= 70.843  RD    port -> 0xE1   INT0_LinkByte reads the header
t= 70.843  SEL:= 2              (0x6007DA) = 2 = "arm the payload"
t= 70.843  ARM   DMA3V=0x0A     six-byte {LE32 dest, LE16 count} record
t= 70.843  ...six payload bytes absorbed by micro-DMA...
t= 70.843  INTTC3 selector=2    ★ INTTC3_LinkDmaDone runs, for the first time ever
t= 70.843  ARM   DMA3V=0x0A     INTTC3_Sel2_ArmPayload re-arms for the block
t= 70.843  SEL:= 4              and hands the completion to selector 4
```

### ⚠ The next blocker, and it IS in the driver

With FIX 6 in, **CPU 2 wrote 71 bytes and CPU 1 read 21**. The one-byte latch is being
overwritten mid-burst: the sender's micro-DMA channel 2 empties a whole block into it inside a
single MAME timeslice, while the receiver only drains it when its own timeslice runs. That is
precisely the failure `wsa1.cpp`'s "WHAT THIS MODEL DOES NOT GUARANTEE" paragraph predicted.

**⚠ The KN5000's remedy was tried and MEASURED, and it is not enough.** Adding
`machine().scheduler().abort_timeslice()` to the end of both link write handlers — the fix
`notes/upstream-patches/kn5000-26-intercpu-latch-int0-handshake.patch` uses for the same kind of
latch — moved CPU 1's reads from **21 to 24** out of the same 71 writes, and `DMAC3` was still
armed from a corrupt record. It is therefore **not committed**; the negative result is recorded in
`wsa1.cpp` so nobody spends the rebuild on it twice.

### `wsa1_link_burst_timing.lua` — which of the two it is, and it is the quantum

The probe prints the emulated time of every latch access to microsecond resolution, which
separates two causes the counts cannot tell apart: the sender's bytes being correctly spaced but
bunched inside MAME's 50 µs quantum (a driver problem), versus timer 2 pacing micro-DMA channel 2
faster than the real part does (a CPU-core problem, the same family as OVERLAY FIX 1). Measured
over a 75 s boot:

```
SENDER GAPS  n=70  min=5.857 us  median=6.036 us  mean=7.453 us  max=75.679 us
TOTAL cpu2 writes=71  cpu1 reads=24   (quantum is 50 us; 28 MHz CPUs)
```

**6 µs is a plausible hardware pacing, so the timer is not the suspect.** ⚠ Reading T23MOD = 0x0E
as selecting the φT16 prescaler tap, `TREG2 = 5` at fFPH = 14 MHz gives 5 × 16 × 71.4 ns =
**5.71 µs**, which is where the measurement lands — but that bit decode is taken from the
TLCS-900/H convention and NOT from a databook this tree has, so treat the agreement as
corroboration, not proof. Nothing below depends on it: what decides the fix is the ratio of the
measured 6 µs byte-time to the quantum. The defect is that the quantum is **50 µs = eight
byte-times**: CPU 1 runs up
to eight bytes ahead, CPU 2 then overwrites the one-byte latch eight times, and CPU 1 collects
only the last. The reads bear it out — each one lands ~40 µs after the byte it took.

That also explains why `abort_timeslice()` could not help: it ends the *sender's* slice, but the
receiver is already ahead in local time and MAME cannot rewind it.

**Fix:** `machine().scheduler().perfect_quantum(attotime::from_usec(20))` in both link write
handlers, so the processors interleave per instruction for one burst-length window and pay for it
only while a message is moving. 20 µs outlasts the 6 µs gap to the next byte, so each byte of a
burst re-arms the window and the whole message stays in lockstep.

**Measured with it in, same probe, same 100 s boot:**

| counter | before FIX 6 | FIX 6 only | FIX 6 + perfect_quantum |
|---|---|---|---|
| CPU 1 → CPU 2 bytes written / read | 41 / — | 43 / — | **5070 / 5070** — no loss |
| CPU 2 → CPU 1 bytes written / read | 2 / 1 | 71 / 21 | **711 / 706** |
| `DMA2V` arms (messages sent) | 5 | 6 | **985** |
| `INTTC3` entries | 0 | 1 | 1 |

The link is no longer the bottleneck: both directions now carry thousands of bytes essentially
without loss, where before the fix the machine managed one received message in a whole boot.

⚠ **CORRECTED 2026-08-27 by the adversarial re-check at the end of this file.** That sentence
reads more into the byte counters than they carry. In the same run CPU 1's `INT0_LinkByte` is
dispatched **once** in 95 s and `INTTC3` runs **once**: 705 of the 706 reads of `0x7C0000` are one
runaway micro-DMA transfer armed with a corrupt count. The CPU 2 → CPU 1 direction still delivers
exactly ONE message per boot, the same as before the quantum change; what the quantum fixed is the
CPU 1 → CPU 2 direction. See `wsa1_fix6_refutation.lua` / `wsa1_wire_window.lua` below — including
the five bytes that are lost and the `BURST_QUANTUM_US` value that stops losing them.

### ⚠ AND THE SCREEN STILL SAYS `Sound Name *****`

Captured at t = 95 s with `tools/rigs/snap_at.lua` on exactly this build —
`screens/wsa1r_udma3fix_t95_sound_mode.png`. **So the link wedge was a real blocker but not the
last one**, and nothing above should be read as having fixed the sound name.

What the same run says about where to look next: CPU 2 answers CPU 1's `0xE2` with an `0xE1`
block, `INTTC3_Sel2_ArmPayload` re-arms channel 3 and writes selector **4** — and **selector 4
never arrives**. `INTTC3` entries stay at 1 for the whole boot and `DMAC3` sits at **16741**
across all twelve `Link_ServiceTask` samples, while CPU 2 sends only ~700 bytes in total. Either
that count is still being read from a bad record, or the block is sent in chunks the receive side
is not being re-armed for. `wsa1_udma3_audit.lua` already prints everything needed to tell those
apart — the selector writes, the `DMA3V` arms and the destination buffers — so start by dumping
the six bytes at `0x6007D3` at the moment `INTTC3_Sel2_ArmPayload` reads them.

---

## `wsa1_fix6_refutation.lua`, `wsa1_e1_record.lua`, `tlcs900_dmav_census.lua` — the adversarial re-check of OVERLAY FIX 6

**Question:** the section above claims (a) micro-DMA channel 3 completed *zero* times before FIX 6,
(b) the cause is the CPU taking an interrupt the channel was armed for, (c) `perfect_quantum()`
then made both directions "essentially lossless". Re-derived here with independent, dispatch-exact
counters and a run-time A/B of both changes.

### How the A/B is done — one binary, four cells

`wsa1_fix6_ab.patch` (committed beside these probes, **not applied to the tree**) adds two
environment switches, `TLCS_NO_FIX6` in `tmp95c061_device::tlcs900_check_irqs()` and `WSA1_NO_PQ`
in both `wsa1_state::cpu*_link_w()`, so one build measures all four cells and no cell differs from
another by anything except the change under test. Apply it, rebuild, then:

```
cd ~/compartilhado/kn7000_mame_build
[TLCS_NO_FIX6=1] [WSA1_NO_PQ=1] DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo \
    -str 100 -window -autoboot_delay 1 \
    -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_fix6_refutation.lua
```

Counters are **reads of the interrupt vector table** — a dispatch is the only thing that executes
`m_pc.d = RDMEML(0xffff00 + vector)` — so they carry no prefetch shadow and no routine-entry
aliasing. Checked against the ROM: `0xFFFF28 -> jp 0xF8E47F` (INT0_LinkByte), `0xFFFF7C ->
jp 0xF8E52D`, `0xFFFF80 -> jp 0xF8E54F` (INTTC3_LinkDmaDone). The selector-word read count is
carried alongside as a second, independent INTTC3 counter; the two agree in all four cells.

### The grid, 95 s boot, same binary, same ROMs

| counter | neither | quantum only | FIX 6 only | both |
|---|---|---|---|---|
| CPU 1 INT0 dispatches (`0xFFFF28`) | 2 | 2 | **1** | **1** |
| CPU 1 INTTC3 dispatches (`0xFFFF80`) | **0** | **0** | 1 | 1 |
| CPU 1 INTTC3 selector reads (`0x6007DA`) | **0** | **0** | 1 | 1 |
| CPU 2 → CPU 1 bytes written / read | 2 / 1 | 2 / 1 | 71 / 21 | 711 / 706 |
| CPU 1 → CPU 2 bytes written / read | 41 / 1 | 41 / 0 | 43 / 21 | 5070 / 5070 |
| CPU 2 INT0 dispatches | 40 | 41 | 7 | 985 |
| CPU 2 INTTC3 dispatches | 0 | 0 | 3 | 985 |
| CPU 1 `DMA3V := 0x0A` arms | 1 | 1 | 2 | 2 |

**FIX 6 is the change that moves the link, and `perfect_quantum()` alone does nothing** — the
quantum-only cell is the baseline to within one byte. That is the cell the original report never
measured, and it is the one that could have refuted it.

### The rule FIX 6 implements is in the databook, not just in `tmp94c241.cpp`

TMP95C061 datasheet (bitsavers, sha256 `ef644920…`, fetched by
`tlcs900_datasheet_quotes.py`), §3.3.2 "High-Speed DMA (HDMA)", p.14:

> When the interrupt is generated in the interrupt request source set by HDMA start vector
> resistors, the interrupt controller sends the **HDMA request** to the CPU in level "6"
> irrelevant to the set interrupt level.

and p.21, "(3) HDMA Start Vector":

> When the HDMA transfer counter value reaches 0, … **the HDMA start vector is cleared**, and the
> HDMA start source of the channel is also cleared.

So an interrupt named by a live `DMAnV` starts a transfer instead of a handler, and the register
self-disarms at completion — which is what `tlcs900_process_hdma()` already did (`m_dma_vector[channel] = 0`)
and what FIX 6 makes `tlcs900_check_irqs()` agree with.

### Two narrow defects in the FIX 6 *implementation* (not in its premise)

1. **No range guard.** `tlcs900_process_hdma()` serves a vector only when
   `vector >= 0x28 && vector != 0x3c && vector < 0x74`; FIX 6 masks *any* matching map entry. For
   `DMAnV & 0x1F` in {0x1D, 0x1E, 0x1F} — vectors 0x74/0x78/0x7C = INTTC0/1/2 — the interrupt is
   then masked from the CPU **and** refused by the DMA, i.e. dead until `DMAnV` changes. The
   datasheet is explicit that only the sources in Table 3.3 (1) are HDMA start sources, so the
   guard belongs in both places. Reachable: `tlcs900_dmav_census.lua` measures **kn1500** writing
   `DMA0V = 0x5A` / `DMA2V = 0x5A` (vector 0x68 = INTRX1) and `DMA1V/DMA3V = 0xA5` (vector 0x14,
   below the map, harmless) — a `5A/A5` pattern that looks like the crt0 RAM test spilling into the
   SFRs. Nothing in *that* set trips the mismatch today, but nothing prevents it either.
2. **HALT.** The same datasheet page says "The HALT state cannot be released by HDMA start"
   (§3.4). `execute_set_input()` clears `m_halted` for an edge-mode INT0/INT4..7 before FIX 6 gets
   a say, so a halted CPU now leaves HALT and dispatches *nothing*. Level-mode INT0 — what the
   SX-WSA1R uses — never touched `m_halted`, so this cannot bite here; an edge-mode user could.

### Regression check on the other TMP95C061 machine in the build

`kn1500` is the only other one (`grep -l TMP95C061 src/mame` = `kn1500.cpp`, `wsa1.cpp`; the KN5000
family is TMP94C241, which already carries this rule). Its `snap_at.lua` capture at t = 20 s is
**byte-identical** with and without FIX 6, md5 `e0c2a193f8a801ffa0e588aac1608927` — it writes
`DMAnV`, but never reaches the serial traffic that would notice.

### ⚠ What the grid refutes: "both directions now carry thousands of bytes essentially without loss"

The byte counters that sentence rests on are **not** counting delivered messages. In the "both"
cell CPU 1's `INT0_LinkByte` was dispatched **once** in 95 emulated seconds and `INTTC3_LinkDmaDone`
ran **once**; `DMA3V` was armed twice. The other **705 of the 706** reads of `0x7C0000` are one
runaway micro-DMA transfer: `INTTC3_Sel2_ArmPayload` (0xF8E5AD) armed channel 3 from the `{LE32
dest, LE16 count}` record at `0x6007D3` with **count = 16741**, so channel 3 now swallows every
byte CPU 2 sends — including the header of every later message — and will not raise `INTTC3` for
another sixteen thousand of them. Selector 4 "never arrives" for that reason.

The CPU 1 → CPU 2 direction is genuinely healthy (5070/5070, and CPU 2 dispatches 985 INT0s and
completes 985 channel-3 transfers). The CPU 2 → CPU 1 direction — the one the sound name comes back
on — delivers **one message per boot**, exactly as many as before the quantum change. The quantum
fixed the *transmit* side; the receive side is where the name is stuck, and the corrupt record is
still corrupt (it was `0xFFEF` before the quantum, `0x4165` after — different garbage, not less).

### Where the sound name actually is — `wsa1_e1_record.lua` + `wsa1_wire_window.lua`

The record CPU 1 assembles is `02 78 10 20 20 44` → dest `0x20107802`, count 17440. A TLCS-900 has
**24 address pins**, so that destination cannot even be driven: the record is corrupt beyond
argument. Putting the sender's writes and the receiver's reads on one timeline shows why, and what
the record should have been:

```
t= 70.880476  CPU2 WRITE 0xE1  (#1)          the answer's header
t= 70.880508          CPU1 READ 0xE1 (#1)    INT0_LinkByte takes it
t= 70.880509                  SELECTOR := 2
t= 70.880512                  DMA3V := 0x0A  channel 3 armed for the 6-byte record
t= 70.880518  CPU2 WRITE 0x00  (#2)   \
t= 70.880524  CPU2 WRITE 0x73  (#3)    |  FIVE BYTES WRITTEN AND NEVER READ --
t= 70.880530  CPU2 WRITE 0x00  (#4)    |  47 us in which the receiver does not run,
t= 70.880536  CPU2 WRITE 0x00  (#5)    |  at one byte every 6 us into a ONE-BYTE latch
t= 70.880542  CPU2 WRITE 0xC0  (#6)   /
t= 70.880548  CPU2 WRITE 0x02  (#7)
t= 70.880559          CPU1 READ 0x02 (#2)    the DMA starts absorbing HERE
                              RECORD := 02 78 10 20 20 44
t= 70.880674                  SELECTOR := 4
... and from here on writes and reads track each other within 0.5 us ...
```

The wire carries, in order: `E1 | 00 73 00 00 C0 02 | 78 10 20 20 44 6F 77 6E 74 6F 77 6E 20 53 65 74 …`

* the true record is **`00 73 00 00 C0 02`** = dest **`0x00007300`** — inside CPU 1's 32 KiB static
  RAM, `map(0x000080, 0x007fff).ram()` — and count **`0x02C0` = 704**;
* **1 + 6 + 704 = 711**, which is *exactly* the measured `cpu2 writes` total for the whole 95 s
  boot. Nothing else is ever sent;
* and the payload's first bytes are `44 6F 77 6E 74 6F 77 6E 20 53 65 74` = **"Downtown Set"**.

**So the sound name does cross the wire.** 704 bytes of name data are sent, read by micro-DMA, and
written to `0x20107802` — nowhere — because the six-byte record that says where to put them was
assembled from the wrong six bytes after five were lost at the head of the burst. `Sound Name
*****` is downstream of those five bytes, not of anything else measured so far.

The loss is a *burst-start* effect: after the lockstep engages, reads follow writes within 0.5 µs
for all 704 payload bytes. What is missing is the sender yielding at the FIRST byte —
`perfect_quantum()` only takes effect from the next scheduling boundary, so CPU 2 empties five
byte-times of its already-granted slice into the one-byte latch first. That is exactly what
`abort_timeslice()` addresses, and **the negative result recorded against it was measured in the
wrong cell** — with FIX 6 but *without* `perfect_quantum()` (21 → 24 reads). The two together were
never tried.

### The window is too short, and that is a one-constant fix — measured

`BURST_QUANTUM_US` was chosen against the 6 µs gap *between* payload bytes. The gap that decides
the outcome is a different one: **42 µs** between the header byte (which arms the window) and the
first byte of the burst. The window expires in that gap, `perfect_quantum()` only takes effect from
the next timeslice — `device_scheduler::add_quantum()` measures the expiry from the scheduler's
current time and the slice already granted runs to its end — and the receiver has meanwhile run
ahead in local time.

Measured with the same probes and a `WSA1_PQ_US` override in the A/B patch:

| `perfect_quantum` window | record CPU 1 assembles | CPU 2 → CPU 1 written / read |
|---|---|---|
| 20 µs (as committed) | `02 78 10 20 20 44` → dest `0x20107802`, count 17440 | 711 / 706 |
| **200 µs** | **`00 73 00 00 C0 02` → dest `0x00007300`, count 704** | **719 / 719, zero loss** |

With 200 µs the whole exchange is in lockstep from byte #2, `INTTC3_Sel2_ArmPayload` arms channel 3
with the real destination and the real count, and **selector 4 arrives** — the open item the
previous section left. Same probe, same 95 s boot:

| counter | 20 µs | 200 µs |
|---|---|---|
| CPU 1 INT0 dispatches | 1 | **4** |
| CPU 1 INTTC3 dispatches | 1 | **5** |
| selectors seen by INTTC3 | `sel2:1` | **`sel1:3 sel2:1 sel4:1`** |
| CPU 2 → CPU 1 written / read | 711 / 706 | **719 / 719** |
| CPU 1 → CPU 2 written / read | 5070 / 5070 | 5080 / 5080 |

**And `abort_timeslice()` is a no-op here, which is now measured in both cells.** In the FIX-6-only
cell it reproduces the recorded negative result exactly — 71 written, **24** read against 21
without it — and on top of `perfect_quantum()` it changes *nothing*: the wire trace is
timestamp-identical and the t = 95 s screenshot is byte-identical. The reason is the one already
written in the README: it ends the sender's slice, and the receiver is ahead in local time.

### ⚠ AND THE NAME STILL DOES NOT APPEAR

`SNAP_AT=95` with `WSA1_PQ_US=200`: the capture is **byte-identical** to
`screens/wsa1r_udma3fix_t95_sound_mode.png`, md5 `24a7cc95d6da10dd84e34ad532e6b5c5`. So delivering
the block to the right address is *also* necessary and not sufficient. What is now known that was
not before: 704 bytes of name text ("Downtown Set" …) do arrive in CPU 1's SRAM at `0x00007300`,
so the next question is no longer about the link at all — it is what CPU 1 does with `0x7300`
after the block lands, and why the SOUND MODE screen keeps printing its fallback string.

---

# ★ `Sound Name *****` -- SOLVED, 2026-08-27, and it was CPU 2's PORT 9

The link work above (OVERLAY FIX 6, the burst quantum) was necessary and was not
sufficient; the section it ends with says so. This is the rest of it.

## The chain, and the exact point it stopped

`wsa1_soundname_path.lua` -- one run, four candidate stopping points separated by
data taps alone. prom_a's fallback string at `0xFC1C49` is reached from exactly
one instruction, `0xFC1BAE ld XIY,0x00fc1c49`, taken when `sub_FC1BDC` returns
`XIY = -1`; so the question is only how far the request/answer got.

**Before, 110 s boot:**

```
COUNTS  req0x80=1  ansbuf_writes=0  fallback_sound_reads=24
COUNTS  ring604800 r=262140 w=0   wire cpu1 w=5080 r=719   cpu2 w=719 r=5080
t=  6.87606  REQ (0x0800) := 0x80  pc=FC1BBC        ... 04 00 00 00, six bytes
t=  7.57579  FALLBACK Sound Name read @0xFC1C48  pc=F8F20F
```

`262140 = 4 x 65535` is `sub_FC1C29`'s poll bound, four times over, against
**zero** ring writes. And `wsa1_name_request_window.lua` shows the request is
not the problem — it crosses the wire in full and CPU 2 reads every byte:

```
t=   6.876076  CPU1 WRITE 0x05  (#5057)  pc=F8E0B9      header, stream 0, 6 bytes
t=   6.876078        CPU2 READ  0x05  (#5057)  pc=F99BD5
t=   6.876091  CPU1 WRITE 0x80  (#5058)  ... 00 04 00 00 00, all read by CPU 2
```

CPU 2's first transmission of the whole boot is at t = 70.88 s. It was not
answering because it was not running: `wsa1_cpu2_timeline.lua` samples its PC
per frame and it never leaves `0xF9A347-0xF9A490` in 80 s — six copies of the
DSP microcode upload's per-byte handshake, `ld C,(0x19) / and C,0x08`, each
bounded by `0x1F40` = 8000 iterations, each one burning the full bound because
P9 read 0.

## The cause: an unbound port is not a neutral port

`wsa1_sch_dsprdy.sh` re-renders the schematic and re-runs the census. Service
manual page 20 (sheet II-9/10, MAIN (A)/MB2), **IC2 TMP95C061AF MICROCOMPUTER
(SUB)**, left pin column:

| pin | name | net |
|---|---|---|
| 19 | VCC | +5D |
| 20 | AN0 | **+5D** (same node as pin 19, junction dot on both) |
| 21 | AN1 | JOYX through R180 1K |
| 22 | AN2 | JOYY through R181 1K |
| 23 | **P93** | **`DSPRDY`, R79 4.7K UP to the VREF node** |

and pins 2-9 are P70-P77 carrying `DSPD0-DSPD7`, which is the byte path the same
routine writes with `ld (0x0013),(XIZ+0x08)`. So P9 bits 0 and 3 idle **high**
on the board; MAME's unbound read of 0 was the wrong level, not a neutral one.
Nineteen sites read SFR 0x19 and all nineteen are in prom_c (prom_a, prom_b and
prom_d have none) — eighteen DSPRDY polls plus `bit 0,(0x19)` at `0xFB050B`.

Fixed by `wsa1_state::cpu2_p9_r()` returning `0x09`.

## The A/B, in one binary

`wsa1_p9_control.lua` puts port 9 back the way it was with a read tap, so the
control and the fix are the *same executable*. **⚠ it needs
`-autoboot_delay 0`**: with the fix in place the upload finishes before t = 1 s,
and a control installed at t = 1 measures the fixed machine (that mistake was
made once here, and it looked like a refutation).

| | control (P9 = 0) | fixed |
|---|---|---|
| ring `0x604800` reads / writes | 262140 / 138 | **322 / 117** |
| `0x000810` contents | untouched | `"     Piano      "` |
| CPU 2 -> CPU 1 bytes | 719 | 948 |
| t = 95 s screenshot | md5 `24a7cc95…` = the old `Sound Name *****` frame, byte-identical | md5 `c0109f39…`, **`Piano`** |

## ⚠ What this did NOT fix: the keybed

The same control, chained onto `wsa1_keybed_note.lua` on `wsa1`, still delivers
the note with P9 masked to 0:

```
cpu2->cpu1: A2 90 3C 3C A2 90 3C 00           header 0xA2 = stream 5, 3 bytes
cpu1->cpu2: 03 90 00 3C 3C  03 90 00 3C 00  03 B0 00 7B 00
```

so the note path was already cured by OVERLAY FIX 6 and the burst quantum. It is
recorded here because the original brief tied the two symptoms to one wedge, and
that turned out to be true of the *first* wedge only.

## The probes added by this pass

| script | question it answers |
|---|---|
| `wsa1_soundname_path.lua` | where does the sound-name chain stop -- request, wire, ring, or copy? |
| `wsa1_name_request_window.lua` | does the request reach CPU 2, byte for byte, and what does CPU 2 do next? |
| `wsa1_cpu2_timeline.lua` | what is CPU 2 executing, per 2-second bucket, over the whole boot? |
| `wsa1_dspready_experiment.lua` | labelled FAKE: what changes if P9 bit 3 is held high? (the experiment that found it, superseded by the schematic) |
| `wsa1_p9_control.lua` | the control: put port 9 back to an unbound read, then chain another probe |
| `wsa1_sch_dsprdy.sh` | which net is IC2 pin 23, and who reads SFR 0x19? |

## The layout-reuse pass (wsa1r.lay: declare each shape once)

`src/mame/layout/wsa1r.lay` is 932 lines but 267 KB: the generator emits each of
the 58 buttons as a COMPLETE inline SVG in absolute artwork coordinates, with a
private copy of the gradient `<defs>`, cropped by a per-button `viewBox`.
`kn5000.lay` instead declares a shape ONCE and places it many times with
`<bounds>`. Deciding which of the 58 may share one `<element>` is a question
about PIXELS, so it is answered with the renderer MAME actually uses.

| script | question it answers |
|---|---|
| `nsvg_hash.c` + `build_nsvg_hash.sh` | do these two SVGs render identically, and if not, by how much? Uses MAME's OWN bundled nanosvg and reproduces `rendlay.cpp` `draw_svg()`'s scale arithmetic, so the answer is about what is displayed, not about what librsvg thinks. |
| `wsa1r_lay_shape_classes.py` | how many DISTINCT shapes are really in the layout -- i.e. how many `<element>`s the rewritten file needs -- and is the absolute→local coordinate change loss-free? |

```sh
sh notes/wsa1-probes/build_nsvg_hash.sh          # once; header-only, no MAME build needed
notes/wsa1-probes/nsvg_hash a.svg 42 25          # hash one SVG at 42x25 bounds
notes/wsa1-probes/nsvg_hash -cmp a.svg b.svg 42 25
python3 notes/wsa1-probes/wsa1r_lay_shape_classes.py
```

`-cmp` exists because a hash is all-or-nothing. Two buttons lifted from the same
drawing differ by Inkscape duplication noise -- a gradient scale agreeing only to
the sixth decimal -- and deciding whether they may share an element needs the
MAGNITUDE of the disagreement, not just its existence. It prints
`ndiff=<pixels> of <total> maxdelta=<0..255> meandelta=<f>`.
