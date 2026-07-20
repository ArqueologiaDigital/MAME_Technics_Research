// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    KN7000 tone generator -- the register decode

    See kn7000_tonegen.h. This file holds the KN7000's register NUMBERING:
    the tg_write() decode that turns firmware register writes into voice
    events on the shared base (kn_tonegen.cpp).

***************************************************************************/

#include "emu.h"
#include "kn7000_tonegen.h"

#include <cmath>

DEFINE_DEVICE_TYPE(KN7000_TONEGEN, kn7000_tonegen_device, "kn7000_tonegen", "KN7000 Tone Generator (firmware-driven, placeholder timbre)")

void kn7000_tonegen_device::tg_write(int tg, uint16_t addr, uint16_t data, int32_t note_x256, int rec_type)
{
	if ((addr & 0xFF00) == 0xFC00) return;            // 0xFC0x idle / status refresh
	const int v = (tg << 6) | ((addr >> 4) & 0x3F);   // voice 0..127 (0..63 sub, 64..127 master)
	const uint16_t cls = addr & 0xFC0F;               // register class (channel masked out)
	if ((cls & 0xFC0E) == 0x2400)                     // pitch (bit0 = pitch18 bit16)
	{
		const uint32_t p18 = (uint32_t(cls & 1) << 16) | data;
		m_stream->update();
		// A REAL note-on always programs the 7-halfword amplitude EG (r4..rA) for the
		// voice immediately before this pitch write (live capture). Boot/init sweeps
		// also hit pitch registers but leave the EG all-zero -- gating those produced
		// faint junk voices ringing for ~20 s after boot (audible now that the dry TG
		// is the default listening tap). Require a programmed EG to key a voice on.
		bool eg_programmed = false;
		for (int k = 0; k < 7; k++) if (m_envreg[v][k] != 0) { eg_programmed = true; break; }
		if (!m_gate[v] && eg_programmed)
		{
			// note-on: musical pitch from the resolved voice-record notePitch16
			// when available; else the legacy absolute decode (anchored where
			// pitch18 0x1C838 = MIDI 96, the keybed top-C reference).
			const double note = (note_x256 >= 0) ? double(note_x256) / 256.0
			                                     : 96.0 + (double(p18) - double(0x1C838)) / 1024.0;
			m_note[v]   = note;
			m_p18ref[v] = p18;
			m_freq[v]   = 440.0 * pow(2.0, (note - 69.0) / 12.0);
			m_gate[v]   = 1;      // held
			m_ton[v]    = machine().time().as_double();   // for release detection (reg0 rule)
			// Voice life-cycle class (workflow RE + 11-family sweep, 2026-07-11):
			//  - GATE_FOLLOW: aux bit15 (brass/sax/organ) -- no firmware key-up write; the
			//    TG (which hosts the key-bed FIFO) gates them off itself on key release.
			//  - MANAGED: firmware voice-record type (rec+0x02 & 0x7C) in {04,08,10,20,40}
			//    -- the firmware sends the 6-write release ramp at key-up (piano, strings,
			//    pad, synth, bass, world). Hold at SUS1 until it arrives.
			//  - ONESHOT: everything else (plucked guitar/mallet classes) -- no key-up
			//    event at all; the sample rings its own envelope, so the held decay
			//    continues past SUS1 to silence at the r8 rate.
			const bool managed_type = (rec_type == 0x04 || rec_type == 0x08 || rec_type == 0x10
			                        || rec_type == 0x20 || rec_type == 0x40);
			if (m_aux[v] & 0x8000)      m_mode[v] = 1;             // gate-follow
			else if (managed_type)      m_mode[v] = 0;             // firmware-managed release
			else if (rec_type >= 0)     m_mode[v] = 2;             // one-shot (pluck classes)
			else                        m_mode[v] = 0;             // unknown record: safest = managed
			const double nowt = machine().time().as_double();
			m_srckey[v] = (m_ctx_time >= 0.0 && (nowt - m_ctx_time) < 0.060) ? m_ctx_key : 0xFF;
			// Sample select: (bank,zone) from the aux word -> donor wave (sine if unmapped).
			{
				const int bank = (m_aux[v] >> 12) & 3, zone = m_aux[v] & 0xFF;
				m_wsel[v] = -1;
				for (size_t i = 0; i < m_wentries.size(); i++)
					if (m_wentries[i].bank == bank && zone >= m_wentries[i].zlo && zone <= m_wentries[i].zhi)
						{ m_wsel[v] = int16_t(i); break; }
				m_wpos[v] = 0.0;
			}
			m_phase[v]  = 0.0;    // clean attack transient
			// Resolve this voice's amplitude envelope from the firmware's 7-param EG.
			// DECODED 2026-07-20 via the AMPLITUDE EDIT -> ENVELOPE screen sweep
			// (notes/tg-envelope-sweep-results.md): the EG lives in r0/r1/r2 as
			// [rate hi | level lo] byte pairs -- r0 = ATK rate | PEAK level,
			// r1 = DCY1 rate | SUS1 level, r2 = DCY2 rate | SUS2 level. Rate bytes:
			// HIGHER = FASTER. Levels 0..0x7F. (Piano: D27F/3900/4500 = fast attack
			// to full peak, two-stage decay to SILENCE; organ: D27F/727F/727F = fast
			// attack, sustain at max -- exactly the audible behavior.) The chip's
			// exact rate->seconds law is PROVISIONAL: T = 13 * 2^(-rate/20) s,
			// calibrated so the piano keeps its shipped ~6 ms attack / ~1.8 s decay.
			constexpr double FS = 44100.0;
			const double peak = std::max(double(m_eg012[v][0] & 0x7F) / 127.0, 1.0 / 127.0);
			double sus1 = double(m_eg012[v][1] & 0x7F) / 127.0;
			double sus2 = double(m_eg012[v][2] & 0x7F) / 127.0;
			// ONESHOT plucks (no key-up ramp): the sample dies out naturally -- force
			// the decay chain to run to silence (the old held-decay behavior).
			if (m_mode[v] == 2) { sus1 = 0.0; sus2 = 0.0; }
			m_peak[v]    = peak;
			m_sus1[v]    = sus1;
			m_sus2[v]    = sus2;
			m_atkstep[v] = peak / (eg_tau(m_eg012[v][0] >> 8) * FS);
			m_d1c[v]     = exp(-1.0 / (eg_tau(m_eg012[v][1] >> 8) * FS));
			m_d2c[v]     = exp(-1.0 / (eg_tau(m_eg012[v][2] >> 8) * FS));
			// Default RELEASE rate: the chip-side damp bank's rA high byte (organ
			// 0xAE = fast stop, pad 0x04 = slow fade -- audibly validated across 11
			// families). Firmware-managed sounds override this with the key-up
			// burst's own r0 rate (see cls 0x0000 below).
			m_rlsc[v] = exp(-1.0 / (std::clamp(eg_tau(m_envreg[v][6] >> 8), 0.02, 12.0) * FS));
			m_stage[v] = ST_ATTACK;
			m_env[v]   = 0.0;
		}
		else
		{
			// held voice: RELATIVE pitch update (bend/vibrato/portamento) around
			// the note-on reference, 0x400 pitch18 units per semitone.
			const double note = m_note[v] + (double(p18) - double(m_p18ref[v])) / 1024.0;
			m_freq[v] = 440.0 * pow(2.0, (note - 69.0) / 12.0);
		}
		m_tgwrites++;
	}
	else if (cls == 0x0000)                           // r0 = [ATK rate | PEAK level]
	{
		m_eg012[v][0] = data;                         // cache for the next note-on resolve
		// KEY-RELEASE, path 2 (firmware-managed sounds): after the r3=0x8000 gate-off
		// the firmware rewrites regs 0,1,4,5,8,9 of the note's ODD companion block with
		// a ramp-down (r0=0x9180: rate 0x91 toward level 0) -- aimed at the companion
		// even when only the even block sounds. A reg0 rewrite below full scale on
		// EITHER block of a pair releases every gated/releasing voice of the pair
		// {v&~1, v|1} gated >20 ms (the note-on's own r0 programming happens BEFORE
		// the pitch-write gate, and boot resets are 0xFF80, so the guard+threshold
		// skip them) and OVERRIDES the release coefficient with the burst's own rate
		// byte -- the piano damp 0x91 -> ~85 ms under the provisional law.
		if (data != 0 && (data >> 8) < 0xFF)
		{
			const double now = machine().time().as_double();
			for (int y = (v & ~1); y <= (v | 1); y++)
				if ((m_gate[y] || m_stage[y] == ST_RELEASE) && (now - m_ton[y]) > 0.020)
				{
					m_stream->update();
					m_gate[y]  = 0;
					m_stage[y] = ST_RELEASE;
					m_rlsc[y]  = exp(-1.0 / (std::clamp(eg_tau(data >> 8), 0.01, 12.0) * 44100.0));
				}
		}
	}
	else if (cls == 0x0001)                           // r1 = [DCY1 rate | SUS1 level];
	{                                                 // 0xC000 = mute (boot init / voice-steal)
		m_eg012[v][1] = data;
		if (data == 0xC000) { m_stream->update(); m_gate[v] = 0; m_stage[v] = ST_RELEASE; }
	}
	else if (cls == 0x0002)                           // r2 = [DCY2 rate | SUS2 level]
	{
		m_eg012[v][2] = data;
	}
	else if (cls == 0x0003)                           // r3 = GATE (sweep result 3):
	{                                                 // 0x87FF at note-on, 0x8000 at key-up
		// UNIVERSAL key-release trigger -- written for EVERY class on key-up (verified
		// on the managed piano AND the gate-follow organ, falsifying the earlier "no
		// key-up write for organ/brass" reading). Release at the voice's default rate
		// (rA damp law); managed sounds refine it with the r0 burst that follows.
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
	else if (cls == 0x2009)                           // per-voice level (best-effort)
	{
		// The firmware writes this once at note-on; in the default full-velocity
		// patch it is 0x5FFF, so normalising by 0x5FFF keeps that voice at unity
		// (no change to the current sound) while honouring softer/louder values
		// the firmware would emit for MIDI velocity or the mixer's part volumes.
		m_stream->update();
		m_level[v] = std::clamp(double(data) / double(0x5FFF), 0.0, 1.4);
	}
	else if ((addr & 0xFC00) == 0x8000)               // group 0x20: per-channel OUTPUT BUS /
	{                                                  // EFFECT-SEND record (0x80xx-0x83xx)
		// ★ DECODED 2026-07-20 (queue item B2; static RE of the lib setter family
		// 0x4C037D0F..0x4C037F10 + live setter/arg traps -- see notes/per-part-depth-bank.md):
		// the group-0x20 register space is a PER-PART SEND MATRIX, addr = 0x8000 |
		// row<<8 | part<<4 | reg, i.e. "channel" 0xRP = row R (0-3) of mixer part P:
		//   row0 (0x80P8)  = part P's send-to-REVERB-bus   [hi byte 0x03 = dest = the
		//                    reverb-return mixer part 3; low7 = level]
		//   row1 (0x81P8)  = part P's send-to-CHORUS bus   [hi 0x0B]
		//   row2 (0x82P8)  = part P's send-to-MULTI bus    [hi = ON marker: 0x06 (dest =
		//                    multi-return part 6) when MULTI is ON, 0x08 when OFF]
		//   row3 (0x83P8)  = part P's output LEVEL/depth   [the "0x85xx depth bank"; for
		//                    the effect-return parts this is the effect's TOTAL DEPTH --
		//                    part 3 = the reverb TOTAL DEPTH we already capture]
		//   reg 0xA        = part P's [direct | return] crossfade pair
		// Mixer parts: raw TG parts + effect-return parts 3 (reverb), 6 (multi) and 9
		// (the per-part Sound-DSP INSERT return for RIGHT1). The firmware maintains the
		// per-part depths in its part records (0x500B5340 + idx*0x54C: +0x15 chorus
		// depth 0x3C, +0x16 multi depth 0x50) and only APPLIES them to part 9's rows
		// when the part-insert flag (record +0 bit3, the SOUND DSP toggle) is on --
		// with the insert off the refresh writes ZERO levels (lib 0x4C004E30's gate
		// jumps to the zero path at 0x4C005083).
		// The GLOBAL REVERB TOGGLE rewrites (capture 2026-07-11, reverb-toggle-findings):
		//   part 3 reg 0xA: 0x007F (ON) <-> 0x7F00 (OFF)   [direct | dsp-return] pair
		//   part B row0:    0x0366 (ON) <-> 0x0300 (OFF)   reverb SEND level 0x66 <-> 0
		// First-order bus model: the pair crossfades the DAC between the TG's DIRECT
		// output and the DSP RETURN, and the send level scales what the DSP receives.
		// Per-channel granularity is captured but the routing is applied globally
		// (single-mix approximation; per-part separation needs per-part TG audio).
		const int ch = (addr >> 4) & 0x3F, reg = addr & 0x0F;
		m_busreg[(tg << 6) | ch][reg] = data;
		if (tg == 1 && ch == 0x03 && reg == 0x0A)
		{
			m_gain_direct = float((data >> 8) & 0x7F) / 127.0f;
			m_gain_return = float(data & 0x7F) / 127.0f;
		}
		if (tg == 1 && ch == 0x0B && reg == 0x08)
			m_gain_send = float(data & 0x7F) / 127.0f;
		if (tg == 1 && ch == 0x33 && reg == 0x08)
			m_gain_depth = float(data & 0x7F) / 127.0f;   // TOTAL DEPTH (live-verified: 0x8500|depth)
		if (tg == 1 && ch == 0x19 && reg == 0x08)
			m_gain_chorus = float(data & 0x7F) / 127.0f;  // CHORUS send (0x8198 low7 = per-part depth;
			                                              // 0x0B00 off -> 0; routes to CHORUS unit 9 --
			                                              // live-captured unit map, dsp-unit-roles-live-capture.md)
		if (tg == 1 && ch == 0x09 && reg == 0x08)
			m_gain_dsp = float(data & 0x7F) / 127.0f;     // SOUND DSP send (0x8098 low7 = per-part depth;
			                                              // routes to the per-part insert pool u2..u6;
			                                              // RIGHT1 = unit 2 -- live-captured unit map)
		if (tg == 1 && ch == 0x29 && reg == 0x08)
		{
			// MULTI send (0x8298 = row2 of insert part 9; routes to MULTI unit 1). The high
			// byte doubles as the firmware's ON marker: 0x06 (dest = multi-return part)
			// when MULTI is ON, 0x08 when OFF. A COLD panel-MULTI toggle writes 0x0600 --
			// ON marker with level 0, because the depth application is gated on the
			// part-insert flag (see the row-map note above). Substitute the part record's
			// default MULTI depth (0x50, live-read at 0x500B5340+idx*0x54C +0x16) so the
			// cold toggle is audible; a firmware-written nonzero level always wins.
			const uint8_t lvl = data & 0x7F;
			const bool on = ((data >> 8) & 0x0F) == 0x06;
			m_gain_multi = float(lvl ? lvl : (on ? 0x50 : 0)) / 127.0f;
		}
		// PER-EFFECT RETURN levels (reg 0xA low byte = DSP-return level for THIS effect's own
		// bus). Live-captured per-effect toggle map (2026-07-12, notes/effect-return-routing.md):
		// each effect owns a distinct return register -- REVERB=ch03.rA (m_gain_return above),
		// SOUND DSP=ch09.rA, MULTI=ch06.rA -- and toggling one effect changes ONLY its own
		// register. The old model scaled chorus/sound-dsp/multi by the REVERB return (gret), so
		// turning reverb off wrongly muted them; using each effect's own return decouples them.
		// (CHORUS toggling changes ONLY its send ch19.r8 -- it has no separate return register --
		// so the chorus wet is send-driven with a fixed makeup, still decoupled from reverb.)
		if (tg == 1 && ch == 0x09 && reg == 0x0A)
			m_gain_dsp_ret = float(data & 0x7F) / 127.0f;   // SOUND DSP return (0x809A low7)
		if (tg == 1 && ch == 0x06 && reg == 0x0A)
			m_gain_multi_ret = float(data & 0x7F) / 127.0f; // MULTI return (0x806A low7)
	}
	else if (cls == 0x1C02)                           // per-voice aux/mode word
	{
		// bit15 marks the gate-follow voice classes (see key_context/key_break above).
		m_aux[v] = data;
	}
	else if (cls >= 0x0004 && cls <= 0x000A)          // amplitude-envelope params r4..rA
	{
		// The firmware writes the sound's per-voice amplitude EG (7 halfwords, ATK PEAK
		// DCY1 SUS1 DCY2 SUS2 RLS) just before the note-on pitch write. Cache them; the
		// note-on resolves them into a decay/sustain/release. (See notes/tg-envelope-*.)
		m_envreg[v][cls - 0x0004] = data;
	}
}
