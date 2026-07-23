// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics KN5000 Tone Generator (IC303 - TC183C230002)

    64-voice PCM wavetable synthesizer. The real chip is a custom Matsushita
    LSI that reads waveform data from 4x 32Mbit ROMs (IC304-IC307, 16MB total).

    Register-indirect interface: SubCPU writes a 16-bit register address to
    0x100000, then reads/writes data at 0x100002. P6.7 GPIO acts as chip-select
    strobe (active low during address phase).

    Waveform ROM format (per IC307 analysis):
      - 198-entry index table at offset 0 (4 bytes each)
      - Parameter records (key zone definitions)
      - Signed 16-bit LE PCM data starting at ~0x1A30

    Each ROM chip is 4MB. The combined 16MB region is loaded as "waveform":
      IC304 at offset 0x000000
      IC305 at offset 0x400000
      IC306 at offset 0x800000
      IC307 at offset 0xC00000

***************************************************************************/

#include "emu.h"
#include "kn5000_tonegen.h"

#include <algorithm>
#include <cmath>
#include <vector>

// Logging
#define LOG_REG_W    (1U << 1)
#define LOG_KEY      (1U << 2)
#define LOG_VOICE    (1U << 3)
#define LOG_GLOBAL   (1U << 4)

#define VERBOSE (0)
#include "logmacro.h"

DEFINE_DEVICE_TYPE(KN5000_TONEGEN, kn5000_tonegen_device, "kn5000_tonegen", "KN5000 Tone Generator")


kn5000_tonegen_device::kn5000_tonegen_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: device_t(mconfig, KN5000_TONEGEN, tag, owner, clock)
	, device_sound_interface(mconfig, *this)
	, m_addr_latch(0)
	, m_stream(nullptr)
	, m_waveform_region_tag("waveform")
	, m_waveform_data(nullptr)
	, m_waveform_size(0)
{
}


void kn5000_tonegen_device::device_start()
{
	// Create stereo output stream at 48kHz (matching DAC sample rate)
	m_stream = stream_alloc(0, 2, 48000);

	// Resolve waveform ROM region
	memory_region *wave_region = machine().root_device().memregion(m_waveform_region_tag);
	if (wave_region)
	{
		m_waveform_data = wave_region->base();
		m_waveform_size = wave_region->bytes();
	}
	else
	{
		m_waveform_data = nullptr;
		m_waveform_size = 0;
	}

	// Parse IC307's 198-entry index table (region offset 0xC00000 = the real dump) and
	// precompute, for every waveform, its PCM start, sample count, and — the crux for
	// faithful pitched playback — its fundamental period (autocorrelation). The other
	// three banks (IC304-306) are BAD_DUMP copies of IC307, so every address computed
	// here reads real KN5000 PCM.
	std::fill(std::begin(m_wave_pcm_start), std::end(m_wave_pcm_start), 0);
	std::fill(std::begin(m_wave_pcm_samples), std::end(m_wave_pcm_samples), 0);
	std::fill(std::begin(m_wave_period), std::end(m_wave_period), 0);
	std::fill(std::begin(m_wave_loop_start), std::end(m_wave_loop_start), 0);
	std::fill(std::begin(m_wave_loop_len), std::end(m_wave_loop_len), 0);
	if (m_waveform_data && m_waveform_size >= 0x1000000)
	{
		static constexpr uint32_t IC307_BASE = 0xC00000;
		const uint8_t *idx = m_waveform_data + IC307_BASE;
		for (int i = 0; i < NUM_INDEX_ENTRIES; i++)
		{
			m_wave_index[i].param_ptr   = idx[i * 4 + 0] | (idx[i * 4 + 1] << 8);
			m_wave_index[i].wave_offset = idx[i * 4 + 2] | (idx[i * 4 + 3] << 8);
		}

		// PCM byte address = wave_offset * 16 (signed-16-LE). Length = span to the next
		// strictly-greater wave_offset (offsets are monotonic non-decreasing; equal
		// entries are multisample duplicates). See notes/kn5000-ic307-content-map.md.
		for (int i = 0; i < NUM_INDEX_ENTRIES; i++)
		{
			uint32_t off = uint32_t(m_wave_index[i].wave_offset) * 16;
			uint32_t next = off;
			for (int j = i + 1; j < NUM_INDEX_ENTRIES; j++)
			{
				uint32_t o = uint32_t(m_wave_index[j].wave_offset) * 16;
				if (o > off) { next = o; break; }
			}
			uint32_t bytes = (next > off) ? (next - off) : 512;
			m_wave_pcm_start[i]   = IC307_BASE + off;
			m_wave_pcm_samples[i] = bytes / 2;
		}

		for (int i = 0; i < NUM_INDEX_ENTRIES; i++)
		{
			m_wave_period[i] = detect_period(m_wave_pcm_start[i], m_wave_pcm_samples[i]);
			compute_loop(i);
		}
	}

	// Save state
	save_item(NAME(m_addr_latch));
	save_item(NAME(m_global_regs));
	for (int i = 0; i < NUM_VOICES; i++)
	{
		save_item(NAME(m_voice[i].regs), i);
		save_item(NAME(m_voice[i].wave_index), i);
		save_item(NAME(m_voice[i].active), i);
		save_item(NAME(m_voice[i].key_on), i);
		save_item(NAME(m_voice[i].key_on_time), i);
		save_item(NAME(m_voice[i].wave_offset), i);
		save_item(NAME(m_voice[i].wave_start), i);
		save_item(NAME(m_voice[i].wave_samples), i);
		save_item(NAME(m_voice[i].loop_start), i);
		save_item(NAME(m_voice[i].loop_end), i);
		save_item(NAME(m_voice[i].pitch_period), i);
		save_item(NAME(m_voice[i].pitch_step), i);
		save_item(NAME(m_voice[i].volume_l), i);
		save_item(NAME(m_voice[i].volume_r), i);
		save_item(NAME(m_voice[i].release_counter), i);
		save_item(NAME(m_voice[i].hold_counter), i);
	}
}


