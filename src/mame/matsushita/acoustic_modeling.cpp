// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics SX-WSA1 / SX-WSA1R -- IC3, the L7A1429 "MODELING LSI", the
    per-channel register file at 0x00104000 on CPU 2.  PLACEHOLDER: no audio is
    synthesised.

    What this device is, what it is NOT, the firmware citations and the grade of
    every claim are in acoustic_modeling.h.  This file is the machine, and the
    machine is small on purpose: a 64-channel parameter file with a register
    select at +0 and data at +2, and nothing that makes a sound.  IC3's product
    leaves on RQWFI/IOWFI(0..12) into IC4, the tone generator, so a faithful
    l7a1429_device is not a sound device at all; making one emit audio before
    IC4 and its six undumped wave mask ROMs exist would be modelling the wrong
    end of the signal path.

***************************************************************************/

#include "emu.h"
#include "acoustic_modeling.h"

#include <cmath>

#define LOG_REG    (1U << 1)   // every register write, named by block and channel
#define LOG_DECODE (1U << 2)   // the derived physical view of a written value

#define VERBOSE 0
#include "logmacro.h"

DEFINE_DEVICE_TYPE(L7A1429, l7a1429_device, "l7a1429", "Technics Acoustic Modeling LSI")


namespace {

// The firmware's own sign-magnitude -> offset-binary step, prom_c 0xFC5361.  It
// is the inverse of the coefficient tables' storage format: under fold() both
// Curve_FE04C9 and Curve_FE05C9 are monotone over all 128 entries, and the
// two's-complement reading is not.
constexpr unsigned fold(uint16_t w)
{
	return (w & 0x8000) ? (0x8000 - (w & 0x7FFF)) : (unsigned(w) + 0x8000);
}

} // anonymous namespace


l7a1429_device::l7a1429_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: device_t(mconfig, L7A1429, tag, owner, clock)
{
}


void l7a1429_device::device_start()
{
	m_latch = 0;
	std::fill(std::begin(m_regs), std::end(m_regs), 0);

	save_item(NAME(m_latch));
	save_item(NAME(m_regs));
}


//-------------------------------------------------
//  block_name - the tone editor's name for a block
//-------------------------------------------------

const char *l7a1429_device::block_name(unsigned block)
{
	// Twelve of the nineteen blocks are drawn on the tone editor's MODELING
	// pages under these names; the names are the machine's own words, in the
	// same DEV104_* vocabulary the disassembly uses.  The other seven blocks,
	// and the global 0x0800, return nullptr on purpose: they are UNIDENTIFIED or
	// WEAK, and a guessed name in a bus trace is worse than a number.
	switch (block)
	{
	case 0x0040: return "MAIN TUNE";            // KEY SHIFT + TUNE, 1/256 semitone
	case 0x0080: return "SUB TUNE";
	case 0x00c0: return "POSITION";             // and its POSITION MOVEMENT page
	case 0x0140: return "MAIN FITTING DECAY";
	case 0x0180: return "SUB FITTING DECAY";
	case 0x01c0: return "MAIN FITTING RISE";
	case 0x0200: return "SUB FITTING RISE";
	case 0x0280: return "SUB GAIN";
	case 0x0340: return "MAIN MUTING Q13";      // the Q13 companion of 0x0400
	case 0x0380: return "SUB MUTING Q13";
	case 0x0400: return "MAIN MUTING Q16";      // the bilinear one-pole cutoff
	case 0x0440: return "SUB MUTING Q16";
	default:     return nullptr;
	}
}


//-------------------------------------------------
//  log_decoded - the DERIVED view of a written value
//-------------------------------------------------

