# FINDINGS — the KN7000 rear USB port (investigation START, 2026-08-03)

Goal: understand how the rear **USB** terminal works, what it offers, and how to emulate it. This is
the opening pass — architecture + features are established; the main-CPU↔USB-CPU register protocol is
the next job. Sources: KN7000 service manual (block diagram p80, parts list p55, schematics p100/118),
the KN7000 owner's manual, and firmware strings.

## One-line answer

The USB terminal is a **USB *device* port to a PC** (type-B / "type AB cable"), served by a **dedicated
USB co-processor subsystem** that is separate from the main MN10300 CPU. It offers **USB-MIDI**,
**USB audio recording**, and **PC data management** — using Panasonic's bundled PC software.

## Hardware — a co-processor subsystem, not a main-CPU peripheral

The USB (and SD) live on the "Q SD I/F" board with their own processors. The main CPU never touches
USB wires; it talks to a USB CPU over a serial link.

```
   USB port (USB+/USB-)                 rear jack -> CN702/CN701
        |
   [IC408  "USB AUDIO"  C2BBGE000618]   USB device controller: USB+/USB-, MIDI RX (USB-MIDI),
        |   |                           and the serial control link to the MAIN CPU
        |   |  DU0-DU7 (8-bit bus)
        |  [IC407 "USB MICRO CONTROLLER" C2CBGF000150]  audio streamer:
        |        SDIU <- IC410 PCM1800E   (ADC, instrument audio -> PC, "record")
        |        SDOU -> IC406 PCM1716    (DAC, PC audio -> instrument, "play")
        |
   === serial link to MAIN CPU (MN10300) ===
        USB.SI, USB.SO, USBM.TX, USB.WAITM, USB.WAITH, USB.SD, USB.ST, USB.MAITU
```

⚠ **Naming caveat:** the block-diagram *function* and the parts-list *name* look swapped. The block on
`USB+/USB-`+`MIDI RX`+main-CPU-serial is drawn as **IC408** (parts name "USB AUDIO"); the block on the
`SDIU/SDOU` audio-codec serial is **IC407** (parts name "USB MICRO CONTROLLER"). Describe by datapath
(front-end USB controller vs codec streamer); confirm the exact split when a board is available.

### USB/SD board IC inventory (parts list p55)

| IC | part | role |
|---|---|---|
| IC401 | `MN102H60KTA` | **SD µ-COM** (SD-card microcontroller) — *separate from USB* |
| IC402 | `MN67737DB1` | **SD DECODER** → CN401 → CN921/CN922 = the SD card slot |
| IC403 | `S29L331AFSTB` | serial EEPROM/flash for the SD µ-COM (block: "EEPROM", DI/DO to IC401) |
| IC406 | `PCM1716ET2` | **USB-audio DAC** (PC → instrument) — "USB DA.L/R" |
| IC407 | `C2CBGF000150` | "USB MICRO CONTROLLER" — audio streamer (codecs ↔ IC408 over DU0-DU7) |
| IC408 | `C2BBGE000618` | "USB AUDIO" — front-end **USB CPU** (USB+/USB-, MIDI RX, main-CPU link) |
| IC410 | `PCM1800E-T1` | **USB-audio ADC** (instrument → PC) |
| IC414 | `C3FBKD000162` | **4 Mbit FLASH** — the SD µ-COM program (roadmap: "SD sub-CPU program"; NO_DUMP) |
| IC404/405/409/411/412/413 | glue / op-amps | buffers, `M5218` op-amp, `TC7W00` gates |

⇒ Every processor in this subsystem (IC408, IC407, the SD µ-COM IC401, its flash IC414, EEPROM IC403)
runs **undumped** firmware. The main program ROM (dumped) only holds the *host side* of the link.

## Features (owner's manual + firmware strings)

The rear terminal takes a **type-AB USB cable** to a PC. The bundled CD-ROM carries three PC apps —
**Audio Recorder, Song Manager, USB Driver** (owner's manual spec sheet, "ACCESSORIES").

1. **USB-MIDI.** The USB CPU has a `MIDI RX` pin. The owner's manual "Computer Connection" screen (MIDI
   MENU) sets the MIDI signal-flow mode:
   - **NORMAL** — ordinary;
   - **PC as master** — for data transmission;
   - **KN as master** — KN7000 is the master keyboard (MIDI → PC);
   - **KN as slave** — KN7000 receives (PC → MIDI);
   - **INTERFACE** — KN7000 acts as a **USB↔MIDI bridge** between a USB-only PC and a MIDI-only
     instrument (i.e. a USB-MIDI adapter).
