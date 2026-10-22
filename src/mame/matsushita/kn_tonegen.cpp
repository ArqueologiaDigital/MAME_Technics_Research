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

#include <algorithm>
#include <climits>
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

void kn_tonegen_base_device::voice_key_on(int v, uint32_t p18, int32_t note_x256)
{
	// Musical pitch from the resolved voice-record notePitch16 when available; else the legacy
	// absolute decode, anchored where pitch18 0x1C838 = MIDI 96 (the keybed top-C reference).
	const double note = (note_x256 >= 0) ? double(note_x256) / 256.0
	                                     : 96.0 + (double(p18) - double(0x1C838)) / 1024.0;
	m_note[v]   = note;
	m_p18ref[v] = p18;
	m_freq[v]   = 440.0 * pow(2.0, (note - 69.0) / 12.0);
	m_gate[v]   = 1;
	m_ton[v]    = machine().time().as_double();
}

void kn_tonegen_base_device::voice_start_eg(int v, bool to_silence)
{
	// The amplitude EG as [rate hi | level lo] byte pairs, DECODED 2026-07-20 via the AMPLITUDE
	// EDIT -> ENVELOPE screen sweep (notes/tg-envelope-sweep-results.md): ATK rate | PEAK, DCY1
	// rate | SUS1, DCY2 rate | SUS2. Rate bytes: HIGHER = FASTER; levels 0..0x7F. (Piano:
	// D27F/3900/4500 = fast attack to full peak, two-stage decay to SILENCE; organ: D27F/727F/727F
	// = fast attack, sustain at max.) to_silence runs the decay chain to silence (one-shot plucks).
	constexpr double FS = 44100.0;
	const double peak = std::max(double(m_eg012[v][0] & 0x7F) / 127.0, 1.0 / 127.0);
	double sus1 = double(m_eg012[v][1] & 0x7F) / 127.0;
	double sus2 = double(m_eg012[v][2] & 0x7F) / 127.0;
	if (to_silence) { sus1 = 0.0; sus2 = 0.0; }
	m_peak[v]    = peak;
	m_sus1[v]    = sus1;
	m_sus2[v]    = sus2;
	m_atkstep[v] = peak / (eg_tau(m_eg012[v][0] >> 8) * FS);
	m_d1c[v]     = exp(-1.0 / (eg_tau(m_eg012[v][1] >> 8) * FS));
	m_d2c[v]     = exp(-1.0 / (eg_tau(m_eg012[v][2] >> 8) * FS));
	// Default RELEASE rate: the third bank's last register (the KN7000's rA) high byte, organ 0xAE
	// = fast stop, pad 0x04 = slow fade (audibly validated across 11 families). A key-off write
	// overrides it with its own rate (voice_release).
	m_rlsc[v]    = exp(-1.0 / (std::clamp(eg_tau(m_envreg[v][6] >> 8), 0.02, 12.0) * FS));
	m_phase[v]   = 0.0;    // clean attack transient
	m_stage[v]   = ST_ATTACK;
	m_env[v]     = 0.0;
}

void kn_tonegen_base_device::voice_bend(int v, uint32_t p18)
{
	// A pitch rewrite on a held voice is a RELATIVE bend (vibrato / portamento / pitch bend)
	// around the note-on reference, 0x400 pitch18 units per semitone.
	const double note = m_note[v] + (double(p18) - double(m_p18ref[v])) / 1024.0;
	m_freq[v] = 440.0 * pow(2.0, (note - 69.0) / 12.0);
	rom_voice_pitch(v, p18);
}

void kn_tonegen_base_device::voice_release(int v, uint8_t rate)
{
	m_stream->update();
	m_gate[v]  = 0;
	m_stage[v] = ST_RELEASE;
	m_rlsc[v]  = exp(-1.0 / (std::clamp(eg_tau(rate), 0.01, 12.0) * 44100.0));
}

void kn_tonegen_base_device::voice_mute(int v)
{
	m_stream->update();
	m_gate[v]  = 0;
	m_stage[v] = ST_RELEASE;
}

