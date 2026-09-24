# KN7000 driver: the source annotations, verbatim

This is the reference copy of every comment the KN7000 driver carried before the
2026-09-24 trim to MAME's house comment volume. It exists so the trim loses nothing:
MAME wants the *what* in the source and the *why* in the PR description and the
project's documentation, and this file is where the *why* went.

Measured before the trim: the 13 matsushita files carried **1124 comment lines across
295 blocks** over 3670 lines of code (30.6%). MAME's own drivers sit at 12.7%
(`model2.h`), 15.0% (`roland_d50.cpp`), 15.2% (`model2.cpp`), 17.3% (`ctk551.cpp`),
23.5% (`ymmu100.cpp`), 24.9% (`gticlub.cpp`), 26.3% (`zr107.cpp`), 28.4%
(`hornet.cpp`). The headers were the outliers -- `kn_tonegen.h` at 67.3% against
`model2.h`'s 12.7%.

Each entry gives the file, the line range in the pre-trim source, and the code the
block preceded, so any of it can be traced back or restored.


---

## `kn7000.cpp` — 177 blocks, 575 lines

### kn7000.cpp:1–55 (55 lines)

```c
// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics SX-KN7000 and related MN10300-based keyboards

    Emulated: the MN10300 CPU and its on-chip peripherals, the LCD, the control
    panel, the floppy and SD interfaces, MIDI, the ADSP-21065L effects DSP, and a
    tone generator that responds to the firmware but has no samples to play - the
    wave ROMs are undumped, so its timbre is a placeholder.

    All five machines are built around a Panasonic MN103002A (MN10300 family,
    AM33 core), running Panasonic's "MILK" object framework.

    Hardware inventory below is taken from the manufacturer's service manuals:

        SX-KN7000  EMID0207013C0 (2002)
        SX-KN6000  EMID9908016C0 (1999)
        SX-KN6500  EMID0101001C0 (2001)
        SX-KN2400, SX-KN2600

    Each manual covers only its own model, except that the SX-KN2400 book's
    parts list reproduces the SX-KN2600's list of main-board integrated
    circuits verbatim - it names devices that appear on no SX-KN2400 schematic
    sheet or board silkscreen, and omits the floppy controller that all three
    SX-KN2400 sources show. The SX-KN2400 devices below are therefore taken
    from its schematics, block diagram and board assembly drawings only.

    Capacities were read from the schematics and parts lists, and confirmed by
    counting address pins. The manuals write ROM sizes in megabits: the KN6000
    manual prints "(64M BIT MASK ROM)" next to parts numbered QSIGX3C64004 and
    up, which fixes both the unit and the meaning of the digits in the part
    number.

    Clocking: the KN6000 and KN6500 manuals print a 32 MHz oscillator at X1,
    feeding a spread-spectrum clock generator at IC6 whose output drives the
    CPU. The KN7000, KN2400 and KN2600 use the same topology, but their
    manuals do not give the frequency of X1, so their core clocks are inferred
    from the KN6000 and KN6500 rather than documented.

    The KN7000's program and table ROMs are not chip reads. They are payloads
    from Panasonic's own firmware update disks, and they validate against the
    checksums that Panasonic ships alongside them: the update descriptor files
    carry a 32-bit sum over the whole payload plus 16-bit sums of each 256 KiB
    block, and every block matches.

    A note on the KN7000's IC16/IC17: these are one pair of 4 MiB flash devices
    on CPU address lines A2-A22, so together they span 8 MiB. Address line A22
    selects between the two regions declared below - the table data occupies
    the half where A22 is low, and the program the half where it is high.

    TODO:
      - dump the wave, rhythm and picture ROMs listed as NO_DUMP below

***************************************************************************/
```

### kn7000.cpp:81–82 (2 lines)

Precedes: `class kn7000_sio_uart_device : public device_t, public device_serial_interface`

```c
//  KN7000 SIO UART -- byte<->bit bridge between a byte-oriented SIO channel and
//  MAME's bit-serial midi_port. One instance per MIDI channel (31250 baud, 8N1).
```

### kn7000.cpp:109–110 (2 lines)

Precedes: `class kn7000_dsp_bridge_device : public device_t, public device_sound_interface`

```c
// kn7000_dsp_bridge_device -- routes the tone-generator audio through the effects
// DSP. It sits between the TG and the speakers with 2 inputs and 2 outputs.
```

### kn7000.cpp:119–121 (3 lines)

Precedes: `void pop_input(int32_t &l, int32_t &r, int32_t &rawl, int32_t &rawr)`

```c
	// Called from the DSP IRQ0 tick (CPU timeline): take one TG input frame, hand back one
	// processed output frame. 24-bit signed samples.
	// rawl/rawr = the un-send-scaled TG mix (for parallel effect sends such as chorus).
```

### kn7000.cpp:149–149 (1 lines)

Precedes: `void set_master_gain(float g) { m_master_gain = g; }`

```c
	// Master output gain (0..1), set from the front-panel MAIN VOLUME slider by the driver.
```

### kn7000.cpp:153–154 (2 lines)

Precedes: `void set_bus_gains(float send, float direct, float ret, float depth)`

```c
	// TG output-bus routing, the REVERB toggle's hardware action: send is what the DSP
	// receives, direct/return the DAC-side crossfade between raw TG and DSP output.
```

### kn7000.cpp:162–164 (3 lines)

Precedes: `void set_effect_returns(float dsp_ret, float multi_ret)`

```c
	// Per-effect DSP returns (each effect has its OWN return level; the reverb toggle only moves
	// the reverb's -- see the tonegen capture). SOUND DSP and MULTI scale their wet by these
	// instead of the reverb return, so reverb on/off no longer mutes them.
```

### kn7000.cpp:197–198 (2 lines)

Precedes: `const int32_t il = int32_t(std::clamp(stream.get(0, s), -1.0f, 1.0f) * SCALE);`

```c
			// push this TG input frame into the DSP's input ring (float -> 24-bit signed),
			// dropping the oldest if full so the DSP always sees recent input (low latency).
```

### kn7000.cpp:201–201 (1 lines)

Precedes: `const float gsend = m_gain_send, gdir = m_gain_direct, gret = m_gain_return;`

```c
			// TG bus routing (reverb toggle): the DSP receives the SEND bus, not the raw mix.
```

### kn7000.cpp:214–214 (1 lines)

Precedes: `ol = il;`

```c
				// DSP not talking yet (early boot) -> dry TG passthrough
```

### kn7000.cpp:220–222 (3 lines)

Precedes: `const uint32_t fill = (m_tx_wr - m_tx_rd + RING) % RING;`

```c
				// Consume the DSP's output only once a small latency buffer has built up, then
				// hold the last sample on underflow. NEVER fall back to the TG here: mixing the
				// (latent) DSP output with the immediate TG phase-cancels and clicks.
```

### kn7000.cpp:257–259 (3 lines)

Precedes: `ol = int32_t(double(ol) * gret * gdepth + double(il) * gdir);`

```c
				// DAC-side crossfade (reverb toggle): DSP return vs TG direct. With reverb ON
				// the pair is {direct 0, return 7F}; OFF is {direct 7F, return 0}, so OFF also
				// mutes the reverb tank at the DAC.
```

### kn7000.cpp:262–263 (2 lines)

Precedes: `const float gdsp_ret = m_gain_dsp_ret, gmul_ret = m_gain_multi_ret;`

```c
				// Chorus/SOUND-DSP/MULTI returns: each is an INDEPENDENT wet, added post-crossfade
				// at its own makeup so it does NOT couple to the reverb TOTAL DEPTH.
```

### kn7000.cpp:275–277 (3 lines)

Precedes: `const float g = m_master_gain;`

```c
			// Front-panel MAIN VOLUME slider: a master output attenuation on the final mix
			// (modelled as a post-DAC analog-style gain; the driver pushes the taper via
			// set_master_gain from the VOL_MAIN adjuster). 1.0 = unity.
```

### kn7000.cpp:323–329 (7 lines)

Precedes: `constexpr offs_t IRQ_VECTOR_BASE = 0x50000000;`

```c
// A maskable interrupt of level L vectors to <base> + IVAR[L]. Every firmware
// clears IVAR0..IVAR6 once at boot and builds a `nop ; jmp handler` thunk at the
// base of work RAM, computing the jump displacement for execution there -- so
// one entry serves all seven levels and the handler address stays the firmware's
// business. Nothing in the 4 MB image branches to the thunk, so it is reached
// from the vector; what decodes work RAM to the CPU's 0x40000000 vector base is
// a board question the available documentation does not answer.
```

### kn7000.cpp:391–393 (3 lines)

Precedes: `required_device<kn_tonegen_base_device> m_tonegen;   // first-cut audio (Phase C Stage 0)`

```c
	// Held by BASE type, like the control panel above: kn7000() installs the two-chip
	// KN7000 decode, kn6000() swaps in the KN6000/KN6500 one (same tag "tonegen", same
	// voice model, different register numbering).
```

### kn7000.cpp:400–401 (2 lines)

Precedes: `required_ioport m_dial;`

```c
	// Control panel button ports and LEDs (CPL = 8 cols, CPC = 5 cols; CPR + the
	// serial HLE device that reads these / drives the LEDs are still to come).
```

### kn7000.cpp:418–419 (2 lines)

Precedes: `required_device<kn_cpanel_base_device> m_cpanel;   // control-panel HLE (buttons, LEDs, an`

```c
	// Held by BASE type: kn7000() installs the KN7000 panel, kn6000() swaps in the
	// KN6000/KN6500 one (same tag "cpanel", same protocol, different matrix + LEDs).
```

### kn7000.cpp:425–426 (2 lines)

Precedes: `uint16_t snd_r(offs_t offset, uint16_t mem_mask = ~0);`

```c
	// Logging handlers for the I/O banks that are not decoded yet.
	// The 0x98000000 sound/peripheral window, whose offsets these decode.
```

### kn7000.cpp:429–432 (4 lines)

Precedes: `uint16_t io_r(offs_t offset, uint16_t mem_mask = ~0);`

```c
	// Everything else that is mapped but not decoded yet: log and move on. This
	// must NOT share a handler with snd_r/snd_w -- MAME gives a handler an offset
	// measured from its own map entry's base, so one switch cannot serve windows
	// at five different bases without aliasing offset 0 of each onto the first.
```

### kn7000.cpp:436–439 (4 lines)

Precedes: `enum { IRQGRP_TIMER = 0x06, IRQGRP_PANEL = 0x1A, IRQGRP_MIDI1 = 0x12, IRQGRP_MIDI2 = 0x14 `

```c
	// --- On-chip interrupt controller (INTC) at 0x34000100 ------------------
	// The register model lives in the CPU core. The driver keeps only board policy:
	// which group each peripheral asserts, the panel transfer-complete re-delivery
	// filter, and the panel-ATN EXTMD edge decode.
```

### kn7000.cpp:445–447 (3 lines)

Precedes: `uint16_t m_kbd_fifo[64] = { };`

```c
	// Keyboard / voice-event FIFO (read at 0x98050004). The firmware polls it for
	// Note events from the key bed: low byte = key code, high byte = velocity,
	// 0xFFFF = empty. Make/break is bit 7 of the key byte, not the velocity.
```

### kn7000.cpp:453–455 (3 lines)

Precedes: `if (note & 0x80) m_tonegen->key_break(note & 0x7F);`

```c
		// Keybed coupling for the tone generator's GATE-FOLLOW voices (brass/sax/organ
		// classes): tell it which key is being made/broken -- the real sub TG hosts this
		// FIFO itself, so it sees these events natively. See key_context()/key_break().
```

### kn7000.cpp:460–464 (5 lines)

Precedes: `uint8_t m_kbd_midi_status = 0;             // MIDI running-status byte`

```c
	// --- MIDI -> internal KEY BED bridge (velocity-sensitive) ------------------
	// A MIDI controller wired here plays the machine's own key bed rather than the
	// rear MIDI IN jacks, so the firmware treats the notes exactly like physical key
	// presses. MIDI note n maps to key index n-36; the 61-key compass is C2..C7 and
	// notes outside it are dropped. Connect a host controller with -kbdmidi <port>.
```

### kn7000.cpp:485–487 (3 lines)

Precedes: `kbd_push(on ? idx : uint8_t(idx | 0x80), on ? vel : 0xff);`

```c
		// make/break = bit 7 of the key byte (see the FIFO note above). A release
		// (MIDI note-off, or note-on velocity 0) sets bit 7; velocity 0xFF = clean
		// key-up. A note-on passes the MIDI velocity straight through.
```

### kn7000.cpp:490–493 (4 lines)

Precedes: `uint16_t m_tg_addr[2] = { 0, 0 };          // latched register address, [0]=main [1]=sub`

```c
	// Tone generators (main 0x98040000 / sub 0x98050000): register-indirect,
	// write-only from the firmware. Address latched at base+0, data written at
	// base+2 -> reg[address]. Voice registers are group<<8|bank<<6|channel
	// (< 0x1000); the 0xFC0x system-refresh group is accepted but not stored.
```

### kn7000.cpp:496–498 (3 lines)

Precedes: `uint16_t m_tg_wave_bank[2] = { 0, 0 };     // latched bank register  (base+6), [0]=main [1`

```c
	// Wave-memory READ port (main 0x9804 / sub 0x9805, offsets +6/+8/+A). The
	// The service-mode WAVE ROM test reads the wave ROMs through this port: bank
	// at base+6, word address at base+8, sample word back at base+A.
```

### kn7000.cpp:504–506 (3 lines)

Precedes: `uint16_t dsp_data_r(offs_t offset, uint16_t mem_mask);`

```c
	// --- Effects DSP (IC306 ADSP-21065L) host port -------------------------
	// The CPU host-boots the SHARC through an index register at 0x98000000 and a
	// data register at 0x9C000000.
```

### kn7000.cpp:511–513 (3 lines)

Precedes: `uint32_t m_dsp_dl_addr = 0;                // reg 0x40: download target address (2x16, low`

```c
	// Host-boot upload state (see dsp_data_w): the firmware sets a target address (reg
	// 0x40), commits a PM/DM block (reg 0x1C = 0xA1/0x41), then streams words to the DMA
	// buffer (index 0x04, 3x16 per 48-bit PM word / 2x16 per 32-bit DM word).
```

### kn7000.cpp:522–524 (3 lines)

Precedes: `static constexpr int DSP_FRAME_HZ = 44100;`

```c
	// Provisional effects-DSP audio frame rate: drives the IRQ0 tick that steps the SHARC
	// kernel's main loop one frame per edge. Stands in for the SPORT/codec frame sync;
	// the value is a plausible placeholder, not measured.
```

### kn7000.cpp:531–531 (1 lines)

```c
	// --- On-chip 16-bit TEMPO timer (mode 0x34001082 / base 0x34001092 / count 0x340010A2)
```

### kn7000.cpp:533–538 (6 lines)

Precedes: `emu_timer *m_sd_insert_timer = nullptr;`

```c
	// --- SD card-detect (GxICR group 0x1B pin, register 0x3400016C) ------------
	// The card/lid switch is an external-interrupt pin whose ICR the firmware polls:
	// bit4 set = no card or lid open, clear = card present. The SD state machine is
	// driven by the detect TRANSITION, so a line that is statically present from
	// power-on never fires it -- model the card as absent at power-on and insert it
	// a few seconds into the boot.
```

### kn7000.cpp:542–544 (3 lines)

Precedes: `output_finder<2> m_sd_leds;              // sd_led0 = SD in use, sd_led1 = SD play/pause`

```c
	// SD "in use" indicator. The CPSD board's front-panel LEDs are not main-CPU
	// outputs, so the lamp is synthesised from real card activity: every SPI byte
	// retriggers a one-shot, and it drops ~250 ms after the last one.
```

### kn7000.cpp:549–550 (2 lines)

Precedes: `void sd_update_carddetect()`

```c
	// The SD slot has a hinged COVER; the firmware reads the cover switch as the
	// card-detect line: closed with a card in means accessible, open means absent.
```

### kn7000.cpp:562–567 (6 lines)

Precedes: `uint16_t m_sdmbx_out = 0xFF;               // last MISO byte (mailbox read value)`

```c
	// --- SD mailbox (register 0x9805000C + ICR group 0x1C handshake) ----------
	// The firmware speaks the standard SD-card SPI protocol through this byte
	// mailbox: wake-up clocks, CMD0, then R1 response reads. Each mailbox write
	// clocks the byte through the spi_sdcard device and asserts INTC group 0x1C;
	// reads return the MISO byte, so the register behaves as a full-duplex SPI
	// data latch.
```

### kn7000.cpp:574–575 (2 lines)

Precedes: `enum { SIO_PANEL = 0, SIO_MIDI1 = 1, SIO_MIDI2 = 2 };`

```c
	// --- SIO: three on-chip USART channels at 0x34000800 / 0x810 / 0x820 ----
	// ch0 = control panel, ch1 = MIDI port 1, ch2 = MIDI port 2.
```

### kn7000.cpp:578–579 (2 lines)

Precedes: `TIMER_CALLBACK_MEMBER(panel_txdone_cb); // one-shot: SIO ch0 sync-transfer complete -> gro`

```c
	// --- Control-panel HLE (the sub-CPU side of the panel serial link) ------
	// LED command bytes arrive as 2-byte [ADDR][DATA] frames on the panel TX;
```

### kn7000.cpp:585–586 (2 lines)

```c
	// --- CPSD (SD sub-CPU MN102H60) HLE on SIO channel 2 --------------------
	// The SD card is reached over SIO channel 2.
```

### kn7000.cpp:594–594 (1 lines)

```c
	// The MN10300/AM33 has a flat 32-bit little-endian address space.
```

### kn7000.cpp:596–597 (2 lines)

Precedes: `map(0x48000000, 0x483fffff).rom().region("table_data", 0);`

```c
	// --- Table / rhythm flash -------------------------------------------
	// kn7000_table.rom, decompressed size 0x3E94D4 bytes (~4 MiB).
```

### kn7000.cpp:600–600 (1 lines)

Precedes: `map(0x48400000, 0x487fffff).rom().region("program", 0);`

```c
	// --- Program flash --------------------------------------------------
```

### kn7000.cpp:603–603 (1 lines)

Precedes: `map(0x50000000, 0x503fffff).ram().share("workram");`

```c
	// --- Work RAM -------------------------------------------------------
```

### kn7000.cpp:606–608 (3 lines)

Precedes: `map(0x4c000000, 0x4cffffff).ram().share("libram");`

```c
	// --- The self-loaded library, and its uncachable alias ------------------
	// The boot code copies a block from the top of the program ROM to 0x8C000000
	// and runs it from 0x4C000000.
```

### kn7000.cpp:611–615 (5 lines)

Precedes: `map(0x90000000, 0x903fffff).ram().share("workram");`

```c
	// External memory is visible twice: cachable at 0x40000000-0x7FFFFFFF and
	// uncachable 0x40000000 above that, which is what the 0x50/0x90, 0x4C/0x8C and
	// 0x44/0x84 pairs are. The firmware writes code through the uncachable view and
	// executes it from the cachable one -- the interrupt vector thunk here, the
	// library at 0x8C000000/0x4C000000.
```

### kn7000.cpp:617–621 (5 lines)

```c
	// 0x96800000-0x969FFFFF inside the window above is the WRITABLE custom-data FLASH
	// (IC21), not RAM. It is carved back out here -- a later map() entry overrides an
// earlier one -- and handed to a real flash device so the firmware's erase and program
// command sequences are decoded instead of being stored as stray bytes. Contents come
// from the "customflash" region, which holds what the "Initial Data" disk installs.
```

### kn7000.cpp:623–624 (2 lines)

Precedes: `map(0x44000000, 0x44ffffff).ram().share("ram44");`

```c
	// Further windows the boot reaches only after the library ROM loads and runs.
	// 0x44000000 is a heavily read and written ~1 MB block, mirrored at 0x84000000.
```

### kn7000.cpp:628–629 (2 lines)

Precedes: `if (!m_lib_mirror)`

```c
	// SD front-panel switch register (byte 0x9CC00008, active-low: bits 0-5 are the
	// six CPSD-side transport switches, 1 = released).
```

### kn7000.cpp:633–635 (3 lines)

Precedes: `return (m_lcdbuf[0x00C00008 >> 2] & 0xFFFFFFC0) | (~m_sdsw->read() & 0x3F);`

```c
			// Bits 0-5 are the six transport switches. Bits 6-7 are the two SD-panel
			// lamps, which the firmware sets and clears with bset/bclr on this byte
			// (eleven sites), so they have to read back for that to work.
```

### kn7000.cpp:638–640 (3 lines)

Precedes: `map(0x9c000000, 0x9c000003).rw(FUNC(kn7000_state::dsp_data_r), FUNC(kn7000_state::dsp_data`

```c
	// Override the low 4 bytes: 0x9C000000 is the effects-DSP host DATA port
	// (paired with the index at 0x98000000), NOT LCD RAM. The framebuffer at
	// 0x9CE00000 and the rest of the bank stay RAM (this narrower entry wins).
```

### kn7000.cpp:643–643 (1 lines)

```c
	// --- Stubs for regions whose behavior is still unknown --------------
```

### kn7000.cpp:645–647 (3 lines)

Precedes: `map(0x41000000, 0x41ffffff).lr8(NAME([](offs_t) -> uint8_t { return 0x00; })).nopw();`

```c
	// --- EXP.CS "SOUND RAM" expansion slots ---------------------------------
	// No expansion board is fitted, so the slot windows read back zero and
	// swallow writes.
```

### kn7000.cpp:651–652 (2 lines)

```c
	// TODO: Picture flash (splash / bitmap graphics), separate device.
	// 0x57800000 is the picture flash; it has no dump, so it is left unmapped.
```

### kn7000.cpp:654–656 (3 lines)

Precedes: `map(0x20000000, 0x2000ffff).rw(FUNC(kn7000_state::io_r), FUNC(kn7000_state::io_w));`

