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


DEFINE_DEVICE_TYPE(KN7000_TONEGEN, kn7000_tonegen_device, "kn7000_tonegen", "KN7000 Tone Generator (firmware-driven)")

void kn7000_tonegen_device::device_start()
{
	kn_tonegen_base_device::device_start();
	save_item(NAME(m_auxidx));

	// Each tone generator reads its own ROM pair: the one at 0x98040000 (the firmware's SUB
	// TG, our index 0) IC207 + IC208, the one at 0x98050000 (MAIN TG, index 1) IC203 + IC204
	// -- the pairing the firmware's WAVE ROM test reads through each TG's port, and the one
	// under which every traced voice finds its own sample at the right pitch.
	static const char *const tags[2][2] = {
		{ "waveform_sub_y", "waveform_sub_x" }, { "waveform_main_y", "waveform_main_x" } };
	memory_region *r[2][2];
	for (int p = 0; p < 2; p++)
		for (int c = 0; c < 2; c++)
			r[p][c] = machine().root_device().memregion(tags[p][c]);
	if (r[0][0] && r[0][1] && r[1][0] && r[1][1])
	{
		const uint32_t bytes = r[0][0]->bytes();
		if (bytes >= 0x100000 && r[0][1]->bytes() == bytes && r[1][0]->bytes() == bytes && r[1][1]->bytes() == bytes)
		{
			for (int p = 0; p < 2; p++)
				set_wave_pair(p, r[p][0]->base(), r[p][1]->base(), bytes);
			osd_printf_info("kn7000 tonegen: playing the wave ROMs (IC203/204, IC207/208)\n");
		}
	}
}

