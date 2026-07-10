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

## RE findings (2026-07-08 session) — CORRECTION to the architecture above
Static RE of the SD driver shows the SD hardware is **memory-mapped**, not (only) reached over the panel
serial link:
- **SD I/O register bank @ `0x90200000`** — the driver reads `0x9020005c`, `0x9020005d`, `0x9020005f`
  (and `0x90008020`) as SD hardware registers, via a register HAL at `0x48566760` (loads the address as an
  immediate, reads indirect). **These are almost certainly the MN67737 (SD host controller) registers.**
- **The driver currently maps `0x90000000–0x97ffffff` as plain RAM** (`map(...).ram().share("vram")` —
  "LCD controller window (regs + trampolines)"), so `0x9020005x` reads back as **zeros** → firmware
  concludes *no card / lid open* → **ERROR 93**. Phase 0 = carve out the SD register sub-range and return
  *lid-closed + card-present* values.
- **SD state RAM** (main-CPU side, updated by the SD driver from the registers):
  - `0x50083cd8` — SD state byte (`SD_GetState`=0x4855e80c, `SD_SetState`=0x4855e803; values 3/4/…).
  - `0x50083bc2` — card-ready status (`SDCardInfoFunc` requires `==1`).
  - `0x50083bc3` — error-flags byte (`bset 0x01/0x02/0x04` per failed hardware check).
  - `0x50083bb8–0x50083bcc` — a dense SD state struct (every byte heavily referenced).
  - Low-level SD command dispatch: `0x4856242e` (→ a deep card/FAT stack: `0x48562264`, `0x48562302`,
    `0x48560fed`, `0x48565d87`, `0x4855f2f7`, …).
- **Revised Phase 0**: add a read/write handler for the SD register bank at `0x90200000` (within the big
  0x90 block) that returns the "card present + lid closed" status the firmware wants; find the exact
  register/bit by dynamically tapping `0x9020005x` reads while the firmware polls, then model it.
- **Card-detect / lid physical read** = `0x3400016c` **bit 0x10 (bit 4)**, in the card reader `0x4854bce0`
  (writes 1 to strobe, reads back, `btst 0x10`): **clear => card present / lid closed**, set => no card.
  A software override sits at `0x50005204` (if `(int16)>=0`, that value wins over the hardware read);
  debounce state at `0x5000520c/0x50005210/0x50151bfc`. IMPORTANT: in the emulator `0x3400016c` already
  reads 0 (bit4=0 => "present"), so ERROR 93 is NOT the card-detect -- it is raised deeper in the ACCESS
  path (the `0x90200000` register/command protocol returning zeros). Card-check wrappers: `0x4854b597`,
  `0x4854b5c5` -> debounce `0x4854bd39` -> raw `0x4854bce0`.
- The **CPSD** panel-serial theory still likely governs the **SD-panel BUTTONS** (LOAD/transport) and
  possibly card-detect notification, but the **data/status path is the memory-mapped `0x90200000` bank**.

## SD communication protocol — FULLY TRACED (2026-07-08, dynamic + static)
Reproduced the whole SD access path live and traced it to the exact hardware hook:

**UI flow (reproducible):** boot → **DISK** button (SEG12 0x80) opens the *DISK MENU* → left soft-key 5
**SD MENU** (SEG03 0x80) → right soft-key 4 **SD-AUDIO PLAY** (SEG0F 0x20) → the screen shows a
**"WAIT!......."** dialog and **hangs there indefinitely** (does not even reach ERROR 93 on this path).
(Soft-keys: LEFT col = SEG03 b3–b7, RIGHT col = SEG0F b2–b6.)

