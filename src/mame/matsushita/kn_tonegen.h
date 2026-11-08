// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics MN10300 keyboards -- tone-generator HLE, shared base

    Every MN10300-generation Technics keyboard drives its tone generator(s)
    the same way, and unlike most such claims this one is settled by the
    firmware itself rather than by the part numbers. The KN7000 carries two
    `C1BB00000709` LSIs (IC201 master + IC205 sub); the KN6000/KN6500 carry a
    single `D82398GD001` (IC213). Different part numbers -- but the same
    driver architecture, because the two firmwares are re-targets of one
    source tree.

    THE DECISIVE EVIDENCE (static RE, 2026-07-20; see
    notes/kn6000-tonegen-spec.md for the full comparison table):

      * The KN6000's tone-generator write primitive at 0x4849465B is
        BYTE-IDENTICAL to the KN7000's TG-A leg at 0x4C036F7C -- the same 20
        bytes, 81 f8c510 fc8700000598 fae0ffff fc8302000598. The KN7000's
        writer is that same routine with a chip-select branch (cmp 0x40,d0)
        wrapped around it, so the KN7000's two-chip path is literally a
        parameterised generalisation of the KN6000's one-chip path.
      * Both pack the same 32-bit command word (slot<<20)|(class<<16)|data
        and latch it as an ADDRESS halfword to +0 then a DATA halfword to +2,
        with the identical bitfield split (slot at address bit 4, 4-bit
        register index). Both expose the same dual asl-20 / asl-18 addressing
        modes.
      * Both use sixteen halfword registers per voice as four 4-register
        banks of [rate|level] byte-pair envelope segments, and share the
        literal constants 0xFF80/0xFF00 (boot reset), 0xA280/0xA200 and
        0x7F80/0x7F00 (damp pairs), 0xC000 (mute) and 0x87FF (gate on).
      * Both build the 18-bit pitch with the same instruction idiom
        (and 0x00018000 / or 0x4000), carrying pitch bit 16 in class bit 0.
      * Plane 0x20 (the per-channel send/output matrix) and plane 0x28 (the
        global register bank) sit at the SAME plane numbers on both chips.
      * Both use a 0xB4-stride library voice record and a 0x130-stride part
        tone block, over a 34-part model.

    WHAT DIFFERS is numbering and sizing, not behaviour: the per-voice
    register index assignment (the gate is r3 on the KN7000, r0 on the
    KN6000; the envelope banks sit at 0/4/8 vs 4/8/C), the per-voice
    parameter plane numbers below 0x20, the slot count (128 across two
    windows vs 64 in one), the shadow-image stride (0x84 vs 0xA0), and the
    KN7000-only 0x98040010/0x98050010 init strobe.

    So the split is drawn exactly where the evidence draws it:

      BASE (here) -- the MECHANISM, proven identical on both chips: the
        [rate|level] envelope decode and its rate->seconds law, the
        four-stage per-voice envelope state machine and all per-voice state,
        the voice events a decode calls (voice_key_on, voice_start_eg,
        voice_bend, voice_release, voice_mute, voice_set_level), the status
        plane read back by the firmware's voice sweep (tg_read), the
        gate-follow key coupling, the effect-send/return gains, the optional
        synthetic wave pack, and the audio stream and rendering.

      DERIVED (kn7000_tonegen.*) -- the NUMBERING: which plane and which
        register index means what, i.e. the tg_write() decode itself, plus
        the voice count (64 per chip), passed to the base constructor.

    kn6000_tonegen_device is that second decode. Its plane map is only
    partly pinned, and its audio is blocked on the undumped IC13/IC14 table
    ROMs; notes/kn6000-tonegen-spec.md records what matched and what did not.

***************************************************************************/

#ifndef MAME_MATSUSHITA_KN_TONEGEN_H
#define MAME_MATSUSHITA_KN_TONEGEN_H

#pragma once

#include <algorithm>
#include <atomic>
#include <cmath>
#include <utility>
#include <vector>


class kn_tonegen_base_device : public device_t, public device_sound_interface
{
public:
	// directly: with the TG-enable gate open the FIRMWARE drives every voice through
	// tg_write() below, so keying a second sine here would double the notes.
	void note_on(uint8_t)  { }
	void note_off(uint8_t) { }

	// Voices this model's tone generator(s) provide (KN7000 = 128 across two
	// chips, KN6000/KN6500 = 64 in one). Sizes every per-voice loop below.
	int num_voices() const { return m_num_voices; }

