// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics KN5000 Tone Generator (IC303 - TC183C230002)

    64-voice PCM wavetable synthesizer. The real chip is a custom Matsushita
    LSI that reads waveform data from 4x 32Mbit ROMs (IC304-IC307, 16MB total).

    Register-indirect interface: SubCPU writes a 16-bit register address to
    0x100000, then reads/writes data at 0x100002. P6.7 GPIO acts as chip-select
    strobe (active low during address phase).

    Waveform ROM format (MEASURED, notes/kn5000-structural-validation.md §1):
    each 4MB chip is FOUR independent 1MB PAGES, and every page carries its own
    self-delimiting directory:
      - index of {param_ptr, wave_offset} u16 pairs; the entry count is encoded in
        entry 0 as `entry0.param_ptr == 4 * count`  (IC307: 198 / 168 / 1072 / 57)
      - parameter records, each starting with a redundant copy of its own
        wave_offset (verified 1495/1495 on IC307)
      - signed 16-bit LE PCM at `page_base + wave_offset * 16`
    A u16 wave_offset times 16 addresses exactly 1MB, which is *why* the page is 1MB.

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
// LOG_BOUND: waveform-selection diagnostics for the DATA-DERIVED map. Reports, per
// note-on, the full decode of +0x040 — class -> {bank, page} and entry -> directory
// slot — plus the chunk's PCM geometry, and WARNS when
//   * the entry lands outside that page's own directory (`OUT-OF-RANGE`) — measured
//     impossible on IC307, so it can only mean an undumped bank; or
//   * the entry exceeds the highest value the firmware's own tone tables ever use for
//     that class (`UNDOCUMENTED`); or
//   * the selected bank has no directory of its own and IC307's was substituted.
// Enable by building with VERBOSE including (1U << 5), e.g. #define VERBOSE (LOG_BOUND).
#define LOG_BOUND    (1U << 5)

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

	// Parse every page directory the wave ROM region carries (4 banks x 4 pages). This
	// is what the {class, entry} decode indexes into; see decode_wave_select().
	parse_page_directories();

	// Save state
	save_item(NAME(m_addr_latch));
	save_item(NAME(m_global_regs));
	for (int i = 0; i < NUM_VOICES; i++)
	{
		save_item(NAME(m_voice[i].regs), i);
		save_item(NAME(m_voice[i].wave_bank), i);
		save_item(NAME(m_voice[i].wave_page), i);
		save_item(NAME(m_voice[i].wave_chunk), i);
		save_item(NAME(m_voice[i].active), i);
		save_item(NAME(m_voice[i].key_on), i);
		save_item(NAME(m_voice[i].key_on_time), i);
		save_item(NAME(m_voice[i].wave_offset), i);
		save_item(NAME(m_voice[i].wave_start), i);
		save_item(NAME(m_voice[i].wave_samples), i);
		save_item(NAME(m_voice[i].loop_start), i);
		save_item(NAME(m_voice[i].loop_end), i);
		save_item(NAME(m_voice[i].pitch_period), i);
		save_item(NAME(m_voice[i].pitch_period_q16), i);
		save_item(NAME(m_voice[i].pitch_step), i);
		save_item(NAME(m_voice[i].volume_l), i);
		save_item(NAME(m_voice[i].volume_r), i);
		save_item(NAME(m_voice[i].release_counter), i);
		save_item(NAME(m_voice[i].hold_counter), i);
		save_item(NAME(m_voice[i].sustain_vol), i);
		save_item(NAME(m_voice[i].env_level), i);
		save_item(NAME(m_voice[i].lp_a), i);
		save_item(NAME(m_voice[i].lp_z), i);
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

	// Voice control register (group 0, bank 0). Three commands reach it:
	//   0x8100          note ON  (7 sites, all `LDW (100002h:24),8100h`)
	//   0x7E00          voice OFF / free (asm L13066 all-voices loop, L26793, L31188)
	//   0xF0xx / 0xFExx the HAND-OFF word, `slot[+0x2d]`
	//
	// WHAT THE HAND-OFF WORD IS NOT (settled this pass, and it contradicts the comment that
	// used to stand here as well as three of the audit reports). It is NOT a per-tick
	// software envelope magnitude:
	//   * it is built by LABEL_025589 (asm L18856-18906, `mag = 0xFF - 4*(VP[0] & 0x3F)`,
	//     `SET 8` iff VP[0] != 0) or by LABEL_0255F3 (L18907-18942, a BARE 0xF000/0xFE00 with
	//     no magnitude field at all), and both only STORE it into `slot[+0x2d]`;
	//   * the five places that ship `slot[+0x2d]` to this register (asm L21485, L24100,
	//     L24137, L29209, L29242) each call `LABEL_022587` — free the channel — on the very
	//     next line;
	//   * MEASURED on the live bus this pass: it is written exactly ONCE per note, 42 us
	//     after the gate for a rhythm voice and 0.5 ms after it for a key-bed voice, from
	//     `ToneGen_WriteSingleReg` (PC 0x02D42F); a 3-second held note gets exactly one
	//     (0xF0FF at +0.5 ms) and nothing else until its release.
	// So it is the point where the firmware stops managing the note and leaves it to the
	// chip's own envelope, and its low bits are a per-partial parameter of that hand-off
	// whose meaning is NOT established.
	//
	// WHY THE ARITHMETIC BELOW IS KEPT ANYWAY. Reading those low bits as an amplitude is
	// wrong in principle, and it is what silences the accompaniment: rhythm voices get the
	// bare 0xF000, so `data & 0x1FF` is 0 and they render at -81 dB. But simply not
	// silencing them is worse, MEASURED: the whole rhythm section then becomes a saturated
	// drone (rms 0.75 FS, peak pinned at 32767, and still sounding after STOP), because a
	// handed-off voice has NO remaining path to end — the firmware has freed its channel and
	// will never send it a 0x7E00, so on real hardware the chip must end it by itself, and
	// how it does that is exactly what is still undecoded. Until that is decoded, the two
	// defects cancel and unmuting alone regresses the instrument. See
	// notes/audit/kn5000-audit-applied.md.
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
			// Hand-off. Do NOT touch key state or waveform position.
			m_voice[ch].env_level = std::min<int>(data & 0x1FF, 0xFF);
		}
	}

	// Key RELEASE detection.
	//
	// HEURISTIC — kept deliberately, and its limits are known. When a held key is
	// released the sub-CPU re-programs the voice's envelope generator with a *release*
	// ramp: a burst of six writes to groups 8/9/A (routine LABEL_027FD6 in v142 asm
	// L23045, and its twin LABEL_02D436 at L29936). It writes the 0x7E00 key-off only
	// LATER, and only once its voice manager (LABEL_02219F asm L13273 -> LABEL_02B4A1
	// L26770) sees the chip report the voice SILENT — which our status_r only does for a
	// one-shot that has played out. Both note-on setup AND note-off release program the
	// same EG registers, so a register write alone is ambiguous.
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

	// +0x080 (group 0, bank 2) is the voice's LEVEL word, and its bit 15 is the burst
	// LOAD STROBE — SET on the first write of ToneGen_WriteVoiceParams (v142 asm L29594
	// `SET 0fh,WA`) and RES on the very last (L29907). +0x040 is written earlier in the
	// same burst (L29573), so resolving here reads a fresh wave number; the authoritative
	// resolve is the one in process_key_on().
	if (group == 0 && bank == 2 && (data & 0x8000))
		resolve_waveform(ch);

	// Pitch: wave/zone select in group 0 bank 1 (+0x040), absolute log pitch in group 4
	// bank 0 (+0x400). The transpose/detune this voice carries is resolved once the whole
	// key press has been programmed (process_key_on -> assign_chord_notes).
	if ((group == 0 && bank == 1) || (group == 4 && bank == 0))
		update_pitch(ch);

	// TVF (filter / brightness): +0x100 = group 1, bank 0. Recomputed on EVERY write, not
	// sampled at key-on, so a controller move that re-emits the register mid-note is honoured
	// (the emitter LABEL_024366, v142 asm L17006, can fold a live PART[+0x1f] offset into the
	// low 7 bits and re-ship the word).
	if (group == 1 && bank == 0)
		update_timbre(ch);

	// Loudness: the level word +0x800 (group 8, bank 0). Group 0 bank 2 is included because
	// the burst's final +0x080 write is the end-of-burst strobe.
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
	//
	// KNOWN GAP: this answers "gated on", not "still sounding", so a voice the firmware
	// HANDED OFF (the 0xF0xx write in data_w, after which it frees the channel and can
	// never send a 0x7E00) is reported active forever and is never reclaimed. Closing that
	// needs a decode of how the chip ends a handed-off note, which is not established —
	// see the long comment in data_w() and notes/audit/kn5000-audit-applied.md.
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
		v.pitch_offset = 0.0;
		return;
	}
	v.chord_time = tchord;

	// Notes of this chord = input note-ons clustered around the press time (a keybed
	// chord shares one exact timestamp; a MIDI chord spans a few ms), sorted ascending.
	std::vector<int> notes;
	for (const auto &ev : m_pending_notes)
		if (std::abs(ev.first - tchord) < 0.015)
			notes.push_back(ev.second);
	if (notes.empty()) { v.true_note = -1; v.pitch_offset = 0.0; return; }
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
		m_voice[p.second].pitch_offset = 0.0;
	}

	// Every voice of the chord now knows its played note. Resolve, per played note, the
	// TRANSPOSE and DETUNE its partials carry in +0x400 (resolve_note_group), then recompute
	// pitch. Done per note because the comparison is only defined between partials of the
	// same key press — a chord's voices legitimately differ by the chord's own intervals.
	std::vector<int> done;
	for (const auto &p : voices)
	{
		const int note = m_voice[p.second].true_note;
		if (std::find(done.begin(), done.end(), note) != done.end())
			continue;
		done.push_back(note);
		resolve_note_group(tchord, note);
	}
	for (const auto &p : voices)
		update_pitch(p.second);
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
	static constexpr double K = 10.0;    // reg[20] level units per amplitude halving
	// REF = the level that maps to full scale. MEASURED live: the loudest strike puts
	// 0xE7 (231) in reg[20]'s high byte, the softest 0xCC (204).
	static constexpr double REF = 231.0;

	int loglevel = (v.regs[20] >> 8) & 0xFF;

	// POLARITY (corrected 2026-07-26): reg[20]'s high byte is a LOG-DOMAIN LEVEL —
	// HIGHER = LOUDER. The earlier code had it inverted (as an attenuation), because the
	// calibration capture was taken BEFORE the key-bed velocity fix: with the input
	// running backwards, "velocity 40" actually reached the firmware as a HARD strike and
	// "velocity 127" as a SOFT one, so the measured 0xE7-at-40 / 0xCC-at-127 was read as
	// "falls as velocity rises". The two inversions cancelled; fixing the input exposed
	// this one. Felipe (real-hardware comparison, 2026-07-26): "If I hit hard I hear a
	// soft sound. If I hit softly, I hear a louder sound."
	//
	// The same error inverted the RELEASE: the firmware ramps this level DOWN at key-up,
	// which under the old reading rendered as amplitude RISING — the long-standing
	// "sound gets louder when I release a key" defect. With the correct polarity the
	// release ramp decays on its own, and a CLEARED register (0x0000) is silence rather
	// than full volume, both of which fall out for free.
	double gain = std::pow(2.0, (double(loglevel) - REF) / K);
	if (gain > 1.0) gain = 1.0;
	if (gain < 0.0) gain = 0.0;

	// Pan: kept centred. The group-8/9/10 register PAIRS are NOT an L/R pair — every
	// updater writes the SAME computed value to both members (LABEL_02682F asm L20831-20838,
	// LABEL_026A93 L21080-21086, LABEL_026AAA L21209-21212, LABEL_02D620 L30130-30150), which
	// an L/R gain pair could not do. There is no evidence-based per-voice pan source yet.
	int amp = int(gain * 32767.0 + 0.5);
	amp = std::min(amp, 32767);

	v.volume_l = int16_t(amp);
	v.volume_r = int16_t(amp);

	// Latch the level this voice was PROGRAMMED with, so the release fade can start from it.
	//
	// MEASURED discriminator (no timing involved): the LOW byte of +0x800 is a rate/flag
	// byte, and its bit 7 separates the two writers. A note-on level comes from
	// LABEL_025636 (v142 asm L19078-19085) as `(level<<8) | TAB_011963[rec+0x28]`, and
	// TAB_011963[0..100] runs 0x00..0x7F — bit 7 CLEAR. Every periodic/release update goes
	// through LABEL_026769 -> LABEL_02682F (L20831-20838), which does `SET 7` — bit 7 SET.
	// Live capture agrees exactly: note-on 0xE57F / 0xD17F / 0xDA7F, pre-note mute 0xFF80,
	// key-up release 0x8B80, panic 0xA280.
	//
	// This is what removes the key-up CLICK. The release burst writes +0x800 with the ramp's
	// TARGET level (0x8B = gain 0.0017) BEFORE it writes the +0x900 that signals the release,
	// so applying it instantly collapsed the voice by 54 dB in a single sample and the 50 ms
	// fade below then operated on already-silent audio. We have not decoded the chip's ramp
	// RATE, so we do not walk towards the target; we fade from the held level instead.
	if (v.key_on && !(v.regs[20] & 0x0080))
		v.sustain_vol = int16_t(amp);
}


