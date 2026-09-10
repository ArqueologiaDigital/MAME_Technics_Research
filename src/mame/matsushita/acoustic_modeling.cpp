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
#if WSA1R_ENABLE_ACOUSTIC_HLE
	, device_sound_interface(mconfig, *this)
#endif
{
}


void l7a1429_device::device_start()
{
	m_latch = 0;
	std::fill(std::begin(m_regs), std::end(m_regs), 0);

	save_item(NAME(m_latch));
	save_item(NAME(m_regs));

#if WSA1R_ENABLE_ACOUSTIC_HLE
	// stereo research HLE output at the pair's audio rate (IC4 X4 = 768 x 44100)
	m_stream = stream_alloc(0, 2, int(SAMPLE_RATE));
	for (auto &v : m_voice)
		v = hle_voice();
#endif
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

#if WSA1R_ENABLE_ACOUSTIC_HLE
	// A write to MAIN TUNE (block 0x0040) is this channel's note event: (re-)excite its
	// resonator from the freshly decoded parameters.  ⚠ RESEARCH stand-in -- the real chip has
	// no key-on register (see "There is no key-off register"); this stands for "the firmware
	// just (re)programmed this voice's pitch", the moment a note is struck on this channel.
	if (block == 0x0040)
	{
		unsigned const ch = m_latch & (VOICES - 1);
		m_stream->update();                          // sync before mutating voice state
		excite_voice(ch, decoded_channel(ch));
	}
#endif
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


#if WSA1R_ENABLE_ACOUSTIC_HLE
//**************************************************************************
//  THE RESEARCH HLE RESONATOR MODEL
//
//  A faithful C++ port of kn5000-roms-disasm wsa1/hle/l7a1429_hle.py (validated against
//  wsa1/notes/HLE-GUIDE-l7a1429.md): per channel a pair of coupled digital-waveguide
//  resonators (MAIN + SUB), each a delay of the pitch period with a one-pole MUTING loss and
//  a feedback gain, plus a POSITION pickup tap; mixed by SUB GAIN; no key-off, so a struck
//  voice sustains and decays on its own.
//
//  ⚠ TWO HONEST STAND-INS, each a documented unknown, NOT the chip's real behaviour:
//    * the excitation is a synthetic shaped burst standing in for IC4's UNDUMPED wave ROMs;
//    * the POSITION absolute scale is unknown (only the 2^v ratio is), so the pickup tap uses
//      a fixed fraction of the loop and position_octaves is not yet mapped to an absolute time.
//**************************************************************************

static constexpr double TWO_PI = 6.283185307179586;

//  one-pole lowpass loss coefficient d for y = (1-d)x + d*y1, -3 dB at fc (l7a1429_hle.onepole_coeff)
static double onepole_d(double fc, double fs)
{
	if (fc >= fs / 2.0)
		return 0.0;
	double const x = std::cos(TWO_PI * fc / fs);
	double const t = 2.0 - x;
	double const r = t * t - 1.0;
	return t - std::sqrt(r > 0.0 ? r : 0.0);
}

void l7a1429_device::setup_waveguide(waveguide &w, double freq_hz, double muting_hz,
                                     double position, double feedback)
{
	double period = (freq_hz > 1.0) ? (SAMPLE_RATE / freq_hz) : double(WG_MAX - 1);
	int n = int(period + 0.5);
	if (n < 2)        n = 2;
	if (n > WG_MAX)   n = WG_MAX;                 // clamp: lowest resolvable pitch
	w.n   = n;
	w.i   = 0;
	w.y1  = 0.0;
	w.d   = onepole_d(muting_hz, SAMPLE_RATE);
	w.fb  = feedback;
	double pos = position < 0.0 ? 0.0 : (position > 0.999 ? 0.999 : position);
	w.tap = int(pos * n);
	std::fill(std::begin(w.buf), std::end(w.buf), 0.0);
}

//  one output sample of the Karplus-Strong / waveguide loop with the POSITION pickup comb
double l7a1429_device::run_waveguide(waveguide &w)
{
	int const n = w.n;
	double const v = w.buf[w.i];
	w.y1 = (1.0 - w.d) * v + w.d * w.y1;         // MUTING loss filter in the loop
	w.buf[w.i] = w.fb * w.y1;                     // feed back around the delay
	int t = w.i - w.tap;
	t %= n; if (t < 0) t += n;
	double const out = v - w.buf[t];             // POSITION pickup: comb of current and tapped
	w.i = (w.i + 1) % n;
	return out;
}

void l7a1429_device::excite_voice(unsigned ch, const l7a1429_resonator_params &p)
{
	if (ch >= VOICES)
		return;
	hle_voice &vo = m_voice[ch];

	// pitch: MAIN from its tune (MIDI note), SUB from its own tune -- a detune that produces
	// the audible coupling (the firmware's sub_FC4269 solver; INTERACTION GAIN widens it).
	double const f_main = 440.0 * std::pow(2.0, (p.main_tune_note - 69.0) / 12.0);
	double f_sub = 440.0 * std::pow(2.0, (p.sub_tune_note - 69.0) / 12.0);
	if (f_sub < 1.0)
		f_sub = f_main * std::pow(2.0, -6.0 / 1200.0);   // default -6 cent if SUB tune unset
	// INTERACTION GAIN nudges the SUB pitch (normal-mode split, scaled by the 0..127 gain)
	double const kappa = double(p.interaction_gain) / 127.0;
	f_sub *= std::pow(2.0, (-kappa * 0.03));     // small gain-scaled detune, in octaves

	double const muting = (p.main_muting_hz > 0.0) ? p.main_muting_hz : 4000.0;
	double const muting_s = (p.sub_muting_hz > 0.0) ? p.sub_muting_hz : muting;
	// POSITION: the absolute scale is unknown; use the ratio to move the pickup fraction only.
	double const pos = 0.5;                       // ⚠ stand-in fraction (absolute scale unknown)
	double const fb  = 0.999;                     // near-lossless loop; MUTING sets the timbre

	setup_waveguide(vo.main, f_main, muting,   pos, fb);
	setup_waveguide(vo.sub,  f_sub,  muting_s, pos, fb);
	vo.sub_gain = (p.sub_gain > 0.0) ? p.sub_gain : 0.0;   // 0 = the explicit OFF

	// excitation: a synthetic shaped burst (STAND-IN for the undumped DRIVER wave sample),
	// shaped by FITTING rise/decay, seeded into both delay lines.
	double const rise  = 0.0005 + p.main_fitting_rise  * 0.02;
	double const decay = 0.005  + p.main_fitting_decay * 0.05;
	int    const blen  = std::min(vo.main.n, int((rise + decay) * SAMPLE_RATE) + 4);
	for (int k = 0; k < blen; k++)
	{
		m_exc_seed = m_exc_seed * 1103515245u + 12345u;
		double const noise = (double((m_exc_seed >> 16) & 0x7fff) / 16384.0) - 1.0;
		double const tt = double(k) / SAMPLE_RATE;
		double const env = std::min(tt / (rise > 1e-5 ? rise : 1e-5), 1.0)
		                 * std::exp(-tt / (decay > 1e-4 ? decay : 1e-4));
		double const s = noise * env * 0.9;
		vo.main.buf[k] += s;
		if (k < vo.sub.n) vo.sub.buf[k] += s;
	}
	vo.active   = true;
	vo.env_peak = 1.0;
}

void l7a1429_device::sound_stream_update(sound_stream &stream)
{
	int const ns = stream.samples();
	for (int s = 0; s < ns; s++)
	{
		double mix = 0.0;
		for (auto &vo : m_voice)
		{
			if (!vo.active)
				continue;
			double y = run_waveguide(vo.main);
			if (vo.sub_gain > 0.0)
				y += vo.sub_gain * run_waveguide(vo.sub);
			mix += y;
			// track a slow peak estimate; retire the voice once it has rung down
			double const a = std::abs(y);
			vo.env_peak += (a - vo.env_peak) * 0.0005;
			if (vo.env_peak < 1e-5)
				vo.active = false;
		}
		mix *= 0.2;                              // headroom for up to 64 voices
		if (mix >  1.0) mix =  1.0;
		if (mix < -1.0) mix = -1.0;
		stream.put(0, s, sound_stream::sample_t(mix));
		stream.put(1, s, sound_stream::sample_t(mix));
	}
}
#endif // WSA1R_ENABLE_ACOUSTIC_HLE
