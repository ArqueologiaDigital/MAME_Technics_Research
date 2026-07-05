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
        0x98040000  main tone generator (IC203/204) - 16-bit register set
        0x98050000  sub  tone generator (IC207/208) - parallel 16-bit set
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
		, m_midi_uart(*this, "midi_uart%u", 0U)
		, m_cpl_seg(*this, "CPL_SEG%u", 0U)
		, m_cpc_seg(*this, "CPC_SEG%u", 0U)
		, m_cpr_seg(*this, "CPR_SEG%u", 0U)
		, m_dial(*this, "DIAL")
		, m_cpl_leds(*this, "cpl_led%u", 0U)
		, m_cpc_leds(*this, "cpc_led%u", 0U)
		, m_cpr_leds(*this, "cpr_led%u", 0U)
	{ }

	void kn7000(machine_config &config) ATTR_COLD;

protected:
	virtual void machine_start() override ATTR_COLD;
	virtual void machine_reset() override ATTR_COLD;

private:
	required_device<mn10300_device> m_maincpu;
	required_device<screen_device> m_screen;
	required_shared_ptr<uint32_t> m_workram;
	required_device_array<kn7000_sio_uart_device, 2> m_midi_uart;

	template <int Ch> void midi_rx(uint8_t data) { sio_rx_push(Ch, data); }

	// Control panel button ports and LEDs (CPL = 8 cols, CPC = 5 cols; CPR + the
	// serial HLE device that reads these / drives the LEDs are still to come).
	required_ioport_array<8> m_cpl_seg;
	required_ioport_array<5> m_cpc_seg;
	required_ioport_array<10> m_cpr_seg;
	required_ioport m_dial;
	output_finder<64> m_cpl_leds;
	output_finder<64> m_cpc_leds;
	output_finder<80> m_cpr_leds;

	void maincpu_mem(address_map &map) ATTR_COLD;

	// bring-up logging handlers for the (not-yet-decoded) I/O banks
	uint16_t io_r(offs_t offset, uint16_t mem_mask = ~0);
	void io_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);

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
	emu_timer *m_panel_timer = nullptr;
	uint8_t m_panel_tx_addr = 0;
	bool    m_panel_tx_have_addr = false;
	uint8_t m_btn_prev[23] = { };   // last scanned state, one per declared segment

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
	map(0x8c000000, 0x8cffffff).ram();
	map(0x90000000, 0x97ffffff).ram();

	// --- Stubs for regions whose behavior is still unknown --------------
	// TODO: Library / boot ROM (undumped) at 0x4C000000. The firmware calls
	//       into it (e.g. a printf-like renderer at 0x4C001A48), so this is
	//       real code, not just data.
	//map(0x4c000000, 0x4c0fffff).rom().region("library", 0);

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
	// The SIO ASIC (panel + two MIDI channels) is a decoded sub-block of the
	// 0x34000000 bank; this more-specific mapping overrides the logger above.
	map(0x34000800, 0x3400082f).rw(FUNC(kn7000_state::sio_r), FUNC(kn7000_state::sio_w));
	map(0x36008000, 0x360080ff).rw(FUNC(kn7000_state::io_r), FUNC(kn7000_state::io_w));
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
	if (!machine().side_effects_disabled())
		logerror("%s: io_r  +%06X mask %04X\n", machine().describe_context(),
			offset << 1, mem_mask);
	return 0;
}

void kn7000_state::io_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	logerror("%s: io_w  +%06X = %04X mask %04X\n", machine().describe_context(),
		offset << 1, data, mem_mask);
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
	// TODO: assert this channel's SIO receive interrupt (ICR 0x34000168 / 148 /
	// 150 -> MN10300 IRQ). The MN10300 core does not yet take interrupts, so a
	// queued byte is not yet delivered to the firmware's RX ISR.
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
		// LED/command stream to the panel sub-CPUs: 2-byte [ADDR][DATA] frames.
		if (!m_panel_tx_have_addr)
		{
			m_panel_tx_addr = data;
			m_panel_tx_have_addr = true;
		}
		else
		{
			m_panel_tx_have_addr = false;
			panel_led_frame(m_panel_tx_addr, data);
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
	const int reg = addr & 0x3f;
	for (int bit = 0; bit < 8; bit++)
	{
		const int led = reg * 8 + bit;
		const int on = BIT(data, bit);
		if (led < 64) m_cpl_leds[led] = on;   // provisional: all to CPL bank
	}
	logerror("%s: panel LED frame addr=%02X data=%02X\n",
		machine().describe_context(), addr, data);
}

