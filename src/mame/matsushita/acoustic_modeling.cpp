// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics SX-WSA1 / SX-WSA1R -- IC3, the L7A1429 "MODELING LSI", the
    per-channel register file at 0x00104000 on CPU 2.  Models the register
    interface and the decoded per-channel resonator state; no audio is synthesised.

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

// The decode functions the register table's units column describes, factored out
// so the logged view (log_decoded) and the modelled state (decoded_channel) can
// never disagree.  Each is a VIEW of the number under a proven unit, not a claim
// about what the die does with it.
constexpr double note_of(uint16_t v)         { return double(v) / 256.0; }    // 0x0040/0x0080: 1/256 semitone
constexpr double q15_of(uint16_t v)          { return double(v) / 32768.0; }  // Q15 blocks
constexpr double position_oct_of(uint16_t v) { return double(v) / 3072.0; }   // 0x00C0: 3072 counts/octave

// 0x0400/0x0440/0x0480: fold(v)/65536 = K/(1+K), K = tan(pi*fc/fs); invert for fc.
// fold() lands in [1, 0xFFFE], so the denominator is never zero.
inline double muting_cutoff_hz(uint16_t v, double fs)
{
	unsigned const f = fold(v);
	double const k = double(f) / double(0x10000 - f);
	return fs * std::atan(k) / M_PI;
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
	// Fourteen of the nineteen blocks are named by the tone editor's MODELING
	// pages; the names are the machine's own words, in the same DEV104_*
	// vocabulary the disassembly uses.  The other five blocks, and the global
	// 0x0800, return nullptr on purpose: they are UNIDENTIFIED, or the firmware
	// has no name to give them, and a guessed name in a bus trace is worse than
	// a number.
	switch (block)
	{
	case 0x0040: return "MAIN TUNE";            // KEY SHIFT + DETUNE, 1/256 semitone
	case 0x0080: return "SUB TUNE";
	case 0x00c0: return "POSITION";             // and its POSITION MOVEMENT page
	case 0x0140: return "MAIN FITTING DECAY";
	case 0x0180: return "SUB FITTING DECAY";
	case 0x01c0: return "MAIN FITTING RISE";
	case 0x0200: return "SUB FITTING RISE";
	case 0x0240: return "DEPTH";                // the register the DEPTH control scales
	case 0x0280: return "SUB GAIN";
	case 0x0300: return "INTERACTION GAIN";     // gated by 0x0000 bits 6..4
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
		// fold(v)/65536 = K/(1+K) with K = tan(pi*fc/fs), the bilinear prewarp;
		// the curve fits that to 1 count over its live band.
		LOGMASKED(LOG_DECODE, "    derived: one-pole cutoff %.1f Hz\n",
			muting_cutoff_hz(data, SAMPLE_RATE));
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
			double const note = note_of(data);
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
			std::pow(2.0, position_oct_of(data)), position_oct_of(data));
		break;

	case 0x0280:
		{
			double const g = q15_of(data);
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
		LOGMASKED(LOG_DECODE, "    derived: Q15 %.5f\n", q15_of(data));
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


//-------------------------------------------------
//  decoded_channel - the modelled resonator state of one channel
//-------------------------------------------------

l7a1429_resonator_params l7a1429_device::decoded_channel(unsigned ch) const
{
	// The register number of block B for this channel is B + ch (0..VOICES-1);
	// the file is one flat array, so a channel's nineteen parameters are its
	// nineteen strides of 0x40.  Same decode functions as log_decoded, so the
	// modelled state and the logged view are one thing seen twice.
	l7a1429_resonator_params p;
	if (ch >= VOICES)
		return p;   // zeroed; out-of-range channels are not part of the file

	auto const r = [&](unsigned block) -> uint16_t { return m_regs[block + ch]; };

	p.mode               = r(0x0000);
	p.main_tune_note     = note_of(r(0x0040));
	p.sub_tune_note      = note_of(r(0x0080));
	p.position_octaves   = position_oct_of(r(0x00c0));   // ratio 2^x; absolute scale unknown
	p.main_fitting_decay = q15_of(r(0x0140));
	p.sub_fitting_decay  = q15_of(r(0x0180));
	p.main_fitting_rise  = q15_of(r(0x01c0));
	p.sub_fitting_rise   = q15_of(r(0x0200));
	p.depth              = q15_of(r(0x0240));
	p.sub_gain           = q15_of(r(0x0280));
	p.interaction_gain   = r(0x0300) & 0x7f;             // 8-bit gain, same value in both halves
	p.main_muting_hz     = muting_cutoff_hz(r(0x0400), SAMPLE_RATE);
	p.sub_muting_hz      = muting_cutoff_hz(r(0x0440), SAMPLE_RATE);
	return p;
}