void kn5000_tonegen_device::device_reset()
{
	m_addr_latch = 0;
	std::fill(std::begin(m_global_regs), std::end(m_global_regs), 0);

	for (int i = 0; i < NUM_VOICES; i++)
		m_voice[i].reset();

	// Clear keybed queue
	while (!m_keybed_queue.empty())
		m_keybed_queue.pop();
}


//-----------------------------------------------------------------------
// Register-indirect interface
//-----------------------------------------------------------------------

void kn5000_tonegen_device::addr_w(uint16_t data)
{
	m_addr_latch = data;
}


void kn5000_tonegen_device::data_w(uint16_t data)
{
	m_stream->update();

	uint16_t addr = m_addr_latch;

	// Global registers: 0x0200-0x020F, 0x0C00-0x0C0F, 0x0E00
	if ((addr & 0xFF00) == 0x0200 || (addr & 0xFF00) == 0x0C00 || (addr & 0xFF00) == 0x0E00)
	{
		int idx = -1;
		if ((addr & 0xFF00) == 0x0200)
			idx = addr & 0x0F;
		else if ((addr & 0xFF00) == 0x0C00)
			idx = 6 + (addr & 0x0F);
		else if (addr == 0x0E00)
			idx = 12;

		if (idx >= 0 && idx < NUM_GLOBAL_REGS)
		{
			m_global_regs[idx] = data;
			LOGMASKED(LOG_GLOBAL, "tonegen: global reg 0x%04X = 0x%04X\n", addr, data);
		}
		return;
	}

	// Per-voice registers
	int ch   = addr & REG_CHANNEL_MASK;
	int bank = (addr >> REG_BANK_SHIFT) & REG_BANK_MASK;
	int group = addr >> REG_GROUP_SHIFT;

	if (ch >= NUM_VOICES)
		return;

	// Map group+bank to register index (32 regs = 8 groups x 4 banks)
	// Groups: 0x00, 0x01, 0x04, 0x05, 0x06, 0x08, 0x09, 0x0A
	static const int group_map[] = { 0, 1, -1, -1, 2, 3, 4, -1, 5, 6, 7, -1, -1, -1, -1, -1 };
	int gi = (group < 16) ? group_map[group] : -1;
	if (gi < 0)
	{
		LOGMASKED(LOG_REG_W, "tonegen: voice %d unknown group 0x%02X bank %d = 0x%04X (addr=0x%04X)\n",
			ch, group, bank, data, addr);
		return;
	}

	int reg_idx = gi * 4 + bank;
	if (reg_idx >= voice_t::NUM_REGS)
		return;

	m_voice[ch].regs[reg_idx] = data;
	LOGMASKED(LOG_REG_W, "tonegen: voice %d reg[%d] (g%d.b%d) = 0x%04X\n", ch, reg_idx, group, bank, data);

	// Voice control register (group 0, bank 0) — carries BOTH the key gate command
	// AND the per-tick amplitude-envelope magnitude. The sub-CPU firmware's software
	// envelope (stepper LABEL_026E5B) rewrites this register every audio tick with
	// 0xF000|mag / 0xFE00|mag, low 9 bits = linear magnitude (0xFF = loudest). The
	// real note-on command is 0x8100; key-off is 0x7E00. Discriminate by command so
	// the per-tick envelope writes do NOT retrigger the voice (which was resetting
	// wave_offset every coarse tick). See notes/kn5000-tonegen-register-semantics.md.
	if (group == 0 && bank == 0)
	{
		if (data == 0x7E00)
		{
			// Idle / key off
			process_key_off(ch);
		}
		else if ((data & 0xFF00) == 0x8100)
		{
			// Real note-on command (0x81xx). Confirmed against the sub-CPU
			// disassembly: LDW (100002h:24), 8100h to group0/bank0 (v142 asm L30213).
			process_key_on(ch);
		}
		else if (data & 0x8000)
		{
			// Per-tick amplitude-envelope magnitude update (0xF000|mag, 0xFE00|mag).
			// Latch the magnitude; do NOT touch key state or waveform position.
			// Verified live: after note-on the firmware writes 0xF0FF (mag 0xFF) here
			// per tick — previously this retriggered the voice (reset wave_offset).
			m_voice[ch].env_level = std::min<int>(data & 0x1FF, 0xFF);
		}
	}

	// Key RELEASE detection.
	//
	// The sub-CPU never writes a 0x7E00 key-off to group0/bank0 when a held key
	// is released. Instead it re-programs the voice's hardware envelope generator
	// with a *release* ramp: a burst of six writes to groups 8/9/A (routine
	// LABEL_027FD6 in v142 asm L23045). Both note-on setup AND note-off release
	// program these same EG registers, so a register write alone is ambiguous.
	// The discriminator: note-ON rewrites the group0/bank0 gate (0x8100) as part
	// of its burst, so its EG-program writes land only a few microseconds after
	// process_key_on(); the note-OFF release burst carries no gate and arrives
	// only once the key is actually released (>=45ms, typically seconds, later).
	//
	// We trigger on the group9/bank0 EG write (0x0900+ch) — written in both bursts
	// but, at note-on, ~12us after the gate — gated on "voice currently keyed on"
	// and "more than 1ms since the note-on gate". That cleanly separates the
	// note-on setup (same-burst, <1ms) from a genuine release (long after the gate)
	// without matching data-table-dependent envelope values. Without this the
	// held voice would never be told to release and would sustain forever.
	if (group == 9 && bank == 0 && m_voice[ch].key_on)
	{
		double now = machine().time().as_double();
		if (now - m_voice[ch].key_on_time > 0.001)
			process_key_off(ch);
	}

	// Waveform pointer latch: group 0, bank 2 with bit 15 SET triggers load,
	// then bit 15 CLEAR finalizes. We resolve on the SET strobe.
	if (group == 0 && bank == 2 && (data & 0x8000))
		resolve_waveform(ch);

	// Pitch: semitone from group 0 bank 1, octave from group 4 bank 0
	if ((group == 0 && bank == 1) || (group == 4 && bank == 0))
		update_pitch(ch);

	// Volume/pan: velocity in group 0 bank 2; main volume (bank 0),
	// pan L (bank 1), pan R (bank 2), DSP send (bank 3) all in group 8
	if ((group == 0 && bank == 2) || group == 8)
		update_voice_params(ch);
}