**The link = SIO channel 2 (`0x34000820`)** — NOT "MIDI-2" as the notes label it; it is the **SD/CPSD**
channel. During WAIT the firmware reads **`0x3400082c` ~372,820×** (a tight poll). The poll is
`btst 0x07,(0x3400082c); bne proceed` @0x484b204c → **bit 7 of `0x3400082c` = RX-ready**.
- `0x34000820` — TX/CONFIG (send: `movhu` data, read-back, `or 0x8000` start-bit, write). @0x484b2820.
- `0x34000828` — RX data byte (`movbu (0x34000828),d0`). @0x484b21f2.
- `0x3400082c` — status; **bit 7 (0x80) = RX-ready**.
- SD-SIO init/config code lives at ~`0x484b27xx`; TX at `0x484b28xx`; RX at `0x484b21xx`.

**It is RX-DRIVEN.** During the WAIT there are **zero TX writes** to `0x34000820` — the firmware is not
sending a command, it is **waiting to receive**. So CPSD (the MN102H60) is expected to **stream status
frames to the main CPU** on channel 2, exactly like CPL/CPC/CPR stream button/LED frames on channel 0
(`0x34000800`), which the driver already HLEs. The firmware polls `0x3400082c` bit 7 and reads frames from
`0x34000828`; with no CPSD streaming, it hangs on "WAIT!".

**=> Revised implementation (Phase 0/1 merged):** extend the driver's SIO HLE to model **channel 2 as CPSD**
— periodically raise `0x3400082c` bit 7 and feed the SD status frames the firmware expects at `0x34000828`
(card-present, lid-closed, ready). Reuse the panel-serial frame machinery (`notes/panel-serial-protocol.md`).
The `0x90200000` bank is the later bulk-data path (not touched until the channel-2 handshake advances).
Next concrete RE step: learn the CPSD frame format — either force bit 7 + feed trial bytes and watch the
firmware's reaction at the RX site (`0x484b21f2`), or RE the RX frame parser around `0x484b21e8`.

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

## Driver implementation status (2026-07-08) — CPSD transport scaffold stood up
Added to src/mame/matsushita/kn7000.cpp:
- **ch2 relabelled** SIO_MIDI2 -> also `SIO_SD` (the SD/CPSD link, per RE).
- **ch2 status bit7**: `sio_r` reg 0xc now returns 0x80 for ch2 while a CPSD frame is queued (the bit the
  SD firmware polls at `btst 0x07,(0x3400082c)`).
- **CPSD delivery path**: `cpsd_queue()` + `cpsd_event` timer + `m_cpsd_resp[]`, mirroring the panel RX
  path; each timer tick does `sio_rx_push(SIO_SD, byte)` (-> ch2 FIFO + asserts group 0x14, the ch2 RX IRQ).
- **Probe**: on the first ch2 poll, one placeholder SysEx frame `f0 12 34 56 f7` is sent to validate the
  end-to-end delivery.

**Result of the probe test:** the firmware now SEES bit7 and takes its RX branch (the "PLEASE WAIT" dialog
changes vs the dead hang), BUT it does **not read the RX bytes** yet (`0x34000829` read count = 0). So the
transport is wired but the **bit7 -> byte-read handoff is not landing**. Open questions for the next pass:
- Is the RX byte read POLLED or via the group-0x14 ISR? (The hot 0x82c poll does NOT read 0x829, so the
  read happens in the bit7-set branch `0x484b2057` -> `0x4854d18f`, or in the ch2 RX ISR.)
- Does bit7 mean "frame pending" or "one byte ready" (i.e. should it mirror `sio_rx_ready`)?
- Is group 0x14 actually enabled when we assert it? (RE `0x4854d18f` and the `0x34000150` bit0 write.)
Next: disassemble `0x4854d18f` and the group-0x14 ISR to find exactly where/when `0x34000829` is read, then
align `cpsd_event` delivery + the bit7 semantics to it.

## Driver status update #2 (2026-07-08) — transport corrected; blocker = ch2 RX interrupt disabled
Refined the ch2 model and traced the delivery to a hard blocker:
- **Corrected the status bits**: the per-byte RX reads gate on **bit4** (`btst 0x10,(0x3400082c)` @0x484b2122,
  a timeout-counter poll), NOT bit7. bit7 (`btst 0x07 @0x484b204c`) is a *select the firmware branches on
  AFTER reading the byte* (bit7 set -> the 0x484b2057 DETECT/sound path; clear -> normal 0x484b2096 parse).
  Forcing bit7 DIVERTED the firmware, so the driver now leaves bit7 alone and drives only bit4 (RxRDY) from
  the ch2 FIFO. `cpsd_queue()` pushes the whole frame into the FIFO at once.
