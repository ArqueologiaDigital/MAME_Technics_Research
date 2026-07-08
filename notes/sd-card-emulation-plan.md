# KN7000 SD-card emulation — plan

## The chips
- **IC401 `MN102H60KTA`** — Panasonic **MN102H** 16-bit microcontroller. This is the **SD sub-CPU**, i.e.
  **"CPSD"**, one of the FOUR panel sub-CPUs (CPL/CPC/CPR/**CPSD**) the driver already knows about (see
  kn7000.cpp comments + notes/panel-serial-protocol.md + io-map.md). It runs its own firmware from an
  **internal mask ROM which is NOT dumped** → chip-level (LLE) emulation is blocked → **HLE is the path**.
- **IC402 `MN67737DB1`** — Panasonic custom LSI, the **SD-card physical interface / host controller** the
  MN102H60 uses to drive the SD bus. Also un-dumped/undocumented → covered by the HLE.
- Service manual confirms the physical **"SD panel" board = CPSD** (§7.6, pp. ~555–606; print/copy-disabled).

## Architecture (how the SD card is reached)
```
MN10300 main CPU  <-->  SIO ASIC ch0 (0x34000800, the panel serial link)  <-->  CPSD (MN102H60)
                                                                                   |
                                                                            MN67737 + SD bus  <-->  SD card
```
- The SD card is driven **over the panel serial link** — the exact same SIO channel (0x34000800) and 4-board
  frame protocol as the panel buttons/LEDs. The 4-board RX decoder (`0x484AD111` → 32-entry jump table
  `0x48613108`) routes CPL/CPC/CPR/**CPSD**. So SD commands/responses ride the panel protocol we already HLE
  for CPL/CPC/CPR.
- Firmware has **extensive** SD support (named functions in the disassembly):
  card info (`SDCardInfoFunc` 0x4855D901, `SDCardNameFunc`), **SD-Audio playback** (`GetSDAudPlay*`,
  `GetSDAudSel*` — song/list/time/play-pause/mode), **SD-Song/MIDI playback** (`GetSDSndPlay*`), lyrics
  (`SDLyricsBoxProc`), volume (`MainSD_VolumeSW`, `ApSD_VolumeSW`), menus (`AcIntTitleMenuSDProc`,
  `AcSDFuncListBoxProc`, …), play/fwd-rew timers (`IvSDPlayTimerProc`, `IvSDFwdRewTimerProc`), and a
  **test mode** (`MainSDTestFunc`, `SDTestStartFunc`). SD state lives in RAM ~`0x5008xxxx` (e.g.
  `0x50083bc2`, `0x5008320c` read by `SDCardInfoFunc`).
- **ERROR 93 "SD lid is open"** (strings @ ~`0x485E5CE8`, EN/FR/ES): the firmware reads a **lid-closed /
  card-present state** (reported by CPSD over the serial link) before allowing SD access.

## Emulation strategy: HLE, extending the existing panel-serial HLE with a CPSD model
Because the MN102H60 firmware is undumped, we **model the CPSD protocol**, backed by a **host SD image
file**. This slots into the mechanism already built for the panel sub-CPUs.

### Phase 0 — clear ERROR 93 (lid closed) — first visible milestone
- RE the lid path: find where the firmware reads the lid/card-present state (a CPSD-reported status byte in
  RAM ~`0x5008xxxx`, or a serial-RX status frame) that gates SD access, and make the CPSD HLE report
  **lid-closed + card-present**. Deliverable: the SD menus open instead of ERROR 93.

### Phase 1 — RE + HLE the CPSD serial protocol
- Extend the 4-board panel decoder HLE to handle the **CPSD group**. Sweep/RE the CPSD command set the main
  CPU sends (card-detect, lid status, mount, **directory list, file open/read/write/seek**, playback control)
  and the response framing, using the named SD functions + panel-serial-protocol.md as the map.
- Model CPSD responses: card present, lid closed, card capacity/FAT info, directory entries, file bytes.

### Phase 2 — host SD image backing
- Add a MAME **image device** for the SD slot (a mountable **FAT16/32 image file**, like the FDC's floppy
  device). CPSD's file-access commands read/write this host image. Provide/validate the KN7000's expected
  on-card directory structure (audio, song, style/sound folders).

### Phase 3 — panel + UI wiring
- Bind the **SD panel buttons** (SD LOAD, SD VOLUME −/+, SKIP/SEARCH, STOP, PLAY/PAUSE — currently visual-only
  in the layout) to the CPSD subsystem. These are on the **CPSD sub-CPU's own button matrix**, so they need a
  CPSD-side scan (a separate sweep, since CPSD wasn't in the CPL panel matrix).
- Model the **lid open/close** as a UI action (a toggle or the "PUSH RELEASE" eject): open → the firmware
  faithfully shows ERROR 93; closed → access works. Drive the **SD IN USE** LED from CPSD activity.

### Phase 4 — content playback
- **SD-Song** (`GetSDSndPlay*`): standard MIDI / sequencer files → play through the sequencer.
- **SD-Audio** (`GetSDAudPlay*`): compressed audio (likely MP3/WAV) → decode + play. NOTE audible output is
  gated by the broader no-audio situation (undumped wave ROMs / TG), but **file access, lists, lyrics,
  timers and the whole UI are independent of audio** and can be fully driven.

## Risks / unknowns
- The **CPSD serial protocol is un-RE'd** — a real effort (comparable to the panel-button protocol RE).
- **MN102H60 firmware undumped** — rules out LLE; a physical dump would later enable full chip-level
  emulation as an alternative to HLE.
- Audio playback gated by the existing no-audio blocker (separate from SD).

## First concrete steps
1. Trace the ERROR-93 lid check (from the SD-access entry, e.g. `AcIntTitleMenuSDProc`/`SDCardInfoFunc`) to
   the exact lid-status read; document the byte/bit.
2. Stand up a minimal CPSD HLE that answers "card present + lid closed" so the SD menu opens (Phase 0).
3. Then grow the directory/file protocol against a host FAT image (Phase 2).