// ---------------------------------------------------------------------------------------
// +0x100 (regs[4]) — the per-voice TVF (filter / brightness)
// ---------------------------------------------------------------------------------------
//
// TRACED end to end in the sub-CPU (v142) and MEASURED live. The note-on chain
// LABEL_02B4E3 (asm L26803) -> LABEL_024102 (L16748) -> LABEL_024444 (L17106) computes
//
//     V = clamp( VP[0x4d] + (int8)PART[0x67]
//                + ((int8)VP[0x37] * (int8)KSCURVE[VP[0x36]>>5][velocity]) >> 5    ; vel curve
//                + ((int8)VP[0x3c] * (clamp(note,VP[0x3a],VP[0x3b]) - VP[0x39])) >> 5 ; key follow
//                + 0x18 , 0, 0x78 )                                      ; LABEL_022BF2 L14494
//     +0x100 = ((VP[0x4e] & 7) << 13) | 0x0400 | V                        ; LABEL_023D01 L16312
//
// BIT 10 IS THE GATE, and it is exact: `SET 0ah` occurs at six places in the whole ROM
// (asm L16346/16429/16476/16542/16790/16832) and ALL SIX store to desc+0x42, i.e. to this
// register — every builder that computes a cutoff sets it, and nothing else in the ROM does.
// The firmware's own "no TVF" constant is 0x017F (LABEL_022DA1, asm L14697) and the
// percussion path ships 0x0000: both have bit 10 CLEAR. So bit 10 = "this word carries a
// computed cutoff", and its absence means BYPASS. (Testing `V != 0x7F` instead would have
// closed the filter completely on every drum kit, whose V is 0.)
//
// PREDICT-THEN-CHECK, 12/12 exact: 9 values recomputed from the ROM bytes against earlier
// live captures, plus 3 taken fresh on the running machine this pass at the driver's
// KEYBED_VELOCITY = 100 — Piano 0x2466 (V=102), Bright Piano 0x2470 (V=112), Mellow Piano
// 0x2450 (V=80). Those three patches are byte-identical in every register the HLE read
// before this change, which is exactly why they rendered bit-identically.
//
// THE ONE CALIBRATED CONSTANT is how many cents of cutoff one unit of V is worth: that
// belongs to the undumped LSI and is not in the firmware. It is BOUNDED by the data, and
// the bounds are what picks the value, not taste:
//   * V = 0x78 must be effectively open. It is the clamp ceiling, 504 of the 1046 partial
//     blocks reach it at velocity 127, and they include Applause / Gun Shot / Helicopter —
//     broadband recordings that cannot be dull. => FC(0x78) ~ 20 kHz.
//   * No pitched stock patch may be silenced. The darkest patch-level value in the whole
//     table is V = 32 ("Vocal Ah", both partials, at C4/velocity 100). Keeping its first
//     formant (~800 Hz) needs <= 63 cents/unit; at the 100 cents/unit that would make the
//     key-follow depth 0x20 exactly 1:1 it would sit at 202 Hz, i.e. inaudible. So 100 is
//     REFUTED by the firmware's own patch data and the usable range is (0, 63].
// 50 cents/unit is taken: safely inside that bound, it puts the floor of the whole computed
// range (V = 0) at 625 Hz so the filter can never silence a voice, and it makes the measured
// ppp->fff swing of a median block (36 units) 1.5 octaves of brightness.
//
// The filter SLOPE is likewise not decoded (the main-CPU Sound Editor has LPF/HPF/BPF/BCF
// pages, so a type selector exists — bits[15:13] and bit 7 are the only plausible carriers
// and neither is established). One pole is the minimal, conservative choice.
void kn5000_tonegen_device::update_timbre(int ch)
{
	voice_t &v = m_voice[ch];

	static constexpr double CENTS_PER_UNIT = 50.0;   // CALIBRATED, bounded to (0,63] by the data
	static constexpr double FC_TOP         = 20000.0; // cutoff at V = 0x78, the clamp ceiling
	static constexpr double V_TOP          = 120.0;   // = 0x78

	if (!(v.regs[4] & 0x0400))
	{
		v.lp_a = 0.0;   // no computed cutoff in this word -> bypass
		return;
	}

	const double cut = double(v.regs[4] & 0x7F);
	const double fc  = FC_TOP * std::pow(2.0, (cut - V_TOP) * CENTS_PER_UNIT / 1200.0);
	v.lp_a = std::exp(-2.0 * M_PI * fc / 48000.0);
}