2. **USB audio recording** ("Audio Recorder" app). Streams the instrument's audio to the PC and saves
   **WAV / WMA / MP3** — "Create Audio Files For Making CD". Hardware path: instrument audio → PCM1800
   ADC (IC410) → USB audio controller → USB. (The reverse, PC → PCM1716 DAC IC406, feeds "USB DA.L/R".)
3. **Data management** ("Song Manager" app). Manage/transfer the instrument's data (songs, etc.) to/from
   the PC. Firmware warns *"…don't disconnect the USB Cable during this procedure, to do so may damage
   your SD Card"* — the transfer touches the SD card, mediated by the main CPU + SD µ-COM.

Firmware gate string: *"This function is only available when you connect to a PC with a USB cable."*

## Emulation assessment

- **What we have:** the host (main MN10300) side of the link, in the dumped program ROM — the "USB
  DRIVER / MANAGER" modules named on the block diagram (owner's manual spec sheet lists a firmware
  "USB DRIVER"). The register/serial interface is `USB.SI/SO` + `USBM.TX` + `USB.WAITM/H` and probably a
  mailbox in the `0x98050000` sound/IO window (cf. the existing `0x9805000C` "SD mailbox").
- **What we don't:** the USB CPU (IC408), the audio streamer (IC407), the SD µ-COM (IC401) and its
  flash (IC414) — all undumped, all masked/custom Panasonic parts.
- **Approach:** two layers, do them in order.
  1. **HLE the host link.** RE the main-CPU-side driver: find where `USB.SI/SO` map, decode the command
     framing to the USB CPU, and answer as a "not connected / no PC" device so the COMPUTER CONNECTION
     menu and any USB status polling behave. This is pure disassembly, no hardware, and it is the same
     shape as the SD-mailbox HLE already in the driver — **start here.**
  2. **Model the USB device to a host (optional, later).** Presenting the KN7000 as a real USB-MIDI /
     USB-audio device to the emulator host is beyond MAME's current USB-device support and needs the
     co-processor behaviour anyway; treat as out of scope until (1) is done.
- **Discipline:** HLE stays within the real interface — the host link registers — and must not read the
  co-processors' private state from a distance (see the HLE chip-boundary rule). If USB behaviour
  depends on data X and the only inputs are the link registers, X is already encoded there; decode it.

## Register-level RE — pass 1 (2026-08-03): what the host link is NOT, and what it is

Pushed on "which main-CPU register carries the link." Progress is mostly by **elimination**, which
narrows it sharply:

1. **NOT an SIO channel.** The MN10300 has exactly **three** on-chip USARTs (0x34000800/810/820), and
   the driver's verified RE assigns all three: ch0 = control panel, ch1 = MIDI-1, ch2 = MIDI-2. (The
   old "SD sub-CPU on ch2" idea was already retracted — ch2 is MIDI-2.) So the USB link is not a
   hardware serial peripheral.
2. **NOT a prominent memory-mapped mailbox.** A histogram of every absolute access into the whole
   `0x98000000–0x9807ffff` I/O window accounts for all of it: main/sub TG (incl. the new wave-read
   port), the `0x9805000C` SD mailbox + `0x9805000E` readback, the FDC at `0x98020000`, and sound
   control at `0x98060000`. The two "unknowns" resolve to sound: `0x98050010` is written beside the
   TG-enable gate `0x500CE380`, and `0x98060000` is an IRQ-protected GPIO latch (shadow `0x50005214`).
   None is USB.
3. **It looks like a transistor-buffered GPIO bit-bang.** On the CPU sheet (p100) the main-side nets
   **`USB.SD`, `USB.ST`, `USB.MAITU`** run through discrete level-shifter transistors (`2SB709ARTX`,
   `2SD601AQTX`) and `TC7W08` AND-gate glue — i.e. GPIO port pins bit-banged into a serial link, not a
   peripheral register. That is exactly why steps 1–2 find nothing. The board side (p118, SCHEMATIC-10)
   carries `USBM.TX`, `USB.WAITM/H`, `USB.SI`, `USB.SO`, and IC408 exposes a `UTXD2` UART pin.
4. **The link is NON-BLOCKING at boot.** The machine boots to the play screen with no USB present, so
   the USB code path runs only on demand (Computer Connection menu / Audio Recorder / Song Manager).
   ⇒ **No boot stub is needed**; HLE is required only to make the USB *features* work, not basic
   operation. This lowers the priority and de-risks it.

⇒ Working model: main CPU bit-bangs a synchronous serial link (`USB.SD` = data, `USB.ST` = clock/strobe,
plus `USB.MAITU` and the `USB.WAIT*` handshake) over GPIO port pins to the USB CPU (IC408), which also
has a UART. The exact **GPIO port + bit** is the missing datum.

