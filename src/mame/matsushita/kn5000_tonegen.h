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
		uint32_t wave_offset;   // Current position in waveform data (16.16 fixed point)
		uint32_t wave_start;    // Start byte offset (into the waveform ROM region) of
		                        // the ONE fundamental period looped for this voice.
		uint32_t wave_length;   // Loop length in samples = the selected wave's detected
		                        // fundamental period (see detect_period / resolve_waveform).
		int      wave_index;    // Selected IC307 index (0..197) whose real PCM this voice
		                        // renders; 0 = the real single-cycle sine (degenerate /
		                        // period-unknown fallback). Chosen from the firmware's
		                        // per-instrument register fingerprint (select_waveform_index).
		uint32_t pitch_step;    // Pitch increment (16.16 fixed point)
		int16_t  volume_l;      // Left channel volume (0-32767)
		int16_t  volume_r;      // Right channel volume (0-32767)
		uint32_t release_counter; // Samples remaining in release phase (0 = no release)
		uint32_t hold_counter;  // Samples remaining in hold phase after key-off
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
			wave_length = 0;
			wave_index = 0;
			pitch_step = 0x10000; // 1.0 = native pitch
			volume_l = 0;
			volume_r = 0;
			release_counter = 0;
			hold_counter = 0;
			env_level = 0xFF;
			true_note = -1;
			chord_time = -1e9;
		}
	};

	// Waveform ROM index entry (matches IC307 format)
	struct wave_index_entry_t
	{
		uint16_t param_ptr;     // Pointer to parameter record
		uint16_t wave_offset;   // Waveform byte offset / 16
	};

	void update_voice_params(int ch);
	void update_pitch(int ch);
	void process_key_on(int ch);
	void process_key_off(int ch);
	int16_t read_waveform_sample(uint32_t byte_offset) const;
	void resolve_waveform(int ch);

	// Real-waveform selection + single-period wavetable extraction. Different
	// instruments (different register fingerprints) resolve to DIFFERENT real IC307
	// waveforms; one fundamental period of each is looped and resampled to the played
	// note, so timbre is real PCM and pitch is exact. See kn5000_tonegen.cpp.
	int  select_waveform_index(const voice_t &v) const;
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

	// Index table cache (198 entries from IC307-format header)
	static constexpr int NUM_INDEX_ENTRIES = 198;
	wave_index_entry_t m_wave_index[NUM_INDEX_ENTRIES];

	// Per-waveform PCM geometry + detected fundamental period, precomputed at
	// device_start from IC307's index table (the one real dump; region offset 0xC00000).
	uint32_t m_wave_pcm_start[NUM_INDEX_ENTRIES];   // region byte offset of the waveform's PCM
	uint32_t m_wave_pcm_samples[NUM_INDEX_ENTRIES]; // total PCM samples available for this waveform
	uint32_t m_wave_period[NUM_INDEX_ENTRIES];      // detected fundamental period in samples
	                                                // (0 = no clean period -> real-sine fallback)
};

DECLARE_DEVICE_TYPE(KN5000_TONEGEN, kn5000_tonegen_device)

#endif // MAME_MATSUSHITA_KN5000_TONEGEN_H