uint16_t kn5000_tonegen_device::data_r()
{
	// Read-back: voice control state
	uint16_t addr = m_addr_latch;
	int ch = addr & REG_CHANNEL_MASK;
	int bank = (addr >> REG_BANK_SHIFT) & REG_BANK_MASK;
	int group = addr >> REG_GROUP_SHIFT;

	if (ch < NUM_VOICES && group == 0 && bank == 0)
	{
		// Return voice status: 0x8100 if key-on or still in hold phase, 0x7E00 if idle
		const voice_t &v = m_voice[ch];
		return (v.key_on || v.hold_counter > 0) ? 0x8100 : 0x7E00;
	}

	return 0;
}


uint16_t kn5000_tonegen_device::status_r()
{
	// Active-voice status poll (read from 0x100000).
	//
	// MEASURED (sub-CPU v142 asm DAC_Write_Sample L11479-11483): the firmware
	// writes a bank index (0..3) to 0x100000, then reads a 16-bit bitmap back
	// from 0x100000 giving the currently-sounding voices in that bank of 16.
	// The voice-manager (LABEL_02219F/LABEL_02222A L13273-13330) computes
	//   ((prev | cur) XOR M) AND M   with M = firmware-commanded-on bitmap,
	// i.e. "voices the firmware turned on that the chip reports SILENT", and
	// releases each such voice via LABEL_02B4A1 (the 0x7E00 key-off, PC 02B4DB).
	//
	// If this read is left unmapped it returns 0 => every held voice looks
	// silent => the firmware auto-releases held keys ~45ms after key-on. To
	// make a held key SUSTAIN (as on real hardware) we report each keyed-on
	// voice as active. Bank = low 2 bits of the value last latched at 0x100000;
	// bit i of the result = voice (bank*16 + i) is currently gated on.
	int bank = m_addr_latch & 0x03;
	uint16_t bitmap = 0;
	for (int i = 0; i < 16; i++)
	{
		int vch = bank * 16 + i;
		if (vch < NUM_VOICES && m_voice[vch].key_on)
			bitmap |= (1u << i);
	}
	return bitmap;
}


//-----------------------------------------------------------------------
// Keyboard input interface
//-----------------------------------------------------------------------

uint16_t kn5000_tonegen_device::kbd_status_r()
{
	return m_keybed_queue.empty() ? 0x0000 : 0x0001;
}


uint16_t kn5000_tonegen_device::kbd_data_r()
{
	if (m_keybed_queue.empty())
		return 0x0000;

	uint16_t data = m_keybed_queue.front();
	m_keybed_queue.pop();
	return data;
}


void kn5000_tonegen_device::push_keybed_event(uint16_t data)
{
	// Record note-ONs (high byte != 0xFF is the SubCPU's note-off marker) with a
	// timestamp so a voice's genuine musical note can be recovered at key-on. The
	// wire format (keybed_scan / kbd_midi_rx) is note-on = (vel<<8)|(raw|0x80),
	// note-off = 0xFF00|raw, raw = MIDI note − 36 (61-key bed spans MIDI 36..96).
	if ((data >> 8) != 0xFF)
	{
		int midi = (data & 0x7F) + 36;
		m_pending_notes.emplace_back(machine().time().as_double(), midi);
		// Bound the history so it can't grow without limit.
		while (m_pending_notes.size() > 64)
			m_pending_notes.pop_front();
	}
	m_keybed_queue.push(data);
}


// A voice's RELATIVE pitch order, built from the two registers that vary per note:
// reg[1]'s low nibble = the multisample zone (coarse, +1 per ~3-4 semitones) and
// reg[8] = the within-zone log pitch (+0x100 per semitone, MEASURED). Weighting the
// zone far above reg[8] makes the combined value MONOTONIC with musical pitch across
// zone boundaries (each zone step of 0x100000 dwarfs reg[8]'s ~0x400 span / ~0x3C8
// boundary reset). Voices of the SAME musical note (dual-layer) share it exactly.
// VERIFIED live on a C-major chord: C4=0x07034C1 < E4=0x08035EC < G4=0x08038EC.
uint32_t kn5000_tonegen_device::voice_pitch_index(int ch) const
{
	return uint32_t(m_voice[ch].regs[1] & 0x0F) * 0x100000u + m_voice[ch].regs[8];
}


// Assign the genuine musical note to each voice of a chord (or a single note) by
// PAIRING the set of simultaneously-keying voices with the set of input notes that
// caused them — because the IC303 registers carry only sample-zone-relative pitch,
// not the note (see update_pitch), and a chord shares one input timestamp so "the
// most recent note" cannot tell the voices apart.
//
// The voice `ch` has just keyed on. We (1) find its chord = the most recent burst of
// input note-ons within the correlation window; (2) gather every currently-keying
// voice belonging to that same burst; (3) sort the voices by voice_pitch_index() and
// the notes by MIDI value, and pair them in order (lowest voice ← lowest note). This
// assigns each DISTINCT pitch its own note, maps dual-layer voices (identical index)
// to the same note, and is independent of the order the voices key on. It is
// re-run as each voice of the chord arrives, so the final state is always correct.
void kn5000_tonegen_device::assign_chord_notes(int ch)
{
	voice_t &v = m_voice[ch];
	double now = machine().time().as_double();

	// Prune events older than the correlation window.
	while (!m_pending_notes.empty() && now - m_pending_notes.front().first > 0.30)
		m_pending_notes.pop_front();

	// Chord press time = the most recent input note-on within the window.
	double tchord = -1.0;
	for (const auto &ev : m_pending_notes)
		if (ev.first <= now + 0.02 && now - ev.first < 0.30 && ev.first > tchord)
			tchord = ev.first;

	if (tchord < 0.0)
	{
		// No correlated input (e.g. demo / rhythm voice) → register-relative fallback.
		v.true_note = -1;
		v.chord_time = -1e9;
		return;
	}
	v.chord_time = tchord;

	// Notes of this chord = input note-ons clustered around the press time (a keybed
	// chord shares one exact timestamp; a MIDI chord spans a few ms), sorted ascending.
	std::vector<int> notes;
	for (const auto &ev : m_pending_notes)
		if (std::abs(ev.first - tchord) < 0.015)
			notes.push_back(ev.second);
	if (notes.empty()) { v.true_note = -1; return; }
	std::sort(notes.begin(), notes.end());

	// Voices of this chord = all keyed-on voices tagged with the same press time.
	std::vector<std::pair<uint32_t,int>> voices; // (pitch_index, ch)
	for (int c = 0; c < NUM_VOICES; c++)
		if (m_voice[c].key_on && std::abs(m_voice[c].chord_time - tchord) < 0.020)
			voices.emplace_back(voice_pitch_index(c), c);

	// Distinct pitch indices, ascending (dual-layer voices collapse to one entry).
	std::vector<uint32_t> distinct;
	for (const auto &p : voices) distinct.push_back(p.first);
	std::sort(distinct.begin(), distinct.end());
	distinct.erase(std::unique(distinct.begin(), distinct.end()), distinct.end());

	// Pair each voice's pitch rank with the note of the same rank (clamp if the counts
	// differ — e.g. a dropped voice), then recompute pitch.
	for (const auto &p : voices)
	{
		size_t rank = std::lower_bound(distinct.begin(), distinct.end(), p.first) - distinct.begin();
		int note = notes[std::min(rank, notes.size() - 1)];
		m_voice[p.second].true_note = note;
		update_pitch(p.second);
	}
}