// Periodic button scan: read each declared segment ioport, and for any that
// changed since last scan, queue a 2-byte [ADDR][DATA] switch-report frame onto
// the panel RX. DATA bit = 1 means pressed (active-high on the wire); the frame
// is the same format the real sub-CPUs emit (notes/panel-serial-protocol.md,
// e.g. START/STOP press = C0 10). Delivery to the firmware awaits SIO interrupts.
TIMER_CALLBACK_MEMBER(kn7000_state::panel_scan)
{
	int seg = 0;
	auto scan_board = [&](auto &ports, int count, uint8_t bank)
	{
		for (int i = 0; i < count; i++, seg++)
		{
			const uint8_t cur = ports[i]->read();
			if (cur != m_btn_prev[seg])
			{
				m_btn_prev[seg] = cur;
				// ADDR = bank(bits6-7, with bit7==bit6) | type0 | subaddr(i);
				// only banks 00 and 11 are valid on the wire.
				const uint8_t addr = bank | (i & 0x07);
				sio_rx_push(SIO_PANEL, addr);
				sio_rx_push(SIO_PANEL, cur);
			}
		}
	};
	scan_board(m_cpl_seg, 8, 0xc0);   // CPL: bank 11 (matches the START/STOP anchor)
	scan_board(m_cpc_seg, 5, 0x00);   // CPC/CPR bank assignment still provisional
	scan_board(m_cpr_seg, 10, 0x00);
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
	// ---- CPL P.C.B. 8x8 switch matrix (SEGn column, bits = SW0..SW7) ----
	PORT_START("CPL_SEG0")   // LCD soft-keys + transport (left)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD Left 4")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD Left 1")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD Left 5")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD Left 2")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("START/STOP")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD Left 3")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("INTRO & ENDING 2")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SYNCHRO & BREAK")

	PORT_START("CPL_SEG1")   // rhythm / style group A
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MEMORY/LOAD")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUL & FUNK")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CUSTOM")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("BALLAD")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("JAZZ COMBO")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("ROCK & POP")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("BIG BAND & SWING")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("R & B")

	PORT_START("CPL_SEG2")   // rhythm / style group B
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MOVIE SHOW")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MARCH")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("ENTERTAINER")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("COUNTRY")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LATIN & WORLD")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("GOSPEL & BLUES")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("BALLROOM")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MODERN DANCE")

	PORT_START("CPL_SEG3")   // fills / transport
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("INTRO & ENDING 1")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("FILL IN 2")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("FADE OUT")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("FILL IN 1")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("FADE IN")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SPLIT POINT")

	PORT_START("CPL_SEG4")   // variation / arranger
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("VARIATION & MSA 3")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("TAP TEMPO")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("VARIATION & MSA 2")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUSIC STYLE ARRANGER")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("VARIATION & MSA 1")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("VARIATION & MSA 4")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_UNUSED)

	PORT_START("CPL_SEG5")   // performance pads
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PAD 5/SOLO")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("ONE TOUCH PLAY")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PAD 4")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PADS BANK")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PAD 1")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PAD 3")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PAD 6/SOLO")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_UNUSED)

	PORT_START("CPL_SEG6")   // pads / global
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PADS STOP")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND SET")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PLAY CHORD OFF/ON")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("ARRANGER OFF/ON")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PADS AUTO")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("DEMO")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_UNUSED)

	PORT_START("CPL_SEG7")   // modes
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUSIC STYLIST")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("AUTO MODE")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("ONE TOUCH PLAY 2")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_UNUSED)

	// ---- CPC P.C.B. (SCHEMATIC DIAGRAM-16, page 130): the part mixer -----
	// Sub-CPU scans columns SEG5,SEG8,SEG9,SEG10,SEG11 x SW0..SW7. The board is
	// dominated by the 16 part MUTE UP/DOWN pairs plus display controls.
	PORT_START("CPC_SEG0")   // schematic SEG5
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("OTHER PARTS/TG")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("HELP")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CONTRAST UP")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CONTRAST DOWN")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE UP 1")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE DOWN 1")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE UP 2")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE DOWN 2")

	PORT_START("CPC_SEG1")   // schematic SEG8
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE UP 3")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE DOWN 3")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE UP 4")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE DOWN 4")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE UP 5")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE DOWN 5")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE UP 6")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE DOWN 6")

	PORT_START("CPC_SEG2")   // schematic SEG9
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE UP 7")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE DOWN 7")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE UP 8")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE DOWN 8")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE UP 9")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE DOWN 9")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE UP 10")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE DOWN 10")

	PORT_START("CPC_SEG3")   // schematic SEG10
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE UP 11")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE DOWN 11")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE UP 12")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE DOWN 12")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE UP 13")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE DOWN 13")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE UP 14")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE DOWN 14")

	PORT_START("CPC_SEG4")   // schematic SEG11
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE UP 15")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE DOWN 15")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE UP 16")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUTE DOWN 16")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PAGE UP")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PAGE DOWN")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("DISPLAY HOLD")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("EXIT")

	// ---- ROT P.C.B.: the data dial (rotary encoder SW1101, feeds CPR) ----
	PORT_START("DIAL")
	PORT_BIT(0xff, 0x00, IPT_DIAL) PORT_SENSITIVITY(30) PORT_KEYDELTA(1) PORT_NAME("DATA DIAL")

	// ---- CPR P.C.B. (SCHEMATIC DIAGRAM-17, page 132) -----------------------
	// Master panel sub-CPU IC1001 (C0BDB000023): the main-CPU serial link
	// attaches here (SIM/SOUT/CLK/CNTR1) and CPR chains to CPL. 10-column matrix
	// SEG0..SEG9 x SW0..SW7. NOTE: transcribed from the schematic; the exact
	// SW-row within each SEG should be verified against the print.
	PORT_START("CPR_SEG0")
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("TECHNI-CHORD")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND GROUP 1")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PROGRAM MENUS")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("DISK EASY REC")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MALLET & ORCH PERC")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("BASS")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CUSTOMIZE")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SD CARD LOAD")

	PORT_START("CPR_SEG1")
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOLO")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART SELECT RIGHT 2")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("DISK MENU LOAD")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("VARIATION")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("BRASS")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SYNTH")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CUSTOM PANEL")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_UNUSED)

	PORT_START("CPR_SEG2")
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART SELECT LEFT")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART SELECT RIGHT 1")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("EFFECT MIC")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND DSP")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("STRINGS & VOCAL")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PAD")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("FAVORITES")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("NEXT BANK")

	PORT_START("CPR_SEG3")
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("TRANSPOSE R1 -")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CONDUCTOR RIGHT 2")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MULTI")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("DIGITAL EFFECT")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("GUITAR")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("TAB ORGAN")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND GROUP 5")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("BANK VIEW")

	PORT_START("CPR_SEG4")
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("TRANSPOSE R1 +")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CONDUCTOR LEFT")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("REVERB")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SUSTAIN")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PIANO")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("DIGITAL DRAWBAR")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND GROUP 4")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND GROUP 6")

	PORT_START("CPR_SEG5")
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD Right 5")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("TRANSPOSE R2 -")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CHORUS")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND EXPLORER")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD Right 1")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD Right 2")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND GROUP 3")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND GROUP 7")

	PORT_START("CPR_SEG6")
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD Right 4")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("TRANSPOSE R2 +")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("EW EXPANSION")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SAX & WOODWIND")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND GROUP 2")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND GROUP 8")

	PORT_START("CPR_SEG7")
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LCD Right 3")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MEMORY")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("ORGAN & ACCORDION")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND SET")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_UNUSED)

	PORT_START("CPR_SEG8")
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("ACCORDION REGISTER")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_UNUSED)

	PORT_START("CPR_SEG9")
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("DRUM KITS")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("WORLD")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_UNUSED)
INPUT_PORTS_END


