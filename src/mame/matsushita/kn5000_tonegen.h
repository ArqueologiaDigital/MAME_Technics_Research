// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics KN5000 Tone Generator (IC303 - TC183C230002)

    64-voice PCM wavetable synthesizer with register-indirect interface.
    Reads waveform data from 4x 32Mbit ROMs (IC304-IC307).

***************************************************************************/

#ifndef MAME_MATSUSHITA_KN5000_TONEGEN_H
#define MAME_MATSUSHITA_KN5000_TONEGEN_H

#pragma once

#include "cpu/upd6383/upd6383.h"

#include <cstdio>
#include <deque>
#include <map>
#include <queue>
#include <string>
#include <vector>

class kn5000_tonegen_device :
	public device_t,
	public device_sound_interface
{
public:
	kn5000_tonegen_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock);

	// Register-indirect interface (SubCPU memory-mapped)
	void addr_w(uint16_t data);    // 0x100000: register address latch
	uint16_t status_r();           // 0x100000: active-voice bitmap readback (poll)
	void data_w(uint16_t data);    // 0x100002: register data write
	uint16_t data_r();             // 0x100002: register data read (status)

	// Keyboard input interface (keybed events from IC303)
	uint16_t kbd_status_r();       // 0x110002: bit 0 = data ready
	uint16_t kbd_data_r();         // 0x110000: note/velocity data

	// Queue a keybed event (from external keybed scanner)
	void push_keybed_event(uint16_t data);

	// Waveform ROM access
	void set_waveform_region(const char *tag) { m_waveform_region_tag = tag; }

	// ---- IC311, the effects DSP: a SEND/RETURN INSERT on this chip ----------
	// MEASURED on the service manual (pp. 34/35, notes/dsp-audiopath-wiring.md
	// sect. 1): this chip's SDOA/SDOB/SDO1 feed IC311's DI1/DI2/DI3 and IC311's
	// DO1/DO2 come back into this chip's SDIA/SDIB. The MAIN MIX leaves on a
	// DIFFERENT pin, SDO0, straight to IC310 and the DAC -- so IC311 can only
	// ever ADD to the output. This chip also GENERATES IC311's LRCK (pin 208),
	// so one DSP frame per output sample is the hardware relationship.
	// set_dsp1_enable_port() names a driver ioport whose bit 0 gates the whole
	// thing; unset or 0 means the DSP is never called at all.
	template <typename T> void set_dsp1(T &&tag) { m_dsp1.set_tag(std::forward<T>(tag)); }
	template <typename T> void set_dsp1_enable_port(T &&tag) { m_dsp1_enable.set_tag(std::forward<T>(tag)); }

	// ---- DIAGNOSTIC render mode ---------------------------------------------
	// set_render_mode_port() names a driver ioport whose bit 0 chooses how a voice's
	// raw sample is produced: 0 = real PCM out of the wave ROM (normal), 1 = a sine
	// synthesised at the voice's own frequency, touching no wave-ROM PCM at all.
	// EVERYTHING else -- note on/off, allocation, pitch tracking, the amplitude EG,
	// the TVF, panning, the mixer, the silence interlock -- is the same code in both
	// modes; the two differ at exactly one `if` in sound_stream_update(). That is the
	// whole point: it isolates "is the glitch in the sample data / addressing?" from
	// "is it in the machinery around it?". Unset or 0 means PCM.
	template <typename T> void set_render_mode_port(T &&tag) { m_render_mode.set_tag(std::forward<T>(tag)); }

	static constexpr int NUM_VOICES = 64;
	static constexpr int NUM_GLOBAL_REGS = 16;

	// ★ THE TWO RATES, WHICH ARE NOT THE SAME NUMBER (§228).
	//   STREAM_RATE     -- what MAME RENDERS at.  Unchanged, and load-bearing:
	//                      the EG rate law, the voice LP coefficient and the
	//                      pitch step are all expressed against it.
	//   DSP_FRAME_RATE  -- IC311's LRCK, i.e. the instrument's Fs.  44 100, by
	//                      four independent ROM-internal proofs; see
	//                      upd6383.h m_frame_hz.  44100/48000 = 147/160 exactly.
	static constexpr uint32_t STREAM_RATE    = 48000;
	static constexpr uint32_t DSP_FRAME_RATE = 44100;

