// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics SX-WSA1 / SX-WSA1R -- the second per-channel register file
    at 0x00104000 on CPU 2.  PLACEHOLDER: no audio is synthesised.

    What this device is, what it is NOT, the firmware citations and the grade
    of every claim are in wsa1_modeling.h.  This file is the machine, and the
    machine is small on purpose: a 64-channel parameter file with an address
    latch at +0 and data at +2, and nothing that makes a sound.

***************************************************************************/

#include "emu.h"
#include "wsa1_modeling.h"

#define LOG_REG (1U << 1)   // every register write, decoded into block and channel

#define VERBOSE 0
#include "logmacro.h"

DEFINE_DEVICE_TYPE(WSA1_MODELING, wsa1_modeling_device, "wsa1_modeling", "SX-WSA1 modelling section (placeholder)")


wsa1_modeling_device::wsa1_modeling_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: device_t(mconfig, WSA1_MODELING, tag, owner, clock)
{
}


void wsa1_modeling_device::device_start()
{
	m_latch = 0;
	std::fill(std::begin(m_regs), std::end(m_regs), 0);

	save_item(NAME(m_latch));
	save_item(NAME(m_regs));
}


//-------------------------------------------------
//  addr_w - 0x104000, the register select
//-------------------------------------------------

void wsa1_modeling_device::addr_w(uint16_t data)
{
	m_latch = data;
}


//-------------------------------------------------
//  data_w - 0x104002
//-------------------------------------------------

void wsa1_modeling_device::data_w(uint16_t data)
{
	if (m_latch < REG_COUNT)
		m_regs[m_latch] = data;

	// Nineteen registers per channel, same `block * 0x40 + channel` numbering:
	// Dev104_WriteAllChanRegs (0xFB77EF) writes block k for k = 1..0x12 from
	// staging word 2*k and block 0 LAST.  Two of the smaller accessors in the
	// same bank write block 0 FIRST (0xFB7983, 0xFB79E5), so "block 0 is a
	// commit register" holds for the unrolled writer and is contradicted for
	// those two -- it is a property of each routine, not of the register.
	// (notes/FINDINGS-prom_c-tone-generator.md sec.4.)
	LOGMASKED(LOG_REG, "reg 0x%04X (block 0x%03X channel %2d) = 0x%04X\n",
		m_latch, m_latch >> 6, int(m_latch & (VOICES - 1)), data);
}


//-------------------------------------------------
//  data_r - 0x104002
//-------------------------------------------------

uint16_t wsa1_modeling_device::data_r()
{
	// NOTHING in prom_c reads this device - all twelve literal-address sites are
	// stores.  A read here therefore means either a code path the analysis has
	// not reached or a decode error, so it is logged unconditionally.
	logerror("%s: UNEXPECTED read of 0x104002 (latch 0x%04X)\n",
		machine().describe_context(), m_latch);
	return 0;
}