//-----------------------------------------------------------------------
// Voice parameter management
//-----------------------------------------------------------------------

void kn5000_tonegen_device::update_voice_params(int ch)
{
	voice_t &v = m_voice[ch];

	// --- Loudness / velocity ---------------------------------------------------
	//
	// The firmware's per-voice loudness is a LOG-DOMAIN level in the HIGH byte of
	// reg[20] (group8/bank0, +0x800). It is built in sub-CPU LABEL_026769 as
	// `loglevel<<8`, where `loglevel` comes from the log table 0x0118FE indexed by
	// (patch level + key-scale) and then VELOCITY-scaled (LABEL_022BB8). Crucially
	// it is an ATTENUATION: LOWER value = LOUDER (MEASURED live 2026-07-23 — reg[20]
	// high byte 0xE7@vel40 → 0xCC@vel127, monotonically falling as velocity rises).
	//
	// The old code (a) inverted reg[20] LINEARLY (0xFF−hi), giving a tiny 24..51
	// span, and (b) multiplied by `reg[2]&0x0FFF` used as a *direct* volume — but
	// reg[2] is ALSO a velocity attenuation (falls with velocity), so that term
	// fought the reg[20] term and squeezed the whole dynamic range to ~1.8x
	// (vel40→127). That is the "velocity too weak / compressed" bug.
	//
	// Correct model: reg[20]'s high byte is a log attenuation, so the linear gain
	// is an EXPONENTIAL of it. K = attenuation units per halving, REF = the value
	// at (near) unity. reg[2] is redundant here — the firmware already folded the
	// velocity into reg[20] — so it is not multiplied in a second time.
	//   gain = 2^((REF − loglevel) / K)
	// The exponential form is grounded (log→linear); K and REF are CALIBRATED (the
	// chip's exact dB/step is internal to the undumped IC303) to keep loud notes
	// strong while giving a musical ~16 dB velocity spread. See
	// notes/kn5000-pitch-velocity.md.
	static constexpr double K = 10.0;    // reg[20] attenuation units per amplitude halving
	static constexpr double REF = 181.0; // loglevel that maps to ~0.2 full-scale

	int loglevel = (v.regs[20] >> 8) & 0xFF;
	double gain;
	if (v.regs[20] == 0)
		gain = 1.0; // uninitialised level register → full (matches old reg[20]==0 case)
	else
	{
		gain = std::pow(2.0, (REF - double(loglevel)) / K);
		if (gain > 1.0) gain = 1.0;
		if (gain < 0.0) gain = 0.0;
	}

	// Pan: kept centred. reg[21]/reg[22] are the bus-0 R gain / 2nd-domain level
	// (also `level<<8`), NOT the low-byte pan the old code assumed (their low bytes
	// read ~0 here). A faithful L/R-gain split is deferred (see the register-
	// semantics note); centred pan preserves the current stereo behaviour.
	int amp = int(gain * 32767.0 + 0.5);
	amp = std::min(amp, 32767);
	v.volume_l = int16_t(amp);
	v.volume_r = int16_t(amp);
}


