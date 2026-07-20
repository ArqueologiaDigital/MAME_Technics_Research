// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics MN10300 keyboards -- tone-generator HLE, shared base

    The model-independent half of the tone-generator emulation: the per-voice
    envelope state machine and its rate->seconds law, the voice state, the
    gate-follow key coupling, the synthetic wave pack, and the audio stream.
    Concrete tone generators (kn7000_tonegen.cpp) supply the register decode
    that drives it.

    See kn_tonegen.h for the firmware evidence behind this split, and
    notes/kn6000-tonegen-spec.md for the KN7000-vs-KN6000 comparison.

***************************************************************************/

#include "emu.h"
#include "kn_tonegen.h"

#include <cmath>


kn_tonegen_base_device::kn_tonegen_base_device(const machine_config &mconfig, device_type type, const char *tag, device_t *owner, uint32_t clock, int num_voices)
	: device_t(mconfig, type, tag, owner, clock)
	, device_sound_interface(mconfig, *this)
	, m_num_voices(num_voices)
{
}

	// PROVISIONAL chip rate-byte -> seconds law (higher byte = faster; sweep-calibrated
	// anchors: piano ATK 0xD2 -> 9 ms, piano DCY1 0x39 -> 1.8 s, damp burst 0x91 -> 85 ms,
	// organ rA 0xAE -> 31 ms, pad rA 0x04 -> ~11 s).
double kn_tonegen_base_device::eg_tau(uint8_t rate)
{
	return std::clamp(13.0 * pow(2.0, -double(rate) / 20.0), 0.001, 30.0);
}
void kn_tonegen_base_device::key_break(uint8_t key)
{
	for (int v = 0; v < m_num_voices; v++)
		if (m_gate[v] && m_mode[v] == 1 && m_srckey[v] == key)
		{
			m_stream->update();
			m_gate[v]  = 0;                      // release at the voice's own rA rate
			m_stage[v] = ST_RELEASE;
		}
}
void kn_tonegen_base_device::device_start()
{
	m_stream = stream_alloc(0, 2, 44100);
	std::fill(std::begin(m_phase), std::end(m_phase), 0.0);
	std::fill(std::begin(m_freq),  std::end(m_freq),  0.0);
	std::fill(std::begin(m_env),   std::end(m_env),   0.0);
	std::fill(std::begin(m_gate),  std::end(m_gate),  0);
	std::fill(std::begin(m_stage), std::end(m_stage), uint8_t(ST_RELEASE));
	std::fill(std::begin(m_level), std::end(m_level), 1.0);
	std::fill(std::begin(m_peak),  std::end(m_peak),  0.0);
	std::fill(std::begin(m_sus1),  std::end(m_sus1),  0.0);
	std::fill(std::begin(m_sus2),  std::end(m_sus2),  0.0);
	std::fill(std::begin(m_atkstep), std::end(m_atkstep), 0.0);
	std::fill(std::begin(m_d1c),   std::end(m_d1c),   0.0);
	std::fill(std::begin(m_d2c),   std::end(m_d2c),   0.0);
	std::fill(std::begin(m_rlsc),  std::end(m_rlsc),  0.0);
	std::fill(std::begin(m_srckey), std::end(m_srckey), 0xFF);
	std::fill(std::begin(m_wsel), std::end(m_wsel), int16_t(-1));
	// Parse the optional synthetic wave pack (magic KN7WVSY2; tools/make_wave_pack.py).
	if (memory_region *wr = machine().root_device().memregion("wavepack"))
	{
		const uint8_t *p = wr->base();
		if (wr->bytes() >= 0x110 && !memcmp(p, "KN7WVSY2", 8))
		{
			const uint32_t n = p[8] | (p[9] << 8) | (p[10] << 16) | (uint32_t(p[11]) << 24);
			auto rd32 = [&](uint32_t o) { return p[o] | (p[o+1] << 8) | (p[o+2] << 16) | (uint32_t(p[o+3]) << 24); };
			for (uint32_t i = 0; i < n && i < 256; i++)
			{
				const uint32_t e = 0x110 + i * 32;
				wentry w;
				w.bank = p[e]; w.zlo = p[e+1]; w.zhi = p[e+2];
				const uint32_t off = rd32(e+4);
				w.len = rd32(e+8); w.lstart = rd32(e+12); w.llen = rd32(e+16);
				w.root_hz = double(rd32(e+20)) / 1000.0;
				if (off + w.len * 2 <= wr->bytes() && w.len && w.root_hz > 1.0
					&& w.lstart + w.llen <= w.len && w.llen)
				{
					w.pcm = reinterpret_cast<const int16_t *>(p + off);
					m_wentries.push_back(w);
				}
			}
			osd_printf_info("kn7000 tonegen: synthetic wave pack loaded (%d zone maps)\n", int(m_wentries.size()));
		}
	}
	save_item(NAME(m_phase));
	save_item(NAME(m_freq));
	save_item(NAME(m_note));
	save_item(NAME(m_p18ref));
	save_item(NAME(m_env));
	save_item(NAME(m_gate));
	save_item(NAME(m_stage));
	save_item(NAME(m_level));
	save_item(NAME(m_envreg));
	save_item(NAME(m_eg012));
	save_item(NAME(m_peak));
	save_item(NAME(m_sus1));
	save_item(NAME(m_sus2));
	save_item(NAME(m_atkstep));
	save_item(NAME(m_d1c));
	save_item(NAME(m_d2c));
	save_item(NAME(m_rlsc));
	save_item(NAME(m_ton));
	save_item(NAME(m_aux));
	save_item(NAME(m_mode));
	save_item(NAME(m_wsel));
	save_item(NAME(m_busreg));
	save_item(NAME(m_wpos));
	save_item(NAME(m_srckey));
	save_item(NAME(m_ctx_key));
	save_item(NAME(m_ctx_time));
	save_item(NAME(m_tgwrites));
}

	// Per-voice amplitude envelope DRIVEN BY THE FIRMWARE'S 7-param EG (r0/r1/r2 rate|level
	// pairs, resolved at note-on -- see tg_write and notes/tg-envelope-sweep-results.md).
	// Full stage chain: linear ATTACK to PEAK (r0), exponential DCY1 toward SUS1 (r1),
	// exponential DCY2 toward SUS2 (r2, the long-tail second stage), then exponential
	// RELEASE to silence when the gate drops (r3=0x8000 / managed r0 burst / steal mute).
	// A piano (SUS1=SUS2=0) genuinely decays to silence in two stages; an organ


	// Per-voice amplitude envelope DRIVEN BY THE FIRMWARE'S 7-param EG (r0/r1/r2 rate|level
	// pairs, resolved at note-on -- see tg_write and notes/tg-envelope-sweep-results.md).
	// Full stage chain: linear ATTACK to PEAK (r0), exponential DCY1 toward SUS1 (r1),
	// exponential DCY2 toward SUS2 (r2, the long-tail second stage), then exponential
	// RELEASE to silence when the gate drops (r3=0x8000 / managed r0 burst / steal mute).
	// A piano (SUS1=SUS2=0) genuinely decays to silence in two stages; an organ
