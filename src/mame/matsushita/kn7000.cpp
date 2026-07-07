// license:GPL2+
// copyright-holders:Felipe Sanches
/******************************************************************************

    Technics SX-KN7000 music keyboard driver

    ---------------------------------------------------------------------------
    WORK IN PROGRESS / DRAFT
    ---------------------------------------------------------------------------

    The SX-KN7000 (2002) is the successor of the SX-KN5000 (see kn5000.cpp).
    Unlike the KN5000 - which is driven by a pair of Toshiba TLCS-900
    (TMP94C241) CPUs - the KN7000 main board is built around a single Panasonic
    MN10300/AM33 CPU (little-endian, byte-aligned variable-length 1..7 byte
    instructions).

    As of this writing there is NO execution core for the MN10300/AM33 family in
    MAME: the only existing code is the disassembler at
    src/devices/cpu/mn10300/mn103dasm.cpp. This driver therefore instantiates a
    mn10300_device (declared in src/devices/cpu/mn10300/mn10300.h) whose
    execution core is itself a work in progress. Everything downstream of the
    CPU (peripherals, video, sound) is consequently guesswork and is marked with
    TODO where behavior is unknown.

    Models: besides the KN7000, this file hosts its MN10300/MILK siblings as drafts
    reusing this machine config - SX-KN6000, SX-KN6500, and the SX-KN2400/KN2600/PR54
    family (one shared firmware, runtime model selector). KN5000 is separate (kn5000.cpp).

    ROMs: each flash is modeled as its physical even/odd 16-bit chips, de-interleaved
    from the checksum-verified .SLD firmware-update images and loaded as good dumps
    (the .SLD/.INF block checksums verify the decompression); real chip dumps would
    supersede them. Per-model details live on the kn5000-docs site.

    Memory layout (from firmware static analysis, the mn10300_sim boot trace,
    and the service-test IC map; see the kn5000-docs "Technics KN7000" pages and
    this repo's notes/io-map.md + notes/library-rom-api.md). 112 individual I/O
    registers have been recovered; the banks and their apparent purpose:

        0x20000000  small register block (7 regs; reset writes 0x30/0x03 to
                                          0x20000070)
        0x32000000  system / timers (15 regs; 0x40/0x42 loaded 0x497/0xEA6 at
                                     reset; 0x800 is a 32-bit counter)
        0x34000000  LCD/display controller + key/panel scan (58 regs - the
                                     largest block; see Display subsystem doc)
        0x36008000  bit-mapped control / GPIO (8 regs, all bset/bclr/btst;
                                     0x36008004 toggled 125x = chip selects)
        0x48000000  Table / rhythm flash               (kn7000_table.rom, ~4 MB)
        0x48400000  Program flash                      (kn7000_program.rom, ~4 MB)
        0x4C000000  Library / kernel ROM (undumped, >= ~6 MB): the C runtime +
                                     MILK kernel; 7,965 calls to 298 entry points
                                     (printf @0x4C001A48, memcpy @0x4C003051, ...)
        0x50000000  Work RAM (>2.5 MB used; initial SP = 0x50021CF8)
        0x57800000  Picture flash (undumped; only lightly referenced)
        0x8C000000  device window / video path (boot copies ROM data here)
        0x90000000  framebuffer / LCD V-RAM window (IC104?)
        0x98040000  tone generator (synth LSI IC205, C1BB00000709) - 16-bit register set
        0x98050000  2nd TG register set (parallel 16-bit)
        0x9804/50004  VOICE-EVENT (keyboard) FIFO reads -- the KN5000-shared "keyboard
                     input" interface (KN5000 0x110000: 16-bit, low byte = note, high
                     byte = velocity; empty = 0xFFFF). This is how physical key presses
                     reach the firmware (parallel to MIDI-in); see notes/tone-generator.md.
                     wave/sample data in undumped ROMs IC203/204/207/208 (C3CBQD00000x)
        0x98020000  sound control (byte regs); 0x98060000/0x98070000 more sound

    Notable work-RAM globals recovered from the disassembly (constants below):
        0x50007578  LCD panel type (0=colour, 2=2-bit grayscale)
        0x5000757A  LCD mode
        0x5000757C  live UI object table (0x38-byte slots; +0x10 = current target)
        0x50122DB8  font descriptor table pointer (0x14-byte entries)
        0x50380004  currently-running task handle
        0x5038002C  main task handle
        0x500D3C5C / 0x500D3C60  per-task (AP / main) focused-object id

    Reset behavior: file offset 0 of the program flash (i.e. CPU address
    0x48400000) contains "jmp 0x4840FF7E", so the reset vector of the AM33 core
    is expected to land at the base of the program flash region. The boot then
    programs the GPIO/timer banks and enters the MILK kernel; mn10300_sim runs
    ~4.59 M instructions before it must call into the undumped 0x4C000000 ROM.

    Hardware blocks named in the service-test IC map (not yet emulated):
        - Program ROMs IC16 / IC17
        - Table / rhythm ROMs
        - Dual tone generators (main TG IC203/IC204, sub TG IC207/IC208)
        - DSP IC306 / IC307
        - Floppy Disk Controller IC103
        - LCD V-RAM IC104
        - Panel sub-CPUs: CPL / CPC / CPR / CPSD
        - SD card
        - USB

******************************************************************************/

#include "emu.h"

#include "cpu/mn10300/mn10300.h"

#include "bus/midi/midi.h"          // pulls in BUSES["MIDI"] for the focused build
#include "bus/midi/midiinport.h"
#include "bus/midi/midioutport.h"

#include "screen.h"

#include "kn7000.lh"


// ----------------------------------------------------------------------------
//  KN7000 SIO UART -- byte<->bit bridge between a byte-oriented SIO channel and
//  MAME's bit-serial midi_port. One instance per MIDI channel (31250 baud, 8N1).
//  Modelled on src/mame/misc/vocalizer.cpp's UART.
// ----------------------------------------------------------------------------
class kn7000_sio_uart_device : public device_t, public device_serial_interface
{
public:
	kn7000_sio_uart_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock = 0);

	auto tx_cb() { return m_tx_cb.bind(); }      // each TX bit -> midi_port write_txd
	auto rx_cb() { return m_rx_cb.bind(); }      // each fully-received byte -> driver

	void write(uint8_t data) { transmit_register_setup(data); }
	bool tx_empty() const { return is_transmit_register_empty(); }

protected:
	virtual void device_start() override {}
	virtual void device_reset() override ATTR_COLD;

	virtual void tra_callback() override { m_tx_cb(transmit_register_get_data_bit()); }
	virtual void rcv_complete() override { receive_register_extract(); m_rx_cb(get_received_char()); }

	devcb_write_line m_tx_cb;
	devcb_write8 m_rx_cb;
};

DEFINE_DEVICE_TYPE(KN7000_SIO_UART, kn7000_sio_uart_device, "kn7000_sio_uart", "KN7000 SIO MIDI UART")

kn7000_sio_uart_device::kn7000_sio_uart_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock) :
	device_t(mconfig, KN7000_SIO_UART, tag, owner, clock),
	device_serial_interface(mconfig, *this),
	m_tx_cb(*this),
	m_rx_cb(*this)
{
}

void kn7000_sio_uart_device::device_reset()
{
	set_data_frame(1, 8, PARITY_NONE, STOP_BITS_1);   // MIDI: 8N1
	set_rate(31250);                                  // MIDI baud
}


namespace {

class kn7000_state : public driver_device
{
public:
	kn7000_state(const machine_config &mconfig, device_type type, const char *tag)
		: driver_device(mconfig, type, tag)
		, m_maincpu(*this, "maincpu")
		, m_screen(*this, "screen")
		, m_workram(*this, "workram")
		, m_vram(*this, "vram")
		, m_lcdbuf(*this, "lcdbuf")
		, m_progrom(*this, "maincpu")
		, m_midi_uart(*this, "midi_uart%u", 0U)
		, m_seg(*this, "SEG%02X", 0U)
		, m_dial(*this, "DIAL")
		, m_cpl_leds(*this, "cpl_led%u", 0U)
		, m_cpc_leds(*this, "cpc_led%u", 0U)
		, m_cpr_leds(*this, "cpr_led%u", 0U)
	{ }

	void kn7000(machine_config &config) ATTR_COLD;
	void kn6000(machine_config &config) ATTR_COLD;
	DECLARE_INPUT_CHANGED_MEMBER(kbd_key);     // PC-key note -> voice-event FIFO (public: PORT_CHANGED_MEMBER)

protected:
	virtual void machine_start() override ATTR_COLD;
	virtual void machine_reset() override ATTR_COLD;

private:
	required_device<mn10300_device> m_maincpu;
	required_device<screen_device> m_screen;
	required_shared_ptr<uint32_t> m_workram;
	required_shared_ptr<uint32_t> m_vram;        // LCD V-RAM window at 0x90000000
	required_shared_ptr<uint32_t> m_lcdbuf;      // firmware's composited RGB565 LCD image @0x9CE00000
	bool m_lib_mirror = false;                   // KN6000/KN6500: library @0x4C/0x8C mirrors the program ROM
	required_region_ptr<uint32_t> m_progrom;     // program flash (holds the CLUT)
	required_device_array<kn7000_sio_uart_device, 2> m_midi_uart;

	template <int Ch> void midi_rx(uint8_t data) { sio_rx_push(Ch, data); }

	// Control panel button ports and LEDs (CPL = 8 cols, CPC = 5 cols; CPR + the
	// serial HLE device that reads these / drives the LEDs are still to come).
	required_ioport_array<0x21> m_seg;  // one per normalized segment 0x00-0x20
	required_ioport m_dial;
	output_finder<512> m_cpl_leds;
	output_finder<64> m_cpc_leds;
	output_finder<512> m_cpr_leds;

	void maincpu_mem(address_map &map) ATTR_COLD;

	// bring-up logging handlers for the (not-yet-decoded) I/O banks
	uint16_t io_r(offs_t offset, uint16_t mem_mask = ~0);
	void io_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);