// ---------------------------------------------------------------------------------------
// +0x400 (regs[8]) is an ABSOLUTE log pitch — transpose and detune, taken from the bus
// ---------------------------------------------------------------------------------------
//
// TRACED (sub-CPU v142 asm: LABEL_023584 L15504 -> LABEL_023A05 L15996 -> LABEL_023A4A
// L16025) and MEASURED. The word the firmware ships to +0x400 is
//
//     +0x400 = (effective note << 8) + 0x80 + trim(chunk) + 2*fine + detune + tunings
//
// at 0x100 units per semitone (0xC00 per octave). `trim` is the multisample partial record's
// own tuning word (`record[+0x04..05]`, stride-6 records only) — how the recording sits
// against the key. Everything the PLAYED note cannot show rides in here: the partial COARSE
// transpose (blk[+0x04], which also moves the key zone, so it changes +0x040 too), the
// partial FINE transpose (blk[+0x05], x2) and the unison/slot detune. MEASURED census over
// the 1046 partial blocks: 879 have no coarse transpose, 109 are +-12/+-24, 58 are other
// intervals; 364 carry a non-zero FINE transpose.
//
// TWO THINGS ARE DERIVABLE FROM THE CHIP'S OWN INPUTS, AND ONE IS NOT.
//
// Derivable — the RELATIVE interval between two voices of the SAME key press. Referring each
// voice's register to its own recording's measured fundamental,
//
//     rho = regs[8]/0x100 - 12*log2(period)          [semitones]
//
// makes the value comparable ACROSS chunks: rho(i) - rho(j) is the interval between the two
// partials. PREDICT-THEN-CHECK on the live capture: `Piano 1 Octave` at C4 (partial 0 on
// chunk 0x019 with +0x400 = 0x392C, partial 1 on chunk 0x007 with 0x34C1) gives
// 4.418 + 7.556 = 11.974 semitones against the +12 its patch record declares — residual
// 0.026 semitone. `Honky-Tonk` (fine -6/+6 on one chunk) gives 0.141 against the 12 register
// units the ROM declares; plain `Piano`'s two layers give 0.003.
//
// NOT derivable — WHICH voice of the pair is the transposed one, i.e. where the pair sits in
// absolute terms. That needs the chunk's own ROOT PITCH, which lives in the wave ROM's
// per-chunk parameter records and is not yet decoded. Everything that could stand in for it
// was measured and rejected this pass (see notes/kn5000-variant-applied.md §3): the
// per-chunk trim can be learned from the register stream, but a transposed partial teaches
// it a value exactly one octave wrong and nothing downstream can tell the two apart; and the
// page-local law `trim + 0x80 - 3072*log2(period) = const (mod 0xC00)`, though it holds to 47
// units on the acoustic-piano page, only fixes the trim MODULO AN OCTAVE.
//
// So this device takes the interval from the register and the anchor from a note-on it can
// PROVE is untransposed: one where every partial of the key press lands at the same rho. Such
// a press pins its chunks' trims for good; a chunk pinned that way can later anchor a press
// that does have a spread. A chunk whose observations disagree by more than half a semitone
// is marked CONFLICTED and never anchors anything. When no anchor exists the device keeps the
// played note — exactly what it did before — so this can only add information.

// A voice's log pitch referred to its own recording's native pitch, in semitones. Comparable
// across chunks (see above). Returns false if the voice has no usable pitch/period.
double kn5000_tonegen_device::voice_rho(int ch) const
{
	const voice_t &v = m_voice[ch];
	return double(int(v.regs[8])) / 256.0 - 12.0 * std::log2(double(v.pitch_period_q16) / 65536.0);
}