void kn_tonegen_base_device::sound_stream_update(sound_stream &stream)
{
	constexpr double FS = 44100.0;
	constexpr double TWO_PI = 6.28318530717958647692;
	for (int s = 0; s < stream.samples(); s++)
	{
		double acc = 0.0;
		for (int v = 0; v < m_num_voices; v++)
		{
			switch (m_stage[v])
			{
			case ST_ATTACK:                                // linear ramp to PEAK (r0)
				m_env[v] += m_atkstep[v];
				if (m_env[v] >= m_peak[v]) { m_env[v] = m_peak[v]; m_stage[v] = ST_DECAY1; }
				break;
			case ST_DECAY1:                                // toward SUS1 at the DCY1 rate
				m_env[v] = m_sus1[v] + (m_env[v] - m_sus1[v]) * m_d1c[v];
				if (std::abs(m_env[v] - m_sus1[v]) < (1.0 / 1024.0))
					{ m_env[v] = m_sus1[v]; m_stage[v] = ST_DECAY2; }
				break;
			case ST_DECAY2:                                // toward SUS2 at the DCY2 rate (hold there)
				m_env[v] = m_sus2[v] + (m_env[v] - m_sus2[v]) * m_d2c[v];
				break;
			default:                                       // ST_RELEASE: decay to silence
				m_env[v] *= m_rlsc[v];
				if (m_env[v] < 0.0005) m_env[v] = 0.0;
				break;
			}
			if (m_env[v] <= 0.0) continue;
			if (m_wsel[v] >= 0)
			{
				// Donor-sample playback (synthetic wave pack): linear interpolation, tail
				// loop (seam crossfaded at build time), stepped by musical pitch / root.
				const wentry &we = m_wentries[m_wsel[v]];
				double pos = m_wpos[v];
				const uint32_t i0 = uint32_t(pos);
				const double fr = pos - double(i0);
				const uint32_t i1 = (i0 + 1 < we.len) ? i0 + 1 : we.lstart;
				const double smp = double(we.pcm[i0]) * (1.0 - fr) + double(we.pcm[i1]) * fr;
				acc += (smp / 32768.0) * m_env[v] * m_level[v];
				pos += m_freq[v] / we.root_hz;
				while (pos >= double(we.lstart + we.llen)) pos -= double(we.llen);
				m_wpos[v] = pos;
			}
			else
			{
				acc += sin(m_phase[v]) * m_env[v] * m_level[v];
				m_phase[v] += TWO_PI * m_freq[v] / FS;
				if (m_phase[v] >= TWO_PI) m_phase[v] -= TWO_PI;
			}
		}
		float smp = std::clamp(float(acc * 0.11), -1.0f, 1.0f);  // headroom for polyphony
		stream.put(0, s, smp);
		stream.put(1, s, smp);
	}
}
