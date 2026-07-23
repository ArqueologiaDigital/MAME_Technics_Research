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

	// Parse waveform index tables from each ROM chip (IC304-IC307)
	// Each chip has 198 entries at offset 0, 4 bytes each
	if (m_waveform_data && m_waveform_size >= 0x1000000)
	{
		// Use IC307 index table (offset 0xC00000) as default
		const uint8_t *idx = m_waveform_data + 0xC00000;
		for (int i = 0; i < NUM_INDEX_ENTRIES; i++)
		{
			m_wave_index[i].param_ptr   = idx[i * 4 + 0] | (idx[i * 4 + 1] << 8);
			m_wave_index[i].wave_offset = idx[i * 4 + 2] | (idx[i * 4 + 3] << 8);
		}
	}

	// Save state
	save_item(NAME(m_addr_latch));
	save_item(NAME(m_global_regs));
	for (int i = 0; i < NUM_VOICES; i++)
	{
		save_item(NAME(m_voice[i].regs), i);
		save_item(NAME(m_voice[i].active), i);
		save_item(NAME(m_voice[i].key_on), i);
		save_item(NAME(m_voice[i].key_on_time), i);
		save_item(NAME(m_voice[i].wave_offset), i);
		save_item(NAME(m_voice[i].wave_start), i);
		save_item(NAME(m_voice[i].wave_length), i);
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


// Recover the true MIDI note for a voice about to key on, by correlating with the
// most recent keybed/MIDI note-on. The firmware issues the voice's register burst
// only a few ms after the input event (MEASURED: ~2-4 ms), and a note may map to
// several voices (dual-layer) that all arrive within that window — so "the most
// recent note-on within a short window" assigns the same correct note to every
// layer of one press. Returns −1 if no recent input (e.g. demo/rhythm voices),
// in which case update_pitch() falls back to the register-relative pitch.
int kn5000_tonegen_device::recover_true_note(double now)
{
	// Prune events older than the correlation window.
	while (!m_pending_notes.empty() && now - m_pending_notes.front().first > 0.30)
		m_pending_notes.pop_front();

	int best = -1;
	double best_t = -1.0;
	for (const auto &ev : m_pending_notes)
	{
		if (ev.first <= now + 0.05 && now - ev.first < 0.30 && ev.first > best_t)
		{
			best_t = ev.first;
			best = ev.second;
		}
	}
	return best;
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
	// Because every voice currently renders the SAME fabricated waveform (IC307
	// index 0, a 256-sample single-cycle sine — the wave-number decode is a
	// separate unresolved bug), the correct output is simply the played note at
	// equal temperament. We recover the TRUE musical note from the real input
	// event (keybed / USB-MIDI, both routed through push_keybed_event) that caused
	// this voice — the faithful "use the real mechanism" approach.

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

	// The fabricated waveform (index 0) is a single cycle over wave_length samples,
	// so it sounds at 48000/wave_length Hz when pitch_step == 0x10000. Set the step
	// to hit the target musical frequency exactly.
	uint32_t wlen = v.wave_length ? v.wave_length : 256;
	double step = 65536.0 * freq * double(wlen) / 48000.0;
	if (step < 1.0) step = 1.0;
	if (step > double(0x7FFFFFFF)) step = double(0x7FFFFFFF);
	v.pitch_step = uint32_t(step + 0.5);

	LOGMASKED(LOG_VOICE, "tonegen: voice %d note=%d freq=%.2f step=0x%08X (r1=%04X r8=%04X)\n",
		ch, v.true_note, freq, v.pitch_step, v.regs[1], v.regs[8]);
}


void kn5000_tonegen_device::resolve_waveform(int ch)
{
	voice_t &v = m_voice[ch];

	// Waveform selection. PROVISIONAL / UNRESOLVED: the chip's wave-number ->
	// physical-address decode lives inside the TC183C230002 and is absent from
	// all dumped data. Static analysis suggested the resolved wave number lands
	// at group4/bank1 (+0x440 = regs[9]), but a live capture of a real Piano
	// note shows regs[9] == 0 (and reg[3]'s low byte is also 0), so neither is
	// confirmed as the wave-number source — every voice currently collapses to
	// index 0. Finding the true wave-number register needs multi-instrument
	// register diffing (select different sounds, diff the voice register file).
	// See notes/kn5000-waveform-rom-banking.md. Until then we resolve through
	// IC307's self-contained 198-entry index (the one real dump), so a voice at
	// least plays real IC307 PCM rather than nothing.
	uint16_t wave_num_reg = v.regs[9]; // group4/bank1 (+0x440): provisional osc-1 wave number
	int wave_idx = wave_num_reg & 0xFF; // valid wave numbers 0x00-0xBF
	if (wave_idx >= NUM_INDEX_ENTRIES)
		wave_idx = wave_idx % NUM_INDEX_ENTRIES;

	// Only IC307 is dumped (offset 0xC00000). Use it for all lookups.
	uint32_t chip_base = 0xC00000; // IC307

	// Read index entry from IC307's index table (always available since IC307 is dumped).
	// This gives us the waveform length for timing purposes even when the actual PCM
	// data is in the missing IC304-IC306 ROMs.  The real tone gen chip tracks voice
	// timing based on these parameters regardless of which ROM chip holds the data.
	static constexpr uint32_t IC307_BASE = 0xC00000;
	if (m_waveform_data && m_waveform_size > IC307_BASE + NUM_INDEX_ENTRIES * 4)
	{
		const uint8_t *idx = m_waveform_data + IC307_BASE;
		uint16_t wave_off_raw = idx[wave_idx * 4 + 2] | (idx[wave_idx * 4 + 3] << 8);
		uint32_t wave_byte_offset = uint32_t(wave_off_raw) * 16;

		v.wave_start = chip_base + wave_byte_offset;

		// Determine length from next index entry
		uint32_t next_off;
		if (wave_idx + 1 < NUM_INDEX_ENTRIES)
		{
			uint16_t next_raw = idx[(wave_idx + 1) * 4 + 2] | (idx[(wave_idx + 1) * 4 + 3] << 8);
			next_off = uint32_t(next_raw) * 16;
		}
		else
		{
			next_off = wave_byte_offset + 512;
		}

		if (next_off > wave_byte_offset)
			v.wave_length = (next_off - wave_byte_offset) / 2; // bytes to samples
		else
			v.wave_length = 256;

		LOGMASKED(LOG_VOICE, "tonegen: voice %d waveform idx=%d chip=0x%06X start=0x%06X len=%d (wavenum reg9=0x%04X)\n",
			ch, wave_idx, chip_base, v.wave_start, v.wave_length, wave_num_reg);
	}
	else
	{
		// No index table available at all — use a reasonable default duration.
		// Even without any ROM data, we must keep the voice active for a
		// realistic duration so the firmware's sequencer part tracking works.
		v.wave_start = 0;
		v.wave_length = 48000; // ~1 second at 48kHz as fallback
	}
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

	// Recover the genuine musical note from the real input event that triggered
	// this voice (see recover_true_note / update_pitch). Done at the note-on gate
	// because by now the register burst — and the keybed/MIDI event before it —
	// have all arrived.
	v.true_note = recover_true_note(machine().time().as_double());

	// Resolve the waveform at key-on: by the time the firmware writes the note-on
	// command (0x8100) it has already written the wave number (regs[9]/regs[10])
	// and all voice params, so this picks up the final wave number rather than a
	// possibly-stale value from the earlier group0/bank2 strobe.
	resolve_waveform(ch);

	// Update pitch from current registers
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
			// This must run even when wave_length == 0 (no waveform ROM data),
			// otherwise voices get stuck permanently active and the firmware's
			// sequencer part bitmask (DRAM[0x10420]) never clears — blocking
			// the Feature Demo from advancing past song initialization.
			if (!v.key_on && v.hold_counter > 0)
			{
				v.hold_counter--;
				if (v.hold_counter == 0 && v.release_counter == 0)
				{
					v.active = false;
					continue;
				}
			}

			// Check if this voice has actual PCM sample data available.
			// IC307 is dumped; IC304-IC306 are missing (NO GOOD DUMP KNOWN) and
			// their region reads back as all zeros, so "has real data" == "some
			// nonzero sample in this waveform". We must NOT judge that by the FIRST
			// sample alone: real waveforms routinely start at a zero-crossing (e.g.
			// IC307 index 0 is a sine that begins at sample 0), which the old
			// first-sample-only test misread as "no data" -> silence. Scan a small
			// window instead: a genuinely-missing (zero-filled) waveform stays 0
			// throughout, while any real waveform has a nonzero sample within a few.
			bool has_pcm_data = false;
			if (v.wave_length > 0 && m_waveform_data && v.wave_start + 1 < m_waveform_size)
			{
				uint32_t probe = std::min<uint32_t>(v.wave_length, 64);
				for (uint32_t k = 0; k < probe; k++)
				{
					uint32_t bp = v.wave_start + k * 2;
					if (bp + 1 >= m_waveform_size) break;
					if (m_waveform_data[bp] != 0 || m_waveform_data[bp + 1] != 0) { has_pcm_data = true; break; }
				}
			}

			if (!has_pcm_data)
			{
				// Voice without PCM data (missing ROM or wave_length==0).
				// Track timing efficiently without per-sample rendering.
				// The chip still considers this voice "active" — it tracks the
				// waveform position internally for status reporting.
				if (v.wave_length > 0)
				{
					// Advance position by one pitch step per sample tick
					v.wave_offset += v.pitch_step;
					uint32_t sample_pos = v.wave_offset >> 16;
					if (sample_pos >= v.wave_length)
					{
						if (v.key_on)
						{
							// Loop while key held (sustain phase)
							v.wave_offset = 0;
						}
						else
						{
							// Waveform finished after key-off
							if (v.hold_counter == 0 && v.release_counter == 0)
								v.active = false;
						}
					}
				}
				if (v.release_counter > 0)
					v.release_counter--;
				if (!v.key_on && v.hold_counter == 0 && v.release_counter == 0)
					v.active = false;
				continue;  // No audio output — skip sample rendering
			}

			// --- Voices with real PCM data below ---

			// Read current sample with linear interpolation (16.16 fixed point)
			uint32_t sample_pos = v.wave_offset >> 16;
			uint32_t frac = v.wave_offset & 0xFFFF;

			if (sample_pos >= v.wave_length)
			{
				if (v.key_on)
				{
					// Loop for sustain
					v.wave_offset = 0;
					sample_pos = 0;
					frac = 0;
				}
				else
				{
					// Waveform finished after key-off: deactivate
					if (v.hold_counter == 0 && v.release_counter == 0)
						v.active = false;
					continue;
				}
			}

			uint32_t byte_pos = v.wave_start + sample_pos * 2;
			int32_t s0 = read_waveform_sample(byte_pos);

			// Linear interpolation with next sample
			int32_t s1;
			if (sample_pos + 1 < v.wave_length)
				s1 = read_waveform_sample(byte_pos + 2);
			else
				s1 = read_waveform_sample(v.wave_start); // wrap to loop start

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