void kn5000_tonegen_device::update_pitch(int ch)
{
	voice_t &v = m_voice[ch];

	// --- Why this is not a simple register read ---
	//
	// The IC303 is a PCM MULTISAMPLE chip. Its per-voice pitch registers are
	// sample-zone RELATIVE, not absolute (MEASURED live, 2026-07-23):
	//   * reg[8] (group4/bank0, +0x400) steps EXACTLY 0x100 per semitone WITHIN a
	//     sample zone, but RESETS at each zone boundary;
	//   * reg[1] (group0/bank1, +0x040) is the zone / coarse selector (its low
	//     nibble = the multisample zone index; +1 every ~3-4 semitones).
	// The per-zone sample ROOT pitch (what turns the relative value into an
	// absolute frequency) lives in the chip's internal multisample table in the
	// WAVE ROM — which is NO_DUMP for IC304-306. So absolute pitch simply CANNOT
	// be derived from the registers; there is no absolute-note register (verified
	// by dumping all 32 per-voice registers across a chromatic run — only reg[1]
	// and reg[8] vary per semitone). See notes/kn5000-pitch-velocity.md.
	//
	// Each voice loops ONE fundamental period of a real IC307 waveform (see
	// resolve_waveform / detect_period). Because that one period is resampled to the
	// target frequency regardless of the recording's native rate, pitch is decoupled
	// from the waveform's (unknown, un-stored) root note — so absolute pitch comes
	// purely from the played note at equal temperament, and NO per-waveform root is
	// needed. We recover the TRUE musical note from the real input event (keybed /
	// USB-MIDI, both routed through push_keybed_event) that caused this voice — the
	// faithful "use the real mechanism" approach.

	double freq;
	if (v.true_note >= 0)
	{
		// Equal temperament, A4 (MIDI 69) = 440 Hz.
		freq = 440.0 * std::pow(2.0, (double(v.true_note) - 69.0) / 12.0);
	}
	else
	{
		// Fallback for voices with no correlated input (e.g. demo / rhythm): use
		// reg[8] as a global log-pitch (0x100 = 1 semitone). This is correct
		// WITHIN a sample zone and monotonic; it can jump at zone boundaries (the
		// missing sample-root problem above), but it is far better than the former
		// behaviour where every semitone collapsed to one pitch. Anchor chosen so
		// a mid-range value lands near middle C.
		uint16_t r8 = v.regs[8];
		if (r8 == 0)
		{
			v.pitch_step = 0x10000;
			return;
		}
		double semis = (double(int(r8)) - double(0x3524)) / 256.0; // 0x100/semitone
		freq = 261.63 * std::pow(2.0, semis / 12.0);               // ref ≈ C4
	}

	// The recording's fundamental period is pitch_period samples, so advancing the
	// playback pointer by `step` per output sample makes that period recur at exactly
	// `freq` Hz — i.e. the whole multi-cycle recording plays back at the played note's
	// pitch, decoupled from the recording's (un-stored) native root. Same period-driven
	// pitch as the previous single-cycle model, so chromatic pitch cannot regress.
	uint32_t wlen = v.pitch_period ? v.pitch_period : 256;
	double step = 65536.0 * freq * double(wlen) / 48000.0;
	if (step < 1.0) step = 1.0;
	if (step > double(0x7FFFFFFF)) step = double(0x7FFFFFFF);
	v.pitch_step = uint32_t(step + 0.5);

	LOGMASKED(LOG_VOICE, "tonegen: voice %d note=%d freq=%.2f step=0x%08X (r1=%04X r8=%04X)\n",
		ch, v.true_note, freq, v.pitch_step, v.regs[1], v.regs[8]);
}


//-----------------------------------------------------------------------
// Real-waveform selection + FULL multi-cycle playback with a derived sustain loop
//-----------------------------------------------------------------------
//
// FAITHFULNESS MODEL (see notes/kn5000-real-sample-select.md; grounded in the findings
// notes kn5000-wave-number.md / kn5000-tone-record.md / kn5000-ic307-content-map.md):
//
//   * The firmware's real per-voice WAVE NUMBER (register +0x440/+0x480) is 0 for every
//     ordinary PCM voice (MEASURED live) — it is a legacy selector these voices bypass by
//     design. Per-instrument identity instead flows through the delivered tonerec's
//     partial-parameter records, which the firmware programs into the pitch/zone and
//     timbre registers. Their high bytes form a STABLE per-instrument fingerprint
//     (regs[1]=+0x040, regs[3]=+0x0C0, regs[5]=+0x140, regs[12]=+0x500) — identical
//     across notes and across a voice's two oscillator layers, distinct between
//     instruments (MEASURED: Piano/Brass/Guitar/Strings/Organ all differ).
//
//   * IC307 is the one REAL wave-ROM dump; its 198 indexed waveforms are real KN5000 PCM.
//     (IC304-306 are BAD_DUMP copies of IC307, so any address computed here reads real
//     PCM — a voice mapping to a "wrong" waveform still plays a real-but-wrong-instrument
//     timbre, the accepted placeholder, never silence or a synthesized timbre.)
//
// SELECTION: the true per-instrument sample map lives in the custom LSI + the undumped
// IC304-306, so it CANNOT be reproduced exactly. We select a real IC307 waveform from the
// firmware's per-instrument fingerprint so that DIFFERENT instruments deterministically
// resolve to DIFFERENT real waveforms (distinct real timbres, never a synthesized one).
// This is a labelled placeholder mapping, not a decode of the real instrument->wave table.
//
// PLAYBACK (the fix for the previous harshness): each voice plays the FULL multi-cycle
// recording from sample 0 — its genuine attack and timbral evolution — then loops a
// precomputed SUSTAIN region (compute_loop) for as long as the note is held. The previous
// model looped ONE short fundamental period taken from the ATTACK transient, which sounded
// like a static buzz; playing the real recording body fixes that.
//
// PITCH (must not regress): pitch is driven ENTIRELY by the equal-tempered played note
// (recovered from the real keybed/MIDI event, update_pitch), via the recording's detected
// fundamental period pitch_period. Advancing the read pointer by that period-derived step
// makes the recording's fundamental recur at exactly the played frequency, so absolute
// pitch is DECOUPLED from the recording's (un-stored) native root — chromatic/octave/chord
// pitch is identical to the prior single-cycle model and cannot regress. The sustain loop
// length is an integer multiple of pitch_period, so looping does not perturb pitch.

// Pick a real IC307 waveform index (0..197, page 0) from the firmware's REGISTER inputs.
//
// The per-voice waveform selection reaches the chip in register +0x040 (= regs[1]), decoded
// from the disassembly + live capture (notes/kn5000-voice-pipeline.md):
//   * high nibble (bits 12-15) = per-instrument BANK/class (MEASURED: Piano 0x7, Brass 0x1,
//     Guitar 0x3, Strings 0x0);
//   * low byte  (bits  0-7)    = multisample KEY-ZONE index (MEASURED live: steps 01->07->
//     08->0A as Piano is played up C2->C4->E4->C5 — i.e. it changes the sampled waveform per
//     key range, which is what MULTISAMPLING is).
// The timbre triple +0x0C0/+0x140/+0x500 (regs[3]/[5]/[12]) is an instrument-constant
// disambiguator for banks that would otherwise overlap.
//
// FAITHFUL vs PROVISIONAL: using (bank, zone) from +0x040 is the REAL register-only encoding
// the chip receives (HLE chip-boundary discipline — we read the chip's own inputs, never
// sub-CPU RAM), and it makes multisampling behave correctly (the waveform now varies with the
// played key-zone, and per instrument). What remains PROVISIONAL is the mapping from
// (bank, zone) to a specific IC307 entry: the custom LSI's internal (bank,zone)->wave-address
// logic is undocumented and the real per-instrument samples are in the undumped IC304-306, so
// the group ASSIGNMENT below is a labelled placeholder over the real IC307 waveforms (a voice
// still always plays real KN5000 PCM). Range 1..189 excludes index 0 (sine) and the
// multisample-duplicate / 3 MB-tail entries 190-197.
int kn5000_tonegen_device::select_waveform_index(const voice_t &v) const
{
	int bank = (v.regs[1] >> 12) & 0x0F;   // +0x040 high nibble: per-instrument
	int zone =  v.regs[1]        & 0xFF;    // +0x040 low byte: multisample key-zone
	uint32_t timbre = ((v.regs[3]  >> 8) & 0xFF) * 7u
	                + ((v.regs[5]  >> 8) & 0xFF) * 3u
	                + ((v.regs[12] >> 8) & 0xFF);
	if ((uint32_t(v.regs[1]) | timbre) == 0)
		return 0; // degenerate / boot voice -> real IC307 sine

	// Per-instrument multisample-group base (bank+timbre), then the key-zone steps WITHIN the
	// group so playing up the keyboard walks adjacent IC307 waveforms (multisample behaviour).
	// The base is the provisional part; the zone-stepping is the faithful register-driven part.
	uint32_t base = 1u + ((uint32_t(bank) * 41u + timbre) % 160u);
	uint32_t idx  = base + (uint32_t(zone) % 24u);
	if (idx > 189u) idx = 189u;
	return int(idx);
}