	// --- On-chip interrupt controller (INTC) at 0x34000100 ------------------
	// GxICR(group) = 0x34000100 + group*4 (16-bit): bit0 DETECT, bit4 REQUEST,
	// bit8 ENABLE, bits12-14 LEVEL. 0x34000100/0x104 double as the IAGR the
	// (self-loaded) library dispatcher reads to find the pending group. A source
	// is pending when its REQUEST bit is set; the CPU maskable line is asserted
	// while any ENABLE&REQUEST source exists. See notes/interrupt-mechanism.md.
	enum { IRQGRP_TIMER = 0x06, IRQGRP_PANEL = 0x1A, IRQGRP_MIDI1 = 0x12, IRQGRP_MIDI2 = 0x14 };
	uint16_t intc_r(offs_t offset, uint16_t mem_mask = ~0);
	void intc_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	void intc_assert(int group);
	void intc_recompute();
	int  intc_pending_group() const;
	uint16_t m_gxicr[0x20] = { };
	IRQ_CALLBACK_MEMBER(irq_ack);              // latches IAGR (group+vector) at accept
	bool m_c11_unserviced = false;             // a panel transfer-complete not yet accepted
	int m_iagr_latch = 0;
	uint16_t m_intc_280 = 0;                   // 0x34000280 latched control fields
	uint16_t m_snd_500e = 0;                   // 0x9805000E readback latch (sound init spins on it)
	// Keyboard / voice-event FIFO (read at 0x98050004). The firmware polls it for
	// note events from the key bed (KN5000-shared "keyboard input"; 16-bit word,
	// low byte = note, high byte = velocity, velocity 0 = note-off; 0xFFFF = empty).
	uint16_t m_kbd_fifo[16] = { };
	uint8_t  m_kbd_head = 0, m_kbd_tail = 0;
	void kbd_push(uint8_t note, uint8_t vel)
	{ m_kbd_fifo[m_kbd_head & 15] = uint16_t(note) | (uint16_t(vel) << 8); m_kbd_head++; }
	// Tone generators (main 0x98040000 / sub 0x98050000): register-indirect,
	// write-only from the firmware. Address latched at base+0, data written at
	// base+2 -> reg[address]. Voice registers are group<<8|bank<<6|channel
	// (< 0x1000); the 0xFC0x system-refresh group is accepted but not stored.
	// See notes/tone-generator.md. (State capture; synthesis is future work.)
	uint16_t m_tg_addr[2] = { 0, 0 };          // latched register address, [0]=main [1]=sub
	uint16_t m_tg_reg[2][0x1000] = { };        // captured voice-register file
	emu_timer *m_sys_timer = nullptr;
	TIMER_CALLBACK_MEMBER(sys_tick);
	emu_timer *m_fav_timer = nullptr;      // one-shot: pre-load Favorites SRAM after the boot BSS-clear
	TIMER_CALLBACK_MEMBER(fav_preload);

	// --- SIO ASIC: three USART channels at 0x34000800 / 0x810 / 0x820 -------
	// ch0 = control panel, ch1 = MIDI port 1, ch2 = MIDI port 2 (see
	// notes/panel-serial-protocol.md). Per channel, at +0x10 stride:
	//   +0 config(16) · +4 control(8) · +8 TX-data(8) · +9 RX-data(8) · +C status(16)
	enum { SIO_PANEL = 0, SIO_MIDI1 = 1, SIO_MIDI2 = 2 };
	uint16_t sio_r(offs_t offset, uint16_t mem_mask = ~0);
	void sio_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	void sio_tx_byte(int ch, uint8_t data);
	void sio_rx_push(int ch, uint8_t data);
	bool sio_rx_ready(int ch) const { return m_sio_rx_head[ch] != m_sio_rx_tail[ch]; }
	uint8_t sio_rx_pop(int ch);

	uint16_t m_sio_config[3] = { 0, 0, 0 };
	uint8_t  m_sio_control[3] = { 0, 0, 0 };
	uint8_t  m_sio_rx_fifo[3][64] = { };   // small ring buffer per channel
	uint8_t  m_sio_rx_head[3] = { 0, 0, 0 };
	uint8_t  m_sio_rx_tail[3] = { 0, 0, 0 };

	// --- Control-panel HLE (the sub-CPU side of the panel serial link) ------
	// LED command bytes arrive as 2-byte [ADDR][DATA] frames on the panel TX;
	// each DATA bit is one LED of the register selected by ADDR. Buttons are
	// scanned from the ioports and reported back as 2-byte [ADDR][DATA] frames
	// on the panel RX (only delivered to the firmware once the MN10300 core
	// takes SIO interrupts -- see notes/panel-serial-protocol.md).
	TIMER_CALLBACK_MEMBER(panel_scan);
	void panel_led_frame(uint8_t addr, uint8_t data);
	uint8_t m_panel_resp[64] = { };        // pending panel->main bytes (replies + button events)
	void panel_queue(const uint8_t *bytes, int n);  // append + kick the ATN delivery
	int     m_panel_resp_len = 0, m_panel_resp_pos = 0;
	TIMER_CALLBACK_MEMBER(panel_event);    // deferred ATN edges / RX-byte delivery
	emu_timer *m_panel_evt = nullptr;      // one-shot; param: 1=ATN edge, 2=deliver RX byte
	emu_timer *m_panel_txdone = nullptr;   // one-shot: sync-transfer complete -> group 0x11
	emu_timer *m_panel_timer = nullptr;
	int     m_panel_pos = 0;               // position within the 7-byte TX frame
	uint8_t m_panel_p1 = 0, m_panel_p2 = 0; // frame payload bytes (positions 2 and 4)
	uint8_t m_btn_prev[0x21] = { }; // last scanned state, one per normSeg 0x00-0x20

	uint32_t screen_update(screen_device &screen, bitmap_rgb32 &bitmap, const rectangle &cliprect);
};


void kn7000_state::maincpu_mem(address_map &map)
{
	// The MN10300/AM33 has a flat 32-bit little-endian address space.

	// --- Table / rhythm flash -------------------------------------------
	// kn7000_table.rom, decompressed size 0x3E94D4 bytes (~4 MiB).
	map(0x48000000, 0x483fffff).rom().region("table", 0);

	// --- Program flash --------------------------------------------------
	// kn7000_program.rom, decompressed size 0x3F6F01 bytes (~4 MiB).
	// Held in program ROMs IC16 / IC17. CPU begins execution here
	// (0x48400000 -> "jmp 0x4840FF7E").
	map(0x48400000, 0x487fffff).rom().region("maincpu", 0);

	// --- Work RAM -------------------------------------------------------
	// The firmware sets the initial SP to 0x50021CF8 and, when single-stepped
	// through boot with the mn10300_sim interpreter, touches RAM past 0x50298000
	// (>2.5 MB), so the real work RAM (IC12/IC13) is larger than the ~1.5 MB BSS.
	// TODO: confirm the exact size; mapping 4 MB here as a working estimate.
	map(0x50000000, 0x503fffff).ram().share("workram");

	// --- Device windows found by executing the boot (mn10300_sim) -------
	// The boot code writes to 0x90000000 and 0x8C000000 (copying from the top of
	// the program ROM). Neither is in the static I/O map (notes/io-map.md); they
	// are almost certainly the LCD V-RAM / video / wave-DMA windows. Mapped as RAM
	// placeholders so bring-up can proceed past them.
	// TODO: identify the real devices (LCD V-RAM = IC104?).
	// KEY: the "library ROM" at 0x4C000000 is NOT a physical/undumped ROM. The
	// boot LOADS it at runtime from the program flash: InitializeBlock27
	// (0x484D7BBD) copies ~253 KB from program-ROM 0x487B8FD1.. into logical
	// 0x4C000000, but its copy loop adds 0x40000000 so the bytes actually land at
	// 0x8C000000 -- and the code later executes at the 0x4C000000 alias. Mapping
	// BOTH ranges to the same RAM lets the firmware populate its own library ROM,
	// so the boot runs real library code with no dump and no HLE. (Proven by
	// tracing the boot in mn10300_sim; see notes/library-rom-loading.md.)
	map(0x4c000000, 0x4cffffff).ram().share("libram");
	map(0x8c000000, 0x8cffffff).ram().share("libram");
	map(0x90000000, 0x97ffffff).ram().share("vram");   // LCD controller window (regs + trampolines)
	// NOTE: 0x96800000-0x969FFFFF within this range is actually the WRITABLE custom-data
	// FLASH (AMD 29LV160-class; unlock cmds to 0x9680AAAA/0x96805554), programmed by the
	// "Initial Data" disk (idd7000). Modeled here as blank RAM -> empty -> style names /
	// Favorites / Custom default. TODO: split out as a real flash device + load the
	// installed content. See notes/initial-data-disk-and-custom-flash.md.

	// Further windows the boot reaches only AFTER the library ROM loads and runs
	// (found by execution). 0x44000000 is a heavily read/written ~1 MB block
	// (RAM/buffer); 0x9C000000 holds an unidentified peripheral at 0x9CC00000.
	// Mapped as RAM placeholders so bring-up proceeds. TODO: identify these.
	// 0x44000000 and its +0x40000000 alias 0x84000000 are the same RAM (the same
	// one-bit window pair as the library ROM 0x4c/0x8c). Boot init copies record
	// arrays to 0x84030FF8..; without the alias those writes were dropped.
	map(0x44000000, 0x44ffffff).ram().share("ram44");
	map(0x84000000, 0x84ffffff).ram().share("ram44");
	map(0x9c000000, 0x9cffffff).ram().share("lcdbuf");   // firmware's composited LCD image (RGB565) lives at 0x9CE00000

	// --- Stubs for regions whose behavior is still unknown --------------
	// TODO: Library / boot ROM (undumped) at 0x4C000000. The firmware calls
	//       into it (e.g. a printf-like renderer at 0x4C001A48), so this is
	//       real code, not just data.
	//map(0x4c000000, 0x4c0fffff).rom().region("library", 0);

	// Data-flash READ views (byte-verified RE, notes/initial-data-disk-and-custom-flash.md):
	//   0x56000000 = the CUSTOM writable flash's read view (programmed by the "Initial Data"
	//                disk idd7000; command/program aperture is a SEPARATE window at 0x96800000,
	//                AMD unlocks 0x9680AAAA -- same 2MB 29LV160 chip). A u32-offset directory
	//                archive lives at flash-offset 0x200. THIS is where the custom-flash image
	//                must be ROM_LOADed once the AST install codec is reversed.
	//   0x57000000 = FACTORY read-only rhythm/style flash (extends the table ROM).
	// Both UNDUMPED; read-as-0 placeholders so boot-time pointer parsing is stable. Empty ->
	// style names / Custom fall back to defaults (the "8 Beat 1" bug).
	map(0x56000000, 0x577fffff).ram().share("dataflash");

	// TODO: Picture flash (splash / bitmap graphics), separate device.
	//map(0x57800000, 0x57ffffff).rom().region("picture", 0);

	// --- I/O register banks -------------------------------------------------
	// 112 I/O registers were recovered by static analysis of the firmware (see
	// notes/io-map.md for the per-register table). Mapped here to logging
	// handlers so every access is visible during bring-up; real device decode
	// (LCD, tone generators, panel, FDC, ...) comes later.
	//   0x20000000  small register block (reset writes 0x30/0x03 to 0x20000070)
	//   0x32000000  system / timers (0x40/0x42 = 0x497/0xEA6 at reset; 0x800 counter)
	//   0x34000000  large peripheral block, 58 regs (likely LCD/display + key/panel)
	//   0x36008000  bit-mapped control / GPIO (0x36008004 toggled 125x)
	//   0x98040000 & 0x98050000  parallel 16-bit sets = the DUAL tone generators
	//                            (main TG IC203/204 + sub TG IC207/208); plus
	//                            0x98020000/0x98060000/0x98070000 sound control
	map(0x20000000, 0x2000ffff).rw(FUNC(kn7000_state::io_r), FUNC(kn7000_state::io_w));
	map(0x32000000, 0x3200ffff).rw(FUNC(kn7000_state::io_r), FUNC(kn7000_state::io_w));
	map(0x34000000, 0x3400ffff).rw(FUNC(kn7000_state::io_r), FUNC(kn7000_state::io_w));
	// On-chip interrupt controller (GxICR array + IAGR) -- more-specific override.
	map(0x34000100, 0x340002ff).rw(FUNC(kn7000_state::intc_r), FUNC(kn7000_state::intc_w)); // GxICR block + the 0x34000200 scheduler-level group reg
	// The SIO ASIC (panel + two MIDI channels) is a decoded sub-block of the
	// 0x34000000 bank; this more-specific mapping overrides the logger above.
	map(0x34000800, 0x3400082f).rw(FUNC(kn7000_state::sio_r), FUNC(kn7000_state::sio_w));
	map(0x36008000, 0x360080ff).rw(FUNC(kn7000_state::io_r), FUNC(kn7000_state::io_w));
	// GPIO input port 0x36008084: bit 0 = panel-link ready/presence line, held
	// HIGH by the panel sub-CPUs. The TX state machine's state-1 handler tests it
	// (btst 0x01 at 0x484AC80C) and ABORTS the whole transaction back to state 0
	// if clear -- with a 0 stub no handshake command could ever be transmitted.
	map(0x36008084, 0x36008085).lr16(NAME([]() -> uint16_t { return 0x0001; }));
	map(0x98000000, 0x9807ffff).rw(FUNC(kn7000_state::io_r), FUNC(kn7000_state::io_w));

	// TODO: replace the logging handlers with real device models: LCD V-RAM
	//       (IC104), FDC (IC103), tone generators, DSP IC306/307, panel sub-CPUs
	//       (CPL/CPC/CPR/CPSD), SD card and USB blocks.
}


