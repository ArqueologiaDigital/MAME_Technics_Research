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

#include <deque>
#include <queue>
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

	static constexpr int NUM_VOICES = 64;
	static constexpr int NUM_GLOBAL_REGS = 16;

protected:
	virtual void device_start() override ATTR_COLD;
	virtual void device_reset() override ATTR_COLD;

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
		uint32_t pitch_step;    // Pitch increment (16.16 fixed point)
		int16_t  volume_l;      // Left channel volume (0-32767)
		int16_t  volume_r;      // Right channel volume (0-32767)
		uint32_t release_counter; // Samples remaining in release phase (0 = no release)
		uint32_t hold_counter;  // Samples remaining in hold phase after key-off
		int16_t  sustain_vol;   // volume last seen while the key was DOWN — a released
		                        // voice may never exceed it (a release only decays).
		int      env_level;     // Per-tick amplitude envelope magnitude (0-0xFF) the
		                        // sub-CPU firmware writes to group0/bank0 (reg_idx 0)
		                        // every audio tick — the real software envelope. 0xFF =
		                        // full (default until the firmware modulates it).
		int      true_note;     // MIDI note recovered from the keybed/MIDI input FIFO at
		                        // key-on (−1 = unknown → r8-relative fallback). Used to
		                        // resolve equal-tempered pitch (see update_pitch()).
		double   chord_time;    // press time of the chord this voice belongs to, used to
		                        // group simultaneous voices for polyphonic note pairing
		                        // (−1e9 = none). See assign_chord_notes().

		void reset()
		{
			std::fill(std::begin(regs), std::end(regs), 0);
			active = false;
			key_on = false;
			key_on_time = 0.0;
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
			pitch_step = 0x10000; // 1.0 = native pitch
			volume_l = 0;
			volume_r = 0;
			release_counter = 0;
			hold_counter = 0;
			sustain_vol = 0;
			env_level = 0xFF;
			true_note = -1;
			chord_time = -1e9;
		}
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
	void update_pitch(int ch);
	void process_key_on(int ch);
	void process_key_off(int ch);
	int16_t read_waveform_sample(uint32_t byte_offset) const;
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
