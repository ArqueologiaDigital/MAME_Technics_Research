// ===========================================================================
// KN1500 additions for src/mame/matsushita/kn5000.cpp
// (SX-KN1500 shares the Toshiba TLCS-900 lineage with the SX-KN5000.)
//
// To integrate:
//   1) Add near the top of kn5000.cpp: #include "cpu/tlcs900/tmp95c061.h"
//      (screen.h is already included by kn5000.cpp).
//   2) Add the class + input + machine config inside the anonymous namespace.
//   3) Add the ROM_START inside the namespace and the SYST line after it.
//   4) Ship the LCD artwork ROM `kn1500_lcd.svg` in the romset (provided alongside).
//
// The program ROM is BAD_DUMP (see below); the SVG LCD panel is loaded as a hashed
// ROM asset and rendered on an SVG screen (the Game & Watch / hh_sm510 pattern).
// ===========================================================================

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
	map(0x000000, 0x77ffff).ram();
	map(0xc00000, 0xdfffff).rom().region("rhythm", 0);
	map(0xe00000, 0xffffff).rom().region("prog", 0);
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

// IC15 mask ROM -> program + rhythm (both BAD_DUMP: unvalidated, does not decode as
// coherent TLCS-900, needs a redump). The LCD SVG is a preserved artwork ROM asset.
ROM_START(kn1500)
	ROM_REGION16_LE(0x200000, "prog", 0)
	ROM_LOAD("technics_qsigt3c16079_5y68-j079_japan_9649eai.ic15", 0x000000, 0x200000, BAD_DUMP CRC(0f78da9a) SHA1(53d5c43d833fb005a7bd377583252b84b646253d))

	ROM_REGION16_LE(0x200000, "rhythm", 0)
	ROM_LOAD("technics_qsigt3c16079_5y68-j079_japan_9649eai.ic15.rest", 0x000000, 0x200000, BAD_DUMP CRC(ce60897a) SHA1(9b54f693f693488132b93e8bfed1927d7e741ae1))

	ROM_REGION(0x35f99, "screen", 0)
	ROM_LOAD("kn1500_lcd.svg", 0x000000, 0x35f99, CRC(d779a7b9) SHA1(0b40105175cc6e2ac05dea65f1ddb6c7c52c4662))
ROM_END

//    YEAR  NAME    PARENT  COMPAT  MACHINE  INPUT   CLASS         INIT        COMPANY     FULLNAME     FLAGS
SYST( 1996, kn1500, 0,      0,      kn1500,  kn1500, kn1500_state, empty_init, "Technics", "SX-KN1500", MACHINE_NOT_WORKING | MACHINE_NO_SOUND )