	// THE MODEL-SPECIFIC HALF: turn one tone-generator register write into voice
	// events on the shared state below. Each derived device supplies its own chip's
	// register NUMBERING here (which plane and which per-voice index means what);
	// everything that decode drives is shared. The driver's io_w routes every TG
	// write through this, so it must stay virtual -- the machine config decides at
	// runtime which chip's decode is installed (KN7000 two-chip vs KN6000 one-chip).
	//   tg:         which TG window the write came from (KN7000 0 = master/0x98040000,
	//               1 = sub/0x98050000; KN6000/KN6500 have only window 1).
	//   note_x256:  MUSICAL pitch in 1/256-semitone units, resolved by the caller from
	//               the firmware's own library voice record, or -1 if unavailable.
	//   rec_type:   the voice record's synthesis/release class, or -1 if unknown.
	virtual void tg_write(int tg, uint16_t addr, uint16_t data, int32_t note_x256 = -1, int rec_type = -1) = 0;

	// A read of the data port (+2) after an address write: the chip's answer about its voices.
	// The firmware's voice allocator polls the status plane to see which voices still sound
	// and how loud they are. The same numbering on both chips:
	//   0xfc08 + g      sixteen "still sounding" bits, bit i = this chip's voice 16g + i (g = 0..3)
	//   0xfc02 | ch<<4  voice ch's envelope level, 13 bits (the firmware keeps (x & 0x1fff) >> 5)
	uint16_t tg_read(int tg, uint16_t addr);

	// Envelope stages (see notes/tg-envelope-sweep-results.md). The firmware's 7-param
	// amplitude EG: ATTACK to PEAK (r0), DCY1 toward SUS1 (r1), DCY2 toward SUS2 (r2),
	// RELEASE to silence on an r0 write with the release flag (low-byte bit 7: the key-off burst,
	// the 0xFF80 reset) or the 0xC000 steal.
	enum : uint8_t { ST_ATTACK = 0, ST_DECAY1, ST_DECAY2, ST_RELEASE };

	// PROVISIONAL chip rate-byte -> seconds law (higher byte = faster; sweep-calibrated
	// anchors: piano ATK 0xD2 -> 9 ms, piano DCY1 0x39 -> 1.8 s, damp burst 0x91 -> 85 ms,
	// organ rA 0xAE -> 31 ms, pad rA 0x04 -> ~11 s).
	static double eg_tau(uint8_t rate);

	uint32_t tg_write_count() const { return m_tgwrites; }
	// Output-bus routing (reverb toggle) -- polled by the driver into the DSP bridge.
	float gain_direct() const { return m_gain_direct; }
	float gain_return() const { return m_gain_return; }
	float gain_send()   const { return m_gain_send; }
	float gain_depth()  const { return m_gain_depth; }
	float gain_chorus() const { return m_gain_chorus; }
	float gain_dsp()    const { return m_gain_dsp; }
	float gain_multi()  const { return m_gain_multi; }
	float gain_dsp_ret()   const { return m_gain_dsp_ret; }    // SOUND DSP own return (ch09.rA)
	float gain_multi_ret() const { return m_gain_multi_ret; }  // MULTI own return (ch06.rA)

	// Keybed coupling for GATE-FOLLOW voices. The SUB TG chip itself hosts the key-bed
	// event FIFO (the firmware reads it at 0x98050004 = the TG's own +4 register), so the
	// hardware plausibly key-gates certain voice classes with NO CPU write: the sound
	// sweep found aux word (latch 0x1C02+blk*0x10) bit15 set for exactly the sustaining
	// families that receive no key-up TG writes (brass/sax/organ; 8/8 blocks, no false
	// positives). That bit turned out to be wave ROM page bit 2 as the firmware remaps it
	// for hardware subtype 5 (notes/g13-waves-2026-10-20); the KN7000 decode keeps the class
	// by testing that page bit. Model: tag each voice with the key that caused it (the most recent MAKE
	// within 60 ms), and on that key's BREAK release the gate-follow voices it started.
	// (Chord edge case: keys pressed near-simultaneously could mis-tag; acceptable for
	// the placeholder.)
	void key_context(uint8_t key) { m_ctx_key = key; m_ctx_time = machine().time().as_double(); }
	void key_break(uint8_t key);

protected:
	kn_tonegen_base_device(const machine_config &mconfig, device_type type, const char *tag, device_t *owner, uint32_t clock, int num_voices);