void kn_tonegen_base_device::voice_set_level(int v, uint16_t data, uint16_t full)
{
	// PROVISIONAL: the field's exact width and law are not confirmed, hence the clamp.
	m_stream->update();
	m_level[v] = std::clamp(double(data) / double(full), 0.0, 1.4);
}

// The firmware's voice sweep (TgVoiceStatusSweep: lib 0x4C03AA86 in the KN7000's v16, 0x4849A499 on
// the KN6000; notes/tg-release-2026-10-21, notes/tg-release-kn6000-2026-10-22) reads the chip once per
// pass for each group of 16 voices: it writes the address 0xFC08 + g, a 0, then reads the data port.
// It ORs the answer with its own mask of held keys, and a voice whose bit falls from 1 to 0 has ended:
// its node is retired. For the voices still sounding and not held it reads 0xFC02 | ch<<4 and keeps
// (x & 0x1FFF) >> 5 as the voice's level; a released voice below 0x80 becomes the first to be stolen.
// Answering 0 to all of this told the firmware that every voice it had just keyed was silent: it
// retired them at its next pass and at the note-off found no voice to release.
// 0xFC01 | ch<<4 is answered 0. On the KN6000 the firmware compares it with a stored target and
// retries until they agree, so it is not the level; the KN7000 runs measured never read it.
uint16_t kn_tonegen_base_device::tg_read(int tg, uint16_t addr)
{
	if ((addr & 0xFC00) != 0xFC00)
		return 0;
	m_stream->update();
	const int ch = (addr >> 4) & 0x3F, reg = addr & 0x0F;
	if (ch == 0 && reg >= 0x8 && reg <= 0xB)
	{
		uint16_t bits = 0;
		for (int i = 0; i < 16; i++)
			if (voice_sounding(voice_index(tg, ((reg - 0x8) << 4) | i)))
				bits |= 1 << i;
		return bits;
	}
	if (reg == 0x2)
		return voice_level13(voice_index(tg, ch));
	return 0;
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
	std::fill(std::begin(m_rsel), std::end(m_rsel), -1);
	std::fill(std::begin(m_rkey), std::end(m_rkey), int32_t(-1));
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
					// Reserved wildcard bank 0xFF = the fabricated DEFAULT sine (see header):
					// it never zone-matches a real voice, so unmapped voices adopt it.
					if (w.bank == 0xFF) m_wdefault = int(m_wentries.size());
					m_wentries.push_back(w);
				}
			}
			osd_printf_info("kn7000 tonegen: synthetic wave pack loaded (%d zone maps)\n", int(m_wentries.size()));
		}
	}
	// If the optional pack ROM supplied no default sine (or is absent entirely), synthesize
	// the identical single-cycle sine ourselves so EVERY voice still plays PCM, never a
	// sin() oscillator. This keeps the render path a single, faithful sample-playback
	// datapath regardless of whether the fabricated ROM is present. Faithful mechanism,
	// fabricated data. (441 samples / one cycle -> 44100/441 = 100.000 Hz root, matching
	// tools/make_wave_pack.py so the audible tone is the same whichever source provides it.)
	if (m_wdefault < 0)
	{
		constexpr int SINE_LEN = 441;
		constexpr double TWO_PI = 6.28318530717958647692;
		m_sine_pcm.resize(SINE_LEN);
		for (int i = 0; i < SINE_LEN; i++)
			m_sine_pcm[i] = int16_t(std::lround(32767.0 * sin(TWO_PI * i / SINE_LEN)));
		wentry w;
		w.bank = 0xFF; w.zlo = 0; w.zhi = 0;
		w.pcm = m_sine_pcm.data();
		w.len = SINE_LEN; w.lstart = 0; w.llen = SINE_LEN;
		w.root_hz = 44100.0 / SINE_LEN;   // 100.000 Hz
		m_wdefault = int(m_wentries.size());
		m_wentries.push_back(w);
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
	save_item(NAME(m_gain_save));
	save_item(NAME(m_rkey));
	save_item(NAME(m_rpos));
	save_item(NAME(m_rrate));
}


// ---------------------------------------------------------------------------
// Playback from the dumped wave ROMs. The format and the rules below are measured from
// the KN7000's four ROMs; the evidence and the producing scripts are in
// notes/g13-waves-2026-10-20 (wavedir.py is the reference implementation of this code).
// ---------------------------------------------------------------------------