// Resolve transpose + detune for every voice of ONE key press (all voices tagged with this
// chord's press time whose paired note is `note`). Partials of one key are what the
// comparison above is defined over — a CHORD's voices differ by the chord's own intervals,
// so they are handled one played note at a time.
void kn5000_tonegen_device::resolve_note_group(double tchord, int note)
{
	// Collect the voices of this key press whose +0x040 names a real IC307 recording with a
	// measurable fundamental — the only ones for which any of this is defined.
	int    ch[NUM_VOICES];
	double rho[NUM_VOICES];
	double off[NUM_VOICES];
	bool   fixed[NUM_VOICES];
	int    n = 0;
	for (int c = 0; c < NUM_VOICES && n < NUM_VOICES; c++)
	{
		const voice_t &v = m_voice[c];
		if (!v.key_on || v.true_note != note || std::abs(v.chord_time - tchord) >= 0.020)
			continue;
		if (!v.wave_real || v.regs[8] == 0 || v.pitch_period_q16 == 0)
			continue;
		ch[n] = c;
		rho[n] = voice_rho(c);
		off[n] = 0.0;
		fixed[n] = false;
		n++;
	}
	if (n == 0)
		return;

	double lo = rho[0], hi = rho[0];
	for (int i = 0; i < n; i++) { lo = std::min(lo, rho[i]); hi = std::max(hi, rho[i]); }

	// ---- 1. LEARN, from a key press that is provably free of a coarse transpose ----------
	//
	// All partials landing within half a semitone of each other means no partial is shifted
	// against the others, so each one's +0x400 reads the note that was played. MEASURED: 441
	// of the 585 multi-partial patches have no coarse transpose at all and 117 have a MIXED
	// set (which this test detects); the 27 that shift every partial equally are caught by
	// the CONFLICTED marking below, as is a part-level octave/transpose setting. Two DISTINCT
	// chunks are required: a lone partial, or a unison pair on one chunk, is no evidence.
	static constexpr double FLAT = 0.5;          // semitones
	if (hi - lo < FLAT)
	{
		bool distinct = false;
		for (int i = 1; i < n && !distinct; i++)
			if (m_voice[ch[i]].wave_chunk != m_voice[ch[0]].wave_chunk ||
				m_voice[ch[i]].wave_page  != m_voice[ch[0]].wave_page)
				distinct = true;
		if (distinct)
		{
			for (int i = 0; i < n; i++)
			{
				voice_t &v = m_voice[ch[i]];
				page_dir_t &d = m_dir[v.wave_bank][v.wave_page];
				if (uint32_t(v.wave_chunk) >= d.count)
					continue;
				const int32_t obs = int32_t(v.regs[8]) - 256 * v.true_note - 0x80;
				uint8_t &st = d.trim_state[v.wave_chunk];
				if (st == 0)
				{
					d.trim[v.wave_chunk] = obs;
					st = 1;
				}
				else if (st == 1 && std::abs(obs - d.trim[v.wave_chunk]) > 128)
				{
					// Two readings more than half a semitone apart. MEASURED impossible for
					// one chunk (367/368 carry a single value across every SET, patch and key
					// that reaches them), so one of them came from a shift this device cannot
					// see: never anchor on that chunk again.
					st = 2;
				}
			}
		}
	}

	// ---- 2. RESOLVE each voice from ITS OWN chunk's trim ---------------------------------
	//
	// Only a voice's own chunk may place it. Crossing chunks is NOT safe: rho differences are
	// the interval between two partials only while both recordings sit in the same octave
	// slot of the wave ROM, and that slot is exactly the undecoded per-chunk root. MEASURED
	// live: `Piano 1 Octave` (chunks 0x019/0x007) gives 11.974 against the +12 its record
	// declares, but `Piano 2 Octave` (chunks 0x019/0x004) gives 36.004 against a true 24 —
	// one octave of error, from two chunks whose slots differ. So the offset of every voice
	// comes from an EXACT learned trim, or from a voice on the SAME chunk (where the slot
	// cancels identically), or it stays 0 and the voice sounds at the played note.
	int nfixed = 0;
	for (int i = 0; i < n; i++)
	{
		const voice_t &v = m_voice[ch[i]];
		const page_dir_t &d = m_dir[v.wave_bank][v.wave_page];
		if (uint32_t(v.wave_chunk) >= d.count || d.trim_state[v.wave_chunk] != 1)
			continue;
		const double nf = (double(int(v.regs[8])) - 128.0 - double(d.trim[v.wave_chunk])) / 256.0;
		if (std::abs(nf - double(note)) > 25.0)   // two octaves of transpose is the extreme
			continue;
		off[i] = nf - double(note);
		fixed[i] = true;
		nfixed++;
	}

	// Voices on a chunk another voice of this press already placed: same chunk, so the
	// unknown per-chunk term cancels and the register difference IS the interval. This is
	// what makes a unison/detune layer beat instead of rendering twice identically.
	for (int i = 0; i < n; i++)
	{
		if (fixed[i])
			continue;
		for (int j = 0; j < n; j++)
		{
			if (!fixed[j])
				continue;
			const voice_t &a = m_voice[ch[i]], &b = m_voice[ch[j]];
			if (a.wave_bank != b.wave_bank || a.wave_page != b.wave_page || a.wave_chunk != b.wave_chunk)
				continue;
			off[i] = off[j] + (rho[i] - rho[j]);
			fixed[i] = true;
			nfixed++;
			break;
		}
	}

	// Nothing placed at all, but the press is flat: spread the layers around the played note
	// by their own register differences. Mean-centred, so the note itself cannot move.
	if (nfixed == 0 && (hi - lo) < FLAT)
	{
		double sum = 0.0;
		for (int i = 0; i < n; i++) sum += rho[i];
		const double mean = sum / double(n);
		for (int i = 0; i < n; i++) off[i] = rho[i] - mean;
	}

	for (int i = 0; i < n; i++)
		m_voice[ch[i]].pitch_offset = std::clamp(off[i], -30.0, 30.0);
}