	// device_t / device_sound_interface overrides
	virtual void device_start() override ATTR_COLD;

	// The nine effect-send gains below are std::atomic<float> (the driver polls them from
	// its DSP bridge while the sound thread writes them), and save_item() cannot take an
	// atomic. They ARE mutable state -- the firmware sets every one of them from its own
	// register writes -- so leaving them out meant a state saved with, say, reverb engaged
	// restored with the boot-default mix. These two hooks shadow them into a plain array
	// that IS saved, which is the idiomatic MAME answer for non-trivially-copyable state.
	virtual void device_pre_save() override;
	virtual void device_post_load() override;

	// Per-voice amplitude envelope DRIVEN BY THE FIRMWARE'S 7-param EG (r0/r1/r2 rate|level
	// pairs, resolved at note-on -- see tg_write and notes/tg-envelope-sweep-results.md).
	// Full stage chain: linear ATTACK to PEAK (r0), exponential DCY1 toward SUS1 (r1),
	// exponential DCY2 toward SUS2 (r2, the long-tail second stage), then exponential
	// RELEASE to silence when the firmware writes r0 with the release flag (low-byte bit 7: its
	// key-off burst, or the 0xFF80 reset) or the 0xC000 steal mute. A piano (SUS1=SUS2=0) genuinely decays to silence in two stages; an organ
	// (SUS1=SUS2=max) holds; an edited slow attack (r0 hi below ~0xD0) swells audibly.
	virtual void sound_stream_update(sound_stream &stream) override;

	static constexpr int MAX_VOICES = 128;   // the KN7000, the largest of the family

	// The voice slot of chip tg's channel ch, 64 per chip. A one-chip model has only ch.
	int voice_index(int tg, int ch) const { return (m_num_voices > 64) ? ((tg << 6) | ch) : ch; }

	// ---- voice events, called by each model's tg_write() decode ----
	void voice_key_on(int v, uint32_t p18, int32_t note_x256);  // pitch and gate of a note-on
	void voice_start_eg(int v, bool to_silence);   // resolve m_eg012/m_envreg, start the attack
	void voice_bend(int v, uint32_t p18);          // pitch rewrite on a held voice
	void voice_release(int v, uint8_t rate);       // key-off write: release at its rate byte
	void voice_mute(int v);                        // 0xc000 steal: release at the default rate
	void voice_set_level(int v, uint16_t data, uint16_t full);  // per-voice level = data / full

	// What the chip reports about voice v (tg_read): whether it still sounds, and its envelope
	// level as a 13-bit value, full scale 0x1FFF at the EG's level 0x7F. The model's envelope is
	// already in the EG's level domain (PEAK, SUS1 and SUS2 are the register levels / 0x7F), so
	// the level is read in that same domain; the chip's own curve is not known.
	bool voice_sounding(int v) const { return m_stage[v] == ST_ATTACK || voice_level13(v) != 0; }
	uint16_t voice_level13(int v) const { return uint16_t(std::clamp(std::lround(m_env[v] * 0x1FFF), 0L, 0x1FFFL)); }