void kn_tonegen_base_device::set_wave_pair(int pair, const uint8_t *y, const uint8_t *x, uint32_t bytes)
{
	m_wave[pair][0] = y;
	m_wave[pair][1] = x;
	m_wave_bytes = bytes;
}

int32_t kn_tonegen_base_device::rom_word(int pair, uint32_t word) const
{
	// stream word 2i is word i of the Y ROM, 2i+1 word i of the X ROM, low byte first
	const uint8_t *const p = m_wave[pair][word & 1];
	const uint32_t a = (word >> 1) * 2;
	if (!p || a + 1 >= m_wave_bytes)
		return 0;
	return int16_t(p[a] | (p[a + 1] << 8));
}

// A sample is selected by (pair, page, entry). Page p's directory starts at stream word
// p * 0x100000: entry j is the four words {A, P, B, Q} at 4j, and A of entry 0 is 4 * the
// entry count. P = 0x1000 | E<<4 | F<<3 | K: E the pitch exponent, F set for 8-bit samples,
// granule L = 2^(K+4) samples. The sample starts at word B*16 of the page. The record at
// word A is B again, then [flags:2][code:6][value:8] words: a value >= 0x80 is a segment of
// (256 - value) granules; flag 0x40 marks the loop start at the end of its segment, flag
// 0x80 the loop end; with no loop end the loop is the one granule after the segments.
// Values below 0x80 are not segments, and the word with both flags ends the record. An
// 8-bit segment's code (a,b) scales its samples by 2^(-b/2) (fitted; code8fit.py).
int kn_tonegen_base_device::rom_sample_index(uint32_t key)
{
	auto it = std::lower_bound(m_rindex.begin(), m_rindex.end(), std::make_pair(key, INT_MIN));
	if (it != m_rindex.end() && it->first == key)
		return it->second;

	int result = -1;
	const int pair = (key >> 20) & 1;
	const uint32_t page = (key >> 12) & 0xFF, entry = key & 0xFFF;
	if (m_wave[pair][0] && page < 16)
	{
		const uint32_t pbase = page * 0x100000;
		const uint32_t count = uint16_t(rom_word(pair, pbase)) / 4;
		if (entry < count)
		{
			const uint32_t A = uint16_t(rom_word(pair, pbase + 4 * entry));
			const uint32_t P = uint16_t(rom_word(pair, pbase + 4 * entry + 1));
			const uint32_t B = uint16_t(rom_word(pair, pbase + 4 * entry + 2));
			rom_sample rs;
			rs.pair = pair;
			rs.base = pbase + B * 16;
			rs.is8 = BIT(P, 3);
			rs.exponent = (P >> 4) & 0xFF;
			const uint32_t L = 1U << ((P & 7) + 4);
			uint32_t pos = 0, ls = 0, le = 0;
			bool have_ls = false, have_le = false;
			float gain = 1.0f;
			for (int k = 1; k < 1024; k++)
			{
				const uint16_t w = uint16_t(rom_word(pair, pbase + A + k));
				const int flags = w >> 14;
				if ((w & 0xFF) >= 0x80)
				{
					pos += (0x100 - (w & 0xFF)) * L;
					gain = float(pow(2.0, -double(BIT(w, 8, 3)) / 2.0));
					if (rs.is8)
						rs.gain.emplace_back(pos, gain);
					if ((flags & 1) && !have_ls) { ls = pos; have_ls = true; }
					if (flags & 2) { le = pos; have_le = true; break; }
				}
				if (flags == 3)
					break;
			}
			if (!have_ls) ls = pos;
			if (!have_le || le <= ls) le = ls + L;
			if (rs.is8)
				rs.gain.emplace_back(~0U, gain);          // past the segments: the last segment's gain
			rs.ls = ls;
			rs.le = le;
			const uint32_t words = rs.is8 ? (le + 1) / 2 : le;
			if (uint64_t(rs.base) + words + 1 < uint64_t(m_wave_bytes))  // stream words = 2 * bytes / 2
			{
				result = int(m_rsamples.size());
				m_rsamples.push_back(std::move(rs));
			}
		}
	}
	m_rindex.insert(it, std::make_pair(key, result));
	return result;
}