// Bring-up placeholder: log every I/O access and return 0. The CPU accesses
// these banks at 8/16/32-bit widths; a 16-bit handler with mem_mask lets MAME
// route all of them. One handler serves all five banks, so `offset` is relative
// to the mapped range -- shift left 1 for the byte offset within the bank. The
// decoded per-register list is in notes/io-map.md.
uint16_t kn7000_state::io_r(offs_t offset, uint16_t mem_mask)
{
	// 0x98070000 (offset 0x38000 within the 0x98000000 window): a status/strap word.
	// Boot init reads it and, if bit 15 is CLEAR, branches into a lengthy factory
	// power-on diagnostic (a battery of RAM/HW tests whose results are bit-banged
	// out on a panel GPIO with multi-second software delays -- not the normal boot
	// path). On real hardware bit 15 is set, so the diagnostic is skipped. Model
	// that here (guard at program-flash 0x484A4FDA: btst 0x8000,d0 / beq 0x484A4FE3).
	if (offset == 0x38000)
		return 0x8000;
	// 0x98050004 (offset 0x28002): the VOICE-EVENT / keyboard FIFO -- the interface
	// the KN5000 firmware calls "keyboard input" (KN5000 0x110000: read voice events,
	// low byte = note, high byte = velocity). The firmware polls it for note on/off
	// events from the physical key bed (parallel to MIDI-in). Boot init reads it in a
	// loop until it yields 0xFFFF (empty / end marker; also the floating-bus value).
	// Returning 0 made the loop treat 0 as a valid note-0 event forever. Return 0xFFFF
	// = empty so the loop terminates (loop at 0x484480A2: movhu (0x98050004); cmp
	// 0xffff; beq exit). Push note/velocity words via kbd_push() to play the key bed.
	if (offset == 0x28002)
	{
		if (!machine().side_effects_disabled() && m_kbd_head != m_kbd_tail)
			return m_kbd_fifo[m_kbd_tail++ & 15];
		return 0xFFFF;
	}
	// 0x9805000E (offset 0x28007): sound-interface register; the init loop at
	// 0x4854BC59 writes a value (d1|0x80) and spins until it READS BACK what it
	// wrote (setlb/lne with a 2-tick timeout) -- a readback latch unblocks it.
	if (offset == 0x28007)
		return m_snd_500e;
	if (!machine().side_effects_disabled())
		logerror("%s: io_r  +%06X mask %04X\n", machine().describe_context(),
			offset << 1, mem_mask);
	return 0;
}

void kn7000_state::io_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	if (offset == 0x28007)                        // 0x9805000E readback latch
	{
		COMBINE_DATA(&m_snd_500e);
		return;
	}
	// Tone-generator register-indirect write interface (write-only; see the
	// member declaration and notes/tone-generator.md). Modeling it here captures
	// the register file and keeps the constant TG traffic out of the io_w log.
	switch (offset)
	{
	case 0x20000: m_tg_addr[0] = data; return;                    // main TG: address latch (0x98040000)
	case 0x20001:                                                 // main TG: data (0x98040002) -> reg[addr]
		if (m_tg_addr[0] < 0x1000) m_tg_reg[0][m_tg_addr[0]] = data;
		return;
	case 0x28000: m_tg_addr[1] = data; return;                    // sub TG: address latch (0x98050000)
	case 0x28001:                                                 // sub TG: data (0x98050002) -> reg[addr]
		if (m_tg_addr[1] < 0x1000) m_tg_reg[1][m_tg_addr[1]] = data;
		return;
	case 0x20002: case 0x20008:                                   // main TG control (0x98040004 / 0x98040010)
		return;
	}
	logerror("%s: io_w  +%06X = %04X mask %04X\n", machine().describe_context(),
		offset << 1, data, mem_mask);
}


// ============================================================================
//  On-chip interrupt controller (INTC)
// ============================================================================
// The library-ROM interrupt handler (self-loaded, entry 0x4C03DDA0) reads the
// pending group from the IAGR at 0x34000100, indexes its handler table, and
// calls the registered ISR callback. offset is the 16-bit word index within
// 0x34000100; group = offset/2, register = 0x34000100 + group*4.

int kn7000_state::intc_pending_group() const
{
	// Among enabled+requested groups, the winner is the highest-priority one =
	// the LOWEST ICR LEVEL value (bits 14:12). Firmware programs: SIO panel/MIDI
	// groups 0x12-0x15 LEVEL=1, 0x0F/0x19 LEVEL=3, group 7 LEVEL=4, and the
	// system tick (group 6) LEVEL=6 -- the lowest priority in the system.
	int best = 0, best_level = 8;
	for (int g = 2; g < 0x20; g++)
		if ((m_gxicr[g] & 0x0110) == 0x0110)   // ENABLE(0x100) & REQUEST(0x10)
		{
			const int level = (m_gxicr[g] >> 12) & 7;
			if (level < best_level) { best_level = level; best = g; }
		}
	return best;
}

// Freeze the arbitration result (group AND vector, atomically) at the instant
// the CPU accepts the interrupt -- the real INTC latches IAGR at acknowledge.
IRQ_CALLBACK_MEMBER(kn7000_state::irq_ack)
{
	const int g = intc_pending_group();
	if (g)
	{
		m_iagr_latch = g;
		if (g == 0x11)
			m_c11_unserviced = false;
		const int level = (m_gxicr[g] >> 12) & 7;
		m_maincpu->set_irq_vector(level == 6 ? 0x4C03DE26 : 0x4C03DDA0);
		m_maincpu->set_irq_level(level);
	}
	return 0;
}

uint16_t kn7000_state::intc_r(offs_t offset, uint16_t mem_mask)
{
	const int reg = offset << 1;                  // byte offset within 0x34000100
	if (reg == 0x00)                              // IAGR: the group latched at interrupt accept
		return m_iagr_latch << 3;
	if (reg == 0x04)
		return 0;
	if (reg == 0x100)                             // 0x34000200: level-6 group register (latched at accept)
		return m_iagr_latch << 2;
	if (reg == 0x180)                             // 0x34000280: per-source 2-bit control fields (latched)
		return m_intc_280;                        // firmware only ever RMWs it (|0xC0 panel, |0x0C00 sound,
		                                          // &0xFF3F|0x80 post-ping) -- state must accumulate
	const int group = reg >> 2;                   // GxICR(group) at +group*4
	if (group < 0x20)
		return m_gxicr[group];
	return 0;
}

void kn7000_state::intc_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	const int reg = offset << 1;
	// The panel transfer-complete (group 0x11) is level-like until serviced: the
	// firmware's ISR-exit ack (full-word 0x0101 at 0x484AC736) w1c-clears DETECT,
	// and on real hardware the NEXT byte's completion always arrives after that
	// ack (the serial shift is slower than the ISR exit). If our deferred
	// completion landed before the ack (and was thus wiped un-serviced),
	// re-deliver it after the ack.
	if (reg == 0x44 && m_c11_unserviced && (data & mem_mask & 0x000f))
		m_panel_txdone->adjust(attotime::from_usec(40), 3);
	if (reg == 0x180)                             // 0x34000280 = EXTMD (ext-int trigger modes)
	{
		const uint16_t prev = m_intc_280;
		COMBINE_DATA(&m_intc_280);
		// Panel ATN pulse, edge 2: the group-0x1A ISR's pass 1 re-arms the pin
		// for the opposite edge (bits 7:6: 11b -> 10b) and expects the second
		// edge of the panel's attention pulse to arrive after it returns.
		// Deferred via timer: pass 1 runs with IE clear and acks its DETECT on
		// exit, so a synchronous assert here would be wiped.
		if (((prev & 0x00c0) == 0x00c0) && ((m_intc_280 & 0x00c0) == 0x0080))
			m_panel_evt->adjust(attotime::from_usec(60), 1);
		return;
	}
	if (reg < 0x08)
		return;                                   // IAGR is read-only
	const int group = reg >> 2;
	if (group >= 0x20)
		return;
	// GxICR write semantics (matches the on-chip INTC, and required for correct
	// delivery): the high byte (ENABLE + LEVEL) is stored as written; the DETECT
	// flags (bits 0-3) are WRITE-1-TO-CLEAR; REQUEST (0x10) is hardware status
	// derived from the surviving DETECT bits. A plain latched write here would
	// let the firmware's enable write (e.g. 0x0100) silently destroy a pending
	// request that arrived between 'clear' and 'enable' -- observed in the panel
	// handshake, where the reply's REQUEST was wiped by the subsequent enable.
	{
		const uint16_t cur = m_gxicr[group];
		const uint16_t nv  = (cur & ~mem_mask) | (data & mem_mask);
		// w1c applies ONLY to detect bits the access actually wrote (mem_mask):
		// the firmware's control-byte writes (movbu to +1, mask 0xFF00) must not
		// touch pending DETECT flags.
		uint16_t detect = (cur & 0x000f) & ~(data & mem_mask & 0x000f);
		m_gxicr[group] = (nv & 0xff00) | detect | (detect ? 0x0010 : 0x0000);
	}
	intc_recompute();
}