void kn5000_tonegen_device::update_pitch(int ch)
{
	voice_t &v = m_voice[ch];

	// --- Where absolute pitch comes from ---
	//
	// The IC303 is a PCM MULTISAMPLE chip. +0x400 (reg[8]) is an ABSOLUTE log pitch at
	// 0x100 units/semitone, but offset by a constant belonging to the selected chunk (the
	// recording's own tuning trim) — which is why a chromatic run appears to "reset" at every
	// zone boundary, and why the register alone cannot give the note. The ABSOLUTE frame
	// therefore still comes from the real input event (keybed / USB-MIDI, both routed through
	// push_keybed_event) that caused this voice; what the register adds is `pitch_offset`, the
	// semitones this partial sounds ABOVE that note — its coarse/fine transpose and its unison
	// detune (resolve_note_group()). An unresolved voice has offset 0, i.e. exactly the
	// behaviour this device had before.
	//
	// Each voice plays a real IC307 recording whose measured fundamental period is resampled
	// to the target frequency, so pitch is decoupled from the recording's (un-stored) native
	// root. See notes/kn5000-pitch-velocity.md and notes/kn5000-variant-applied.md.

	// An APERIODIC recording (drum, applause, noise — detect_period returned 0) has no
	// fundamental, so "resample it so its fundamental lands on the played note" is not
	// defined for it. Play it exactly as recorded. MEASURED: this is 16/198 of page 0 and
	// 28/168 of page 1 — precisely the pages the ROM's own name table fills with
	// `Rock Bass Drm`, `HiHat Open`, `Applause`, `Telephone`. Pitched pages are unaffected
	// (page 3 = piano and page 2 = drawbar footage have 0 such chunks).
	if (v.pitch_period_q16 == 0)
	{
		v.pitch_step = 0x10000;   // 1.0 = the recording's own rate
		return;
	}

	double freq;
	double note_f = 0.0;

	if (v.true_note >= 0)
	{
		// Equal temperament, A4 (MIDI 69) = 440 Hz, plus the transpose/detune the +0x400
		// register carries for this partial.
		note_f = double(v.true_note) + v.pitch_offset;
		freq = 440.0 * std::pow(2.0, (note_f - 69.0) / 12.0);
	}
	else
	{
		// Fallback for voices with no correlated input (e.g. demo / rhythm) on a chunk whose
		// trim is not known: use reg[8] as a global log-pitch (0x100 = 1 semitone). This is
		// correct WITHIN a sample zone and monotonic; it can jump at zone boundaries, but it
		// is far better than the former behaviour where every semitone collapsed to one
		// pitch. Anchor chosen so a mid-range value lands near middle C.
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
	// Fractional period (16.16) — rounding it to whole samples detunes the note by up to
	// 1200/(2P) cents, which is tens of cents on the short recordings at the top of a
	// multisample. MEASURED: this is what takes the chromatic run from +-26 cents to a
	// few, and the octave ratio from 1.9705 to ~2.
	double step = freq * double(v.pitch_period_q16) / 48000.0;
	if (step < 1.0) step = 1.0;
	if (step > double(0x7FFFFFFF)) step = double(0x7FFFFFFF);
	v.pitch_step = uint32_t(step + 0.5);

	LOGMASKED(LOG_VOICE, "tonegen: voice %d note=%d off=%+.3f -> %.3f freq=%.2f step=0x%08X (r1=%04X r8=%04X)\n",
		ch, v.true_note, v.pitch_offset, note_f, freq, v.pitch_step, v.regs[1], v.regs[8]);
}


//-----------------------------------------------------------------------
// Real-waveform selection + FULL multi-cycle playback with a derived sustain loop
//-----------------------------------------------------------------------
//
// FAITHFULNESS MODEL (notes/kn5000-datamap-applied.md, resting on
// notes/kn5000-structural-validation.md and notes/kn5000-firmware-sample-tables.md):
//
//   * The per-voice wave selection reaches IC303 in EXACTLY ONE register, +0x040
//     (= regs[1]) — traced through ToneGen_WriteVoiceParams (sub-CPU v142 asm L29565)
//     and confirmed live for 16 SOUND-GROUPs x 7 notes. The delivered partial record
//     carries no address, so this one 16-bit value is the WHOLE of the wave selection
//     the chip ever receives. +0x440/+0x480 are per-note-on rotating voice/DMA SLOT
//     COUNTERS and carry no waveform identity — they are NEVER selected on.
//
//   * That value is DECODED, not guessed. A wave ROM is four 1 MB pages, each with its
//     own self-delimiting directory; +0x040 names {bank, page, directory slot}. The
//     firmware's own tone tables and the ROM's own directories were derived completely
//     independently of each other and AGREE — see decode_wave_select() below.
//
//   * The firmware's per-instrument PARTIAL RECORDS (Table Data ROM, reached via the
//     tone record's multisample-SET index) are what say which samples belong to which
//     instrument. This device never reads them: they are outside the chip boundary. It
//     only decodes the +0x040 words those records ultimately produce — which is exactly
//     what the real LSI sees.
//
// PLAYBACK: each voice plays the FULL multi-cycle recording from sample 0 — its genuine
// attack and timbral evolution — then loops a precomputed SUSTAIN region (compute_loop)
// for as long as the note is held.
//
// PITCH: driven ENTIRELY by the equal-tempered played note (recovered from the real
// keybed/MIDI event, update_pitch) via the recording's measured fundamental period.
// Advancing the read pointer by that period-derived step makes the recording's
// fundamental recur at exactly the played frequency, so absolute pitch is DECOUPLED from
// the recording's (un-stored) native root. The sustain loop length is an integer multiple
// of the period, so looping does not perturb pitch.


// Parse the self-delimiting directory at the head of every 1 MB page of every bank.
//
// ACCEPTANCE TEST (all six checks are MEASURED properties of the real IC307 dump,
// notes/kn5000-structural-validation.md §1) — a page is only accepted as a directory if
// it passes all of them, so a blank or non-directory page is rejected rather than
// producing garbage addresses:
//   1. entry0.param_ptr is a nonzero multiple of 4  -> count = entry0.param_ptr / 4
//   2. the directory itself fits in the page
//   3. param_ptr is monotonic non-decreasing
//   4. the directory does not overlap the first parameter record
//   5. every wave_offset x16 stays inside the page
//   6. the redundant back-reference holds for EVERY entry: the u16 at the head of a
//      parameter record equals that entry's own wave_offset (1495/1495 on IC307).
void kn5000_tonegen_device::parse_page_directories()
{
	// Bank field (+0x040 bits[15:14]) -> which socket, as a region byte offset.
	//
	//   bank 1 = IC307. PROVEN (structural-validation §3): IC307's four pages declare
	//     198 / 168 / 1072 / 57 slots, and the firmware's classes 4 / 5 / 7 require
	//     directories of exactly 198 / 168 / 57 — three exact hits out of three testable
	//     classes, with all 465 of their (class, entry) pairs in range at base 0.
	//   bank 0 = the socket serving classes 0-3. Those classes need directories of
	//     >=214 / 177 / 185 / 436 slots, which no IC307 page can supply, so they are on a
	//     DIFFERENT chip. WHICH of IC304/305/306 that is, is a wiring fact we do not have
	//     (§7 states the falsifiable test: whichever chip declares those four counts, in
	//     that order, is bank 0). It is given IC304's slot here; today all three sockets
	//     are loaded with a BAD_DUMP copy of IC307 anyway (see kn5000.cpp ROM_REGION), so
	//     the choice is byte-equivalent and is the ONE line to revisit when a real dump
	//     of IC304/305/306 appears.
	//   banks 2/3 are never selected: bit 3 of the class field is 0 in all 1444
	//     (class, entry) pairs the firmware's tone tables produce.
	static constexpr uint32_t BANK_BASE[NUM_BANKS] = { 0x000000, 0xC00000, 0x400000, 0x800000 };

	for (int b = 0; b < NUM_BANKS; b++)
	{
		for (int p = 0; p < PAGES_PER_BANK; p++)
		{
			page_dir_t &d = m_dir[b][p];
			d = page_dir_t();
			d.base = BANK_BASE[b] + uint32_t(p) * PAGE_SIZE;

			if (!m_waveform_data || uint64_t(d.base) + PAGE_SIZE > m_waveform_size)
				continue;
			const uint8_t *pg = m_waveform_data + d.base;

			auto u16at = [&](uint32_t o) -> uint32_t { return uint32_t(pg[o]) | (uint32_t(pg[o + 1]) << 8); };

			const uint32_t head = u16at(0);                                   // 1
			if (head == 0 || (head & 3) != 0)
				continue;
			const uint32_t n = head / 4;
			if (uint64_t(n) * 4 > PAGE_SIZE - 4)                              // 2
				continue;

			std::vector<uint32_t> param(n), wave(n);
			bool ok = true;
			for (uint32_t i = 0; i < n && ok; i++)
			{
				param[i] = u16at(i * 4);
				wave[i]  = u16at(i * 4 + 2);
				if (i && param[i] < param[i - 1])                             // 3
					ok = false;
				if (param[i] < n * 4)                                         // 4
					ok = false;
				if (uint64_t(wave[i]) * 16 >= PAGE_SIZE)                      // 5
					ok = false;
				if (ok && u16at(param[i]) != wave[i])                         // 6
					ok = false;
			}
			if (!ok)
				continue;

			// PCM extent of a chunk = from its own wave_offset to the SMALLEST wave_offset
			// in the directory that is strictly greater (else the end of the page). Taking
			// the minimum over the whole directory rather than "the next entry" is what
			// makes this correct where offsets step backwards — page 1 of IC307 has three
			// such entries, which re-use an earlier recording rather than break the format.
			std::vector<uint32_t> sorted(wave);
			std::sort(sorted.begin(), sorted.end());
			sorted.erase(std::unique(sorted.begin(), sorted.end()), sorted.end());

			d.count = n;
			d.pcm_start.resize(n);
			d.pcm_samples.resize(n);
			d.period.assign(n, 0);
			d.period_q16.assign(n, 0);
			d.loop_start.assign(n, 0);
			d.loop_len.assign(n, 0);
			d.analysed.assign(n, 0);
			d.trim.assign(n, 0);
			d.trim_state.assign(n, 0);
			for (uint32_t i = 0; i < n; i++)
			{
				auto it = std::upper_bound(sorted.begin(), sorted.end(), wave[i]);
				const uint32_t end_off = (it == sorted.end()) ? PAGE_SIZE : (*it * 16);
				const uint32_t off = wave[i] * 16;
				d.pcm_start[i]   = d.base + off;
				d.pcm_samples[i] = (end_off > off) ? ((end_off - off) / 2) : 0;
			}

			LOGMASKED(LOG_GLOBAL, "tonegen: wave bank %d page %d @0x%06X: %d directory slots\n",
				b, p, d.base, d.count);
		}
	}
}


// Measure the fundamental period and derive a sustain loop for one chunk, on first use.
// Doing this for all 1495 chunks of all four banks at device_start would cost seconds of
// start-up; a chunk is analysed once, the first time a voice selects it.
void kn5000_tonegen_device::analyse_chunk(page_dir_t &d, int chunk)
{
	if (chunk < 0 || uint32_t(chunk) >= d.count || d.analysed[chunk])
		return;
	d.analysed[chunk] = 1;
	d.period_q16[chunk] = detect_period(d.pcm_start[chunk], d.pcm_samples[chunk]);
	d.period[chunk]     = d.period_q16[chunk] >> 16;   // whole samples, for the loop geometry
	compute_loop(d, chunk);
}


// DECODE the sole wave-selection register, +0x040, into a physical chunk. This replaces
// the previous heuristic GROUP table + zone scaling entirely: there is no table of tuned
// constants left in the selection path, only the ROM's own directories.
//
//     class = bits[15:12]        entry = bits[11:0]
//     page  = class & 3          bank  = (class >> 2) & 3
//     chunk = entry              a PLAIN 0-BASED INDEX into that page's directory
//
// WHY THIS AND NOT SOMETHING ELSE — every step is a measurement, not a choice:
//
//   * The four counts IC307 declares for its pages (198 / 168 / 1072 / 57) were read from
//     the ROM with no reference to the firmware. The directory size each class REQUIRES
//     (max entry + 1, over all 487 multisample SET descriptors in the Table Data ROM) was
//     computed from the firmware with no reference to the ROM. class 4 -> 198, class 5 ->
//     168, class 7 -> 57: THREE EXACT MATCHES OUT OF THREE testable classes, with
//     page = class & 3. All 465 of those classes' pairs land in range with base 0 — no
//     per-class offset, no fudge constant.
//   * The assignment is forced, not chosen: classes 0 and 3 need >=214 and >=436 slots, so
//     only page 2 could hold either and they collide there — classes 0-3 cannot be on
//     IC307 at all, and for classes 4-7 the identity map is the UNIQUE injective
//     assignment with more than one exact match.
//   * Cross-checked three further ways, each against a structure derived independently:
//     the firmware's key zones for one shared recording tile the keyboard with 0 overlaps
//     (15 groups, 11 tiling exactly); IC307's own key-split bytes track the firmware's
//     zone bounds as MIDI key = 1.5 x (value - 40) exactly; and the measured fundamental
//     of the chunk this formula selects tracks the firmware's key zone with slope 1.00 /
//     R^2 0.998 on all five piano SETs, where every wrong page or shuffled index collapses
//     to slope ~0.
//   * It also explains the live capture: PIANO's two oscillators read +0x040 = 0x7007 and
//     0x7017, and page 3 is two byte-identical 16-chunk runs — the 0x10 offset IS the
//     group size.
//
// Class 7 = the acoustic piano bank = page 3. Class 4 = page 0 (organ/accordion + SFX),
// class 5 = page 1 (drums/flutes), class 6 = page 2 (drawbar footage).
kn5000_tonegen_device::wave_ref_t kn5000_tonegen_device::decode_wave_select(uint16_t w) const
{
	wave_ref_t r;
	const int cls = (w >> 12) & 0x0F;
	r.entry = int(w) & 0x0FFF;
	r.page  = cls & 3;
	r.bank  = (cls >> 2) & 3;
	r.chunk = r.entry;
	r.out_of_range = false;
	r.undocumented = false;
	r.substituted  = false;

	// Highest entry each class uses across all 487 firmware multisample SET descriptors
	// (MEASURED, notes/data/kn5000-multisample-sets.tsv). DIAGNOSTIC ONLY — it does not
	// take part in the decode; it just lets LOG_BOUND flag a value the firmware's own
	// tables never produce, which would mean an untraced selection path (drawbar/drum-kit)
	// or a decode error.
	static const uint16_t FW_MAX_ENTRY[8] = { 0x0D5, 0x0B0, 0x0B8, 0x1B3, 0x0C5, 0x0A7, 0x096, 0x038 };
	if (cls < 8 && r.entry > int(FW_MAX_ENTRY[cls]))
		r.undocumented = true;

	const page_dir_t *d = &m_dir[r.bank][r.page];
	if (!d->count && m_dir[IC307_BANK][r.page].count)
	{
		// This socket carries no directory of its own (undumped / blank). Fall back to the
		// same PAGE of IC307, the one hardware-rooted dump, so the voice still renders real
		// KN5000 PCM through the real paged datapath instead of going silent. LABELLED as a
		// substitution — it is dead code while kn5000.cpp fills every bank with IC307.
		d = &m_dir[IC307_BANK][r.page];
		r.substituted = true;
	}

	if (!d->count)
	{
		r.chunk = -1;                       // no wave ROM at all
		r.out_of_range = true;
		return r;
	}

	if (uint32_t(r.chunk) >= d->count)
	{
		// The entry is past the end of this page's directory. On IC307 (bank 1) this is
		// MEASURED impossible — 465/465 of the firmware's classes-4-7 pairs are in range —
		// so it can only occur for classes 0-3, whose real chip is undumped and whose
		// directory is therefore the wrong (substituted) size. Wrap rather than clamp, so a
		// multisample still steps through distinct real recordings as it walks its zones,
		// and flag it: every occurrence is a consequence of the missing dump, not of the
		// decode. Never silence.
		r.chunk = int(uint32_t(r.chunk) % d->count);
		r.out_of_range = true;
	}
	return r;
}


// Measure the fundamental period (in samples) of a real wave-ROM recording, so it can be
// resampled to the played note and given a pitch-continuous sustain loop.
//
// Method: UNBIASED normalized autocorrelation
//     r(lag) = sum x[i]x[i+lag] / sqrt( sum x[i]^2 * sum x[i+lag]^2 )
// over the overlap, taken from a window in the recording's BODY; then, only AFTER the
// correlation has first fallen below zero (any smooth waveform has r ~ 1 at small lags —
// without this guard a single-cycle recording reports a tiny bogus period: MEASURED, the
// 256-sample synthetic sine on page 0 read 4), the SMALLEST lag that is a local maximum
// reaching 0.92 x peak (which defeats octave-doubling, where the correlation at 2P is as
// high as at P), finally refined to SUB-SAMPLE resolution by fitting a parabola to r()
// around that lag.
//
// The sub-sample refinement is not a nicety: the playback rate is proportional to the
// measured period, so rounding it to a whole sample detunes the note by up to
// 1200/(2P) cents. The piano bank's periods run 237 down to 7 samples, i.e. up to ~85
// cents at the top — MEASURED live before this refinement: +16 cents on C4-D#4, +24 on
// E4-G4, -14 on G#4-B4, jumping exactly at the firmware's 4-semitone zone boundaries
// (the signature of per-chunk rounding), and an octave ratio of 1.9705 instead of 2.
//
// Two corrections over the previous estimator, both of them fixes to a measurement bias
// rather than tuning:
//   * it normalised every lag by the FULL-window energy while summing progressively fewer
//     terms, which biases r downward in proportion to lag and so systematically rejects
//     low notes. The unbiased form divides by the energy actually in the overlap.
//   * it correlated from sample 0, i.e. across the ATTACK transient, which is inharmonic
//     and defeats correlation. The body window is the same "sustain starts about a third
//     in" convention compute_loop() already uses.
//
// PREDICT-THEN-CHECK on the piano bank (page 3), whose 16 chunks are one chromatic
// multisample: the measured periods MUST fall monotonically with the key zone.
//     old estimator: 238 173 132 103 82 69 54 40 34 26 21 18 [29 51 16 29]  <- breaks
//     this one:  237.40 173.47 132.28 103.73 82.17 69.00 54.07 40.68
//                 34.60  26.22  21.51  18.07 14.40 10.16  8.12  7.21        <- 16/16 monotone
// and the span 237.40 : 7.21 = 60.50 semitones against the firmware's own 16 zones x 4
// semitones = 60. Chunks with no resolvable period fall from 11/57 to 0/57 on that page
// and 36 -> 30 of 168 on page 1; unchanged at 16/198 on page 0 and 0/1072 on page 2.
//
// Returns the period in 16.16 fixed point, or 0 when the recording has no fundamental at
// all (drum, applause, noise); the caller then plays it at its native rate, which is what
// an aperiodic one-shot wants.
uint32_t kn5000_tonegen_device::detect_period(uint32_t region_byte_start, uint32_t samples) const
{
	if (!m_waveform_data || samples < 32)
		return samples << 16; // trivially one "cycle" (or nothing)

	// Window from the recording's BODY, past the attack transient.
	uint32_t off = samples / 3;
	uint32_t W   = std::min<uint32_t>(samples - off, 4096);
	if (W < 64) { off = 0; W = std::min<uint32_t>(samples, 4096); }

	const uint32_t minlag = 4;
	const uint32_t maxlag = std::min<uint32_t>(W / 2, 2048);
	if (maxlag <= minlag)
		return samples << 16; // very short -> the whole wave is a single cycle

	// Load the window as doubles (bounds-checked; region is real PCM at every bank).
	std::vector<double> x(W, 0.0);
	for (uint32_t i = 0; i < W; i++)
	{
		uint32_t bp = region_byte_start + (off + i) * 2;
		if (bp + 1 >= m_waveform_size) { x.resize(i); break; }
		x[i] = double(int16_t(m_waveform_data[bp] | (m_waveform_data[bp + 1] << 8)));
	}
	const uint32_t n = uint32_t(x.size());
	if (n <= minlag * 2 + 4)
		return samples << 16;

	// Remove DC, so a sample with an offset does not correlate with itself at every lag.
	double mean = 0.0;
	for (uint32_t i = 0; i < n; i++) mean += x[i];
	mean /= double(n);
	double energy = 0.0;
	for (uint32_t i = 0; i < n; i++) { x[i] -= mean; energy += x[i] * x[i]; }
	if (energy < 1.0)
		return samples << 16; // silent window -> nothing to loop

	const uint32_t hi = std::min<uint32_t>(maxlag, n - 1);
	std::vector<double> r(hi + 1, -2.0);
	for (uint32_t lag = minlag; lag <= hi; lag++)
	{
		double c = 0.0, e0 = 0.0, e1 = 0.0;
		for (uint32_t i = 0; i + lag < n; i++)
		{
			c  += x[i] * x[i + lag];
			e0 += x[i] * x[i];
			e1 += x[i + lag] * x[i + lag];
		}
		const double den = std::sqrt(e0 * e1);
		r[lag] = (den > 1.0) ? (c / den) : -2.0;
	}

	// Skip the lag-0 shoulder: a period can only be claimed once the correlation has
	// fallen below zero at least once. If it never does, the window contains less than one
	// cycle — the recording IS a single cycle (page 2's 64-sample drawbar footage waves,
	// page 0's synthetic sine), so its own length is the period.
	uint32_t cross = 0;
	for (uint32_t lag = minlag; lag <= hi; lag++)
		if (r[lag] < 0.0) { cross = lag; break; }
	if (cross == 0)
		return (samples <= 2048) ? (samples << 16) : 0;

	double peak = -2.0;
	for (uint32_t lag = cross; lag <= hi; lag++)
		peak = std::max(peak, r[lag]);

	// Refine an integer lag to sub-sample resolution by fitting a parabola to the three
	// correlation values around it — the standard estimator for a sampled peak.
	auto refine = [&](uint32_t lag) -> uint32_t
	{
		double frac = 0.0;
		if (lag > minlag && lag + 1 <= hi)
		{
			const double y0 = r[lag - 1], y1 = r[lag], y2 = r[lag + 1];
			const double den = y0 - 2.0 * y1 + y2;
			if (den < -1e-12 || den > 1e-12)
				frac = 0.5 * (y0 - y2) / den;
			frac = std::clamp(frac, -0.5, 0.5);
		}
		const double p = std::max(1.0, double(lag) + frac);
		return uint32_t(p * 65536.0 + 0.5);
	};

	if (peak >= 0.5)
	{
		for (uint32_t lag = cross + 1; lag + 1 <= hi; lag++)
			if (r[lag] >= 0.92 * peak && r[lag] >= r[lag - 1] && r[lag] >= r[lag + 1])
				return refine(lag);
		for (uint32_t lag = cross; lag <= hi; lag++)
			if (r[lag] >= 0.92 * peak)
				return refine(lag);
	}

	// No fundamental. A short recording is itself ~one cycle; a long aperiodic one
	// (drum hit, applause) has none -> 0, and the caller plays it as recorded.
	return (samples <= 2048) ? (samples << 16) : 0;
}


// Derive a SUSTAIN LOOP for waveform `i`: IC307 stores no loop points (MEASURED,
// notes/kn5000-ic307-content-map.md §3.4), yet the real chip loops the sustain of a held
// note autonomously. We pick a region in the recording's BODY (never the attack transient,
// which is what made single-period looping sound harsh) whose length is an integer number of
// fundamental periods — so the loop seam is pitch-continuous — and slide the start within one
// period to minimise the sample/slope discontinuity at the seam. Result: play the whole real
// recording once (real attack + evolution), then loop a clean body region for as long as held.
void kn5000_tonegen_device::compute_loop(page_dir_t &d, int i)
{
	uint32_t start = d.pcm_start[i];
	uint32_t N     = d.pcm_samples[i];
	uint32_t P     = d.period[i];

	if (P == 0 || N == 0)
	{
		d.loop_start[i] = 0;
		d.loop_len[i]   = (N > 0) ? N : 0;
		return;
	}

	// Short waves (<= ~2 periods, e.g. the single-cycle sine): loop the whole thing.
	if (N <= 2 * P)
	{
		d.loop_start[i] = 0;
		d.loop_len[i]   = std::max<uint32_t>(P, (P <= N) ? (N / P) * P : N);
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

	d.loop_start[i] = best_ls;
	d.loop_len[i]   = loop_len;
}


void kn5000_tonegen_device::resolve_waveform(int ch)
{
	voice_t &v = m_voice[ch];

	// DECODE the sole wave-selection register into a physical wave-ROM chunk, then play
	// that chunk's real PCM. Register-only: nothing outside the chip's own interfaces is
	// consulted (the +0x040 word it is given, and the wave ROM it is wired to).
	const uint16_t w = v.regs[1];             // +0x040
	const wave_ref_t s = decode_wave_select(w);

	v.wave_bank  = s.bank;
	v.wave_page  = s.page;
	v.wave_chunk = s.chunk;
	// Only a chunk that resolves inside the ONE hardware-rooted dump is a real recording
	// whose {chunk <-> +0x400} pitch relation means anything: on an undumped socket the
	// entry was wrapped into a substituted directory, so the recording played has no
	// connection to the pitch the register asks for. See update_pitch().
	v.wave_real  = (s.bank == IC307_BANK) && !s.substituted && !s.out_of_range && (s.chunk >= 0);

	if (s.chunk < 0)
	{
		// No wave ROM at all (no dump loaded). Nothing to render.
		v.wave_start = v.wave_samples = v.loop_start = v.loop_end = 0;
		v.pitch_period = 0;
		v.pitch_period_q16 = 0;
		v.wave_offset = 0;
		return;
	}

	// A directory of the substituted bank may have been used; re-resolve the same way
	// decode_wave_select() did so we read the geometry it actually chose.
	page_dir_t &d = s.substituted ? m_dir[IC307_BANK][s.page] : m_dir[s.bank][s.page];
	analyse_chunk(d, s.chunk);

	v.wave_start    = d.pcm_start[s.chunk];
	v.wave_samples  = d.pcm_samples[s.chunk];
	// pitch_period == 0 means the recording is APERIODIC (a drum, applause, noise). It has
	// no fundamental, so resampling it to a musical note is meaningless; update_pitch()
	// plays it at its native rate. That keeps REAL PCM for percussion instead of
	// substituting an unrelated waveform, which is what the old sine fallback did.
	v.pitch_period     = d.period[s.chunk];
	v.pitch_period_q16 = d.period_q16[s.chunk];
	v.loop_start    = d.loop_start[s.chunk];
	v.loop_end      = d.loop_start[s.chunk] + d.loop_len[s.chunk];
	if (v.loop_end == 0 || v.loop_end > v.wave_samples)
		v.loop_end = v.wave_samples;          // safety: never index past the recording
	if (v.loop_start >= v.loop_end)
		v.loop_start = (v.loop_end > v.pitch_period) ? (v.loop_end - v.pitch_period) : 0;
	v.wave_offset   = 0;                       // start at sample 0 = the real attack

	// ---- SELECTION DIAGNOSTIC (LOG_BOUND) ----------------------------------------
	// Reports the data-derived decode and flags anything the derivation says must not
	// happen. On IC307 (bank 1) OUT-OF-RANGE is MEASURED impossible: 465/465 of the
	// firmware's class-4..7 pairs are inside their page's directory.
	if (VERBOSE & LOG_BOUND)
	{
		const int cls = (w >> 12) & 0x0F;
		if (s.out_of_range)
			logerror("tonegen: OUT-OF-RANGE +040=%04X cls=%d entry=0x%03X -> bank %d page %d has %d slots -> wrapped to chunk %d%s\n",
				w, cls, s.entry, s.bank, s.page, d.count, s.chunk,
				(s.bank != IC307_BANK) ? " (bank is UNDUMPED)" : " *** ON IC307: DECODE ERROR ***");
		else if (s.undocumented)
			logerror("tonegen: UNDOCUMENTED +040=%04X cls=%d entry=0x%03X exceeds the firmware tables' max for this class -> bank %d page %d chunk %d\n",
				w, cls, s.entry, s.bank, s.page, s.chunk);
		else
			logerror("tonegen: sel +040=%04X cls=%d entry=0x%03X -> bank %d page %d chunk %d/%d  pcm 0x%06X %d smp period %d%s\n",
				w, cls, s.entry, s.bank, s.page, s.chunk, d.count,
				v.wave_start, v.wave_samples, v.pitch_period,
				s.substituted ? " (IC307 substituted for an undumped socket)" : "");
	}

	LOGMASKED(LOG_VOICE, "tonegen: voice %d +040=%04X -> bank %d page %d chunk %d start=0x%06X samples=%d period=%d loop[%d:%d]\n",
		ch, w, v.wave_bank, v.wave_page, v.wave_chunk, v.wave_start, v.wave_samples,
		v.pitch_period, v.loop_start, v.loop_end);
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
	v.env_level = 0xFF; // see the hand-off discussion in data_w()
	v.lp_z = 0.0;       // the per-voice filter starts from rest
	v.pitch_offset = 0.0; // resolved from +0x400 once the whole key press is programmed

	// Resolve the waveform at key-on: by the time the firmware writes the note-on
	// command (0x8100) it has already written the wave-select register +0x040 (= regs[1],
	// v142 asm L29573, the FIRST write of the burst) and all the other voice params, so
	// this picks up the final selection rather than a possibly-stale earlier value.
	resolve_waveform(ch);

	// Recover the genuine musical note for this voice (and re-pair the whole chord it
	// belongs to) from the real input events that triggered it. Must run after
	// resolve_waveform (update_pitch needs pitch_period). See assign_chord_notes().
	assign_chord_notes(ch);

	// Update pitch (also covers the no-input fallback case where assign_chord_notes
	// leaves true_note = −1 without calling update_pitch itself).
	update_pitch(ch);

	// Update volume and the TVF from the current registers. +0x800 and +0x100 are both
	// written earlier in the same burst (asm L29736 and L29619), so they are already final.
	update_voice_params(ch);
	update_timbre(ch);
	v.sustain_vol = v.volume_l;   // floor for the release fade, refined by update_voice_params
}


void kn5000_tonegen_device::process_key_off(int ch)
{
	voice_t &v = m_voice[ch];

	// IDEMPOTENT. This is reached from two places — the release heuristic above and the
	// firmware's own 0x7E00 — and the firmware's 0x7E00 arrives ~41 ms after the heuristic
	// has already fired. Re-arming the counters there would restart the fade at full
	// amplitude, i.e. make a released note get LOUDER again part-way through its release.
	if (!v.key_on)
		return;

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
			// page 0 chunk 0 is a sine that begins at sample 0), which a first-sample-only
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

			// ---- Per-voice TVF (filter / brightness) from +0x100 -------------------------
			// One-pole low-pass whose cutoff the firmware computed from the patch's base
			// cutoff, its velocity curve and its key follow (see update_timbre). lp_a == 0
			// is the firmware's own bypass encoding, and costs a compare.
			if (v.lp_a > 0.0)
			{
				v.lp_z = double(sample) * (1.0 - v.lp_a) + v.lp_z * v.lp_a;
				sample = int32_t(v.lp_z);
			}

			// The group0/bank0 hand-off word's low bits, used as a linear amplitude.
			// Known to be the WRONG reading and deliberately retained — see data_w().
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
			else if (!v.key_on)
			{
				// Released AND the release fade has completed: the voice must stay SILENT.
				// hold_counter keeps it "active" ~100ms purely so the firmware's status
				// polling still sees it, but that is a bookkeeping lifetime, NOT audio.
				// Without this, once release_counter hit 0 the fade multiplier above was
				// skipped and the voice jumped back to FULL amplitude for the rest of the
				// hold — heard as the amplitude momentarily INCREASING on key release
				// (reported from real-hardware comparison, 2026-07-25).
				sample = 0;
			}

			// Apply volume. Once the key is up the amplitude comes from `sustain_vol`, the
			// level the voice was PROGRAMMED with while it was held, and the fade above
			// supplies the decay. Using volume_l here instead read the release burst's
			// TARGET level as if it were already reached, which collapsed the voice by
			// 54 dB in a single sample: an audible CLICK on every key release, MEASURED as
			// a 2346-LSB step. The chip's ramp RATE is not decoded, so we do not pretend to
			// walk to that target — see update_voice_params.
			const int32_t vol_l = v.key_on ? v.volume_l : v.sustain_vol;
			const int32_t vol_r = v.key_on ? v.volume_r : v.sustain_vol;
			mix_l += (sample * vol_l) >> 15;
			mix_r += (sample * vol_r) >> 15;

			// Advance position
			v.wave_offset += v.pitch_step;
		}

		// Output headroom / anti-clip (fix for chord distortion). Each voice can reach full
		// scale, so a chord (3 notes x up to 2 oscillators = up to ~6 voices) summed past
		// +/-32767 and the old hard clamp turned that into audible clipping. Instead of
		// clamping, apply a soft limiter: the mix is trimmed by HEADROOM and then passes
		// through LINEARLY below a knee K, and is smoothly tanh-saturated above it (so dense
		// chords compress rather than clip). Bounded to (-1,1] with no hard corner.
		// NOTE the trim applies to EVERYTHING, so the "passes through unchanged" the older
		// comment claimed is really "passes through scaled by HEADROOM, linearly": a single
		// voice at full scale peaks at 0.70, not 1.0. That is deliberate (it is the chord
		// margin) and MEASURED as not making the instrument quiet — a plain two-oscillator
		// C4 peaks at -1.2 dBFS. See notes/kn5000-faithful-render-v2.md.
		auto softclip = [](int32_t acc) -> float
		{
			constexpr float K = 0.75f;                 // linear region: |x| <= K is not saturated
			constexpr float HEADROOM = 0.70f;      // pre-limiter trim: leaves margin so chords don't slam the rail
			float x = HEADROOM * float(acc) / 32768.0f;
			float a = std::fabs(x);
			if (a <= K)
				return x;
			float sgn = (x < 0.0f) ? -1.0f : 1.0f;
			return sgn * (K + (1.0f - K) * std::tanh((a - K) / (1.0f - K)));
		};

		stream.put(0, s, sound_stream::sample_t(softclip(mix_l)));
		stream.put(1, s, sound_stream::sample_t(softclip(mix_r)));
	}
}