double kn_tonegen_base_device::rom_fetch(const rom_sample &rs, uint32_t i) const
{
	if (!rs.is8)
		return double(rom_word(rs.pair, rs.base + i));
	const int32_t w = rom_word(rs.pair, rs.base + (i >> 1));
	const int8_t b = int8_t(BIT(i, 0) ? (w >> 8) : w);
	auto g = std::upper_bound(rs.gain.begin(), rs.gain.end(), i,
			[] (uint32_t x, const std::pair<uint32_t, float> &s) { return x < s.first; });
	return double(b) * 256.0 * (g != rs.gain.end() ? g->second : 1.0f);
}

// Source samples per 44.1 kHz output sample. p18 0x1E200 is note 96 (C7), 0x400 per
// semitone, and a waveform with a period of 2^(E-9) samples sounds at p18's note: checked
// against the firmware's own notes for piano, bass, mallet, organ, brass and strings
// voices (pitchcheck.py).
double kn_tonegen_base_device::rom_rate(uint32_t p18, int exponent)
{
	constexpr double C7 = 2093.004522404789;   // 440 * 2^(27/12)
	return pow(2.0, (double(p18) - double(0x1E200)) / double(0x3000) + double(exponent - 9)) * C7 / 44100.0;
}

bool kn_tonegen_base_device::rom_voice_start(int v, int pair, uint32_t sel20, uint32_t p18)
{
	const uint32_t key = (uint32_t(pair & 1) << 20) | (sel20 & 0xFFFFF);
	const int idx = rom_sample_index(key);
	m_rsel[v] = idx;
	m_rkey[v] = (idx >= 0) ? int32_t(key) : -1;
	m_rpos[v] = 0.0;
	if (idx < 0)
		return false;
	m_rrate[v] = rom_rate(p18, m_rsamples[idx].exponent);
	return true;
}

void kn_tonegen_base_device::rom_voice_pitch(int v, uint32_t p18)
{
	if (m_rsel[v] >= 0)
		m_rrate[v] = rom_rate(p18, m_rsamples[m_rsel[v]].exponent);
}

// The effect-send gains are std::atomic<float>, which save_item() cannot register, so they
// are shadowed into m_gain_save around a save/load. They are genuine runtime state: the
// firmware writes all nine from its own register traffic (tg_write), and the driver writes
// two more from the DSP bridge. Before this, a state saved with reverb engaged came back
// with the boot-default mix -- silently, because nothing about the restored machine looked
// wrong until you listened to it.
void kn_tonegen_base_device::device_pre_save()
{
	m_gain_save[GAIN_DIRECT]    = m_gain_direct;
	m_gain_save[GAIN_RETURN]    = m_gain_return;
	m_gain_save[GAIN_SEND]      = m_gain_send;
	m_gain_save[GAIN_DEPTH]     = m_gain_depth;
	m_gain_save[GAIN_CHORUS]    = m_gain_chorus;
	m_gain_save[GAIN_DSP]       = m_gain_dsp;
	m_gain_save[GAIN_MULTI]     = m_gain_multi;
	m_gain_save[GAIN_DSP_RET]   = m_gain_dsp_ret;
	m_gain_save[GAIN_MULTI_RET] = m_gain_multi_ret;
}

void kn_tonegen_base_device::device_post_load()
{
	m_gain_direct    = m_gain_save[GAIN_DIRECT];
	m_gain_return    = m_gain_save[GAIN_RETURN];
	m_gain_send      = m_gain_save[GAIN_SEND];
	m_gain_depth     = m_gain_save[GAIN_DEPTH];
	m_gain_chorus    = m_gain_save[GAIN_CHORUS];
	m_gain_dsp       = m_gain_save[GAIN_DSP];
	m_gain_multi     = m_gain_save[GAIN_MULTI];
	m_gain_dsp_ret   = m_gain_save[GAIN_DSP_RET];
	m_gain_multi_ret = m_gain_save[GAIN_MULTI_RET];
	// the ROM sample table is derived from the ROMs, so only the keys are saved
	for (int v = 0; v < MAX_VOICES; v++)
		m_rsel[v] = (m_rkey[v] >= 0) ? rom_sample_index(uint32_t(m_rkey[v])) : -1;
}

