// license:GPL2+
// copyright-holders:Felipe Sanches
/******************************************************************************

    Technics SX-KN5000 music keyboard driver

******************************************************************************/

#include "emu.h"

#include "kn5000_cpanel.h"
#include "kn5000_tonegen.h"

#include "bus/technics/kn5000/hdae5000.h"
#include "bus/midi/midi.h"
#include "cpu/tlcs900/tmp94c241.h"
#include "cpu/upd6383/upd6383.h"
#include "imagedev/floppy.h"
#include "machine/gen_latch.h"
#include "machine/nvram.h"
#include "machine/upd765.h"
#include "video/pc_vga.h"

#include "screen.h"
#include "speaker.h"

#include "kn5000.lh"

#include <queue>

class mn89304_vga_device : public svga_device
{
public:
	// construction/destruction
	mn89304_vga_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock = 0);

protected:
	virtual void device_reset() override ATTR_COLD;

	virtual void palette_update() override;
	virtual void recompute_params() override;
	virtual uint16_t offset() override;
};

DEFINE_DEVICE_TYPE(MN89304_VGA, mn89304_vga_device, "mn89304_vga", "MN89304 VGA")

// MN89304: Matsushita/Panasonic VGA-compatible LCD controller.
// Key differences from standard VGA:
// - 4-bit RAMDAC (12-bit RGB, not 18-bit) — handled by palette_update() using pal4bit()
// - Row offset has 8x multiplier — handled by offset() override
// - Extended sequencer registers (0x06-0x13) for LCD panel timing via indirect bank (SEQ[9-C])
// - Extended CRTC registers 0x19, 0x1A for LCD-specific configuration
// - Region-dependent LCD timing variant selected via SEQ[0x0F]
// - Firmware uses 320x240 8bpp indexed color, no hardware scrolling
// Related chip: MN89306 used on Taito TZ board (taitotz.cpp)
mn89304_vga_device::mn89304_vga_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: svga_device(mconfig, MN89304_VGA, tag, owner, clock)
{
}

void mn89304_vga_device::device_reset()
{
	svga_device::device_reset();
	svga.rgb8_en = 1;
}

// sets up mode 0, by default it will throw 155 Hz, assume divided by 3
void mn89304_vga_device::recompute_params()
{
	u8 xtal_select = (vga.miscellaneous_output & 0x0c) >> 2;
	int xtal;

	switch(xtal_select & 3)
	{
		case 0: xtal = XTAL(25'174'800).value() / 3; break;
		case 1: xtal = XTAL(28'636'363).value() / 3; break;
		case 2:
		default:
			throw emu_fatalerror("MN89304: setup ext. clock select");
	}

	recompute_params_clock(1, xtal);
}


void mn89304_vga_device::palette_update()
{
	// 4bpp RAMDAC
	for (int i = 0; i < 256; i++)
	{
		set_pen_color(
			i,
			pal4bit(vga.dac.color[3*(i & vga.dac.mask) + 0]),
			pal4bit(vga.dac.color[3*(i & vga.dac.mask) + 1]),
			pal4bit(vga.dac.color[3*(i & vga.dac.mask) + 2])
		);
	}
}

uint16_t mn89304_vga_device::offset()
{
	return svga_device::offset() << 3;
}


namespace {

// Logging macros for inter-CPU communication debugging
#define LOG_LATCH    (1U << 1)  // Latch read/write (command bytes only)
#define LOG_LATCH_DATA (1U << 2) // Latch read/write (all data bytes - very verbose)
#define LOG_HANDSHAKE (1U << 3) // MSTAT/SSTAT handshake changes
#define LOG_RESET    (1U << 4)  // Sub CPU reset control
#define LOG_KEYBED   (1U << 5)  // Tone generator keybed HLE events
#define LOG_ALL_LATCH (LOG_LATCH | LOG_LATCH_DATA)

#define VERBOSE (LOG_LATCH | LOG_RESET)
#include "logmacro.h"

class kn5000_state : public driver_device
{
public:
	kn5000_state(const machine_config &mconfig, device_type type, const char *tag)
		: driver_device(mconfig, type, tag)
		, m_cpanel(*this, "cpanel")
		, m_maincpu(*this, "maincpu")
		, m_subcpu(*this, "subcpu")
		, m_maincpu_latch(*this, "maincpu_latch")
		, m_subcpu_latch(*this, "subcpu_latch")
		, m_fdc(*this, "fdc")
		, m_floppy(*this, "fdc:0")
		, m_tonegen(*this, "tonegen")
		, m_dsp1(*this, "dsp1")
		, m_com_select(*this, "COM_SELECT")
		, m_extension(*this, "extension")
		, m_keybed(*this, "KEY%u", 0U)
		, m_checking_device_led_cn11(*this, "checking_device_led_cn11")
		, m_checking_device_led_cn12(*this, "checking_device_led_cn12")
		, m_mstat(0)
		, m_sstat(0)
		, m_cpanel_inta(0)
		, m_subcpu_latch_write_count(0)
		, m_maincpu_latch_write_count(0)
	{ }

	void kn5000(machine_config &config) ATTR_COLD;

protected:
	virtual void machine_start() override ATTR_COLD;
	virtual void machine_reset() override ATTR_COLD;

private:
	required_device<kn5000_cpanel_device> m_cpanel;
	required_device<tmp94c241_device> m_maincpu;
	required_device<tmp94c241_device> m_subcpu;
	required_device<generic_latch_8_device> m_maincpu_latch;
	required_device<generic_latch_8_device> m_subcpu_latch;
	required_device<upd72067_device> m_fdc;
	required_device<floppy_connector> m_floppy;
	required_device<kn5000_tonegen_device> m_tonegen;
	// IC311, the effects DSP -- an NEC uPD6383GF-3BA.  DRAFT CORE, held
	// DISABLED: the host interface is exercised and the uploaded microcode
	// lands in a real I-RAM, but the instruction set is not decoded, so
	// nothing executes and there is no audio from it.
	required_device<upd6383_device> m_dsp1;
	required_ioport m_com_select;
	required_device<kn5000_extension_connector> m_extension;

	// Panel button ports (CP{L,R}_SEG*) now live in kn5000_cpanel_device (device_input_ports()).
	required_ioport_array<6> m_keybed;   // 61-key keyboard (6 ports x 12 bits, last port 1 key)
	output_finder<> m_checking_device_led_cn11;
	output_finder<> m_checking_device_led_cn12;
	uint8_t m_mstat;
	uint8_t m_sstat;
	uint8_t m_subcpu_p7 = 0xff;  // Sub CPU port 7: DSP strobes / chip select / C-D
	uint8_t m_cpanel_inta;
	uint32_t m_subcpu_latch_write_count;
	uint32_t m_maincpu_latch_write_count;

	// A 4-channel x 8-register block at 0x130000, associated with IC311 but
	// NOT part of the uPD6383GF: it is a separate board-level register file
	// (written by DSP_Init_Channels, subcpu 0x01FC95, and DSP_Write_Channel,
	// 0x01FCDE).  An earlier revision wrongly modelled it as the DSP's
	// command/data port, which is why an upload capture hooked here saw
	// nothing but zeros.  Read-back model only.
	uint8_t m_dsp_reg_addr = 0;
	uint8_t m_dsp_regs[0x100]{};
	void dsp_reg_addr_w(uint16_t data);
	void dsp_reg_data_w(uint16_t data);
	uint16_t dsp_reg_data_r();