```c
	// --- I/O register banks -------------------------------------------------
	// The I/O registers were recovered by static analysis of the firmware; the ones
	// still undecoded fall through to the logging handlers.
```

### kn7000.cpp:660–661 (2 lines)

Precedes: `if (m_lib_mirror)`

```c
	// KN6000/KN6500: the firmware polls further on-chip 16-bit timer counters
	// (TMnBC at 0x340010a4+, beyond the TM4/TM5 pair the core models) as plain RAM.
```

### kn7000.cpp:664–665 (2 lines)

Precedes: `map(0x36008000, 0x360080ff).rw(FUNC(kn7000_state::io_r), FUNC(kn7000_state::io_w));`

```c
	// The on-chip INTC, SIO and TM4/TM5 timer windows are decoded by the CPU core's
	// own internal map, which is appended after this one.
```

### kn7000.cpp:667–667 (1 lines)

Precedes: `map(0x36008084, 0x36008085).lr16(NAME([]() -> uint16_t { return 0x0001; }));`

```c
	// GPIO input port 0x36008084: bit 0 = panel-link ready/presence, held asserted.
```

### kn7000.cpp:669–670 (2 lines)

Precedes: `if (!m_lib_mirror)`

```c
	// GPIO output latch 0x36008004: bit1 = the SD card's SPI chip select, active-low
	// (bclr asserts, bset releases).
```

### kn7000.cpp:681–683 (3 lines)

Precedes: `map(0x98020000, 0x9802000f).rw(FUNC(kn7000_state::fdc_r), FUNC(kn7000_state::fdc_w));`

```c
	// Floppy disk controller IC103 (C1DB00000607, N82077AA/PC-AT-compatible) at
	// 0x98020000, carved out of the io window above -- it must come after it so the
	// narrower entry wins. Confirmed against the service manual.
```

### kn7000.cpp:685–686 (2 lines)

Precedes: `map(0x98010000, 0x98010003).rw(FUNC(kn7000_state::fdc_dma_r), FUNC(kn7000_state::fdc_dma_w`

```c
	// FDC.DACK byte slot at 0x98010000 (decoder Y1). The software-DMA handler, invoked
	// per FDC.DRQ on INTC group 0x18, moves one FIFO byte through here per request.
```

### kn7000.cpp:689–689 (1 lines)

Precedes: `}`

```c
	// TODO: replace the logging handlers with real device models.
```

### kn7000.cpp:693–695 (3 lines)

Precedes: `void kn7000_state::dsp_data_mem(address_map &map)`

```c
// IC307/IC308, the effects DSP's external SRAM. On the 21065L, 0x20000 is where
// external memory begins; the effects kernel clears its delay-line buffers there at
// boot and the reverb and echo effects run out of them.
```

### kn7000.cpp:702–702 (1 lines)

Precedes: `uint16_t kn7000_state::tg_wave_read(int tg)`

```c
// Read one sample word out of a wave ROM through the tone generator's own port.
```

### kn7000.cpp:732–732 (1 lines)

Precedes: `if (offset == 0x38000)`

```c
	// 0x98070000 (offset 0x38000 within the 0x98000000 window): a status/strap word.
```

### kn7000.cpp:735–737 (3 lines)

Precedes: `return 0x8000 | 0x0006 | (m_rearsw->read() & 0x1000);`

```c
		// bit12 (data bus D28) = the rear-panel MIDI IN / BASS PEDAL selector, SW701.
		// bits 1..2 = the TG-present strap: with bit1 clear the firmware leaves the
		// TG-enable gate closed and the machine is silent, so report both TGs present.
```

### kn7000.cpp:740–741 (2 lines)

Precedes: `if (offset == 0x28002)`

```c
	// 0x98050004 (offset 0x28002): the VOICE-EVENT / keyboard FIFO -- the interface
	// what the KN5000 firmware calls "keyboard input".
```

### kn7000.cpp:748–750 (3 lines)

Precedes: `if (offset == 0x28006)                            // 0x9805000C: SD mailbox data latch`

```c
	// 0x9805000E (offset 0x28007): sound-interface register; the init loop at
	// 0x4854BC59 writes a value (d1|0x80) and spins until it READS BACK what it
	// wrote (setlb/lne with a 2-tick timeout) -- a readback latch unblocks it.
```

### kn7000.cpp:755–756 (2 lines)

Precedes: `if (offset == 0x20005) return tg_wave_read(0);`

```c
	// Wave-memory read port DATA (main 0x9804000A / sub 0x9805000A): return the
	// sample word for the latched (bank, address). See tg_wave_read().
```

### kn7000.cpp:759–761 (3 lines)

Precedes: `if (!machine().side_effects_disabled())`

```c
	// (The FDC is IC103 at 0x98020000 = decoder slot Y2; 0x98010000 = Y1 = FDC.DACK, the DMA-ack strobe,
	// not the register base -- that is why the old 0x98010000 probe never saw register traffic. The FDC
	// registers are carved out of this io window at 0x98020000-0f -> fdc_r/fdc_w.)
```

### kn7000.cpp:775–777 (3 lines)

Precedes: `switch (offset)`

```c
	// Tone-generator register-indirect write interface (write-only; see the member
	// declaration). Modeling it here captures the register file and keeps the
	// constant TG traffic out of the snd_w log.
```

### kn7000.cpp:794–795 (2 lines)

Precedes: `case 0x20003: m_tg_wave_bank[0] = data; return;              // main TG wave bank    (0x98`

```c
	// Wave-memory read port: the service-mode WAVE ROM test latches a bank at
	// base+6 and a word address at base+8, then reads the sample word at base+A.
```

### kn7000.cpp:801–801 (1 lines)

Precedes: `logerror("%s: snd_w +%06X = %04X mask %04X\n", machine().describe_context(),`

```c
	// (The FDC registers at 0x98020000-0f are carved out of this window -> fdc_r/fdc_w; see io_r note.)
```

### kn7000.cpp:806–806 (1 lines)

Precedes: `uint16_t kn7000_state::dsp_data_r(offs_t offset, uint16_t mem_mask)`

```c
// Effects-DSP host DATA port at 0x9C000000 (paired with the index at 0x98000000).
```

### kn7000.cpp:809–810 (2 lines)

Precedes: `switch (m_dsp_index)`

```c
	// Answer the host register read selected by the latched index. The boot probe
	// reads register 0 and requires 0x20 to consider the DSP alive.
```

### kn7000.cpp:824–824 (1 lines)

Precedes: `switch (m_dsp_index)`

```c
	// Host boot: decode the upload protocol and stream the program into the DSP.
```

### kn7000.cpp:831–832 (2 lines)

Precedes: `if (data == 0xa1)      { m_dsp_mode = 1; m_dsp_cur = m_dsp_dl_addr; m_dsp_wcnt = 0; m_dsp_`

```c
		// Upload framing: 0xA1 opens a PM block and 0x41 a DM block, both targeting the
		// address last written to register 0x40; words then stream through index 0x04.
```

### kn7000.cpp:840–841 (2 lines)

Precedes: `if (m_dsp_running && m_dsp_mode == 1)`

```c
				// A runtime upload into PROGRAM memory changes live code behind the DRC's
				// back, so tell it to invalidate.
```

### kn7000.cpp:850–853 (4 lines)

Precedes: `m_dsp_irq_timer->adjust(attotime::from_hz(DSP_FRAME_HZ), 0, attotime::from_hz(DSP_FRAME_HZ`

```c
				// Start the audio frame tick: the kernel's reset handler enables IRQ0 and
				// then IDLEs waiting for the first one, which drives its main loop one audio
				// frame per edge. On real hardware IRQ0 comes from the SPORT/codec frame
				// sync; a periodic pulse stands in for it here.
```

### kn7000.cpp:864–865 (2 lines)

Precedes: `const uint64_t w = (uint64_t(m_dsp_wbuf[2]) << 32) | (uint64_t(m_dsp_wbuf[1]) << 16) | m_d`

```c
				// The firmware streams the 3 halfwords LSW-first, so the 48-bit PM word is
				// wbuf[2]:wbuf[1]:wbuf[0] (verified: puts the opcode field in the high bits).
```

### kn7000.cpp:886–887 (2 lines)

```c
//  On-chip interrupt controller (INTC) -- board-policy hooks only
// The INTC register model lives in the MN10300 core; only board policy is here.
```

### kn7000.cpp:891–894 (4 lines)

Precedes: `if (!m_dsp_running)`

```c
	// Audio frame tick: pulse the effects DSP's IRQ0, the kernel's frame interrupt. Only the
	// assert is needed -- the SHARC clears the pending bit when it takes the interrupt, so one
	// edge is delivered per tick. The kernel configures IRQ0 edge-triggered (MODE2 0x18011) and
	// its handler at PM 0x8020 sets R13=1 to hand a frame to the main loop.
```

### kn7000.cpp:898–899 (2 lines)

Precedes: `constexpr uint32_t obuf = 0xC342;   // unit-0 effect RETURN (L,R) -> TG -> DAC`

```c
	// Audio path: none of the DSP's TX slots feeds a DAC directly. All four SPORT TX
	// pins loop back, so the processed audio is read out of the kernel's own buffers.
```

### kn7000.cpp:905–905 (1 lines)

Precedes: `float chsend = m_tonegen->gain_chorus();`

```c
		// Multi-unit routing, from the effect-select and download-port traffic:
```

### kn7000.cpp:932–933 (2 lines)

Precedes: `dm.write_dword(ibuf,     uint32_t(il));`

```c
		// The kernel programs the SPORTs with DTYPE=01 ("right-justify, sign-extend
		// MSBs", TRM ch.9), so the buffers hold sign-extended 24-bit samples.
```

### kn7000.cpp:938–938 (1 lines)

Precedes: `dm.write_dword(0xC376, uint32_t(int32_t(double(rawl) * chsend)));`

```c
			// feed the CHORUS unit (9) its send: raw TG mix scaled by the chorus send level.
```

### kn7000.cpp:944–944 (1 lines)

Precedes: `dm.write_dword(0xC366, uint32_t(int32_t(double(rawl) * dspsend)));`

```c
			// feed the SOUND DSP insert (unit 2 = RIGHT1): raw TG mix scaled by its send level.
```

### kn7000.cpp:950–950 (1 lines)

Precedes: `dm.write_dword(0xC364, uint32_t(int32_t(double(rawl) * mulsend)));`

```c
			// feed the MULTI unit (1): raw TG mix scaled by its send level.
```

### kn7000.cpp:963–964 (2 lines)

```c
// (The on-chip TEMPO timer -- TM5, the clock behind all sequenced playback --
// is modeled in the MN10300 core now: mn10300.cpp tm5_*.)
```

### kn7000.cpp:968–969 (2 lines)

Precedes: `m_sd_leds[0] = 1;`

```c
	// SD "in use" lamp: every mailbox byte is a live SPI transfer, so the card is being accessed. Light
	// the LED and (re)arm the one-shot; a burst of bytes keeps it steady, and it drops ~250 ms after the last.
```

### kn7000.cpp:973–975 (3 lines)

Precedes: `if (m_sdcard)`

```c
	// Full-duplex SPI byte transfer: shift the 8 bits through the card (MSB
	// first), collecting MISO into m_sdmbx_out; then raise the ack (group 0x1C
	// DETECT/REQUEST -- polled, not interrupt-driven).
```

### kn7000.cpp:992–994 (3 lines)

Precedes: `sd_update_carddetect();`

```c
	// The card appears: clear the group-0x1B DETECT/REQUEST bits -> the polled
	// reader sees bit4 drop, the debounce runs, and the firmware posts the
	// card-insert message (see the member declaration for the chain).
```

### kn7000.cpp:998–998 (1 lines)

Precedes: `TIMER_CALLBACK_MEMBER(kn7000_state::sd_inuse_off)`

```c
// SD "in use" one-shot expiry: no SPI byte for ~250 ms -> the card is idle, clear the lamp.
```

### kn7000.cpp:1006–1008 (3 lines)

Precedes: `sd_update_carddetect();`

```c
	// The user opened or closed the SD slot cover: update the card-detect line.
	// Closing with a card in produces the insert edge (mount); opening drops
	// access so the firmware shows "ERROR 93: SD lid is open" on the SD screens.
```

### kn7000.cpp:1012–1013 (2 lines)

Precedes: `INPUT_CHANGED_MEMBER(kn7000_state::kbd_key)`

```c
// A PC-key note press or release: push a voice event into the key-bed FIFO the
// firmware polls. param carries the key index; velocity is fixed for host keys.
```

### kn7000.cpp:1020–1021 (2 lines)

```c
//  SIO -- three on-chip USART channels (panel + two MIDI ports)
//
```

### kn7000.cpp:1024–1025 (2 lines)

Precedes: `TIMER_CALLBACK_MEMBER(kn7000_state::panel_txdone_cb)`

```c
// The main-CPU SIO channel-0 sync-transfer completion, INTC group 0x11. Deferred
// ~40us so the panel's reply cannot overtake the ISR that acknowledges it.
```

### kn7000.cpp:1032–1033 (2 lines)

Precedes: `TIMER_CALLBACK_MEMBER(kn7000_state::volume_scan)`

```c
// Front-panel MAIN VOLUME slider -> master output gain on the final mix. A squared
// taper approximates a natural volume law (the exact analog-slider taper is unknown);
```

### kn7000.cpp:1041–1043 (3 lines)

Precedes: `m_sd_leds[1] = (m_lcdbuf[0x00C00008 >> 2] & 0xC0) ? 1 : 0;`

```c
	// SD panel lamp. The firmware drives two lamp bits, 6 and 7, of the SD panel
	// GPIO byte; which bit is which lamp is not established, so the single output
	// the artwork carries follows either of them.
```

### kn7000.cpp:1048–1050 (3 lines)

```c
// --- Control-panel buttons and LEDs -----------------------------------------
// Like the KN5000, the KN7000 front panel is driven by dedicated sub-CPUs that
// scan the matrix and report over a serial link; kn7000_cpanel models them.
```

### kn7000.cpp:1053–1055 (3 lines)

```c
	// The tone generators (IC201/IC205) and the effects DSP (IC306, ADSP-21065L) are
	// always fitted on the KN7000, so the firmware voices notes and processes effects
	// unconditionally -- there are no machine-configuration switches for them.
```

### kn7000.cpp:1057–1059 (3 lines)

```c
	// Front-panel BUTTON matrix (CP{board}_SEG{col}) is now declared by the control-panel
	// device itself (kn7000_cpanel_device::device_input_ports(), in kn7000_cpanel.cpp) -- the
	// panel sub-CPUs own those inputs. The layout references them as "cpanel:CP{board}_SEG{col}".
```

### kn7000.cpp:1064–1067 (4 lines)

Precedes: `PORT_START("VOL_MAIN")   PORT_ADJUSTER(80, "Main Volume")`

```c
	// Front-panel volume sliders (the ESQ1-style slider script in kn7000.lay binds
	// these; PORT_ADJUSTER gives a 0-100 value the layout knob animates). MAIN drives
	// the DSP bridge's master gain and APC/SEQ is sent to the panel as a CP 0xD2
	// frame; MIC and LINE-IN are read but reach no audio path yet.
```

### kn7000.cpp:1072–1074 (3 lines)

Precedes: `PORT_START("TEMPO_KNOB") PORT_ADJUSTER(50, "Tempo / Program Knob")`

```c
	// TEMPO/PROGRAM knob: a RELATIVE encoder (wire 0x17). The adjuster value itself is meaningless to the
	// firmware -- the control-panel device (kn7000_cpanel) converts its CHANGES into [0x17, position] encoder steps. Dragging
	// the layout knob up raises the tempo, down lowers it. Centre start so there is room to drag both ways.
```

### kn7000.cpp:1077–1077 (1 lines)

Precedes: `PORT_START("REARSW")`

```c
	// Rear-panel MIDI IN / BASS PEDAL selector switch, SW701 on the JACK board.
```

### kn7000.cpp:1083–1084 (2 lines)

Precedes: `PORT_START("CPSD_SDSW")   // SD play/vol board -- GPIO 0x9CC00008, not on the CP serial li`

```c
	// SD front-panel switches (CPSD-side matrix, byte 0x9CC00008 ACTIVE-LOW,
	// bits 0-5 -> panel events 0x7020B5..0x7020BA per descriptor SEG1D @0x48613fc4).
```

### kn7000.cpp:1093–1094 (2 lines)

Precedes: `PORT_START("SDCOVER")`

```c
	// SD slot cover switch. The slot has a hinged cover and the firmware only looks
	// for a card while it is closed.
```

### kn7000.cpp:1100–1101 (2 lines)

Precedes: `#define KN_KEYM(mask, idx, gm, name) \`

```c
	// Music key bed: the full 61 keys, C2..C7. The FIFO value is the key index,
	// which is the internal note number minus 36.
```

### kn7000.cpp:1180–1181 (2 lines)

Precedes: `constexpr offs_t LCD = (0x9ce00000 - 0x9c000000) / 4;      // word offset of the framebuff`

```c
	// Present the firmware's OWN composited image -- the exact bytes the real LCD
	// controller scans; the firmware composites the planes in software.
```

### kn7000.cpp:1184–1185 (2 lines)

Precedes: `if (m_lcd_kn24)`

```c
	// KN2400/KN2600: a 320x240 FOUR-LEVEL GRAYSCALE panel. The firmware composites into a
// 2bpp buffer at 0x9C800000 (stride 80 bytes, MSB-first pixel pairs, 0 = lightest).
```

### kn7000.cpp:1204–1206 (3 lines)

Precedes: `const bool kn6 = m_lcd_kn6;`

```c
	// KN7000: 640x240 RGB565, scanned top-to-bottom. KN6000/KN6500: the same composited buffer,
	// but the panel is RGB555 and physically mounted rotated 180 degrees -- so read it reversed
	// (bottom-right to top-left) and decode 5-5-5. (Decoding a 555 gray as 565 tinted it blue.)
```

### kn7000.cpp:1225–1227 (3 lines)

Precedes: `uint32_t kn7000_state::customflash_r(offs_t offset, uint32_t mem_mask)`

```c
// IC21, the custom-data flash at 0x96800000 -- a 16 Mbit bottom-boot part (MBM29LV160B class).
// The firmware drives it with the full AMD command set: unlock at +0xAAAA/+0x5554,
// then autoselect, erase and program.
```

### kn7000.cpp:1248–1249 (2 lines)

```c
	// output_finders auto-resolve in this MAME version (see kn5000_cpanel) --
	// no explicit resolve() call is needed or available.
```

### kn7000.cpp:1251–1253 (3 lines)

Precedes: `if (m_customflash)`

```c
	// IC21 custom-data flash at 0x96800000, over the top of the broad RAM window. Installed
	// here rather than in the address map because the map is shared and is also constructed
	// during the validity check, when this optional device is not resolved.
```

### kn7000.cpp:1273–1274 (2 lines)

Precedes: `m_panel_txdone = timer_alloc(FUNC(kn7000_state::panel_txdone_cb), this);`

```c
	// Periodic control-panel button scan (the real sub-CPUs poll their matrices
	// continuously and report changes over the serial link).
```

### kn7000.cpp:1278–1279 (2 lines)

```c
	// (The AM33 maskable-interrupt vectors are configured per level on the core
	// in kn7000/kn6000(machine_config) -- set_maskable_vector.)
```

### kn7000.cpp:1282–1285 (4 lines)

Precedes: `if (m_lib_mirror)`

```c
	// KN6000/KN6500: unlike the KN7000, which self-loads its library, these
	// firmwares read the library at 0x4C000000/0x8C000000 without ever writing
	// it. What backs that window on the board is not established; filling it from
	// the program ROM here is what makes the boot find what it reads.
```

### kn7000.cpp:1293–1293 (1 lines)

Precedes: `save_item(NAME(m_c11_unserviced));`

```c
	// (INTC + TM5 timer state is save_item'd by the MN10300 core now.)
```

### kn7000.cpp:1296–1296 (1 lines)

Precedes: `save_item(NAME(m_snd_500e));`

```c
	// (SIO channel state is save_item'd by the MN10300 core now.)
```

### kn7000.cpp:1303–1305 (3 lines)

```c
	// (SIO / INTC / TM5 state is cleared by the MN10300 core's device_reset,
	// which runs BEFORE this -- after-children ordering -- so the SD group-0x1B
	// re-init below lands on top of the cleared GxICR array.)
```

### kn7000.cpp:1307–1307 (1 lines)

Precedes: `m_dsp->set_input_line(INPUT_LINE_HALT, ASSERT_LINE);`

```c
	// Hold the SHARC halted; the firmware host-boots it through dsp_data_w.
```

### kn7000.cpp:1318–1318 (1 lines)

Precedes: `m_vol_timer->adjust(attotime::from_hz(250), 0, attotime::from_hz(250));`

```c
	// Poll the MAIN VOLUME slider -> DSP master gain at ~250 Hz.
```

### kn7000.cpp:1321–1322 (2 lines)

Precedes: `if (m_lib_mirror)`

```c
	// System tick, ~1 kHz. The real rate is unknown; the input clock has not been
	// identified. The interrupt dispatches to the firmware's RTOS handler.
```

### kn7000.cpp:1324–1325 (2 lines)

Precedes: `m_sys_timer->adjust(attotime::from_seconds(2), 0, attotime::from_hz(1000));`

```c
		// KN6000/KN6500: delay the tick past the single-threaded part of the boot, so
		// the scheduler exists by the time the first one arrives.
```

### kn7000.cpp:1331–1331 (1 lines)

Precedes: `if (!m_lib_mirror)`

```c
	// (TM5 mode/base/countdown are reset by the core's device_reset.)
```

### kn7000.cpp:1334–1335 (2 lines)

Precedes: `m_maincpu->intc_icr_set(0x1B, 0x0012);`

```c
		// SD card-detect: the polled group-0x1B ICR (0x3400016C) bit4 reads
		// 1 = no card, 0 = card present.
```

### kn7000.cpp:1348–1349 (2 lines)

