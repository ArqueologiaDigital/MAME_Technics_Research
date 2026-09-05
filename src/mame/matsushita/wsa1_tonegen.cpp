// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics SX-WSA1 / SX-WSA1R -- IC4 tone generator PLACEHOLDER SINE backend.

    Why this file is here, what it is NOT, and the boundary it must not cross are
    in wsa1_tonegen.h.  This is the machine: a 64-voice bank of sine oscillators,
    each fed a frequency by the firmware's own PITCH register and gated by its
    own block-0 lifecycle latch, summed into a stereo stream.  No wave ROM, no
    synthesis, no read of another device's memory -- only the two values the
    firmware writes to 0x0010C000 that this placeholder can honestly use.

***************************************************************************/

#include "emu.h"
#include "wsa1_tonegen.h"

#include <cmath>

DEFINE_DEVICE_TYPE(WSA1_TONEGEN, wsa1_tonegen_device, "wsa1_tonegen", "Technics SX-WSA1R Tone Generator (placeholder sine)")


wsa1_tonegen_device::wsa1_tonegen_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: device_t(mconfig, WSA1_TONEGEN, tag, owner, clock)
	, device_sound_interface(mconfig, *this)
	, m_enable(*this, finder_base::DUMMY_TAG)
{
}


void wsa1_tonegen_device::device_start()
{
	for (unsigned i = 0; i < SINE_SIZE; i++)
		m_sine[i] = float(std::sin(2.0 * M_PI * double(i) / double(SINE_SIZE)));

	// 0 inputs, 2 outputs (stereo), at the pair's real audio rate.
	m_stream = stream_alloc(0, 2, STREAM_RATE);

	for (voice &v : m_voice)
		v = voice{};

	for (int i = 0; i < NUM_VOICES; i++)
	{
		save_item(NAME(m_voice[i].phase), i);
		save_item(NAME(m_voice[i].inc), i);
		save_item(NAME(m_voice[i].pitch), i);
		save_item(NAME(m_voice[i].gate), i);
		save_item(NAME(m_voice[i].env), i);
	}
}


//-------------------------------------------------
//  inc_for - PITCH register (1/256 semitone) -> phase increment per sample
//-------------------------------------------------

uint32_t wsa1_tonegen_device::inc_for(uint16_t reg0400) const
{
	// chan + 0x0400 is the pitch in units of 1/256 semitone
	// (FINDINGS-prom_c-dev10c-register-meanings.md sec.2), seeded note*256 + 0x80
	// and saturated to 0..0x7FFF.  Read value/256 as a MIDI note number -- the
	// half-step datum (whether the +0x80 seed is an offset or a rounding bias) is
	// not established, so this uses the plain reading and is a PLACEHOLDER pitch,
	// good to well within the tuning a sine wants.
	if (reg0400 == 0)
		return 0;                       // no pitch programmed yet -> no oscillator

	double const note = double(reg0400) / 256.0;
	double freq = 440.0 * std::pow(2.0, (note - 69.0) / 12.0);
	if (freq <= 0.0)
		return 0;
	if (freq > double(STREAM_RATE) / 2.0)   // never alias past Nyquist
		freq = double(STREAM_RATE) / 2.0;

	return uint32_t((freq / double(STREAM_RATE)) * 4294967296.0);
}


void wsa1_tonegen_device::set_pitch(unsigned ch, uint16_t reg0400)
{
	if (ch >= NUM_VOICES)
		return;
	m_stream->update();                 // apply at the correct point in the stream
	m_voice[ch].pitch = reg0400;
	m_voice[ch].inc   = inc_for(reg0400);
}


void wsa1_tonegen_device::set_gate(unsigned ch, bool on)
{
	if (ch >= NUM_VOICES)
		return;
	m_stream->update();
	if (on && !m_voice[ch].gate)
		m_voice[ch].phase = 0;          // start each note at zero phase, click-free with the env ramp
	m_voice[ch].gate = on;
}


//-------------------------------------------------
//  sound_stream_update - sum the gated voices' sines
//-------------------------------------------------

void wsa1_tonegen_device::sound_stream_update(sound_stream &stream)
{
	// Read the placeholder-enable toggle once per update; default on when no port
	// is bound.  Off => every voice's target is 0 and the bank fades to silence.
	bool const enabled = (m_enable.read_safe(1) & 1) != 0;

	// Per-voice peak, with headroom for many simultaneous voices, and gate-edge
	// ramps (~4 ms attack, ~40 ms release) so note-on/off never clicks.
	constexpr float PEAK    = 0.18f;
	constexpr float ATTACK  = PEAK / (0.004f * float(STREAM_RATE));
	constexpr float RELEASE = PEAK / (0.040f * float(STREAM_RATE));

	for (int s = 0; s < stream.samples(); s++)
	{
		float mix = 0.0f;

		for (voice &v : m_voice)
		{
			float const target = (enabled && v.gate) ? PEAK : 0.0f;

			if (v.env < target)
				v.env = std::min(target, v.env + ATTACK);
			else if (v.env > target)
				v.env = std::max(target, v.env - RELEASE);

			if (v.env <= 0.0f || v.inc == 0)
				continue;

			v.phase += v.inc;
			mix += m_sine[v.phase >> (32 - SINE_BITS)] * v.env;
		}

		// A placeholder can legitimately hard-clip on the rare fully-stacked
		// chord; it keeps the mix bounded without a compressor the real part
		// does not have.
		mix = std::clamp(mix, -1.0f, 1.0f);

		stream.put(0, s, sound_stream::sample_t(mix));
		stream.put(1, s, sound_stream::sample_t(mix));
	}
}
