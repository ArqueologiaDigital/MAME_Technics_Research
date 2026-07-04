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

#include "screen.h"


namespace {

class kn7000_state : public driver_device
{
public:
	kn7000_state(const machine_config &mconfig, device_type type, const char *tag)
		: driver_device(mconfig, type, tag)
		, m_maincpu(*this, "maincpu")
		, m_screen(*this, "screen")
		, m_workram(*this, "workram")
	{ }

	void kn7000(machine_config &config) ATTR_COLD;

protected:
	virtual void machine_start() override ATTR_COLD;
	virtual void machine_reset() override ATTR_COLD;

private:
	required_device<mn10300_device> m_maincpu;
	required_device<screen_device> m_screen;
	required_shared_ptr<uint8_t> m_workram;

	void maincpu_mem(address_map &map) ATTR_COLD;

	// bring-up logging handlers for the (not-yet-decoded) I/O banks
	uint16_t io_r(offs_t offset, uint16_t mem_mask = ~0);
	void io_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);

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


static INPUT_PORTS_START(kn7000)
	// TODO: The KN7000 front panel is driven by dedicated panel sub-CPUs
	//       (CPL/CPC/CPR/CPSD) over a serial protocol, as on the KN5000.
	//       Button/slider input ports will be added once that protocol and
	//       the panel HLE device have been reverse-engineered.
INPUT_PORTS_END


uint32_t kn7000_state::screen_update(screen_device &screen, bitmap_rgb32 &bitmap, const rectangle &cliprect)
{
	// TODO: Real LCD controller (V-RAM at IC104) is not emulated yet.
	bitmap.fill(rgb_t::black(), cliprect);
	return 0;
}


void kn7000_state::machine_start()
{
}

void kn7000_state::machine_reset()
{
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
	ROM_REGION(0x400000, "maincpu", ROMREGION_ERASEFF)
	ROM_LOAD("kn7000_program.rom", 0x000000, 0x3f6f01, BAD_DUMP CRC(d9399328) SHA1(cc1c364ce4fd8096eab4453825c0cc5e15009261))

	// Table / rhythm flash -> mapped at CPU 0x48000000. Decompressed size 0x3E94D4.
	ROM_REGION(0x400000, "table", ROMREGION_ERASEFF)
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