### Sharpest next probe (either works)
- **Dynamic:** run the emulator, navigate MIDI MENU → COMPUTER CONNECTION (or open Audio Recorder), and
  log GPIO accesses (`0x36008000` region + the MN10300 port data registers). The pins toggled only in
  that screen are the link. This is the fastest way to the port/bit.
- **Static/visual:** trace `USB.SD/ST/MAITU` on p100 through the buffer transistors to the CPU port pins
  (the net names appear once, at the CN105 connector edge; the CPU-pin end is reached through the glue).
- Then find the firmware bit-bang routine at that port and the Computer-Connection handler that drives
  it; that yields the command framing for HLE.

## Register-level RE — pass 2 (2026-08-03): dynamic GPIO trace built + run

Built a reusable dynamic tracer — `tools/gpio_trace.lua` (MAME `-autoboot_script`). It installs
read/write taps over the GPIO ranges, records `(addr, PC, R/W)` for every access (arming AFTER boot to
skip init noise), and dumps an aggregate via `emu.print_info`. (Two gotchas baked in: retain the tap +
notifier subscriptions in `_G` or the GC kills them at ~frame 120; `io.open` is sandboxed, so log via
`emu.print_info`.)

**What it showed.** All GPIO the firmware touches is in the **external latches at `0x36008000`** — the
on-chip port ranges `0x34000000-0xff` and `0x34000300-0x7ff` are never accessed. Steady-state (post-boot,
idle) only two things run:

| addr | PC | what |
|---|---|---|
| `0x36008084` (in) | `0x484ACEE1` (×521) | control-panel ready/handshake input poll (known) |
| `0x36008004` (out) | `0x4C02BCF0` (×260) | toggles **bit 5** at ~10 Hz — a heartbeat/clock (RMW: read, invert bit5, write) |

So on `0x36008004`: **bit1 = SD SPI CS** (known), **bit5 = periodic heartbeat/clock**. Other bits of
`0x36008004` and of the `0x36008024/44/64` output latches are set once at boot and idle after.

**No USB activity at idle** — confirming the pass-1 conclusion that the USB link is on-demand. The tool
is ready to capture the USB bit-bang the moment the USB code path runs; it just needs that path
triggered.

### ⛔ The blocker to capturing USB dynamically: the COMPUTER CONNECTION screen is unreachable
The USB code runs from **MIDI MENU → COMPUTER CONNECTION** (or the Audio Recorder). Reaching it needs
the **LCD soft-keys** (the bezel buttons around the screen), which are **not yet mapped** in the driver
— the same known gap that blocks the DISK menu. There is no dedicated MIDI/menu hardware button to
shortcut it. So the dynamic tool cannot yet drive the firmware into the USB path.

### Two ways to unblock (pick one next)
1. **Map the LCD soft-keys.** Then navigate to COMPUTER CONNECTION and let `gpio_trace.lua` capture the
   bit-bang directly. Also unblocks DISK/other menus — high general value.
2. **Find and force the USB-connect input.** Locate the GPIO input bit the firmware reads to detect a
   PC, force it "connected" from a Lua tap, and watch the firmware start driving the link. Cheaper if
   the connect bit can be found (it's likely a bit of an input latch near `0x36008084`), but the input
   latches beyond `0x36008084` are not yet identified.

Either path ends the same way: `gpio_trace.lua` records the exact `0x36008000` bits toggled by the USB
routine, and disassembling those PCs gives the bit-bang framing to HLE.

## Concrete next steps

1. Read schematic **p118/119** (main-CPU 4/5) to fix which MN10300 port pins carry `USB.SI/SO`,
   `USBM.TX`, `USB.WAITM/H` → which I/O register / SIO channel.
2. Find the host **USB driver** in firmware: search for accesses to that register, and for the
   COMPUTER-CONNECTION menu handler (MIDI MENU) that writes the mode (NORMAL/PC-master/…/INTERFACE).
3. Decode the link **command framing** (it is a serial mailbox with a WAIT handshake, like the SD path).
4. Decide the HLE contract: what a "no PC attached" USB CPU replies, so the menu and status are stable.
5. Cross-check against the KN5000/HD-AE5000, which had its own CP-serial saga — the framing may be a
   relative of that link (`notes/kn5000-cpserial-INDEX.md`).

## Related

- SD card path (already partly modelled at `0x9805000C`): the SD is a *sibling* co-processor here, not
  the same block as USB — worth reconciling the driver's "SD mailbox" comment with this topology.
- `HLE chip-boundary discipline`, `Fake with the REAL mechanism` (memory).
