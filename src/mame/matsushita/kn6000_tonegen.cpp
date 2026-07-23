// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    KN6000/KN6500 tone generator -- the register decode

    See kn6000_tonegen.h for how this numbering was recovered from the
    firmware's own note-on register blit (0x484948CB) and its damp/mute
    literals. This file holds only the decode; the voice model it drives is
    shared with the KN7000 in kn_tonegen.cpp.

***************************************************************************/

#include "emu.h"
#include "kn6000_tonegen.h"

#include <cmath>

DEFINE_DEVICE_TYPE(KN6000_TONEGEN, kn6000_tonegen_device, "kn6000_tonegen", "KN6000 Tone Generator (firmware-driven, placeholder timbre)")

void kn6000_tonegen_device::tg_write(int tg, uint16_t addr, uint16_t data, int32_t note_x256, int rec_type)
{
	(void)tg;                                          // one chip, one window -- always 1
	if ((addr & 0xFF00) == 0xFC00) return;             // 0xFC0x idle / status refresh
	const int v = (addr >> 4) & 0x3F;                  // voice slot 0..63
	const uint16_t cls = addr & 0xFC0F;                // register class (slot masked out)

	if ((cls & 0xFC00) == 0x5000)                      // PITCH (plane 0x14): the note-on trigger
	{
		// The 18-bit pitch: the shadow record holds it as a 32-bit word whose HIGH
		// half is OR-ed into the address (blit site 0x48494A5E, `or 0x50000000`), so
		// the class low nibble carries pitch bits 16+ exactly as the KN7000's
		// 0x2400|bit0 does -- with two spare bits here rather than one.
		const uint32_t p18 = (uint32_t(cls & 0x0F) << 16) | data;

		// This register is written LAST-but-a-few in the note-on blit, after the whole
		// envelope bank, so by the time we get here the EG is cached. Require a
		// programmed EG before keying a voice on: boot reset and damp sweeps also touch
		// pitch registers but leave the envelope at zero, and gating those in produces
		// junk voices ringing after boot (the KN7000 hit exactly this).
		bool eg_programmed = false;
		for (int k = 0; k < 3; k++) if (m_eg012[v][k] != 0) { eg_programmed = true; break; }

		m_stream->update();
		if (!m_gate[v] && eg_programmed)
		{
			// NOTE-ON. Musical pitch comes from the firmware's own notePitch16 in the
			// library voice record (resolved driver-side, see kn7000.cpp
			// tg_pitch_resolve) -- the chip's pitch18 is sample-zone-relative and
			// cannot be sounded directly. With no record available, fall back to the
			// raw pitch18 read on the KN7000's anchor; that is a rough stand-in, which
			// is why the driver only enables sound once the record resolve works.
			const double note = (note_x256 >= 0) ? double(note_x256) / 256.0
			                                     : 96.0 + (double(p18) - double(0x1C838)) / 1024.0;
			m_note[v]   = note;
			m_p18ref[v] = p18;
			m_freq[v]   = 440.0 * pow(2.0, (note - 69.0) / 12.0);
			m_gate[v]   = 1;
			m_ton[v]    = machine().time().as_double();

			// Voice life cycle. The KN6000's aux/mode word (the analogue of the
			// KN7000's class 0x1C02 gate-follow marker) is NOT yet identified, and the
			// record's type field is not yet decoded either, so every voice is treated
			// as MANAGED: hold at the sustain level until the firmware's own key-up
			// arrives. That is the safe default here because the KN6000 writes a
			// UNIVERSAL key-up gate (0x8000 to cls 0x0000) for every voice class, so no
			// note can get stuck waiting for a release that never comes.
			m_mode[v]   = 0;
			(void)rec_type;
			m_srckey[v] = 0xFF;
			m_wsel[v]   = int16_t(m_wdefault);         // wave ROMs undumped -> fabricated default sine PCM
			m_wpos[v]   = 0.0;
			m_phase[v]  = 0.0;                         // clean attack transient

			// Resolve the amplitude envelope from the firmware's own [rate|level] byte
			// pairs at cls 0x0004/0x0005/0x0006 (the KN7000's r0/r1/r2 shifted by +4).
			constexpr double FS = 44100.0;
			const double peak = std::max(double(m_eg012[v][0] & 0x7F) / 127.0, 1.0 / 127.0);
			const double sus1 = double(m_eg012[v][1] & 0x7F) / 127.0;
			const double sus2 = double(m_eg012[v][2] & 0x7F) / 127.0;
			m_peak[v]    = peak;
			m_sus1[v]    = sus1;
			m_sus2[v]    = sus2;
			m_atkstep[v] = peak / (eg_tau(m_eg012[v][0] >> 8) * FS);
			m_d1c[v]     = exp(-1.0 / (eg_tau(m_eg012[v][1] >> 8) * FS));
			m_d2c[v]     = exp(-1.0 / (eg_tau(m_eg012[v][2] >> 8) * FS));
			// Default release rate: the third envelope bank's last register (cls 0x000E),
			// the positional analogue of the KN7000's rA whose per-sound value tracks the
			// audible release character. Overridden by the key-up burst's own rate below.
			m_rlsc[v]  = exp(-1.0 / (std::clamp(eg_tau(m_envreg[v][6] >> 8), 0.02, 12.0) * FS));
			m_stage[v] = ST_ATTACK;
			m_env[v]   = 0.0;
		}
		else
		{
			// Held voice: a pitch rewrite is a RELATIVE bend (vibrato / portamento /
			// pitch bend) around the note-on reference, 0x400 pitch18 units per semitone.
			const double note = m_note[v] + (double(p18) - double(m_p18ref[v])) / 1024.0;
			m_freq[v] = 440.0 * pow(2.0, (note - 69.0) / 12.0);
		}
		m_tgwrites++;
	}
	else if (cls == 0x0000)                            // idx 0 = GATE
	{
		// 0x87FF at note-on (written FIRST in the blit, before the envelope is loaded,
		// so it is not the note-on trigger here), 0x8000 at key-up. The KN7000 carries
		// this on r3; it is the one register that genuinely moved between the chips.
		if ((data >> 8) == 0x80)
		{
			const double now = machine().time().as_double();
			if (m_gate[v] && (now - m_ton[v]) > 0.020)
			{
				m_stream->update();
				m_gate[v]  = 0;
				m_stage[v] = ST_RELEASE;
			}
		}
	}
	else if (cls == 0x0004)                            // amp EG [ATK rate | PEAK level]
	{
		m_eg012[v][0] = data;
		// KEY-RELEASE path 2 (firmware-managed sounds): after the gate-off the firmware
		// rewrites the first two registers of each envelope bank ({4,5,8,9,C,D}) with a
		// ramp-down toward level 0, and the ramp's own rate byte is the real release
		// rate. Mirrors the KN7000's reg0-rewrite rule -- but WITHOUT its even/odd
		// companion-block pairing, which has no confirmed KN6000 counterpart (spec
		// section 2): release only this voice, so an unrelated neighbour cannot be cut.
		if (data != 0 && (data >> 8) < 0xFF)
		{
			const double now = machine().time().as_double();
			if ((m_gate[v] || m_stage[v] == ST_RELEASE) && (now - m_ton[v]) > 0.020)
			{
				m_stream->update();
				m_gate[v]  = 0;
				m_stage[v] = ST_RELEASE;
				m_rlsc[v]  = exp(-1.0 / (std::clamp(eg_tau(data >> 8), 0.01, 12.0) * 44100.0));
			}
		}
	}
	else if (cls == 0x0005)                            // amp EG [DCY1 rate | SUS1 level]
	{
		m_eg012[v][1] = data;
		if (data == 0xC000) { m_stream->update(); m_gate[v] = 0; m_stage[v] = ST_RELEASE; }
	}
	else if (cls == 0x0006)                            // amp EG [DCY2 rate | SUS2 level]
	{
		m_eg012[v][2] = data;
		if (data == 0xC000) { m_stream->update(); m_gate[v] = 0; m_stage[v] = ST_RELEASE; }
	}
	else if (cls >= 0x0008 && cls <= 0x000E)           // pitch/filter envelope banks
	{
		// The positional analogue of the KN7000's r4..rA: two further three-register
		// [rate|level] banks (cls 0x0008-0x000A and 0x000C-0x000E) plus their trailers.
		// Neither envelope is modelled yet -- the bank is kept for the note-on validity
		// check and for the release-rate heuristic above.
		m_envreg[v][cls - 0x0008] = data;
	}
	else if (cls == 0x4000)                            // per-voice LEVEL (plane 0x10)
	{
		// Written once per note-on from shadow +0x64. The default full-velocity patch
		// writes 0x3FFF (live capture), so normalise by that to keep the default voice
		// at unity while honouring the softer values the firmware emits for MIDI
		// velocity and the mixer's part volumes. PROVISIONAL: the field's exact width
		// and law are not confirmed, hence the clamp.
		m_stream->update();
		m_level[v] = std::clamp(double(data) / double(0x3FFF), 0.0, 1.4);
	}
	// The per-channel effect-send matrix -- the KN7000's group-0x20 (0x8000|row<<8|
	// part<<4|reg) -- is deliberately NOT decoded here. On the KN6000 the 0x8000-0x9000
	// classes are PER-VOICE wave/sample parameters (the note-on blit sources them from
	// shadow +0x8C..+0x9C), which falsifies the cross-model spec's provisional reading
	// that plane 0x20 is the send matrix on both chips. The matrix appears instead in
	// the 0xA0xx family (0xA0F8/0xA178/0xA188/0xA1A8... -- the same row/part/reg shape,
	// rebased), but which row means which effect bus is unverified, so the effect-send
	// gains keep their defaults rather than being driven from a guess. Until that is
	// settled the KN6000 is run with the dry TG path, which needs no send decode.
}