protected:
	virtual void device_start() override ATTR_COLD;
	virtual void device_reset() override ATTR_COLD;
	virtual void device_stop() override ATTR_COLD;

	// device_sound_interface
	virtual void sound_stream_update(sound_stream &stream) override;

private:
	// Register address encoding:
	// Bits 15-8: register group
	// Bits 7-6: sub-bank (0-3)
	// Bits 5-0: channel (0-63)
	static constexpr int REG_CHANNEL_MASK = 0x3F;
	static constexpr int REG_BANK_SHIFT = 6;
	static constexpr int REG_BANK_MASK = 0x03;
	static constexpr int REG_GROUP_SHIFT = 8;

	// Voice state
	struct voice_t
	{
		// Register banks (32 registers = 8 groups x 4 banks)
		// Groups: 0x00, 0x01, 0x04, 0x05, 0x06, 0x08, 0x09, 0x0A
		static constexpr int NUM_REGS = 32;
		uint16_t regs[NUM_REGS];

		// Playback state
		bool     active;        // Voice is producing sound
		bool     key_on;        // Key is pressed
		double   key_on_time;   // machine time (s) of the note-on gate — used to
		                        // distinguish note-on EG programming (same burst,
		                        // <1ms after gate) from a note-off release burst.

		// ---- AMPLITUDE ENVELOPE GENERATOR (GAP CAL-1) --------------------------------
		// The three-segment EG the firmware programs into +0x800 / +0x840 / +0x880, each
		// word = (target_level << 8) | rate. The level is a LOG amplitude at exactly
		// 16 counts per octave (DERIVED — see eg_level_to_gain in the .cpp), so the ramp
		// is linear in level units, i.e. linear in dB.
		double   eg_level;      // current level code, 0..255 (0 = silence, 255 = 0 dB)
		double   eg_target;     // the running segment's target level code
		double   eg_step;       // level units per output sample; 0 = HOLD (rate 0)
		int      eg_seg;        // 0/1/2 = which of +0x800/+0x840/+0x880 is running
		bool     eg_running;    // R1 latch: SET by the 0x81xx gate, CLEARED by 0x7E00 or
		                        // by genuine silence (R2s). This — not "is it loud yet" —
		                        // is what status_r reports, because the firmware's
		                        // teardown edge is pre-armed at allocation.
		uint32_t silent_samples; // R2s interlock: consecutive output samples whose rendered
		                        // contribution rounded below 0.5 LSB of the 16-bit output.
		uint32_t wave_offset;   // Current playback position (16.16 fixed point), relative
		                        // to wave_start; runs 0 .. loop_end then loops [loop_start,loop_end).
		uint32_t wave_start;    // Start byte offset (into the waveform ROM region) of the
		                        // selected waveform's FULL multi-cycle PCM recording.
		uint32_t wave_samples;  // Total samples in the recording (full attack+body played once).
		uint32_t loop_start;    // Sustain-loop start sample (held notes loop [loop_start,loop_end)).
		uint32_t loop_end;      // Sustain-loop end sample; loop length = loop_end-loop_start is
		                        // an integer multiple of pitch_period so the seam is pitch-continuous.
		uint32_t pitch_period;  // Fundamental period, whole samples (see update_pitch / detect_period).
		                        // 0 = the recording is APERIODIC (drum/SFX) -> played at native rate.
		uint32_t pitch_period_q16; // The same period in 16.16 — what the playback rate is derived
		                        // from, so the note is not detuned by the rounding to whole samples.
		int      wave_bank;     // Wave-ROM bank  = +0x040 bits[15:14]  (1 = IC307, the one real dump)
		int      wave_page;     // 1 MB page      = +0x040 bits[13:12]
		int      wave_chunk;    // Directory slot = +0x040 bits[11:0], a plain 0-based index into
		                        // that page's own self-delimiting directory. See decode_wave_select().
		bool     wave_real;     // The +0x040 word names a chunk on the ONE hardware-rooted dump
		                        // (IC307) and lands inside that page's real directory. Only then
		                        // is the {chunk <-> +0x400} pitch relation meaningful, because on
		                        // an undumped socket the chunk actually played is a substituted,
		                        // unrelated recording. See resolve_note_group().
		uint32_t pitch_step;    // Pitch increment (16.16 fixed point)
		// ---- diagnostic sine mode only (see set_render_mode_port) ----------
		// A DEDICATED accumulator, not a reuse of wave_offset: wave_offset has only
		// 16 integer bits and is re-based on loop_start by the loop wrap, so it
		// cannot free-run as a phase. Q32 turns gives a 48000/2^32 = 11 uHz quantum,
		// i.e. sub-cent at every note; a 16.16 phase would be ~46 cents out at the
		// bottom of the keyboard.
		uint32_t sine_phase;    // Q32 turns, free-running
		uint32_t sine_inc;      // Q32 turns per output sample = hz * 2^32 / STREAM_RATE
		                        // 0 = this voice has no absolute pitch -> stays silent
		int16_t  volume_l;      // Left  PAN gain, Q15 (0-32767) — from +0x180, see update_voice_params.
		int16_t  volume_r;      // Right PAN gain, Q15 (0-32767). Loudness is the EG's job, not these.
		uint32_t release_counter; // Samples remaining in release phase (0 = no release)
		uint32_t hold_counter;  // Samples remaining in hold phase after key-off
		int      env_level;     // Low 9 bits of the group0/bank0 HAND-OFF word (0xF0xx/0xFExx),
		                        // used as a linear amplitude. That reading is WRONG — the word
		                        // is written exactly once per note, right before the firmware
		                        // frees the channel, and its low bits are an undecoded
		                        // hand-off parameter. It is retained only because removing it
		                        // turns the accompaniment into a saturated drone. The full
		                        // evidence, and what has to be decoded to fix it properly, are
		                        // in the comment on data_w().
		double   lp_a;          // One-pole low-pass coefficient for the per-voice TVF driven by
		                        // +0x100 (see update_timbre). 0.0 = filter bypassed.
		double   lp_z;          // ... and its state.
		int      true_note;     // MIDI note recovered from the keybed/MIDI input FIFO at
		                        // key-on (−1 = unknown → r8-relative fallback). Used to
		                        // resolve equal-tempered pitch (see update_pitch()).
		double   chord_time;    // press time of the chord this voice belongs to, used to
		                        // group simultaneous voices for polyphonic note pairing
		                        // (−1e9 = none). See assign_chord_notes().
		double   pitch_offset;  // semitones this voice sounds ABOVE its played note, taken
		                        // from +0x400: the partial's coarse/fine transpose and the
		                        // unison detune. 0 = sounds at the played note.
		                        // See resolve_note_group().
		uint8_t  pitch_anchor;  // pitch_anchor_t: WHERE the absolute pitch of this voice came
		                        // from. Diagnostic only — nothing reads it back to render.
		                        // Censused per note-on and reported at device_stop, so the
		                        // fallback share is stated out loud rather than assumed.

		void reset()
		{
			std::fill(std::begin(regs), std::end(regs), 0);
			// +0x180 (regs[6]) is the PAN register and the firmware's own default for it is
			// 0x0040 = CENTRE (LABEL_0272A3, v142 asm L21912). It MUST be initialised to that:
			// a voice whose +0x180 is never written would otherwise decode as pan 0x00 and
			// render HARD LEFT. See update_voice_params().
			regs[6] = 0x0040;
			active = false;
			key_on = false;
			key_on_time = 0.0;
			eg_level = 0.0;
			eg_target = 0.0;
			eg_step = 0.0;
			eg_seg = 0;
			eg_running = false;
			silent_samples = 0;
			wave_offset = 0;
			wave_start = 0;
			wave_samples = 0;
			loop_start = 0;
			loop_end = 0;
			pitch_period = 0;
			pitch_period_q16 = 0;
			wave_bank = 0;
			wave_page = 0;
			wave_chunk = 0;
			wave_real = false;
			pitch_step = 0x10000; // 1.0 = native pitch
			sine_phase = 0;
			sine_inc = 0;
			volume_l = 0;
			volume_r = 0;
			release_counter = 0;
			hold_counter = 0;
			env_level = 0xFF;
			lp_a = 0.0;
			lp_z = 0.0;
			true_note = -1;
			chord_time = -1e9;
			pitch_offset = 0.0;
			pitch_anchor = 0;   // ANCHOR_KEYBED
		}
	};

	// ---- WHERE A VOICE'S ABSOLUTE PITCH CAME FROM -----------------------------------
	// Ordered best-evidence first. update_pitch() walks this ladder and records which
	// rung it stopped on, so the run's own log states the coverage split instead of
	// leaving a silent fallback to be discovered later. See update_pitch().
	enum pitch_anchor_t : uint8_t
	{
		ANCHOR_KEYBED = 0,      // true_note >= 0: a real keybed / USB-MIDI event. UNCHANGED.
		ANCHOR_FIRMWARE,        // firmware C table, selector carries exactly ONE C
		ANCHOR_FIRMWARE_AMBIG,  // firmware C table, selector carries >1 C -> modal value used
		ANCHOR_LEARNED,         // no firmware C; the chunk's runtime-LEARNED trim was pinned
		ANCHOR_CONSTANT,        // ⚠ nothing placed it: the old 0x3524 constant. Not a measurement.
		ANCHOR_NONE,            // no pitch information at all (regs[8] == 0) -> silent sine
		ANCHOR_COUNT
	};

	// ---- Wave-ROM page directory -------------------------------------------------
	//
	// MEASURED (notes/kn5000-structural-validation.md §1): a KN5000 wave ROM is FOUR
	// self-delimiting directories, one per 1 MB page — not one index plus 3 MB of
	// un-indexed PCM, as the older content map assumed. Each page begins with its own
	// index of {param_ptr, wave_offset} u16 pairs whose length is encoded in entry 0
	// (`entry0.param_ptr == 4 * count`), followed by the parameter records and then
	// s16le PCM. IC307's four counts are 198 / 168 / 1072 / 57, and every one of the
	// 1495 parameter records starts with a redundant copy of its own `wave_offset`
	// (1495/1495 — a back-reference an accidental pattern cannot satisfy).
	struct page_dir_t
	{
		uint32_t base = 0;                  // region byte offset of this 1 MB page
		uint32_t count = 0;                 // directory slots (0 = no valid directory here)
		std::vector<uint32_t> pcm_start;    // region byte offset of each chunk's PCM
		std::vector<uint32_t> pcm_samples;  // s16le sample count of each chunk
		std::vector<uint32_t> period;       // measured fundamental, whole samples (0 = aperiodic)
		std::vector<uint32_t> period_q16;   // the same fundamental in 16.16 fixed point. A real
		                                    // fundamental is NOT a whole number of samples, and
		                                    // rounding it to one detunes the note by up to
		                                    // 1200/(2*P) cents — ~30 cents where P is only ~20
		                                    // samples, as it is at the top of the piano bank.
		std::vector<uint32_t> loop_start;   // sustain-loop start sample within the chunk
		std::vector<uint32_t> loop_len;     // sustain-loop length (integer multiple of period)
		std::vector<uint8_t>  analysed;     // period/loop computed for this chunk yet?

		// ---- per-chunk LOG-PITCH TRIM, learned from the register stream -----------------
		// +0x400 (regs[8]) is an ABSOLUTE log pitch at 0x100 units/semitone, offset by a
		// constant that belongs to the CHUNK (the recording's own tuning/root trim):
		//     regs[8] = 0x100 * note + 0x80 + trim(chunk)
		// MEASURED over the firmware's 143 stride-6 multisample SET descriptors x 128 keys:
		// the trim is a function of the +0x040 word ALONE — 367 of 368 chunks carry exactly
		// one value across every SET, patch and key that reaches them (the single exception,
		// +0x040 = 0x6028, carries two values 3072 apart = one octave: a drawbar footage wave
		// deliberately reused an octave up). So one observation of a chunk pins it, and the
		// note can then be read straight out of the register.
		//
		// It is only learned from a note-on the device can prove is UNTRANSPOSED (see
		// kn5000_tonegen_device::assign_chord_notes), because a transposed partial reports the
		// PLAYED note against a register that carries the SOUNDING one — an error of exactly
		// one octave, indistinguishable after the fact.
		//   state 0 = never learned;  1 = learned;  2 = CONFLICTED (two observations more than
		//   half a semitone apart -> the chunk cannot serve as a pitch anchor).
		std::vector<int32_t> trim;
		std::vector<uint8_t> trim_state;
	};

	// Which wave-ROM chunk a +0x040 value names.
	struct wave_ref_t
	{
		int  bank;          // +0x040 bits[15:14]
		int  page;          // +0x040 bits[13:12]
		int  chunk;         // directory slot actually used
		int  entry;         // +0x040 bits[11:0] as written by the firmware
		bool out_of_range;  // entry >= directory count (only reachable on an undumped bank)
		bool undocumented;  // entry above the highest value the firmware's own tables use
		bool substituted;   // this bank has no directory of its own; IC307's was used
	};

	static constexpr int NUM_BANKS = 4;
	static constexpr int PAGES_PER_BANK = 4;
	static constexpr uint32_t PAGE_SIZE = 0x100000;   // a u16 wave_offset x16 addresses exactly 1 MB
	static constexpr int IC307_BANK = 1;              // the one hardware-rooted dump

	void update_voice_params(int ch);
	// ---- amplitude EG (GAP CAL-1) ------------------------------------------------
	// LEVEL byte -> linear gain, DERIVED from the sub-CPU's own log table (see the .cpp).
	float  eg_level_to_gain(double level) const;
	// RATE byte -> level units per output sample (0 = HOLD).
	static double eg_rate_to_step(int rate);
	// Load segment `seg` (0/1/2 = +0x800/+0x840/+0x880) as the running segment.
	void load_eg_segment(int ch, int seg);
	// Per-voice TVF (filter / brightness) from +0x100 = regs[4]. See the comment on the
	// definition for the full firmware derivation.
	void update_timbre(int ch);
	void update_pitch(int ch);
	// The firmware's per-selector absolute-pitch constant C, for the +0x040 word `sel`.
	// Returns false if the firmware's own multisample SET descriptors never produce that
	// selector, in which case NOTHING is written to `c`/`ambiguous`. Pure table lookup over
	// the generated kn5000_pitch_trim.hxx; no state, no ROM access.
	static bool firmware_pitch_trim(uint16_t sel, int32_t &c, bool &ambiguous);
	// +0x400 handling: a voice's log pitch REFERRED TO ITS OWN RECORDING (so it can be
	// compared across chunks), and the per-key-press resolution of transpose + detune.
	double voice_rho(int ch) const;
	void resolve_note_group(double tchord, int note);
	void process_key_on(int ch);
	void process_key_off(int ch);
	int16_t read_waveform_sample(uint32_t byte_offset) const;
	// The sine mode's counterpart to read_waveform_sample(): same role, same output
	// range, no ROM access.
	int32_t sine_sample(uint32_t phase) const;
	void resolve_waveform(int ch);

	// Real-waveform selection from register +0x040 (= regs[1]) ONLY (chip boundary).
	// DATA-DERIVED — the wave ROM's own directories decode it (no heuristic, no table
	// of guessed constants):
	//
	//     page      = (w >> 12) & 3          1 MB page inside the bank
	//     bank      = (w >> 14) & 3          which wave ROM   (1 = IC307)
	//     chunk     =  w        & 0x0FFF     plain 0-based slot in THAT page's directory
	//
	// Validated by predict-then-check: the directory sizes the firmware's tone tables
	// REQUIRE (max entry + 1 per class: 198 / 168 / 57) equal the directory sizes IC307
	// itself DECLARES on pages 0 / 1 / 3 — 3/3 exact — and all 465 (class, entry) pairs
	// the firmware uses on those pages land in range with base 0.
	// See notes/kn5000-datamap-applied.md and notes/kn5000-structural-validation.md.
	wave_ref_t decode_wave_select(uint16_t w) const;
	void parse_page_directories();
	void analyse_chunk(page_dir_t &d, int chunk);
	// Returns the measured fundamental in 16.16 fixed point (0 = the recording is aperiodic).
	uint32_t detect_period(uint32_t region_byte_start, uint32_t samples) const;

	// Amplitude-EG gain curve, built at device_start: index = round(level * 16), so
	// 0..4080 covers level codes 0..255 at 1/16-count (0.0235 dB) resolution. Built from
	// the DERIVED law gain = 2^((L-255)/16); tabulated because it is evaluated once per
	// voice per output sample.
	static constexpr int EG_GAIN_TABLE = 4096;
	float m_eg_gain[EG_GAIN_TABLE];

	// ---- diagnostic sine oscillator ------------------------------------------
	// SINE_PEAK is chosen to match the wave ROM's typical RMS, not its peak. MEASURED
	// on the IC307 dump: the PCM is peak-normalised (median chunk peak 32713, 89.7% of
	// 1495 chunks peaking >= 32000) with a median crest factor of 5.38 dB, so a
	// peak-matched sine would sit ~6 dB hotter than the material it stands in for.
	// Body RMS medians are 11364 / 10929 / 18652 / 3619 for pages 0..3; a 16384 peak
	// gives RMS 11585, within 0.2 dB of the melodic multisample pages, and is a clean
	// power of two that leaves headroom under the 0.85 softclip knee with 64 voices.
	// ⚠ Sine and PCM mode are therefore NOT level-matched sample for sample -- see the
	// mode banner in sound_stream_update().
	static constexpr int     SINE_TABLE = 4096;
	static constexpr int32_t SINE_PEAK  = 16384;
	int16_t m_sine_tab[SINE_TABLE];

	// State
	uint16_t     m_addr_latch;           // Current register address
	uint16_t     m_global_regs[NUM_GLOBAL_REGS]; // Global configuration
	voice_t      m_voice[NUM_VOICES];
	sound_stream *m_stream;

	// Keybed event queue
	std::queue<uint16_t> m_keybed_queue;

	// Pending keybed/MIDI note-ons (machine time, MIDI note), used to recover the
	// TRUE musical note for each voice at key-on. The IC303 registers only carry a
	// sample-zone-RELATIVE pitch (reg[8] steps 0x100/semitone within a multisample
	// zone; the per-zone sample root lives in the undumped wave ROM), so absolute
	// pitch cannot be derived from the registers alone. Instead we correlate each
	// voice note-on with the real input event that caused it. See update_pitch().
	std::deque<std::pair<double,int>> m_pending_notes;
	void assign_chord_notes(int ch);
	uint32_t voice_pitch_index(int ch) const;

	// Waveform ROM
	const char  *m_waveform_region_tag;
	const uint8_t *m_waveform_data;
	uint32_t     m_waveform_size;

	// ---- IC311 effects-DSP send/return (see set_dsp1 above) -----------------
	optional_device<upd6383_device> m_dsp1;
	optional_ioport                 m_dsp1_enable;
	// bit 0: 0 = PCM from the wave ROM (default), 1 = diagnostic sine. Read ONCE per
	// stream update, never cached in a member -- see set_render_mode_port above.
	optional_ioport                 m_render_mode;

	// LOG_CENSUS diagnostic only (VERBOSE bit 6); not save-stated, not load-bearing.
	double   m_census_last  = -1e9;
	uint32_t m_census_nopcm = 0;
	uint32_t m_census_clr[5] = { 0, 0, 0, 0, 0 };
	// LOG_GLITCH diagnostic only (VERBOSE bit 7); not save-stated, not load-bearing.
	// Previous PER-VOICE post-pan contribution, so a step can be attributed to the voice
	// that produced it rather than to the mix. Zeroed whenever a voice contributes nothing.
	int32_t  m_glitch_prev[NUM_VOICES][2] = { };
	int32_t  m_glitch_prev2[NUM_VOICES][2] = { };   // one sample older still
	int32_t  m_glitch_mix[2] = { 0, 0 };            // previous FINAL output sample
	// Per-CHUNK glitch census. Logging one line per click loses events on a long run, so the
	// attribution is accumulated here and reported ONCE, at device_stop.
	struct glitch_stat_t
	{
		uint64_t events = 0, wraps = 0, clamps = 0, sum_d = 0;
		uint32_t max_d = 0, samples = 0, period = 0, max_step = 0;
		bool     real = false;
	};
	std::map<uint32_t, glitch_stat_t> m_glitch_chunk;   // key = bank<<20 | page<<16 | chunk
	uint64_t m_glitch_total = 0, m_mixclick_total = 0;

	// ---- PER-NOTE-ON CAPTURE (env var KN5000_NOTELOG=<path>; DEFAULT OFF) ------------
	// One CSV row per note-on gate, carrying BOTH the programming that the note started
	// with AND the outcome it actually produced (peak / RMS of this voice's own post-pan
	// contribution over its lifetime). It is a pure observer: nothing here is read back by
	// the render, so with the variable unset the only cost is a null-pointer test per
	// note-on and per rendered sample, and with it set the audio is bit-identical (VERIFIED
	// by md5 of the -wavwrite capture, see notes).
	//
	// It is a RUNTIME switch on purpose. The pre-existing LOG_* masks are compile-time
	// (VERBOSE), so proving "instrumented == uninstrumented" with them would compare two
	// different binaries; with an env var the same binary produces both captures, which is
	// the only version of that check that can actually fail.
	std::FILE *m_notelog = nullptr;
	struct notelog_rec_t
	{
		bool     open = false;
		double   t_on = 0.0;
		uint64_t nsamp = 0;      // samples this voice actually rendered
		int32_t  peak = 0;       // max |post-pan contribution|, either channel
		double   sumsq = 0.0;    // for RMS of (L+R)/2
		int      env_hand = -1;  // env_level carried by the group0/bank0 hand-off word
		double   t_hand = -1.0;  // when that word arrived
		double   t_ko = -1.0;    // when process_key_off() fired for this note
		int      ko_src = 0;     // 0 = never released, 1 = group9 release heuristic,
		                         // 2 = the firmware's own 0x7E00 free
		// ENVELOPE PROFILE. "A quick click followed by a very faint sound" and "a note at
		// the right level" are indistinguishable in a peak, and only barely distinguishable
		// in an RMS — so the row also carries the SHAPE: the peak |contribution| in each of
		// NPROF consecutive 10 ms windows from the gate. That is the measurement Felipe's
		// description is actually about, and it is the one a crest factor can only hint at.
		static constexpr int NPROF = 24;      // 240 ms
		static constexpr int PROF_SAMPLES = 480;  // 10 ms at the 48 kHz stream rate
		uint64_t s0 = 0;         // stream sample clock at the gate
		int32_t  prof[NPROF] = { };
		// The SAME buckets, but carrying the amplitude EG's own state at the end of each
		// window: eg_level rounded, and the running segment index. Without this an
		// amplitude collapse can only be attributed to "the envelope" in the abstract; with
		// it, the level trajectory and the segment that produced it are both on the row.
		// -1 = the voice rendered no sample in that window.
		int16_t  eglvl[NPROF];
		int8_t   egseg[NPROF];
		// WHY the envelope left a segment. Each entry is the (target,rate) word that was
		// RUNNING at the moment the EG advanced out of segment 0 and out of segment 1,
		// together with the level it was at and the rendered-sample offset. Parking on
		// segment 2 versus segment 1 is what separates an audible note from a faint one in
		// this instrument, so the row has to carry the word whose rate allowed the hop.
		uint16_t adv_word[2] = { 0xFFFF, 0xFFFF };  // regs[20+seg] as the hop was taken
		int16_t  adv_lvl[2]  = { -1, -1 };
		int32_t  adv_at[2]   = { -1, -1 };          // rendered-sample offset of the hop
		std::string head;        // the note-on half of the row, formatted at the gate
	};
	// Free-running output-sample counter, used ONLY to bucket the profile above. The gate
	// arrives between stream updates, so the note-on is timestamped with the clock as of
	// the last rendered sample; the quantisation is at most one stream block.
	uint64_t m_nl_sampclock = 0;
	notelog_rec_t m_nl[NUM_VOICES];
	void notelog_begin(int ch);
	void notelog_seg_advance(int ch);
	void notelog_flush(int ch, const char *reason);

	// ---- PITCH-ANCHOR CENSUS (diagnostics only, reported at device_stop) -------------
	// Counted ONCE PER NOTE-ON (in process_key_on, after update_pitch has decided), so the
	// numbers are directly comparable with the offline capture analysis in
	// tools/kn5000-rootpitch/decode.py, which counts note-on events too. The fallback to
	// the 0x3524 constant is NOT a measurement and must never be silent: the selectors that
	// reach it are listed by name so the next pass can extend the table rather than guess.
	uint64_t m_anchor_census[ANCHOR_COUNT] = { };
	std::map<uint16_t, uint64_t> m_anchor_unplaced;     // +0x040 words with no C at all
	// diagnostics only, reported at device_stop
	uint64_t m_dsp1_frames = 0;      // frames handed to IC311
	//  ★ §31: DSP input-stage clipping census (see kn5000_tonegen.cpp)
	uint64_t m_insta_n = 0, m_insta_clip = 0, m_insta_clip2x = 0, m_insta_sum = 0;
	int32_t  m_insta_peak = 0;
	uint64_t m_dsp1_kept = 0;        // frames whose return was USABLE (trap-free)

	// ---- ★★★★ §228: THE DSP FRAME CLOCK IS DECOUPLED FROM THIS STREAM --------
	//
	// IC303 drives IC311's LRCK, so ONE PC sweep per LRCK period is the hardware
	// relationship.  It does NOT follow that one sweep per *emulated output
	// sample* is right, and it was not: this stream is allocated at 48 000 while
	// the instrument's Fs is 44 100 (four independent ROM-internal proofs -- see
	// upd6383.h m_frame_hz).  So every emulated delay, reverb and LFO ran
	// 48000/44100 = +8.84 % fast.
	//
	// The fix keeps the RENDERING rate where it is (moving the stream would drag
	// the EG law, the LP coefficient and the pitch step with it, i.e. shipping
	// audio) and gates run_frame() with a phase accumulator instead:
	// 44 100/48 000 = 147/160 exactly, so 44 100 frames are issued per emulated
	// second, exactly, with no drift.
	//
	// ⚠ TWO DECLARED APPROXIMATIONS, both confined to the WET path, which is
	// behind DSPCFG and today measures exactly zero (§54 peak 0, both buckets):
	//   * the send is DECIMATED without a filter (the chip's serial receiver
	//     simply never sees the 13 of 160 samples that fall between LRCK edges);
	//   * the return is held zero-order until the next frame (imaging).
	// Neither touches the dry mix, which is finished before this block runs.
	uint32_t m_dsp1_phase = 0;       // 0 .. STREAM_RATE-1, the 147/160 accumulator
	uint32_t m_dsp1_hz = 0;          // LRCK rate handed to IC311 (resolved at start)
	int32_t  m_dsp1_wet[2] = { 0, 0 };  // last frame's return, held between frames

	// The 16 page directories (4 banks x 4 pages), parsed from the wave ROM region at
	// device_start. PCM geometry is filled in eagerly (cheap); the fundamental period
	// and sustain loop of a chunk are measured on first use (analyse_chunk), because
	// measuring all 1495 chunks of every bank up front would cost seconds of start-up.
	page_dir_t m_dir[NUM_BANKS][PAGES_PER_BANK];

	// Derive a sustain loop for one chunk: a region in the recording's body whose length
	// is an integer number of fundamental periods, refined to the lowest seam
	// discontinuity. The ROM stores no loop points (see notes), so we derive one.
	void compute_loop(page_dir_t &d, int chunk);
};

DECLARE_DEVICE_TYPE(KN5000_TONEGEN, kn5000_tonegen_device)

#endif // MAME_MATSUSHITA_KN5000_TONEGEN_H