Precedes: `uint8_t kn7000_state::fdc_r(offs_t off)`

```c
// ================= FDC (IC103, C1DB00000607, N82077AA-compatible) at 0x98020000 =================
// Confirmed by the SX-KN7000 service-manual schematic (chip-select decoder IC1 TC74VHC138F, page 101:
```

### kn7000.cpp:1376–1377 (2 lines)

Precedes: `void kn7000_state::fdc_irq_w(int state)`

```c
// FDC interrupt and DMA-request lines -> on-chip INTC group 0x18. The sector-data
// phase is software DMA: the FDC asserts DRQ and the handler moves one byte.
```

### kn7000.cpp:1388–1389 (2 lines)

Precedes: `uint8_t kn7000_state::fdc_dma_r(offs_t)`

```c
// FDC.DACK byte slot at 0x98010000 (decoder Y1). A read/write here transfers one FIFO byte to/from the
// FDC in the current DMA operation (asserts DACK); the software-DMA ISR uses it per FDC.DRQ.
```

### kn7000.cpp:1402–1404 (3 lines)

Precedes: `device.option_add("35hd", FLOPPY_35_HD);   // 3.5" high-density (1.44 MB, the KN7000 defau`

```c
	// The KN7000 formats 1.44 MB "2HD" disks (firmware string "1.44M Byte format : 2HD" @0x25D160)
	// and also accepts 720 KB "2DD" media (firmware: '…"2HD". It can be used only "2DD" type in this
	// mode'). A 3.5" HD drive reads/writes both, so default to 35hd and offer 35dd as an option.
```

### kn7000.cpp:1411–1412 (2 lines)

Precedes: `FUJITSU_29LV160B(config, m_customflash);`

```c
	// IC21, the custom-data flash. The firmware identifies the part with a JEDEC
	// autoselect before writing to it.
```

### kn7000.cpp:1415–1417 (3 lines)

Precedes: `MN103002A(config, m_maincpu, 16_MHz_XTAL * 2);`

```c
	// Panasonic MN103002A (MN10300/AM33 core), IC4 on MAIN 1/5. A 16.0 MHz
	// crystal feeds the on-chip PLL, which doubles it (service manual,
	// SCHEMATIC DIAGRAM-1).
```

### kn7000.cpp:1420–1421 (2 lines)

Precedes: `m_maincpu->set_reset_pc(0x48400000);`

```c
	// The MN10300 always resets to 0x40000000; this is where the board answers
	// that, and the flash does begin with the vector table it implies.
```

### kn7000.cpp:1426–1427 (2 lines)

Precedes: `m_maincpu->intc_ack_cb().set([this](uint8_t group) {`

```c
	// Group 0x11 (panel transfer complete) is level-like until serviced: if a
	// completion landed before the ISR's ack wiped it, re-deliver it after.
```

### kn7000.cpp:1432–1432 (1 lines)

Precedes: `m_maincpu->intc_accept_cb().set([this](uint8_t group) {`

```c
	// group 0x11 latched into the IAGR at accept -> it has been serviced.
```

### kn7000.cpp:1437–1438 (2 lines)

Precedes: `m_maincpu->intc_extmd_cb().set([this](uint16_t data) {`

```c
	// EXTMD written: decode the panel-ATN edge re-arm transition (bits 7:6
	// 11b -> 10b) against our previous-value shadow.
```

### kn7000.cpp:1446–1446 (1 lines)

Precedes: `m_maincpu->sio_tx_done_cb<0>().set([this](int state) {`

```c
	// On-chip SIO routing; the register model itself lives in the CPU core.
```

### kn7000.cpp:1448–1448 (1 lines)

Precedes: `m_panel_txdone->adjust(attotime::from_usec(40), 3);`

```c
		// Sync-transfer completion -> group 0x11, always deferred (see panel_txdone_cb).
```

### kn7000.cpp:1451–1452 (2 lines)

Precedes: `m_maincpu->sio_tx_cb<0>().set([this](uint8_t data) { m_cpanel->tx_byte(data); });`

```c
	// The main CPU transmits 7-byte frames with interleaved line syncs; the
	// panel HLE parses them, decodes LED writes, and queues replies.
```

### kn7000.cpp:1454–1455 (2 lines)

Precedes: `m_maincpu->sio_rx_rdy_cb<0>().set([this](int state) { intc_assert(0x10); });`

```c
	// One group-0x10 interrupt per reply byte the panel delivers into the ch0
	// RX ring (the state-8 handler reads 0x34000809 per interrupt).
```

### kn7000.cpp:1457–1458 (2 lines)

Precedes: `m_maincpu->sio_rx_enable_cb<0>().set([this](int state) { m_cpanel->rx_enable(); });`

```c
	// Config bit14 written set (group-0x1A ISR pass 2): the panel may now send
	// its queued reply.
```

### kn7000.cpp:1460–1462 (3 lines)

Precedes: `m_maincpu->sio_tx_cb<1>().set(m_midi_uart[0], FUNC(kn7000_sio_uart_device::write));`

```c
	// ch1/ch2 = MIDI 1 / MIDI 2: TX bytes serialize out through the UART
	// bridges below; each received byte raises the channel's RX group
	// (MIDI-1 0x12, MIDI-2 0x14).
```

### kn7000.cpp:1468–1470 (3 lines)

Precedes: `SCREEN(config, m_screen).set_lcd();`

```c
	/* video hardware */
	// LCD panel. Exact geometry is uncertain: the KN7000 front-panel LCD is
// reported as either 320x240 or 640x240. Using 640x240 as a placeholder.
```

### kn7000.cpp:1474–1474 (1 lines)

Precedes: `m_screen->set_size(640, 240);`

```c
	// 640x240 8bpp LCD (proven from the blitter stride 0x280 and height 0xF0).
```

### kn7000.cpp:1479–1479 (1 lines)

Precedes: `KN7000_SIO_UART(config, m_midi_uart[0], 0);`

```c
	// --- MIDI ports (SIO channels 1 & 2 at 0x34000810 / 0x34000820) ---------
```

### kn7000.cpp:1486–1487 (2 lines)

Precedes: `KN7000_SIO_UART(config, m_kbd_midi_uart, 0);`

```c
	// MIDI -> internal key bed (velocity). A dedicated IN port so a controller
	// plays the key bed itself, distinct from the two rear MIDI IN jacks.
```

### kn7000.cpp:1498–1500 (3 lines)

Precedes: `KN7000_CPANEL(config, m_cpanel);`

```c
	// Control panel HLE (buttons, LEDs, analog controls) on SIO channel 0. The
	// device queues replies + button/analog events; the driver bridges its ATN
	// pulse and reply bytes to the main CPU's interrupt controller and SIO0 RX.
```

### kn7000.cpp:1504–1506 (3 lines)

Precedes: `m_cpanel->set_dial_port(m_dial);`

```c
	// The panel scan-matrix button ports (CP{board}_SEG{col}) are declared by the control-panel
	// device itself now (kn7000_cpanel_device::device_input_ports()); no wiring needed here. The
	// shared front-panel analog controls stay in the driver's INPUT_PORTS and are handed over by tag:
```

### kn7000.cpp:1511–1511 (1 lines)

Precedes: `SPEAKER(config, "speaker", 2).front();`

```c
	// --- Sound. Shared by every model that reuses this config.
```

### kn7000.cpp:1513–1514 (2 lines)

Precedes: `SPI_SDCARD(config, m_sdcard, 0);`

```c
	// Every model reusing this config has the floppy drive; the ones without an
	// SD slot remove it below.
```

### kn7000.cpp:1519–1519 (1 lines)

Precedes: `N82077AA(config, m_fdc, 24'000'000);`

```c
	// IC103 floppy disk controller (custom C1DB00000607, N82077AA/PC-AT-compatible) + 3.5" drive.
```

### kn7000.cpp:1523–1525 (3 lines)

Precedes: `FLOPPY_CONNECTOR(config, "fdc:0", kn7000_floppies, "35hd", floppy_image_device::default_pc`

```c
	// PC floppy formats: KN7000 disks are FAT12 and "interchangeable with a PC" (standard IBM-PC MFM),
	// so use default_pc_floppy_formats -- it adds FLOPPY_PC_FORMAT (raw .img round-trip) on top of the
	// MFM containers, unlike the KN5000's default_mfm_floppy_formats which cannot load a raw PC image.
```

### kn7000.cpp:1529–1531 (3 lines)

Precedes: `KN7000_DSP_BRIDGE(config, m_dspbridge, 0);`

```c
	// Route the tone-generator audio through the effects-DSP bridge, then to the speakers.
	// The bridge is transparent (passes the TG through) unless the effects DSP is running, so
	// this does not change the DSP-off behaviour.
```

### kn7000.cpp:1538–1540 (3 lines)

Precedes: `ADSP21065L(config, m_dsp, 60'000'000);`

```c
	// IC306 effects DSP -- Analog Devices ADSP-21065L SHARC, host-booted by the
	// MN10300 over the 0x98000000 (index) / 0x9C000000 (data) port. The part is
	// marked S21065LKS240: the KS-240 grade is 60 MHz core, 240 MFLOPS.
```

### kn7000.cpp:1542–1543 (2 lines)

Precedes: `m_dsp->enable_recompiler();`

```c
	// The effects kernel is fixed-point-MAC heavy: interpreting it drops the machine
	// to ~36% of real time, where the recompiler keeps it near 90%.
```

### kn7000.cpp:1548–1549 (2 lines)

Precedes: `}`

```c
	// TODO: the DSP's SDRAM (IC307/8), the SPORT audio path, and the rear USB
	//       subsystem, whose co-processor firmware is undumped.
```

### kn7000.cpp:1555–1556 (2 lines)

Precedes: `config.set_default_layout(layout_kn7000);`

```c
	// Clickable front-panel artwork: buttons bound to the ioports, LEDs bound to
	// the cpl_led/cpc_led/cpr_led outputs.
```

### kn7000.cpp:1560–1562 (3 lines)

Precedes: `void kn7000_state::kn6000(machine_config &config)`

```c
// KN6000/KN6500 reuse the KN7000 machine, but their firmware expects the library
// at 0x4C000000 to be populated already rather than self-loading it; machine_start
// fills it from the program ROM.
```

### kn7000.cpp:1568–1569 (2 lines)

Precedes: `config.device_remove("tonegen");`

```c
	// The KN6000/KN6500 front panel speaks the same CP wire protocol as the KN7000,
	// so only the matrix geometry and the LED decode differ.
```

### kn7000.cpp:1574–1574 (1 lines)

Precedes: `config.device_remove("sdcard");`

```c
	// The KN6000 and KN6500 have the floppy drive but no SD slot.
```

### kn7000.cpp:1585–1586 (2 lines)

Precedes: `}`

```c
	// No artwork: the KN6000/KN6500 panel layout is not finished, and the KN7000's
	// would put every clickable element at the wrong place with the wrong binding.
```

### kn7000.cpp:1589–1592 (4 lines)

Precedes: `void kn7000_state::kn6500(machine_config &config)`

```c
// The KN6500 is the KN6000 machine with a different firmware BUILD. Same hardware
// (one D82398GD001 tone generator, same 64 voices, same register numbering), but the
// build's RAM layout shifted, so the driver-side voice-record binding has to follow it:
// the per-TG-slot voice record sits one record earlier than the KN6000's.
```

### kn7000.cpp:1598–1600 (3 lines)

Precedes: `void kn7000_state::kn24_base(machine_config &config)`

```c
// KN2400/KN2600 reuse the KN7000 machine, but their firmware self-loads its library
// into WORK RAM at 0x50120000 through the 0x90000000 (+0x40000000) alias window, so
// that window must alias work RAM instead of being a separate share (see maincpu_mem).
```

### kn7000.cpp:1603–1606 (4 lines)

Precedes: `kn7000_base(config);`

```c
	// PLACEHOLDER: this inherits the KN7000's control panel, whose scan matrix is
	// the wrong one -- the SX-KN2400/KN2600 front panel is a different and smaller
	// one that has not been drawn. It does not inherit the artwork; only kn7000()
	// calls set_default_layout.
```

### kn7000.cpp:1609–1609 (1 lines)

Precedes: `m_screen->set_size(320, 240);`

```c
	// 320x240 4-level grayscale LCD (2bpp framebuffer at 0x9C800000).
```

### kn7000.cpp:1614–1615 (2 lines)

Precedes: `void kn7000_state::kn2400(machine_config &config)`

```c
// IC404, the SD sub-CPU program, is listed "KN2600 only": the KN2400 has the
// floppy drive and no SD slot, the KN2600 has both.
```

### kn7000.cpp:1628–1660 (33 lines)

```c
/***************************************************************************

    SX-KN7000

    IC16, IC17   C3FBNG000016   32 Mbit flash, program + table (see note above)
    IC18         C3CBND000046   64 Mbit mask ROM, rhythm  (later production)
    IC20         C3FBMD000050   32 Mbit flash, rhythm      (earlier production,
                                same site, and half the capacity; the manual
                                states IC20 is not supplied as a spare part)
    IC19         C3CBMD000098   64 Mbit picture ROM
    IC21         C3FBMD000050   16 Mbit custom flash (user data).  The service
                                manual captions this "32M FLASH", but that is
                                copied from IC20: the firmware's flash device
                                table (0x485CF9E0) accepts only 16 Mbit parts,
                                so a 32 Mbit device would fail its autoselect
                                check.  It also builds a 0x200000 sector map,
                                and the board decodes a 2 MB window at
                                0x96800000.  Three independent reasons for
                                16 Mbit.
    IC203        C3CBQD000002  128 Mbit mask ROM, wave, main TG bank Y (AWAY)
    IC204        C3CBQD000001  128 Mbit mask ROM, wave, main TG bank X (AWAX)
    IC207        C3CBQD000004  128 Mbit mask ROM, wave, sub TG bank Y (BWAY)
    IC208        C3CBQD000003  128 Mbit mask ROM, wave, sub TG bank X (BWAX)

    The wave devices sit on two independent buses per tone generator, so they
    are declared as one region per bank rather than concatenated. The block
    diagram shows IC207 and IC208 the other way round, but the schematic gives
    BWAY on IC207 and BWAX on IC208 at pin level, the chip-enable groups agree
    with it, and the part numbers pair as Y = 000002/000004 against
    X = 000001/000003.
    IC414        C3FBKD000162    4 Mbit flash, SD card sub-CPU program

***************************************************************************/
```

### kn7000.cpp:1689–1702 (14 lines)

Precedes: `ROM_REGION16_BE(0x200000, "custom_data", ROMREGION_ERASEFF)`

```c
	// The custom flash holds user data, and is populated from a floppy rather than
	// programmed at the factory: the firmware inflates the CTMINI payload from an
	// "Initial Data Disk" and writes it verbatim to offset 0x20000, which is the top
	// 30 of the 64 KiB sectors.  Nothing is written below that, so the boot sectors
	// are left erased here.
	//
	// The images below are not dumps of IC21 and are marked BAD_DUMP accordingly.
	// Each is the payload one published data set writes into the part, taken from
	// the manufacturer's own installer, so a part programmed from that floppy reads
	// back as declared -- but nobody has read one off a chip. They are a BIOS choice
	// because a real instrument holds exactly one at a time. Sectors 19..29 are
	// byte-identical in all nine, so a third of the region is an invariant template.
	// 16_BE: intelfsh preloads a 16-bit part with m_region->as_u16(), a host-native
	// read, so a byte-wide region would reach the device halfword-swapped.
```

### kn7000.cpp:1728–1742 (15 lines)

```c
/***************************************************************************

    SX-KN6000

    IC11, IC12   M29LV160B8TN   16 Mbit flash, program
    IC13         QSIGX3C16008   16 Mbit mask ROM, table data
    IC14         QSIGX3C16007   16 Mbit mask ROM, table data
    IC15         QSIGX3C32021   32 Mbit mask ROM, rhythm data
    IC18         A49BV161490T   16 Mbit flash, custom rhythm (user data)
    IC205        QSIGX3C64004   64 Mbit mask ROM, wave, bank Y (WAY)
    IC206        QSIGX3C64005   64 Mbit mask ROM, wave, bank X (WAX)
    IC207        QSIGX3C64006   64 Mbit mask ROM, wave, bank Y (WAY)
    IC208        QSIGX3C64007   64 Mbit mask ROM, wave, bank X (WAX)

***************************************************************************/
```

### kn7000.cpp:1764–1765 (2 lines)

Precedes: `ROM_REGION16_BE(0x200000, "custom_data", ROMREGION_ERASEFF)`

```c
	// Populated from the IDD6000 Initial Data Disk, which serves both the KN6000 and
	// the KN6500; see the note in the KN7000 set above.  Not a chip dump.
```

### kn7000.cpp:1771–1801 (31 lines)

```c
/***************************************************************************

    SX-KN6500

    IC11, IC12   M29LV160B8TN   16 Mbit flash, program
    IC13         C3FBMD000069   16 Mbit table data, supplied pre-programmed
    IC14         C3FBMD000068   16 Mbit table data, supplied pre-programmed
                                (the schematic legend reads "PROGRAMMED MASK
                                ROM", copied from the KN6000, but the pinout
                                drawn beside it - RESET, RY/BY, VPP, WE - is a
                                NOR flash, so no device type is asserted here)
    IC15         QSIGX3C32021   32 Mbit mask ROM, rhythm data
    IC18         M29LV160B8TN   16 Mbit flash, custom rhythm (user data).  The
                                schematic labels IC11, IC12 and IC18 with this
                                same part but three different descriptors, so
                                it is fitted at all three flash sites rather
                                than being a repeated parts-list row.  The
                                firmware will only program a device whose
                                autoselect response is in its table, and that
                                table holds MBM29LV160B and AT49BV16X4 - both
                                16 Mbit bottom boot, which is what fixes the
                                geometry here.  Which vendor's 29LV160B this
                                designation refers to is not established.
    IC205        QSIGX3C64004   64 Mbit mask ROM, wave, bank Y (WAY)
    IC206        QSIGX3C64005   64 Mbit mask ROM, wave, bank X (WAX)
    IC207        QSIGX3C64006   64 Mbit mask ROM, wave, bank Y (WAY)
    IC208        QSIGX3C64007   64 Mbit mask ROM, wave, bank X (WAX)
    IC209        QSIGX3C64020   64 Mbit mask ROM, wave, bank Y (WAY)
    IC210        QSIGX3C64019   64 Mbit mask ROM, wave, bank X (WAX)

***************************************************************************/
```

### kn7000.cpp:1825–1825 (1 lines)

Precedes: `ROM_REGION16_BE(0x200000, "custom_data", ROMREGION_ERASEFF)`

```c
	// Same IDD6000 payload as the KN6000; not a chip dump.
```

### kn7000.cpp:1831–1866 (36 lines)

```c
/***************************************************************************

    SX-KN2400 and SX-KN2600

    One firmware image serves both models, selecting between them at run time,
    and the two boards carry an identical set of memory devices: the schematic
    sheet holding the tone generator and both wave ROMs is the same drawing in
    both manuals, and the board assembly drawings list the same designators.
    The models differ in storage and I/O only - the SX-KN2400 has a floppy
    drive and controller, the SX-KN2600 an SD card interface. They therefore
    share every ROM listed below except the SD sub-processor's program flash,
    which is fitted only on the SX-KN2600.

    IC12, IC13   C3FBNG000007   32 Mbit flash, program (see note below)
    IC14         C3ZBNG000023   64 Mbit flash, rhythm and other data
    IC302        C3ZBP0000003   64 Mbit flash, wave bank Y (AWAY bus)
    IC303        C3ZBP0000004   64 Mbit flash, wave bank X (AWAX bus)
    IC404        C3ZBK0000020    4 Mbit flash, SD sub-CPU program (KN2600 only)

    Neither board carries a table or font ROM: the schematics, the board
    assembly drawings and the block diagrams agree that the devices listed
    above are the only memories present, and the LCD controller at IC104 has
    no external memory attached.

    The block diagrams describe IC302 and IC303 as 128 Mbit parts addressed by
    WAY0-WAY22, but the schematics show only 22 address inputs, and the tone
    generator's WAY22 and WAY23 pins terminate unconnected. The 64 Mbit figure
    from the schematics is used here.

    A note on IC12/IC13: the schematics show 21 address inputs driven from CPU
    address lines A2-A22, making these 32 Mbit devices that together span
    8 MiB. The dumps below cover 4 MiB of that pair. The remainder has not been
    read, so it is not described here; on the KN7000 the equivalent pair holds
    the table data in the half that these dumps do not cover.

***************************************************************************/
```

### kn7000.cpp:1869–1872 (4 lines)

Precedes: `ROM_REGION32_LE(0x400000, "table_data", ROMREGION_ERASEFF) \`

```c
	/* The firmware reads 0x48000000-0x483fffff. No separate table part appears in \
	   any SX-KN2400 source, and the header above explains why: as on the KN7000, \
	   that data lives in the half of the IC12/IC13 pair these dumps do not cover. \
	   The region stands in for it and is left erased. */ \
```

### kn7000.cpp:1895–1895 (1 lines)

Precedes: `ROM_REGION(0x80000, "sdcard_cpu", 0)`

```c
	// The SD card interface is fitted only on the SX-KN2600.