	// IC311's EXTERNAL delay memory = IC309, a 4-Mbit DRAM.  The uPD6383GF's
	// I-RAM, C-RAM and D-RAM are all on-die and are mapped by the device
	// itself; this one is a separate chip on this board, driven by the DSP's
	// own RAS/CAS/WE and A0-A16 lines, so it is the driver's to provide.
	void dsp1_delay_map(address_map &map) ATTR_COLD;

	// Latch access wrappers
	uint8_t subcpu_latch_r();
	uint8_t maincpu_latch_r();
	void subcpu_latch_w(uint8_t data);
	void maincpu_latch_w(uint8_t data);

	// Tone generator keybed scanning
	uint8_t m_keybed_prev[61];
	emu_timer *m_keybed_timer;
	TIMER_CALLBACK_MEMBER(keybed_scan);
	static constexpr uint8_t KEYBED_VELOCITY = 100; // fixed velocity for PC keyboard

	// ~NMI (SNS): on real hardware, the power supply asserts the CPU's NMI pin when
	// power is removed.  The ROM's NMI handler (NMI_StorePayloadChecksums at 0xEF08D4)
	// checks a guard flag in internal CPU RAM (0x0400 == 0x80), and if set, computes
	// payload checksums and stores them at DRAM[0xFFD4/0xFFD2] so that
	// SubCPU_Payload_Verify passes on the next boot, then halts the CPU.
	//
	// WE DO NOT MODEL THIS.  MAME's exit path calls eat_all_cycles() before NVRAM is
	// saved, so the real NMI handler cannot run at exit time.  A write tap used to
	// intercept Boot_DisplayScreen's clearing of DRAM[0xFFD4] and substitute the
	// checksums, but it was REMOVED in b1cf7db: the tap itself was the cause of the
	// "Sound Name Error" -- it made the firmware skip the maincpu->subcpu payload
	// transfer (upstream patch kn5000-29).
	//
	// So there is currently NO workaround, and the unmodelled power-down transaction
	// is the root of two visible defects: a virgin NVRAM grows a spurious "<Db>"
	// transpose on its own SECOND boot with no input at all, and the firmware's
	// power-off splash animation never runs.  See side-quests/pending/
	// kn5000_splash_animation.txt -- restoring it means EXECUTING the firmware's
	// power-off code, not substituting driver code for it.