void kn_tonegen_base_device::sound_stream_update(sound_stream &stream)
{
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
			if (m_rsel[v] >= 0)
			{
				// A voice keyed from the dumped wave ROMs: linear interpolation, loop [ls, le).
				const rom_sample &rs = m_rsamples[m_rsel[v]];
				double pos = m_rpos[v];
				if (!std::isfinite(pos) || pos < 0.0 || pos >= double(rs.le))
					pos = double(rs.ls);
				const uint32_t i0 = uint32_t(pos);
				const double fr = pos - double(i0);
				const uint32_t i1 = (i0 + 1 < rs.le) ? i0 + 1 : rs.ls;
				const double smp = rom_fetch(rs, i0) * (1.0 - fr) + rom_fetch(rs, i1) * fr;
				acc += (smp / 32768.0) * m_env[v] * m_level[v];
				double step = m_rrate[v];
				if (!std::isfinite(step) || step < 0.0) step = 0.0;
				pos += step;
				if (pos >= double(rs.le))
				{
					double rel = fmod(pos - double(rs.ls), double(rs.le - rs.ls));
					if (!std::isfinite(rel) || rel < 0.0) rel = 0.0;
					pos = double(rs.ls) + rel;
				}
				m_rpos[v] = pos;
				continue;
			}
			if (m_wsel[v] < 0) continue;   // no wave selected (unkeyed voice) -> silent
			// SINGLE, FAITHFUL DATAPATH: every voice reads PCM from the wave pack, exactly
			// as the real chip reads its wave ROM -- donor zones where a KN5000 sample was
			// mapped, or the fabricated default sine (m_wdefault) everywhere else. There is
			// no sin() oscillator; the hardware has none. Linear interpolation, tail loop
			// (seam crossfaded at build time for donors; single cycle for the sine), stepped
			// by musical pitch / root. Faithful mechanism -- the DATA is placeholder, the
			// PLAYBACK PATH is real.
			const wentry &we = m_wentries[m_wsel[v]];
			double pos = m_wpos[v];
			// SANITISE the read position before indexing the PCM. A model whose
			// note->pitch resolve is not yet reversed (e.g. the KN6000) can hand us a
			// non-finite or out-of-range frequency; an unguarded uint32_t(pos) on inf/NaN
			// or a huge pos would index the sample array out of bounds and crash the
			// emulator. Keep pos finite and within the sample before use.
			if (!std::isfinite(pos) || pos < 0.0 || pos >= double(we.len))
				pos = double(we.lstart);
			const uint32_t i0 = uint32_t(pos);
			const double fr = pos - double(i0);
			const uint32_t i1 = (i0 + 1 < we.len) ? i0 + 1 : we.lstart;
			const double smp = double(we.pcm[i0]) * (1.0 - fr) + double(we.pcm[i1]) * fr;
			acc += (smp / 32768.0) * m_env[v] * m_level[v];
			// Advance by musical pitch / root, then wrap into the tail loop. GUARD both:
			// a model whose note->pitch resolve is not yet reversed (e.g. the KN6000) can
			// hand us a non-finite, negative, or absurdly large frequency. The step is
			// clamped finite/non-negative, and the loop wrap is done with an O(1) modulo
			// (NOT a subtract-loop): a huge finite step through a subtract-loop would
			// iterate billions of times and livelock the single-threaded emulator.
			double step = m_freq[v] / we.root_hz;
			if (!std::isfinite(step) || step < 0.0) step = 0.0;
			pos += step;
			const double end = double(we.lstart + we.llen);
			if (pos >= end)
			{
				double rel = fmod(pos - double(we.lstart), double(we.llen));
				if (!std::isfinite(rel) || rel < 0.0) rel = 0.0;
				pos = double(we.lstart) + rel;
			}
			m_wpos[v] = pos;
		}
		float smp = std::clamp(float(acc * 0.11), -1.0f, 1.0f);  // headroom for polyphony
		stream.put(0, s, smp);
		stream.put(1, s, smp);
	}
}