void kn7000_state::intc_assert(int group)
{

	m_gxicr[group] |= 0x0011;
	// (REQUEST + DETECT bit0 were just set above; the scheduler-level dispatcher at 0x4C03DE72 scans the DETECT bits 0-3 to pick the sub-source within the group)
	intc_recompute();
}

void kn7000_state::intc_recompute()
{
	// The AM33 dispatches each interrupt LEVEL through its own vector, and the
	// firmware installs two distinct handlers:
	//  - 0x4C03DDA0: quick dispatch (no stack switch) -- used by the high-
	//    priority device levels (reads IAGR at 0x34000100).
	//  - 0x4C03DE26: the SCHEDULER entry -- outermost entry saves the interrupted
	//    task's SP into its TCB (*0x5038002C), switches to the scheduler stack
	//    (*0x50380CBC), dispatches (reads the group register at 0x34000200), and
	//    on exit reloads SP from the (possibly re-chosen) current TCB. Only the
	//    system tick (group 6, LEVEL=6, the lowest priority) uses this one.
	// Routing the tick to the quick handler instead desynchronizes the TCB
	// saved-SPs from reality (the scheduler moves *0x5038002C but nothing
	// switches stacks), which corrupts the next yield -- so the vector must be
	// selected per pending level.
	const int g = intc_pending_group();
	if (g)
	{
		const int level = (m_gxicr[g] >> 12) & 7;
		m_maincpu->set_irq_vector(level == 6 ? 0x4C03DE26 : 0x4C03DDA0);
		m_maincpu->set_irq_level(level);
	}
	m_maincpu->set_input_line(0, g ? ASSERT_LINE : CLEAR_LINE);
}

TIMER_CALLBACK_MEMBER(kn7000_state::sys_tick)
{
	intc_assert(IRQGRP_TIMER);
}

// One-shot (t=3s, after the boot BSS-clear): install the factory "Initial Data"
// Favorites into battery-backed SRAM so the Favorites screen lists the 4 presets
// without the (still-unreversed) custom-flash AST install. The firmware VALIDATES this
// block against a 16-byte magic ("KN7000 SDDIR INF" @0x50083D72; check at 0x4855EC0B)
// rather than clearing it, so once present the firmware keeps it. The Favorites LIST
// only needs the 16-char names; the 9 u16 recall-items per record need flash-backed
// reference resolution, so they stay 0 (a CUSTOM favorite can't be recalled until the
// flash is modeled). Data = idd7000 03FAVINI.FAV; layout verified by RE (name-setter
// 0x48561CDB, item-setter 0x48561D8E, format 0x4855EC34). STOPGAP for the unmodeled
// battery SRAM; see notes/initial-data-disk-and-custom-flash.md.
TIMER_CALLBACK_MEMBER(kn7000_state::fav_preload)
{
	auto poke8 = [&](offs_t cpu, uint8_t b)
	{
		const offs_t o = cpu - 0x50000000;                 // byte offset into workram
		uint32_t &w = m_workram[o >> 2];
		const unsigned sh = 8 * (o & 3);
		w = (w & ~(0xffu << sh)) | (uint32_t(b) << sh);
	};
	static const char magic[16] =
		{ 'K','N','7','0','0','0',' ','S','D','D','I','R',' ','I','N','F' };
	for (int i = 0; i < 16; i++)
		poke8(0x50083D72 + i, uint8_t(magic[i]));           // block magic @+0x00
	static const char *const fav[4] = {                     // directory @0x5008FDCA, 34-byte records
		"    Example     ", " Cool Sounds !  ", " Cool Rhythms ! ", "  Entertainer   " };
	for (int r = 0; r < 4; r++)
		for (int i = 0; i < 16; i++)
			poke8(0x5008FDCA + r * 34 + i, uint8_t(fav[r][i]));  // name[16]; items[9] left 0
}

// A PC-key note press/release: push a voice-event into the keyboard FIFO the
// firmware polls at 0x98050004 (KN5000-shared format: low=note, high=velocity,
// velocity 0 = note-off). param carries the MIDI note number; velocity is fixed
// (PC keys are not velocity-sensitive). Confirmed end-to-end: the firmware reads
// each pushed event exactly once from the FIFO.
INPUT_CHANGED_MEMBER(kn7000_state::kbd_key)
{
	kbd_push(uint8_t(param), newval ? 0x64 : 0x00);
}


// ============================================================================
//  SIO ASIC -- three USART channels (panel + two MIDI ports)
// ============================================================================
//
// The handlers are 16-bit (as the whole 0x34000000 bank is); `offset` is the
// 16-bit-word index within 0x34000800. Each channel spans 0x10 bytes = 8 words,
// so channel = offset / 8 and the byte within the channel is (offset << 1) & 0xf.
// Byte registers (control @+4, TX @+8, RX @+9) are reached with movbu, i.e. a
// masked 16-bit access: TX is the low byte of word 4, RX the high byte.

uint16_t kn7000_state::sio_r(offs_t offset, uint16_t mem_mask)
{
	const int ch = offset / 8;
	const int reg = (offset << 1) & 0x0f;
	switch (reg)
	{
	case 0x0:                    // config
		return m_sio_config[ch];
	case 0x4:                    // control (byte @+4)
		return m_sio_control[ch];
	case 0x8:                    // +8 TX (write-only) / +9 RX (read, high byte)
		if (ACCESSING_BITS_8_15)
			return uint16_t(sio_rx_pop(ch)) << 8;
		return 0;
	case 0xc:                    // status: bit4 = RxRDY, bits0-2 = rx errors (none)
		return sio_rx_ready(ch) ? 0x0010 : 0x0000;
	}
	return 0;
}

void kn7000_state::sio_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	const int ch = offset / 8;
	const int reg = (offset << 1) & 0x0f;
	switch (reg)
	{
	case 0x0:                    // config
		COMBINE_DATA(&m_sio_config[ch]);
		// Bit 15 = transfer START on the synchronous panel link: the firmware
		// sets it to clock one byte and then polls the register until the
		// hardware self-clears it on completion. The HLE completes transfers
		// instantly. In the RX direction (mode field low3 = 7) the panel
		// sub-CPU supplies the next response byte of its pending reply.
		if (ch == SIO_PANEL && (m_sio_config[ch] & 0x8000))
		{
			m_sio_config[ch] &= 0x7fff;
			// Bit15 = start/busy for the boot's POLLED bit-bang path only; it just
			// self-clears here. The per-byte transfer trigger is the DATA write
			// itself: state-2 (0x484AC8D2) and later payload states write data with
			// NO bit15 write at all -- an armed/pending model makes each such
			// transfer complete only on the NEXT retry's arm, advancing the state
			// machine one step per retry (the observed parking). Completion is
			// modeled per data write in sio_tx_byte.
		}
		// RX enable (bit14, set by the group-0x1A ISR's pass 2 together with mode
		// low3=7 and state:=8): the panel now sends its queued reply, one byte per
		// group-0x10 interrupt (the state-8 handler reads 0x34000809 into the ring
		// at 0x5006BDB4 and bumps the head that the handshake success test checks).
		if (ch == SIO_PANEL && (m_sio_config[ch] & 0x4000) && m_panel_resp_pos < m_panel_resp_len)
			m_panel_evt->adjust(attotime::from_usec(60), 2);
		break;
	case 0x4:                    // control (byte @+4)
		if (ACCESSING_BITS_0_7)
			m_sio_control[ch] = data & 0xff;
		break;
	case 0x8:                    // TX data (byte @+8 = low byte)
		if (ACCESSING_BITS_0_7)
			sio_tx_byte(ch, data & 0xff);
		break;
	default:
		break;
	}
}

void kn7000_state::sio_rx_push(int ch, uint8_t data)
{
	const uint8_t next = (m_sio_rx_head[ch] + 1) % std::size(m_sio_rx_fifo[ch]);
	if (next == m_sio_rx_tail[ch])
		return;                  // FIFO full -- drop (overrun)
	m_sio_rx_fifo[ch][m_sio_rx_head[ch]] = data;
	m_sio_rx_head[ch] = next;
	// Deliver the byte: assert the channel's RX interrupt group (ICRs: panel RX
	// 0x34000168 -> group 0x1A, MIDI-1 RX 0x34000148 -> 0x12, MIDI-2 RX
	// 0x34000150 -> 0x14; see notes/panel-serial-protocol.md #6). The firmware's
	// RX ISR reads +0x09 and acks its GxICR; polling paths see RxRDY regardless.
	static constexpr int rx_group[3] = { 0x1a, 0x12, 0x14 };
	if (ch != SIO_PANEL)                          // panel: the sync-transfer-complete
		intc_assert(rx_group[ch]);                // assert in sio_w covers group 0x1A

}

uint8_t kn7000_state::sio_rx_pop(int ch)
{
	if (m_sio_rx_head[ch] == m_sio_rx_tail[ch])
		return 0;
	const uint8_t v = m_sio_rx_fifo[ch][m_sio_rx_tail[ch]];
	if (!machine().side_effects_disabled())
		m_sio_rx_tail[ch] = (m_sio_rx_tail[ch] + 1) % std::size(m_sio_rx_fifo[ch]);
	return v;
}