	void nvram2_init(nvram_device &device, void *data, size_t size);
	void maincpu_mem(address_map &map) ATTR_COLD;
	void subcpu_mem(address_map &map) ATTR_COLD;
};

// Reading a latch de-asserts that CPU's /INT0 from inside the read handler
// (generic_latch_8_device::read() calls set_input_line(..., CLEAR_LINE)).  That
// clear is deferred by synchronize() until the end of the timeslice, so the
// level-detect re-assertion in the CPU core would keep re-raising the /INT0 flag
// on an already-released line -- firing the receive ISR many extra times per byte
// and corrupting the inter-CPU byte stream (a scrambled SubCPU payload, and
// "Sound Name Error" once the payload fails to answer command 0x2B).  Clear the
// level synchronously instead.
uint8_t kn5000_state::subcpu_latch_r()
{
	uint8_t const val = m_subcpu_latch->read();
	m_subcpu->clear_int0_level();
	return val;
}

uint8_t kn5000_state::maincpu_latch_r()
{
	uint8_t const val = m_maincpu_latch->read();
	m_maincpu->clear_int0_level();
	return val;
}

void kn5000_state::subcpu_latch_w(uint8_t data)
{
	m_subcpu_latch_write_count++;
	// Log command bytes (E1, E2, E3) and first few data bytes
	if (data == 0xe1 || data == 0xe2 || data == 0xe3)
		LOGMASKED(LOG_LATCH, "MainCPU -> SubCPU latch: cmd 0x%02X (write #%u) PC=%06X\n",
			data, m_subcpu_latch_write_count, m_maincpu->pc());
	else
		LOGMASKED(LOG_LATCH_DATA, "MainCPU -> SubCPU latch: 0x%02X (write #%u)\n",
			data, m_subcpu_latch_write_count);

	// Force tight CPU interleaving so subcpu HDMA can process each byte
	// before the next one is written. On real hardware, HDMA steals cycles
	// between main CPU instructions.
	machine().scheduler().perfect_quantum(attotime::from_usec(100));

	// Force-clear the latch pending state before writing.  On real hardware every
	// latch write raises a fresh /INT0 on the receiver, whether or not the previous
	// value was read.  generic_latch's pending callback only fires on a CHANGE, so
	// if the latch is still marked "written" -- which happens whenever the
	// receiver's ISR ran but declined to read because of the MSTAT/SSTAT handshake
	// -- the next write silently replaces the value and raises no interrupt.
	if (m_subcpu_latch->pending_r())
		m_subcpu_latch->acknowledge_w(0);

	m_subcpu_latch->write(data);

	// perfect_quantum() only constrains FUTURE scheduling, so without this the
	// writer would run on to the end of its timeslice and could push several more
	// bytes before the receiver ever gets to look at this one.  Yield now.
	m_maincpu->abort_timeslice();
}

void kn5000_state::maincpu_latch_w(uint8_t data)
{
	m_maincpu_latch_write_count++;
	if (data == 0xe1 || data == 0xe2 || data == 0xe3)
		LOGMASKED(LOG_LATCH, "SubCPU -> MainCPU latch: cmd 0x%02X (write #%u) PC=%06X\n",
			data, m_maincpu_latch_write_count, m_subcpu->pc());
	else
		LOGMASKED(LOG_LATCH_DATA, "SubCPU -> MainCPU latch: 0x%02X (write #%u)\n",
			data, m_maincpu_latch_write_count);

	// Same reasoning as subcpu_latch_w, in the reply direction: keep the main CPU's
	// DMAR-driven reads in step with the SubCPU's HDMA channel 2 writes, and make
	// each write raise a fresh /INT0.
	machine().scheduler().perfect_quantum(attotime::from_usec(100));

	if (m_maincpu_latch->pending_r())
		m_maincpu_latch->acknowledge_w(0);

	m_maincpu_latch->write(data);

	m_subcpu->abort_timeslice();
}

// Scan PC keyboard input ports and generate note-on/note-off events
// Called every 1ms by timer, matching real IC303 hardware scan rate
TIMER_CALLBACK_MEMBER(kn5000_state::keybed_scan)
{
	for (int port = 0; port < 6; port++)
	{
		uint16_t keys = m_keybed[port]->read();
		int num_keys = (port < 5) ? 12 : 1; // last port has only 1 key (C7)

		for (int bit = 0; bit < num_keys; bit++)
		{
			int raw_note = port * 12 + bit;
			uint8_t pressed = (keys >> bit) & 1;
			uint8_t prev = m_keybed_prev[raw_note];

			if (pressed && !prev)
			{
				// Key pressed: data = (velocity << 8) | (raw_note | 0x80)
				uint16_t data = (uint16_t(KEYBED_VELOCITY) << 8) | (raw_note | 0x80);
				m_tonegen->push_keybed_event(data);
				LOGMASKED(LOG_KEYBED, "Keybed: note ON raw=%d MIDI=%d vel=%d data=0x%04X\n",
					raw_note, raw_note + 0x24, KEYBED_VELOCITY, data);
			}
			else if (!pressed && prev)
			{
				// Key released: data = (0xFF << 8) | raw_note
				uint16_t data = (0xFF00) | raw_note;
				m_tonegen->push_keybed_event(data);
				LOGMASKED(LOG_KEYBED, "Keybed: note OFF raw=%d MIDI=%d data=0x%04X\n",
					raw_note, raw_note + 0x24, data);
			}
			m_keybed_prev[raw_note] = pressed;
		}
	}
}

void kn5000_state::maincpu_mem(address_map &map)
{
	map(0x000000, 0x0fffff).ram().share("nvram1"); // 1Mbyte = 2 * 4Mbit DRAMs @ IC9, IC10 (CS3)
	// Button states and LED control are handled via serial protocol to cpanel HLE device
	// Floppy Controller @ IC208 (UPD72068GF)
	// Register layout matches PC AT (smc37c78-style) with offsets doubled for 16-bit data bus:
	// MSR at offset 4 (address 0x110008), FIFO at offset 5 (address 0x11000A)
	map(0x110008, 0x110008).rw(m_fdc, FUNC(upd72067_device::msr_r), FUNC(upd72067_device::auxcmd_w));
	map(0x11000a, 0x11000a).rw(m_fdc, FUNC(upd72067_device::fifo_r), FUNC(upd72067_device::fifo_w));
	map(0x120000, 0x12ffff).rw(m_fdc, FUNC(upd72067_device::dma_r), FUNC(upd72067_device::dma_w)); // Floppy DMA Acknowledge
	map(0x140000, 0x14ffff).r(FUNC(kn5000_state::maincpu_latch_r)); // @ IC23
	map(0x140000, 0x14ffff).w(FUNC(kn5000_state::subcpu_latch_w)); // @ IC22 (logged wrapper)
	map(0x1703b0, 0x1703df).m("vga", FUNC(mn89304_vga_device::io_map)); // LCD controller @ IC206
	map(0x1a0000, 0x1dffff).rw("vga", FUNC(mn89304_vga_device::mem_linear_r), FUNC(mn89304_vga_device::mem_linear_w));
	map(0x1e0000, 0x1fffff).ram().share("nvram2"); // 1Mbit SRAM @ IC21 (CS0)  Note: I think this is the message "ERROR in back-up SRAM"
	map(0x300000, 0x3fffff).rom().region("custom_data", 0); // 8MBit FLASH ROM @ IC19 (CS5)
	map(0x400000, 0x7fffff).rom().region("rhythm_data", 0); // 32MBit ROM @ IC14 (A22=1 and CS5)
	// The subcpu payload is stored compressed in IC19 flash at 0x3E0000, which is part of the "custom_data" region above.
	map(0x800000, 0x9fffff).mirror(0x200000).rom().region("table_data", 0); //2 * 8MBit ROMs @ IC1, IC3 (CS2)
	map(0xe00000, 0xffffff).mask(0x1fffff).rom().region("program", 0); //2 * 8MBit FLASH ROMs @ IC4, IC6
}

void kn5000_state::subcpu_mem(address_map &map)
{
	map(0x000000, 0x0fffff).ram(); // 1Mbyte = 2 * 4Mbit DRAMs @ IC28, IC29
	map(0x100000, 0x100001).rw(m_tonegen, FUNC(kn5000_tonegen_device::status_r), FUNC(kn5000_tonegen_device::addr_w)); // Tone gen register address latch (write) / active-voice bitmap poll (read)
	map(0x100002, 0x100003).rw(m_tonegen, FUNC(kn5000_tonegen_device::data_r), FUNC(kn5000_tonegen_device::data_w)); // Tone gen register data
	map(0x110000, 0x110001).r(m_tonegen, FUNC(kn5000_tonegen_device::kbd_data_r));   // Tone gen keybed data
	map(0x110002, 0x110003).r(m_tonegen, FUNC(kn5000_tonegen_device::kbd_status_r)); // Tone gen keybed status
	map(0x120000, 0x12ffff).r(FUNC(kn5000_state::subcpu_latch_r)); // @ IC22
	map(0x120000, 0x12ffff).w(FUNC(kn5000_state::maincpu_latch_w)); // @ IC23 (logged wrapper)
	// A 4-channel x 8-register block associated with DSP1 @ IC311, written by
	// DSP_Init_Channels (subcpu 0x01FC95) / DSP_Write_Channel (0x01FCDE).
	// NOTE: this is NOT the uPD6383GF host interface -- the microprogram and coefficient
	// uploads go over Sub CPU port PZ with the port 7 strobes (see machine config).
	map(0x130000, 0x130001).w(FUNC(kn5000_state::dsp_reg_addr_w));   // register address
	map(0x130002, 0x130003).rw(FUNC(kn5000_state::dsp_reg_data_r), FUNC(kn5000_state::dsp_reg_data_w)); // register data
	map(0x1e0000, 0x1effff).noprw(); // Waveform/sample RAM (stub)
	map(0xfe0000, 0xffffff).rom().region("subcpu", 0); // 1Mbit MASK ROM @ IC30

	// DSP2 @ IC310 (MN19413) uses GPIO serial: PF.0=SDA, PF.2=SCLK, PE.6=CS2.
	// ---------------------------------------------------------------------
	// ---------------------------------------------------------------------
	// PROVENANCE (2026-07-22): the board facts below -- IC311's 25 MHz crystal,
	// IC310's 20 MHz, and the delay DRAMs IC309 = M5M44260AJ-7S and
	// IC308 = M5M418128AJ-6 -- were CONFIRMED BY FELIPE, who read them directly.
	// (An automated pass had cited him before he had actually been asked; he has
	// since verified them himself, so the attribution now stands.)
	// These are load-bearing: the delay-memory size sets where addresses wrap and
	// therefore every reverb tap length and delay time the emulation produces.
	//
	// STILL OPEN: the M5M44260 is organised 256K x 16, which needs 18 address bits
	// (9 row + 9 column), but the uPD6383GF's documented bus is A0-A16 -- 17 lines,
	// exactly half the part.  Either one bit is left unconnected and half the DRAM
	// is unused, or the KN5000 wires something the CDJ-500 block diagram does not
	// show.  AS_DELAY is deliberately mapped at what the DSP can defensibly
	// address rather than the full part, because the wrap point is what would
	// silently corrupt the reverb tap lengths.
	// ---------------------------------------------------------------------
	// Clocked by its own 20 MHz crystal (Felipe, verified), against the
	// 25 MHz one on IC311 -- two independent effect processors, two clocks.
	// NOT EMULATED AT ALL: no device, no capture, no audio. Its bodies
	// autocorrelate at lag 4, suggesting a 32-bit instruction word rather than
	// the uPD6383's 36 (notes/kn5000-dsp-INDEX.md backlog item 7).
	//
	// Its delay memory is IC308 = M5M418128AJ-6: a 1-Mbit DRAM, 8-BIT data bus
	// and 9 address pins, i.e. 131,072 words x 8 (row 9 + column 8 = 17 bits).
	// Self-consistent, and a quarter of the delay memory IC311 gets from IC309.
	// The 8-bit width is the interesting part and is NOT explained: 8-bit audio
	// samples would be far too coarse for a delay/reverb send, so either DSP2
	// takes two accesses per sample (16-bit samples in a byte-wide memory) or
	// it stores something companded. Worth settling before anyone models it.
}

void kn5000_state::dsp_reg_addr_w(uint16_t data)
{
	m_dsp_reg_addr = data & 0xff;
}

void kn5000_state::dsp_reg_data_w(uint16_t data)
{
	m_dsp_regs[m_dsp_reg_addr] = data & 0xff;
}

uint16_t kn5000_state::dsp_reg_data_r()
{
	return m_dsp_regs[m_dsp_reg_addr];
}


// --- IC311 (uPD6383GF) external digital-delay DRAM -------------------------

void kn5000_state::dsp1_delay_map(address_map &map)
{
	// IC309 = M5M44260AJ-7S (Felipe, verified): a Mitsubishi 4-Mbit
	// DRAM with a 16-BIT DATA BUS and 9 ADDRESS PINS, i.e. 262,144 words x 16
	// bits with the row and column addresses multiplexed over A0-A8 by RAS and
	// CAS in the usual way -- 9 + 9 = 18 address bits in total.
	//
	// The x16 organisation CORROBORATES the CDJ-500 block diagram, which shows
	// the delay memory reached through I/O1-16 while the DSP core is 24-bit:
	// the delay line really does store 16-bit samples, so a delayed sample is
	// truncated going out and coming back. That is a property of the hardware,
	// not an emulation shortcut, and it will matter once the core runs.
	//
	// HOW MUCH OF IT THE DSP REACHES IS NOT ESTABLISHED. The DRAM wants 18
	// multiplexed bits; the uPD6383GF's documented address bus is A0-A16, 17
	// lines, and it drives RAS/CAS/WE itself, so it is doing the multiplexing.
	// 17 bits addresses 131,072 words -- exactly HALF the part. Either one bit
	// is left off and half the DRAM is unused (routine when the bigger part is
	// the cheaper or the second-sourced one), or the KN5000 wires something the
	// CDJ-500 diagram does not show. So this maps what the DSP can defensibly
	// address, not what the part holds. Do NOT quietly widen it to 256K: the
	// delay TIMES depend on where the address wraps, and the reverb tap lengths
	// in notes/kn5000-dsp-reverb.md are the thing that would go wrong.
	//
	// What would settle it: which of the DSP's address pins actually reach
	// IC309's A0-A8 on the board, or a measured delay time once the core runs.
	map(0x00000, 0x1ffff).ram();      // 128K words x 16 bits (A0-A16)
}


static void kn5000_floppies(device_slot_interface &device)
{
	device.option_add("35hd", FLOPPY_35_HD);
	device.option_add("35dd", FLOPPY_35_DD);
}

static INPUT_PORTS_START(kn5000)
	PORT_START("CN11")
	PORT_DIPNAME(0x01, 0x01, "Main CPU Checking Device")
	PORT_DIPSETTING(   0x00, DEF_STR(On))
	PORT_DIPSETTING(   0x01, DEF_STR(Off))