- **The RX handler is `0x484b2037`**, registered (SD init table @0x484b26f0) for **group 0x14** with ICR
  `0x34000150`. It reads +9 (0x34000829) at entry.
- **BLOCKER (hard data):** during the entire SD access `0x34000150` = `0x1011` -> **ENABLE(bit8)=0**,
  LEVEL=1, DETECT=1; and there are **ZERO writes** to `0x34000150` while the SD screen waits. So group 0x14
  is initialised DISABLED and never enabled -> the CPU never takes the ch2 RX interrupt, so `0x484b2037`
  never runs, so 0x34000829 is never read (RX reads = 0), regardless of FIFO/bit4/REQUEST. `intc_assert(0x14)`
  does set REQUEST(bit4) but ENABLE gates it.
- **Interpretation:** the SD RX is NOT delivered through the enabled interrupt in this scenario. Either the
  firmware only enables group 0x14 after an earlier handshake step CPSD must satisfy first (so we're stuck
  before that step), or the read is driven by a poll site we haven't pinned (PC-sampling the WAIT was spread
  out, no single hot loop -- the firmware is busy in 0x4854d18f sound-refresh + 0x484b28xx SD-SIO).
- **Next:** pin the EXACT hot `0x3400082c` poll site (targeted PC breakpoint / count per-ref) and read what
  condition advances it; and RE the SD-SIO init (0x484b27xx: builds the ISR table, calls 0x484b2615 /
  0x484b2691) to find where/whether group 0x14 ENABLE gets set and what gates it. That determines whether to
  drive the RX via a modelled interrupt-enable or a pure status-poll response.

## Driver status update #3 (2026-07-08) — ROOT CAUSE: the SD subsystem never initialises
Chased the RX-trigger handshake down through every layer and hit the real blocker, which is UPSTREAM of
the RX path:
- Added the correct **bit6 = TxRDY** to the ch2 status (a UART always-empty-in-HLE bit the SD-SIO poll
  helper 0x484b288f waits on: `btst 0x40|0x10, (0x3400082c)`). bit4=RxRDY, bit6=TxRDY both now modelled.
- **The SD state machine (0x48551f80) NEVER RUNS**: during the whole boot + an SD access there are ZERO
  writes to the SD state (`0x50083cd8`, `0x50083bc2`, `0x50083bc1`), and the entire state block
  `0x50083bb8-0x50083bcf` stays 0x00. So the subsystem is completely uninitialised.
- **The SD-SIO init function `0x484b26ca` NEVER RUNS**: ZERO writes to the ch2 config `0x34000820` or
  control `0x34000824` across the entire boot. This is the function that would configure ch2, build the
  ISR table (0x484b26f0: group 0x13->0x484b1f29, group 0x14->0x484b2037) and enable the group-0x14 RX IRQ.
  Because it never runs, group 0x14 stays disabled (ICR 0x34000150 ENABLE bit8=0), the state machine never
  runs, and every SD access hangs on "PLEASE WAIT".
- `0x484b26ca` has **no traceable callers** (no direct call, no absolute/aliased pointer in the image) ->
  it is dispatched indirectly (a MILK task / scheduler entry, or a computed jump) or is gated on a
  hardware-presence / config condition that the emulator never satisfies.

**Reframed problem:** SD emulation is NOT primarily an RX-frame-protocol job -- it is first a matter of
getting the SD subsystem to INITIALISE. The ch2 transport model (status bits + cpsd_queue delivery) is
correct and ready, but it is premature until the init runs.