void l7a1429_device::log_decoded(unsigned block, uint16_t data) const
{
	// ⚠ EVERY LINE BELOW IS A VIEW OF THE NUMBER, NOT AN OBSERVATION OF THE
	// CHIP.  What is proven is the closed form of the ROM curves that produce
	// these words; that the die then runs a one-pole filter or a delay line with
	// them is STRONG and unmeasured.  Nothing here feeds anything.
	switch (block)
	{
	case 0x0400: case 0x0440: case 0x0480:
		{
			// fold(v)/65536 = K/(1+K) with K = tan(pi*fc/fs), the bilinear
			// prewarp; the curve fits that to 1 count over its live band.
			double const k = double(fold(data)) / double(0x10000 - fold(data));
			LOGMASKED(LOG_DECODE, "    derived: one-pole cutoff %.1f Hz\n",
				SAMPLE_RATE * std::atan(k) / M_PI);
		}
		break;

	case 0x0340: case 0x0380: case 0x03c0:
		{
			// The SAME cutoff in Q13: (1 - fold(v)/8192) * K = 1/128.  Saturated
			// entries carry no cutoff, so say nothing rather than print one.
			double const s = 1.0 - double(fold(data)) / 8192.0;
			if (s > 0.0)
				LOGMASKED(LOG_DECODE, "    derived: one-pole cutoff %.1f Hz (Q13 form)\n",
					SAMPLE_RATE * std::atan(1.0 / (128.0 * s)) / M_PI);
			else
				LOGMASKED(LOG_DECODE, "    derived: Q13 form saturated\n");
		}
		break;

	case 0x0040: case 0x0080:
		{
			double const note = double(data) / 256.0;
			LOGMASKED(LOG_DECODE, "    derived: note %.3f = %.2f Hz\n",
				note, 440.0 * std::pow(2.0, (note - 69.0) / 12.0));
		}
		break;

	case 0x00c0:
		// A log-domain PERIOD at 3072 counts per octave.  ⚠ The constant that
		// turns it into a time in samples is nowhere in the firmware, so only
		// the ratio is printed; inventing a scale here would be inventing a
		// number the hardware has never been asked for.
		LOGMASKED(LOG_DECODE, "    derived: period x%.4f (%.3f octaves; absolute scale unknown)\n",
			std::pow(2.0, double(data) / 3072.0), double(data) / 3072.0);
		break;

	case 0x0280:
		{
			double const g = double(data) / 32768.0;
			if (g > 0.0)
				LOGMASKED(LOG_DECODE, "    derived: gain %.5f (%.1f dB)\n", g, 20.0 * std::log10(g));
			else
				LOGMASKED(LOG_DECODE, "    derived: gain 0 (OFF)\n");
		}
		break;

	case 0x0140: case 0x0180: case 0x01c0: case 0x0200: case 0x0240:
		// Q15.  ⚠ The low three bits are a separate field the packer masks or
		// forces, so the fraction is approximate in its last step.  For the RISE
		// blocks the value is the block's own cutoff coefficient times a factor
		// in [0, 0.996); whether that reads as a lower cutoff or as an input
		// gain premultiplied into the coefficient is undecided, so neither
		// reading is printed.
		LOGMASKED(LOG_DECODE, "    derived: Q15 %.5f\n", double(data) / 32768.0);
		break;

	default:
		break;
	}
}


//-------------------------------------------------
//  addr_w - 0x104000, the register select
//-------------------------------------------------

void l7a1429_device::addr_w(uint16_t data)
{
	// IC3's NAD, off SA1.  The (select, data) pair is the only atomic unit the
	// firmware has: nothing guards it, no interrupts are disabled around it, and
	// no group of registers is written as a unit.
	m_latch = data;
}


//-------------------------------------------------
//  data_w - 0x104002
//-------------------------------------------------

void l7a1429_device::data_w(uint16_t data)
{
	if (m_latch < REG_COUNT)
		m_regs[m_latch] = data;

	// Register number = block * 0x40 + channel over 64 channels, except 0x0800,
	// which is written once at power-on and carries no channel field.
	unsigned const block = m_latch & ~(VOICES - 1);
	char const *const name = block_name(block);

	if (m_latch == 0x0800)
		LOGMASKED(LOG_REG, "reg 0x0800 = 0x%04X  [global, no channel]\n", data);
	else
		LOGMASKED(LOG_REG, "reg 0x%04X = 0x%04X  [block 0x%04X %s, channel %2d]\n",
			m_latch, data, block, name ? name : "(unidentified)",
			int(m_latch & (VOICES - 1)));

	log_decoded(block, data);
}


//-------------------------------------------------
//  data_r - 0x104002
//-------------------------------------------------

uint16_t l7a1429_device::data_r()
{
	// NOTHING in prom_c reads this device: all NINE literal-address sites in the
	// image are stores, and a 45-second bus trace of the emulated machine saw
	// 2,642 writes and zero reads.  A read therefore means either a code path
	// the analysis has not reached or a decode error, so it is logged
	// unconditionally rather than under a VERBOSE mask.
	logerror("%s: UNEXPECTED read of 0x104002 (latch 0x%04X)\n",
		machine().describe_context(), m_latch);
	return 0;
}