void kn7000_state::sio_tx_byte(int ch, uint8_t data)
{
	switch (ch)
	{
	case SIO_PANEL:
		// Every data write clocks one sync transfer. Completion -> group 0x11 --
		// ALWAYS deferred (an ISR-context write + synchronous assert is wiped by
		// the exit ack). Safe with IAGR latched at accept.
		m_panel_txdone->adjust(attotime::from_usec(40), 3);
		// The main CPU transmits 7-byte FRAMES with interleaved line syncs:
		//   pos 0 sync, 1 sync, 2 PAYLOAD1, 3 sync, 4 PAYLOAD2, 5 sync, 6 sync
		// (TX sites: sender 0x484AC5E9; states 1..6 at 0x484AC7FA / 0x484AC8D3 /
		// 0x484AC977 / 0x484AC9FF / 0x484ACA96 / 0x484ACAEA). Parse by position.
		switch (m_panel_pos)
		{
		case 2: m_panel_p1 = data; break;
		case 4: m_panel_p2 = data; break;
		}
		if (++m_panel_pos >= 7)
		{
			m_panel_pos = 0;
			// Frame complete. Handshake commands (payload1 = 0x1F/0x1D/0x1E init,
			// 0x20/0xE0 ping CPL/CPR, 0x29/0xDD -- the boot's observed sequence)
			// are answered with a TYPE-3 sync packet and an ATN pulse on the
			// panel's external-interrupt pin (group 0x1A, EXTMD bits 7:6). All
			// other frames carry LED-register updates [addr][data].
			switch (m_panel_p1)
			{
			case 0x1f: case 0x1d: case 0x1e: case 0x20: case 0xe0: case 0x29: case 0xdd:
			{
				// TYPE-3 sync reply; delivery via the ATN pulse (edge 2 rides the
				// EXTMD 11b->10b re-arm; bytes deliver one per group-0x10
				// interrupt once the ISR's pass 2 sets RX enable).
				static constexpr uint8_t sync_reply[2] = { 0x18, 0x00 };
				panel_queue(sync_reply, 2);
				break;
			}
			case 0x00:
				break;                     // idle/padding frame
			default:
				panel_led_frame(m_panel_p1, m_panel_p2);
				break;
			}
		}
		break;
	case SIO_MIDI1:
	case SIO_MIDI2:
		// Serialize the byte out through the channel's UART to its MIDI OUT port.
		m_midi_uart[ch - SIO_MIDI1]->write(data);
		break;
	}
}

// One decoded LED-command frame: ADDR selects an 8-LED register on one of the
// panel boards, DATA is that register's 8 LED bits. The board is chosen by the
// bank field in ADDR bits 6-7; the register index is ADDR bits 0-5. This mirrors
// the firmware's LED shadow layout (notes/panel-serial-protocol.md).
// TODO: the exact ADDR->(board,physical LED) table still needs cross-checking
// against the schematic silk-screen; the structural decode below is provisional.
void kn7000_state::panel_led_frame(uint8_t addr, uint8_t data)
{
	// addr = panel(bits 7:6; 0x00=right/CPR, 0xC0/0xE0=left/CPL) | reg(bits 5:0).
	// Each data bit is one LED of register `reg`. Index reg*8+bit within the bank.
	// (Provisional: reg<->physical-LED map is derived in notes/panel-leds.md but
	// not yet bound in the layout; both banks are wired for when it is.)
	const int reg = addr & 0x3f;
	const bool left = (addr & 0xc0) != 0;
	for (int bit = 0; bit < 8; bit++)
	{
		const int led = reg * 8 + bit;
		const int on = BIT(data, bit);
		if (led < 512) { if (left) m_cpl_leds[led] = on; else m_cpr_leds[led] = on; }
	}
	logerror("%s: panel LED frame addr=%02X data=%02X\n",
		machine().describe_context(), addr, data);
}

// Queue panel->main bytes (a handshake reply or a button-event packet) and start
// the delivery dance if idle: the panel pulses its ATN line (group 0x1A); the
// firmware's ISR switches the link to RX and clocks the bytes in one group-0x10
// interrupt at a time (state-8 handler -> the 92-byte ring -> the frame decoder).
void kn7000_state::panel_queue(const uint8_t *bytes, int n)
{
	if (m_panel_resp_pos == m_panel_resp_len)
		m_panel_resp_pos = m_panel_resp_len = 0;          // queue fully drained: reset
	if (m_panel_resp_len + n > int(sizeof(m_panel_resp)))
		return;                                           // overflow: drop (panel would too)
	const bool was_idle = (m_panel_resp_pos == m_panel_resp_len);
	for (int i = 0; i < n; i++)
		m_panel_resp[m_panel_resp_len++] = bytes[i];
	if (was_idle)
		m_panel_evt->adjust(attotime::from_usec(60), 1);  // ATN edge 1
}

// Deferred panel events (one-shot; scheduled from ISR-context register writes so
// the interrupt lands after the firmware's current handler returns):
//  param 1: ATN edge on the panel's external-interrupt pin -> group 0x1A.
//  param 2: the panel places its next reply byte on SIO0 -> group 0x10; the
//           state-8 handler reads it from +9 and stores it into the RX ring.
TIMER_CALLBACK_MEMBER(kn7000_state::panel_event)
{
	if (param == 1)
		intc_assert(0x1a);
	else if (param == 3)
	{
		m_c11_unserviced = true;
		intc_assert(0x11);                 // sync-transfer complete
	}
	else if (param == 2 && m_panel_resp_pos < m_panel_resp_len)
	{
		sio_rx_push(SIO_PANEL, m_panel_resp[m_panel_resp_pos++]);
		intc_assert(0x10);
		if (m_panel_resp_pos < m_panel_resp_len)
			m_panel_evt->adjust(attotime::from_usec(120), 2);   // next byte
	}
}

// Periodic button scan: read each declared segment ioport, and for any that
// changed since last scan, queue a 2-byte [ADDR][DATA] switch-report frame onto
// the panel RX. DATA bit = 1 means pressed (active-high on the wire); the frame
// is the same format the real sub-CPUs emit (notes/panel-serial-protocol.md,
// e.g. START/STOP press = C0 10). Delivery to the firmware WORKS via the ATN/SIO
// handshake in panel_queue -- VERIFIED: a held DEMO (SEG06 0x40) press enters demo
// mode. NB a press must be HELD across scans (>~1 frame); a single-frame Lua tap can
// be cleared by the input frame-update before this 250 Hz scan samples it.
TIMER_CALLBACK_MEMBER(kn7000_state::panel_scan)
{
	// Inputs are declared one ioport per NORMALIZED SEGMENT (SEG00..SEG15), the
	// identity the firmware's button dispatcher (0x484ADB59) uses. For a changed
	// segment we emit its 2-byte [ADDR][DATA] switch frame, computing the wire
	// ADDR by REVERSE-normalizing (the inverse of table 0x486135A0):
	//   normSeg 0x00-0x0B -> ADDR 0xC0-0xCB (grp3), 0x0C-0x15 -> 0x00-0x09 (grp0),
	//   0x16-0x19 -> 0xD0-0xD3, 0x1A -> 0x10, 0x20 -> 0x17. normSeg 0x1B-0x1F have NO
	//   wire path (not panel-serial buttons). DATA = segment bitmask (bit=1 pressed);
	//   the main CPU XORs vs its shadow for press/release edges.
	// Delivery rides the ATN dance via panel_queue (a bare fifo push never IRQs).
	static const uint8_t seg_to_addr[0x21] = {
		0xc0,0xc1,0xc2,0xc3,0xc4,0xc5,0xc6,0xc7,0xc8,0xc9,0xca,0xcb, // normSeg 0x00-0x0B
		0x00,0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08,0x09,           // normSeg 0x0C-0x15
		0xd0,0xd1,0xd2,0xd3,0x10,0xff,0xff,0xff,0xff,0xff,0x17,       // normSeg 0x16-0x20
	};
	for (int seg = 0; seg < 0x21; seg++)
	{
		const uint8_t addr = seg_to_addr[seg];
		if (addr == 0xff)   // normSeg 0x1B-0x1F: no wire path
			continue;
		const uint8_t cur = m_seg[seg]->read();
		if (cur == m_btn_prev[seg])
			continue;
		m_btn_prev[seg] = cur;
		const uint8_t pkt[2] = { addr, cur };
		panel_queue(pkt, 2);
	}
}


// --- Control-panel buttons and LEDs -----------------------------------------
// Like the KN5000, the KN7000 front panel is driven by dedicated panel sub-CPUs
// -- one per panel PCB -- that scan the button matrices and drive the LEDs, and
// talk to the main MN10300 over a synchronous serial link. Confirmed from the
// service manual schematics (SX-KN7000, SCHEMATIC DIAGRAM-15..18):
//
//   * CPL P.C.B. (page 128, "CPL CIRCUIT"): sub-CPU IC1101 = C0BDB646823
//     (8-bit microcomputer, xtal X1101). Scans an 8x8 switch matrix
//     (strobes SW0..SW7 x columns SEG0..SEG7) and drives an LED matrix through
//     IC1102 (HD74LS138 3-to-8 decoder) + transistor rows + buffers IC1103.
//     Serial link pins: SIN, SOUT, CLK, RST, CNTR1 -> to the CPR board / main.
//   * CPC (centre), CPR (right) and CPSD boards: same design (pages 130-133).
//
// On the main-CPU side the link is ONE channel of a multi-channel USART/SIO ASIC
// mapped at 0x34000800 (config 0x800, control 0x804, TX-data 0x808, RX-data 0x809,
// status 0x80C; interrupt via ICR 0x34000168). It is INTERRUPT-DRIVEN, half-duplex:
// the RX ISR (0x484ACC13) reads one byte from 0x34000809 into a 92-byte ring buffer
// (0x5006BDB4), a frame decoder (0x484AD111) parses a header byte whose bits[5:3]
// are a 3-bit message type, and a switch-byte dispatcher (0x484AD680) indexes a
// 32-entry jump table (0x48613108) = the four panel groups CPL/CPC/CPR/CPSD. LED
// bytes go OUT on the SAME channel (TX path 0x484ABF50 -> 0x34000808). GPIO lines
// 0x36008004/24/64 strobe/select the sub-CPUs. NOTE: the sibling SIO channels at
// 0x34000810 and 0x34000820 are the two MIDI ports, NOT panel. See notes/io-map.md
// and the kn5000-docs Control Panel Protocol page.
//
// The button names below are transcribed from the CPL schematic; the exact
// SW-row within each SEG column should be double-checked against the print. Only
// CPL is filled in so far (pages 130-133 will populate CPC/CPR/CPSD). A proper
// serial-protocol HLE device (as in kn5000_cpanel.cpp) is still to be written.