**Next RE step:** find how `0x484b26ca` (or the SD task that owns it) is dispatched -- inspect the MILK
task table / scheduler registrations and the boot-time system-init list for the SD entry, and find the
gate (likely a "SD hardware present" probe of the `0x90200000` bank or a ch2 status handshake that must
succeed BEFORE the init proceeds). Only once the init runs will the group-0x14 enable + RX handshake matter.

## Driver status update #4 (2026-07-08) — SD-init dispatch + the SD-present strap gate
Went after the SD-init dispatch; corrected an earlier wrong conclusion and found the gate:
- **The SD/SIO init `0x484b26ca` DOES run at early boot** (my earlier "never runs" was a tap-timing
  artifact -- taps installed from a frame callback miss the pre-t=1 boot window). Proof: `0x5006bfd2`
  reads `0x06` during the WAIT, and bit1 = `!strap_bit12` is written by `0x484b2615` -- so that code ran.
- **SD-present gate = strap `0x98070000` bit 12.** `0x484b2615` does `d0 = strap>>12 & 1`, inverts it, and
  stores it as **`0x5006bfd2` bit 1** (an "SD absent" flag, checked at 0x484b24d2/24e6/258f/... and the
  SD init). The driver hardcodes the strap to `0x8000` (bit12=0) -> bit1=1 -> firmware treats SD as absent.
- **But bit 12 is NOT a clean SD-present toggle.** Strapping it on (`0x9000`) DID clear the flag
  (`0x5006bfd2` 0x06->0x04, bit1=0) BUT **broke the boot**: blank LCD, hang BEFORE any ch2 SIO activity
  (0 config/TX/RX/status-polls). So bit12 is entangled with other early-boot config; SD-present can't just
  be strapped on. Reverted to `0x8000`.
- Even with bit1 cleared, the SD **state machine still never ran** (state stays 0) -> there are further
  gates (e.g. `0x5006bfd2` bit2 stays set). The bring-up is multiply gated.
- **REGRESSION FIXED:** last session's `bit6=TxRDY` on the ch2 status (commit 54de957) actually **broke the
  boot** (blank LCD -- ch2 is also MIDI-2, and the poll helper 0x484b288f read garbage). Removed it; boot
  renders again (verified 61k non-black LCD pixels). *(That build had been published broken.)*

**Where this leaves SD:** the subsystem is gated off by design when the strap says "no SD", and the strap
bit that would say "SD present" also drives other early-boot config we don't model, so flipping it hangs
the boot. Cracking SD now means (a) finding the FULL set of what bit12/SD-present enables at boot and
modelling the missing hardware so the boot survives it, then (b) the ch2 CPSD transport (already built)
carries the traffic. This is a substantial multi-part effort, not a one-line fix.

## CORRECTION (2026-07-08, later) — strap bit12 is the BASS-PEDAL SWITCH, not SD-present
Update #3/#4 above concluded that strap `0x98070000` bit12 gates the SD subsystem ("SD board present").
**That was WRONG.** bit12 (= data-bus D28) is the rear-panel **MIDI IN / BASS PEDAL selector SW701**:
`BassPedalSw` (0x484A2CB1) -> `0x484b2615` reads bit12 and stores `!bit12` into the MIDI-in mode flag
`0x5006bfd2` bit1. It has nothing to do with SD. (Now driven by the `REARSW` input port; commit 6846f94.)
Consequences:
- Setting bit12 (strap 0x9000) does NOT break the boot -- the blank-LCD hang seen during the SD dig was the
  separate `bit6=TxRDY` ch2 regression, which was reverted. With bit6 gone, 0x9000 boots fine.
- **The SD subsystem's dormancy root cause is therefore UNKNOWN again.** The valid SD findings still stand
  (link = SIO ch2; status bit4=RxRDY; RX handler 0x484b2037 for group 0x14; the group-0x14 IRQ is disabled;
  the SD state machine never runs; state block all-zero). But WHY it never initialises is NOT the strap.
  Re-open the "what triggers the SD init/state-machine" question without the strap red herring.

