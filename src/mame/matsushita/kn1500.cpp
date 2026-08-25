// license:GPL2+
// copyright-holders:Felipe Sanches
/******************************************************************************

    Technics SX-KN1500 music keyboard driver

    Toshiba TLCS-900 lineage (TMP95C061), sibling of the SX-KN5000.
    Dedicated segment/dot-matrix LCD (artwork preserved as an SVG ROM asset).

    Work in progress: getting the boot to drive its LCD so the display output
    can be observed. See kn7000_mame/notes/kn1500-lcd.md.

******************************************************************************/

#include "emu.h"
#include "cpu/tlcs900/tmp95c061.h"
#include "screen_svg.h"


namespace {

class kn1500_state : public driver_device
{
public:
	kn1500_state(const machine_config &mconfig, device_type type, const char *tag)
		: driver_device(mconfig, type, tag)
		, m_maincpu(*this, "maincpu")
	{ }

	void kn1500(machine_config &config) ATTR_COLD;

private:
	void mem_map(address_map &map) ATTR_COLD;
	required_device<tmp95c061_device> m_maincpu;
};

void kn1500_state::mem_map(address_map &map)
{
	// Memory map from the SX-KN1500 service manual + the crt0's TMP95C061 chip-select
	// setup (MSAR/MAMR at 0x3c-0x3f, 0x5c-0x5f): CS3=RAM @0x000000 (MAMR3=0x0f -> ~1MB
	// window), CS1=rhythm ROM @0xc00000, CS2=program ROM @0xe00000, CS0 @0x780000.
	// Work RAM is IC21 (M5M4417, 4 Mbit = 512 KB DRAM), mirrored in the 1 MB CS3 window.
	// (The previous 0x000000-0x77ffff / 7.5 MB map was a placeholder and is wrong.)
	map(0x000000, 0x07ffff).ram().mirror(0x080000);
	map(0xc00000, 0xdfffff).rom().region("rhythm", 0);   // IC17 rhythm/accomp data ROM
	map(0xe00000, 0xffffff).rom().region("prog", 0);      // IC15 program mask ROM
	// TODO: CS0 @0x780000 (IC18/IC19 EPROMs?) and the LCD graphic controller
	// (LCDCS/DSPCS, D80-D87 8-bit + command/data select) are not yet mapped.
}

static INPUT_PORTS_START( kn1500 )
INPUT_PORTS_END

void kn1500_state::kn1500(machine_config &config)
{
	TMP95C061(config, m_maincpu, 24_MHz_XTAL);
	m_maincpu->set_addrmap(AS_PROGRAM, &kn1500_state::mem_map);

	// LCD panel artwork, rendered from the "screen" SVG ROM region.
	// Upstream replaced SCREEN(..., SCREEN_TYPE_SVG) with a dedicated SCREEN_SVG device
	// type; see e.g. casio/ctk551.cpp.
	// screen_svg_device is NOT a screen_device and has no set_visarea_full(); its SVG
	// region defaults to the device tag, which is the "screen" region declared below.
	screen_svg_device &screen(SCREEN_SVG(config, "screen"));
	screen.set_refresh_hz(60);
	screen.set_size(600, 232);
}

// IC15 mask ROM -> program + rhythm halves.  The LCD SVG is a preserved ROM
// asset (original artwork).
//
// ⚠ BAD_DUMP IS NOT "CONSERVATIVE" HERE ANY MORE.  This comment used to say
// BAD_DUMP was an unvalidated marker and that "the program does boot
// coherently".  Measured 2026-08-25, that is wrong on both counts.
//
// Split the 2 MiB program image into eight 256 KiB blocks.  Four of them --
// 0xE00000, 0xE40000, 0xF00000, 0xF40000 -- have 0xFF in EVERY odd-offset
// byte, and each one's even-offset stream is EXACTLY the odd-offset stream of
// the block 512 KiB above it: 131072 of 131072 bytes, all four pairs, no
// exceptions.  The odd bytes are not missing, they are displaced.  Measure it
// again with notes/wsa1-probes/kn1500_ic15_dump_defect.py.
//
// It is load-bearing, and it is why this machine never boots.  The crt0 memory
// test at 0xFA0460 fetches 10-byte region descriptors from a table at
// 0xF38B24 -- inside one of the damaged blocks -- so it reads
// start = 0xFFDEFFF2 / length = 0xFFF2FF00, walks the whole 24-bit space and
// ends up writing its 0xA5/0x5A pattern over the CPU's own internal I/O
// registers (caught live by notes/wsa1-probes/tlcs900_16bit_unmodelled_use.lua,
// which saw the RAM test scribbling on T4MOD, T4FFCR and T45CR).  The machine
// then spins there forever; a 30 s run never leaves 0xFA047F-0xFA04A3.
//
// The obvious repair does NOT work and is deliberately not applied: treating
// the four undamaged blocks as the real 1 MiB ROM leaves 0xF38B24 pointing at
// instrument-name ASCII, not at a descriptor.  IC15 needs a RE-DUMP.  Nothing
// should be invented in the meantime.
ROM_START(kn1500)
	ROM_REGION16_LE(0x200000, "prog", 0)
	ROM_LOAD("technics_qsigt3c16079_5y68-j079_japan_9649eai.ic15", 0x000000, 0x200000, BAD_DUMP CRC(0f78da9a) SHA1(53d5c43d833fb005a7bd377583252b84b646253d))

	ROM_REGION16_LE(0x200000, "rhythm", 0)
	ROM_LOAD("technics_qsigt3c16079_5y68-j079_japan_9649eai.ic15.rest", 0x000000, 0x200000, BAD_DUMP CRC(ce60897a) SHA1(9b54f693f693488132b93e8bfed1927d7e741ae1))

	ROM_REGION(0x35f99, "screen", 0)
	ROM_LOAD("kn1500_lcd.svg", 0x000000, 0x35f99, CRC(d779a7b9) SHA1(0b40105175cc6e2ac05dea65f1ddb6c7c52c4662))
ROM_END

} // anonymous namespace


//    YEAR  NAME    PARENT  COMPAT  MACHINE  INPUT   CLASS         INIT        COMPANY     FULLNAME     FLAGS
SYST(1996, kn1500, 0,      0,      kn1500,  kn1500, kn1500_state, empty_init, "Technics", "SX-KN1500", MACHINE_NOT_WORKING | MACHINE_NO_SOUND)
