// license:BSD-3-Clause
// copyright-holders:Olivier Galibert, Felipe Sanches
//
// HD-AE5000, Hard Disk & Audio Extension for Technics KN5000 emulation
//
// The HD-AE5000 was an extension board for the Technics KN5000 musical keyboard.
// It provided a hard-disk, additional audio outputs and a serial port to interface
// with a computer to transfer files to/from the hard-drive.
//
// "AE" is Audio Extension.
//
//
// THE AUDIO EXTENSION -- where the third serial output of IC311 goes
// ==================================================================
// The effects DSP (IC311, uPD6383GF) has three serial audio outputs.  DO1 and DO2
// return into the tone generator and become the main mix.  DO3 does not: the
// KN5000 service manual's schematics route it OFF THE MAIN BOARD --
//
//     DO3  -> extension connector (HSO) pin 62
//     LRCK -> extension connector (HSO) pin 61
//
// -- and the only board that plugs into that connector is this one.  So the third
// DSP output IS the audio extension, and the "AE" in the product name is literal.
//
// WHAT THE BOARD DOES WITH IT, from Technics' own promotional material:
//
//     "On requests from many musicians we [have] realized the best possible
//      solution for separate outputs for bass and drums.  In detail, there are
//      3 different selections (Drums L/R, Drums and bass mixed stereo, Drums L
//      and Bass R) and for MIDI file play you also are able to select the tracks
//      for drums and bass, or you can separate any other track to your main PA
//      system.  Because of KN5000 hardware reasons, all separate outputs are
//      developed as DIRECT OUT and have NO VOLUME CONTROL from the KN5000.  They
//      have the same level as the line outputs."
//
// Three consequences worth stating, because each is a modelling decision:
//
//   1. DO3 is a SEPARATE PHYSICAL OUTPUT, not a component of the main mix.  The
//      tone generator is therefore CORRECT to leave DO3 out of its L/R sum -- see
//      kn5000_tonegen.cpp, where this note retires an educated guess that had DO3
//      down as "unknown destination".
//   2. It is DIRECT OUT at line level.  Whatever the KN5000's master volume and
//      the per-unit output-level registers do, they do not apply here.
//   3. The three selections (Drums L/R | Drums+Bass stereo | Drums L + Bass R)
//      are a function of THIS board, not of the DSP: the DSP presents one stereo
//      serial stream on DO3/LRCK and the HD-AE5000 decides what appears on the
//      jacks.
//
// NOT EMULATED (see unemulated_features() below).  What is recorded here is the
// ROUTING, which is documented by the schematics and by the manufacturer; the
// rendering is not implemented, and the DSP that would feed it does not yet
// produce audio.

#include "emu.h"
#include "hdae5000.h"

#include "bus/ata/atadev.h"
#include "bus/ata/ataintf.h"
#include "machine/i8255.h"

namespace {

class hdae5000_device : public device_t, public device_kn5000_extension_interface
{
public:
	// The separate bass/drum outputs.  The board's input is the effects DSP's third
	// serial output, DO3 + LRCK, on extension-connector pins 62 and 61 (see the note
	// at the top of this file).  Neither the DO3 feed nor the three output selections
	// are rendered.
	static constexpr feature_type unemulated_features() { return feature::SOUND; }

	hdae5000_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock = 0);

	virtual void program_map(address_space_installer &space) override;

protected:
	virtual void device_start() override ATTR_COLD;
	virtual void device_reset() override ATTR_COLD;
	virtual void device_add_mconfig(machine_config &config) override ATTR_COLD;

	virtual const tiny_rom_entry *device_rom_region() const override ATTR_COLD;

private:
	required_device<ata_interface_device> m_ata;
	required_device<i8255_device> m_ppi;
	required_memory_region m_rom;
	memory_share_creator<uint16_t> m_ram;

	void card_map(address_map &map) ATTR_COLD;

	void ata_intrq_w(int state);
};

hdae5000_device::hdae5000_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock) :
	device_t(mconfig, HDAE5000, tag, owner, clock),
	device_kn5000_extension_interface(mconfig, *this),
	m_ata(*this, "ata"),
	m_ppi(*this, "ppi"),
	m_rom(*this, "rom"),
	m_ram(*this, "ram", 0x80000, ENDIANNESS_LITTLE)
{
}

void hdae5000_device::program_map(address_space_installer &space)
{
	space.install_device(0x000000, 0x2fffff, *this, &hdae5000_device::card_map);
}