	PORT_START("CN12")
	PORT_DIPNAME(0x01, 0x01, "Sub CPU Checking Device")
	PORT_DIPSETTING(   0x00, DEF_STR(On))
	PORT_DIPSETTING(   0x01, DEF_STR(Off))

	PORT_START("COM_SELECT")
	PORT_DIPNAME(0xf0, 0xe0, "Computer Interface Selection")
	PORT_DIPSETTING(   0xe0, "MIDI")
	PORT_DIPSETTING(   0xd0, "PC1")
	PORT_DIPSETTING(   0xb0, "PC2")
	PORT_DIPSETTING(   0x70, "Mac")

	PORT_START("AREA")
	PORT_DIPNAME(0x06, 0x06, "Area Selection")
	PORT_DIPSETTING(   0x02, "Thailand, Indonesia, Iran, U.A.E., Panama, Argentina, Peru, Brazil")
	PORT_DIPSETTING(   0x04, "USA, Mexico")
	PORT_DIPSETTING(   0x06, "Other")

/*
    Actual full list of regions (but it is unclear if there's any
    other hardware difference among them):

    PORT_DIPSETTING(   0x04, "(M): U.S.A.")
    PORT_DIPSETTING(   0x06, "(MC): Canada")
    PORT_DIPSETTING(   0x04, "(XM): Mexico")
    PORT_DIPSETTING(   0x06, "(EN): Norway, Sweden, Denmark, Finland")
    PORT_DIPSETTING(   0x06, "(EH): Holland, Belgium")
    PORT_DIPSETTING(   0x06, "(EF): France, Italy")
    PORT_DIPSETTING(   0x06, "(EZ): Germany")
    PORT_DIPSETTING(   0x06, "(EW): Switzerland")
    PORT_DIPSETTING(   0x06, "(EA): Austria")
    PORT_DIPSETTING(   0x06, "(EP): Spain, Portugal, Greece, South Africa")
    PORT_DIPSETTING(   0x06, "(EK): United Kingdom")
    PORT_DIPSETTING(   0x06, "(XL): New Zealand")
    PORT_DIPSETTING(   0x06, "(XR): Australia")
    PORT_DIPSETTING(   0x06, "(XS): Malaysia")
    PORT_DIPSETTING(   0x06, "(MD): Saudi Arabia, Hong Kong, Kuwait")
    PORT_DIPSETTING(   0x06, "(XT): Taiwan")
    PORT_DIPSETTING(   0x02, "(X): Thailand, Indonesia, Iran, U.A.E., Panama, Argentina, Peru, Brazil")
    PORT_DIPSETTING(   0x06, "(XP): Philippines")
    PORT_DIPSETTING(   0x06, "(XW): Singapore")
*/

	// The front-panel BUTTON scan matrix (CP{L,R}_SEG*) is declared by the control-panel
	// device itself now (kn5000_cpanel_device::device_input_ports(), in kn5000_cpanel.cpp) --
	// the panel sub-CPUs own those inputs. The layout references them as "cpanel:CP*_SEG*".


	// 61-key keyboard (C2-C7) — directly connected to tone generator IC303
	// IC303 does hardware key scanning; this HLE injects events at 0x110000
	// PC keyboard mapping: Z-row = lower octave, Q-row = upper octave (piano layout)
	// Base octave = C4 (raw notes 24-47 for the two mapped octaves)

