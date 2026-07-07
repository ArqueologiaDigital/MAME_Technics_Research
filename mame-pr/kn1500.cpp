// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics SX-KN1500 - preservation skeleton

    An early (1996) Technics arranger keyboard built around a Toshiba TLCS-900
    (TMP95C061) - the same lineage as the later SX-KN5000 (kn5000.cpp), separate
    from the Panasonic MN10300 keyboards (technics_kn.cpp). Emulation is not
    implemented; this declares the CPU and the mask-ROM images for preservation.

    The two images come from the mask ROM marked IC15 (QSIGT3C16079): ".ic15" is
    the program ROM, ".ic15.rest" the rhythm ROM. Both are BAD_DUMP: the dump is
    unvalidated and does not decode as coherent TLCS-900 (odd byte lanes read 0xFF
    and the reset-vector region is empty), so a redump is needed.

***************************************************************************/

#include "emu.h"
#include "cpu/tlcs900/tmp95c061.h"


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
}

ROM_START(kn1500)
	ROM_REGION16_LE(0x200000, "prog", 0)
	ROM_LOAD("technics_qsigt3c16079_5y68-j079_japan_9649eai.ic15", 0x000000, 0x200000, BAD_DUMP CRC(0f78da9a) SHA1(53d5c43d833fb005a7bd377583252b84b646253d))

	ROM_REGION16_LE(0x200000, "rhythm", 0)
	ROM_LOAD("technics_qsigt3c16079_5y68-j079_japan_9649eai.ic15.rest", 0x000000, 0x200000, BAD_DUMP CRC(ce60897a) SHA1(9b54f693f693488132b93e8bfed1927d7e741ae1))
ROM_END

} // anonymous namespace


//    YEAR  NAME    PARENT  COMPAT  MACHINE  INPUT   CLASS         INIT        COMPANY     FULLNAME     FLAGS
SYST( 1996, kn1500, 0,      0,      kn1500,  kn1500, kn1500_state, empty_init, "Technics", "SX-KN1500", MACHINE_NOT_WORKING | MACHINE_NO_SOUND )