uint32_t kn7000_state::screen_update(screen_device &screen, bitmap_rgb32 &bitmap, const rectangle &cliprect)
{
	// TODO: Real LCD controller (V-RAM at IC104) is not emulated yet.
	bitmap.fill(rgb_t::black(), cliprect);
	return 0;
}


void kn7000_state::machine_start()
{
	// output_finders auto-resolve in this MAME version (see kn5000_cpanel) --
	// no explicit resolve() call is needed or available.

	// Periodic control-panel button scan (the real sub-CPUs poll their matrices
	// continuously and report changes over the serial link).
	m_panel_timer = timer_alloc(FUNC(kn7000_state::panel_scan), this);

	save_item(NAME(m_sio_config));
	save_item(NAME(m_sio_control));
	save_item(NAME(m_sio_rx_fifo));
	save_item(NAME(m_sio_rx_head));
	save_item(NAME(m_sio_rx_tail));
	save_item(NAME(m_panel_tx_addr));
	save_item(NAME(m_panel_tx_have_addr));
	save_item(NAME(m_btn_prev));
}

void kn7000_state::machine_reset()
{
	for (int ch = 0; ch < 3; ch++)
	{
		m_sio_config[ch] = 0;
		m_sio_control[ch] = 0;
		m_sio_rx_head[ch] = m_sio_rx_tail[ch] = 0;
	}
	m_panel_tx_have_addr = false;
	std::fill(std::begin(m_btn_prev), std::end(m_btn_prev), 0);

	// Start scanning the panel at ~250 Hz.
	m_panel_timer->adjust(attotime::from_hz(250), 0, attotime::from_hz(250));
}