	PORT_START("KEY0")  // C2-B2 (raw notes 0-11, MIDI 36-47)
	PORT_BIT( 0x001, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C2")
	PORT_BIT( 0x002, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C#2")
	PORT_BIT( 0x004, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D2")
	PORT_BIT( 0x008, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D#2")
	PORT_BIT( 0x010, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("E2")
	PORT_BIT( 0x020, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F2")
	PORT_BIT( 0x040, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F#2")
	PORT_BIT( 0x080, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G2")
	PORT_BIT( 0x100, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G#2")
	PORT_BIT( 0x200, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A2")
	PORT_BIT( 0x400, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A#2")
	PORT_BIT( 0x800, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("B2")

	PORT_START("KEY1")  // C3-B3 (raw notes 12-23, MIDI 48-59)
	PORT_BIT( 0x001, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C3")
	PORT_BIT( 0x002, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C#3")
	PORT_BIT( 0x004, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D3")
	PORT_BIT( 0x008, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D#3")
	PORT_BIT( 0x010, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("E3")
	PORT_BIT( 0x020, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F3")
	PORT_BIT( 0x040, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F#3")
	PORT_BIT( 0x080, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G3")
	PORT_BIT( 0x100, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G#3")
	PORT_BIT( 0x200, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A3")
	PORT_BIT( 0x400, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A#3")
	PORT_BIT( 0x800, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("B3")

	// KEY2 and KEY3 have no default PORT_CODE assignments because all candidate
	// keys (Z/S/X/D/C/V/G/B/H/N/J/M, Q/2/W/3/E/R/5/T/6/Y/7/U) conflict with
	// control panel button mappings above. Use MAME's input configuration UI
	// (Tab menu) to assign keyboard keys to these notes.

	PORT_START("KEY2")  // C4-B4 (raw notes 24-35, MIDI 60-71) — Middle C octave
	PORT_BIT( 0x001, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C4")
	PORT_BIT( 0x002, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C#4")
	PORT_BIT( 0x004, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D4")
	PORT_BIT( 0x008, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D#4")
	PORT_BIT( 0x010, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("E4")
	PORT_BIT( 0x020, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F4")
	PORT_BIT( 0x040, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F#4")
	PORT_BIT( 0x080, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G4")
	PORT_BIT( 0x100, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G#4")
	PORT_BIT( 0x200, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A4")
	PORT_BIT( 0x400, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A#4")
	PORT_BIT( 0x800, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("B4")

	PORT_START("KEY3")  // C5-B5 (raw notes 36-47, MIDI 72-83)
	PORT_BIT( 0x001, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C5")
	PORT_BIT( 0x002, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C#5")
	PORT_BIT( 0x004, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D5")
	PORT_BIT( 0x008, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D#5")
	PORT_BIT( 0x010, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("E5")
	PORT_BIT( 0x020, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F5")
	PORT_BIT( 0x040, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F#5")
	PORT_BIT( 0x080, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G5")
	PORT_BIT( 0x100, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G#5")
	PORT_BIT( 0x200, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A5")
	PORT_BIT( 0x400, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A#5")
	PORT_BIT( 0x800, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("B5")

	PORT_START("KEY4")  // C6-B6 (raw notes 48-59, MIDI 84-95)
	PORT_BIT( 0x001, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C6")
	PORT_BIT( 0x002, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C#6")
	PORT_BIT( 0x004, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D6")
	PORT_BIT( 0x008, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D#6")
	PORT_BIT( 0x010, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("E6")
	PORT_BIT( 0x020, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F6")
	PORT_BIT( 0x040, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F#6")
	PORT_BIT( 0x080, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G6")
	PORT_BIT( 0x100, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G#6")
	PORT_BIT( 0x200, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A6")
	PORT_BIT( 0x400, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A#6")
	PORT_BIT( 0x800, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("B6")

	PORT_START("KEY5")  // C7 (raw note 60, MIDI 96) — highest key
	PORT_BIT( 0x001, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C7")
	PORT_BIT( 0xffe, IP_ACTIVE_HIGH, IPT_UNUSED )
INPUT_PORTS_END


void kn5000_state::machine_start()
{
	save_item(NAME(m_mstat));
	save_item(NAME(m_sstat));
	save_item(NAME(m_cpanel_inta));
	save_item(NAME(m_subcpu_latch_write_count));
	save_item(NAME(m_maincpu_latch_write_count));
	save_item(NAME(m_keybed_prev));
	save_item(NAME(m_dsp_reg_addr));
	save_item(NAME(m_dsp_regs));

	m_extension->program_map(m_maincpu->space(AS_PROGRAM));



	// Keybed scan timer: poll keyboard input ports every 1ms
	std::fill(std::begin(m_keybed_prev), std::end(m_keybed_prev), 0);
	m_keybed_timer = timer_alloc(FUNC(kn5000_state::keybed_scan), this);
	m_keybed_timer->adjust(attotime::from_msec(1), 0, attotime::from_msec(1));

	// NOTE: an earlier "SNS payload-checksum" write tap on DRAM[0xFFD4] was REMOVED
	// here (2026-07-20) — it was the root cause of the KN5000 "Sound Name Error".
	//
	// Boot_DisplayScreen clears DRAM[0xFFD4] to 0 during boot.  The firmware's
	// SubCPU_Payload_Verify treats a zero there as "no valid stored payload
	// checksum" and therefore performs a FRESH decompress-and-transfer of the
	// SubCPU firmware payload over the inter-CPU latch.  The old tap intercepted
	// that clear and substituted a checksum computed from the DRAM checksum
	// regions (0xF180/0xF980) as they stood at that early instant — before those
	// regions hold the values the verify expects — so the firmware instead took
	// the "payload already valid, skip the transfer" path.  The SubCPU then ran
	// with no (or stale) firmware and never answered the MainCPU's 0x2B sound-name
	// query: RIGHT1/RIGHT2/LEFT showed "Sound Name Error".  This also matches
	// upstream mainline MAME, whose kn5000 has no such tap and boots to real voice
	// names.  With the tap gone, the SubCPU receives its payload, its cooperative
	// scheduler stays healthy (XSSP bounded, no stack leak), and it replies to the
	// name query.  See side-quests/findings/kn5000_driver_findings.md.
}

void kn5000_state::machine_reset()
{
	m_checking_device_led_cn11 = 0;
	m_checking_device_led_cn12 = 0;

	// Clear keybed state
	std::fill(std::begin(m_keybed_prev), std::end(m_keybed_prev), 0);

}



void kn5000_state::nvram2_init(nvram_device &device, void *data, size_t size)
{
	// Initialize NVRAM with factory defaults from program ROM.
	// On real hardware, NVRAM (backup SRAM) is pre-programmed at the factory.
	// Without valid data, the firmware fails header/checksum validation and
	// skips Sub-CPU payload transfer, causing incomplete initialization.
	//
	// Factory defaults location in v10 ROM: offset 0x0A0150 (0x72A6 bytes)
	// Header: "KN5000 SOUND RAM" (16 bytes), followed by settings data.
	// Checksum: one's complement of sum of 0x24B8 LE words from offset 0x10,
	// stored at offset 0x72A8.
	uint8_t *dest = reinterpret_cast<uint8_t *>(data);
	std::fill_n(dest, size, 0);

	const uint8_t *rom = memregion("program")->base();
	static constexpr uint32_t FACTORY_DEFAULTS_ROM_OFFSET = 0x0A0150;
	static constexpr uint32_t FACTORY_DEFAULTS_SIZE = 0x72A6;
	static constexpr uint32_t CHECKSUM_WORD_COUNT = 0x24B8;
	static constexpr uint32_t CHECKSUM_DATA_OFFSET = 0x10;
	static constexpr uint32_t CHECKSUM_STORE_OFFSET = 0x72A8;

	std::copy_n(rom + FACTORY_DEFAULTS_ROM_OFFSET, FACTORY_DEFAULTS_SIZE, dest);

	// Compute checksum matching firmware's validation routine (LABEL_FEF93B):
	// ADD DE, (XWA+) loop over 0x24B8 words, then CPL DE
	uint16_t sum = 0;
	for (uint32_t i = 0; i < CHECKSUM_WORD_COUNT; i++)
	{
		uint32_t offset = CHECKSUM_DATA_OFFSET + i * 2;
		uint16_t word = dest[offset] | (dest[offset + 1] << 8);
		sum += word;
	}
	uint16_t checksum = ~sum;
	dest[CHECKSUM_STORE_OFFSET] = checksum & 0xFF;
	dest[CHECKSUM_STORE_OFFSET + 1] = (checksum >> 8) & 0xFF;
}

void kn5000_state::kn5000(machine_config &config)
{
	// Note: The CPU has an internal clock doubler
	TMP94C241(config, m_maincpu, 2 * 8_MHz_XTAL); // TMP94C241F @ IC5
	// Address bus is set to 32 bits by the pins AM1=+5v and AM0=GND
	m_maincpu->set_addrmap(AS_PROGRAM, &kn5000_state::maincpu_mem);
	// Interrupt 4: FDCINT
	// Interrupt 5: FDCIRQ
	// Interrupt 6: FDC.H/D // NOTE: interrupt handler is empty
	// Interrupt 7: FDC.I/O // NOTE: interrupt handler is empty
	// Interrupt 9: HDDINT
	// Interrupt A <edge>: ~CPSCK "Control Panel Serial Clock"
	// ~NMI: SNS
	// TC0: FDCTC — Timer 0 match output pulses FDC Terminal Count
	m_maincpu->to0_callback().set(m_fdc, FUNC(upd72067_device::tc_line_w));


	// MAINCPU PORT 7:
	//   bit 5 (~BUSRQ pin): RY/~BY pin of maincpu ROMs
	m_maincpu->port7_read().set_constant(0x20); // bit 5: checked at EF3735 (v10 ROM)


	// MAINCPU PORT 8:
	//   bit 6 (~WAIT pin) (input): Something involving VGA.RDY, FDC.DMAACK
	//                              and shift-register @ IC18


	// MAINCPU PORT A:
	//   bit 0 (output) = sub_cpu ~RESET / SRST
	m_maincpu->porta_write().set(
			[this] (u8 data) {
				m_subcpu->set_input_line(INPUT_LINE_RESET, BIT(data, 0) ? CLEAR_LINE : ASSERT_LINE);
			});

	// MAINCPU PORT C:
	//   bit 0 (input) = "check terminal" switch
	//   bit 1 (output) = "check terminal" LED
	m_maincpu->portc_read().set_ioport("CN11");
	m_maincpu->portc_write().set(
			[this] (u8 data) {
				m_checking_device_led_cn11 = BIT(~data, 1);
			});


	// MAINCPU PORT D:
	//   bit 0 (output) = FDCRST
	//   bit 6 (input) = FD.I/O
	m_maincpu->portd_write().set(m_fdc, FUNC(upd72067_device::reset_w)).bit(0);
	m_maincpu->portd_read().set([this] {
		// bit 6 = FD.I/O: floppy disk change signal (active low on hardware)
		// MAME's dskchg_r() returns 1 = "change detected" (active high), so
		// invert for the active-low hardware signal the firmware expects.
		floppy_image_device *floppy = m_floppy->get_device();
		return floppy ? ((!floppy->dskchg_r()) << 6) : 0x00;
	});


	// MAINCPU PORT E:
	//   bit 0 (input) = +5v
	//   bit 2 (input) = HDDRDY
	//   bit 4 (?) = MICSNS
	//   bit 5 (input) = INTA (control panel interrupt)
	m_maincpu->porte_read().set(
			[this] {
				// Bit 0: +5v (always 1 when no HDD extension)
				// Bit 5: INTA from control panel (active HIGH — firmware checks BIT 5,(PE); JR NZ)
				return 0x01 | (m_cpanel_inta ? 0x20 : 0x00);
			});


	// MAINCPU PORT F: shared with serial interface pins
	//   bit 0 = TXD0 (MIDI TX)
	//   bit 1 = RXD0 (MIDI RX)
	//   bit 2 = SCLK0 (disabled by firmware — MIDI uses no clock)
	//   bit 4 = TXD1 (control panel data)
	//   bit 5 = RXD1 (control panel data)
	//   bit 6 (input) = SCLK1 pin state — a routine in the main CPU's
	//     implementation of the control panel protocol polls this to confirm
	//     the serial clock is idle (HIGH) before sending commands.
	//     Without it, the firmware times out after 200 retries and displays
	//     "ERROR in CPU data transmission".
	m_maincpu->portf_read().set_constant(0x40);


	// MAINCPU PORT G:
	//   bit 2 (input) = FS1  (Foot Switches and Foot Controler ?)
	//   bit 3 (input) = FS2
	//   bit 4 (input) = FC1
	//   bit 5 (input) = FC2
	//   bit 6 (input) = FC3
	//   bit 7 (input) = FC4


	// MAINCPU PORT H:
	m_maincpu->porth_read().set_ioport("AREA"); // checked at EF083E (v10 ROM)


	// MAINCPU PORT Z:
	//   bit 0 = (output) MSTAT0
	//   bit 1 = (output) MSTAT1
	//   bit 2 = (input) SSTAT0
	//   bit 3 = (input) SSTAT1
	//   bit 4 = (input) COM.PC2
	//   bit 5 = (input) COM.PC1
	//   bit 6 = (input) COM.MAC
	//   bit 7 = (input) COM.MIDI
	m_maincpu->portz_read().set(
			[this] {
				// bits 0-1: MSTAT — the MainCPU's own outputs; do NOT OR them into
				//   the read here.  The last-known-good state
				//   (kn5000_aided_by_claude @ 2026-02-17, commit f8cd34a8) reads back
				//   only SSTAT and COM_SELECT; the firmware polls Port Z for the sub
				//   CPU's SSTAT to pace the inter-CPU transfer.  The branch tip
				//   (6897868, 2026-03-09) added the "MSTAT readback", and the earlier
				//   kn5000-27 "parity" fix mistakenly matched that tip — feeding the
				//   MainCPU its own MSTAT makes it mis-read the handshake and stream
				//   the payload without pacing, which starves the SubCPU scheduler.
				//   See side-quests/findings/kn5000_driver_findings.md.
				// bits 2-3: SSTAT (input from the sub CPU)
				// bits 4-7: COM_SELECT (interface-selection switches)
				return m_com_select->read() | (m_sstat << 2);
			});
	m_maincpu->portz_write().set(
			[this] (u8 data) {
				m_mstat = data & 3;
			});


	// RX0/TX0 = MRXD/MTXD (MIDI)
	auto &mdin(MIDI_PORT(config, "mdin"));
	midiin_slot(mdin);
	mdin.rxd_handler().set(m_maincpu, FUNC(tmp94c241_device::rxd0));

	// TX0 = MTXD (MIDI output)
	auto &mdout(MIDI_PORT(config, "mdout"));
	midiout_slot(mdout);
	m_maincpu->txd0().set("mdout", FUNC(midi_port_device::write_txd));

	// RX1/TX1 = CPDATA, SCLK1 = CPSCK — wired to control panel HLE
	KN5000_CPANEL(config, m_cpanel);
	m_maincpu->txd1().set(m_cpanel, FUNC(kn5000_cpanel_device::rxd));
	m_maincpu->sclk1_out().set(m_cpanel, FUNC(kn5000_cpanel_device::sioclk));
	m_maincpu->tx1_start().set(m_cpanel, FUNC(kn5000_cpanel_device::tx_start));
	m_cpanel->txd().set(m_maincpu, FUNC(tmp94c241_device::rxd1));
	m_cpanel->sclk_out().set(m_maincpu, FUNC(tmp94c241_device::sioclk1));
	m_cpanel->inta().set(
			[this] (int state) {
				m_cpanel_inta = state;
				m_maincpu->set_input_line(TLCS900_INTA, state ? ASSERT_LINE : CLEAR_LINE);
			});

	// The button input ports are declared by the control-panel device itself now
	// (kn5000_cpanel_device::device_input_ports()); no wiring needed here.

	// AN0 = EXP (expression pedal?)
	// AN1 = AFT

	// Note: The CPU has an internal clock doubler
	TMP94C241(config, m_subcpu, 2*10_MHz_XTAL); // TMP94C241F @ IC27
	// Address bus is set to 8 bits by the pins AM1=GND and AM0=GND
	m_subcpu->set_addrmap(AS_PROGRAM, &kn5000_state::subcpu_mem);

	// SUBCPU PORT C:
	//   bit 0 (input) = "check terminal" switch
	//   bit 1 (output) = "check terminal" LED
	m_subcpu->portc_read().set_ioport("CN12");
	m_subcpu->portc_write().set(
			[this] (u8 data) {
				m_checking_device_led_cn12 = (BIT(data, 1) == 0);
			});


	// SUBCPU PORT D:
	//   bit 0 = (output) SSTAT0
	//   bit 1 = (output) SSTAT1
	//   bit 2 = (input) MSTAT0
	//   bit 3 (not used)
	//   bit 4 = (input) MSTAT1
	m_subcpu->portd_read().set(
			[this] {
				return (BIT(m_mstat, 0) << 2) | (BIT(m_mstat, 1) << 4);
			});
	m_subcpu->portd_write().set(
			[this] (u8 data) {
				m_sstat = data & 3;
			});


	// SUBCPU PORT 7 + PORT Z: the uPD6383GF (IC311) host interface (uC-IF).
	//
	// THIS is where every DSP microprogram and coefficient byte travels -- NOT the
	// 0x130000 register block, which is a separate 4x8 register file. From the v1.42
	// Sub CPU ROM:
	//   DSP_Set_Command_Mode  0x0383A7  RES 6,(P7)   C/D = 0 -> command
	//   DSP_Set_Data_Mode     0x0383AB  SET 6,(P7)   C/D = 1 -> data
	//   DSP_Assert_Write      0x0383AF  RES 3,(P7)   /WRITE (active low)
	//   DSP_Assert_Read_Data  0x0383B7  RES 4,(P7)   /READ  (active low)
	//   DSP_Select_Chip       0x0383CB  RES 5,(P7)   /CS DSP1 (active low; DSP2 = PE.6)
	//   the byte itself is written to (PZ) inside DSP_Send_Command / DSP_Send_Data
	m_subcpu->port7_write().set(
			[this] (u8 data) {
				m_subcpu_p7 = data;
			});
	m_subcpu->portz_write().set(
			[this] (u8 data) {
				// Only capture while DSP1 is selected (P7.5 low). P7.6 is C/D.
				if (!BIT(m_subcpu_p7, 5))
					m_dsp1->host_w(BIT(m_subcpu_p7, 6), data);
			});

	// SUBCPU PORT H:
	//   bit 0 (input) = DSP1 (IC311) ready signal (active high)
	//   bit 1 (output) = DSP1 reset (active low)
	//   On real hardware, the DSP asserts this line after accepting a command.
	//   Always ready since the DSP1 stub accepts all register writes immediately.
	m_subcpu->porth_read().set_constant(0x01);


	GENERIC_LATCH_8(config, m_maincpu_latch); // @ IC23
	m_maincpu_latch->data_pending_callback().set_inputline(m_maincpu, TLCS900_INT0);

	GENERIC_LATCH_8(config, m_subcpu_latch); //  @ IC22
	m_subcpu_latch->data_pending_callback().set_inputline(m_subcpu, TLCS900_INT0);

	UPD72067(config, m_fdc, 32'000'000); // actual controller is UPD72068GF-3B9 at IC208
	m_fdc->intrq_wr_callback().set_inputline(m_maincpu, TLCS900_INT4);
	m_fdc->drq_wr_callback().set_inputline(m_maincpu, TLCS900_INT5);
	// Review:
	// Interrupt 4: FDCINT
	// Interrupt 5: FDCIRQ


	// NOTE: int6 and int7 handlers are empty routines
	// Interrupt 6: FDC.H/D
	// Interrupt 7: FDC.I/O
	//
	// m_fdc->hdl_wr_callback().set_inputline(m_maincpu, TLCS900_INT6);
	// TC is wired above via m_maincpu->to0_callback()
	// m_fdc->??_wr_callback().set_inputline(m_maincpu, TLCS900_INT7);


	FLOPPY_CONNECTOR(config, "fdc:0", kn5000_floppies, "35hd", floppy_image_device::default_mfm_floppy_formats).enable_sound(true);

	// Extension port
	KN5000_EXTENSION(config, m_extension, kn5000_extension_intf, nullptr);
	m_extension->irq_callback().set_inputline(m_maincpu, TLCS900_INT9);

	// video hardware
	// LCD Controller MN89304 @ IC206 24_MHz_XTAL
	screen_device &screen(SCREEN(config, "screen", SCREEN_TYPE_LCD));
	screen.set_raw(XTAL(40'000'000)/6, 424, 0, 320, 262, 0, 240);
	screen.set_screen_update("vga", FUNC(mn89304_vga_device::screen_update));

	mn89304_vga_device &vga(MN89304_VGA(config, "vga"));
	vga.set_screen("screen");
	// 4 Mbit, M5M44265CJ6S
	vga.set_vram_size(0x80000);
	// iochrdy tied to refresh pin and SA19, A21 and A20 to GND
	// VGA.A18 signal from maincpu thru T7W139F (IC12) decoder selects upper/lower 256KB
	// bank of the 512KB VRAM chip. Firmware only uses the lower bank (~153KB for two
	// 320x240 framebuffer pages), so banking is not emulated.

	// audio hardware
	SPEAKER(config, "lspeaker").front_left();
	SPEAKER(config, "rspeaker").front_right();

	// IC311: NEC uPD6383GF-3BA effects DSP, clocked by its own 25 MHz crystal
	// (Felipe, verified -- this replaces an earlier NOMINAL 16.9344 MHz
	// that was reverse-engineered from "384 words per 44.1 kHz frame").
	//
	// Worth noting because it is a consistency check on the whole execution
	// model: the sample rate is 44,100 Hz (established from the firmware's own
	// ms x 0xAC44 / 0x3E8) and is set by the audio clocks on BCLKI/LRCKI/XFsI,
	// NOT by this crystal. 25 MHz / 44.1 kHz = 567 cycles per sample frame,
	// comfortably more than the 384 words of I-RAM. So "the PC sweeps I-RAM
	// once per sample frame", which is what the Fs-RST / PC-RST pins and the
	// straight-line effect bodies imply (notes/kn5000-dsp-encoding.md sect. 6),
	// FITS -- with room to spare, as it must, since real instructions may take
	// more than one cycle.
	UPD6383(config, m_dsp1, 25_MHz_XTAL);
	// I-RAM, C-RAM and D-RAM are on-die and the device maps them itself; only
	// the external digital-delay DRAM is this board's business.
	m_dsp1->set_addrmap(AS_DELAY, &kn5000_state::dsp1_delay_map);
	// HELD DISABLED ON PURPOSE.  The instruction set is not decoded, so the
	// core must not execute: a partially-correct effects DSP is exactly the
	// failure mode that produced audible-but-wrong sound on the KN7000.  What
	// we want from it today is its I-RAM -- a real, addressable,
	// debugger-visible copy of the uploaded microcode.  Remove this only when
	// the ISA justifies it.
	m_dsp1->set_disable();
	// research instrumentation: dump the host upload stream at exit
	m_dsp1->set_capture_file("kn5000_dsp1_upload");

	KN5000_TONEGEN(config, m_tonegen, 0);
	m_tonegen->add_route(0, "lspeaker", 1.0);
	m_tonegen->add_route(1, "rspeaker", 1.0);

	NVRAM(config, "nvram1", nvram_device::DEFAULT_ALL_0);
	NVRAM(config, "nvram2").set_custom_handler(FUNC(kn5000_state::nvram2_init));

	config.set_default_layout(layout_kn5000);
}

ROM_START(kn5000)
	ROM_DEFAULT_BIOS("v10")
	ROM_SYSTEM_BIOS(0, "v10", "Version 10 - August 2nd, 1999")
	ROM_SYSTEM_BIOS(1, "v9", "Version 9 - January 26th, 1999")
	ROM_SYSTEM_BIOS(2, "v8", "Version 8 - November 13th, 1998")
	ROM_SYSTEM_BIOS(3, "v7", "Version 7 - June 26th, 1998")
	ROM_SYSTEM_BIOS(4, "v6", "Version 6 - January 16th, 1998") // sometimes refered to as "update6v0"
	ROM_SYSTEM_BIOS(5, "v5", "Version 5 - November 12th, 1997") // sometimes refered to as "update5v0"
	ROM_SYSTEM_BIOS(6, "v4", "Version 4") // I have a v4 board but haven't dumped it yet
	ROM_SYSTEM_BIOS(7, "v3", "Version 3") // I have a v3 board but haven't dumped it yet

	ROM_REGION16_LE(0x200000, "program" , 0) // main cpu

	// FIXME: These are actually stored in a couple flash rom chips IC6 (even) and IC4 (odd)
	//
	// Note: These ROMs from v5 to v10 were extracted from the system update floppies
	//       which were compressed using LZSS.
	//
	//       System update disks for older versions were not found yet, so dumping
	//       efforts will require other methods.
	//
	//       More info at:
	//       https://github.com/felipesanches/kn5000_homebrew/blob/main/kn5000_extract.py

	ROMX_LOAD("kn5000_v10_program.rom", 0x00000, 0x200000, CRC(00303406) SHA1(1f2abc5b1b7b9e16fdf796f26d939edaceded354), ROM_BIOS(0))
	ROMX_LOAD("kn5000_v9_program.rom",  0x00000, 0x200000, CRC(c791d765) SHA1(d9a3b462b1f9302402e8d37aacd15f069f56abd9), ROM_BIOS(1))
	ROMX_LOAD("kn5000_v8_program.rom",  0x00000, 0x200000, CRC(46b4b242) SHA1(a10a6f5a35175b74c3cfb42cef3bdf571c2858bb), ROM_BIOS(2))
	ROMX_LOAD("kn5000_v7_program.rom",  0x00000, 0x200000, CRC(a5a25eb0) SHA1(4c682cb248034a2de04c688b0a45654b8726bffb), ROM_BIOS(3))
	ROMX_LOAD("kn5000_v6_program.rom",  0x00000, 0x200000, CRC(0205db30) SHA1(51108e2d75b180a034395e90bd40ca2bd2a0adfb), ROM_BIOS(4))
	ROMX_LOAD("kn5000_v5_program.rom",  0x00000, 0x200000, CRC(fbd035e3) SHA1(7b69a8aaa84ee3d337acc0c29c34154c5da2df32), ROM_BIOS(5))
	ROMX_LOAD("kn5000_v4_program.rom",  0x00000, 0x200000, NO_DUMP, ROM_BIOS(6))
	ROMX_LOAD("kn5000_v3_program.rom",  0x00000, 0x200000, NO_DUMP, ROM_BIOS(7))

	// Note: I've never seen boards with versions 1 or 2.

	ROM_REGION16_LE(0x20000, "subcpu", 0)
	ROM_LOAD("kn5000_subcpu_boot.ic30", 0x00000, 0x20000, BAD_DUMP CRC(a45ceb77) SHA1(d29429a9a1ef7a718fa88c1aa38d0f7238ba5d94)) // Ranges fe0800-ff7800 and ff9800-fff000 not dumped yet. Assumed here as being filled with 0xFF.

	ROM_REGION16_LE(0x200000, "table_data", 0)
	ROM_LOAD32_WORD("kn5000_table_data_rom_even.ic3", 0x000000, 0x100000, CRC(b6f0becd) SHA1(1fd2604236b8d12ea7281fad64d72746eb00c525))
	ROM_LOAD32_WORD("kn5000_table_data_rom_odd.ic1",  0x000002, 0x100000, CRC(cd907eac) SHA1(bedf09d606d476f3e6d03e590709715304cf7ea5))

	ROM_REGION16_LE(0x100000, "custom_data", 0)
	ROM_LOAD("kn5000_custom_data_rom.ic19", 0x000000, 0x100000, CRC(5de11a6b) SHA1(4709f815d3d03ce749c51f4af78c62bf4a5e3d94))
	// IC19 is a flash ROM. The contents here were dumped from a system that had it already programmed by the initial data disk.
	//
	// The subcpu payload is stored compressed (LZSS SLIDE4K format) in IC19 flash at address 0x3E0000 (offset 0xE0000).
	// During boot, the maincpu decompresses it and transfers it to the subcpu RAM via the inter-cpu latches.
	// The compressed payloads below were extracted from the system update floppy disk images.
	ROMX_LOAD("kn5000_subprogram_v142_compressed.rom", 0x0e0000, 0x16c13, CRC(f81e598f) SHA1(13718900afd55cb2e5ff0be213ba1f5dd14bc174), ROM_BIOS(0)) // v10
	ROMX_LOAD("kn5000_subprogram_v142_compressed.rom", 0x0e0000, 0x16c13, CRC(f81e598f) SHA1(13718900afd55cb2e5ff0be213ba1f5dd14bc174), ROM_BIOS(1)) // v9
	ROMX_LOAD("kn5000_subprogram_v141_compressed.rom", 0x0e0000, 0x16bfd, CRC(c6d4ad98) SHA1(ac9791441ceb13748a2196a0a6a400431d6aed5e), ROM_BIOS(2)) // v8
	ROMX_LOAD("kn5000_subprogram_v141_compressed.rom", 0x0e0000, 0x16bfd, CRC(c6d4ad98) SHA1(ac9791441ceb13748a2196a0a6a400431d6aed5e), ROM_BIOS(3)) // v7
	ROMX_LOAD("kn5000_subprogram_v140_compressed.rom", 0x0e0000, 0x16bc4, CRC(5b182629) SHA1(13098dd150c5a6083a5d15a63d5d785802d8e8ae), ROM_BIOS(4)) // v6
	ROMX_LOAD("kn5000_subprogram_v140_compressed.rom", 0x0e0000, 0x16bc4, CRC(5b182629) SHA1(13098dd150c5a6083a5d15a63d5d785802d8e8ae), ROM_BIOS(5)) // v5

	ROM_REGION16_LE(0x400000, "rhythm_data", 0)
	ROM_LOAD("kn5000_rhythm_data_rom.ic14", 0x000000, 0x400000, CRC(76d11a5e) SHA1(e4b572d318c9fe7ba00e5b44ea783e89da9c68bd))

	ROM_REGION16_LE(0x1000000, "waveform", 0)
	ROM_LOAD("kn5000_waveform_rom.ic304", 0x000000, 0x400000, NO_DUMP)
	ROM_LOAD("kn5000_waveform_rom.ic305", 0x400000, 0x400000, NO_DUMP)
	ROM_LOAD("kn5000_waveform_rom.ic306", 0x800000, 0x400000, NO_DUMP)
	ROM_LOAD("kn5000_waveform_rom.ic307", 0xc00000, 0x400000, CRC(20ff4629) SHA1(4b511bff6625f4655cabd96a263bf548d2ef4bf7))
ROM_END

} // anonymous namespace

//   YEAR  NAME   PARENT  COMPAT  MACHINE INPUT   STATE         INIT        COMPANY      FULLNAME             FLAGS
CONS(1998, kn5000,    0,       0, kn5000, kn5000, kn5000_state, empty_init, "Technics", "SX-KN5000", MACHINE_NOT_WORKING|MACHINE_IMPERFECT_SOUND)