	// ---- per-voice state and the effect-send gains ----
	// Shared MECHANISM (see the header comment for the firmware evidence); the derived
	// class decodes its own register numbering into these.
	sound_stream *m_stream = nullptr;
	double   m_phase[128] = { };     // per-voice oscillator phase
	double   m_ton[128]   = { };     // note-on machine time (s) -- release detection
	uint16_t m_aux[128]   = { };     // per-voice sample select, low 16 bits (plane 0x1C data)
	uint8_t  m_mode[128]  = { };     // 0=MANAGED (firmware key-up burst) 1=GATE_FOLLOW 2=ONESHOT
	// SYNTHETIC wave-pack playback (kn7000_waves_synthetic.rom, optional). Entries map the
	// runtime sample select -- aux word bank (bits13:12) + zone (bits7:0) -- to donor PCM.
	struct wentry { uint8_t bank, zlo, zhi; const int16_t *pcm; uint32_t len, lstart, llen; double root_hz; };
	std::vector<wentry> m_wentries;
	// FABRICATED DEFAULT SINE (Felipe Sanches' faithful-MECHANISM principle): where no wave
	// ROMs are loaded (the KN6000/KN6500/KN2400 here, or a KN7000 without its dumps), a voice
	// that maps to no donor zone plays a fabricated sine
	// PCM sample through the SAME sample-playback datapath the real chip uses -- there is
	// NO sin() oscillator, exactly as on hardware. m_wdefault indexes that pack entry
	// (pack bank 0xFF); if the optional pack ROM is absent we synthesize the identical
	// sine into m_sine_pcm at start so the datapath is still pure PCM. So m_wsel is never
	// left -1 for a keyed voice -- every voice plays PCM. Faithful mechanism, fabricated data.
	std::vector<int16_t> m_sine_pcm;   // owned buffer for the synthesized fallback sine
	int      m_wdefault = -1;          // pack index of the default sine (-1 = no pack at all)
	int16_t  m_wsel[128];            // wave-pack entry per voice (-1 = none/silent; else PCM)
	uint16_t m_busreg[128][16] = { };// group-0x20 output-bus/effect-send register file
	std::atomic<float> m_gain_direct{ 0.0f };  // DAC crossfade: TG direct (reverb OFF side)
	std::atomic<float> m_gain_return{ 1.0f };  // DAC crossfade: DSP return (reverb ON side)
	std::atomic<float> m_gain_send{ 0.80f };   // TG -> DSP send level (boot default 0x66/0x7F)
	std::atomic<float> m_gain_depth{ float(0x50) / 127.0f };  // REVERB TOTAL DEPTH (0x8338 low7, default 0x50)
	std::atomic<float> m_gain_chorus{ 0.0f };   // CHORUS send (0x8198 low7); 0 = chorus off (default)
	std::atomic<float> m_gain_dsp{ 0.0f };      // SOUND DSP send (0x8098 low7); 0 = off (default)
	std::atomic<float> m_gain_multi{ 0.0f };    // MULTI send (0x8298 low7); 0 = off (default)
	std::atomic<float> m_gain_dsp_ret{ 0.0f };  // SOUND DSP own return (0x809A low7); 0 = off
	std::atomic<float> m_gain_multi_ret{ 0.0f };// MULTI own return (0x806A low7); 0 = off

	// Save-state shadow of the nine atomics above, in the order listed by GAIN_SLOT.
	// Written by device_pre_save(), read back by device_post_load(); never used to render.
	enum : int { GAIN_DIRECT, GAIN_RETURN, GAIN_SEND, GAIN_DEPTH, GAIN_CHORUS,
				 GAIN_DSP, GAIN_MULTI, GAIN_DSP_RET, GAIN_MULTI_RET, GAIN_SLOTS };
	float    m_gain_save[GAIN_SLOTS] = { };
	double   m_wpos[128] = { };      // sample position (fractional)
	uint8_t  m_srckey[128];          // keybed key index that caused this voice (0xFF = none)
	uint8_t  m_ctx_key = 0xFF;       // most recent keybed MAKE (key index)
	double   m_ctx_time = -1.0;      // ...and when it was pushed
	double   m_freq[128]  = { };     // per-voice frequency (Hz)
	double   m_note[128]  = { };     // per-voice musical note at note-on (bend reference)
	uint32_t m_p18ref[128] = { };    // per-voice pitch18 at note-on (bend reference)
	double   m_env[128]   = { };     // per-voice envelope level
	uint8_t  m_gate[128]  = { };     // per-voice gate: 1 = firmware note held, 0 = muted/released
	uint8_t  m_stage[128] = { };     // envelope stage (ST_ATTACK..ST_RELEASE)
	double   m_level[128] = { };     // per-voice level (firmware class 0x2009; 1.0 = default full)
	// Per-voice AMPLITUDE ENVELOPE, driven by the firmware's own 7-param EG. Decoded via
	// the AMPLITUDE EDIT -> ENVELOPE screen sweep (notes/tg-envelope-sweep-results.md):
	// r0 = [ATK rate | PEAK level], r1 = [DCY1 rate | SUS1 level], r2 = [DCY2 rate | SUS2
	// level] (rate bytes: higher = faster; levels 0..0x7F), r3 = gate (0x87FF on / 0x8000
	// key-up). r4..rA DECODED 2026-07-20 (FILTER/PITCH ENVELOPE screen sweeps, see
	// tg-envelope-sweep-results.md RESULT 4): r4/r5/r6 = the PITCH ENVELOPE ([ATK|PEAK]
	// [DCY1|SUS1] [DCY2|SUS2], same pair layout as the amplitude EG), r7 hi = pitch-EG
	// TOTAL DEPTH, r8/r9/rA = the FILTER ENVELOPE (same three pairs), rB lo = filter
	// START POINT. Filter/pitch LEVEL bytes are SIGNED offsets (0 = screen 40) and
	// CUTOFF ADJUST folds into every filter level byte host-side. Neither EG is
	// modelled yet (placeholder timbre has no filter/pitch mod); the bank is kept for
	// the note-on validity check and for rA hi as the release-rate HEURISTIC --
	// semantically the filter-EG DCY2 rate, whose per-sound value tracks the audible
	// release character (organ 0xAE fast stop / pad 0x04 slow fade; 11-family sweep)
	// because these sounds close the filter in step with the amplitude release.
	// Behaviorally validated; kept as-is.
	uint16_t m_eg012[128][3] = { };   // raw r0/r1/r2 per voice (the 7-param amplitude EG)
	uint16_t m_envreg[128][7] = { };  // raw r4..rA per voice (damp/aux bank)
	double   m_peak[128] = { };       // resolved PEAK level 0..1 (r0 lo)
	double   m_sus1[128] = { };       // resolved SUS1 level 0..1 (r1 lo)
	double   m_sus2[128] = { };       // resolved SUS2 level 0..1 (r2 lo)
	double   m_atkstep[128] = { };    // per-sample linear attack increment (r0 hi)
	double   m_d1c[128]  = { };       // per-sample DCY1 coefficient toward SUS1 (r1 hi)
	double   m_d2c[128]  = { };       // per-sample DCY2 coefficient toward SUS2 (r2 hi)
	double   m_rlsc[128] = { };       // per-sample release coefficient (rA hi default,
	                                  // overridden by the key-off r0 write's rate)
	uint32_t m_tgwrites = 0;         // count of firmware pitch writes seen (0 = engine dormant)
	int      m_num_voices;           // 128 (KN7000) or 64 (KN6000/KN6500)