void kn7000_state::kn7000(machine_config &config)
{
	// Panasonic MN10300/AM33 main CPU.
	// TODO: The actual clock frequency is unknown; 10 MHz is a placeholder.
	MN10300(config, m_maincpu, 10_MHz_XTAL);
	m_maincpu->set_addrmap(AS_PROGRAM, &kn7000_state::maincpu_mem);

	/* video hardware */
	// LCD panel. Exact geometry is uncertain: the KN7000 front-panel LCD is
	// reported as either 320x240 or 640x240. Using 640x240 as a placeholder.
	// TODO: confirm resolution, pixel clock and the LCD controller feeding
	//       the V-RAM at IC104.
	SCREEN(config, m_screen, SCREEN_TYPE_LCD);
	m_screen->set_refresh_hz(60);
	m_screen->set_vblank_time(ATTOSECONDS_IN_USEC(0));
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


ROM_START(kn7000)
	// ------------------------------------------------------------------
	// Both images below are the *decompressed* .SLD payloads taken from the
	// KN7000 system-update disks (Program update kn7-16 and Table update
	// kn7-14), reconstructed and checksum-verified by the kn7000_extraction
	// tool. They are the contents the updater writes into the on-board flash,
	// so they stand in for the physical flash dumps. Flagged BAD_DUMP because
	// they are derived from the update disks rather than read from the chips;
	// the CRC/SHA1 below are of the reconstructed images.
	// TODO: read IC16/IC17 (and the table ROMs) directly and, if the parts are
	//       interleaved, split these regions accordingly.
	// ------------------------------------------------------------------

	// Program flash -> mapped at CPU 0x48400000. Decompressed size 0x3F6F01.
	ROM_REGION32_LE(0x400000, "maincpu", ROMREGION_ERASEFF)
	ROM_LOAD("kn7000_program.rom", 0x000000, 0x3f6f01, BAD_DUMP CRC(d9399328) SHA1(cc1c364ce4fd8096eab4453825c0cc5e15009261))

	// Table / rhythm flash -> mapped at CPU 0x48000000. Decompressed size 0x3E94D4.
	ROM_REGION32_LE(0x400000, "table", ROMREGION_ERASEFF)
	ROM_LOAD("kn7000_table.rom", 0x000000, 0x3e94d4, BAD_DUMP CRC(eb3a0f01) SHA1(fcf5645a1a2300ff5e42e73b8f42ccd10a190d86))

	// TODO: Library / boot ROM at 0x4C000000 - currently undumped.
	//ROM_REGION(0x100000, "library", ROMREGION_ERASEFF)
	//ROM_LOAD("kn7000_library.rom", 0x000000, 0x100000, NO_DUMP)

	// TODO: Picture flash at 0x57800000 - not dumped yet.
	//ROM_REGION(0x800000, "picture", ROMREGION_ERASEFF)
	//ROM_LOAD("kn7000_picture.rom", 0x000000, 0x800000, NO_DUMP)
ROM_END

} // anonymous namespace


//   YEAR  NAME    PARENT  COMPAT  MACHINE  INPUT   CLASS         INIT        COMPANY     FULLNAME      FLAGS
SYST(2002, kn7000, 0,      0,      kn7000,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN7000", MACHINE_NOT_WORKING | MACHINE_NO_SOUND)