static INPUT_PORTS_START(kn7000)
	// Panel buttons organized by NORMALIZED SEGMENT (normSeg), the identity the
	// firmware's button dispatcher (0x484ADB59) actually uses. panel_scan emits
	// each segment's reverse-normalized wire address (bank11 subs 0-0xB -> segs
	// 0x00-0x0B; bank00 subs 0-9 -> segs 0x0C-0x15). Names for segs 0x00-0x07 are
	// the transcribed CPL panel labels (verified: START/STOP etc.); names for
	// 0x08-0x15 are derived from each button's firmware event code + arg (see
	// notes/panel-button-map.md) -- honest and traceable, refined as arg->genre
	// and arg->sound-group tables are decoded.
	PORT_START("SEG00")   // normSeg 0x00 -- CPL transport/style
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PAD 1")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PAD 4")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM 8&16 BEAT")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM ROCK & POP")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM BALLAD")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM JAZZ & SWING")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM BALLROOM")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM MOVIE & SHOW")

	PORT_START("SEG01")   // normSeg 0x01 -- CPL transport/style
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PAD 2")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PAD 5")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM ENTERTAINER")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM ORGANIST")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM 60s & 70s")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM MODERN DANCE")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM SOUL & R&B")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM COUNTRY & WESTERN")

	PORT_START("SEG02")   // normSeg 0x02 -- CPL transport/style
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PAD 3")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PAD 6")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM MARCH & WALTZ")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM LATIN & WORLD")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM CUSTOM")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM COMPOSER MEMORY")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND ARRANGER SET")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND ARRANGER OFF/ON")

	PORT_START("SEG03")   // normSeg 0x03 -- CPL transport/style
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("INTRO & ENDING 1")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("APC / CHORD FINDER")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("AUTO PLAY CHORD OFF/ON")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD LEFT 1 (RIGHT1 part OFF)")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD LEFT 2 (RIGHT2 part OFF)")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD LEFT 3 (LEFT part OFF)")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD LEFT 4 (ACCOMP1 part OFF)")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD LEFT 5 (ACCOMP2 part OFF)")

	PORT_START("SEG04")   // normSeg 0x04 -- CPL transport/style
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 1 ON")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 1 OFF")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 2 ON")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 2 OFF")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 3 ON")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 3 OFF")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 4 ON")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 4 OFF")

	PORT_START("SEG05")   // normSeg 0x05 -- CPL transport/style
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 5 ON")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 5 OFF")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 6 ON")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 6 OFF")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 7 ON")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 7 OFF")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 8 ON")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 8 OFF")

	PORT_START("SEG06")   // normSeg 0x06 -- CPL transport/style
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 9 ON")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 9 OFF")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 10 ON")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 10 OFF")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 11 ON")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 11 OFF")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 12 ON")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 12 OFF")

	PORT_START("SEG07")   // normSeg 0x07 -- CPL transport/style
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 13 ON")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 13 OFF")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 14 ON")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 14 OFF")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 15 ON")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 15 OFF")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 16 ON")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE PART 16 OFF")

	PORT_START("SEG08")   // normSeg 0x08 -- part mixer mutes
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("part18 ON")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("part18 OFF")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("OTHER PARTS & FR")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("HELP")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("DISPLAY HOLD")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("EXIT")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND CONTROLLER MODE")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND CONTROLLER RESET")

	PORT_START("SEG09")   // normSeg 0x09 -- part mixer mutes
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PADS BANK")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PADS STOP")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PADS AUTO SETTING")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUSIC STYLE ARRANGER")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("VARIATION & MSA")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("VARIATION & MSA")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("DEMO")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Part Mute Down p09")

	PORT_START("SEG0A")   // normSeg 0x0A -- part mixer mutes
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Part Mute Up p0A")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Part Mute Down p0A")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Part Mute Up p0B")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Part Mute Down p0B")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Part Mute Up p0C")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Part Mute Down p0C")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Part Mute Up p0D")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Part Mute Down p0D")

	PORT_START("SEG0B")   // normSeg 0x0B -- part mixer mutes
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Part Mute Up p0E")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Part Mute Down p0E")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Part Mute Up p0F")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Part Mute Down p0F")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Part Mute Up p18")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Part Mute Down p18")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Fn Key 20A0")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Part Mute Up p17")

	PORT_START("SEG0C")   // normSeg 0x0C -- sound / right panel
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND PIANO")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND GUITAR")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND MALLET&ORCH PERC")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND WORLD")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND STRINGS & VOCAL")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND BRASS")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Fn Toggle 0B")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_UNUSED)

	PORT_START("SEG0D")   // normSeg 0x0D -- sound / right panel
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND SAX & WOODWIND")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND ORGAN&ACCORDION")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND SOUND EXPLORER")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND DIGITAL DRAWBAR")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND ORGAN TABS")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND ACCORD REGISTER")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Fn 2016")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Fn Toggle 0A")

	PORT_START("SEG0E")   // normSeg 0x0E -- sound / right panel
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND PAD")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND SYNTH")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND BASS")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND DRUM KITS")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SUSTAIN")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("DIGITAL EFFECT")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Fn Key 20AE")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_UNUSED)

	PORT_START("SEG0F")   // normSeg 0x0F -- sound / right panel
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND DSP")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND DSP VARIATION")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD RIGHT 1 (RIGHT1 part ON)")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD RIGHT 2 (RIGHT2 part ON)")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD RIGHT 3 (LEFT part ON)")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD RIGHT 4 (ACCOMP1 part ON)")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD RIGHT 5 (ACCOMP2 part ON)")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Fn 2012")

	PORT_START("SEG10")   // normSeg 0x10 -- sound / right panel
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("ONE TOUCH PLAY")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SPLIT POINT")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("VARIATION & MSA")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("VARIATION & MSA")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART SELECT")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART SELECT")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART SELECT")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOLO")

	PORT_START("SEG11")   // normSeg 0x11 -- sound / right panel
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("FADE IN/OUT")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("FADE IN/OUT")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("FILL IN 1/2")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("FILL IN 1/2")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CONDUCTOR")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CONDUCTOR")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CONDUCTOR")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("TECHNI-CHORD")

	PORT_START("SEG12")   // normSeg 0x12 -- sound / right panel
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("INTRO & ENDING")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("INTRO & ENDING")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("TAP TEMPO")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("START/STOP")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PROGRAM MENU")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("DISK")

	PORT_START("SEG13")   // normSeg 0x13 -- sound / right panel
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("TRANSPOSE -/+")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("TRANSPOSE -/+")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("R1/R2 OCTAVE -/+")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("R1/R2 OCTAVE -/+")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CHORUS")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MULTI EFFECT")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("REVERB")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MIC REVERB & EFFECT")

	PORT_START("SEG14")   // normSeg 0x14 -- sound / right panel
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Sound Select 0F")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Sound Select 06")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_UNUSED)

	PORT_START("SEG15")   // normSeg 0x15 -- sound / right panel
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SYNCHRO & BREAK")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Sound Select 05")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_UNUSED)

	// SEG16-SEG20: DIAL/DATA/special panel-serial buttons (wire ADDR 0xD0-0xD3, 0x10, 0x17 from
	// PanelWireNormTable 0x486135A0). normSeg 0x1B-0x1F (0x1000 soft-keys, 0x20B5-BD, 0x2005/2030
	// dup events) have NO wire path and are not panel-serial; defined empty for the array. Names
	// are placeholders (event codes) pending snapshot ID; see notes/panel-descriptor-map.md.
	PORT_START("SEG16")   // normSeg 0x16 -- wire ADDR 0xD0
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Fn 1005 (DIAL?)")
	PORT_BIT(0xfe, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG17")   // normSeg 0x17 -- wire ADDR 0xD1
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Fn 1004 (DATA?)")
	PORT_BIT(0xfe, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG18")   // normSeg 0x18 -- wire ADDR 0xD2
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Fn 1009")
	PORT_BIT(0xfe, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG19")   // normSeg 0x19 -- wire ADDR 0xD3
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Fn 1010")
	PORT_BIT(0xfe, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG1A")   // normSeg 0x1A -- wire ADDR 0x10
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Fn 1011")
	PORT_BIT(0xfe, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG1B")   // normSeg 0x1B -- no wire path
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG1C")   // normSeg 0x1C -- no wire path
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG1D")   // normSeg 0x1D -- no wire path
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG1E")   // normSeg 0x1E -- no wire path
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG1F")   // normSeg 0x1F -- no wire path
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG20")   // normSeg 0x20 -- wire ADDR 0x17
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Fn 1020")
	PORT_BIT(0xfe, IP_ACTIVE_HIGH, IPT_UNUSED)

	PORT_START("DIAL")
	PORT_BIT(0xff, 0x00, IPT_DIAL) PORT_SENSITIVITY(30) PORT_KEYDELTA(1) PORT_NAME("DATA DIAL")

	// Music key bed (subset: ~2 octaves on the PC keyboard, tracker-style layout).
	// Each key pushes a note-on/off voice-event into the FIFO the firmware polls at
	// 0x98050004 (see kbd_key / kbd_push). MIDI note numbers; C4 = 0x3C = 60.
#define KN_KEY(mask, note, code, name) \
	PORT_BIT(mask, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME(name) PORT_CODE(code) \
	PORT_CHANGED_MEMBER(DEVICE_SELF, FUNC(kn7000_state::kbd_key), note)
	PORT_START("KEYS0")   // lower octave: Z S X D C V G B H N J M  (C4..B4)
	KN_KEY(0x0001, 0x3C, KEYCODE_Z, "Key C4")
	KN_KEY(0x0002, 0x3D, KEYCODE_S, "Key C#4")
	KN_KEY(0x0004, 0x3E, KEYCODE_X, "Key D4")
	KN_KEY(0x0008, 0x3F, KEYCODE_D, "Key D#4")
	KN_KEY(0x0010, 0x40, KEYCODE_C, "Key E4")
	KN_KEY(0x0020, 0x41, KEYCODE_V, "Key F4")
	KN_KEY(0x0040, 0x42, KEYCODE_G, "Key F#4")
	KN_KEY(0x0080, 0x43, KEYCODE_B, "Key G4")
	KN_KEY(0x0100, 0x44, KEYCODE_H, "Key G#4")
	KN_KEY(0x0200, 0x45, KEYCODE_N, "Key A4")
	KN_KEY(0x0400, 0x46, KEYCODE_J, "Key A#4")
	KN_KEY(0x0800, 0x47, KEYCODE_M, "Key B4")
	PORT_START("KEYS1")   // upper octave: Q 2 W 3 E R 5 T 6 Y 7 U I  (C5..C6)
	KN_KEY(0x0001, 0x48, KEYCODE_Q, "Key C5")
	KN_KEY(0x0002, 0x49, KEYCODE_2, "Key C#5")
	KN_KEY(0x0004, 0x4A, KEYCODE_W, "Key D5")
	KN_KEY(0x0008, 0x4B, KEYCODE_3, "Key D#5")
	KN_KEY(0x0010, 0x4C, KEYCODE_E, "Key E5")
	KN_KEY(0x0020, 0x4D, KEYCODE_R, "Key F5")
	KN_KEY(0x0040, 0x4E, KEYCODE_5, "Key F#5")
	KN_KEY(0x0080, 0x4F, KEYCODE_T, "Key G5")
	KN_KEY(0x0100, 0x50, KEYCODE_6, "Key G#5")
	KN_KEY(0x0200, 0x51, KEYCODE_Y, "Key A5")
	KN_KEY(0x0400, 0x52, KEYCODE_7, "Key A#5")
	KN_KEY(0x0800, 0x53, KEYCODE_U, "Key B5")
	KN_KEY(0x1000, 0x54, KEYCODE_I, "Key C6")
#undef KN_KEY
INPUT_PORTS_END


uint32_t kn7000_state::screen_update(screen_device &screen, bitmap_rgb32 &bitmap, const rectangle &cliprect)
{
	// Present the firmware's OWN composited image -- the exact bytes the real LCD
	// controller scans. The firmware's software compositor blends the UI plane and the
	// 12-bit direct-colour picture planes (see notes/display-dual-plane-direct-color.md)
	// into a 640x240 RGB565 buffer at 0x9CE00000 (linear, top-to-bottom). Reading it
	// directly gives a pixel-perfect display (gamma-correct UI colours, pictures
	// composited by the machine itself) and supersedes reconstructing it from the work-
	// RAM planes + CLUT. Runtime-verified against a dump: the home screen is pixel-exact.
	// (The boot-splash JPEG still decodes to garbage -- a separate software-decoder bug
	// -- so the splash reads as noise here too, faithfully.)
	// TODO: honour the 2-bit grayscale panel (type 2 at 0x50007578).
	constexpr offs_t LCD = (0x9ce00000 - 0x9c000000) / 4;      // word offset of the RGB565 buffer in the 0x9c RAM
	for (int y = cliprect.top(); y <= cliprect.bottom(); y++)
	{
		uint32_t *const dst = &bitmap.pix(y);
		for (int x = cliprect.left(); x <= cliprect.right(); x++)
		{
			const offs_t k = y * 640 + x;                     // linear pixel index
			const uint32_t w = m_lcdbuf[LCD + (k >> 1)];
			const uint16_t v = (k & 1) ? uint16_t(w >> 16) : uint16_t(w);   // little-endian RGB565
			dst[x] = rgb_t(((v >> 11) & 0x1f) << 3, ((v >> 5) & 0x3f) << 2, (v & 0x1f) << 3);
		}
	}
	return 0;
}


void kn7000_state::machine_start()
{
	// output_finders auto-resolve in this MAME version (see kn5000_cpanel) --
	// no explicit resolve() call is needed or available.

	// Periodic control-panel button scan (the real sub-CPUs poll their matrices
	// continuously and report changes over the serial link).
	m_panel_timer = timer_alloc(FUNC(kn7000_state::panel_scan), this);
	m_panel_evt = timer_alloc(FUNC(kn7000_state::panel_event), this);
	m_panel_txdone = timer_alloc(FUNC(kn7000_state::panel_event), this);

	// The AM33 maskable interrupt vectors to the library-ROM low-level handler
	// (self-loaded; context-save entry at 0x4C03DDA0). The system-tick timer
	// raises the periodic interrupt that drives the MILK scheduler.
	m_maincpu->set_irq_vector(0x4C03DDA0);

	// KN6000/KN6500: unlike the KN7000 (which self-loads its library), the
	// "library" at 0x4C000000/0x8C000000 is a bus mirror of the program ROM.
	// Populate the aliased libram from the program ROM so the boot finds it.
	if (m_lib_mirror)
		memcpy(memshare("libram")->ptr(), memregion("maincpu")->base(), memregion("maincpu")->bytes());
	m_sys_timer = timer_alloc(FUNC(kn7000_state::sys_tick), this);
	m_fav_timer = timer_alloc(FUNC(kn7000_state::fav_preload), this);

	save_item(NAME(m_gxicr));
	save_item(NAME(m_sio_config));
	save_item(NAME(m_sio_control));
	save_item(NAME(m_sio_rx_fifo));
	save_item(NAME(m_sio_rx_head));
	save_item(NAME(m_sio_rx_tail));
	save_item(NAME(m_panel_pos));
	save_item(NAME(m_panel_p1));
	save_item(NAME(m_panel_p2));
	save_item(NAME(m_btn_prev));
	save_item(NAME(m_snd_500e));
	save_item(NAME(m_tg_addr));
	save_item(NAME(m_tg_reg));
}

void kn7000_state::machine_reset()
{
	for (int ch = 0; ch < 3; ch++)
	{
		m_sio_config[ch] = 0;
		m_sio_control[ch] = 0;
		m_sio_rx_head[ch] = m_sio_rx_tail[ch] = 0;
	}
	m_panel_pos = 0;
	std::fill(std::begin(m_btn_prev), std::end(m_btn_prev), 0);
	std::fill(std::begin(m_gxicr), std::end(m_gxicr), 0);

	// Start scanning the panel at ~250 Hz.
	m_panel_timer->adjust(attotime::from_hz(250), 0, attotime::from_hz(250));

	// System tick ~1 kHz (real rate TBD -- input clock unknown; tune later). The timer
	// interrupt dispatches (via IAGR=group<<3) to the real RTOS handler, whose context
	// save uses the AM33 F6 "udf"/DSP ops (getx etc.) -- now implemented in the core
	// (execute_f6), so this is ACTIVE and the boot is stable. (Earlier this was HELD
	// because those F6 ops were skipped and the saved context was corrupted; that is
	// resolved.) See notes/interrupt-mechanism.md ("F6 / udf extended ops").
	m_sys_timer->adjust(attotime::from_hz(1000), 0, attotime::from_hz(1000));

	// Pre-load the factory "Initial Data" Favorites into battery-backed SRAM. This
	// must run AFTER the boot BSS-clear (which zeroes work RAM up to ~0x50180000) but
	// before the Favorites screen is opened, so it is deferred to a one-shot timer
	// (see fav_preload). Confirmed by RE: a machine_reset write is wiped by the clear;
	// a t=3s write survives and the firmware keeps it.
	m_fav_timer->adjust(attotime::from_seconds(3));
}

void kn7000_state::kn7000(machine_config &config)
{
	// Panasonic MN103002A (MN10300/AM33 core), IC4 on MAIN 1/5.
	// Clock tree (SX-KN7000 service manual, SCHEMATIC DIAGRAM-1): a 16.0 MHz
	// reference crystal X1 (part H0J160500026 -- the H0J<freq*10> code family:
	// X102 H0J177=17.73, X103 H0J240=24.0, X104 H0J143=14.32 MHz) drives clock
	// generator IC6 (C02BZ0000667: XIN/XOUT/FRSEL/S1/S2 -> SSCLK). SSCLK also
	// feeds a divide-by-2 flip-flop IC11 (TC7WH74) that clocks peripherals, so
	// the CPU itself is NOT the /2 branch (an 8 MHz AM33 is implausible for a
	// 2003 flagship that boots in ~12-15 s). The AM33 core runs the 16 MHz
	// reference through its internal PLL; x2 = 32 MHz matches the measured boot
	// work (~400M cycles / 32 MHz ~= 12.5 s, i.e. real-hardware boot time).
	// CONFIRMED via firmware MIDI-baud cross-check: the MIDI UARTs (SC1/SC2 at
	// 0x34000810/0x34000820) are set to 8N1 with the baud clock = Timer-3
	// underflow / 8 (SC1CTR CK field = 0x5), and TM3 counts at IOCLK with reload
	// TM3BR = 0x3F (63). MIDI baud is exactly 31250, so
	//   31250 = IOCLK / (8 * (0x3F + 1)) = IOCLK / 512  =>  IOCLK = 16.000 MHz.
	// The AM33 core runs at 2x IOCLK (schematic /2 peripheral branch via IC11;
	// MN10300 IOCLK = fc/2 convention) => fc = 32.000 MHz. Only 16 MHz IOCLK
	// reproduces TM3BR=0x3F (32 MHz would need 0x7F); 40/48 excluded likewise.
	MN10300(config, m_maincpu, 16_MHz_XTAL * 2);
	m_maincpu->set_irq_acknowledge_callback(FUNC(kn7000_state::irq_ack));
	m_maincpu->set_addrmap(AS_PROGRAM, &kn7000_state::maincpu_mem);

	/* video hardware */
	// LCD panel. Exact geometry is uncertain: the KN7000 front-panel LCD is
	// reported as either 320x240 or 640x240. Using 640x240 as a placeholder.
	// TODO: confirm resolution, pixel clock and the LCD controller feeding
	//       the V-RAM at IC104.
	SCREEN(config, m_screen, SCREEN_TYPE_LCD);
	m_screen->set_refresh_hz(60);
	m_screen->set_vblank_time(ATTOSECONDS_IN_USEC(0));
	// 640x240 8bpp LCD (proven from the blitter stride 0x280 and height 0xF0).
	m_screen->set_size(640, 240);
	m_screen->set_visarea(0, 640 - 1, 0, 240 - 1);
	m_screen->set_screen_update(FUNC(kn7000_state::screen_update));

	// Clickable front-panel artwork: buttons bound to the ioports, LEDs bound to
	// the cpl_led/cpc_led/cpr_led outputs. Generated by tools/gen_layout.py.
	config.set_default_layout(layout_kn7000);

	// --- MIDI ports (SIO channels 1 & 2 at 0x34000810 / 0x34000820) ---------
	// Each channel has a byte<->bit UART bridge feeding a standard MAME MIDI
	// IN/OUT port pair. TX (firmware -> SIO -> UART -> MIDI OUT) works now;
	// MIDI IN bytes are queued on the SIO RX FIFO but only reach the firmware
	// once the MN10300 core takes SIO receive interrupts.
	KN7000_SIO_UART(config, m_midi_uart[0], 0);
	m_midi_uart[0]->tx_cb().set("mdout1", FUNC(midi_port_device::write_txd));
	m_midi_uart[0]->rx_cb().set(FUNC(kn7000_state::midi_rx<SIO_MIDI1>));
	MIDI_PORT(config, "mdin1", midiin_slot, "midiin").rxd_handler().set(m_midi_uart[0], FUNC(kn7000_sio_uart_device::rx_w));
	MIDI_PORT(config, "mdout1", midiout_slot, "midiout");

	KN7000_SIO_UART(config, m_midi_uart[1], 0);
	m_midi_uart[1]->tx_cb().set("mdout2", FUNC(midi_port_device::write_txd));
	m_midi_uart[1]->rx_cb().set(FUNC(kn7000_state::midi_rx<SIO_MIDI2>));
	MIDI_PORT(config, "mdin2", midiin_slot, "midiin").rxd_handler().set(m_midi_uart[1], FUNC(kn7000_sio_uart_device::rx_w));
	MIDI_PORT(config, "mdout2", midiout_slot, "midiout");

	// TODO: sound hardware (dual tone generators + DSP IC306/IC307),
	//       floppy disk controller (IC103), SD card and USB.
}

// KN6000/KN6500 reuse the KN7000 machine, but their library ROM at 0x4C000000 is
// a bus mirror of the program ROM (populated in machine_start), not self-loaded.
void kn7000_state::kn6000(machine_config &config)
{
	kn7000(config);
	m_lib_mirror = true;
}


ROM_START(kn7000)
	ROM_REGION32_LE(0x400000, "maincpu", ROMREGION_ERASEFF)   // program IC16/IC17 -> 0x48400000
	ROM_LOAD32_WORD("kn7000_program_even.rom", 0x000000, 0x200000, CRC(529b87ce) SHA1(f198fd9a9ea31a454acfe7be0eb935beca6771b1))
	ROM_LOAD32_WORD("kn7000_program_odd.rom",  0x000002, 0x200000, CRC(a36e6222) SHA1(721d4469dc5f692f7a2c16c556b2e21115df19f6))
	ROM_REGION32_LE(0x400000, "table", ROMREGION_ERASEFF)
	ROM_LOAD32_WORD("kn7000_table_even.rom", 0x000000, 0x200000, CRC(005a6db2) SHA1(2f4112ea9b039b17b5ada6952b7646adae8d9dd6))
	ROM_LOAD32_WORD("kn7000_table_odd.rom",  0x000002, 0x200000, CRC(7e1a312e) SHA1(435b597b926ebac56d4710bcae25b635a59a9ce5))

	// TODO: Library / boot ROM at 0x4C000000 - currently undumped.
	//ROM_REGION(0x100000, "library", ROMREGION_ERASEFF)
	//ROM_LOAD("kn7000_library.rom", 0x000000, 0x100000, NO_DUMP)

	// TODO: Picture flash at 0x57800000 - not dumped yet.
	//ROM_REGION(0x800000, "picture", ROMREGION_ERASEFF)
	//ROM_LOAD("kn7000_picture.rom", 0x000000, 0x800000, NO_DUMP)

	// Tone-generator waveform / sample ROMs -- UNDUMPED. The synth LSI IC205
	// (C1BB00000709, "TONE GENERATOR" in the service manual) plays PCM samples
	// from four custom Panasonic mask ROMs on the sound board: IC203
	// (C3CBQD000002), IC204 (C3CBQD000001), IC207 (C3CBQD000004), IC208
	// (C3CBQD000003). These are physically separate chips, NOT part of the
	// firmware update disks this driver's ROMs come from, so audible sound is
	// impossible until they are dumped from the board (see the service manual
	// "8.9 WAVE ROM test" / "8.10 SOUND SYSTEM test"; sizes below are placeholders).
	//ROM_REGION(0x400000, "wave", ROMREGION_ERASEFF)
	//ROM_LOAD("kn7000_wave_ic203.rom", 0x000000, 0x400000, NO_DUMP)  // C3CBQD000002
	//ROM_LOAD("kn7000_wave_ic204.rom", 0x400000, 0x400000, NO_DUMP)  // C3CBQD000001
	//ROM_LOAD("kn7000_wave_ic207.rom", 0x800000, 0x400000, NO_DUMP)  // C3CBQD000004
	//ROM_LOAD("kn7000_wave_ic208.rom", 0xc00000, 0x400000, NO_DUMP)  // C3CBQD000003
ROM_END


// ===================================================================
// KN6000 / KN6500 -- MN10300 siblings of the KN7000 (DRAFT drivers).
// Same CPU family and same 0x48400000 program base as the KN7000
// (verified: KN6000 reset vector at 0x48400000 is "jmp 0x484002e3"),
// so for now they reuse kn7000_state and the kn7000 machine config;
// per-model memory map / peripheral wiring is still to be tuned.
// The images are the decompressed IK*.SLD (KN6000) / IKV*.SLD (KN6500)
// firmware-update payloads -- BAD_DUMP because they are derived from
// the update disks, not read from the chips (IC11/IC12 program flash,
// IC13/IC14 table mask ROM per the service manual).
// ===================================================================
ROM_START(kn6000)
	ROM_REGION32_LE(0x400000, "maincpu", ROMREGION_ERASEFF)   // program IC12/IC11 (IK1) -> 0x48400000
	ROM_LOAD32_WORD("kn6000_program_even.rom", 0x000000, 0x200000, CRC(56c2cfe3) SHA1(e15a4c73440f1dcdf06457f9956c96bf20d68b16))
	ROM_LOAD32_WORD("kn6000_program_odd.rom",  0x000002, 0x200000, CRC(9d94da6c) SHA1(d73b4c8ebf0c67b6a2eeb5571d0273fc6efbfe4c))
	ROM_REGION32_LE(0x400000, "table", ROMREGION_ERASEFF)     // table -> 0x48000000 (IK2, 0x1F7A31)
	ROM_LOAD32_WORD("kn6000_table_even.rom", 0x000000, 0x200000, CRC(fa5e4f93) SHA1(0426da99b1589c0362e6321466beab21b22b81b0))
	ROM_LOAD32_WORD("kn6000_table_odd.rom",  0x000002, 0x200000, CRC(fd8e3bcd) SHA1(e1b63d45299b67e5258d5d08a949ea8e05c1b8e6))
ROM_END

ROM_START(kn6500)
	ROM_REGION32_LE(0x400000, "maincpu", ROMREGION_ERASEFF)   // program IC12/IC11 (IKV1) -> 0x48400000
	ROM_LOAD32_WORD("kn6500_program_even.rom", 0x000000, 0x200000, CRC(f42a2fcf) SHA1(7cebf73bf623fd714ca455ed50b80da1d2186414))
	ROM_LOAD32_WORD("kn6500_program_odd.rom",  0x000002, 0x200000, CRC(ca2a733f) SHA1(2484d3b76b62b05ded39e4194cdc74fd3c01bcbe))
	ROM_REGION32_LE(0x400000, "table", ROMREGION_ERASEFF)     // table -> 0x48000000 (IKV2, 0x181691)
	ROM_LOAD32_WORD("kn6500_table_even.rom", 0x000000, 0x200000, CRC(8c7f33a2) SHA1(d44fb4415cd6b571e11e57d4a7642226b0bf4edf))
	ROM_LOAD32_WORD("kn6500_table_odd.rom",  0x000002, 0x200000, CRC(6953e094) SHA1(abf4c2252d40c71c761503d657593eb6e9c0eecc))
ROM_END


// ===================================================================
// KN2400 / KN2600 -- also MN10300/MILK siblings (DRAFT drivers). The
// SX-KN2000/KN2400/KN2600 family shares ONE firmware image: the update
// disk's KN24PRG.DAT is byte-identical to LKG1.SLD + LKG2.SLD, and the
// image carries "KN2000"/"KN2400"/"KN2600" model strings (it branches on
// model at runtime). Verified MN10300: reset vector at 0x48400000 is
// "jmp 0x48705bdf"; MILK toolkit present (MT_GetProcedureSp, ...). So
// kn2600 is a clone of kn2400 (same ROMs). Reuses kn7000_state / the
// kn7000 machine config for now; memory map / peripherals to be tuned.
// ===================================================================
ROM_START(kn2400)
	// KN2400/KN2600/PR54 share one firmware (runtime model selector): program =
	// LKG1@0x48400000 + LKG2@0x48600000 (== KN24PRG.DAT); no separate table flash.
	ROM_REGION32_LE(0x400000, "maincpu", ROMREGION_ERASEFF)   // program
	ROM_LOAD32_WORD("kn2400_program_even.rom", 0x000000, 0x200000, CRC(b94fc8a8) SHA1(86d5d9916afdb90f82de78064b1d76fce3a21d7b))
	ROM_LOAD32_WORD("kn2400_program_odd.rom",  0x000002, 0x200000, CRC(73781cbc) SHA1(d90a3560561efd94322dca1a6710f2d5d3837cd2))
	ROM_REGION32_LE(0x400000, "table", ROMREGION_ERASEFF)  // no separate table flash on this model
ROM_END

// KN2600 shares the KN2400 firmware image -> clone of kn2400 (ROMs resolve from the parent set).
ROM_START(kn2600)
	ROM_REGION32_LE(0x400000, "maincpu", ROMREGION_ERASEFF)
	ROM_LOAD32_WORD("kn2400_program_even.rom", 0x000000, 0x200000, CRC(b94fc8a8) SHA1(86d5d9916afdb90f82de78064b1d76fce3a21d7b))
	ROM_LOAD32_WORD("kn2400_program_odd.rom",  0x000002, 0x200000, CRC(73781cbc) SHA1(d90a3560561efd94322dca1a6710f2d5d3837cd2))
	ROM_REGION32_LE(0x400000, "table", ROMREGION_ERASEFF)
ROM_END

} // anonymous namespace


//   YEAR  NAME    PARENT  COMPAT  MACHINE  INPUT   CLASS         INIT        COMPANY     FULLNAME      FLAGS
SYST(2002, kn7000, 0,      0,      kn7000,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN7000", MACHINE_NOT_WORKING | MACHINE_NO_SOUND)

// KN6000 / KN6500 -- draft drivers reusing the KN7000 machine config (same MN10300 CPU, same 0x48400000 base).
SYST(2000, kn6000, 0,      0,      kn6000,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN6000", MACHINE_NOT_WORKING | MACHINE_NO_SOUND)
SYST(2001, kn6500, 0,      0,      kn6000,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN6500", MACHINE_NOT_WORKING | MACHINE_NO_SOUND)

// KN2400 / KN2600 -- MN10300/MILK siblings sharing one firmware image (kn2600 = clone of kn2400).
SYST(1998, kn2400, 0,      0,      kn7000,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN2400", MACHINE_NOT_WORKING | MACHINE_NO_SOUND)
SYST(2000, kn2600, kn2400, 0,      kn7000,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN2600", MACHINE_NOT_WORKING | MACHINE_NO_SOUND)