// Detect the fundamental period (in samples) of a real IC307 waveform, so ONE clean cycle
// can be looped and resampled to any note. Method: biased normalized autocorrelation over a
// bounded window; find the first negative-going zero crossing (to skip the lag-0 shoulder
// that fools a naive "highest early peak" — which is why a pure sine was previously
// mis-detected), then take the argmax lag beyond it. Returns 0 when no clear repetition is
// found and the wave is too long to treat as a single cycle (caller then uses the real
// sine). Short waves with no internal repetition (e.g. IC307 index 0, one 256-sample sine)
// return their own length. MEASURED periodicity basis: notes/kn5000-ic307-content-map.md 2.2.
uint32_t kn5000_tonegen_device::detect_period(uint32_t region_byte_start, uint32_t samples) const
{
	if (!m_waveform_data || samples < 32)
		return samples; // trivially one "cycle" (or nothing)

	const uint32_t W = std::min<uint32_t>(samples, 4096);
	const uint32_t minlag = 16;
	const uint32_t maxlag = std::min<uint32_t>(W / 2, 2048);
	if (maxlag <= minlag)
		return samples; // very short -> the whole wave is a single cycle

	// Load the window as doubles (bounds-checked; region is real PCM at every bank).
	std::vector<double> x(W, 0.0);
	for (uint32_t i = 0; i < W; i++)
	{
		uint32_t bp = region_byte_start + i * 2;
		if (bp + 1 >= m_waveform_size) { x.resize(i); break; }
		x[i] = double(int16_t(m_waveform_data[bp] | (m_waveform_data[bp + 1] << 8)));
	}
	const uint32_t n = uint32_t(x.size());
	if (n <= minlag + 4)
		return samples;

	double c0 = 0.0;
	for (uint32_t i = 0; i < n; i++) c0 += x[i] * x[i];
	if (c0 < 1.0)
		return samples; // silent window -> nothing to loop

	bool crossed = false;
	double best_r = -2.0;
	uint32_t best_lag = 0;
	const uint32_t hi = std::min<uint32_t>(maxlag, n - 1);
	for (uint32_t lag = 1; lag <= hi; lag++)
	{
		double c = 0.0;
		for (uint32_t i = 0; i + lag < n; i++) c += x[i] * x[i + lag];
		double r = c / c0;
		if (!crossed && r < 0.0) crossed = true;
		if (crossed && lag >= minlag && r > best_r) { best_r = r; best_lag = lag; }
	}

	if (best_lag == 0 || best_r < 0.5)
	{
		// No clear periodic peak. A short wave is itself ~one cycle; a long one has no
		// usable single-cycle loop -> signal fallback (0) so the caller uses the sine.
		return (samples <= 2048) ? samples : 0;
	}
	return best_lag;
}


// Derive a SUSTAIN LOOP for waveform `i`: IC307 stores no loop points (MEASURED,
// notes/kn5000-ic307-content-map.md §3.4), yet the real chip loops the sustain of a held
// note autonomously. We pick a region in the recording's BODY (never the attack transient,
// which is what made single-period looping sound harsh) whose length is an integer number of
// fundamental periods — so the loop seam is pitch-continuous — and slide the start within one
// period to minimise the sample/slope discontinuity at the seam. Result: play the whole real
// recording once (real attack + evolution), then loop a clean body region for as long as held.
void kn5000_tonegen_device::compute_loop(int i)
{
	uint32_t start = m_wave_pcm_start[i];
	uint32_t N     = m_wave_pcm_samples[i];
	uint32_t P     = m_wave_period[i];

	if (P == 0 || N == 0)
	{
		m_wave_loop_start[i] = 0;
		m_wave_loop_len[i]   = (N > 0) ? N : 0;
		return;
	}

	// Short waves (<= ~2 periods, e.g. the single-cycle sine): loop the whole thing.
	if (N <= 2 * P)
	{
		m_wave_loop_start[i] = 0;
		m_wave_loop_len[i]   = std::max<uint32_t>(P, (P <= N) ? (N / P) * P : N);
		return;
	}

	auto smp = [&](uint32_t s) -> int32_t {
		uint32_t bp = start + s * 2;
		if (bp + 1 >= m_waveform_size) return 0;
		return int16_t(m_waveform_data[bp] | (m_waveform_data[bp + 1] << 8));
	};

	// Loop length = k periods, a few kcycles but bounded, and at most ~2/5 of the recording.
	uint32_t cap = std::min<uint32_t>(4096, N / 2);
	uint32_t k = std::max<uint32_t>(1, std::min<uint32_t>(cap / P, (N * 2 / 5) / P));
	uint32_t loop_len = k * P;

	// Place the loop to END about one period before the recording end (skip any tail
	// boundary artifact), inside the sustain region (>= N/3 in).
	uint32_t le0 = (N > P) ? (N - P) : N;
	uint32_t ls0 = (le0 > loop_len) ? (le0 - loop_len) : 0;
	if (ls0 < N / 3) { ls0 = N / 3; }
	if (ls0 + loop_len >= N) { ls0 = (N > loop_len) ? (N - loop_len - 1) : 0; }

	// Refine ls within +/- P/2 to minimise the seam discontinuity x[le-1]->x[ls].
	uint32_t best_ls = ls0;
	int64_t  best_score = INT64_MAX;
	uint32_t lo = (ls0 > P / 2) ? (ls0 - P / 2) : 0;
	uint32_t hi = ls0 + P / 2;
	for (uint32_t ls = lo; ls <= hi; ls++)
	{
		uint32_t le = ls + loop_len;
		if (le >= N) break;
		int64_t disc = std::abs(int64_t(smp(ls)) - int64_t(smp(le)));
		int64_t slope = std::abs((int64_t(smp(ls + 1)) - int64_t(smp(ls))) -
		                         (int64_t(smp(le)) - int64_t(smp(le - 1))));
		int64_t score = disc * 2 + slope;
		if (score < best_score) { best_score = score; best_ls = ls; }
	}

	m_wave_loop_start[i] = best_ls;
	m_wave_loop_len[i]   = loop_len;
}