void kn7000_tonegen_device::tg_write(int tg, uint16_t addr, uint16_t data, int32_t note_x256, int rec_type)
{
	if ((addr & 0xFF00) == 0xFC00) return;            // 0xFC0x idle / status refresh
	const int v = voice_index(tg, (addr >> 4) & 0x3F);  // voice 0..127 (0..63 sub, 64..127 master)
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
			voice_key_on(v, p18, note_x256);
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
			// The sweep's "aux bit15" was measured with the driver reporting hardware subtype 5,
			// under which the firmware remaps the ROM page (TgVoiceRouteFieldSet, tables at
			// 0x48587774) and select bit 15 is page bit 2. The driver now reports the subtype the
			// dumped ROMs need (pages unmapped), so the same voice class is page bit 2 here.
			const uint32_t page = (uint32_t(m_auxidx[v]) << 4) | (m_aux[v] >> 12);
			if (BIT(page, 2))           m_mode[v] = 1;             // gate-follow
			else if (managed_type)      m_mode[v] = 0;             // firmware-managed release
			else if (rec_type >= 0)     m_mode[v] = 2;             // one-shot (pluck classes)
			else                        m_mode[v] = 0;             // unknown record: safest = managed
			const double nowt = machine().time().as_double();
			m_srckey[v] = (m_ctx_time >= 0.0 && (nowt - m_ctx_time) < 0.060) ? m_ctx_key : 0xFF;
			// Sample select: (bank,zone) from the aux word -> donor wave, else the
			// fabricated default sine (m_wdefault). Never -1 -> the voice always plays
			// PCM through the single sample-playback datapath (no sin() oscillator).
			if (has_wave_roms())
			{
				// The dumped wave ROMs: this TG's own pair, page and entry from the 20-bit
				// select, rate from pitch18 and the sample's exponent. A select with no sample
				// (an expansion-board page, with no board) plays nothing, as the chip would.
				rom_voice_start(v, tg, (uint32_t(m_auxidx[v]) << 16) | m_aux[v], p18);
				m_wsel[v] = -1;
			}
			else
			{
				m_rsel[v] = -1;
				m_rkey[v] = -1;
				const int bank = (m_aux[v] >> 12) & 3, zone = m_aux[v] & 0xFF;
				m_wsel[v] = int16_t(m_wdefault);
				for (size_t i = 0; i < m_wentries.size(); i++)
					if (m_wentries[i].bank == bank && zone >= m_wentries[i].zlo && zone <= m_wentries[i].zhi)
						{ m_wsel[v] = int16_t(i); break; }
				m_wpos[v] = 0.0;
			}
			// The amplitude EG from r0/r1/r2, the default release from rA. ONESHOT plucks (no
			// key-up ramp) die out naturally: their decay chain runs to silence.
			voice_start_eg(v, m_mode[v] == 2);
		}
		else
			voice_bend(v, p18);
		m_tgwrites++;
	}
	else if (cls == 0x0000)                           // r0 = [ATK rate | PEAK level]
	{
		m_eg012[v][0] = data;                         // cache for the next note-on resolve
		// KEY-RELEASE. The low byte is [release flag | level]: the note-on programs r0 with
		// bit 7 clear (0xD27F, 0x557F: attack rate | PEAK), while every key-off and reset
		// write has it set with level 0 (0x9180, 0xAA80, 0xC280, the 0xFF80 reset; the
		// KN5000's damp pairs 0x7F80/0xA280 too). At key-off the firmware sends that r0 in
		// a 6-write burst (r0, r1, r4, r5, r8, r9: TgVoiceEgBurstWrite) to EVERY voice of
		// the note (notes/tg-release-2026-10-21). So the flag releases this voice, at the
		// write's own rate byte -- the piano damp 0x91 -> ~85 ms under the provisional law.
		// (It used to release the even/odd pair after a 20 ms guard: that matched what the
		// firmware sent while the status reads (tg_read) answered 0, which made the firmware
		// drop all but one voice of a note within 0.1 s of its note-on.)
		if (BIT(data, 7))
			voice_release(v, data >> 8);
	}
	else if (cls == 0x0001)                           // r1 = [DCY1 rate | SUS1 level];
	{                                                 // 0xC000 = mute (boot init / voice-steal)
		m_eg012[v][1] = data;
		if (data == 0xC000) voice_mute(v);
	}
	else if (cls == 0x0002)                           // r2 = [DCY2 rate | SUS2 level]
	{
		m_eg012[v][2] = data;
	}
	// r3 is not a gate: TgVoiceGateOn writes 0x87FF and TgVoiceGateOff the voice's cached word
	// (0x8000-0xF000) about 0.1 ms later, inside every note-on, with class 0x3000 bit 14 set
	// and cleared around them -- a key-on strobe. Neither is written at key-off.
	else if (cls == 0x2009)                           // per-voice level (best-effort)
	{
		// The firmware writes this once at note-on; in the default full-velocity
		// patch it is 0x5FFF, so normalising by 0x5FFF keeps that voice at unity
		// (no change to the current sound) while honouring softer/louder values
		// the firmware would emit for MIDI velocity or the mixer's part volumes.
		voice_set_level(v, data, 0x5FFF);
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
		m_busreg[voice_index(tg, ch)][reg] = data;
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
	else if ((addr & 0xFC00) == 0x1C00)               // plane 0x1C: the 20-bit sample select
	{
		// select bits 19:16 travel in the register index, bits 15:0 in the data; bits 19:12
		// are the wave ROM page, 11:0 the directory entry. Page bit 2 also marks the
		// gate-follow voice classes (see key_context/key_break and the note-on above).
		m_aux[v] = data;
		m_auxidx[v] = addr & 0x0F;
	}
	else if (cls >= 0x0004 && cls <= 0x000A)          // amplitude-envelope params r4..rA
	{
		// The firmware writes the sound's per-voice amplitude EG (7 halfwords, ATK PEAK
		// DCY1 SUS1 DCY2 SUS2 RLS) just before the note-on pitch write. Cache them; the
		// note-on resolves them into a decay/sustain/release. (See notes/tg-envelope-*.)
		m_envreg[v][cls - 0x0004] = data;
	}
}