```

### kn7000.cpp:1903–1903 (1 lines)

Precedes: `SYST(2002, kn7000, 0,      0,      kn7000,  kn7000, kn7000_state, empty_init, "Technics", `

```c
//   YEAR  NAME    PARENT  COMPAT  MACHINE  INPUT   CLASS         INIT        COMPANY     FULLNAME      FLAGS
```

### kn7000.cpp:1906–1906 (1 lines)

Precedes: `SYST(1999, kn6000, 0,      0,      kn6000,  kn7000, kn7000_state, empty_init, "Technics", `

```c
// KN6000 / KN6500 reuse the KN7000 machine config: same MN10300, same ROM base.
```

### kn7000.cpp:1908–1908 (1 lines)

Precedes: `SYST(2001, kn6500, 0,      0,      kn6500,  kn7000, kn7000_state, empty_init, "Technics", `

```c
// The KN6500 is the KN6000 with one constant changed, tone generator included.
```

### kn7000.cpp:1911–1911 (1 lines)

Precedes: `SYST(2000, kn2400, 0,      0,      kn2400,  kn7000, kn7000_state, empty_init, "Technics", `

```c
// KN2400 / KN2600 -- MN10300/MILK siblings sharing one firmware image (kn2600 = clone of kn2400).
```


---

## `kn_tonegen.h` — 15 blocks, 94 lines

### kn_tonegen.h:1–63 (63 lines)

```c
// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics MN10300 keyboards -- tone-generator HLE, shared base

    Every MN10300-generation Technics keyboard drives its tone generator(s)
    the same way, and unlike most such claims this one is settled by the
    firmware itself rather than by the part numbers. The KN7000 carries two
    `C1BB00000709` LSIs (IC201 master + IC205 sub); the KN6000/KN6500 carry a
    single `D82398GD001` (IC213). Different part numbers -- but the same
    driver architecture, because the two firmwares are re-targets of one
    source tree.

    THE DECISIVE EVIDENCE:

      * The KN6000's tone-generator write primitive at 0x4849465B is
        BYTE-IDENTICAL to the KN7000's TG-A leg at 0x4C036F7C -- the same 20
        bytes, 81 f8c510 fc8700000598 fae0ffff fc8302000598. The KN7000's
        writer is that same routine with a chip-select branch (cmp 0x40,d0)
        wrapped around it, so the KN7000's two-chip path is literally a
        parameterised generalisation of the KN6000's one-chip path.
      * Both pack the same 32-bit command word (slot<<20)|(class<<16)|data
        and latch it as an ADDRESS halfword to +0 then a DATA halfword to +2,
        with the identical bitfield split (slot at address bit 4, 4-bit
        register index). Both expose the same dual asl-20 / asl-18 addressing
        modes.
      * Both use sixteen halfword registers per voice as four 4-register
        banks of [rate|level] byte-pair envelope segments, and share the
        literal constants 0xFF80/0xFF00 (boot reset), 0xA280/0xA200 and
        0x7F80/0x7F00 (damp pairs), 0xC000 (mute) and 0x87FF (gate on).
      * Both build the 18-bit pitch with the same instruction idiom
        (and 0x00018000 / or 0x4000), carrying pitch bit 16 in class bit 0.
      * Plane 0x20 (the per-channel send/output matrix) and plane 0x28 (the
        global register bank) sit at the SAME plane numbers on both chips.
      * Both use a 0xB4-stride library voice record and a 0x130-stride part
        tone block, over a 34-part model.

    WHAT DIFFERS is numbering and sizing, not behaviour: the per-voice
    register index assignment (the gate is r3 on the KN7000, r0 on the
    KN6000; the envelope banks sit at 0/4/8 vs 4/8/C), the per-voice
    parameter plane numbers below 0x20, the slot count (128 across two
    windows vs 64 in one), the shadow-image stride (0x84 vs 0xA0), and the
    KN7000-only 0x98040010/0x98050010 init strobe.

    So the split is drawn exactly where the evidence draws it:

      BASE (here) -- the MECHANISM, proven identical on both chips: the
        [rate|level] envelope decode and its rate->seconds law, the
        four-stage per-voice envelope state machine and all per-voice state,
        the gate-follow key coupling, the effect-send/return gains (planes
        0x20/0x28, same numbers on both), the optional synthetic wave pack,
        and the audio stream and rendering.

      DERIVED (kn7000_tonegen.*) -- the NUMBERING: which plane and which
        register index means what, i.e. the tg_write() decode itself, plus
        the chip/window count.

    kn6000_tonegen_device is that second decode. Its plane map is only partly
    pinned, so the KN6000/KN6500 render with the same placeholder waveforms the
    KN7000 does.

***************************************************************************/
```

### kn_tonegen.h:78–79 (2 lines)

Precedes: `int num_voices() const { return m_num_voices; }`

```c
	// Voices this model's tone generator(s) provide (KN7000 = 128 across two
	// chips, KN6000/KN6500 = 64 in one). Sizes every per-voice loop below.
```

### kn_tonegen.h:82–86 (5 lines)

Precedes: `virtual void tg_write(int tg, uint16_t addr, uint16_t data) = 0;`

```c
	// The model-specific half: turn one tone-generator register write into voice
	// events on the shared state below. Each derived device decodes its own chip's
	// register numbering. The arguments are exactly what the chip is given -- a
	// register number and a word -- so nothing here can depend on CPU state the
	// hardware cannot see.
```

### kn_tonegen.h:89–91 (3 lines)

Precedes: `enum : uint8_t { ST_ATTACK = 0, ST_DECAY1, ST_DECAY2, ST_RELEASE };`

```c
	// The firmware's 7-param amplitude EG:
	// ATTACK to PEAK (r0), DCY1 toward SUS1 (r1), DCY2 toward SUS2 (r2),
	// RELEASE to silence on the r3 gate-off / managed r0 burst / 0xC000 steal.
```

### kn_tonegen.h:94–96 (3 lines)

Precedes: `static double eg_tau(uint8_t rate);`

```c
	// PROVISIONAL chip rate-byte -> seconds law (higher byte = faster; sweep-calibrated
	// anchors: piano ATK 0xD2 -> 9 ms, piano DCY1 0x39 -> 1.8 s, damp burst 0x91 -> 85 ms,
	// organ rA 0xAE -> 31 ms, pad rA 0x04 -> ~11 s).
```

### kn_tonegen.h:100–100 (1 lines)

Precedes: `float gain_direct() const { return m_gain_direct; }`

```c
	// Output-bus routing (reverb toggle) -- polled by the driver into the DSP bridge.
```

### kn_tonegen.h:111–112 (2 lines)

Precedes: `void key_context(uint8_t key) { m_ctx_key = key; m_ctx_time = machine().time().as_double()`

```c
	// Keybed coupling for GATE-FOLLOW voices. The SUB TG chip itself hosts the key-bed
	// event FIFO, which the firmware reads at the TG's own +4 register.
```

### kn_tonegen.h:119–119 (1 lines)

Precedes: `virtual void device_start() override ATTR_COLD;`

```c
	// device_t / device_sound_interface overrides
```

### kn_tonegen.h:123–124 (2 lines)

Precedes: `virtual void sound_stream_update(sound_stream &stream) override;`

```c
	// Per-voice amplitude envelope driven by the firmware's 7-param EG (r0/r1/r2
	// rate|level pairs, resolved at note-on -- see tg_write).
```

### kn_tonegen.h:127–129 (3 lines)

Precedes: `sound_stream *m_stream = nullptr;`

```c
	// ---- per-voice state and the effect-send gains ----
	// Shared MECHANISM (see the header comment for the firmware evidence); the derived
	// class decodes its own register numbering into these.
```

### kn_tonegen.h:135–136 (2 lines)

Precedes: `struct wentry { uint8_t bank, zlo, zhi; const int16_t *pcm; uint32_t len, lstart, llen; do`

```c
	// SYNTHETIC wave-pack playback (kn7000_waves_synthetic.rom, optional). Entries map the
	// runtime sample select -- aux word bank (bits13:12) + zone (bits7:0) -- to donor PCM.
```

### kn_tonegen.h:139–140 (2 lines)

Precedes: `std::vector<int16_t> m_sine_pcm;   // owned buffer for the synthesized fallback sine`

```c
	// The wave ROMs are undumped, so a voice that maps to no donor zone plays a
	// fabricated sine rather than silence.
```

### kn_tonegen.h:145–147 (3 lines)

Precedes: `float    m_gain_direct = 0.0f;     // DAC crossfade: TG direct (reverb OFF side)`

```c
	// Effect-send gains. Written by tg_write() off the machine's io_w and read by
	// the driver's volume_scan timer -- both on the emulation thread, so these are
	// plain floats and save_item registers them directly.
```

### kn_tonegen.h:168–168 (1 lines)

Precedes: `uint16_t m_eg012[128][3] = { };   // raw r0/r1/r2 per voice (the 7-param amplitude EG)`

```c
	// Per-voice AMPLITUDE ENVELOPE, driven by the firmware's own 7-param EG:
```

### kn_tonegen.h:178–178 (1 lines)

Precedes: `uint32_t m_tgwrites = 0;         // count of firmware pitch writes seen (0 = engine dorman`

```c
									  // overridden by the managed key-up burst's r0 rate)
```


---

## `kn_tonegen.cpp` — 6 blocks, 40 lines

### kn_tonegen.cpp:1–15 (15 lines)

```c
// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics MN10300 keyboards -- tone-generator HLE, shared base

    The model-independent half of the tone-generator emulation: the per-voice
    envelope state machine and its rate->seconds law, the voice state, the
    gate-follow key coupling, the synthetic wave pack, and the audio stream.
    Concrete tone generators (kn7000_tonegen.cpp) supply the register decode
    that drives it.

    See kn_tonegen.h for the firmware evidence behind this split.

***************************************************************************/
```

### kn_tonegen.cpp:30–32 (3 lines)

Precedes: `double kn_tonegen_base_device::eg_tau(uint8_t rate)`

```c
	// PROVISIONAL chip rate-byte -> seconds law (higher byte = faster; sweep-calibrated
	// anchors: piano ATK 0xD2 -> 9 ms, piano DCY1 0x39 -> 1.8 s, damp burst 0x91 -> 85 ms,
	// organ rA 0xAE -> 31 ms, pad rA 0x04 -> ~11 s).
```

### kn_tonegen.cpp:65–68 (4 lines)

Precedes: `if (m_wdefault < 0)`

```c
	// The wave ROMs have no dump, so every voice plays a synthesized single-cycle
	// sine through the ordinary sample-playback path rather than a sin() oscillator:
	// the mechanism is the real one, only the data is fabricated. 441 samples per
	// cycle gives a 44100/441 = 100 Hz root.
```

### kn_tonegen.cpp:154–160 (7 lines)

Precedes: `const wentry &we = m_wentries[m_wsel[v]];`

```c
			// SINGLE, FAITHFUL DATAPATH: every voice reads PCM from the wave pack, exactly
			// as the real chip reads its wave ROM -- donor zones where a KN5000 sample was
			// mapped, or the fabricated default sine (m_wdefault) everywhere else. There is
			// no sin() oscillator; the hardware has none. Linear interpolation, tail loop
			// (seam crossfaded at build time for donors; single cycle for the sine), stepped
			// by musical pitch / root. Faithful mechanism -- the DATA is placeholder, the
			// PLAYBACK PATH is real.
```

### kn_tonegen.cpp:163–167 (5 lines)

Precedes: `if (!std::isfinite(pos) || pos < 0.0 || pos >= double(we.len))`

```c
			// SANITISE the read position before indexing the PCM. A model whose
			// note->pitch resolve is not yet reversed (e.g. the KN6000) can hand us a
			// non-finite or out-of-range frequency; an unguarded uint32_t(pos) on inf/NaN
			// or a huge pos would index the sample array out of bounds and crash the
			// emulator. Keep pos finite and within the sample before use.
```

### kn_tonegen.cpp:175–180 (6 lines)

Precedes: `double step = m_freq[v] / we.root_hz;`

```c
			// Advance by musical pitch / root, then wrap into the tail loop. GUARD both:
			// a model whose note->pitch resolve is not yet reversed (e.g. the KN6000) can
			// hand us a non-finite, negative, or absurdly large frequency. The step is
			// clamped finite/non-negative, and the loop wrap is done with an O(1) modulo
			// (NOT a subtract-loop): a huge finite step through a subtract-loop would
			// iterate billions of times and livelock the single-threaded emulator.
```


---

## `kn7000_tonegen.h` — 4 blocks, 16 lines

### kn7000_tonegen.h:1–11 (11 lines)

```c
// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    KN7000 tone generator

    Two LSIs, IC201 (master) and IC205 (sub), C1BB00000709, 64 voice slots
    each. Only the register numbering is here; the voice model, envelopes and
    audio stream are shared with the KN6000 in kn_tonegen.h.

***************************************************************************/
```

### kn7000_tonegen.h:22–23 (2 lines)

Precedes: `class kn7000_tonegen_device : public kn_tonegen_base_device`

```c
// kn7000_tonegen_device -- FIRMWARE-DRIVEN audio output (Phase C, Stage 2).
//
```

### kn7000_tonegen.h:27–27 (1 lines)

Precedes: `kn7000_tonegen_device(const machine_config &mconfig, const char *tag, device_t *owner, uin`

```c
	// 128 voices: 64 per chip, slot bit 6 selecting sub (IC205) or master (IC201).
```

### kn7000_tonegen.h:33–34 (2 lines)

Precedes: `virtual void tg_write(int tg, uint16_t addr, uint16_t data) override;`

```c
	// Stage 2 -- FIRMWARE-DRIVEN synthesis. Every tone-generator register write (both
	// TGs) is routed here from io_w, once the TG-enable gate is open.
```


---

## `kn7000_tonegen.cpp` — 19 blocks, 54 lines

### kn7000_tonegen.cpp:1–11 (11 lines)

```c
// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    KN7000 tone generator -- the register decode

    See kn7000_tonegen.h. This file holds the KN7000's register NUMBERING:
    the tg_write() decode that turns firmware register writes into voice
    events on the shared base (kn_tonegen.cpp).

***************************************************************************/
```

### kn7000_tonegen.cpp:29–30 (2 lines)

Precedes: `bool eg_programmed = false;`

```c
		// A real note-on always programs the 7-halfword amplitude EG first, so require
		// a programmed EG before keying a voice on.
```

### kn7000_tonegen.cpp:35–42 (8 lines)

Precedes: `const double note = 96.0 + (double(p18) - double(0x1C838)) / 1024.0;`

```c
			// Note-on. The pitch register carries an ABSOLUTE LOG PITCH at 0x400 units
			// per semitone, anchored where pitch18 0x1C838 = MIDI 96, the keybed top-C
			// reference. The firmware folds it by whole octaves into the sample zone's
			// key range when the zone cannot cover the played key (the KN5000's
			// Pitch_Fold_Octaves_Into_Range does exactly this, in the same 8.8 domain),
			// so with the wave ROMs undumped the zone limits are unknown and a voice
			// whose zone would have folded sounds an octave out. The pitch CLASS is
			// exact either way.
```

### kn7000_tonegen.cpp:49–55 (7 lines)

Precedes: `m_mode[v] = (m_aux[v] & 0x8000) ? 1 : 0;`

```c
			// Voice life-cycle class:
			//  - GATE_FOLLOW: aux bit15 (brass/sax/organ) -- no firmware key-up write; the
			//    TG, which hosts the key-bed FIFO, gates them off itself on key release.
			// The synthesis/release class lives in a firmware record the chip never
			// sees, so only the aux word's gate-follow marker is available here.
			// Everything else is treated as firmware-managed, which is the safe
			// default: a managed voice waits for the firmware's key-up write.
```

### kn7000_tonegen.cpp:59–61 (3 lines)

Precedes: `{`

```c
			// Sample select: (bank,zone) from the aux word -> donor wave, else the
			// fabricated default sine (m_wdefault). Never -1 -> the voice always plays
			// PCM through the single sample-playback datapath (no sin() oscillator).
```

### kn7000_tonegen.cpp:71–71 (1 lines)

Precedes: `constexpr double FS = 44100.0;`

```c
			// Resolve this voice's amplitude envelope from the firmware's 7-param EG.
```

### kn7000_tonegen.cpp:76–77 (2 lines)

Precedes: `if (m_mode[v] == 2) { sus1 = 0.0; sus2 = 0.0; }`

```c
			// ONESHOT plucks (no key-up ramp): the sample dies out naturally -- force
			// the decay chain to run to silence (the old held-decay behavior).
```

### kn7000_tonegen.cpp:85–85 (1 lines)

Precedes: `m_rlsc[v] = exp(-1.0 / (std::clamp(eg_tau(m_envreg[v][6] >> 8), 0.02, 12.0) * FS));`

```c
			// Default release rate: the chip-side damp bank's rA high byte.
```

### kn7000_tonegen.cpp:92–93 (2 lines)

Precedes: `const double note = m_note[v] + (double(p18) - double(m_p18ref[v])) / 1024.0;`

```c
			// held voice: RELATIVE pitch update (bend/vibrato/portamento) around
			// the note-on reference, 0x400 pitch18 units per semitone.
```

### kn7000_tonegen.cpp:102–103 (2 lines)

Precedes: `if (data != 0 && (data >> 8) < 0xFF)`

```c
		// KEY-RELEASE, path 2 (firmware-managed sounds): after the r3=0x8000 gate-off
		// the firmware rewrites regs 0,1,4,5,8,9 of the note's odd companion block.
```

### kn7000_tonegen.cpp:128–128 (1 lines)

Precedes: `if ((data >> 8) == 0x80)`

```c
		// Universal key-release trigger, written for every voice class on key-up.
```

### kn7000_tonegen.cpp:142–142 (1 lines)

Precedes: `m_stream->update();`

```c
		// The firmware writes this once at note-on.
```

### kn7000_tonegen.cpp:148–148 (1 lines)

Precedes: `const int ch = (addr >> 4) & 0x3F, reg = addr & 0x0F;`

```c
		// Decoded from the library's setter family and its live argument traffic:
```

### kn7000_tonegen.cpp:162–162 (1 lines)

Precedes: `if (tg == 1 && ch == 0x09 && reg == 0x08)`

```c
														  // 0x0B00 off -> 0; routes to CHORUS unit 9)
```

### kn7000_tonegen.cpp:165–166 (2 lines)

Precedes: `if (tg == 1 && ch == 0x29 && reg == 0x08)`

```c
														  // routes to the per-part insert pool u2..u6,
														  // RIGHT1 being unit 2)
```

### kn7000_tonegen.cpp:169–171 (3 lines)

Precedes: `const uint8_t lvl = data & 0x7F;`

```c
			// MULTI send (0x8298 = row 2 of insert part 9, routing to MULTI unit 1). The
			// high byte doubles as the firmware's ON marker, 0x06 meaning the multi-return
			// part is the destination.
```

### kn7000_tonegen.cpp:176–177 (2 lines)

Precedes: `if (tg == 1 && ch == 0x09 && reg == 0x0A)`

```c
		// PER-EFFECT RETURN levels (reg 0xA low byte = DSP-return level for THIS effect's own
		// bus), from the per-effect toggle map:
```

### kn7000_tonegen.cpp:185–185 (1 lines)

Precedes: `m_aux[v] = data;`

```c
		// bit15 marks the gate-follow voice classes (see key_context/key_break above).
```

### kn7000_tonegen.cpp:190–192 (3 lines)

Precedes: `m_envreg[v][cls - 0x0004] = data;`

```c
		// The firmware writes the sound's per-voice amplitude EG (7 halfwords, ATK PEAK
		// DCY1 SUS1 DCY2 SUS2 RLS) just before the note-on pitch write. Cache them; the
		// note-on resolves them into a decay/sustain/release. (See notes/tg-envelope-*.)
```


---

## `kn6000_tonegen.h` — 2 blocks, 14 lines

### kn6000_tonegen.h:1–12 (12 lines)

```c
// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    KN6000/KN6500 tone generator

    One LSI, IC213 D82398GD001, 64 voice slots behind a register window at
    0x98050000/2. Driven entirely by the firmware's voice engine. Only the
    register numbering is here; the voice model, envelopes and audio stream
    are shared with the KN7000 in kn_tonegen.h.

***************************************************************************/
```

### kn6000_tonegen.h:26–27 (2 lines)

Precedes: `kn6000_tonegen_device(const machine_config &mconfig, const char *tag, device_t *owner, uin`

```c
	// 64 voice slots in ONE chip (IC213) behind a single window -- no chip select,
	// so the driver always calls tg_write() with tg = 1 (the 0x98050000 window).
```


---

## `kn6000_tonegen.cpp` — 13 blocks, 37 lines

### kn6000_tonegen.cpp:1–12 (12 lines)

```c
// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    KN6000/KN6500 tone generator -- the register decode

    See kn6000_tonegen.h for how this numbering was recovered from the
    firmware's own note-on register blit (0x484948CB) and its damp/mute
    literals. This file holds only the decode; the voice model it drives is
    shared with the KN7000 in kn_tonegen.cpp.

***************************************************************************/
```

### kn6000_tonegen.cpp:30–30 (1 lines)

Precedes: `const uint32_t p18 = (uint32_t(cls & 0x0F) << 16) | data;`

```c
		// The 18-bit pitch: the class word's low nibble carries bits 16-17.
```

### kn6000_tonegen.cpp:33–34 (2 lines)

Precedes: `bool eg_programmed = false;`

```c
		// This register is written near the end of the note-on blit, after the envelope,
		// so a programmed EG is the signal that the voice is really starting.
```

### kn6000_tonegen.cpp:41–43 (3 lines)

Precedes: `const double note = 96.0 + (double(p18) - double(0x1C838)) / 1024.0;`

```c
			// Note-on. The pitch register carries an absolute log pitch, 0x400 units per
			// semitone; see kn7000_tonegen.cpp for the octave-fold caveat that the
			// undumped wave ROMs leave open.
```

### kn6000_tonegen.cpp:51–52 (2 lines)

Precedes: `m_mode[v]   = 0;`

```c
			// Voice life cycle. The KN6000's aux/mode word (the analogue of the
			// KN7000's class 0x1C02 gate-follow marker) is not yet identified.
```

### kn6000_tonegen.cpp:59–60 (2 lines)

Precedes: `constexpr double FS = 44100.0;`

```c
			// Resolve the amplitude envelope from the firmware's own [rate|level] byte
			// pairs at cls 0x0004/0x0005/0x0006 (the KN7000's r0/r1/r2 shifted by +4).
```

### kn6000_tonegen.cpp:71–73 (3 lines)

Precedes: `m_rlsc[v]  = exp(-1.0 / (std::clamp(eg_tau(m_envreg[v][6] >> 8), 0.02, 12.0) * FS));`

```c
			// Default release rate: the third envelope bank's last register (cls 0x000E),
			// the positional analogue of the KN7000's rA whose per-sound value tracks the
			// audible release character. Overridden by the key-up burst's own rate below.
```

### kn6000_tonegen.cpp:80–81 (2 lines)

Precedes: `const double note = m_note[v] + (double(p18) - double(m_p18ref[v])) / 1024.0;`

```c
			// Held voice: a pitch rewrite is a RELATIVE bend (vibrato / portamento /
			// pitch bend) around the note-on reference, 0x400 pitch18 units per semitone.
```

### kn6000_tonegen.cpp:89–91 (3 lines)

Precedes: `if ((data >> 8) == 0x80)`

```c
		// 0x87FF at note-on (written FIRST in the blit, before the envelope is loaded,
		// so it is not the note-on trigger here), 0x8000 at key-up. The KN7000 carries
		// this on r3; it is the one register that genuinely moved between the chips.
```

### kn6000_tonegen.cpp:106–107 (2 lines)

Precedes: `if (data != 0 && (data >> 8) < 0xFF)`

```c
		// KEY-RELEASE path 2 (firmware-managed sounds): after the gate-off the firmware
		// rewrites the first two registers of each envelope bank ({4,5,8,9,C,D}).
```

### kn6000_tonegen.cpp:132–133 (2 lines)

Precedes: `m_envreg[v][cls - 0x0008] = data;`

```c
		// The positional analogue of the KN7000's r4..rA: further three-register banks
		// holding the pitch and filter envelopes.
```

### kn6000_tonegen.cpp:138–138 (1 lines)

Precedes: `m_stream->update();`

```c
		// Written once per note-on. Full velocity gives the nominal maximum.
```

### kn6000_tonegen.cpp:142–143 (2 lines)

Precedes: `}`

```c
	// The per-channel effect-send matrix, the KN7000's group 0x20, is deliberately not
	// decoded here: the KN6000's use of that range has not been mapped.
```


---

## `kn_cpanel.h` — 16 blocks, 45 lines

### kn_cpanel.h:1–27 (27 lines)

```c
// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics MN10300 keyboards -- control-panel HLE, shared base

    Every MN10300-generation Technics keyboard (KN7000, KN6000/KN6500,
    KN2400/KN2600, ...) drives its front panel the same way: one 8-bit
    sub-CPU per panel PCB scans that board's button matrix and drives its
    LEDs, and all of them talk to the main CPU over the SAME synchronous
    serial link (channel 0 of the SIO ASIC), using the SAME wire protocol.

    That protocol -- the 7-byte TX frame layout, the handshake commands, the
    ATN/RX interrupt dance, the [ADDR][DATA] switch and latched-control
    frames, and the analog controls (DATA dial, TEMPO/PROGRAM wheel, APC/SEQ
    fader) -- lives HERE, because it is genuinely model-independent. This is
    empirically confirmed: the KN6000 driver, running the KN7000's panel
    device unmodified, accepts button presses and its TEMPO/PROGRAM wheel
    works perfectly. Only the *contents* of the matrix differ.

    What each model supplies (pure virtuals below):
      - its scan-matrix ioports (how many, and which normalized segment each
        drives),
      - its segment -> wire-ADDR reverse-normalization table,
      - its LED-register decode.

***************************************************************************/
```

### kn_cpanel.h:37–38 (2 lines)

Precedes: `template <typename T> void set_dial_port(T &&tag) { m_dial.set_tag(std::forward<T>(tag)); `

```c
	// The analog controls the panel sub-CPUs scan live in the driver's ioports;
	// the device reads them through these tags.
```

### kn_cpanel.h:43–43 (1 lines)

Precedes: `auto atn() { return m_atn_cb.bind(); }   // panel ATN pulse -> main asserts INTC group 0x1`

```c
	// Callbacks to the main CPU (its interrupt controller / SIO channel 0):
```

### kn_cpanel.h:47–47 (1 lines)

Precedes: `void tx_byte(uint8_t data);   // main CPU wrote one panel TX byte (SIO ch0 +8)`

```c
	// From the main CPU (SIO / INTC bridge):
```

### kn_cpanel.h:52–54 (3 lines)

Precedes: `virtual bool chorus_led() const { return false; }`

```c
	// Firmware-authoritative global-effect ON state, read from the LED frames the firmware
	// itself sends. Only the KN7000 has the effects DSP wired up, so the base reports "off"
	// and the KN7000 device overrides these (see kn7000_cpanel.cpp).
```

### kn_cpanel.h:61–61 (1 lines)

Precedes: `virtual void device_start() override ATTR_COLD;`

```c
	// device_t overrides
```

### kn_cpanel.h:65–65 (1 lines)

Precedes: `virtual int     num_scan_ports() const = 0;`

```c
	// ---- per-model geometry, supplied by the derived panel device ----
```

### kn_cpanel.h:69–69 (1 lines)

Precedes: `virtual int     num_segs() const = 0;`

```c
	// Reverse-normalization: normSeg -> wire ADDR (0xFF = this segment has no wire path).
```

### kn_cpanel.h:72–72 (1 lines)

Precedes: `virtual void    panel_led_frame(uint8_t addr, uint8_t data) = 0;`

```c
	// Decode one [ADDR][DATA] LED-register frame onto this model's LED outputs.
```

### kn_cpanel.h:80–80 (1 lines)

Precedes: `void panel_queue(const uint8_t *bytes, int n);`

```c
	// Append panel->main reply bytes and kick the ATN delivery dance if idle.
```

### kn_cpanel.h:84–84 (1 lines)

Precedes: `int     m_panel_pos;                   // position within the 7-byte TX frame`

```c
	// Serial frame parse (7-byte TX frames from the main CPU).
```

### kn_cpanel.h:88–88 (1 lines)

Precedes: `uint8_t m_panel_resp[64];              // pending panel->main bytes (replies + button even`

```c
	// Response queue (panel -> main).
```

### kn_cpanel.h:92–92 (1 lines)

Precedes: `emu_timer *m_panel_evt;                // one-shot; param: 1=ATN edge, 2=deliver RX byte`

```c
	// Timers.
```

### kn_cpanel.h:96–96 (1 lines)

Precedes: `uint8_t m_btn_prev[MAX_SEGS];          // last scanned state, one per normSeg`

```c
	// Input scan state.
```

### kn_cpanel.h:106–106 (1 lines)

Precedes: `devcb_write_line m_atn_cb;`

```c
	// Callbacks to the main CPU.
```

### kn_cpanel.h:110–110 (1 lines)

Precedes: `optional_ioport m_dial;                // DATA dial (rotary encoder, wire 0x10)`

```c
	// Shared analog panel controls (set by the main driver via the set_*_port() helpers above).
```


---

## `kn_cpanel.cpp` — 18 blocks, 72 lines

### kn_cpanel.cpp:1–14 (14 lines)

```c
// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics MN10300 keyboards -- control-panel HLE, shared base

    The model-independent half of the front-panel emulation: the CP serial
    protocol, the ATN/RX handshake, the analog controllers, and the periodic
    matrix scan. Concrete panels (kn7000_cpanel.cpp, kn6000_cpanel.cpp)
    supply their own matrix geometry and LED decode.

    See kn_cpanel.h for the rationale of the split.

***************************************************************************/
```

### kn_cpanel.cpp:69–70 (2 lines)

Precedes: `m_panel_resp_len = m_panel_resp_pos = 0;`

```c
	// Drop any in-flight reply and its deferred delivery -- no stale byte can leak
	// after a soft reset (identical at cold boot, where both are already zero).
```

### kn_cpanel.cpp:78–79 (2 lines)

Precedes: `m_panel_timer->adjust(attotime::from_hz(250), 0, attotime::from_hz(250));`

```c
	// Periodic button/analog scan at 250 Hz (real panel sub-CPUs continuously
	// monitor their matrices and push change notifications via the ATN line).
```

### kn_cpanel.cpp:83–86 (4 lines)

Precedes: `void kn_cpanel_base_device::tx_byte(uint8_t data)`

```c
// One panel TX byte from the main CPU (SIO channel 0). The main CPU transmits
// 7-byte FRAMES with interleaved line syncs:
//   pos 0 sync, 1 sync, 2 PAYLOAD1, 3 sync, 4 PAYLOAD2, 5 sync, 6 sync
// Parse by position.
```

### kn_cpanel.cpp:97–100 (4 lines)

Precedes: `switch (m_panel_p1)`

```c
		// Frame complete. Handshake commands (payload1 = 0x1F/0x1D/0x1E init,
		// 0x20/0xE0 ping CPL/CPR, 0x29/0xDD -- the boot's observed sequence) are
		// answered with a TYPE-3 sync packet and an ATN pulse. All other frames
		// carry LED-register updates [addr][data].
```

### kn_cpanel.cpp:110–112 (3 lines)

Precedes: `panel_led_frame(m_panel_p1, m_panel_p2);`

```c
			// NB: addr byte 0x00 is NOT idle/padding -- it is a register-0 LED update
			// [0x00][bits]. The firmware frame builder skips only data==0xFF, so 0x00
			// addresses must be decoded too.
```

### kn_cpanel.cpp:119–120 (2 lines)

Precedes: `void kn_cpanel_base_device::panel_queue(const uint8_t *bytes, int n)`

```c
// The panel raises ATN, the main CPU's group-0x1A ISR switches the link to RX and
// clocks the bytes in one group-0x10 interrupt at a time.
```

### kn_cpanel.cpp:134–138 (5 lines)

Precedes: `TIMER_CALLBACK_MEMBER(kn_cpanel_base_device::panel_event)`

```c
// Deferred panel events (one-shot; scheduled from ISR-context register writes so
// the interrupt lands after the firmware's current handler returns):
//  param 1: ATN edge on the panel's external-interrupt pin -> main asserts group 0x1A.
//  param 2: the panel places its next reply byte on SIO0 -> main pushes it onto the
//           RX FIFO and asserts group 0x10 (the state-8 handler reads it from +9).
```

### kn_cpanel.cpp:151–152 (2 lines)

Precedes: `void kn_cpanel_base_device::rx_enable()`

```c
// Main CPU enabled SIO ch0 RX (config bit14, set by the group-0x1A ISR's pass 2):
// the panel now sends its queued reply, one byte per group-0x10 interrupt.
```

### kn_cpanel.cpp:159–160 (2 lines)

Precedes: `void kn_cpanel_base_device::atn_rearm()`

```c
// The group-0x1A ISR's pass 1 re-armed EXTMD for the opposite edge (11b -> 10b)
// and expects the panel's second ATN edge to arrive after it returns.
```

### kn_cpanel.cpp:166–168 (3 lines)

Precedes: `TIMER_CALLBACK_MEMBER(kn_cpanel_base_device::panel_scan)`

```c
// Periodic scan: read the analog controllers and each declared button segment,
// and for any that changed since last scan queue the 2-byte [ADDR][DATA] frame
// the real sub-CPUs emit. Delivery rides the ATN/SIO handshake in panel_queue.
```

### kn_cpanel.cpp:171–175 (5 lines)

Precedes: `{`

```c
	// Front-panel APC/SEQ VOLUME slider -> the firmware's own accompaniment/sequencer volume,
	// delivered the way the real hardware does it: the panel sub-CPU digitises the pot and sends a
	// CP-protocol TYPE 2 "latched control" frame [ADDR, DATA]. ADDR 0xD2 (bank11/type2/sub2) = APC/SEQ
	// VOLUME. The handler does DATA -> NOT -> latch -> >>1 -> a monotonic 0..127 remap, so a LOUDER
	// setting needs a LOWER DATA byte. Map the 0..100 adjuster accordingly and emit only on change.
```

### kn_cpanel.cpp:180–183 (4 lines)

Precedes: `m_vol_apcseq_prev = data;`

```c
			// First scan: just record the initial pot position. Do NOT emit a frame during early boot --
			// the firmware isn't servicing the panel handshake yet, so an undelivered frame would sit in
			// the response queue and block all later ATN kicks (buttons included). The slider takes over
			// on the first real move (matching the hardware's soft-takeover behaviour).
```

### kn_cpanel.cpp:195–199 (5 lines)

Precedes: `{`

```c
	// Front-panel DATA dial (the big value wheel with the central SET button) -> CP-protocol TYPE 2
	// "latched control" frame [0x10, POSITION]. The wheel is a rotary ENCODER: the panel sub-CPU keeps
	// an 8-bit position counter and ships it on the CP link, and the main-CPU handler DIFFS successive
	// positions to derive turn direction/amount. MAME's IPT_DIAL is precisely this kind of relative
	// accumulator (0..255, wraps), so we forward its value verbatim.
```

### kn_cpanel.cpp:215–219 (5 lines)

Precedes: `{`

```c
	// Front-panel TEMPO/PROGRAM knob -> CP-protocol RELATIVE encoder [0x17, STEP]. The main-CPU handler
	// latches the wire byte, but the tempo routine ADDS it as a SIGNED 8-bit step every frame --
	// tempo += (int8_t)wire -- it does NOT diff an absolute position. So forward a clean SIGNED step,
	// slewing m_tempoknob_prev toward the adjuster one detent per scan. (Sending a growing ABSOLUTE
	// position made the firmware race to the 300-BPM rail regardless of direction.)
```

### kn_cpanel.cpp:221–223 (3 lines)

Precedes: `if (m_tempoknob_field == nullptr && m_tempoknob.found())`

```c
		// Read the RAW adjuster setting (field live value), NOT m_tempoknob.read_safe() -- the analog PORT
		// read runs the value through interpolation/sensitivity, whose per-scan wobble injects spurious
		// mixed-sign steps that cancel the relative-encoder motion. Locate the field once, lazily.
```

### kn_cpanel.cpp:235–236 (2 lines)

Precedes: `int delta = int(adj) - int(m_tempoknob_prev);`

```c
			// The layout knob is an INFINITE rotary encoder: a full-circle drag wraps the 0..100 adjuster
			// past its ends. Take the direction the SHORT way round (a jump of >50 = a wrap).
```

### kn_cpanel.cpp:247–251 (5 lines)

Precedes: `uint8_t seg_state[MAX_SEGS] = { 0 };`

```c
	// Inputs are declared one ioport per NORMALIZED SEGMENT, the identity the firmware's
	// button dispatcher uses. For a changed segment we emit its 2-byte [ADDR][DATA] switch
	// frame, computing the wire ADDR by REVERSE-normalizing via the model's table.
	// DATA = segment bitmask (bit=1 pressed); the main CPU XORs vs its shadow for edges.
	// Delivery rides the ATN dance via panel_queue (a bare fifo push never IRQs).
```


---

## `kn7000_cpanel.h` — 7 blocks, 25 lines

### kn7000_cpanel.h:1–18 (18 lines)

```c
// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    KN7000 control panel HLE

    High-level emulation of the KN7000 front-panel sub-CPUs (one per panel
    PCB) that scan the button matrices and analog controls and drive the panel
    LEDs, talking to the main MN10300 over a synchronous serial link (channel
    0 of the SIO ASIC).

    Only the KN7000-SPECIFIC half lives here: the button scan matrix (40
    normalized segments, 230 descriptor button-bits) and the three-board LED
    register decode. The CP wire protocol, the ATN/RX handshake and the analog
    controllers are shared with the other MN10300 models and live in the base
    class (kn_cpanel.h / kn_cpanel.cpp).

***************************************************************************/
```

### kn7000_cpanel.h:32–32 (1 lines)

Precedes: `virtual bool chorus_led() const override { return m_chorus_led; }`

```c
	// Global-effect ON state, read from the LED frames the firmware sends the panel.
```

### kn7000_cpanel.h:37–37 (1 lines)

Precedes: `virtual void device_start() override ATTR_COLD;`

```c
	// device_t overrides
```

### kn7000_cpanel.h:41–41 (1 lines)

Precedes: `virtual int     num_scan_ports() const override { return 22; }`

```c
	// per-model geometry (see kn_cpanel.h)
```

### kn7000_cpanel.h:50–50 (1 lines)

Precedes: `bool m_chorus_led = false;          // D1082 CHORUS (cpr_led29)`

```c
	// Global-effect LED shadow (set in panel_led_frame; see chorus_led()/multi_led()).
```

### kn7000_cpanel.h:54–55 (2 lines)

Precedes: `optional_ioport_array<22> m_phys;      // CP{board}_SEG{col}`

```c
	// Button scan-matrix ports -- OWNED by this device (declared in device_input_ports(),
	// bound by tag in the constructor). One per physical board SEG column.
```

### kn7000_cpanel.h:58–58 (1 lines)

Precedes: `output_finder<512> m_cpl_leds;`

```c
	// LED outputs (the three panel PCBs: left / center / right).
```


---

## `kn7000_cpanel.cpp` — 9 blocks, 51 lines

### kn7000_cpanel.cpp:1–15 (15 lines)

```c
// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    KN7000 control panel HLE

    Like the KN5000, the KN7000 front panel is driven by dedicated panel
    sub-CPUs -- one per panel PCB -- that scan the button matrices and drive
    the LEDs, and talk to the main MN10300 over a synchronous serial link.
    The main CPU delivers whole bytes on SIO channel 0; this device parses the
    7-byte TX frames, decodes the LED-register writes, and replies with
    handshake / button-event / analog-controller packets that ride back to the
    firmware via the panel ATN pulse and the SIO0 receive interrupt.

***************************************************************************/
```

### kn7000_cpanel.cpp:27–30 (4 lines)

Precedes: `static const uint8_t PORT_SEG[22] = {`

```c
// Physical scan matrix == firmware normalized-segment space (see kn7000.cpp INPUT_PORTS header).
// PORT_SEG[port] is the normSeg (= sub-CPU scan column) that input port n drives; the SW bit is
// forwarded unchanged. Each scan column maps to exactly one wire ADDR (no per-bit repacking), so
// this is a pure identity -- no per-button translation table is needed.
```

### kn7000_cpanel.cpp:37–46 (10 lines)

Precedes: `static INPUT_PORTS_START(kn7000_cpanel)`

```c
// The front-panel BUTTON matrix belongs to the panel sub-CPUs this device emulates, so the
// ports live HERE (device_input_ports()) rather than in the driver's INPUT_PORTS -- the layout
// references them as "cpanel:CP{board}_SEG{col}". Each CP{board}_SEG{col} port is one scan
// segment the panel sub-CPU drives, and each bit is one SW sense line it reads. This is exactly
// the firmware's normalized-segment (normSeg) space: port n -> normSeg PORT_SEG[n] with the bit
// unchanged, then reverse-normalized to the wire ADDR (one ADDR per column: CPL/CPC bank11 subs
// 0xC0-0xCB -> segs 0x00-0x0B; CPR bank00 subs 0x00-0x09 -> segs 0x0C-0x15). Because each scan
// column maps to a single wire ADDR (no per-bit repacking), naming the ports by scan column is a
// pure identity. Button-to-column assignments come from each button's firmware event code + arg.
// LEDs are driven independently on the same normSeg keys.
```

### kn7000_cpanel.cpp:256–257 (2 lines)

Precedes: `m_phys(*this, { "CPL_SEG0", "CPL_SEG1", "CPL_SEG2", "CPL_SEG3", "CPL_SEG4", "CPL_SEG6", "C`

```c
	// Bind to this device's OWN button ports (declared in device_input_ports() above), in
	// PORT_SEG[] index order (CPL_SEG0,1,2,3,4,6,7 / CPC_SEG5,8,9,10,11 / CPR_SEG0..9).
```

### kn7000_cpanel.cpp:274–275 (2 lines)

Precedes: `uint8_t kn7000_cpanel_device::port_seg(int port) const`

```c
// Physical scan matrix == firmware normalized-segment space: port n -> normSeg PORT_SEG[n],
// SW bit forwarded unchanged (a pure identity -- each scan column is exactly one wire ADDR).
```

### kn7000_cpanel.cpp:281–284 (4 lines)

Precedes: `uint8_t kn7000_cpanel_device::seg_wire_addr(int seg) const`

```c
// Reverse-normalization (the inverse of the firmware's normalization table):
//   normSeg 0x00-0x0B -> ADDR 0xC0-0xCB (grp3), 0x0C-0x15 -> 0x00-0x09 (grp0),
//   0x16-0x19 -> 0xD0-0xD3, 0x20 -> 0x17. normSeg 0x1A (wire 0x10 = DATA dial) is a
//   VALUATOR, emitted by the base class's dial block, NOT here; 0x1B-0x1F have NO wire path.
```

### kn7000_cpanel.cpp:297–304 (8 lines)

Precedes: `const int reg = addr & 0x3f;`

```c
	// One decoded LED-command frame. ADDR = board (bits 7:6; 0x00 = CPR / right panel, 0xC0/0xE0 =
	// CPL / left panel) | LED register (bits 5:0). Each DATA bit is one LED; its output index is
	// reg*8 + bit within that board's bank (cpr_led#/cpl_led#), and the comment names the panel
	// function/mode that LED indicates (KN5000 style). This map is kept in sync with -- and generated
	// from -- the layout's LED bindings (tools/gen_lay.py LED_PURPOSE), which carry the empirically
	// verified assignments (e.g. FAVORITES = cpr_led2 via PANEL_LED). Bits marked
	// (unmapped) are real firmware LEDs whose panel function is not yet identified; the default arm
	// keeps any register not enumerated here working too.
```

### kn7000_cpanel.cpp:347–348 (2 lines)

Precedes: `m_multi_led  = BIT(data, 4);`

```c
			// Shadow the global-effect ON state for the driver's DSP bridge (the firmware's
			// only cold-toggle announcement of CHORUS is this LED -- see chorus_led()).
```

### kn7000_cpanel.cpp:451–454 (4 lines)

Precedes: `const int creg = addr & 0x1f;`

```c
		// CPC board (centre panel: OTHER PARTS/TG, the 16-part MUTE grid, ...). One sub-CPU drives both
		// CPL and CPC LEDs and selects the board with ADDR bit 5: 0xC0-0xDF = CPL, 0xE0-0xFF = CPC
		// (empirically CPC LED frames appear only as ADDR 0xE0-0xFF; register = ADDR bits 4:0). Bits not
		// yet tied to a panel function are still driven, so the layout can name cpc_led# once identified.
```


---

## `kn6000_cpanel.h` — 5 blocks, 27 lines

### kn6000_cpanel.h:1–21 (21 lines)

```c
// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    KN6000 / KN6500 control panel HLE

    The SX-KN6000 and SX-KN6500 share ONE panel device: their firmware button
    matrices are BYTE-IDENTICAL (30 descriptor segments, 164 button-bits, zero
    differing entries), so a single class serves both models.

    The panel is scanned by TWO Mitsubishi M37471M2196S 8-bit sub-CPUs (service
    manual pp.45-49): IC1 on the CPL board (10 SEG strobe columns) and IC10 on
    the CPR board (16 SEG columns, 10 of them wired). The CPC, LCDL, LCDC and
    LCDR boards have no CPU of their own -- they are matrix extensions hanging
    off those two. Buttons sit at (SEG column x SW0..SW7 return line); LEDs sit
    at (PNP anode group x SEG column).

    The CP wire protocol, the ATN/RX handshake and the analog controllers are
    shared with the KN7000 and live in the base class (kn_cpanel.h).

***************************************************************************/
```

### kn6000_cpanel.h:36–36 (1 lines)

Precedes: `virtual ioport_constructor device_input_ports() const override ATTR_COLD;`

```c
	// device_t overrides
```

### kn6000_cpanel.h:39–39 (1 lines)

Precedes: `virtual int     num_scan_ports() const override { return 20; }`

```c
	// per-model geometry (see kn_cpanel.h)
```

### kn6000_cpanel.h:48–49 (2 lines)

Precedes: `optional_ioport_array<20> m_phys;`

```c
	// Button scan-matrix ports -- OWNED by this device. One per sub-CPU scan column:
	// CPL_SEG0..9 = normSeg 0x00-0x09, CPR_SEG0..9 = normSeg 0x0A-0x13.
```

### kn6000_cpanel.h:52–53 (2 lines)

Precedes: `output_finder<512> m_cpl_leds;`

```c
	// LED outputs (the two sub-CPU banks). No KN6000 .lay exists yet, so these are
	// currently unbound sinks; the D-number/legend inventory is in the notes.
```


---

## `kn6000_cpanel.cpp` — 4 blocks, 74 lines

### kn6000_cpanel.cpp:1–53 (53 lines)

```c
// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    KN6000 / KN6500 control panel HLE

    ONE device serves both models: their firmware button matrices are
    BYTE-IDENTICAL (compared descriptor-for-descriptor across all 30 segments
    and 164 button-bits -- zero differences).

    Where this matrix comes from
    ----------------------------
    The seg/bit GEOMETRY is extracted from the firmware itself: the
    PanelButtonDispatch descriptor arrays, reached through the pointer table at
    library 0x4C19BCAC (KN6000) / 0x4C19BDB0 (KN6500), consumed by the dispatcher
    at 0x4844D376 which indexes that table directly with the segment byte. Each
    12-byte entry is { u16 event, u16 class, u8 mask, u8 bit, u8 group, u8 flag,
    u32 handler }.

    The NAMES come from the SX-KN6000 service manual (pp.45-49), and the two
    sources agree cell-for-cell: all 150 populated button-bits in normSeg
    0x00-0x13 are accounted for, and every switch group the manual inventories
    (16 RHYTHM GROUP in 6/6/4 columns, 16 SOUND GROUP in 6/6/4, 32 MUTE UP/DOWN
    in four 8-tall columns, 6 PERFORMANCE PADS sharing three columns as 1/4, 2/5,
    3/6, 8 PANEL MEMORY, the CONDUCTOR and PART SELECT quads) lands exactly where
    the descriptors put it. That mutual confirmation is what makes this map
    trustworthy without a live sweep.

    Board split (service manual, confirmed by the descriptor content)
    ----------------------------------------------------------------
    Two Mitsubishi M37471M2196S sub-CPUs scan everything:
      IC1 on CPL -- 10 SEG columns -> normSeg 0x00-0x09, covering the CPL board
                    itself plus its matrix extensions LCDL and LCDC:
                      0x00-0x03 LCDL (RHYTHM GROUP, SOUND ARRANGER, APC, LCDL keys)
                      0x04-0x08 LCDC (32 MUTE UP/DOWN, PAGE/TR/HELP/HOLD/EXIT)
                      0x09      CPL  (PERFORMANCE PADS ops, MSA, VARIATION, DEMO)
      IC10 on CPR -- 16 SEG columns, 10 wired -> normSeg 0x0A-0x13, covering CPR
                    plus its extensions LCDR and CPC:
                      0x0A-0x0D LCDR (SOUND GROUP, SUSTAIN/DIGITAL EFFECT, LCDR keys)
                      0x0E-0x13 CPC + CPR (transport, effects, PANEL MEMORY, ...)
    A button is (SEG column x SW0..SW7 return line); an LED is (PNP anode group
    x SEG column). Note normSeg 0x12 is CPR SEG9, not SEG8: the manual finds CPR
    SEG8 unwired, and the firmware's normalized numbering skips it.

    Segments 0x14-0x1D exist in the descriptor table but are NOT panel buttons --
    they are the latched analog controls (the four pots at 0x16-0x19, the DATA
    dial at 0x1A) and pedal/rear switches, which reach the firmware through the
    base class's TYPE 2 control path rather than the switch-frame path.

    The CP wire protocol, ATN/RX handshake and analog controllers are shared with
    the KN7000 and live in the base class (kn_cpanel.cpp).

***************************************************************************/
```

### kn6000_cpanel.cpp:65–67 (3 lines)

Precedes: `static INPUT_PORTS_START(kn6000_cpanel)`

```c
// The front-panel BUTTON matrix belongs to the panel sub-CPUs this device emulates, so the
// ports live HERE rather than in the driver's INPUT_PORTS. One port per sub-CPU scan column;
// each bit is one SW return line, forwarded unchanged (port index == normSeg, a pure identity).
```

### kn6000_cpanel.cpp:268–273 (6 lines)

Precedes: `uint8_t kn6000_cpanel_device::seg_wire_addr(int seg) const`

```c
// Reverse-normalization: normSeg -> CP wire ADDR. The KN6000 keeps the same two-bank
// wire allocation as the KN7000 -- the CPL-side sub-CPU answers on ADDRs 0xC0.., the
// CPR-side one on 0x00.. -- but with 10 columns each rather than the KN7000's 12 + 10.
// (That the wire encoding is shared is what makes the KN6000 accept panel traffic at all
// while running the KN7000's panel device, and is why its TEMPO/PROGRAM wheel already
// worked: only the matrix CONTENTS differ, not the transport.)
```

### kn6000_cpanel.cpp:280–291 (12 lines)

Precedes: `void kn6000_cpanel_device::panel_led_frame(uint8_t addr, uint8_t data)`

```c
// One decoded LED-command frame. ADDR = board (bit 7:6 clear = CPR, set = CPL) | LED
// register; each DATA bit is one LED at index reg*8 + bit within that board's bank.
//
// The service manual inventories every LED by designator, colour and legend (CPL D125-D130,
// LCDL D101-D134, LCDC D106, LCDR D301-D320, CPC D323-D345, CPR D351-D377). What it does NOT
// give without further wire tracing is the anode-group x SEG coordinate for most of them,
// i.e. which register/bit the
// firmware uses. So this is a faithful GENERIC decode onto cpl_led#/cpr_led# outputs: the
// firmware's LED writes land on stable, correctly-banked output names. Binding individual
// D-numbers to legends is deferred until a KN6000 .lay exists to display them (there is none
// yet), at which point the manual's inventory plus the built-in "Panel SW & LED test"
// (service manual p.22 section 7.5) gives the ground truth to bind against.
```


---

# Part 2: the CPU-core files (2026-09-24)

The same move, applied to the rest of the series.

**`src/devices/cpu/mn10300/`** is new in this submission, so the whole file was in
scope: 135 blocks, 429 lines. Target was its closest sibling, `mn10200.cpp`/`.h`, at
15.8% / 14.9%; MAME's CPU cores span 2.0% (`h8.cpp`) to 40.9% (`m6805.cpp`).

**`src/devices/cpu/sharc/`** belongs to upstream. Reformatting upstream's own comments
in a pull request about something else is out of scope, so only blocks where *every*
line came from one of this branch's commits were touched -- found with `git blame`
against `upstream/master..HEAD`, 62 blocks totalling 203 lines. Any block mixing
upstream text with ours was left completely alone, which errs toward keeping too much.

Why these needed it more than the driver did, measured as our added lines against each
file's own baseline:

| file | our added lines | the file's baseline | ratio |
|---|---|---|---|
| `sharc.h` | 58.8% | 5.2% | 11x |
| `sharc.cpp` | 28.4% | 2.9% | 10x |
| `sharcdrc.cpp` | 20.1% | 5.9% | 3.4x |
| `sharcops.hxx` | 17.2% | 7.0% | 2.5x |

A reader opening `sharc.h` saw our hunks at eleven times the density of the code
around them.

## MN10300 core (new files)

### `mn10300.cpp` — 105 blocks, 365 lines

**mn10300.cpp:1–13** (13 lines)

```c
// license:BSD-3-Clause
// copyright-holders:Felipe Sanches
/*
    Panasonic MN10300 (AM33) CPU core.

    Implements the subset exercised by the Technics SX-KN series firmware, plus
    the on-chip interrupt controller, timers and serial channels. Unimplemented
    opcodes log and are skipped. mn103dasm.cpp supplies the debugger view.

    Encoding: destination register = operand bits [1:0], source = bits [3:2];
    PC-relative targets are relative to the start of the instruction;
    immediates and displacements are little-endian.
*/
```

**mn10300.cpp:23–25** (3 lines)

```c
// PSW flag bits. The low nibble (Z,N,C,V) is definite and load-bearing; IE/IM
// are confirmed from the firmware (every ICR update brackets `and 0xf7ff,psw` /
// `or 0x0800,psw`, and the maskable-interrupt path works end-to-end).
```

**mn10300.cpp:42–44** (3 lines)

```c
//**************************************************************************
//  construction / device plumbing
//**************************************************************************
```

**mn10300.cpp:55–57** (3 lines)

```c
	// Flat 32-bit little-endian space, 32-bit data bus. The concrete part supplies
	// the internal map, which is appended after the driver's map and so takes
	// priority over any overlapping driver entry.
```

**mn10300.cpp:85–90** (6 lines)

```c
// Internal address map, in a flat 32-bit little-endian space with a 32-bit data
// bus: IVAR0-IVAR6 (0x20000000-0x2000001B), the INTC (0x34000100-0x340002FF),
// the SIO (0x34000800-0x3400082F) and the TM4/TM5 timer windows (0x34001080,
// 0x34001090 and 0x340010A0, 4 bytes each, the counter window read-only). The
// machine maps the rest; the timer windows are narrow so that the undecoded
// registers beside them reach it rather than being swallowed here.
```

**mn10300.cpp:94–94** (1 lines)

```c
	// GxICR array, the 0x34000200 group register and the 0x34000280 EXTMD latch.
```

**mn10300.cpp:97–98** (2 lines)

```c
	// TM4/TM5: mode bytes @0x34001080/82, reloads @0x34001090/92, counters
	// @0x340010A0/A2 (only TM5 -- offset 1 of each word pair -- is live).
```

**mn10300.cpp:145–146** (2 lines)

```c
	// (m_tm5_timer is a device-allocated emu_timer and is save-stated
	// automatically.)
```

**mn10300.cpp:172–173** (2 lines)

```c
	// The boot address is strapped per board (set_reset_pc). SP is left at zero:
	// the reset code establishes its own before its first push or call.
```

**mn10300.cpp:183–183** (1 lines)

```c
	// On-chip SIO: config and control cleared, RX rings emptied by head = tail.
```

**mn10300.cpp:191–194** (4 lines)

```c
	// On-chip INTC + TM5. m_iagr_latch and m_intc_280 are deliberately NOT
	// cleared here; both are construction-initialised, and a board that drives
	// polled ICR lines re-establishes them in its own machine_reset, which runs
	// after this one (device_reset_after_children ordering).
```

**mn10300.cpp:196–197** (2 lines)

```c
	// ...and the delivery state derived from them, which would otherwise survive
	// a reset holding the level and vector of an interrupt that no longer exists.
```

**mn10300.cpp:218–220** (3 lines)

```c
//**************************************************************************
//  interrupts
//**************************************************************************
```

**mn10300.cpp:224–225** (2 lines)

```c
	// Line 0 is the single maskable interrupt raised by the on-chip interrupt
	// controller above. Latch it; the run loop re-checks it each instruction.
```

**mn10300.cpp:230–234** (5 lines)

```c
// Accept a maskable interrupt: the AM33 pushes the return PC and PSW to the
// stack and vectors to the handler; we clear IE so the handler runs without
// immediate re-entry (it re-enables IE via rti after acking its source, or
// explicitly once the source's REQUEST bit is cleared). level/group are recorded
// for faithfulness; the actual source is resolved by the handler reading IAGR.
```

**mn10300.cpp:238–241** (4 lines)

```c
	// The INTC freezes its arbitration result -- group and vector -- at the accept
	// instant. PSW.IM below takes the `level` PARAMETER, which check_irq captured
	// before that re-arbitration, so a source arriving between the two does not
	// change the mask the handler runs under.
```

**mn10300.cpp:254–261** (8 lines)

```c
	// PSW.IM level masking: a pending interrupt is accepted only when its
	// priority level is numerically LOWER than IM (level 0 = highest priority;
	// IM=7 accepts everything, IM=0 accepts nothing). take_irq sets IM to the
	// accepted level, so an in-service level blocks same-or-lower priorities
	// until rti restores the saved PSW -- without this, a handler that
	// re-enables IE mid-body (the panel state machine does) immediately
	// re-accepts its own still-pending level-0 interrupt and nests itself
	// hundreds deep until the stack is destroyed.
```

**mn10300.cpp:268–283** (16 lines)

```c
//**************************************************************************
//  interrupt vector registers (IVAR0-IVAR6) @ 0x20000000
//**************************************************************************
//
// Seven 16-bit registers, IVARn at 0x20000000 + n*4, one per maskable interrupt
// level: a level-n interrupt vectors to m_vector_base + IVAR[n], the register
// holding only the low 16 bits of the entry point. Reset enters at the base and
// a nonmaskable interrupt at base + 8. The upper half of each four-byte slot is
// unimplemented. Levels run 0 (highest priority) to 6; level 7 is the idle
// value of PSW.IM and has no register, and check_irq requires level < PSW.IM,
// so it is never delivered.
//
// The base is 0x40000000 on the parts the documentation covers, which is also
// where the reset vector always sits, so a board that boots from a ROM there
// gets a vector table at the bottom of its ROM. A machine whose decode differs
// says so with set_vector_base().
```

**mn10300.cpp:302–332** (31 lines)

```c
//**************************************************************************
//  on-chip interrupt controller (INTC) @ 0x34000100
//**************************************************************************
//
// Reverse-engineered from software that drives it; no datasheet was available.
//
// GxICR(group) = 0x34000100 + group*4 (16-bit): bits 3:0 DETECT, bit4
// REQUEST, bit8 ENABLE, bits 14:12 LEVEL. A source is pending when its
// REQUEST bit is set; the maskable line is asserted while any
// ENABLE&REQUEST source exists; among pending groups the winner is the
// LOWEST level value (highest priority). Quirks:
//  * 0x34000100/0x104 double as the IAGR an interrupt dispatcher reads:
//    0x34000100 returns the latched group << 3; the
//    0x34000200 group register returns it << 2. Both latch at the accept
//    instant (real INTC latches IAGR at acknowledge).
//  * GxICR write: high byte (ENABLE+LEVEL) stored as written; DETECT bits
//    are write-1-to-clear, limited to the byte lanes actually written;
//    REQUEST is derived from the surviving DETECT bits.
//  * group 0x17 software-trigger self-ack: writing DETECT bit0 latches
//    DETECT+REQUEST, which software uses to hand-shake a device self-test.
//  * EXTMD (0x34000280) is a latched read-back register; every write is
//    reported outward via intc_extmd_cb, so a board can decode transitions.
//
// Vector delivery: each interrupt LEVEL carries its own handler address, in
// the IVAR register file below.
//
// The register model and its quirks are above. An interrupt
// handler reads the pending group from the IAGR at 0x34000100, indexes its
// handler table and calls the ISR registered for that group. `offset` is the
// 16-bit word index within 0x34000100; group = offset/2, register =
// 0x34000100 + group*4.
```

**mn10300.cpp:334–339** (6 lines)

```c
// Outward event callbacks, all optional and all no-ops when unbound:
//   intc_ack_cb    (write8, data = group): a GxICR write carried DETECT-ack
//        bits (data & mem_mask & 0x000f).
//   intc_accept_cb (write8, data = group): this group was latched into the IAGR
//        at interrupt accept.
//   intc_extmd_cb  (write16): the new EXTMD value after each write.
```

**mn10300.cpp:342–343** (2 lines)

```c
	// Among enabled+requested groups the winner is the highest-priority one,
	// which is the LOWEST ICR LEVEL value (bits 14:12).
```

**mn10300.cpp:354–355** (2 lines)

```c
// Freeze the arbitration result (group and vector, atomically) at the instant
// the CPU accepts the interrupt -- the INTC latches IAGR at acknowledge.
```

**mn10300.cpp:362–362** (1 lines)

```c
		// Board hook: this group was latched into the IAGR (see intc_accept_cb).
```

**mn10300.cpp:381–381** (1 lines)

```c
												  // so the state has to accumulate
```

**mn10300.cpp:394–398** (5 lines)

```c
		// Board hook: the KN7000 decodes the panel-ATN edge re-arm transition
		// (bits 7:6, 11b -> 10b) here -- the group-0x1A ISR's pass 1 re-arms
		// the pin for the opposite edge and expects the second edge of the
		// panel's attention pulse after it returns. That decode (with its
		// previous-value shadow and deferred assert) stays driver-side.
```

**mn10300.cpp:407–408** (2 lines)

```c
	// A write carrying DETECT-ack bits: report it outward, so a board that needs
	// level-like re-delivery for one of its sources can implement it.
```

**mn10300.cpp:411–415** (5 lines)

```c
	// Software trigger on group 0x17 (GxICR 0x3400015c): writing a DETECT bit
	// latches REQUEST, so a poll of REQUEST succeeds without an external source
	// asserting. Software uses this to hand-shake a device self-test. Writing
	// DETECT alone leaves ENABLE clear, so nothing is dispatched. Only this group
	// is known to be used that way; generalising it awaits evidence.
```

**mn10300.cpp:422–428** (7 lines)

```c
	// GxICR write semantics (matches the on-chip INTC, and required for correct
	// delivery): the high byte (ENABLE + LEVEL) is stored as written; the DETECT
	// flags (bits 0-3) are WRITE-1-TO-CLEAR; REQUEST (0x10) is hardware status
	// derived from the surviving DETECT bits. A plain latched write here would
	// let the firmware's enable write (e.g. 0x0100) silently destroy a pending
	// request that arrived between 'clear' and 'enable' -- observed in the panel
	// handshake, where the reply's REQUEST was wiped by the subsequent enable.
```

**mn10300.cpp:432–434** (3 lines)

```c
		// w1c applies ONLY to detect bits the access actually wrote (mem_mask):
		// the firmware's control-byte writes (movbu to +1, mask 0xFF00) must not
		// touch pending DETECT flags.
```

**mn10300.cpp:443–444** (2 lines)

```c
	// REQUEST + DETECT bit0; a handler scans DETECT bits 0-3 to pick the
	// sub-source within the group.
```

**mn10300.cpp:458–458** (1 lines)

```c
	// Drive our own maskable input line through the standard, synchronized path.
```

**mn10300.cpp:463–478** (16 lines)

```c
//**************************************************************************
//  on-chip 16-bit timers @ 0x34001080 (TM4/TM5)
//**************************************************************************
//
// TM5 underflow asserts INTC group 7. Control sequences, read off the software
// that drives the timer:
//   start   write mode -> write base -> bset 0x40 (load counter from base) ->
//           bclr 0x40 -> bset 0x80 (count enable)
//   restart bclr 0x80 -> bset/bclr 0x40 -> bset 0x80
//   tempo   write a new base to 0x34001092 while running -- takes effect on the
//           next underflow (auto-reload).
// The low mode bits select the source clock; see tm5_rearm for the prescale.
//
// The handlers are 16-bit on the word pairs 0x1080/0x1090/0x10A0; offset 0 =
// the TM4 half (kept at the driver behaviour: reads 0, writes dropped),
// offset 1 = TM5.
```

**mn10300.cpp:510–512** (3 lines)

```c
	// Live down-count, derived from the emu_timer's phase. Taken in ticks: the
	// product of the reload and the remaining attoseconds overflows 64 bits for
	// any reload above ~6073.
```

**mn10300.cpp:532–533** (2 lines)

```c
	// While running, the new reload takes effect at the next underflow: keep the
	// current countdown, change only the periodic reload.
```

**mn10300.cpp:538–541** (4 lines)

```c
// TM5: mode byte @0x34001082, 16-bit reload @0x34001092, down-counter
// @0x340010A2. Underflow asserts INTC group 7. The TM4 half of each register
// word (offset 0 of each window) reads 0 and drops writes; TM5BC writes fall
// through to the machine map, which maps the counter window read-only.
```

**mn10300.cpp:544–548** (5 lines)

```c
	// IOCLK = fc/2 (MN10300 convention; KN7000: 32 MHz core clock -> 16 MHz
	// IOCLK, confirmed from the firmware's own MIDI-baud math: IOCLK/8/(TM3BR+1)
	// = 31250 => 16 MHz). The prescale is fixed by the 96-PPQN math: at
	// the boot default of q=120 the rate must be 192 Hz; the observed reload
	// confirms the divider (logged above).
```

**mn10300.cpp:562–584** (23 lines)

```c
//**************************************************************************
//  on-chip SIO -- three serial channels @ 0x34000800/0x810/0x820
//**************************************************************************
//
// Reverse-engineered from software that drives it; no datasheet was available.
//
// Register layout per channel (stride 0x10, 16-bit regs):
//   +0  config   bit15 = sync-transfer START (self-clears instantly here,
//                        since transfers complete instantly)
//                bit14 = RX enable (the endpoint may send its queued reply)
//   +4  control  (byte)
//   +8  TX data  (byte, write; the data write itself clocks one transfer)
//   +9  RX data  (byte, read; pops the 64-byte RX FIFO)
//   +C  status   bit4 = RxRDY only; bit7 (RX-empty) and bit6 (TxRDY) are
//                deliberately not modelled (see sio_r).
//
// Precedent for on-chip serial living in the CPU core: the MN10200 (m_serial[]).
//
// The handlers are 16-bit; `offset` is the 16-bit-word index within
// 0x34000800. Each channel spans 0x10 bytes = 8 words, so channel = offset / 8
// and the byte within the channel is (offset << 1) & 0xf. Byte registers
// (control @+4, TX @+8, RX @+9) are reached with movbu, i.e. a masked 16-bit
// access: TX is the low byte of word 4, RX the high byte.
```

**mn10300.cpp:586–594** (9 lines)

```c
// Interrupt-worthy events go out through per-channel callbacks; the machine
// forwards them to the INTC, which keeps the board-specific group numbers and
// any deferral driver-side:
//   sio_tx_cb        (write8): byte written to the TX data register
//   sio_tx_done_cb   (write_line, 1 per event): that byte's transfer completed.
//        Invoked BEFORE sio_tx_cb.
//   sio_rx_rdy_cb    (write_line, 1 per byte): a byte was pushed into the RX FIFO
//   sio_rx_enable_cb (write_line, called with 1): config bit14 written set
// Unbound callbacks are no-ops, so a machine may wire only what it needs.
```

**mn10300.cpp:610–612** (3 lines)

```c
		// Only RxRDY is modelled. The status byte also carries RX-empty (bit7)
		// and TxRDY (bit6); supplying them changes boot-time behaviour on the
		// machines tested here, so they wait until TX is actually modelled.
```

**mn10300.cpp:626–631** (6 lines)

```c
		// Bit 15 = transfer START on the synchronous link (ch0): software sets
		// it to clock one byte, then polls until the hardware self-clears it.
		// Transfers complete instantly here, so it just self-clears. The actual
		// per-byte trigger is the DATA write -- software drives whole payloads
		// without touching bit15 again -- so completion is signalled per data
		// write in sio_tx_byte, not per bit15 write.
```

**mn10300.cpp:634–635** (2 lines)

```c
		// RX enable (bit14): notify the endpoint, which may now send its queued
		// reply, one byte per RX interrupt.
```

**mn10300.cpp:652–657** (6 lines)

```c
// Every data write clocks one (instantly completed) transfer. The completion
// event is raised BEFORE the byte is handed to the endpoint, mirroring the
// driver HLE's order (it scheduled its deferred group-0x11 INTC assert before
// calling the panel's tx_byte). The receiving driver is expected to defer the
// completion before asserting its INTC (an ISR-context synchronous assert is
// wiped by the exit ack -- see the KN7000's panel_txdone_cb / c11_unserviced).
```

**mn10300.cpp:664–667** (4 lines)

```c
// Endpoint -> RX FIFO. Each successfully-pushed byte fires the channel's
// RX-ready callback (KN7000 INTC groups: ch0 -> 0x10, ch1 -> 0x12,
// ch2 -> 0x14; the firmware's RX ISR reads +0x09 and acks its GxICR; polling
// paths see RxRDY regardless).
```

**mn10300.cpp:689–691** (3 lines)

```c
//**************************************************************************
//  flag helpers (32-bit)
//**************************************************************************
```

**mn10300.cpp:700–700** (1 lines)

```c
// r = a + b + carry_in; sets Z,N,C,V; returns the 32-bit result.
```

**mn10300.cpp:713–713** (1 lines)

```c
// r = a - b - borrow_in; sets Z,N,C(borrow),V; returns the 32-bit result.
```

**mn10300.cpp:726–727** (2 lines)

```c
// Condition test for the C0..C9 b<cc> family (indices into f_conds order:
// blt,bgt,bge,ble,bcs,bhi,bcc,bls,beq,bne).
```

**mn10300.cpp:761–763** (3 lines)

```c
//**************************************************************************
//  execute
//**************************************************************************
```

**mn10300.cpp:769–772** (4 lines)

```c
		// Service a pending maskable interrupt before fetching the next opcode.
		// The on-chip INTC line is LEVEL-triggered, so this is checked every
		// instruction (not just on the assert edge) -- it must fire the moment the
		// firmware sets PSW.IE while a source is still pending.
```

**mn10300.cpp:786–786** (1 lines)

```c
		// ---- clr dD (D = bits[3:2]) ----
```

**mn10300.cpp:792–792** (1 lines)

```c
		// ---- extb/extbu/exth/exthu dD ----
```

**mn10300.cpp:798–798** (1 lines)

```c
		// ---- add imm8,aD / add imm8,dD (imm8 sign-extended) ----
```

**mn10300.cpp:804–804** (1 lines)

```c
		// ---- mov imm16,aD (zx) / mov imm16,dD (sx) ----
```

**mn10300.cpp:810–810** (1 lines)

```c
		// ---- mov sp,aD ----
```

**mn10300.cpp:813–813** (1 lines)

```c
		// ---- inc dD (flags) / inc aD (no flags) (D = bits[3:2]) ----
```

**mn10300.cpp:817–817** (1 lines)

```c
		// ---- mov dD/aD,(disp8,sp)  (disp8 unsigned) ----
```

**mn10300.cpp:823–823** (1 lines)

```c
		// ---- inc4 aD (no flags) / asl2 dD ----
```

**mn10300.cpp:827–827** (1 lines)

```c
		// ---- mov (disp8,sp),dD / (disp8,sp),aD  (disp8 unsigned) ----
```

**mn10300.cpp:833–833** (1 lines)

```c
		// ---- mov dS,(aM) (0x60-0x6F) / mov (aM),dD (0x70-0x7F), 32-bit ----
```

**mn10300.cpp:841–841** (1 lines)

```c
		// ---- mov imm8,dD (src==dst) / mov dS,dD ----
```

**mn10300.cpp:848–848** (1 lines)

```c
		// ---- mov imm8,aD (zx, src==dst) / mov aS,aD ----
```

**mn10300.cpp:855–855** (1 lines)

```c
		// ---- cmp imm8,dD (sx, src==dst) / cmp dS,dD ----
```

**mn10300.cpp:862–862** (1 lines)

```c
		// ---- cmp imm8,aD (zx, src==dst) / cmp aS,aD ----
```

**mn10300.cpp:869–869** (1 lines)

```c
		// ---- conditional branches / bra (disp8, target = start_pc + sx8) ----
```

**mn10300.cpp:882–882** (1 lines)

```c
		// ---- nop ----
```

**mn10300.cpp:885–885** (1 lines)

```c
		// ---- jmp disp16 ----
```

**mn10300.cpp:889–889** (1 lines)

```c
		// ---- call disp16, regs, imm8 ----
```

**mn10300.cpp:896–896** (1 lines)

```c
			// imm8-total frame convention: return PC at [SP], regs below, SP -= imm8.
```

**mn10300.cpp:905–905** (1 lines)

```c
		// ---- movm (sp),regs (pop) / movm regs,(sp) (push) ----
```

**mn10300.cpp:909–914** (6 lines)

```c
		// ---- loop cache: setlb / Lcc (MN10300 hardware loop) ----
		// setlb records the loop top (LAR = the instruction after setlb) and
		// caches its first word (LIR). Lcc, at the loop bottom, branches back to
		// LAR while its condition holds. We re-fetch from LAR rather than model
		// the instruction-cache micro-op, which is functionally identical since
		// the loop body in memory does not change.
```

**mn10300.cpp:923–925** (3 lines)

```c
		// lra: unconditional branch back to the loop top (the setlb hardware loop).
		// The sim computes PC = LAR-4; this core stores the loop top directly in
		// m_lar (= that value), so a plain jump is correct -- same as Lcc taken.
```

**mn10300.cpp:928–928** (1 lines)

```c
		// ---- jmp disp32 (reset vector uses this) ----
```

**mn10300.cpp:932–932** (1 lines)

```c
		// ---- call disp32, regs, imm8 ----
```

**mn10300.cpp:939–939** (1 lines)

```c
			// imm8-total frame convention (see 0xCD).
```

**mn10300.cpp:948–952** (5 lines)

```c
		// ---- retf regs, imm8 : fast return via the MDR-cached address ----
		// imm8-total convention: SP += imm8 puts SP at the frame top; the return
		// PC comes from MDR (set by the paired call), and the saved registers are
		// read from fixed offsets below the new SP. PC is taken before the register
		// restore (which may itself reload the caller's MDR).
```

**mn10300.cpp:963–963** (1 lines)

```c
		// ---- ret regs, imm8 : normal return (PC read from the frame top) ----
```

**mn10300.cpp:974–974** (1 lines)

```c
		// ---- add dS,dD ----
```

**mn10300.cpp:979–979** (1 lines)

```c
		// ---- prefixed groups ----
```

**mn10300.cpp:992–993** (2 lines)

```c
		// TODO(MN10300): 0xF9,0xFB,0xFD (udf imm) still unimplemented --
		// these fall through to the length-correct skip below until needed.
```

**mn10300.cpp:995–998** (4 lines)

```c
			// Not implemented yet. Advance PC by the (validated) real length so
			// the fetch stream stays aligned and the machine remains steppable
			// during bring-up. This treats the opcode as a no-op rather than a
			// trap -- correct results require the real implementation.
```

**mn10300.cpp:1001–1008** (8 lines)

```c
				// AM33 udf00 immediate forms (F9=imm8, FB=imm16, FD=imm32): signed
				// multiply-by-immediate, identical to the F6 op2>>4==0 "mulq" the core
				// already implements (low 32 -> Dn, high 32 -> MDRQ). Confirmed against
				// fixed-point coefficient-multiply code
				// (`udf00 0x59ba,d1 ; add 0x2000,d1 ; asr 14,d1`, signed coefficients).
				// op2 must be 0x00-0x03: binutils gives mulq SIMM8,Dn as 0xf90000
				// mask 0xfffc00, and op2 bit 3 selects the AM33 `mov` forms
				// (0xf90800 / 0xfb080000 / 0xfd080000) instead.
```

**mn10300.cpp:1034–1034** (1 lines)

```c
		// TODO(MN10300): real per-instruction cycle counts.
```

**mn10300.cpp:1041–1043** (3 lines)

```c
// 0xFC prefix: 32-bit immediate / displacement / absolute forms (6 bytes total
// for the reg-immediate cases). Only the common register-immediate ops are
// implemented; the (disp32,sp)/(abs32) load-store forms are TODO.
```

**mn10300.cpp:1072–1073** (2 lines)

```c
// 0xFC: imm32 / disp32 / abs32 forms. Always 6 bytes (op, op2, then a 32-bit
// operand). PC is set to start+6 at the end unless a control-flow op returns.
```

**mn10300.cpp:1126–1129** (4 lines)

```c
// 0xF5: AM33 DSP register writes (putx, putchclx). 2-byte, like F2. Semantics
// from the GDB simulator (sim_mn10300.igen). Operand regs are op2 bits [1:0]=Dn,
// [3:2]=Dm. (binutils also lists a colliding `mov Am,Rn` for F5xx; every F5 use
// seen so far is a DSP put-op.)
```

**mn10300.cpp:1144–1147** (4 lines)

```c
// 0xF6: AM33 DSP ops (mulq/mulqu/sat16/sat24 and the MAC-register get-ops). The
// interrupt handler uses getx/getchx/getclx to save the DSP accumulator that
// movm cannot reach. Semantics from the GDB simulator; MAME's disassembler
// mislabels this whole group as "udf".
```

**mn10300.cpp:1169–1170** (2 lines)

```c
		// most-significant set bit in Dm's low 16 bits (0 if none). Used by the
		// Huffman leading-run decode in software JPEG decoders.
```

**mn10300.cpp:1180–1180** (1 lines)

```c
// 0xF8: imm8 / disp8 forms. Always 3 bytes (op, op2, then one operand byte).
```

**mn10300.cpp:1244–1244** (1 lines)

```c
	// and/or/xor/not: set Z,N; clear V (C left undefined -> cleared here).
```

**mn10300.cpp:1251–1251** (1 lines)

```c
// 0xF0: reg-indirect moves and indirect call/jmp/ret. Always 2 bytes.
```

**mn10300.cpp:1270–1270** (1 lines)

```c
			// Control flow, selected by the whole op2 value.
```

**mn10300.cpp:1275–1275** (1 lines)

```c
			// TODO(MN10300): FE trap
```

**mn10300.cpp:1286–1287** (2 lines)

```c
// 0xF1: cross-type reg-reg arithmetic (between data and address registers).
// Always 2 bytes. dst=bits[1:0], src=bits[3:2].
```

**mn10300.cpp:1316–1316** (1 lines)

```c
// 0xF2: logical / mul / div / shift / special-register moves. Always 2 bytes.
```

**mn10300.cpp:1334–1337** (4 lines)

```c
		// div/divu set V: 0 when the quotient fits, 1 on zero-division or when it
		// does not, in which case the manual leaves Dn, MDR and the other flags
		// undefined -- so they are left alone. The 64/32 divide is guarded rather
		// than attempted: INT64_MIN / -1 traps on the host.
```

**mn10300.cpp:1342–1343** (2 lines)

```c
			// INT64_MIN / -1 traps on the host, and so does the matching %, so the
			// no-result cases are decided BEFORE either operator runs.
```

**mn10300.cpp:1414–1414** (1 lines)

```c
// 0xF3: 32-bit indexed load/store, EA = aM + dI. Always 2 bytes.
```

**mn10300.cpp:1432–1432** (1 lines)

```c
// 0xF4: byte/half indexed load/store, EA = aM + dI. Always 2 bytes.
```

**mn10300.cpp:1450–1450** (1 lines)

```c
// 0xFA: imm16 / disp16 forms. Always 4 bytes (op, op2, imm16-lo, imm16-hi).
```

**mn10300.cpp:1460–1460** (1 lines)

```c
		// mov/movbu/movhu (disp16,aM): type=bits[6:5], bit4=dir(store), reg=bits[3:2], aM=bits[1:0]
```

**mn10300.cpp:1489–1490** (2 lines)

```c
			// store reg -> (disp16,sp): op2 = 1001_rrtt, reg=bits[3:2], tt=bits[1:0]
			// (0 mov aM / 1 mov dM / 2 movbu dM / 3 movhu dM). binutils 0xfa90..0xfa93.
```

**mn10300.cpp:1520–1520** (1 lines)

```c
// 0xFE: bit set/clear/test on an absolute address. 5 bytes (abs16) or 7 (abs32).
```

**mn10300.cpp:1536–1536** (1 lines)

```c
	// kind == 0x02: btst (no write)
```

**mn10300.cpp:1541–1559** (19 lines)

```c
// Register-list transfer for movm. call/ret use store_regs_at/load_regs_at
// below, whose frame differs: the 16-byte MDRQ/MCRH/MCRL/MCVF gap sits above
// E0/E1 rather than below, and bit 3 covers 28 bytes there rather than 32.
//
// Register-mask bit -> register:
//   bit 7 = D2   bit 6 = D3   bit 5 = A2   bit 4 = A3
//   bit 3 = {D0, D1, A0, A1, MDR, LIR, LAR} + a 4-byte dummy slot (32 bytes)
//   bit 2 = {E2, E3}
//   bit 1 = {E4, E5, E6, E7}
//   bit 0 = {E0, E1} + a 16-byte MDRQ/MCRH/MCRL/MCVF gap
//
// load pops in the
// exact reverse so SP and the saved values always round-trip.
// movm regs,(sp) save. Register-per-mask-bit mapping and order are the exact
// AM33 semantics from the GDB simulator (sim_mn10300.igen, opcode 0xCF):
// the extended (E-register/DSP) groups are pushed first (highest addresses),
// then D2/D3/A2/A3, then the {D0,D1,A0,A1,MDR,LIR,LAR}+dummy group last. The
// dummy 4-byte slot from bit 3 is what an interrupt handler reuses to save the
// DSP context (getx/getchx/getclx), which is why modelling it exactly matters.
```

**mn10300.cpp:1597–1605** (9 lines)

```c
// Offset-based register block used by call/ret/retf (NOT movm). The frame top is
// `base` (= the SP where the return PC lives); the saved registers occupy fixed
// negative offsets below it and SP is NOT touched here. The offset walk is exactly
// the GDB simulator's (op_utils / the 0xdf,0xde igen), so store_regs_at and
// load_regs_at round-trip and a call's frame is read back correctly by ret/retf.
// call/ret/retf use the AM33 imm8-total frame convention: the return PC sits at
// [SP] and the saved registers at fixed negative offsets below it, and SP moves
// only by imm8. These two write and read the register block at those offsets
// WITHOUT moving SP, mirroring the GDB simulator's ret/retf offset walk.
```

### `mn10300.h` — 27 blocks, 44 lines

**mn10300.h:1–5** (5 lines)

```c
// license:BSD-3-Clause
// copyright-holders:Felipe Sanches
/*
    Panasonic MN10300 (AM33) CPU core.
*/
```

**mn10300.h:12–12** (1 lines)

```c
// Debugger/state-table indices (unique, non-zero; value order is cosmetic)
```

**mn10300.h:21–21** (1 lines)

```c
	// TODO(MN10300/AM33): E0..E7, MDRQ, LIR/LAR, MCRH/MCRL/MCVF, SSP/MSP/USP, ...
```

**mn10300.h:24–24** (1 lines)

```c
// External interrupt input lines
```

**mn10300.h:30–30** (1 lines)

```c
	// TODO(MN10300): the nonmaskable interrupt is not modelled.
```

**mn10300.h:38–38** (1 lines)

```c
	// construction/destruction (single concrete, instantiable device)
```

**mn10300.h:40–41** (2 lines)

```c
	// Reset state. The boot address is strapped per board, so the machine supplies
	// it; the reset code establishes its own stack pointer.
```

**mn10300.h:44–45** (2 lines)

```c
	// On-chip interrupt controller (INTC) @ 0x34000100.
	//
```

**mn10300.h:47–49** (3 lines)

```c
	// Raw ICR access for POLLED lines a board drives directly (a card-detect pin,
	// say). Deliberately NO recompute: such lines never have ENABLE set, so
	// delivery is unaffected.
```

**mn10300.h:53–53** (1 lines)

```c
	// Where this board's decode puts the CPU's vector base (see ivar_w).
```

**mn10300.h:55–55** (1 lines)

```c
	// Outward event callbacks; see intc_pending_group() in the .cpp.
```

**mn10300.h:60–62** (3 lines)

```c
	// On-chip serial (SIO): three channels @ 0x34000800/0x810/0x820.
	//
	// Per-channel event callbacks; see sio_r() in the .cpp.
```

**mn10300.h:68–69** (2 lines)

```c
	// Endpoint devices (panel HLE, MIDI UART bridges) deliver received bytes
	// here; each successful push fires sio_rx_rdy_cb for that channel.
```

**mn10300.h:73–75** (3 lines)

```c
	// On-chip 16-bit timers @ 0x34001080 (TM4/TM5 pair).
	//
	// The prescale between IOCLK and the counter, fixed by the 96-PPQN math.
```

**mn10300.h:83–84** (2 lines)

```c
	// The MN103002A's on-chip peripheral complement: INTC at 0x34000100, SIO at
	// 0x34000800, and the TM4/TM5 timer windows.
```

**mn10300.h:87–87** (1 lines)

```c
	// device_t overrides
```

**mn10300.h:91–91** (1 lines)

```c
	// device_execute_interface overrides
```

**mn10300.h:93–93** (1 lines)

```c
	// Timing is uncalibrated: one cycle per instruction, seven for an interrupt.
```

**mn10300.h:97–97** (1 lines)

```c
	// TODO(MN10300): no internal clock divider is modelled (the MN10200 has one).
```

**mn10300.h:99–99** (1 lines)

```c
	// device_memory_interface overrides
```

**mn10300.h:102–102** (1 lines)

```c
	// device_state_interface overrides
```

**mn10300.h:105–105** (1 lines)

```c
	// device_disasm_interface overrides
```

**mn10300.h:178–178** (1 lines)

```c
	// TODO(MN10300/AM33): extended registers E0..E7, MDRQ, register banks.
```

**mn10300.h:192–192** (1 lines)

```c
	// TODO(MN10300): alignment policy undecided; any offset is accepted.
```

**mn10300.h:225–225** (1 lines)

```c
	// shift/logical flag helpers
```

**mn10300.h:228–229** (2 lines)

```c
	// typed memory transfer used by the F8/FA/FC (disp,aM)/(disp,sp)/(abs) moves.
	// type: 0/1 = 32-bit mov (a-reg iff a_reg), 2 = movbu (byte), 3 = movhu (half).
```

**mn10300.h:237–239** (3 lines)

```c
// The concrete part in the Technics SX-KN series. The family base above carries
// the core; this carries the peripheral map, the way cpu/mn10200 splits
// mn10200_device from MN1020012A.
```

### `mn10300_insn_length.h` — 3 blocks, 20 lines

**mn10300_insn_length.h:1–18** (18 lines)

```c
// license:BSD-3-Clause
// copyright-holders:Felipe Sanches
/*
    MN10300 instruction-length decoder (dependency-free).

    Returns the length in bytes of the MN10300 instruction whose first two bytes
    are (op, op2). Only 0xFE needs op2; for every other first byte op2 is ignored,
    so callers that only have the first byte may pass 0.

    This is shared by the CPU core (to advance PC correctly, including over
    not-yet-implemented opcodes so the fetch stream stays aligned) and by the
    standalone validator in tests/, which checks it instruction-by-instruction
    against MAME unidasm over the real KN7000 ROM: 550328/550328 legal
    instructions match (the only discrepancies being the documented 0xF4
    disassembler bug and illegal "?" opcodes, both expected).

    Header-only and free of any MAME dependency so the test can compile it alone.
*/
```

**mn10300_insn_length.h:44–44** (1 lines)

```c
			// imm8 forms are the src==dst encodings (bits[3:2]==bits[1:0]).
```

**mn10300_insn_length.h:77–77** (1 lines)

```c
// Convenience overload for callers holding a raw pointer to the instruction.
```

## SHARC (our added blocks only)

### `sharc.cpp` — 10 blocks, 19 lines

**sharc.cpp:144–144** (1 lines)

```c
// ADSP-21065L (KN7000 IC306). See the class comment in sharc.h.
```

**sharc.cpp:161–163** (3 lines)

```c
// Internal program memory: 48-bit instruction words in 64-bit slots. The recovered firmware
// loads code at PM 0x8000-0x8Dxx; model it (generously) as plain RAM. Not the base's
// block-interleaved pm_r/pm_w (those assume the 2M/4M 0x20000 geometry).
```

**sharc.cpp:166–166** (1 lines)

```c
	// Code region (0x8000-0x8FFF): 48-bit instructions in 64-bit slots (kernel code 0x8000-0x8Dxx).
```

**sharc.cpp:168–169** (2 lines)

```c
	// Data region: filter coefficients and state. This is the PM-bus view of the same
	// SRAM data_65l presents on the DM bus, so PM(0x9800) == DM(0x9800).
```

**sharc.cpp:173–174** (2 lines)

```c
// Internal data memory + IOP registers. IOP 0x00-0x00FF is stubbed (see iop65l_r/w).
// Anything from 0x20000 up is EXTERNAL memory and belongs to the board.
```

**sharc.cpp:179–179** (1 lines)

```c
	// Data region: shared with pgm_65l so a DM write is readable via the PM bus.
```

**sharc.cpp:190–193** (4 lines)

```c
// 21065L IOP register bank -- stubbed. The base 2106x core fatalerrors on the
// 21065L-specific SPORT/SDRAM/DMA offsets (0x28-0x3C, 0x53-0x7B, 0xE0-0xFC);
// returning 0 and accepting writes lets a program run without crashing. Real
// SPORT/SDRAM/DMA modelling is still to do.
```

**sharc.cpp:201–201** (1 lines)

```c
	// Writes are accepted and dropped; see iop65l_r.
```

**sharc.cpp:309–311** (3 lines)

```c
	// A host-side agent modified program memory behind the DRC's back; mark the
	// recompiled cache dirty so execute_run_drc() flushes and recompiles from the
	// updated PM on its next timeslice. Harmless in interpreter mode.
```

**sharc.cpp:637–637** (1 lines)

```c
	// The 21065L declares no memory blocks, so it reaches here with length 0.
```

### `sharc.h` — 12 blocks, 47 lines

**sharc.h:38–43** (6 lines)

```c
	// Host code-upload notification: when something OUTSIDE the SHARC (e.g. a host
	// port DMA writing a new microprogram into internal PM) modifies the program
	// memory, the DRC's self-modify detection (which only fires for PM writes issued
	// by the SHARC's own pm_write handlers) is bypassed and the recompiled cache goes
	// stale. Call this after such a write to force a full cache flush on the next
	// timeslice so the new code actually runs.
```

**sharc.h:108–110** (3 lines)

```c
	// Reset PC (boot entry). The 2106x reset vector is at internal-RAM-base + 4
	// (0x20004 for the 2M/4M parts); the 21065L variant overrides this for its own
	// internal-RAM layout.
```

**sharc.h:113–115** (3 lines)

```c
	// Base of internal memory: 0x20000 on the 2M/4M parts, 0x8000 on the 21065L.
	// check_interrupts() vectors a taken interrupt N to irq_vector_base() + N*4,
	// and this is also the 128 KiB page the DRC frontend's loop map covers.
```

**sharc.h:119–123** (5 lines)

```c
	// Lowest address the DRC memory accessors treat as internal-SRAM (served from m_blocks,
	// the block-interleaved fast path). The 2M/4M parts put internal SRAM at 0x20000-0x3FFFF;
	// the 21065L has a different layout and does not populate m_blocks, so it overrides this to
	// an out-of-range value, forcing every access through the address map (space_access) which
	// serves its plain-RAM internal SRAM (0x8000-0x1FFFF) and external SDRAM (0x20000+).
```

**sharc.h:582–589** (8 lines)

```c
// ADSP-21065L -- the low-cost SHARC variant used as the Technics KN7000's effects DSP
// (IC306). Same 2106x instruction set as the base, but a smaller, differently-organised
// on-chip SRAM and a different I/O-register personality. That personality is derived from
// the program the KN7000 uploads to it: code at PM 0x8000-0x8Dxx, data at DM
// 0x9800/0x9C40/0xC000/0xC302, external SDRAM
// delay memory at 0x80000+, and an IOP register set the base core does not model. Modelled
// here with plain-RAM internal memory (the base's block-interleaved pm_r/pm_w assume the
// 2M/4M geometry) and stubbed IOP registers.
```

**sharc.h:593–593** (1 lines)

```c
	// construction/destruction
```

**sharc.h:598–599** (2 lines)

```c
	// The 21065L's internal RAM base is 0x8000, so its interrupt vector table sits at 0x8000
	// (vector N at 0x8000 + N*4; e.g. IRQ0 = vector 8 = 0x8020).
```

**sharc.h:602–604** (3 lines)

```c
	// The 21065L does not populate m_blocks; route all DRC memory accesses through the address
	// map by making no address qualify for the internal-SRAM fast path (0x01000000 > any
	// 24-bit SHARC address). See pgm_65l/data_65l for the actual internal/external RAM.
```

**sharc.h:607–613** (7 lines)

```c
	// RSTI (reset) is vector 1 at 0x8004, whose slot holds "IDLE ; JUMP init". The IDLE is the
	// host-boot download-wait; our host-boot glue only releases the DSP once the full program
	// has been uploaded, so that wait is already satisfied and we want to enter at the JUMP
	// (0x8005). MAME primes the fetch pipeline with daddr = reset_pc + 1 and the execute loop
	// runs the instruction at daddr first, so the effective first instruction is reset_pc + 1.
	// Setting reset_pc = 0x8004 therefore begins execution at 0x8005 (JUMP init), skipping the
	// IDLE at 0x8004 -- exactly the post-download-wait entry we want.
```

**sharc.h:624–628** (5 lines)

```c
	// Internal-SRAM data region (0x9000-0x1FFFF), shared between the PM and DM buses so a value
	// written via DM(addr) is readable via PM(addr) -- the SHARC's unified internal memory. The
	// recovered kernel loads filter coefficients/state to DM 0x9800/0x9C40 (host boot) and reads
	// them via the PM bus (R3 = PM(I8), I8 = 0x9800). The code region (0x8000-0x8FFF, 48-bit
	// instructions) is PM-only and kept as separate .ram(); nothing lives in 0x8D93-0x97FF.
```

**sharc.h:630–631** (2 lines)

```c
	// Sized from what the uploaded program actually uses: it reaches 0x1FFE6.
	// 0x20000 up is external memory and belongs to the board.
```

**sharc.h:636–637** (2 lines)

```c
	// PM data accesses land in 64-bit program slots; the core's pm_read32/pm_write32 use the top
	// 32 of the 48-bit word (read_qword >> 16 / data << 16), so mirror that convention here.
```

### `sharcdrc.cpp` — 29 blocks, 99 lines

**sharcdrc.cpp:156–161** (6 lines)

```c
	// Fallback for compute operations the DRC doesn't yet generate inline (notably the
	// fixed-point multiplier / MAC family): run the interpreter's COMPUTE() for exactly this
	// one instruction. The generator wraps this in save_fast_iregs / load_fast_iregs so the
	// register file in memory is current; here we round-trip the flags between the DRC's
	// unpacked astat_drc and the packed astat that COMPUTE() reads and writes. COMPUTE() still
	// throws for a genuinely-unknown opcode, so nothing is silently ignored.
```

**sharcdrc.cpp:170–172** (3 lines)

```c
	// Same idea as compute_fallback, but for immediate-shift ops the DRC has no inline generator
	// for (e.g. the field-deposit/extract SE variants used by the KN7000 effects kernel): run the
	// interpreter's SHIFT_OPERATION_IMM() for this one instruction, round-tripping the flags.
```

**sharcdrc.cpp:282–285** (4 lines)

```c
// MODE1 ALUSAT tail for fixed-point ALU results (TRM B-6): expects the WRAPPED result
// in I8 and the captured overflow flag (0/1) in I9; writes dst, then clamps it to
// 0x7FFFFFFF / 0x80000000 when saturation mode is on and the op overflowed. Every
// interpreter compute_* fixed ALU op saturates, so every native DRC emission must too.
```

**sharcdrc.cpp:289–292** (4 lines)

```c
	// MODE1.ALUSAT is read at RUNTIME, like the interpreter does. Baking it in at
	// translation time would need every path that rewrites MODE1 to invalidate the
	// cache, and the status-stack pop does not -- nor could it usefully, since
	// cache_dirty is only examined once per timeslice.
```

**sharcdrc.cpp:3241–3244** (4 lines)

```c
									// Toggle each selected flag: the arithmetic flags live one-per-byte
									// in astat_drc, the FLG output bits in the packed astat. (Modelled on
									// the SET ASTAT case above; the KN7000 kernel toggles FLG1 as a
									// ping-pong bank flag in its main loop.)
```

**sharcdrc.cpp:3967–3972** (6 lines)

```c
	// Rather than abort, run this one compute op through the interpreter's COMPUTE(). This lets
	// the DRC compile blocks that contain compute ops it has no inline generator for (the SHARC
	// DRC never implemented the fixed-point multiplier / MAC family, which the KN7000 effects
	// kernel leans on) instead of forcing the whole device back to the interpreter. The register
	// file lives partly in fast host registers inside a block, so flush it to / from memory
	// around the call; compute_fallback handles the flag round-trip.
```

**sharcdrc.cpp:3982–3983** (2 lines)

```c
	// As generate_unimplemented_compute, but for immediate-shift ops with no inline generator:
	// run this one op through the interpreter's SHIFT_OPERATION_IMM() instead of aborting.
```

**sharcdrc.cpp:4085–4090** (6 lines)

```c
			// Fixed-point multiply / multiply-accumulate in parallel with an ALU add/sub/avg.
			// multiop groups as grp=(multiop>>2): 1=Rm=Rxm*Rym, 2=MRF+=Rxm*Rym, 3=Rm=MRF+Rxm*Rym,
			// 4=MRF-=Rxm*Rym, 5=Rm=MRF-Rxm*Rym; alu=(multiop&3): 0=add, 1=sub, 2=average. Native
			// emission (previously an interpreter fallback -- save/restore + C call per op -- in the
			// effect kernel's per-frame hot path). Mirrors the interpreter's compute_*.
			// Product aligned 1.63 (<<1); Rm = MR1 (63:32).
```

**sharcdrc.cpp:4107–4107** (1 lines)

```c
				// p = (Rxm * Rym) << 1   (64-bit signed product, in I0)
```

**sharcdrc.cpp:4112–4112** (1 lines)

```c
				// MR accumulate / register result
```

**sharcdrc.cpp:4121–4124** (4 lines)

```c
				// Multiplier flags: interpreter clears MN/MV/MU/MI and sets MN from Rm for the
				// register-destination groups (1,3,5); MRF-only groups (2,4) leave MN clear.
				// Gate each write on its liveness (as the rest of the DRC does) so dead flags cost
				// nothing, because a flag the frontend did not mark required is never read.
```

**sharcdrc.cpp:4138–4138** (1 lines)

```c
				// Parallel ALU
```

**sharcdrc.cpp:4166–4167** (2 lines)

```c
				// ALU flags: interpreter clears all ALU flags then sets AN/AZ from the final Ra.
				// Gated on liveness (dead flags unread -> WAV stays bit-identical).
```

**sharcdrc.cpp:4557–4563** (7 lines)

```c
						// The last hot single-function op the DRC left to the interpreter (the
						// 21065L effect microprograms use it for reverb/filter interpolation).
						// Mirrors compute_avg (sharcops.hxx): value = (Rx>>1)+(Ry>>1)+(Rx&Ry&1)
						// (overflow-free signed average == uint32((int64)(Rx+Ry) >> 1)); flags =
						// clear all, AC = carry-out of the 32-bit Rx+Ry, AV = 0 (an average cannot
						// overflow), AN/AZ from the result, AF/AS/AI cleared. Gated on liveness.
						// AC first (captured before the value adds clobber the host carry):
```

**sharcdrc.cpp:4596–4599** (4 lines)

```c
						// Mirrors interpreter compute_abs exactly: overflow only for
						// Rx == 0x80000000 (AV + sticky AOS, clamped to 0x7FFFFFFF in ALUSAT
						// mode); AS = sign of the INPUT, AZ/AN from the (possibly saturated)
						// result, AC/AI/AF cleared.
```

**sharcdrc.cpp:4607–4607** (1 lines)

```c
						// I0 = abs((int32)Rx):  I1 = Rx >> 31 (arithmetic);  I0 = (Rx ^ I1) - I1
```

**sharcdrc.cpp:4641–4641** (1 lines)

```c
						// See generate_fixed_alusat_tail: hardware saturates in ALUSAT mode.
```

**sharcdrc.cpp:4809–4820** (12 lines)

```c
						// Fixed-point Dual Add/Subtract. Both halves saturate under ALUSAT and
						// the flags are OR-merged across the two results. The add half's flags
						// are set before its saturation tail, so its AN/AZ are corrected for
						// the saturated value like every other site. The subtract half's are
						// merged into them first, so the same correction would rewrite the
						// merged value rather than the subtract's own contribution, and it is
						// left out: with ALUSAT set and the subtract saturating, AN can still
						// read the unsaturated sign -- Rx=0x7FFFFFFF, Ry=0xFFFFFFFF overflows
						// the subtract, and this reports AN=1 against the interpreter's 0.
						// AZ cannot diverge the same way: r_sub == 0 needs Rx == Ry, which
						// zeroes (Rx ^ Ry) and so av_sub. Closing the AN case needs the
						// correction applied before the merge.
```

**sharcdrc.cpp:5370–5377** (8 lines)

```c
				// Native single-function fixed-point multiplier / MAC, SIGNED x SIGNED forms
				// (0x70-0x7f = Rx*Ry, 0xb0-0xbf = MR + Rx*Ry, 0xf0-0xff = MR - Rx*Ry). This is the
				// Technics KN7000 effects kernel's hot path: without these it took ~66M
				// interpreter fallbacks per reverb run, since the existing native MAC covered
				// only the MULTI-function forms. Mirrors the interpreter's general fixed
				// multiplier (sharcops.hxx). Unsigned/mixed-sign and the RND (0x18-0x1F) forms
				// still fall back; the SAT family (0x00-0x0F) is native below. Op byte:
				//   [7:6] oper (1=Rx*Ry, 2=MR+, 3=MR-)  [5]xsgn [4]ysgn  [3]frac  [2]dest=MR  [1]MRB  [0]round
```

**sharcdrc.cpp:5385–5385** (1 lines)

```c
					// p = (int64)Rx * (int64)Ry ; frac aligns the product to 1.63 (<<1)
```

**sharcdrc.cpp:5394–5396** (3 lines)

```c
					// Multiplier flags, mirroring the interpreter's SET_FLAG_* bit for bit --
					// including their 64-bit-MR approximation, since MAME models MR without the
					// MR2 stage. Liveness-gated, so only the last definer in a sequence pays.
```

**sharcdrc.cpp:5398–5398** (1 lines)

```c
					// MV = the high half is neither 0 nor all-ones, i.e. uint32_t(high + 1) > 1.
```

**sharcdrc.cpp:5406–5406** (1 lines)

```c
					// MU = high half zero and low half non-zero.
```

**sharcdrc.cpp:5415–5415** (1 lines)

```c
					// MN is the sign of the delivered half -- bits 63:32 for fractional.
```

**sharcdrc.cpp:5429–5433** (5 lines)

```c
				// SAT MRx family (op 0x00-0x0F, TRM B-57): saturate the accumulator to the
				// destination format's range.  Mirrors the interpreter exactly: MR is modelled
				// as 64 bits (no MR2 stage), so only the integer forms can actually clamp --
				// the fractional forms pass MR through (the MAC path itself wraps at 64 bits).
				// Op byte: [3] fractional  [2] dest = MR  [1] MRB select  [0] signed.
```

**sharcdrc.cpp:5465–5467** (3 lines)

```c
					// TRM B-57 flags, mirroring the interpreter: MN = sign of the result in
					// its format (signed forms only), MV/MI cleared, MU = fractional underflow
					// only ("integer results do not underflow").  Gated on liveness.
```

**sharcdrc.cpp:5484–5484** (1 lines)

```c
							// MU = (bits 63:32 == 0) && (bits 31:0 != 0)  [SET_FLAG_MU]
```

**sharcdrc.cpp:5498–5498** (1 lines)

```c
						// fractional destination takes MR1 (bits 63:32), integer takes MR0
```

**sharcdrc.cpp:6117–6121** (5 lines)

```c
			// Mirrors the interpreter: Rn = sext(Rx, min(len,32)) << bit (0 when len == 0
			// or bit >= 32); SZ from the result, SV = (bit+len > 32), SS cleared.  This is
			// the LFO phase-accumulator wrap op in the chorus/flanger/phaser families.
			// Shift-by-zero is routed to flag-generating ops (AND/BFXS) so the requested
			// Z flag is always produced.
```

### `sharcfe.h` — 1 blocks, 2 lines

**sharcfe.h:311–312** (2 lines)

```c
	// Which 128 KiB page holds internal program memory: 0x20000 on the 2M/4M
	// parts, 0x8000 on the 21065L. The loop map is indexed by pc & 0x1ffff.
```

### `sharcops.hxx` — 10 blocks, 36 lines

**sharcops.hxx:731–736** (6 lines)

```c
/* Rn = (Rx + Ry) / 2   -- fixed-point average (ALU single-function op 0x09).
   This is the fixed-point twin of the floating-point FAVG (op 0x89) and is used
   heavily by the ADSP-21065L effect microprograms (reverb/filter interpolation),
   so leaving it unimplemented makes those effects compute nothing. Modelled as a
   signed 33-bit add shifted right one bit (so it cannot overflow -> AV always 0);
   the carry-out of the 32-bit adder sets AC, matching the hardware adder. */
```

**sharcops.hxx:745–745** (1 lines)

```c
	// AV stays clear: an average can never overflow the destination.
```

**sharcops.hxx:793–797** (5 lines)

```c
				// Fixed-point multiplier/MAC in parallel with an ALU add/sub/avg. The multiop
				// field groups as (multiop>>2): 1 = Rm=Rxm*Rym, 2 = MRF+=Rxm*Rym,
				// 3 = Rm=MRF+Rxm*Rym, 4 = MRF-=Rxm*Rym, 5 = Rm=MRF-Rxm*Rym; and (multiop&3):
				// 0 = add, 1 = sub, 2 = average. All signed fractional (product aligned to 1.63);
				// the Rm result takes MR1 (bits 63:32), matching compute_mul_ssfr_* above.
```

**sharcops.hxx:827–827** (1 lines)

```c
				// MODE1 ALUSAT: clamp on overflow, as compute_add/compute_sub do.
```

**sharcops.hxx:842–842** (1 lines)

```c
				/* Rm = Rxm*Rym (SSFR),  Ra = Rxa + Rya,  Rs = Rxa - Rya */
```

**sharcops.hxx:1002–1008** (7 lines)

```c
						// General fixed-point multiplier / MAC. The op byte decodes as:
						//   [7:6] operation: 1 = Rx*Ry, 2 = MR + Rx*Ry, 3 = MR - Rx*Ry
						//   [5]   Rx signed    [4] Ry signed
						//   [3]   fractional (result << 1)   [2] destination: 0 = Rn, 1 = MR
						//   [1]   MR select: 0 = MRF, 1 = MRB   [0] round-to-nearest
						// (The specific cases above are fast-paths for the same decode; op 0 =
						// clear/saturate/round forms are handled by their own cases / below.)
```

**sharcops.hxx:1012–1018** (7 lines)

```c
							// SAT MRx (op 0x00-0x0F, TRM B-57): saturate the accumulator to the
							// destination format's range.  Op byte: [3] fractional  [2] dest = MR
							// [1] MRB select  [0] signed (mod1, TRM Table B-5).  Our MR model is
							// 64-bit (no MR2 stage), so the fractional forms can never observe
							// overflow -- the MAC path itself wraps at 64 bits; only the integer
							// forms (32-bit destination range) can actually clamp here.
							// RND MRx (0x18-0x1F) remains unimplemented (unused by the KN7000 pool).
```

**sharcops.hxx:1042–1044** (3 lines)

```c
							// TRM B-57 flags: MN = sign of the result in its format (unsigned
							// results are never negative), MV/MI cleared, MU = fractional
							// underflow only ("integer results do not underflow").
```

**sharcops.hxx:1089–1091** (3 lines)

```c
						// MN is the sign of the DELIVERED value: the fractional forms hand
						// over MR1, bits 63:32. Upstream's own fractional multipliers pass
						// the already-shifted word to SET_FLAG_MN for the same reason.
```

**sharcops.hxx:1099–1100** (2 lines)

```c
							// Rn destination leaves MR unchanged; fractional takes MR1 (bits 63:32),
							// integer takes MR0 (bits 31:0).
```
