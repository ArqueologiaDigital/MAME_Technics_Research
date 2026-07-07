// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics MN10300 keyboards - preservation skeletons

    Skeleton drivers for the Panasonic MN10300/AM33-based Technics arranger
    keyboards: SX-KN2400, SX-KN2600, SX-KN6000, SX-KN6500 and SX-KN7000. They
    share the Panasonic "MILK" application framework and one evolving source
    tree. Emulation is not implemented; these declare the CPU and the firmware
    ROMs for preservation. The MN10300/AM33 execution core is supplied by a
    separate change; the mn10300 device stands in as a minimal placeholder.

    The earlier Toshiba TLCS-900 keyboards (SX-KN1500, SX-KN5000) live in
    kn5000.cpp.

    ROMs: de-interleaved into the physical even/odd 16-bit flash chips from the
    checksum-verified .SLD firmware updates and loaded as good dumps (real chip
    reads would supersede them).

***************************************************************************/

#include "emu.h"
#include "cpu/mn10300/mn10300.h"


namespace {

class kn7000_state : public driver_device
{
public:
	kn7000_state(const machine_config &mconfig, device_type type, const char *tag)
		: driver_device(mconfig, type, tag)
		, m_maincpu(*this, "maincpu")
	{ }

	void kn7000(machine_config &config) ATTR_COLD;

private:
	void mem_map(address_map &map) ATTR_COLD;
	required_device<mn10300_device> m_maincpu;
};

void kn7000_state::mem_map(address_map &map)
{
	map(0x48400000, 0x487fffff).rom().region("maincpu", 0);
}

static INPUT_PORTS_START( kn7000 )
INPUT_PORTS_END

void kn7000_state::kn7000(machine_config &config)
{
	MN10300(config, m_maincpu, 32'000'000); // clock unverified
	m_maincpu->set_addrmap(AS_PROGRAM, &kn7000_state::mem_map);
}


// KN2400 / KN2600 (one firmware serves both, plus PR54): program = LKG1+LKG2.
ROM_START(kn2400)
	ROM_REGION32_LE(0x400000, "maincpu", ROMREGION_ERASEFF)
	ROM_LOAD32_WORD("kn2400_program_even.rom", 0x000000, 0x200000, CRC(b94fc8a8) SHA1(86d5d9916afdb90f82de78064b1d76fce3a21d7b))
	ROM_LOAD32_WORD("kn2400_program_odd.rom",  0x000002, 0x200000, CRC(73781cbc) SHA1(d90a3560561efd94322dca1a6710f2d5d3837cd2))
ROM_END

ROM_START(kn2600)
	ROM_REGION32_LE(0x400000, "maincpu", ROMREGION_ERASEFF)
	ROM_LOAD32_WORD("kn2400_program_even.rom", 0x000000, 0x200000, CRC(b94fc8a8) SHA1(86d5d9916afdb90f82de78064b1d76fce3a21d7b))
	ROM_LOAD32_WORD("kn2400_program_odd.rom",  0x000002, 0x200000, CRC(73781cbc) SHA1(d90a3560561efd94322dca1a6710f2d5d3837cd2))
ROM_END

ROM_START(kn6000)
	ROM_REGION32_LE(0x400000, "maincpu", ROMREGION_ERASEFF)
	ROM_LOAD32_WORD("kn6000_program_even.rom", 0x000000, 0x200000, CRC(5baeae6d) SHA1(4c9eddf227565e0b0a1d92ff3e869a02b9133833))
	ROM_LOAD32_WORD("kn6000_program_odd.rom",  0x000002, 0x200000, CRC(537471c0) SHA1(2464ce5a59416dd31c0215fb3a4ee900715df2fa))
	ROM_REGION32_LE(0x400000, "table", ROMREGION_ERASEFF)
	ROM_LOAD32_WORD("kn6000_table_even.rom", 0x000000, 0x200000, CRC(fa5e4f93) SHA1(0426da99b1589c0362e6321466beab21b22b81b0))
	ROM_LOAD32_WORD("kn6000_table_odd.rom",  0x000002, 0x200000, CRC(fd8e3bcd) SHA1(e1b63d45299b67e5258d5d08a949ea8e05c1b8e6))
ROM_END

ROM_START(kn6500)
	ROM_REGION32_LE(0x400000, "maincpu", ROMREGION_ERASEFF)
	ROM_LOAD32_WORD("kn6500_program_even.rom", 0x000000, 0x200000, CRC(d6cd26bb) SHA1(76fd4c8a5793024da5b01956a15c9c4afe7c91d6))
	ROM_LOAD32_WORD("kn6500_program_odd.rom",  0x000002, 0x200000, CRC(1691c3d8) SHA1(a6d95f51881a30b4e83352cee296b97d7b1ee222))
	ROM_REGION32_LE(0x400000, "table", ROMREGION_ERASEFF)
	ROM_LOAD32_WORD("kn6500_table_even.rom", 0x000000, 0x200000, CRC(8c7f33a2) SHA1(d44fb4415cd6b571e11e57d4a7642226b0bf4edf))
	ROM_LOAD32_WORD("kn6500_table_odd.rom",  0x000002, 0x200000, CRC(6953e094) SHA1(abf4c2252d40c71c761503d657593eb6e9c0eecc))
ROM_END

ROM_START(kn7000)
	ROM_REGION32_LE(0x400000, "maincpu", ROMREGION_ERASEFF)
	ROM_LOAD32_WORD("kn7000_program_even.rom", 0x000000, 0x200000, CRC(529b87ce) SHA1(f198fd9a9ea31a454acfe7be0eb935beca6771b1))
	ROM_LOAD32_WORD("kn7000_program_odd.rom",  0x000002, 0x200000, CRC(a36e6222) SHA1(721d4469dc5f692f7a2c16c556b2e21115df19f6))
	ROM_REGION32_LE(0x400000, "table", ROMREGION_ERASEFF)
	ROM_LOAD32_WORD("kn7000_table_even.rom", 0x000000, 0x200000, CRC(005a6db2) SHA1(2f4112ea9b039b17b5ada6952b7646adae8d9dd6))
	ROM_LOAD32_WORD("kn7000_table_odd.rom",  0x000002, 0x200000, CRC(7e1a312e) SHA1(435b597b926ebac56d4710bcae25b635a59a9ce5))
ROM_END

} // anonymous namespace


//    YEAR  NAME    PARENT  COMPAT  MACHINE  INPUT   CLASS         INIT        COMPANY     FULLNAME      FLAGS
SYST( 1998, kn2400, 0,      0,      kn7000,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN2400", MACHINE_NOT_WORKING | MACHINE_NO_SOUND )
SYST( 2000, kn2600, kn2400, 0,      kn7000,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN2600", MACHINE_NOT_WORKING | MACHINE_NO_SOUND )
SYST( 2000, kn6000, 0,      0,      kn7000,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN6000", MACHINE_NOT_WORKING | MACHINE_NO_SOUND )
SYST( 2001, kn6500, 0,      0,      kn7000,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN6500", MACHINE_NOT_WORKING | MACHINE_NO_SOUND )
SYST( 2002, kn7000, 0,      0,      kn7000,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN7000", MACHINE_NOT_WORKING | MACHINE_NO_SOUND )