void kn5000_tonegen_device::resolve_waveform(int ch)
{
	voice_t &v = m_voice[ch];

	// Select the real IC307 waveform for this voice from the instrument fingerprint, then
	// loop ONE detected fundamental period of its real PCM. Pitch is applied by resampling
	// that period to the played note (update_pitch), so no per-waveform root is needed.
	int idx = select_waveform_index(v);
	if (idx < 0 || idx >= NUM_INDEX_ENTRIES)
		idx = 0;

	uint32_t period = m_wave_period[idx];
	if (period == 0)
	{
		// No clean loop period for this waveform -> fall back to the real IC307 sine
		// (index 0). Keeps a REAL waveform at EXACTLY the right pitch rather than risk a
		// wrong pitch (the task's hard constraint). Honest approximation, labelled here.
		idx = 0;
		period = m_wave_period[0] ? m_wave_period[0] : 256;
	}

	v.wave_index    = idx;
	v.wave_start    = m_wave_pcm_start[idx];
	v.wave_samples  = m_wave_pcm_samples[idx];
	v.pitch_period  = period;
	v.loop_start    = m_wave_loop_start[idx];
	v.loop_end      = m_wave_loop_start[idx] + m_wave_loop_len[idx];
	if (v.loop_end == 0 || v.loop_end > v.wave_samples)
		v.loop_end = v.wave_samples;          // safety: never index past the recording
	if (v.loop_start >= v.loop_end)
		v.loop_start = (v.loop_end > period) ? (v.loop_end - period) : 0;
	v.wave_offset   = 0;                       // start at sample 0 = the real attack

	LOGMASKED(LOG_VOICE, "tonegen: voice %d wave idx=%d start=0x%06X samples=%d period=%d loop[%d:%d] (fp %02X/%02X/%02X/%02X)\n",
		ch, v.wave_index, v.wave_start, v.wave_samples, v.pitch_period, v.loop_start, v.loop_end,
		(v.regs[1] >> 8) & 0xFF, (v.regs[3] >> 8) & 0xFF, (v.regs[5] >> 8) & 0xFF, (v.regs[12] >> 8) & 0xFF);
}


void kn5000_tonegen_device::process_key_on(int ch)
{
	voice_t &v = m_voice[ch];

	LOGMASKED(LOG_KEY, "tonegen: KEY ON voice %d\n", ch);

	v.key_on = true;
	v.key_on_time = machine().time().as_double(); // gate timestamp for release detection
	v.active = true;
	v.wave_offset = 0;
	v.release_counter = 0;
	v.hold_counter = 0;
	v.env_level = 0xFF; // full until the firmware's per-tick envelope modulates it

	// Resolve the waveform at key-on: by the time the firmware writes the note-on
	// command (0x8100) it has already written the wave number (regs[9]/regs[10])
	// and all voice params, so this picks up the final wave number rather than a
	// possibly-stale value from the earlier group0/bank2 strobe.
	resolve_waveform(ch);

	// Recover the genuine musical note for this voice (and re-pair the whole chord it
	// belongs to) from the real input events that triggered it. Must run after
	// resolve_waveform (update_pitch needs pitch_period). See assign_chord_notes().
	assign_chord_notes(ch);

	// Update pitch (also covers the no-input fallback case where assign_chord_notes
	// leaves true_note = −1 without calling update_pitch itself).
	update_pitch(ch);

	// Update volume/pan from current registers
	update_voice_params(ch);
}


void kn5000_tonegen_device::process_key_off(int ch)
{
	voice_t &v = m_voice[ch];

	LOGMASKED(LOG_KEY, "tonegen: KEY OFF voice %d\n", ch);

	v.key_on = false;

	// Start release envelope: ~50ms fade-out at 48kHz = 2400 samples
	v.release_counter = 2400;

	// Hold voice active for firmware status readback.
	// The firmware polls voice status at each sequencer tick (~192 Hz from INTTR5).
	// A short hold ensures at least a few poll cycles see the voice as active.
	// 100ms = 4800 samples at 48kHz (covers ~19 poll cycles at 192 Hz).
	v.hold_counter = 4800;
}


int16_t kn5000_tonegen_device::read_waveform_sample(uint32_t byte_offset) const
{
	if (!m_waveform_data || byte_offset + 1 >= m_waveform_size)
		return 0;

	// Signed 16-bit little-endian PCM
	return int16_t(m_waveform_data[byte_offset] | (m_waveform_data[byte_offset + 1] << 8));
}


//-----------------------------------------------------------------------
// Sound stream update — mix all active voices into stereo output
//-----------------------------------------------------------------------