## BREAKTHROUGH (2026-07-10) — the dormancy was OUR status bits; the link is now ALIVE

Felipe un-paused the SD work. Root cause of the "SD subsystem never initialises"
mystery: **it was never dormant at all.** An SD link task runs from boot, calling the
link-ready helper 0x484b2889 (~65k calls/s, measured) which polls status 0x3400082C
for bit6|bit4 ten times and yields (kernel semaphore 0x4C03D6BC), forever — because
our ch2 HLE never set TxRDY. Every earlier "the state machine never runs" observation
was downstream of this one missing bit.

Corrections to earlier findings (all verified live and/or adversarially):
- **bit7 of 0x3400082C = RX EMPTY**, not a frame flag: the classifier 0x484b28ee
  reads the RX byte at +9 UNCONDITIONALLY, then treats bit7-set as "no byte" (burst
  ends, task yields). "bit7 diverts the firmware" (update #2) = this empty marker.
- **"bit6 breaks the boot" (update #4) does NOT reproduce** — with bit6 set the boot
  is fine; the old blank-LCD was some other transient. Fear removed.
- **The 0x90200000 "SD host controller bank" was a MISREAD** (adversarially
  CONFIRMED): 0x9020005c/5d/5f etc. are 24-bit sound-parameter database IDs
  (namespace tag 9) fed to the library parameter engine at 0x48566760 — not SD
  registers. The CPSD serial link is the ENTIRE SD path.

The live link (captured):
- Boot t=1.37: firmware configures ch2 (config 0x1181 -> 0x5181 -> 0xD181, control
  0x00, a status-side write 0x3F to +0xD) and transmits its first byte: **0xFE**
  (keep-alive ping, MIDI-active-sense style on the shared UART framing).
- RX byte classes (classifier 0x484b28ee): >=0xF8 keep-alive (handler 0x484b2454),
  0xF0 frame START (in-frame flag 0x50150ade:=1), 0xF7 frame END (flag:=0), 0x80-
  0xF6 and data bytes -> frame parser 0x484b251d. The link task's state dispatch
  (0x484b29c5) counts frames with 30-cycle timeouts.
- Trial HLE response FE F0 00 F7 to the ping: ALL 4 BYTES consumed (popped at
  t=3.4) and classified. **Transport proven end-to-end.** The conversation now
  stalls only on CONTENT: what the real CPSD status frame payload must carry
  (card-present/lid/etc.) to advance the SD init + state machine (0x48551f80).

Driver (commit 0f00f9a): ch2 status = 0x40 | (rx?0x10:0x80) for KN7000; ch2 TX
rerouted from the MIDI-2 UART to cpsd_rx_byte() (first version answers the ping);
placeholder probe removed. KN6000/6500 untouched.

IN FLIGHT: 4-way static-RE workflow (wf_d6998fbd-c86) on (1) who dispatches the SD
state machine 0x48551f80 + gates, (2) the TG-strap boot-to-SD-menu wait condition,
(3) the full ch2 frame format + handshake (the critical one), (4) the 0x90200000
non-bank (DONE: misread confirmed). Next: implement the real CPSD status frames per
(3), then the card/directory/file protocol against a host FAT image (plan Phase 2).

## Status update (2026-07-10, later) — ch2 was MIDI-2 all along; the REAL gate is a MILK property
Workflow findings (adversarially confirmed): **ch2 is the MIDI-2 UART, not CPSD** (ISR
0x484B2037 = Midi2RxIsr; the 372k polls during SD WAIT are the engine loop's idle MIDI
pump; group-0x14 RX IRQ is disabled BY DESIGN — RX is drained by polling). The keep-alive
we injected was feeding a phantom MIDI device — to be retired. The ch2 status-bit fixes
(TxRDY/RxRDY/RX-empty) remain correct as MIDI-2 UART modeling.

The REAL SD architecture: state machine tick 0x485519bc (state byte 0x50083cd8), state 0
gated on **GetProperty(object 0x0210033F, property 0x00060047) != -1** (checked in
0x485521a1); once un-gated it posts a mount job to the disk worker task 0x4854ad90
(created by DiskInit 0x4854aced; ctrl block *(0x50082918)); mount = card-detect ->
card init 0x485630de -> VFS: SD = device 'd' mounted as "C:" (DOS-like fops in RAM device
table 0x500079f8) -> FAT mount -> state 3 + card-ready 0x50083bc2=1. The PHYSICAL SD
transport hides behind the device-'d' fops (still to be enumerated at runtime).

OPEN PUZZLE: forcing the gate had no effect because the tick itself never runs — bp
counters show 0 hits on 0x485519bc AND on the engine-loop tail that calls it
(0x4c02bdfe) AND even on the claimed loop head 0x4c02bbe8 — yet lib bps demonstrably
work (the 1 kHz ISR 0x4C02BB05 counted 18000 earlier) and DiskInit never ran
(*(0x50082918)==0). So the "engine loop 0x4C02BBE8" is NOT the running loop (an
alternate/task variant?), and the SD tick's true dispatcher is still unidentified.
Remaining workflow finders (sd-boot-menu, cpsd-protocol/dispatch) may resolve; else
next: find the RUNNING engine loop (PC-sample the engine task, or trace who calls
0x484574AF live, which demonstrably pumps the demo).

## RESOLUTION (2026-07-10, workflow wf_d6998fbd-c86 complete, all 8 agents CONFIRMED)

**The SD-menu boot mystery: six phantom button presses.** TG-present boots enable the
SD-panel scan; the SD front-panel switch register (byte **0x9CC00008**, ACTIVE-LOW,
bits0-5 = the six CPSD-side transport switches; events 0x7020B5..BA per descriptor
table 0x48613fc4) read 0x00 as plain RAM = all pressed -> deliberate UI takeover to
the SD screen. Fixed: reads return idle (commit d53539d) -> **TG-present boots reach
the PMEM home screen with sound; sound is now ON BY DEFAULT** (the opt-in existed only
because of this). Gate-poke (bit2) obsolete.

**The SD state machine is demand-driven** (true entry 0x485519b7, called at 0x485519bc
-- MN10300 callers target POST-PROLOGUE addresses; the old 0x48551f80 was mid-insn):
DiskInit DOES run at boot (state=0 is normal); triggers = (a) card-insert message
0x107020bb (from the card-detect TRANSITION: polled group-0x1B ICR 0x3400016C bit4
1->0, debounce 0x4854bd39; a statically-present line never edges) then (b) a user SD
action (SD-audio pump 0x48578e6f or the Sdc screens' sync poster 0x4855216b). State-0
UI kick also needs GetProperty(0x0210033F,0x60047) != -1.

**Driver now models the empty slot** (bit4=1 default; insert timer plumbed). Mount
chain once triggered: card checks -> **card-init 0x485630de = the FIRST unmodeled
hardware touch (the real SD data transport, behind VFS device-'d' fops)** -> FAT chain
-> state 3 + card-ready. NEXT (Phase 2): RE 0x485630de's hardware accesses to identify
and HLE the transport, back it with a host FAT image, then wire the insert action +
the 6 SD-panel switches as input ports.

**Tooling lessons (important):** (1) MN10300 `call` performs the callee's register-save
-- callers target entry+prologue; scan for BOTH addresses. (2) MAME debugger actions
must use `d@(addr)` -- `dword@` makes bpset fail SILENTLY (caused false "never runs"
negatives). (3) The ch2 experiments (phantom bytes) wedged the boot -> black LCD; ch2
is MIDI-2, leave it plain.

## Phase 2 progress (2026-07-10, autonomous tick) — THE SD DATA TRANSPORT IS IDENTIFIED

Followed the VFS device-'C' fops to the metal (runtime dump + disasm):
- VFS device table @0x500079f8 (0x28-byte entries, name ptr +0x1C): dev0='A' (floppy,
  fops @0x500079B8), **dev1='C' (SD, fops @0x500079D8: 0x48470328/33E/343/33A/4BB/59F/
  683/689)**, shared FS ops @0x50007990 (0x4846F195..).
- The fops funnel into command poster 0x4847030e -> disk-worker message TYPE 3 (FDC =
  type 2) -> worker handler 0x4854afee -> command switch (3=read, 4=write, 8/A/B/C
  control) -> e.g. cmd-3 builds a command block @0x50007ee4 (sector# LE @+4) and calls
  the transfer primitive **0x4854c3ab** (block size 0x200 = SD sector).
- **THE HARDWARE: the primitives (0x4854bfa2 etc.) strobe ICR 0x34000170 (external-
  interrupt group 0x1C) and read/write the 16-bit register 0x9805000C** (sound-bank
  window; io_w offset +05000C -- the register PC 0x4854BF74 already writes 20,000x at
  boot = the SD probe idling against our zero-returning stub). Shadow word @0x50005200.
  So the CPSD data link = a strobed 16-bit mailbox on the sound bus with a group-0x1C
  handshake -- NOT a UART, NOT the panel link, NOT MMIO at 0x902xxxxx.

NEXT (the concrete HLE): capture the exact strobe/data sequence live (log 0x9805000C
r/w + 0x34000170 during boot-probe and during a mount attempt with the insert edge
fired), RE the wait helpers 0x4854bb89/0x4854bc8f/0x4854c94d/0x4854c1d5, then answer
the probe so card-init 0x485630de succeeds against a host FAT image.

## Phase 2 — TRANSPORT DONE, mount completion in progress (2026-07-10, commits 9279ba0/3457304)

**The SD data transport is a byte-wide SPI master and it WORKS.** Register 0x9805000C =
one full-duplex SPI shift register to the SD slot; handshake via ICR 0x34000170 (group
0x1C, polled bit4). Send-byte primitive 0x4854bf4d: W1C DETECT bit0, write byte, poll
bit4. The firmware speaks STOCK SD SPI: 10x 0xFF wake-up, CMD0 (40 00 00 00 00 95),
CMD1, CMD9 (SEND_CSD). DRIVER: each 0x9805000C write clocks 8 bits (MSB-first) through
MAME's spi_sdcard (m_sdcard, prefer SD, MISO via callback -> m_sdmbx_out) + asserts
group 0x1C; card permanently SS-selected; attach with `-harddisk file.hd`. VERIFIED:
CMD0->R1 0x01, CMD1->0x00, CMD9->CSD, all answered correctly by spi_sdcard.

CARD PRESENCE (commit 3457304): edge-driven. Boot "no card" (bit4=1); if an image is
attached, m_sd_insert_timer fires the 1->0 edge at t=6 (insert msg 0x107020bb -> mount)
and leaves bit4=0 for the debounce (0x4854bd39 <- raw read 0x4854bce0: btst bit4,
clear=present; software override 0x50005204 >=0 -> low byte). No image -> ERROR 93.

MOUNT COMPLETION BLOCKER (the remaining work): mount worker 0x48551f8d requires card
check 0x4854b597 != 0, which returns non-zero ONLY if the "card-initialised" flag
0x5016064c != 0. That flag is set INDIRECTLY by a separate disk-worker init sub-command
(handler 0x4854afee; store-address loaded at 0x4854b0ae/0x4854b11a). The boot-time SPI
init (CMD0/1/9) runs but does NOT set 0x5016064c -> chicken-and-egg. NEXT: from the
in-flight command-layer finder (wf_6a5ed26e-8d4), identify the worker sub-command that
runs the FULL card-init (through CMD9 CSD parse -> capacity -> sets 0x5016064c + the
multiplier 0x50160668 / limit 0x50160664 cmd-3 uses) and what response it needs; ensure
that init is actually invoked in the mount path (it may need a prior "identify" message
the file ops post). Then cmd-3 (read) will pull FAT sectors from the host image.
Host image: raw FAT16 superfloppy, mount as -harddisk (a 64MB test image = sdtest.hd).
