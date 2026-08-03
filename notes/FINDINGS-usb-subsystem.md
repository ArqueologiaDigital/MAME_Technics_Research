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