void kn5000_tonegen_device::sound_stream_update(sound_stream &stream)
{
	for (int s = 0; s < stream.samples(); s++)
	{
		int32_t mix_l = 0;
		int32_t mix_r = 0;

		for (int ch = 0; ch < NUM_VOICES; ch++)
		{
			voice_t &v = m_voice[ch];
			if (!v.active)
				continue;

			// Handle hold timer (keeps voice "active" for firmware status queries).
			// This must run even when the voice has no waveform data, otherwise voices
			// get stuck permanently active and the firmware's sequencer part bitmask
			// (DRAM[0x10420]) never clears — blocking the Feature Demo from advancing.
			if (!v.key_on && v.hold_counter > 0)
			{
				v.hold_counter--;
				if (v.hold_counter == 0 && v.release_counter == 0)
				{
					v.active = false;
					continue;
				}
			}

			// Check if this voice has actual PCM sample data available. All four wave
			// banks now hold real IC307 PCM (IC304-306 are BAD_DUMP copies), so any
			// resolved wave_start reads real data. We must NOT judge that by the FIRST
			// sample alone: real waveforms routinely start at a zero-crossing (e.g.
			// IC307 index 0 is a sine that begins at sample 0), which a first-sample-only
			// test would misread as "no data" -> silence. Scan a small window instead: a
			// genuinely-missing (zero-filled) waveform stays 0 throughout, while any real
			// waveform has a nonzero sample within a few.
			bool has_pcm_data = false;
			if (v.wave_samples > 0 && m_waveform_data && v.wave_start + 1 < m_waveform_size)
			{
				uint32_t probe = std::min<uint32_t>(v.wave_samples, 64);
				for (uint32_t k = 0; k < probe; k++)
				{
					uint32_t bp = v.wave_start + k * 2;
					if (bp + 1 >= m_waveform_size) break;
					if (m_waveform_data[bp] != 0 || m_waveform_data[bp + 1] != 0) { has_pcm_data = true; break; }
				}
			}

			if (!has_pcm_data)
			{
				// Voice without PCM data (missing ROM or wave_samples==0).
				// Track timing efficiently without per-sample rendering.
				// The chip still considers this voice "active" — it tracks the
				// waveform position internally for status reporting.
				if (v.wave_samples > 0)
				{
					v.wave_offset += v.pitch_step;
					uint32_t sample_pos = v.wave_offset >> 16;
					if (sample_pos >= v.wave_samples)
					{
						if (v.key_on)
							v.wave_offset = 0;         // loop while key held (sustain phase)
						else if (v.hold_counter == 0 && v.release_counter == 0)
							v.active = false;          // finished after key-off
					}
				}
				if (v.release_counter > 0)
					v.release_counter--;
				if (!v.key_on && v.hold_counter == 0 && v.release_counter == 0)
					v.active = false;
				continue;  // No audio output — skip sample rendering
			}

			// --- Voices with real PCM data below ---
			//
			// FULL multi-cycle playback: play the whole real IC307 recording once from
			// sample 0 (its genuine attack + timbral evolution), then, while the note is
			// held (or ringing out under release), loop the precomputed SUSTAIN region
			// [loop_start,loop_end). The loop length is an integer number of fundamental
			// periods (compute_loop), so the seam is pitch-continuous and there is no
			// buzzy single-cycle artefact. Positions are 16.16 fixed point.
			uint32_t loop_len = (v.loop_end > v.loop_start) ? (v.loop_end - v.loop_start) : 0;
			uint32_t sample_pos = v.wave_offset >> 16;
			uint32_t frac = v.wave_offset & 0xFFFF;

			if (sample_pos >= v.loop_end)
			{
				// Reached the end of the play-through / loop region -> wrap back into the
				// sustain loop, preserving fractional phase (no glitch). If there is no
				// usable loop, snap to the loop start (or 0). This runs whether or not the
				// key is still down; the release/hold counters below handle deactivation,
				// so a released note keeps sounding (faded) instead of cutting abruptly.
				if (loop_len)
				{
					uint32_t base = v.loop_start << 16;
					uint32_t span = loop_len << 16;
					v.wave_offset = base + ((v.wave_offset - base) % span);
				}
				else
				{
					v.wave_offset = v.loop_start << 16;
				}
				sample_pos = v.wave_offset >> 16;
				frac = v.wave_offset & 0xFFFF;
			}

			// Real IC307 PCM, linearly interpolated (16.16 fixed point). At the loop tail
			// the "next" sample wraps to loop_start so interpolation stays continuous.
			int32_t s0, s1;
			{
				if (sample_pos >= v.wave_samples)          // safety clamp
					sample_pos = v.wave_samples ? v.wave_samples - 1 : 0;
				uint32_t byte_pos = v.wave_start + sample_pos * 2;
				s0 = read_waveform_sample(byte_pos);
				uint32_t next_pos = sample_pos + 1;
				if (loop_len && next_pos >= v.loop_end)
					next_pos = v.loop_start;               // wrap interp to loop start
				if (next_pos >= v.wave_samples)
					next_pos = v.wave_samples ? v.wave_samples - 1 : 0;
				s1 = read_waveform_sample(v.wave_start + next_pos * 2);
			}

			int32_t sample = s0 + ((s1 - s0) * int32_t(frac >> 1)) / 32768;

			// Apply the firmware's per-tick amplitude envelope (reg_idx 0 magnitude,
			// written every audio tick by the sub-CPU's software envelope generator).
			// This is the real attack/decay/sustain/release contour; env_level=0xFF is
			// full. See notes/kn5000-tonegen-register-semantics.md.
			sample = sample * v.env_level / 0xFF;

			// Apply release envelope (voice-lifecycle fade + deactivation). Kept for
			// deactivation timing; the firmware envelope above supplies the real shape.
			if (v.release_counter > 0)
			{
				sample = sample * int32_t(v.release_counter) / 2400;
				v.release_counter--;
				if (v.release_counter == 0 && v.hold_counter == 0)
				{
					v.active = false;
				}
			}

			// Apply volume
			mix_l += (sample * v.volume_l) >> 15;
			mix_r += (sample * v.volume_r) >> 15;

			// Advance position
			v.wave_offset += v.pitch_step;
		}

		// Clip to 16-bit range and convert to float (-1.0 to 1.0)
		mix_l = std::clamp(mix_l, -32768, 32767);
		mix_r = std::clamp(mix_r, -32768, 32767);

		stream.put(0, s, sound_stream::sample_t(mix_l) / 32768.0f);
		stream.put(1, s, sound_stream::sample_t(mix_r) / 32768.0f);
	}
}