	// ---- playback from the dumped wave ROMs (KN7000; notes/g13-waves-2026-10-20) ----
	// Each tone generator owns one ROM pair, read as one stream of 16-bit words: word 2i is
	// word i of the Y ROM, word 2i+1 word i of the X ROM. The stream is 16 pages of 1 Mi
	// words, each starting with its own directory {A record, P format, B start/16, Q}. A
	// derived device that has the ROMs calls set_wave_pair() at start and rom_voice_start()
	// at note-on; voices started that way play the ROM instead of the wave pack.
	struct rom_sample
	{
		int      pair;                        // which ROM pair
		uint32_t base;                        // stream word of the sample's first word (reversed: one past its last)
		uint32_t ls, le;                      // loop start / end, in samples from the start
		int      exponent;                    // P bits 8:4: a period of 2^(E-9) samples sounds at p18's note
		bool     is8;                         // P bit 3: two 8-bit samples per word, low byte first
		bool     reverse;                     // P bit 9: plays from base - 1 down
		std::vector<std::pair<uint32_t, float>> gain;  // 8-bit: (segment end, gain) in order
	};
	void set_wave_pair(int pair, const uint8_t *y, const uint8_t *x, uint32_t bytes);
	bool has_wave_roms() const { return m_wave[0][0] && m_wave[1][0]; }
	// select the sample for (pair, 20-bit select) and key voice v at pitch p18; false = none
	bool rom_voice_start(int v, int pair, uint32_t sel20, uint32_t p18);
	void rom_voice_pitch(int v, uint32_t p18);           // held voice: new pitch, same sample
	static double rom_rate(uint32_t p18, int exponent);  // source samples per output sample

	const uint8_t *m_wave[2][2] = { };   // [pair][Y, X] ROM bytes; pair 0 = 0x98040000, 1 = 0x98050000
	uint32_t m_wave_bytes = 0;           // bytes per ROM
	std::vector<rom_sample> m_rsamples;                  // samples resolved so far
	std::vector<std::pair<uint32_t, int>> m_rindex;      // (key, m_rsamples index), sorted
	int      m_rsel[128];                // m_rsamples index per voice (-1 = not a ROM voice); derived from m_rkey
	int32_t  m_rkey[128];                // pair<<20 | page<<12 | entry per voice, -1 = none (saved)
	double   m_rpos[128]  = { };         // sample position in the ROM voice
	double   m_rrate[128] = { };         // source samples per output sample
	int      rom_sample_index(uint32_t key);             // resolve (and cache) a sample, -1 = none
	int32_t  rom_word(int pair, uint32_t word) const;    // one 16-bit stream word, signed
	double   rom_fetch(const rom_sample &rs, uint32_t i) const;  // decoded sample i
};

#endif // MAME_MATSUSHITA_KN_TONEGEN_H