void hdae5000_device::card_map(address_map &map)
{
	// ATA IDE at CN2 — 16-bit bus, registers at byte offsets (register N at base + N*2)
	// CS0: registers 0-7 (data, error/features, sector count, LBA, status/command)
	map(0x130010, 0x13001f).rw(m_ata, FUNC(ata_interface_device::cs0_r), FUNC(ata_interface_device::cs0_w));
	// CS1: registers 0-7 (alt status/device control at offset 6 = address 0x13002C)
	map(0x130020, 0x13002f).rw(m_ata, FUNC(ata_interface_device::cs1_r), FUNC(ata_interface_device::cs1_w));
	map(0x160000, 0x160007).umask16(0x00ff).rw(m_ppi, FUNC(i8255_device::read), FUNC(i8255_device::write)); // parallel port interface (NEC uPD71055) IC9
	map(0x200000, 0x27ffff).ram().share("ram"); // hsram: 2 * 256k bytes Static RAM @ IC5, IC6 (CS5)
	map(0x280000, 0x2fffff).rom().region(m_rom, 0);
}

/*
PPI pin 2 /CS = CN6 pin 59 PPIFCS
ATA pin 31 INTRQ = CN6 pin 58 HDINT → routed to extension slot IRQ → TLCS900 INT9
*/

void hdae5000_device::ata_intrq_w(int state)
{
	// Forward ATA INTRQ (active high) through extension slot connector to main CPU INT9
	kn5000_extension_connector *connector = downcast<kn5000_extension_connector *>(owner());
	if (connector)
		connector->irq_w(state);
}

void hdae5000_device::device_add_mconfig(machine_config &config)
{
	ATA_INTERFACE(config, m_ata).options(ata_devices, "hdd", nullptr, false);
	m_ata->irq_handler().set(FUNC(hdae5000_device::ata_intrq_w));

	/* Optional Parallel Port */
	I8255(config, m_ppi); // actual chip is a NEC uPD71055 @ IC9

	// Port A: DB15 connector
	// m_ppi->in_pa_callback().set(FUNC(?_device::ppi_in_a));
	// m_ppi->out_pb_callback().set(FUNC(?_device::ppi_out_b));
	// m_ppi->in_pc_callback().set(FUNC(?_device::ppi_in_c));
	// m_ppi->out_pc_callback().set(FUNC(?_device::ppi_out_c));

	// We may later add this for the auxiliary audio output
	// provided by this extension board:
	// SPEAKER(config, "mono").front_center();
}

void hdae5000_device::device_start()
{
}

void hdae5000_device::device_reset()
{
}

ROM_START(hdae5000)
	ROM_REGION16_LE(0x80000, "rom" , 0)
	ROM_DEFAULT_BIOS("v2.06i")

	ROM_SYSTEM_BIOS(0, "v1.10i", "Version 1.10i - July 6th, 1998")
	ROMX_LOAD("hd-ae5000_v1_10i.ic4", 0x000000, 0x80000, CRC(7461374b) SHA1(6019f3c28b6277730418974dde4dc6893fced00e), ROM_BIOS(0))

	ROM_SYSTEM_BIOS(1, "v1.15i", "Version 1.15i - October 13th, 1998")
	ROMX_LOAD("hd-ae5000_v1_15i.ic4", 0x000000, 0x80000, CRC(e76d4b9f) SHA1(581fa58e2cd6fe381cfc312c73771d25ff2e662c), ROM_BIOS(1))

	// Version 2.01i is described as having "additions like lyrics display etc."
	ROM_SYSTEM_BIOS(2, "v2.01i", "Version 2.01i - January 15th, 1999") // installation file indicated "v2.0i" but signature inside the ROM is "v2.01i"
	ROMX_LOAD("hd-ae5000_v2_01i.ic4", 0x000000, 0x80000, CRC(961e6dcd) SHA1(0160c17baa7b026771872126d8146038a19ef53b), ROM_BIOS(2))

	ROM_SYSTEM_BIOS(3, "v2.06i", "Version 2.06i") // unknown release date
	ROMX_LOAD("hd-ae5000_v2_06i.ic4", 0x000000, 0x80000, CRC(836be80a) SHA1(c4da28f0ad16b1288774af761b3729142e8050b3), ROM_BIOS(3))
ROM_END

const tiny_rom_entry *hdae5000_device::device_rom_region() const
{
	return ROM_NAME(hdae5000);
}

} // anonymous namespace

DEFINE_DEVICE_TYPE_PRIVATE(HDAE5000, device_kn5000_extension_interface, hdae5000_device, "hdae5000", "HD-AE5000, Hard Disk & Audio Extension")
