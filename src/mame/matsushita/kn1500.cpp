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
#include "screen.h"


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
	screen_device &screen(SCREEN(config, "screen", SCREEN_TYPE_SVG));
	screen.set_refresh_hz(60);
	screen.set_size(600, 232);
	screen.set_visarea_full();
}

// IC15 mask ROM -> program + rhythm halves. BAD_DUMP is a conservative
// "unvalidated" marker (the program does boot coherently). The LCD SVG is a
// preserved ROM asset (original artwork).
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
