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

// The firmware-derived per-selector absolute-pitch constant C, generated from
// notes/data/kn5000-pitch-trim-table.tsv by tools/gen_kn5000_pitch_trim.py. See the
// header of that file, and update_pitch() below, for what it is and what it is not.

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

// Logging
// One-shot diagnostic for the HLE-EQ insert: dumps band-0 raw C-RAM cells and the
// computed gain. Compile with -DKN5000_EQHLE_DEBUG=1 to enable; default off.
#ifndef KN5000_EQHLE_DEBUG
#define KN5000_EQHLE_DEBUG 0
#endif

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
// Per-second voice census, used to prove that the PCM and sine render modes allocate
// voices identically. Build with VERBOSE including (1U << 6).
#define LOG_CENSUS   (1U << 6)
// LOG_GLITCH: PER-VOICE click attribution. A "click" in the OUTPUT MIX proves nothing about
// which voice caused it -- two clean voices can sum to a step -- so this watches each voice's
// OWN post-pan contribution, accumulates a per-CHUNK census of the samples at which it jumps
// by more than GLITCH_THRESH, and prints that census once at device_stop. Everything a cause
// classification needs is counted there: loop-seam wraps, chunk-overrun clamps, the chunk
// geometry (N, P, P==N) and the resampling ratio. Build with VERBOSE including (1U << 7).
//
// ⚠ THE STEP DETECTOR IS NOT A GLITCH DETECTOR. |x[n]-x[n-1]| > 8000 is reached by any
// full-scale content above ~1.9 kHz, so a drum or SFX recording trips it by simply being
// played correctly. Read the census by CHUNK GEOMETRY, never by the raw count -- and note
// that the sine render mode's "zero clicks" is NOT a null that can fail: a sine at the
// demo's level physically cannot produce a step that large. See
// notes/TODO-kn5000-pcm-glitch-attribution.md.
#define LOG_GLITCH   (1U << 7)
// Step size, in output LSBs, at which a single voice's own contribution is counted. The
// mix-level detector used throughout this investigation fires at 8000; 4000 here so a voice
// that is only half the guilty step is still seen.
#define GLITCH_THRESH 4000
// LOG_WINDOW: unconditional per-sample dump of the finished output plus every voice that is
// contributing, over one hard-coded window. Used to prove that a -wavwrite capture and the
// device's own sample sequence are the same thing before any timestamp is trusted (they are:
// MEASURED 100% of 10560 samples identical, no offset).
#define LOG_WINDOW   (1U << 8)
#define WINDOW_T0    30.10
#define WINDOW_T1    30.32
// LOG_GLITCHEV: one line PER EVENT, with the full sample-path state. Verbose enough that a
// long run LOSES lines (MEASURED: an 80 s run kept ~1 in 6.5 of them while the same passage
// in a 32 s run kept all), which is exactly why LOG_GLITCH keeps counters instead.
#define LOG_GLITCHEV (1U << 9)

#define VERBOSE (0)
#include "logmacro.h"

DEFINE_DEVICE_TYPE(KN5000_TONEGEN, kn5000_tonegen_device, "kn5000_tonegen", "KN5000 Tone Generator")


// Human-readable name of a pitch_anchor_t (see the header), for the per-voice log line and
// the device_stop census. Index-matched to the enum; out-of-range reads back as "?" rather
// than walking off the array, so adding an enumerator and forgetting a name is visible in
// the log instead of being undefined behaviour.
static const char *const ANCHOR_NAMES[] =
{ "keybed", "firmware-C", "firmware-C(ambiguous)", "learned-trim", "CONSTANT-0x3524", "none" };

static const char *anchor_name(unsigned a)
{
	return (a < (sizeof(ANCHOR_NAMES) / sizeof(ANCHOR_NAMES[0]))) ? ANCHOR_NAMES[a] : "?";
}


kn5000_tonegen_device::kn5000_tonegen_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: device_t(mconfig, KN5000_TONEGEN, tag, owner, clock)
	, device_sound_interface(mconfig, *this)
	, m_addr_latch(0)
	, m_stream(nullptr)
	, m_waveform_region_tag("waveform")
	, m_waveform_data(nullptr)
	, m_waveform_size(0)
	, m_dsp1(*this, finder_base::DUMMY_TAG)
	, m_dsp1_enable(*this, finder_base::DUMMY_TAG)
	, m_dsp_hle(*this, finder_base::DUMMY_TAG)
	, m_render_mode(*this, finder_base::DUMMY_TAG)
{
}



// ---------------------------------------------------------------------------
// Save-state shadowing for the two STL containers that hold real machine state.
// save_item() takes trivially-copyable storage only, so the queue and the deque are
// flattened here and rebuilt on load. See notes/FINDINGS-savestate-audit.md for why the
// other unregistered members on this device stay unregistered.
// ---------------------------------------------------------------------------
void kn5000_tonegen_device::device_pre_save()
{
	// std::queue has no iterator: copy it and drain the copy, leaving the live one alone.
	std::queue<uint16_t> q = m_keybed_queue;
	m_kq_count = 0;
	while (!q.empty() && m_kq_count < SAVE_KQ_MAX)
	{
		m_kq_save[m_kq_count++] = q.front();
		q.pop();
	}
	if (!q.empty())
		logerror("kn5000_tonegen: keybed FIFO deeper than %d on save; %d event(s) NOT saved\n",
				SAVE_KQ_MAX, int(q.size()));

	m_pn_count = 0;
	for (const auto &ev : m_pending_notes)
	{
		if (m_pn_count >= SAVE_PN_MAX)
			break;
		m_pn_time_save[m_pn_count] = ev.first;
		m_pn_note_save[m_pn_count] = ev.second;
		m_pn_count++;
	}
}

void kn5000_tonegen_device::device_post_load()
{
	std::queue<uint16_t> empty;
	m_keybed_queue.swap(empty);
	for (uint32_t i = 0; i < m_kq_count && i < SAVE_KQ_MAX; i++)
		m_keybed_queue.push(m_kq_save[i]);

	m_pending_notes.clear();
	for (uint32_t i = 0; i < m_pn_count && i < SAVE_PN_MAX; i++)
		m_pending_notes.emplace_back(m_pn_time_save[i], int(m_pn_note_save[i]));
}

void kn5000_tonegen_device::device_start()
{
	// Create stereo output stream at 48kHz (matching DAC sample rate)
	m_stream = stream_alloc(0, 2, STREAM_RATE);

	// ---- ★★★★ §228: TELL IC311 ITS LRCK RATE ---------------------------------
	//
	// See the m_dsp1_phase banner in the header.  DEFAULT 44 100, which is Fs on
	// this instrument by four independent ROM-internal proofs (upd6383.h
	// m_frame_hz carries them).  `UPD6383_FRAMEHZ=48000' restores the pre-§228
	// behaviour -- one frame per output sample -- and is the TWO-SIDED CONTROL
	// arm: it must reproduce the archived 1 440 001 frames over 30 s exactly.
	//
	// ⚠ It is read here and not per sample, and it is announced UNCONDITIONALLY
	// with the gate's state (rule 8 as sharpened by §220).
	m_dsp1_hz = DSP_FRAME_RATE;
	if (const char *e = getenv("UPD6383_FRAMEHZ"))
	{
		const unsigned long v = strtoul(e, nullptr, 10);
		if (v >= 1000 && v <= STREAM_RATE)
			m_dsp1_hz = uint32_t(v);
	}
	logerror("kn5000_tonegen: ★★★★ §228 DSP FRAME CLOCK = %u Hz (UPD6383_FRAMEHZ; "
			"DEFAULT %u = the instrument's Fs; %u = the pre-§228 one-frame-per-output-sample "
			"behaviour, kept as the two-sided control).  The rendering stream stays at %u Hz.\n",
			m_dsp1_hz, DSP_FRAME_RATE, STREAM_RATE, STREAM_RATE);
	if (m_dsp1.found())
		m_dsp1->set_frame_hz(m_dsp1_hz);

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

	// Amplitude-EG gain curve (see eg_level_to_gain for the derivation).
	//
	// KN5000_EGLAW is an EXPERIMENT SWITCH, default OFF (= the derived log law). It exists
	// so a single binary can render both arms of the "is the EG segment LEVEL byte a log
	// code or a linear amplitude?" A/B; nothing in the shipped path reads it when unset.
	//   log (default) gain = 2^((L-255)/16)     16 counts/octave, derived from table 0x010764
	//   lin           gain = L/255              the linear-amplitude candidate under test
	// ★ DEFAULT CHANGED 2026-08-06, at Felipe's explicit direction, as a DELIBERATELY
	// PARTIAL fix shipped to gather listening data. `lin` is now ON unless
	// KN5000_EGLAW=log asks for the derived logarithmic law back.
	//
	// The honest status: the log law IS derived and bit-exact from ROM table 0x010764,
	// so `lin` is NOT believed to be the chip's true law. What it demonstrably does is
	// stop the 0x727F voice class collapsing to -53 dB after a 5 ms attack, which is
	// audible as "a click instead of a note". On its own it costs 7.65% clipped samples
	// on the organ; TOGETHER WITH KN5000_LVL080 (also now default on) it costs NONE --
	// MEASURED, 40 s captures, window 28-38 s, left channel:
	//     organ  base 8996 rms / peak 32768 / 0.0160% clipped
	//     organ  lin  18339 rms / peak 32768 / 7.6500% clipped
	//     organ  BOTH  2661 rms / peak 17676 / 0.0000% clipped
	//     piano  base 3370 rms / peak 23048 / 0.0000% clipped
	//     piano  BOTH  3668 rms / peak 24072 / 0.0000% clipped
	// So the two changes are a JOINT calibration: +0x080's per-voice level absorbs the
	// headroom the linear law spends, and the piano -- Felipe's regression gate -- lands
	// within 0.4 dB of its baseline with zero clipping.
	//
	// STILL OPEN, and the reason this is provisional rather than a fix: the true law needs
	// the chip's gain-staging REFERENCE (which code is full scale), which is not in the
	// firmware and needs one measurement on real hardware. Revisit when that arrives.
	const char *eglaw = getenv("KN5000_EGLAW");
	const bool lin = !(eglaw && eglaw[0] == 'l' && eglaw[1] == 'o');
	for (int i = 0; i < EG_GAIN_TABLE; i++)
	{
		const double L = double(i) / 16.0;
		// Level code 0 is the firmware's TERMINAL target and must render as true silence:
		// the whole voice manager presupposes that the chip can reach zero (it frees a
		// channel only once the chip reports it silent). The exact law gives -95.95 dB
		// there, which is within a hair of the 16-bit quantum anyway.
		m_eg_gain[i] = (i == 0) ? 0.0f
		             : lin ? float(L / 255.0)
		                   : float(std::pow(2.0, (L - 255.0) / 16.0));
	}
	if (lin)
		logerror("tonegen: KN5000_EGLAW=lin -- EG level byte rendered as LINEAR amplitude\n");

	// ---- EXPERIMENT SWITCHES (see the header). Both default OFF. --------------------
	//
	// KN5000_EGSEG=gate tests the hypothesis "the chip LATCHES all three segment words at
	// the note-on gate", i.e. that reading v.regs[20+seg] at the moment of the hop picks
	// up a word the note never had. What the raw bus says about that is written up at
	// load_eg_segment(); the switch exists so the claim is answered with a rendered
	// measurement and not only with an argument.
	//
	// KN5000_LVL080=on renders register +0x080 as the per-voice output level that
	// Voice_Build_OutputLevel builds it into, instead of using it only as a burst strobe.
	if (const char *s = getenv("KN5000_EGSEG"))
		m_eg_gate_latch = (s[0] == 'g');

	// ---- ROM-INTEGRITY MUTE (NOT an experiment switch), DEFAULT ON ------------------
	// Specified by Felipe, 2026-08-06: "I want the PCM mode to mute all samples from the
	// undumped ROMs, but do not mute any samples from the good ROM. And I want the sine
	// wave mode to play everything regardless of the associated ROM, because it does not
	// depend on the samples, so there's no need to mute them in that mode."
	//
	// IC307 is the only wave ROM anyone has dumped. IC304/305/306 are loaded with a
	// BAD_DUMP copy of it (kn5000.cpp ROM_REGION), so every voice that selects one of them
	// plays a REAL RECORDING FROM THE WRONG PLACE. No level metric can see that — rms,
	// peak and clipping are all perfectly happy while the instrument plays the wrong
	// instrument — which is exactly how it went unnoticed until Felipe listened.
	//
	// KN5000_UNDUMPED=play renders them anyway. Use it to hear WHAT is being suppressed
	// and how loud it would be, never as the shipped default.
	if (const char *s = getenv("KN5000_UNDUMPED"))
		m_mute_undumped = !(s[0] == 'p');
	logerror("tonegen: undumped-socket mute is %s (PCM mode only; sine mode always plays everything)\n",
			m_mute_undumped ? "ON" : "OFF (KN5000_UNDUMPED=play)");
	// DEFAULT ON since 2026-08-06 -- see the EG-law banner above; the two are a joint
	// calibration and enabling only one of them clips. KN5000_LVL080=off restores the
	// old strobe-only behaviour.
	m_use_level080 = true;
	if (const char *s = getenv("KN5000_LVL080"))
		m_use_level080 = !(s[0] == 'o' && s[1] == 'f');
	// ★ DEFAULT OFF, and the two paragraphs that follow are the DECODE (which stands);
	// the ⚠⚠ block below is WHY IT IS NOT ENABLED (which was re-derived on 2026-08-06 and
	// is not what the first attempt said). The group0/bank0 hand-off word's low bits are
	// NOT an amplitude, and reading them as one silences 42% of both demos' note-ons.
	//
	// DERIVED from the sub-CPU ROM: slot[+0x2D] is built by exactly two routines --
	// Voice_Build_GateCommand (0x025589) computes low = 0xFF - 4*(partial[0] & 0x3F) with
	// BIT 8 AS ITS OWN ENABLE, and its twin ..._NoPartial (0x0255F3) computes no low field
	// at all. MEASURED over 1814 note-ons on the live bus: the low byte is only ever 0x00
	// or 0xFF and bit 8 is NEVER SET (1814/1814). So we were reading a disabled per-partial
	// parameter as a linear gain.
	//
	// The population split is structural, not musical: 81-byte partials always give 0xFF,
	// 21-byte partials always give 0x00, and Part 3 is 100% of the 21-byte kind in both
	// demos (157/157 organ, 146/146 piano) with drum-key-shaped descriptors on a steady
	// onset grid -- it is the percussion part. ⚠ BUT PART 3 IS NOT THE WHOLE MUTED
	// POPULATION, and calling the mute "the drum mute" was the error that produced the
	// wrong noise attribution below: 739 organ note-ons carry low byte 0x00, of which only
	// 157 are Part 3. The other 553+ are class-6 = IC307 page 2 = the organ's own drawbar
	// footage waves. Both parts are silenced by this read; only one of them is percussion.
	//
	// THE TEST THAT COULD HAVE FAILED: within those 185 drum note-ons the word is
	// BIT-IDENTICAL while their own loudness registers span 32.7 dB of EG attack level and
	// 8.3 dB of +0x080 output level. So it is not a velocity, not a per-part volume, and
	// not an expression value (expression is part+0x10 and reaches the chip via the EG).
	//
	// MEASURED effect (base -> ctrl), INAUDIBLE / OK note counts:
	//   organ pcm  1320/338 -> 1199/473     organ sine 1516/198 -> 1404/316
	//   piano pcm   247/342 ->  142/451     piano sine  218/377 ->  157/438
	// The drum class's median voice peak rises +25.4 dB; the already-audible classes are
	// bit-unchanged.
	//
	// ⚠⚠ REVERTED TO DEFAULT OFF, 2026-08-06, ON FELIPE'S LISTENING TEST: with the decode
	// on, the organ demo is "really bad, extreme noise".
	//
	// ⚠ AND THE FIRST EXPLANATION OF THAT NOISE WAS WRONG. It said the un-muted voices are
	// the percussion part and that percussion selects the UNDUMPED sockets, so un-muting
	// played substituted recordings. RETRACTED, 2026-08-06 — the bank census refutes it
	// outright. Of the note-ons this decode un-mutes (hand-off low byte 0x00):
	//     organ 739 of 1827, of which 738 are on BANK 1 = IC307, the good dump
	//     piano 180 of  666, of which 179 are on BANK 1 = IC307
	// One note-on in each demo, the power-on ping at +040 = 0x0000, is not. So the noise is
	// NOT the missing dumps, the undumped-socket mute below cannot suppress it, and
	// re-enabling this decode on that reasoning would ship the same noise again.
	//
	// WHAT THE NOISE ACTUALLY IS, measured on the same capture. The un-muted organ voices
	// are 185 selections of IC307 PAGE 1 held for a MEDIAN OF 4.4 SECONDS (max 6.3), and
	// detect_period cannot pitch those recordings. Its fallback then declares the WHOLE
	// recording to be one cycle, so update_pitch stretches it to reach the note:
	//     +040 = 0x505B  87 notes  1496 samples "one cycle" -> played at 11.5x
	//     +040 = 0x5046   7 notes  1568 samples "one cycle" -> played at 19.0x
	// A 31 ms recording crammed into one 130-sample cycle (369.9 Hz) and repeated ~1830
	// times over a five-second note is a granular buzz at the right pitch, not a note. The
	// other 53 get period 0 (genuinely aperiodic, zcr 0.40-0.59) and compute_loop gives them
	// loop_len = the whole recording, so a 51 ms noise burst repeats ~100 times per note, at
	// up to -4.6 dBFS while the organ's own voices sit at -36 dBFS. MEASURED on the ctrl arm
	// WITH the bank mute on: mix rms -29.2 -> -12.9 dB, peak 8012 -> 32502 (-0.07 dBFS).
	// That is the extreme noise, and it is an HLE defect in the period/loop estimators on
	// the GOOD dump — see notes/FINDINGS-kn5000-eg-level-law.md §J.
	//
	// SO THIS STAYS OFF until the P == wave_samples fallback is fixed, and it is worth
	// saying what it costs: it is the LARGEST single defect in the organ demo. It silences
	// 738 of 1762 note-ons (42%) — more than the missing ROMs (64) and more than the faint
	// EG class (599) — and those 738 are on the one ROM we actually have.
	//
	// KN5000_HANDOFF=ctrl re-enables it. In SINE mode it is safe and informative: no PCM is
	// read, so neither failure above exists, and it is how to hear the muted part's timing
	// and envelopes.
	// KN5000_EGFREE=on -- the refuted probe that reports a voice silent once its last EG
	// segment reaches its target. Kept because it isolates that one mechanism cleanly, but it
	// DELETES HELD NOTES, so it must never be reachable from the UI: it was a persisted
	// PORT_CONFNAME until 2026-08-06 and silently broke Felipe's instrument for a day.
	if (const char *s = getenv("KN5000_EGFREE"))
		m_eg_free_probe = (s[0] == 'o' && s[1] == 'n') || s[0] == '1';
	if (m_eg_free_probe)
		logerror("tonegen: KN5000_EGFREE=on -- freeing voices once the EG finishes (DELETES HELD NOTES)\n");

	m_handoff_ctrl = false;
	if (const char *s = getenv("KN5000_HANDOFF"))
		m_handoff_ctrl = (s[0] == 'c');
	if (m_eg_gate_latch)
		logerror("tonegen: KN5000_EGSEG=gate -- EG segment words LATCHED at the note-on gate\n");
	if (m_use_level080)
		logerror("tonegen: KN5000_LVL080=on -- +0x080 rendered as a per-voice output level\n");
	if (m_handoff_ctrl)
		logerror("tonegen: KN5000_HANDOFF=ctrl -- hand-off word carries no amplitude\n");

	// Diagnostic sine oscillator table (see SINE_PEAK in the header for how the
	// amplitude was chosen). Tabulated + interpolated rather than calling std::sin per
	// sample, mirroring m_eg_gain above: this mode exists to expose glitches, so its own
	// distortion must stay far below anything that could be mistaken for one.
	for (int i = 0; i < SINE_TABLE; i++)
		m_sine_tab[i] = int16_t(std::lround(double(SINE_PEAK) * std::sin(2.0 * M_PI * double(i) / double(SINE_TABLE))));

	// Save state
	save_item(NAME(m_addr_latch));
	save_item(NAME(m_global_regs));
	save_item(NAME(m_kq_save));
	save_item(NAME(m_kq_count));
	save_item(NAME(m_pn_time_save));
	save_item(NAME(m_pn_note_save));
	save_item(NAME(m_pn_count));
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
		save_item(NAME(m_voice[i].sine_phase), i);
		save_item(NAME(m_voice[i].sine_inc), i);
		save_item(NAME(m_voice[i].volume_l), i);
		save_item(NAME(m_voice[i].volume_r), i);
		save_item(NAME(m_voice[i].release_counter), i);
		save_item(NAME(m_voice[i].hold_counter), i);
		save_item(NAME(m_voice[i].eg_level), i);
		save_item(NAME(m_voice[i].eg_target), i);
		save_item(NAME(m_voice[i].eg_step), i);
		save_item(NAME(m_voice[i].eg_seg), i);
		save_item(NAME(m_voice[i].eg_word), i);
		save_item(NAME(m_voice[i].gain080), i);
		save_item(NAME(m_voice[i].eg_running), i);
		save_item(NAME(m_voice[i].silent_samples), i);
		save_item(NAME(m_voice[i].env_level), i);
		save_item(NAME(m_voice[i].lp_a), i);
		save_item(NAME(m_voice[i].lp_z), i);
	}

	//  ★ §228: the LRCK accumulator and the held return are stream state.
	save_item(NAME(m_dsp1_phase));
	save_item(NAME(m_dsp1_wet));

	// ---- PER-NOTE-ON CAPTURE (KN5000_NOTELOG), default OFF --------------------------
	if (const char *nlpath = std::getenv("KN5000_NOTELOG"))
	{
		if (*nlpath)
		{
			m_notelog = std::fopen(nlpath, "w");
			if (m_notelog)
				std::fprintf(m_notelog,
					"t_on,ch,sel040,r080,r100,r180,r400,eg0,eg1,eg2,"
					"eg0_lvl,eg0_rate,eg1_lvl,eg1_rate,eg2_lvl,eg2_rate,"
					"env_on,eg_level0,eg_target0,eg_step0,eg_seg0,"
					"lp_a,vol_l,vol_r,bank,page,chunk,wave_real,wave_samples,period,"
					"true_note,anchor,pitch_step,pitch_off,mode,"
					"t_off,dur,nsamp,peak,rms,peak_db,rms_db,"
					"env_hand,hand_word,t_hand_rel,env_end,eg_level_end,eg_seg_end,"
					"eg0_end,eg1_end,eg2_end,t_ko_rel,ko_src,prof10ms,eglvl10ms,egseg10ms,"
					"adv01_word,adv01_lvl,adv01_at,adv12_word,adv12_lvl,adv12_at,reason\n");
			else
				logerror("tonegen: KN5000_NOTELOG='%s' could not be opened; capture is OFF\n", nlpath);
		}
	}
}


// ---------------------------------------------------------------------------------------
// PER-NOTE-ON CAPTURE (KN5000_NOTELOG) — see the declaration in the header.
// ---------------------------------------------------------------------------------------
//
// notelog_begin() runs at the very END of process_key_on(), i.e. after the waveform, the
// pitch, the pan, the TVF and EG segment 0 have all been resolved, so the row records the
// state the note ACTUALLY STARTS FROM rather than a mid-burst snapshot.
//
// The three EG words are logged twice: as programmed at the gate (eg0/eg1/eg2) and as they
// stand when the note is flushed (eg0_end/eg1_end/eg2_end), because the firmware rewrites
// them on release. env_on is likewise near-useless on its own — process_key_on() forces
// env_level to 0xFF and the group0/bank0 hand-off word arrives tens of microseconds LATER —
// so the hand-off value and its delay are captured separately (env_hand / t_hand_rel).
void kn5000_tonegen_device::notelog_begin(int ch)
{
	if (!m_notelog)
		return;

	notelog_flush(ch, "retrig");

	const voice_t &v = m_voice[ch];
	notelog_rec_t &r = m_nl[ch];

	char buf[768];
	std::snprintf(buf, sizeof(buf),
		"%.6f,%d,%04X,%04X,%04X,%04X,%04X,%04X,%04X,%04X,"
		"%u,%u,%u,%u,%u,%u,"
		"%d,%.4f,%.4f,%.9f,%d,"
		"%.6f,%d,%d,%d,%d,%d,%d,%u,%u,"
		"%d,%u,%u,%.4f,%s",
		machine().time().as_double(), ch,
		v.regs[1], v.regs[2], v.regs[4], v.regs[6], v.regs[8],
		v.regs[20], v.regs[21], v.regs[22],
		unsigned((v.regs[20] >> 8) & 0xFF), unsigned(v.regs[20] & 0xFF),
		unsigned((v.regs[21] >> 8) & 0xFF), unsigned(v.regs[21] & 0xFF),
		unsigned((v.regs[22] >> 8) & 0xFF), unsigned(v.regs[22] & 0xFF),
		v.env_level, v.eg_level, v.eg_target, v.eg_step, v.eg_seg,
		v.lp_a, int(v.volume_l), int(v.volume_r),
		v.wave_bank, v.wave_page, v.wave_chunk, v.wave_real ? 1 : 0,
		v.wave_samples, v.pitch_period,
		v.true_note, unsigned(v.pitch_anchor), v.pitch_step, v.pitch_offset,
		(m_render_mode.read_safe(0) & 3) == RENDER_SINE ? "sine" :
		(m_render_mode.read_safe(0) & 3) == RENDER_SINE_SUB ? "pcm+sine-substitutes" : "pcm");

	r.head     = buf;
	r.open     = true;
	r.t_on     = machine().time().as_double();
	r.nsamp    = 0;
	r.peak     = 0;
	r.sumsq    = 0.0;
	r.env_hand  = -1;
	r.hand_word = -1;
	r.t_hand    = -1.0;
	r.t_ko     = -1.0;
	r.ko_src   = 0;
	r.s0       = m_nl_sampclock;
	std::fill(std::begin(r.prof), std::end(r.prof), 0);
	std::fill(std::begin(r.eglvl), std::end(r.eglvl), int16_t(-1));
	std::fill(std::begin(r.egseg), std::end(r.egseg), int8_t(-1));
	r.adv_word[0] = r.adv_word[1] = 0xFFFF;
	r.adv_lvl[0]  = r.adv_lvl[1]  = -1;
	r.adv_at[0]   = r.adv_at[1]   = -1;
}


// Called immediately BEFORE the EG hops out of its running segment, so it records the word
// that was in force when the hop was allowed rather than the one that replaces it.
void kn5000_tonegen_device::notelog_seg_advance(int ch)
{
	if (!m_notelog)
		return;
	notelog_rec_t &r = m_nl[ch];
	if (!r.open)
		return;
	const voice_t &v = m_voice[ch];
	const int i = v.eg_seg;                // 0 -> 1 or 1 -> 2
	if (i < 0 || i > 1 || r.adv_at[i] >= 0)
		return;
	r.adv_word[i] = v.regs[20 + i];
	r.adv_lvl[i]  = int16_t(std::lround(v.eg_level));
	r.adv_at[i]   = int32_t(r.nsamp);
}


void kn5000_tonegen_device::notelog_flush(int ch, const char *reason)
{
	if (!m_notelog)
		return;
	notelog_rec_t &r = m_nl[ch];
	if (!r.open)
		return;
	r.open = false;

	const voice_t &v = m_voice[ch];
	const double t   = machine().time().as_double();
	const double rms = r.nsamp ? std::sqrt(r.sumsq / double(r.nsamp)) : 0.0;
	// dBFS against the 16-bit output scale the voice is summed into. A voice that rendered
	// nothing at all reports -999 rather than -inf so the column stays numeric.
	auto db = [](double x) { return (x > 0.0) ? 20.0 * std::log10(x / 32768.0) : -999.0; };

	std::string prof, eglvl, egseg;
	for (int i = 0; i < notelog_rec_t::NPROF; i++)
	{
		char pb[24];
		std::snprintf(pb, sizeof(pb), "%s%d", i ? ";" : "", r.prof[i]);   prof  += pb;
		std::snprintf(pb, sizeof(pb), "%s%d", i ? ";" : "", r.eglvl[i]);  eglvl += pb;
		std::snprintf(pb, sizeof(pb), "%s%d", i ? ";" : "", r.egseg[i]);  egseg += pb;
	}

	std::fprintf(m_notelog,
		"%s,%.6f,%.6f,%llu,%d,%.3f,%.2f,%.2f,%d,%04X,%.6f,%d,%.4f,%d,%04X,%04X,%04X,%.6f,%d,%s,%s,%s,"
		"%04X,%d,%d,%04X,%d,%d,%s\n",
		r.head.c_str(), t, t - r.t_on, (unsigned long long)r.nsamp,
		r.peak, rms, db(double(r.peak)), db(rms),
		r.env_hand, unsigned(r.hand_word & 0xFFFF),
		(r.t_hand >= 0.0) ? (r.t_hand - r.t_on) : -1.0,
		v.env_level, v.eg_level, v.eg_seg,
		v.regs[20], v.regs[21], v.regs[22],
		(r.t_ko >= 0.0) ? (r.t_ko - r.t_on) : -1.0, r.ko_src,
		prof.c_str(), eglvl.c_str(), egseg.c_str(),
		r.adv_word[0], r.adv_lvl[0], r.adv_at[0],
		r.adv_word[1], r.adv_lvl[1], r.adv_at[1], reason);
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


void kn5000_tonegen_device::device_stop()
{
	// Notes still sounding when the run ends still carry an outcome; flush them rather than
	// silently dropping them, so a row count can be reconciled against the note-on count.
	if (m_notelog)
	{
		for (int ch = 0; ch < NUM_VOICES; ch++)
			notelog_flush(ch, "eof");
		std::fclose(m_notelog);
		m_notelog = nullptr;
	}

	// ---- UNDUMPED-SOCKET CENSUS --------------------------------------------------------
	// UNCONDITIONAL, like the pitch-anchor census below and for the same reason: a run that
	// silently dropped part of the music must say so. Grep for it before believing any
	// statement about what this driver's audio does or does not contain.
	if (m_undumped_muted)
		logerror("tonegen: %u note-ons selected an UNDUMPED socket (IC304/305/306); "
				"PCM mode rendered them %s\n",
				uint32_t(m_undumped_muted), m_mute_undumped ? "SILENT" : "with substituted IC307 material");

	// ---- LOG_GLITCH summary: WHICH CHUNK produced the clicks (VERBOSE bit 7) -----------
	// One line per wave-ROM chunk that ever made a voice's own contribution jump by more
	// than GLITCH_THRESH, so the attribution survives a run of any length.
	if (VERBOSE & LOG_GLITCH)
	{
		logerror("glitch census: %u per-voice events, %u mix clicks (>8000) over %.3f s\n",
				uint32_t(m_glitch_total), uint32_t(m_mixclick_total), machine().time().as_double());
		std::vector<std::pair<uint32_t, glitch_stat_t>> gv(m_glitch_chunk.begin(), m_glitch_chunk.end());
		std::sort(gv.begin(), gv.end(), [](auto &a, auto &b) { return a.second.events > b.second.events; });
		for (const auto &e : gv)
			logerror("glitch chunk b%dp%dc%-4d real=%d N=%-6u P=%-5u P==N=%d maxstep=%6.2fx "
					"events=%-6u mean|d|=%-6u max|d|=%-6u wraps=%-5u clamps=%u\n",
					(e.first >> 20) & 3, (e.first >> 16) & 3, e.first & 0xFFFF, e.second.real ? 1 : 0,
					e.second.samples, e.second.period, (e.second.period == e.second.samples) ? 1 : 0,
					double(e.second.max_step) / 65536.0, uint32_t(e.second.events),
					uint32_t(e.second.sum_d / std::max<uint64_t>(1, e.second.events)),
					e.second.max_d, uint32_t(e.second.wraps), uint32_t(e.second.clamps));
	}

	// ---- PITCH-ANCHOR CENSUS -----------------------------------------------------------
	// UNCONDITIONAL (not behind VERBOSE): the point of it is that the fallback to the bare
	// 0x3524 constant — which is NOT a measurement — can never be silent. One line per
	// anchor source, plus the selectors that nothing could place.
	{
		uint64_t total = 0;
		for (unsigned i = 0; i < unsigned(ANCHOR_COUNT); i++)
			total += m_anchor_census[i];
		if (total != 0)
		{
			logerror("kn5000_tonegen: pitch-anchor census over %u note-ons "
					"(C table: %u selectors, %u single-valued, %u ambiguous):\n",
					uint32_t(total), uint32_t(m_pitch_c.size()),
					m_pitch_single, m_pitch_ambiguous);
			for (unsigned i = 0; i < unsigned(ANCHOR_COUNT); i++)
				logerror("   %-24s %8u  (%5.1f%%)\n", anchor_name(i),
						uint32_t(m_anchor_census[i]),
						100.0 * double(m_anchor_census[i]) / double(total));
			if (!m_anchor_unplaced.empty())
			{
				// Sort by how often each unplaced selector was keyed, most first: that is the
				// work list for extending the table, and it is the honest statement of what
				// this decode does NOT cover.
				std::vector<std::pair<uint16_t, uint64_t>> u(m_anchor_unplaced.begin(), m_anchor_unplaced.end());
				std::sort(u.begin(), u.end(), [](auto &a, auto &b) { return a.second > b.second; });
				logerror("   ⚠ %u selectors have NO firmware C and fell back to the constant:\n",
						uint32_t(u.size()));
				for (size_t i = 0; i < u.size() && i < 24; i++)
					logerror("      +0x040 = %04X  (class %d entry %03X)  %u note-ons\n",
							u[i].first, (u[i].first >> 12) & 0x0F, u[i].first & 0x0FFF,
							uint32_t(u[i].second));
				if (u.size() > 24)
					logerror("      ... and %u more\n", uint32_t(u.size() - 24));
			}
		}
	}

	// Honest accounting of the EXPERIMENTAL IC311 send/return. Reported here as
	// well as in the DSP device itself because this is the side that decides
	// whether a return was actually mixed in.
	if (m_dsp1_frames != 0)
	{
		// plain %u, matching MAME house style (a u64 count only overflows u32
		// after ~25 hours of emulated audio at 48 kHz).
		logerror("IC311 send/return: %u frames sent, %u returns USABLE (%u per 10000).\n",
				uint32_t(m_dsp1_frames), uint32_t(m_dsp1_kept),
				uint32_t((10000 * m_dsp1_kept) / m_dsp1_frames));
		//  ★★★★ §228: SAY THE CLOCK OUT LOUD, from THIS side of the pin, with the
		//  measurement that grades it.  Frames per emulated second is the one
		//  figure here that the declaration cannot fabricate.
		{
			const double secs = machine().time().as_double();
			logerror("kn5000_tonegen: ★★★★ §228 DSP FRAME CLOCK: declared %u Hz, rendering "
					"stream %u Hz, %u frames over %.6f emulated s = %.3f frames/s "
					"(pre-§228 this read 48000.0 -- archived arms, 1440001 frames / 30 s)\n",
					m_dsp1_hz, STREAM_RATE, uint32_t(m_dsp1_frames), secs,
					(secs > 0.0) ? double(m_dsp1_frames) / secs : 0.0);
		}
		if (m_insta_n)
			//  ⚠ §228 CHANGED THIS DENOMINATOR, deliberately: the audit is inside
			//  the LRCK gate, so it counts the channel-samples the CHIP ACTUALLY
			//  SEES (2 per frame), not the ones MAME renders.  Against a pre-§228
			//  log it is smaller by 44100/48000; the PERCENTAGES are comparable,
			//  the raw count is not.
			logerror("kn5000_tonegen: DSP INPUT AUDIT -- %u channel-samples AT LRCK, peak |mix| %d "
					"(full scale 32768), clipped %u (%.2f%%), over 2x FS %u (%.2f%%), mean |mix| %u\n",
					uint32_t(m_insta_n), m_insta_peak,
					uint32_t(m_insta_clip), 100.0 * double(m_insta_clip) / double(m_insta_n),
					uint32_t(m_insta_clip2x), 100.0 * double(m_insta_clip2x) / double(m_insta_n),
					uint32_t(m_insta_sum / m_insta_n));
		if (m_dsp1_kept == 0)
			logerror("IC311 send/return: EVERY frame trapped, so EVERY return was discarded and\n"
					"    the rendered audio is EXACTLY the dry mix. That is the expected outcome\n"
					"    today -- see notes/dsp-audiopath-wired.md. Whether the SEND is reaching\n"
					"    the microcode at all is a separate question, and the DSP's own\n"
					"    INPUT-STAGE AUDIT above answers it (notes/dsp-k6-input-stage-applied.md).\n");
	}
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
	// ---- THE HAND-OFF WORD, DECODED (2026-08-06) ------------------------------------
	// Its low field is NOT an amplitude, and reading it as one is what makes 42 % of the
	// organ demo's note-ons — INCLUDING THE ENTIRE DRUM PART — silent. The word is the last
	// write of the note-on burst and it is emitted per PARTIAL by one of two builders,
	// chosen by which PARTIAL-RECORD LAYOUT the voice's partial belongs to:
	//
	//   Voice_Build_GateCommand  0x025589   low9 = (0xFF - 4*(partial[0] & 0x3F))
	//                                              | (partial[0] != 0 ? 0x100 : 0)
	//   ..._NoPartial            0x0255F3   low9 = 0  (a BARE 0xF000 / 0xFE00 constant;
	//                                                  no low field is computed at all)
	//   both then OR in 0xF000 (or 0xFE00 when part[+0x12] != 0 and the global mode byte
	//   0x04134C is in {0,5,6}) and run Voice_Apply_GateRouting 0x02552A, which rewrites
	//   bits[14:12] and bits[11:9] from the two nibbles of part[+0x25] (CC 0x9B).
	//
	// MEASURED, tools/kn5000_handoff_probe.lua, both demos, t = 22–40 s, reading the
	// sub-CPU's own slot record (0x04308E + ch*0x47) at each write. 1330 organ + 484 piano
	// hand-offs, one per gate, exactly four distinct values:
	//
	//   organ  FEFF 706  FE00 412  F000 157  F0FF  55
	//   piano  F0FF 278  F000 146  FEFF  60
	//
	//   * the low byte is only ever 0x00 or 0xFF and BIT 8 IS NEVER SET (1814/1814), i.e.
	//     partial[0] == 0 in every one of the 1495 note-ons that ran the 0x025589 builder,
	//     so its "magnitude" is the constant 0xFF by construction. It does not track
	//     velocity, volume or expression — it does not vary at all;
	//   * low byte 0x00 comes from the OTHER builder, and the split is by partial-record
	//     LAYOUT, not by loudness: the slot's partial pointer sits at tone_base + {102,
	//     183, 264, 345} (81-byte records) for every 0xFF note and at tone_base + {16, 37}
	//     (21-byte records) for every 0x00 note, 1814/1814;
	//   * PART 3 — the drum/rhythm part — is 100 % of the second kind (157/157 organ,
	//     146/146 piano), and its partial byte varies per hit (0x14, 0x20, 0x28, 0x34,
	//     0x40, 0x4C, 0x58, 0x60, 0x6C) exactly as a drum key would. The organ's parts 0
	//     and 1 fire SIX and FIVE voices per note-on, of which two are of the second kind.
	//
	// So `sample * env_level / 0xFF` is not a level control: it is a mute keyed on a tone
	// architecture bit, and it deletes every percussion voice in the instrument. The
	// earlier reading ("the five sites that ship slot[+0x2d] free the channel next line")
	// was based on a stale symbol — LABEL_022587 is Voice_Clear_HoldBit, which clears the
	// voice's HELD bit and re-prioritises; it does not free anything. On the bus the free
	// count matches the gate count (1320 vs 1330 organ, 458 vs 484 piano), so handed-off
	// voices ARE reclaimed.
	//
	// KN5000_HANDOFF=ctrl renders the decode (env_level stays 0xFF for every voice); the
	// default is still the old magnitude reading. See notes/FINDINGS-kn5000-handoff-word.md
	// for why the decoded arm is not yet the default.
	if (group == 0 && bank == 0)
	{
		if (data == 0x7E00)
		{
			// FREE. This is the firmware's REPLY to our own silence report (status_r), so by
			// construction the channel is already inaudible when it arrives. It drops the
			// eg_running latch at once — the firmware has taken the channel back and must be
			// able to re-gate it — while the short fade below finishes any residue.
			//
			// The lifecycle design (rule R5) calls for a hard stop on the same sample. That is
			// NOT adopted here and the reason is measured, not cautious: with the release
			// heuristic still in place (GAP LIFE-2 below), the 0x7E00 for a key-bed voice
			// arrives ~41 ms after the fade has already started, when the voice is still at
			// ~18 % amplitude — a hard stop there would ADD a click that today's guarded
			// path does not have. R5 only becomes free once the chip's own release ramp is
			// decoded; see notes/audit/kn5000-gaps-applied.md.
			if (VERBOSE & LOG_CENSUS) m_census_clr[0]++;
			m_voice[ch].eg_running = false;
			const bool was_on = m_voice[ch].key_on;
			process_key_off(ch);
			// PER-NOTE-ON CAPTURE: attribute the release to the firmware's own free.
			if (m_notelog && m_nl[ch].open && was_on && m_nl[ch].t_ko < 0.0)
			{ m_nl[ch].t_ko = machine().time().as_double(); m_nl[ch].ko_src = 2; }
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
			// EXPERIMENT (KN5000_HANDOFF=ctrl): with the decode above, the word carries no
			// amplitude at all and env_level stays at the 0xFF process_key_on() set.
			if (!m_handoff_ctrl)
				m_voice[ch].env_level = std::min<int>(data & 0x1FF, 0xFF);
			// PER-NOTE-ON CAPTURE: record the hand-off separately from the note-on snapshot.
			// process_key_on() forces env_level to 0xFF, so the value that actually gates
			// this note only exists from here on. The RAW word is logged too — the fields
			// that matter (bits[14:12], bits[11:9], bit 8) are all above the low byte.
			if (m_notelog && m_nl[ch].open && m_nl[ch].env_hand < 0)
			{
				m_nl[ch].env_hand  = std::min<int>(data & 0x1FF, 0xFF);
				m_nl[ch].hand_word = data;
				m_nl[ch].t_hand    = machine().time().as_double();
			}
		}
	}

	// Key RELEASE detection — GAP LIFE-2, and the answer is that THERE IS NO DETERMINISTIC
	// NOTE-OFF SIGNAL ON THIS BUS. IC303 has no note-off input: +0x000 takes a GATE (0x81xx)
	// and a FREE (0x7E00) and nothing else, and a key release reaches the chip only as a new
	// (target, rate) for the amplitude EG. Four measured facts kill every candidate signal:
	//   * LABEL_02CD71 (asm L29178) is a GENERAL "levels changed" service with ten call
	//     sites; Voice_CC_Portamento (L25150) -> LABEL_02CCD3 (L29116) -> Voice_ParamInit
	//     (L29344) -> LABEL_02CD71 -> LABEL_02D436 re-emits the whole six-write "release"
	//     burst on every sounding channel of a part WITH THE KEYS STILL DOWN;
	//   * Voice_ParamInit is simultaneously the note-off service (asm L29469, the velocity-0
	//     branch of Voice_NoteOn) — one routine, both duties;
	//   * a note-off may produce NO bus write at all for up to ~3.1 s (chan[+0x2f] |= 0x0080
	//     arms a countdown, asm L29372-L29386, consumed by LABEL_026E5B at L21467);
	//   * a note-off may instead arrive as a hard mute 0xFF00/0xFF80 (Voice_NoteOff asm
	//     L28663/L28677) which is BYTE-IDENTICAL to the note-ON pre-mute from Voice_SetPitch
	//     (L28560/L28578).
	// The +0x840 -> +0x940 adjacency proposed by the audit is exact for LABEL_02D436, but
	// LABEL_02D436 is not note-off-specific: it says "the EG program was replaced", which is
	// precisely the thing that carries no note-off information. Reported as a MISS rather
	// than shipped.
	//
	// So the timing HEURISTIC below stays. The lifecycle design would delete it, on the
	// argument that the chip's own release ramp ends the note and status_r then reports the
	// silence — but that ramp is exactly what is NOT decoded (the low byte of the +0x800
	// release word is 0x80, i.e. rate 0 = HOLD, so an EG driven straight from the register
	// stream would freeze a released note at its sustain level and never end it). Until the
	// meaning of that bit-7 word is established, this heuristic is the only thing that ends
	// a key-bed note, and removing it would be a regression, not a fix.
	//
	// Its limits are known. When a held key is released the sub-CPU re-programs the voice's
	// envelope generator: a burst of six writes to groups 8/9/A (routine LABEL_027FD6 in
	// v142 asm L23045, and its twin LABEL_02D436 at L29936). It writes the 0x7E00 key-off
	// only LATER, once its voice manager (LABEL_02219F asm L13273 -> LABEL_02B4A1 L26770)
	// sees the chip report the voice SILENT. Both note-on setup AND note-off release program
	// the same EG registers, so a register write alone is ambiguous.
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
		{
			process_key_off(ch);
			// PER-NOTE-ON CAPTURE: attribute the release to the group9 timing heuristic.
			if (m_notelog && m_nl[ch].open && m_nl[ch].t_ko < 0.0)
			{ m_nl[ch].t_ko = now; m_nl[ch].ko_src = 1; }
		}
	}

	// EFFECT SENDS: there are none, and ignoring +0x8C0 / +0x900..+0x9C0 / +0xA00 / +0xA40
	// is CORRECT, not a gap. They are envelope-generator stage words of exactly the same
	// shape as +0x800/+0x840/+0x880: the +0x8C0 builder (asm L17645-17660) is literally
	// `rate = curve(TONE[+0x3d] + TONE[+0x3e]); level<<8; OR; LD (0451EAh),WA`, and
	// LABEL_027FD6 (L23045) / LABEL_02D436 (L29936) rewrite six of them as three (seg0,seg1)
	// PAIRS from consecutive struct words — a send would not be paired with another send by
	// a shared struct stride. The effects live on a DIFFERENT bus (DSP1/DSP2 at 0x130000 /
	// 0x130002, DSP_Write_Channel L9687), and the per-part depths (CC 0x91 -> chan+0x7F,
	// 0x97 -> +0x80, 0x9B -> +0x8D) never reach IC303: the depth routine LABEL_0233F8
	// (L15318-15600) contains no 0x100000/0x100002 access at all. No placeholder is written.
	// (What IS still missing from those words is their role as ENVELOPES — the two extra EGs
	// are not modelled; only the amplitude EG is.)

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

	// PAN (+0x180 = group 1, bank 2) and the amplitude EG (+0x800/+0x840/+0x880 = group 8).
	// Group 0 bank 2 is included because the burst's final +0x080 write is its end strobe.
	// +0x180 is written BEFORE the gate in the note-on burst (MEASURED: 22.307762 0180 0000
	// vs 22.307783 0000 8100), so the pan is valid from the very first rendered sample; it
	// can also be re-shipped mid-note by LABEL_026F4A, so it is read live rather than latched.
	if ((group == 0 && bank == 2) || (group == 1 && bank == 2) || group == 8)
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
	// Chip status poll (read from 0x100000), and the closing half of GAP LIFE-1.
	//
	// THE ROOT FACT: IC303 has no note-off input. Its control register +0x000 accepts
	// exactly two lifecycle commands — 0x81xx = GATE and 0x7E00 = FREE — and everything
	// between is envelope programming. So the firmware learns that a note has ended by
	// ASKING THE CHIP, through this port, and that closes a loop the HLE used to break.
	// MEASURED on the live bus: `12.481481 R 0000 0000` -> `12.481537 W 0000 7E00`, 56 us
	// later. The comment that used to stand here — "a handed-off voice can never get a
	// 0x7E00" — is therefore false: the 0x7E00 is GENERATED BY the silence report.
	// Because we never reported silence, handed-off (accompaniment / rhythm) voices were
	// never freed: MEASURED, ch0 gated 5.859349, handed off 5.859385, never freed,
	// re-gated 12.006012 for a different note.
	//
	// R0 — THE LATCH IS NOT TWO BITS. The firmware issues two different reads through this
	// one port (asm L13280 and L13341):
	//     latch 0x0000..0x0003  -> the active-voice bitmap of that bank of 16
	//     latch 0x0180 + ch     -> that voice's current envelope level
	//     anything else         -> not issued by v142
	// Masking the latch to 2 bits answered a level query with a bank bitmap (MEASURED:
	// latch 0x0180 returned 0x0003, latch 0x018C returned 0xFC00).
	m_stream->update();   // the silence interlock below is maintained per rendered sample

	const uint16_t latch = m_addr_latch;

	if (latch >= 0x0180 && latch < 0x0180 + NUM_VOICES)
	{
		// Per-voice envelope-level readback. The firmware keeps (V & 0x3FFF) >> 5 truncated
		// to 8 bits (asm L13341-13342) and only ever COMPARES it against 0x80 — the level at
		// which LABEL_021E83 (asm L12946) advances the voice's allocator stage — so the map
		// only has to be monotone, not exact. Our EG level code is already the chip's own
		// 8-bit log amplitude, so it goes out shifted into place.
		const voice_t &v = m_voice[latch - 0x0180];
		if (!v.eg_running)
			return 0;
		int lvl = int(v.eg_level + 0.5);
		lvl = std::clamp(lvl, 0, 0xFF);
		return uint16_t(lvl << 5);
	}

	if (latch <= 0x0003)
	{
		// R1 — "active" is the eg_running LATCH, not a level test. It is SET only by the
		// 0x81xx gate (all seven sites: asm L29757, L30213, L30294, L30667, L30891, L31071,
		// L31086) and CLEARED only by 0x7E00 or by genuine silence. It must be a latch
		// because the allocator PRE-ARMS the teardown edge at allocation time
		// (`LDA XBC,292Eh / OR (XBC+WA),DE`, asm L13582-L13584): an "is it loud yet" test
		// would report 0 on the first poll after the gate — while the attack is still
		// ramping — and the firmware would tear the brand-new note straight back down.
		//
		// WHY A HELD NOTE CANNOT BE RECLAIMED BY THIS. The teardown needs a poll that reads
		// the bit as 0 (it is computed from `prev & ~new`, asm L13291-13302). We only report
		// 0 once the voice's own rendered contribution has been below half an output LSB
		// continuously for a full bank-poll period, so on the poll that could fire a
		// teardown the voice is already contributing exactly nothing — the firmware's
		// 0x7E00 can never remove audible sound. While a key is down the EG sits at its
		// programmed sustain level, so the interlock never arms and the voice is
		// structurally unreclaimable, for any hold duration.
		const int bank = latch & 0x03;
		uint16_t bitmap = 0;
		for (int i = 0; i < 16; i++)
		{
			const int vch = bank * 16 + i;
			if (vch < NUM_VOICES && m_voice[vch].eg_running)
				bitmap |= (1u << i);
		}
		return bitmap;
	}

	return 0;
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

// =======================================================================================
// GAP CAL-1 — THE AMPLITUDE ENVELOPE GENERATOR
// =======================================================================================
//
// Registers +0x800 / +0x840 / +0x880 (regs[20]/[21]/[22]) are the three programmed
// segments of the per-voice amplitude EG. Each word is
//
//     (target_level << 8) | (bit7 flag) | rate[6:0]
//
// MEASURED-by-construction: the sole builder LABEL_025A9E (v142 asm L19395-19469) writes
//   slot[+0x3c] = (PEAK  << 8) | 0x7F                      -> +0x800   ATK  / PEAK
//   slot[+0x3e] = (SUST1 << 8) | max(RATE[desc+0x0a], 4)   -> +0x840   DECAY1 / SUST1
//   slot[+0x40] = (SUST2 << 8) | RATE[desc+0x0c]  (or 0)   -> +0x880   DECAY2 / SUST2
// and the alternate path LABEL_025636 (asm L19078-19087) builds +0x800 as
// `(level<<8) | RATETAB_0x011963[desc+0x28]`. The main-CPU Sound-Edit page (main ROM file
// 0x112072) reads `ATK PEAK DECAY1 SUST1 DECAY2 SUST2 RELEASE`, landing 1:1 on those three
// registers. Full derivation: notes/audit/kn5000-eg-calibration.md.
//
// ---------------------------------------------------------------------------------------
// LAW (a)  LEVEL byte -> LINEAR GAIN.  **DERIVED FROM THE ROM, not fitted.**
// ---------------------------------------------------------------------------------------
//
//     gain(L) = 2 ^ ((L - 255) / 16)          i.e. 0.376287 dB per level unit
//
// The evidence is the firmware's OWN level converter. LABEL_0232C7 (asm L15195-15214)
// builds register +0x080 through table 0x010764 (sub-ROM file offset 0x1864), and that
// table is bit-exactly
//        T[i] = round( 128 * log2( 2^(i>>4) * (1 + (i&15)/16) ) )   for 256 of 256 entries
// — a 4-bit-exponent / 4-bit-mantissa float. So an 8-bit level code is a LOG AMPLITUDE at
// exactly 16 counts per octave. Three independent corroborations:
//   * the 9-position maximum-loudness cap table 0x011ADF steps exactly 3.010 dB;
//   * the 8-bit target (16/oct), the 12-bit +0x080 (256/oct) and the 13-bit level readback
//     (512/oct, from `AND 3FFFh; SRL 5` asm L13341-13342) span the SAME 96 dB domain;
//   * the voice manager's 0x80 stage-advance threshold is exactly 8 octaves = -47.79 dB.
//
// THIS REPLACES the fitted pair `2^((L-231)/10)` that shipped until 2026-07-26, which was
// wrong in BOTH constants: K = 10 (0.602 dB/unit) is 1.6x too steep — it implies 153.5 dB
// across a register whose own domain is 96 dB — and REF = 231 saturated the top 25 codes,
// making 26 of the 127 velocities render identically. Measured discrepancies on values the
// firmware actually writes: Piano PEAK 0xE5 -9.78 vs -1.20 dB; Piano SUST1 0x48 -68.86 vs
// -95.73; Piano SUST2 0x40 -71.87 vs -100.54; terminal 0x00 -95.95 vs -139.08. That last
// pair is why "running the EG" looked dangerous: under the OLD constants a held piano's
// own sustain target evaluated to -100 dB. Under the derived law it is -71.9 dB and the
// note sustains, which is what a piano string does.
//
// Level code 0 returns exactly 0 (see device_start): the firmware's voice manager frees a
// channel only when the chip reports it SILENT, so a gain law that never reaches zero
// would deadlock a 64-voice instrument. -95.95 dB vs -inf is inaudible either way.
//
// ---------------------------------------------------------------------------------------
// 2026-08-06 — THE LINEAR-AMPLITUDE CANDIDATE IS FALSIFIED, and the log law is corroborated
// by a table it had not been checked against. Run the A/B yourself with KN5000_EGLAW=lin.
// ---------------------------------------------------------------------------------------
//
// The candidate was gain(L) = L/255, proposed to rescue the ORGAN demo, whose voices are
// programmed +0x840 = 0x727F (SUST1 = level 114 at rate 127) and therefore park at
// 2^(-141/16) = -53.06 dB about 1.9 ms into every note. It does what it was designed to do
// and STILL fails, on the piano gate and on the ROM:
//
//   MEASURED A/B, one binary, 70 s runs, identical note streams in both arms (4714/4714
//   organ and 941/941 piano notelog rows, so the change perturbs no firmware behaviour;
//   with KN5000_EGLAW unset the piano WAV is md5-identical to the log arm, 455697aa..):
//     organ, the 2307 voices whose +0x840 = 0x727F   click fraction 0.999 -> 0.019 (PCM)
//                                                                   0.999 -> 0.015 (sine)
//                        their tail/peak  -49.8 dB -> -6.7 dB, vs the loud class at -2.0 dB
//     PIANO REGRESSION GATE, and this is what kills it:
//                        peak 23048 -> 32768, rms -23.7 -> -10.2 dBFS, clipped-sample
//                        fraction 0.00000 -> 0.00561
//     organ mix clipped-sample fraction 0.00191 -> 0.12373  (12.4 % of samples at the rail)
//   So the organ's voices become audible only by driving the whole instrument into the
//   clipper. Restoring headroom needs a second, purely fitted master trim.
//
//   ROM CORROBORATION OF THE LOG LAW, from a table the derivation above never used.
//   Voice_LevelCap_Lookup (0x011ADF) = 49 49 53 57 61 65 69 73 77 — FADER INDICES, fed
//   through Level_Fader by Voice_Calc_LevelPair_EGA (asm L21601). Level_Fader steps a
//   uniform -2 per index across that whole span, so the nine cap positions are level codes
//   136 128 120 112 104 96 88 80: spaced EXACTLY 8 counts, i.e. exactly 3.010 dB apart
//   under 16 counts/octave. A nine-position loudness cap in exact 3 dB steps is a designed
//   control; under gain = L/255 the same nine positions span 4.6 dB in total and are not.
//   Equally: Level_Fader's uniform -2/index makes the 0..100 parameter LINEAR IN dB at
//   0.75 dB per step (the standard level-parameter taper) under the log law, while under
//   the linear law its top 75 % of travel spans only 10 dB.
//
// WHAT THAT LEAVES. The gap the organ needs closed is 128 level counts (the loud class
// parks at 242, the faint class at 114). Any log-form law closes it only with a slope of
// 6 dB/128 counts = 0.047 dB/count, i.e. 128 counts per octave — eight times shallower than
// the bit-exact 4e4m table at 0x010764 allows. So no re-calibration of THIS law can be the
// fix; either those voices should not reach segment 1, or the loudness they are missing is
// carried by a register the HLE does not read (see +0x080 below).
//
// AND THE PIANO IS NOT A CONTROL FOR THIS LAW, which invalidates the between-demo A/B that
// motivated the candidate. MEASURED: the piano's +0x840 is 0x3A4C — SUST1 = level 58, i.e.
// 21 dB BELOW the organ's 114 — but at rate 76, whose step traverses the EG's 255 counts in
// 12.8 s. Its notes are ended by the group-9 release heuristic at ~77 ms, so 516 of 571
// piano voices never leave segment 1 at all (adv12_word = FFFF) and flush with eg_level
// still at a median of 206. The piano "plays almost perfectly" because its amplitude EG is
// effectively BYPASSED, not because the level law is right.
float kn5000_tonegen_device::eg_level_to_gain(double level) const
{
	int i = int(level * 16.0 + 0.5);
	if (i <= 0) return 0.0f;
	if (i >= EG_GAIN_TABLE) i = EG_GAIN_TABLE - 1;
	return m_eg_gain[i];
}


// ---------------------------------------------------------------------------------------
// LAW (b)  RATE byte -> SEGMENT SPEED.  Structure DERIVED; the two time constants are
//          explicitly CALIBRATED because the seconds are NOT in the ROM.
// ---------------------------------------------------------------------------------------
//
// DERIVED (MEASURED), and these are the parts that matter musically:
//   * rate 0x7F is the FASTEST rate. It is hard-coded as the attack (`OR BC,007fh`,
//     asm L19399) and is the firmware's neutral default word 0xFF7F (asm L21915).
//   * rate 0 means HOLD — the segment does not move. Proved by the clamp asymmetry:
//     DECAY1 is clamp(.,4,127) (asm L19424-19427 and L19304-19307) but DECAY2 is
//     clamp(.,0,127) (asm L19309-19312) and is simply omitted (= 0) when the descriptor's
//     "has DECAY2" bit is clear (asm L19463-19467). A firmware that refuses to put 0 on
//     the segment that must ramp, and defaults to 0 on the segment that must not, is
//     saying 0 = stop. LIVE: +0x880 is xx00 in 197/197 rhythm note-ons.
//   * a LINEAR rate->speed law is FALSIFIED by the register pair the machine actually
//     writes: Piano DECAY1 = rate 76 over 157 level units, Drum DECAY1 = rate 4 over 115.
//     Linear would make the piano's whole decay 13.7x SHORTER than the drum's and only
//     15 % longer than its own attack. The encoding must be exponential, and solving the
//     same two anchors against "attack 2-10 ms, held piano audible 4-10 s" bounds it to
//     3.8 .. 7.7 rate counts per doubling.
//
// NOT DERIVABLE, with a positive argument (notes/audit/kn5000-eg-calibration.md §3.5):
// the firmware never computes an envelope time — it POLLS the chip (LABEL_02219F asm
// L13334-13348) — and an exhaustive scan of every near-geometric u16 run in the sub ROM
// found 11 exponential tables, all LFO/pitch, none indexed by a rate byte. IC303 is
// undumped. So the two constants below are CALIBRATED, not measured, and they are the
// only fitted numbers in this file's envelope path.
//
// THE EXPERIMENT THAT REPLACES THEM (~20 min on Felipe's real KN5000): hold one note on
// PIANO at a fixed velocity and time the attack peak -> -40 dB; repeat on a patch whose
// DECAY1 rate differs strongly (STRINGS / ORGAN), reading the rate back out of +0x840's
// low byte. Then D = (r2-r1) / log2(t1*dL2 / (t2*dL1)) and T127 follows from either point.
// A third rate over-determines it and validates the exponential FORM itself.
double kn5000_tonegen_device::eg_rate_to_step(int rate)
{
	static constexpr double D    = 4.0;      // CALIBRATED — rate counts per doubling of speed
	                                         //   (tight end of the DERIVED 3.8..7.7 bound)
	static constexpr double T127 = 0.0034;   // CALIBRATED — seconds for rate 127 to traverse
	                                         //   the full 255-unit range
	static constexpr double SAMPLE_RATE = 48000.0;

	rate &= 0x7F;
	if (rate == 0)
		return 0.0;                          // HOLD — DERIVED, see above
	// speed = 255 / (T127 * 2^((127-rate)/D))  level units per second
	return 255.0 / (T127 * std::pow(2.0, (127.0 - double(rate)) / D) * SAMPLE_RATE);
}


// Make segment `seg` (0/1/2 = +0x800/+0x840/+0x880) the running one. The EG's CURRENT
// LEVEL is deliberately untouched (rule R3): a segment load is a new (target, rate) pair
// and nothing else, so a ramp always continues from where it actually is. That is what
// makes "the release starts from the HELD level" (commit d3457eb) an emergent property
// rather than a special case.
// ⚠ "DOES THE CHIP LATCH THE THREE SEGMENT WORDS AT THE GATE?" — MEASURED, and the answer
// is NO. The hypothesis was that reading the register at the hop picks up a word that did
// not exist when the note started. The raw bus (tools/kn5000_tgbus_trace.lua) refutes its
// premise outright: +0x840 is rewritten **3 us** after the gate (median 3.0 us, max 4 us,
// in 310/310 organ and 117/117 piano note-ons) and +0x880 6 us after it, while the EG's
// first hop is ~1.9 ms in — 600x later. The words ARE final long before they are read.
// Latching them at the gate would instead freeze segment 1 at its pre-mute placeholder
// 0xFF00 (level 255, rate 0 = HOLD) in 310/310 and 117/117 note-ons, i.e. it would discard
// the entire decay program the firmware writes 3 us later and hold every voice at its
// attack peak. KN5000_EGSEG=gate renders that arm so the regression is a number, not an
// argument; the numbers are in notes/FINDINGS-kn5000-eg-level-law.md.
void kn5000_tonegen_device::load_eg_segment(int ch, int seg)
{
	voice_t &v = m_voice[ch];
	if (seg < 0) seg = 0;
	if (seg > 2) seg = 2;
	const uint16_t w = m_eg_gate_latch ? v.eg_word[seg]
	                                   : v.regs[20 + seg];      // +0x800 / +0x840 / +0x880
	v.eg_seg    = seg;
	v.eg_target = double((w >> 8) & 0xFF);
	v.eg_step   = eg_rate_to_step(w & 0x7F);
}


void kn5000_tonegen_device::update_voice_params(int ch)
{
	voice_t &v = m_voice[ch];

	// ---- STEREO PAN, from +0x180 (regs[6]) bits[6:0] -------------------------------
	//
	// MEASURED end to end (notes/audit/kn5000-output-design.md §1): MIDI CC 0x0A (Pan)
	// -> Voice_CC_Pan (asm L25081) -> LABEL_0288C5 (L23469, store at chan +0x76) ->
	// LABEL_032E1E (L35522), which computes
	//     pan = clamp(patch_pan + (CC10 - 0x40), 0, 0x7F)
	// into each of the part's four tone slots at [+0x23]/[+0x24], and LABEL_0251BA
	// (L18456) / the per-tick LABEL_026F4A (L21568) -> LABEL_02D670 (L30169) ship it to
	// chip register +0x180. The PATCH-side source is partial_block[+0x01] (previously
	// recorded only as "partial flags"), and the firmware's own default word is 0x0040
	// (asm L21912) — which is why voice_t::reset() seeds regs[6] with it.
	//
	// ROM-wide census: the value is strictly 0..0x7F, 692 of 1046 partials sit exactly at
	// 0x40, 252 of 258 mono patches are centred, and 194 of 216 two-partial patches are
	// mirror-paired around it. Live: a held Piano C4's two oscillators carry +0x180 =
	// 0x0000 and 0x007F — hard left and hard right — while their group-8/9/10 words are
	// byte-identical, which is also what falsifies the old "+0x840/+0x880 are the L/R bus
	// gains" reading (they are EG segments 1 and 2; equal high bytes mean "decay to X then
	// hold at X", and the Piano's own 484C / 4000 pair is not even equal).
	//
	// TAPER: linear BALANCE. This is forced, not preferred — 66.2 % of partials sit at
	// centre so centre must keep unity, and the mix already reaches +8.96 dB over full
	// scale in dense passages so no gain may exceed unity. Constant-power normalised to
	// centre gives sqrt(2) at the extremes (violates the second), normalised to the
	// extremes gives 0.707 at centre (violates the first). Balance is the only standard
	// law satisfying both; the shape BETWEEN the anchors is CALIBRATED (IC303's pan
	// attenuator table is a chip internal).
	//
	// WHICH END IS LEFT is INFERRED (strong): the firmware adds CC10 - 0x40 with no
	// inversion and MIDI CC 10 is 0 = left by definition. If the real instrument is the
	// other way round, invert with `pan = 0x7F - pan` — one line. Felipe's ear on the
	// default Piano (whose two layers are hard-panned) is the arbiter.
	const int pan = v.regs[6] & 0x7F;         // bits[15:7] are a separate streamed-voice field
	const double gl = (pan <= 0x40) ? 1.0 : double(0x7F - pan) / double(0x7F - 0x40);
	const double gr = (pan >= 0x40) ? 1.0 : double(pan)       / double(0x40);

	v.volume_l = int16_t(std::lround(gl * 32767.0));
	v.volume_r = int16_t(std::lround(gr * 32767.0));

	// ---- +0x080 AS A PER-VOICE OUTPUT LEVEL (EXPERIMENT, KN5000_LVL080=on) ----------
	//
	// The HLE reads +0x080 (= regs[2]) only as a burst strobe, but Voice_Build_OutputLevel
	// (0x0232C7) builds its low 12 bits through table 0x010764, which is bit-exactly
	// `T[i] = round(128*log2(2^(i>>4) * (1+(i&15)/16)))` doubled — i.e. the field IS a log
	// amplitude at 256 counts per octave, full scale 4084. So the decode needs no inversion:
	//     gain = 2^((field - 4084) / 256)
	// MEASURED spread over the demos: 39 dB (organ) / 26 dB (piano). Rendering it makes
	// EVERYTHING quieter, which is why it is an experiment and not a shipped change — it
	// only becomes a candidate together with the missing gain-staging reference R (see
	// notes/FINDINGS-kn5000-eg-level-law.md).
	if (m_use_level080)
	{
		const int field = v.regs[2] & 0x0FFF;   // bits 15 and 14:12 are the strobe and pan
		v.gain080 = float(std::pow(2.0, (double(field) - 4084.0) / 256.0));
	}

	// ---- EG segment reprogramming (rule R3) ---------------------------------------
	//
	// A write to +0x800/+0x840/+0x880 loads a new (target, rate) for that segment and
	// NOTHING else: it never re-arms the voice, never resets the wave pointer and never
	// resets the EG's current level. If the write lands on the segment that is currently
	// running, the ramp simply re-aims.
	//
	// BIT 7 OF THE LOW BYTE is the one thing here that is NOT decoded, and the
	// conservative treatment of it is load-bearing. MEASURED: every note-on programming
	// path leaves it CLEAR (the rate tables run 0..127, and the attack literal is 0x7F),
	// while the software volume/expression path LABEL_026769 -> LABEL_02682F (asm
	// L20831-20838, `SLA 8,WA; SET 7,WA -> +0x800`) always SETS it. Those software writes
	// are a level COMMAND of undecoded semantics, not a segment program — and taking them
	// as segment targets would be actively wrong: at key-up the firmware ships 0x8B80
	// (level 139 = -43.65 dB), which is LOUDER than the piano's own sustain level 0x48
	// (-68.86 dB), so honouring it would make a released note get LOUDER. That is exactly
	// the defect reported from real-hardware comparison on 2026-07-25. So a bit-7 write
	// is ignored by the EG.
	//
	// The same rule disposes of the pre-reuse "full scale blip" (audit GAP 7) with no
	// special case at all: the pre-reuse pair is +0x840 = 0xFF00 / +0x800 = 0xFF80, and
	// 0xFF00 carries rate 0 = HOLD while 0xFF80 has bit 7 set — so neither moves the EG,
	// and the channel is no longer slammed to full scale 386 us before it is re-gated.
	if (v.eg_running)
		load_eg_segment(ch, v.eg_seg);
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



// Look up the firmware's per-selector absolute-pitch constant C for a +0x040 word.
//
// kn5000_pitch_trim::TABLE is sorted by selector and holds 1444 entries — every
// (class, entry) pair the firmware's own 487 multisample SET descriptors can produce.
// A selector NOT in it is one the traced tone tables never emit (the drawbar / drum-kit
// selection paths are the known candidates, the same ones decode_wave_select() flags as
// `undocumented`); there is no C for it and the caller must say so out loud.
bool kn5000_tonegen_device::firmware_pitch_trim(uint16_t sel, int32_t &c, bool &ambiguous) const
{
	const auto it = std::lower_bound(m_pitch_c.begin(), m_pitch_c.end(), sel,
			[](const pitch_entry &e, uint16_t s) { return e.sel < s; });
	if (it == m_pitch_c.end() || it->sel != sel)
		return false;
	c = int32_t(it->c);
	ambiguous = (it->ambiguous != 0);
	return true;
}


void kn5000_tonegen_device::update_pitch(int ch)
{
	voice_t &v = m_voice[ch];

	// --- Where absolute pitch comes from ---
	//
	// The IC303 is a PCM MULTISAMPLE chip. +0x400 (reg[8]) is an ABSOLUTE log pitch at
	// 0x100 units/semitone, but offset by a constant belonging to the selected chunk (the
	// recording's own tuning trim) — which is why a chromatic run appears to "reset" at every
	// zone boundary, and why the register ALONE cannot give the note.
	//
	// TWO SOURCES for the absolute frame, and they do not overlap:
	//
	//   * a voice with a correlated INPUT EVENT (keybed / USB-MIDI, both routed through
	//     push_keybed_event) takes its note from that event; what the register adds is
	//     `pitch_offset`, the semitones this partial sounds ABOVE that note — its
	//     coarse/fine transpose and its unison detune (resolve_note_group()). An unresolved
	//     voice has offset 0, i.e. exactly the behaviour this device had before.
	//
	//   * a voice with NO input event — demo, rhythm, sequencer — takes its note from the
	//     registers alone, by subtracting the firmware's own per-selector constant C:
	//     `note = (regs[8] - 0x80 - C(regs[1])) / 256`. See the second branch below. Before
	//     that decode existed those voices were placed by one global constant (0x3524),
	//     which MEASURED a median +10.4 semitones of error over the demo.
	//
	// Each voice plays a real IC307 recording whose measured fundamental period is resampled
	// to the target frequency, so pitch is decoupled from the recording's (un-stored) native
	// root. See notes/kn5000-pitch-velocity.md and notes/kn5000-variant-applied.md.

	// ---- the voice's ABSOLUTE musical frequency ---------------------------------------
	// Computed FIRST and unconditionally. The PCM path below is free to give up early
	// (an aperiodic recording, a missing reg[8]) and leave pitch_step at 1.0, but the
	// diagnostic sine oscillator still needs a real frequency in exactly those cases --
	// indeed they are the ones it is most useful for. Nothing below this block changed:
	// pitch_step is still produced by the same arithmetic, in the same branches, with the
	// same early-outs.
	double freq = 0.0;
	double note_f = 0.0;

	if (v.true_note >= 0)
	{
		// Equal temperament, A4 (MIDI 69) = 440 Hz, plus the transpose/detune the +0x400
		// register carries for this partial.
		//
		// ⚠ REGRESSION GATE. This branch — every keybed and USB-MIDI note — is deliberately
		// BYTE-FOR-BYTE what it was before the per-selector decode below was added. The
		// decode serves only voices the device has no input event for.
		note_f = double(v.true_note) + v.pitch_offset;
		freq = 440.0 * std::pow(2.0, (note_f - 69.0) / 12.0);
		v.pitch_anchor = ANCHOR_KEYBED;
	}
	else if (v.regs[8] != 0)
	{
		// ---- VOICES WITH NO CORRELATED INPUT: demo, rhythm, sequencer ------------------
		//
		// +0x400 is an ABSOLUTE log pitch at 0x100 units/semitone, but offset by a constant
		// that belongs to the SELECTED RECORDING:
		//
		//     +0x400 = (note << 8) + 0x80 + C(+0x040) + 2*fine + detune
		//
		// so with C known the note comes straight out of the two registers the chip is
		// given, and nothing else is needed:
		//
		//     note = (regs[8] - 0x80 - C(regs[1])) / 256
		//
		// C is FIRMWARE-DERIVED, not fitted to audio: it is arithmetic on the sub-CPU's own
		// 487 multisample SET descriptors (kn5000_pitch_trim.hxx, generated). MEASURED over
		// 5384 captured demo note-ons: this decode lands on an integer MIDI note 70.4% of
		// the time against a C-permuted null of 15.1 ± 6.9%, and 0.9% for the bare 0x3524
		// constant it replaces — and the residual non-integer part is the traced
		// `2*fine + detune`, all of it under 0.4 semitone, so the NOTE still rounds right.
		// See notes/FINDINGS-kn5000-chunk-root-pitch.md.
		//
		// THE LADDER, best evidence first. Every rung is recorded in v.pitch_anchor and
		// censused per note-on at device_stop — the fallback is never silent.
		int32_t c = 0;
		bool ambiguous = false;
		if (firmware_pitch_trim(v.regs[1], c, ambiguous))
		{
			// 1367 of the 1444 selectors carry exactly one C across every SET, patch and
			// key that reaches them. The other 77 carry more than one; the table gives the
			// KEY-WEIGHTED MODAL value, which is the most probable reading of that selector
			// but can be wrong — for a handful of selectors the candidates sit a whole
			// octave apart (a drawbar footage wave deliberately reused an octave up). They
			// are flagged so the census can report their share separately rather than
			// letting them dilute the single-valued result.
			v.pitch_anchor = ambiguous ? ANCHOR_FIRMWARE_AMBIG : ANCHOR_FIRMWARE;
		}
		else if (v.wave_real && uint32_t(v.wave_chunk) < m_dir[v.wave_bank][v.wave_page].count
				&& m_dir[v.wave_bank][v.wave_page].trim_state[v.wave_chunk] == 1)
		{
			// The firmware tables never emit this selector, but this chunk's trim was
			// PINNED at runtime by an untransposed key press (resolve_note_group) — which
			// is the very same quantity C, learned instead of tabulated. Strictly more
			// information than the constant below.
			//  ⚠ RUN-DEPENDENT: nothing is learned until a keybed/MIDI note has been
			//  played, so during pure demo playback this rung is inert (the census will
			//  read 0) and it cannot contaminate a demo-only measurement.
			c = m_dir[v.wave_bank][v.wave_page].trim[v.wave_chunk];
			v.pitch_anchor = ANCHOR_LEARNED;
		}
		else
		{
			// ⚠ NOT A MEASUREMENT. No C from any source. Keep the historical behaviour:
			// treat reg[8] as a global log pitch anchored so a mid-range value lands near
			// middle C. Correct WITHIN a sample zone and monotonic, but its absolute pitch
			// is wrong by whatever the selected recording's own trim is — MEASURED median
			// +10.4 semitones over the demo. Retained ONLY so such a voice still sounds;
			// the census names the selectors that land here.
			//     note = 60 + (regs[8] - 0x3524)/256  ==  (regs[8] - 0x80 - (-1884))/256
			c = -1884;
			v.pitch_anchor = ANCHOR_CONSTANT;
		}

		// ⚠ pitch_offset is deliberately NOT added here. It is the transpose/detune a
		// partial carries ABOVE its played note, recovered by resolve_note_group() for
		// keybed voices only — and it is already inside regs[8], which is what this branch
		// decodes. Adding it would double-count. resolve_note_group() only ever runs on
		// voices with true_note >= 0, so it is 0 on every voice reaching this branch.
		note_f = (double(int(v.regs[8])) - 128.0 - double(c)) / 256.0;
		freq = 440.0 * std::pow(2.0, (note_f - 69.0) / 12.0);
	}
	else
	{
		v.pitch_anchor = ANCHOR_NONE;
	}
	// freq == 0.0 means this voice carries no pitch information at all. The sine then
	// renders honest silence rather than an invented note; the silence interlock frees the
	// voice normally.
	v.sine_inc = (freq <= 0.0) ? 0u
		: uint32_t(std::llround(std::min(freq, double(STREAM_RATE) / 2.0 - 1.0)
				* 4294967296.0 / double(STREAM_RATE)));

	// ---- PCM resampling ratio (unchanged) ---------------------------------------------
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
	if (v.true_note < 0 && v.regs[8] == 0)
	{
		v.pitch_step = 0x10000;
		return;
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

	LOGMASKED(LOG_VOICE, "tonegen: voice %d note=%d off=%+.3f -> %.3f freq=%.2f step=0x%08X (r1=%04X r8=%04X) anchor=%s\n",
		ch, v.true_note, v.pitch_offset, note_f, freq, v.pitch_step, v.regs[1], v.regs[8],
		anchor_name(v.pitch_anchor));
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

	// No fundamental. A short recording is itself ~one cycle; a long one with no detectable
	// period has none -> 0, and the caller plays it as recorded (pitch_step = 1.0).
	//
	// The bound is 256, not 2048 (changed 2026-08-14). MEASURED: 29 REFERENCED chunks of
	// 608-2016 samples reach this line, and returning N<<16 for them makes update_pitch
	// compute step = freq * N / 48000 -- 8x too fast at C4 for N=1496, worse higher up.
	// That is the "extreme noise" this file already blames on +040 = 0x505B and 0x5046,
	// which are exactly two of them (page 1 entries 0x05B/0x046, 1496 and 1568 samples).
	// Below 256 the opposite holds: page 2's 16-144-sample wavetable chunks really ARE one
	// cycle, and N<<16 is the only correct answer for them -- detect_period's own maxlag is
	// ~N/3, so it cannot report a period equal to N even when that is the truth.
	// Full analysis and the falsified alternative (lowering the 0.5 gate returns the second
	// harmonic on known ground truth) in notes/FINDINGS-ic307-page2.md.
	return (samples <= 256) ? (samples << 16) : 0;
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

	// ---- ROM-INTEGRITY FLAG: is this voice reading a socket we actually HAVE? ----------
	// bank 1 is IC307, the one hardware-rooted dump. Banks 0/2/3 are IC304/305/306, which
	// are UNDUMPED and are filled with a BAD_DUMP copy of IC307 (kn5000.cpp ROM_REGION), so
	// a selection there resolves to a real recording that has NOTHING to do with the sound
	// the instrument asked for. `substituted` covers the same failure from the other side
	// (a socket with no directory of its own, i.e. a truly empty region).
	// This is a statement about the DUMP, not about the decode or the music: it is exactly
	// as true with an empty wave-ROM file as with this one. See m_mute_undumped.
	v.wave_undumped = (s.bank != IC307_BANK) || s.substituted;
	if (v.wave_undumped)
		m_undumped_muted++;   // note-ons that selected a socket we do not have

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

	// R4 — THE GATE IS AN UNCONDITIONAL FULL RE-INITIALISATION. No per-voice playback state
	// survives it: wave pointer to 0, filter to rest, EG back to segment 0, silence interlock
	// cleared. This is what makes voice STEALING clean — a stolen channel is re-initialised,
	// never left ringing — without the HLE having to model the firmware's allocator (which it
	// must not: that is list surgery over sub-CPU RAM at 0x148D + ch*0x27, outside the chip
	// boundary). The EG's current LEVEL is deliberately NOT reset (rule R3): the attack ramps
	// from wherever the channel actually is, which is click-free in both directions.
	v.key_on = true;
	v.key_on_time = machine().time().as_double(); // gate timestamp for release detection
	v.active = true;
	v.eg_running = true;
	v.silent_samples = 0;
	v.wave_offset = 0;
	v.sine_phase = 0;          // diagnostic sine mode: same gate, same re-initialisation
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

	// PITCH-ANCHOR CENSUS, one count per note-on (not per register write), so it is directly
	// comparable with the offline capture analysis. Reported at device_stop; a voice that
	// fell through to the bare 0x3524 constant also has its selector named there.
	if (v.pitch_anchor < ANCHOR_COUNT)
		m_anchor_census[v.pitch_anchor]++;
	if (v.pitch_anchor == ANCHOR_CONSTANT)
		m_anchor_unplaced[v.regs[1]]++;

	// Update pan and the TVF from the current registers, then start the amplitude EG at
	// segment 0. +0x800, +0x180 and +0x100 are all written earlier in the same burst
	// (asm L29736, L29691 and L29619), so they are already final when the gate arrives.
	//
	// +0x840 AND +0x880 ARE NOT, and that is correct rather than a defect to work around.
	// MEASURED on the raw bus (tools/kn5000_tgbus_trace.lua, organ demo, 65 gates): the
	// burst is  ... +0x800 (-2 us) | GATE 0x8100 | +0x840 (+3 us) +0x880 (+6 us) +0x8C0
	// (+10 us) +0x900..+0xA40 (+13..+28 us) | +0x080 end strobe (+31 us).  So every
	// notelog row necessarily snapshots +0x840 at its PRE-MUTE value 0xFF00 — that is an
	// artifact of where the snapshot is taken, not a stale register: the real segment-1
	// word is in regs[21] 3 us later, and load_eg_segment(ch, 1) does not read it until the
	// EG actually leaves segment 0 about 1.8 ms in. There is nothing here to defer.
	// (An earlier pass sized this gap at ~2 ms and proposed deferring the latch; the trace
	// says 3 us.)
	update_voice_params(ch);
	update_timbre(ch);
	// EXPERIMENT ONLY (KN5000_EGSEG=gate): snapshot the three segment words here, which is
	// what "the chip latches at the gate" would mean. Written unconditionally because it is
	// two stores; only load_eg_segment() reads them, and only under the switch.
	v.eg_word[0] = v.regs[20];
	v.eg_word[1] = v.regs[21];
	v.eg_word[2] = v.regs[22];
	load_eg_segment(ch, 0);

	// PER-NOTE-ON CAPTURE (KN5000_NOTELOG). Last, so the row records the finished state.
	notelog_begin(ch);
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


// The diagnostic sine mode's counterpart to read_waveform_sample(): same role in the
// pipeline, same output range, no ROM access. `phase' is Q32 turns; the table is indexed
// by the top 12 bits and the next 16 interpolate, so the residual distortion is far below
// anything that could be mistaken for a rendering glitch.
int32_t kn5000_tonegen_device::sine_sample(uint32_t phase) const
{
	const uint32_t idx  = phase >> 20;
	const int32_t  a    = m_sine_tab[idx];
	const int32_t  b    = m_sine_tab[(idx + 1) & (SINE_TABLE - 1)];
	const int32_t  frac = int32_t((phase >> 4) & 0xFFFF);
	return a + ((b - a) * frac) / 65536;
}


//-----------------------------------------------------------------------
// Sound stream update — mix all active voices into stereo output
//-----------------------------------------------------------------------

void kn5000_tonegen_device::sound_stream_update(sound_stream &stream)
{
	// One full bank-poll period of the firmware's voice manager, in output samples.
	// MEASURED: Audio_Process_Init alternates two paths at 40.69 Hz (24.576 ms) and the
	// manager reads one bank of 16 per pass, so a given voice's bit is inspected every
	// 4 x 24.576 ms = 98.33 ms. See the R2s interlock below.
	static constexpr uint32_t SILENT_HOLDOFF = 4720;   // 98.33 ms at 48 kHz

	// ---- IC311 (uPD6383GF) EFFECTS-DSP SEND/RETURN INSERT ---------------------------
	//
	// EXPERIMENTAL and OFF BY DEFAULT. The gate is read ONCE per stream update, not per
	// sample, so toggling it in the MAME menu takes effect at the next update and never
	// costs anything per sample. With it off, `dsp_on' is false, run_frame() is never
	// called, and the two `wet' accumulators below stay at literal 0 -- so `mix_l + 0'
	// is bit-identical to today's `mix_l'.
	const u8 dspcfg = u8(m_dsp1_enable.read_safe(0));
	const bool dsp_on = m_dsp1.found() && (dspcfg & 1);
	// ---- HLE audible-effect SELECTOR (DSPHLE port) ------------------------------------
	// EXPERIMENTAL, default OFF. The DSPHLE port is a SINGLE-SELECT, not a bitmask: the
	// panel loads exactly one effect at a time, and each insert reads that effect's own
	// decoded C-RAM layout, so only one may run. 1 = parametric EQ, 2 = single delay,
	// 3 = chorus. When 0 the per-sample paths are skipped and the output is byte-identical.
	const u8 dsphle = m_dsp1.found() ? u8(m_dsp_hle.read_safe(0)) : 0;
	// ---- HLE PARAMETRIC-EQ INSERT (audible decoded EQ) --------------------------------
	// The 5-band DF-I biquad cascade (kn5000_dsp_hle.h) filters the mix using RBJ design
	// parameters reconstructed from the effects DSP's decoded C-RAM (see the per-sample
	// block below and N1-EQ-COEFFICIENT-MEMORY). Validated by an in-emulator spectral A/B.
	const bool eq_hle = (dsphle == 1);
	if (eq_hle)
	{
		// The raw C-RAM cells are NOT direct-form biquad coefficients: eq_spectral_ab.py
		// proved no permutation of {cell0..5} -> {b0,b1,b2,a1,a2} yields a valid peaking
		// response (that needs the undecoded x/y-history realization, walled N2). But the
		// DESIGN PARAMETERS are recoverable from the cells, and building textbook RBJ
		// peaking biquads from them is the validated HLE route (dsp/hle/). Per band:
		//   * FREQUENCY  (SOLID, MEASURED, N1'): cell 0x03 == 2*cos w0  ->  w0 = acos(c3/2).
		//     Cross-checked: cell 0x00 == -c3/2 == -cos w0 in every capture, and band 1's
		//     0x03 gives 966 Hz (== N1' band-1 centre).  Universal across bands.
		//   * GAIN       (MEASURED per band): A^2 == 1 + G[band]*(c1-0.5).  Cell base+1 is
		//     EXACTLY 0.5 (0x200000) at 0 dB -- for every band, and under a frequency-only edit
		//     -- and deviates only under a gain edit; so (c1-0.5) is the pure, frequency-
		//     INDEPENDENT gain signal (unlike (c1-c2), which an FC edit would misread as
		//     +31 dB).  Each band's slope G was fit by driving THAT band's gain +12 dB on the
		//     panel and reading its cell (dsp/tools/eq_band_gain_calibrate.py): the slope is
		//     NOT uniform -- it roughly HALVES per band (the gain cell moves ~2x further per dB
		//     as the band centre rises), so a single constant is wrong for bands 1-4.
		//   * Q          (ASSUMED): 2.0.  Q sets bandwidth only; the peak height that the
		//     spectral A/B checks == the designed dB regardless of Q.
		// Coefficients are RBJ (Audio EQ Cookbook), normalised by a0.  Default OFF; validated
		// offline (eq_rbj_reconstruct_ab.py) and by in-emulator spectral A/B at bands 0 and 2
		// (+~11 dB at the band centre, flat elsewhere).  See N1-EQ-COEFFICIENT-MEMORY note.
		constexpr double GAIN_G[5] = { 465.8, 225.8, 114.2, 58.3, 30.5 };  // per-band A^2 slope
		constexpr double QVAL   = 2.0;      // assumed band Q (documented)
		auto q22 = [](uint32_t v) -> double {
			int32_t s = (v & 0x800000) ? int32_t(v) - 0x1000000 : int32_t(v);
			return double(s) / 4194304.0; };
		for (int band = 0; band < 5; band++)
		{
			const uint8_t base = uint8_t(band * 6);
			const u32 r1 = m_dsp1->cram_read(base + 1);
			const u32 r3 = m_dsp1->cram_read(base + 3);
			double c1 = q22(r1);   // gain cell
			double c3 = q22(r3);   // frequency cell
			// m_cram is read at one of two scales that differ by exactly 2x (N1':
			// "operand = C-RAM cell >> 1"). The capture dumps recorded the CELL scale
			// (0x03 = 2*cos w0, gain baseline 0.5); at runtime, when the EQ insert reads
			// m_cram without the LLE having executed (the normal HLE case, DSPCFG off),
			// m_cram holds the firmware-uploaded OPERAND scale -- exactly half (0x03 =
			// cos w0, baseline 0.25). Detect via the frequency cell: all five fixed band
			// centres (673..3219 Hz) have cos w0 in 0.89..0.995, so |c3|<=1 is operand
			// scale (double both cells back to the cell scale the formula is calibrated on);
			// |c3|>1 is already cell scale. MEASURED: runtime c3=0.9954, c1=0.2532 (+12 dB)
			// == exactly half the dump's 1.9908 / 0.50654.
			const double norm = (std::fabs(c3) <= 1.0) ? 2.0 : 1.0;
			c1 *= norm; c3 *= norm;
			const double cosw0 = std::clamp(c3 * 0.5, -0.9995, 0.9995);
			const double asq   = 1.0 + GAIN_G[band] * (c1 - 0.5); // A^2; >1 boost, <1 cut
			if (KN5000_EQHLE_DEBUG)
			{
				static u32 dbgcall = 0; static int dbgn = 0; static bool dbgthis = false;
				if (band == 0) { dbgthis = ((dbgcall++ % 400) == 0 && dbgn < 40); if (dbgthis) dbgn++; }
				if (dbgthis)
					fprintf(stderr, "### EQHLE t=%.2f b%d r1=%06X r3=%06X c1=%.4f c3=%.4f asq=%.3f\n",
							machine().time().as_double(), band, r1, r3, c1, c3, asq);
			}
			// A band is ACTIVE only if its cells are a plausible peaking design: c3 is a
			// real 2*cos w0 (|c3|<=2) and asq is a sane gain (about -17..+34 dB). Zeroed or
			// not-yet-uploaded C-RAM (c1=c3=0 -> asq=-226) or garbage -> unity passthrough,
			// so a missing/idle EQ can never turn into the broadband cut that a raw A=0.1
			// cascade would produce.
			if (std::fabs(c3) > 2.001 || asq < 0.02 || asq > 50.0 ||
			    std::fabs(asq - 1.0) < 1e-4)   // out-of-range / 0 dB / unused -> passthrough
			{
				m_eq_l[band].set_coeffs(1.0, 0.0, 0.0, 0.0, 0.0, 1.0);
				m_eq_r[band].set_coeffs(1.0, 0.0, 0.0, 0.0, 0.0, 1.0);
				continue;
			}
			const double A     = std::sqrt(std::max(asq, 0.01));
			const double w0    = std::acos(cosw0);
			const double alpha = std::sin(w0) / (2.0 * QVAL);
			const double b0 = 1.0 + alpha * A;
			const double b1 = -2.0 * cosw0;
			const double b2 = 1.0 - alpha * A;
			const double a0 = 1.0 + alpha / A;
			const double a1 = -2.0 * cosw0;
			const double a2 = 1.0 - alpha / A;
			m_eq_l[band].set_coeffs(b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0, 1.0);
			m_eq_r[band].set_coeffs(b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0, 1.0);
		}
	}
	// ---- HLE SINGLE-DELAY INSERT: read the pinned params (once per update) -------------
	// EXPERIMENTAL, default OFF (DSPHLE port bit 1). Pinned by intervention (drive one panel
	// param, diff the C-RAM/descriptor dumps -- the EQ method): FEEDBACK L = C-RAM cell 0x00,
	// FEEDBACK R = cell 0x09 (only 0x00 moved when FEEDBACK L was driven), DELAY L length =
	// descriptor cell 0x26 (= 15437 samples = 350 ms at the ROM default, matching the decode).
	// Two scale rules keyed on DSPCFG bit 1 (m_speculative), which is what doubles both banks:
	//   * descriptor: with bit 1 ON the device already wrote the TRUE sample count (R3 x2);
	//     with it OFF the bank holds half, so double it.
	//   * C-RAM feedback: with bit 1 ON cram_read returns the CELL scale (2x); the multiplier
	//     operand (the actual gain) is half that. With bit 1 OFF it is already the operand.
	// MIX is the SINGLE-DELAY internal designed constant ~0.5 (STRONG). HIGH DAMP not yet
	// pinned -> no in-loop damping (repeats keep their tone) until a damp intervention lands.
	const bool dly_hle = (dsphle == 2);
	int    dly_N   = 0;
	double dly_gl  = 0.0, dly_gr = 0.0;
	const double dly_mix = 0.5;
	if (dly_hle)
	{
		auto q22d = [](u32 v) -> double {
			int32_t s = (v & 0x800000) ? int32_t(v) - 0x1000000 : int32_t(v);
			return double(s) / 4194304.0; };
		const bool bit1 = (dspcfg & 2) != 0;
		const u16 draw = m_dsp1->dsc_read(0x26);
		// The descriptor counts samples at the DSP's 44.1 kHz; the delay line runs at the
		// tonegen STREAM_RATE (48 kHz), so convert or the echo lands ~8% early. With DSPCFG
		// bit 1 ON the bank holds the true 44.1k count (R3 x2 applied at write); with it OFF
		// it holds half. Use bit 1 ON (DSPCFG=3) for a correct delay time.
		const double n441 = bit1 ? double(draw) : 2.0 * double(draw);
		dly_N = int(n441 * double(STREAM_RATE) / 44100.0 + 0.5); // 44.1k samples -> stream samples
		dly_N = std::clamp(dly_N, 1, 34999);                     // fit the delay line
		const double fscale = bit1 ? 0.5 : 1.0;                  // cell -> operand (actual gain)
		dly_gl = std::clamp(q22d(m_dsp1->cram_read(0x00)) * fscale, -0.97, 0.97);
		dly_gr = std::clamp(q22d(m_dsp1->cram_read(0x09)) * fscale, -0.97, 0.97);
	}
	// ---- HLE CHORUS INSERT: read the pinned params (once per update) -------------------
	// EXPERIMENTAL, default OFF (DSPHLE == 3). A quadrature LFO-swept delay. Pinned by
	// intervention on CHORUS (TYPEIDX 0): RATE = C-RAM cell 0x00 (the phase increment: it
	// tracked the live D-RAM ramp 114->494 exactly when LFO SPEED was driven), WET GAIN =
	// C-RAM cell 0x09 (moved 0.303->0.505 when the panel DEPTH was driven). Cell 0x02 is a
	// fixed constant 240 = the modulation SWEEP amplitude in 44.1k samples (not panel-
	// driven; the "settled modulation value is constant"). Cell 0x01 = wrap 0x7FFFFF (2^23).
	// LFO rate: f_Hz = inc * 44100 / 2^23 (inc = the applied increment, cell scale 114).
	// The two voices are quadrature (sin/cos) reads of one phase. Base delay not separately
	// pinned -> use the sweep amplitude as the base so the tap stays positive (short chorus).
	// Same DSPCFG-bit-1 scale rule as the delay (cell vs operand half).
	const bool cho_hle = (dsphle == 3);
	double cho_inc = 0.0, cho_depth = 0.0, cho_base = 0.0, cho_wet = 0.0;
	if (cho_hle)
	{
		auto q22c = [](u32 v) -> double {
			int32_t s = (v & 0x800000) ? int32_t(v) - 0x1000000 : int32_t(v);
			return double(s) / 4194304.0; };
		const bool bit1 = (dspcfg & 2) != 0;
		const double cs = bit1 ? 1.0 : 2.0;                       // operand -> cell scale
		const double inc = double(m_dsp1->cram_read(0x00) & 0xffffff) * cs;   // phase incr (cell scale)
		const double f_hz = inc * 44100.0 / 8388608.0;           // 2^23 modulus
		cho_inc   = std::clamp(f_hz, 0.05, 12.0) / double(STREAM_RATE);       // cycles per output sample
		const double sweep44 = double(m_dsp1->cram_read(0x02) & 0xffffff) * cs;   // sweep amp, 44.1k samples
		cho_depth = std::clamp(sweep44, 4.0, 1500.0) * double(STREAM_RATE) / 44100.0;  // -> stream samples
		cho_base  = cho_depth;                                    // keep read tap >= 0 (short chorus)
		cho_wet   = std::clamp(q22c(m_dsp1->cram_read(0x09)) * cs, 0.0, 0.95); // wet gain (panel DEPTH)
	}
	// ---- HLE FLANGER INSERT: read the pinned params (once per update) ------------------
	// EXPERIMENTAL, default OFF (DSPHLE == 4). The chorus topology PLUS a feedback path.
	// Its C-RAM layout DIFFERS from the chorus (probed separately). Pinned by intervention
	// on FLANGER (TYPEIDX 3): RATE = C-RAM cell 0x05 (phase increment; drove 38->418 with
	// LFO SPEED -> f = inc*44100/2^23 = 0.20 Hz at rest), RESONANCE/FEEDBACK = cell 0x00
	// (0.594 cell -> 0.30 operand, the documented flanger feedback; rose with RESONANCE),
	// panel DEPTH = cell 0x08 (0.808->1.0; scales the LFO sweep amplitude). Cell 0x06 = wrap
	// 0x7FFFFF. Same DSPCFG-bit-1 cell/operand scale rule as the chorus/delay. Base + sweep
	// are short (a flanger's whole point); a fixed max sweep is scaled by the DEPTH cell.
	const bool fl_hle = (dsphle == 4);
	double fl_inc = 0.0, fl_depth = 0.0, fl_base = 0.0, fl_fb = 0.0;
	if (fl_hle)
	{
		auto q22f = [](u32 v) -> double {
			int32_t s = (v & 0x800000) ? int32_t(v) - 0x1000000 : int32_t(v);
			return double(s) / 4194304.0; };
		const bool bit1 = (dspcfg & 2) != 0;
		const double cs = bit1 ? 1.0 : 2.0;                        // operand -> cell scale
		const double inc = double(m_dsp1->cram_read(0x05) & 0xffffff) * cs;   // phase incr (cell scale)
		const double f_hz = inc * 44100.0 / 8388608.0;
		fl_inc = std::clamp(f_hz, 0.02, 12.0) / double(STREAM_RATE);
		// DEPTH cell (0..1) scales a max LFO sweep of ~5 ms (240 samples @44.1k), -> stream rate
		const double depth01 = std::clamp(q22f(m_dsp1->cram_read(0x08)) * cs, 0.0, 1.0);
		fl_depth = depth01 * 240.0 * double(STREAM_RATE) / 44100.0;
		fl_base  = 2.0;                                            // very short base (high notches)
		fl_fb    = std::clamp(q22f(m_dsp1->cram_read(0x00)) * cs * 0.5, -0.95, 0.95);  // feedback = operand
	}
	// ---- HLE PHASER INSERT: read the pinned params (once per update) -------------------
	// EXPERIMENTAL, default OFF (DSPHLE == 5). A cascade of first-order all-pass stages whose
	// one shared coefficient is swept by an LFO, with feedback (resonance) -- the classic
	// phaser. Pinned by intervention on PHASER (TYPEIDX 4): RATE = C-RAM cell 0x00 (phase
	// increment; drove 76->456 with LFO SPEED -> 0.40 Hz at rest), MANUAL = cell 0x06 (the
	// all-pass CENTRE coefficient), DEPTH = cell 0x05 (the coefficient sweep amplitude),
	// RESONANCE = cell 0x02 (feedback ~0.3 operand). One shared MANUAL cell => a cascade of
	// identical all-pass stages. Coefficients read at the operand scale (cell/2) like the
	// biquad/feedback; the RATE increment is used at cell scale (the applied P<<1 value).
	const bool ph_hle = (dsphle == 5);
	double ph_inc = 0.0, ph_ac = 0.0, ph_ad = 0.0, ph_fb = 0.0;
	if (ph_hle)
	{
		auto q22p = [](u32 v) -> double {
			int32_t s = (v & 0x800000) ? int32_t(v) - 0x1000000 : int32_t(v);
			return double(s) / 4194304.0; };
		const bool bit1 = (dspcfg & 2) != 0;
		const double cs = bit1 ? 1.0 : 2.0;
		const double inc = double(m_dsp1->cram_read(0x00) & 0xffffff) * cs;
		ph_inc = std::clamp(inc * 44100.0 / 8388608.0, 0.02, 12.0) / double(STREAM_RATE);
		ph_ac  = std::clamp(q22p(m_dsp1->cram_read(0x06)) * cs * 0.5, -0.95, 0.95);  // centre a (operand)
		ph_ad  = std::clamp(q22p(m_dsp1->cram_read(0x05)) * cs * 0.5,  0.0, 0.40);   // sweep amplitude
		ph_fb  = std::clamp(q22p(m_dsp1->cram_read(0x02)) * cs * 0.5, -0.95, 0.95);  // feedback (resonance)
	}
	// ---- HLE ENSEMBLE + VIBRATO INSERTS: read the pinned params (once per update) ------
	// Both are chorus-family (LFO-swept delay), pinned by intervention:
	//   ENSEMBLE (DSPHLE==6, TYPEIDX 5): RATE = cell 0x00 (76 -> 0.40 Hz); panel DEPTH moves
	//     SIX small-integer cells 0x02/0x04/0x06 (L) and 0x09/0x0B/0x0D (R) = the per-voice
	//     tap delays in 44.1k samples (a genuine multi-voice ensemble), scaled by DEPTH.
	//   VIBRATO (DSPHLE==7, TYPEIDX 17): RATE = cell 0x02 (760 -> ~4 Hz, faster as a vibrato
	//     should be); panel DEPTH = cell 0x05 (0.202) scaling the pitch sweep; mix cell 0x0C.
	// Same DSPCFG-bit-1 scale rule; rate increments read at cell scale, coeffs at operand.
	const bool ens_hle = (dsphle == 6);
	const bool vib_hle = (dsphle == 7);
	double ens_inc = 0.0, ens_tap[3] = { 0, 0, 0 };
	double vib_inc = 0.0, vib_depth = 0.0, vib_wet = 0.0;
	if (ens_hle || vib_hle)
	{
		auto q22m = [](u32 v) -> double {
			int32_t s = (v & 0x800000) ? int32_t(v) - 0x1000000 : int32_t(v);
			return double(s) / 4194304.0; };
		const bool bit1 = (dspcfg & 2) != 0;
		const double cs = bit1 ? 1.0 : 2.0;
		const double sr48 = double(STREAM_RATE) / 44100.0;
		if (ens_hle)
		{
			const double inc = double(m_dsp1->cram_read(0x00) & 0xffffff) * cs;
			ens_inc = std::clamp(inc * 44100.0 / 8388608.0, 0.02, 12.0) / double(STREAM_RATE);
			// three per-channel voice tap delays (L cells 0x02/0x04/0x06), in 44.1k samples
			ens_tap[0] = std::clamp(double(m_dsp1->cram_read(0x02) & 0xffffff) * cs, 2.0, 1500.0) * sr48;
			ens_tap[1] = std::clamp(double(m_dsp1->cram_read(0x04) & 0xffffff) * cs, 2.0, 1500.0) * sr48;
			ens_tap[2] = std::clamp(double(m_dsp1->cram_read(0x06) & 0xffffff) * cs, 2.0, 1500.0) * sr48;
		}
		if (vib_hle)
		{
			const double inc = double(m_dsp1->cram_read(0x02) & 0xffffff) * cs;
			vib_inc = std::clamp(inc * 44100.0 / 8388608.0, 0.02, 12.0) / double(STREAM_RATE);
			vib_depth = std::clamp(q22m(m_dsp1->cram_read(0x05)) * cs, 0.0, 1.0) * 240.0 * sr48;  // sweep
			vib_wet   = std::clamp(q22m(m_dsp1->cram_read(0x0C)) * cs, 0.0, 1.0);                  // mix
		}
	}
	// ---- HLE COMBO INSERTS: SINGLE DELAY chained with a modulation effect --------------
	// The combi effects are the union of two sub-effect topologies (delay -> modulation),
	// packed into one C-RAM layout that differs from the standalones, so pinned separately.
	// They reuse the standalone delay/chorus delay lines (only one effect runs at a time).
	//   S.DELAY+CHORUS (DSPHLE==8, TYPEIDX 23): pinned by intervention -- delay FEEDBACK L =
	//     C-RAM cell 0x02, chorus RATE = C-RAM cell 0x00 (114 -> 0.6 Hz, moved with LFO SPEED),
	//     delay length = descriptor 0x26 (~300 ms). The chorus sweep/wet are not separately
	//     pinned in the combo layout -> a modest fixed sweep + a fixed wet are used (the
	//     validated quantities are the delay echo time and the chorus modulation RATE).
	const bool cmb_sdcho = (dsphle == 8);
	int    cmb_dN = 0;
	double cmb_gfb = 0.0, cmb_cinc = 0.0, cmb_csweep = 0.0;
	if (cmb_sdcho)
	{
		auto q22b = [](u32 v) -> double {
			int32_t s = (v & 0x800000) ? int32_t(v) - 0x1000000 : int32_t(v);
			return double(s) / 4194304.0; };
		const bool bit1 = (dspcfg & 2) != 0;
		const double cs = bit1 ? 1.0 : 2.0;
		const double n441 = (bit1 ? 1.0 : 2.0) * double(m_dsp1->dsc_read(0x26));
		cmb_dN = std::clamp(int(n441 * double(STREAM_RATE) / 44100.0 + 0.5), 1, 34999);
		cmb_gfb = std::clamp(q22b(m_dsp1->cram_read(0x02)) * cs * 0.5, -0.95, 0.95);  // delay feedback
		const double inc = double(m_dsp1->cram_read(0x00) & 0xffffff) * cs;           // chorus rate
		cmb_cinc = std::clamp(inc * 44100.0 / 8388608.0, 0.02, 12.0) / double(STREAM_RATE);
		cmb_csweep = 120.0 * double(STREAM_RATE) / 44100.0;   // fixed chorus sweep (not pinned in combo)
	}
	// ---- HLE COMBOS 2: S.DELAY + {FLANGER, VIBRATO, PHASER, S.DELAY} -------------------
	// Each = a delay stage chained with a second block, pinned by intervention (each combo
	// has its OWN layout): +FLANGER (9, TYPEIDX 25) mod RATE=cell 0x00 (0.2 Hz), delay
	// feedback=0x04; +VIBRATO (10, TYPEIDX 26) RATE=cell 0x00 (0.6 Hz), delay feedback=0x04;
	// +PHASER (11, TYPEIDX 27) RATE=cell 0x03 (0.4 Hz), MANUAL=0x0A, DEPTH=0x09, delay
	// feedback=0x00; +S.DELAY (12, TYPEIDX 24) delay1 feedback=0x00, delay2 feedback=0x05.
	// Delay length = descriptor 0x26 for all. Reuse the standalone mod-block delay lines /
	// all-pass stages; +s.delay uses a second long delay line (m_dly2). Second-stage feedback
	// / all-pass coeffs read at operand scale; rates at cell scale (applied increment).
	const int cmb2 = (dsphle >= 9 && dsphle <= 12) ? dsphle : 0;
	int    c2_dN = 0;
	double c2_gfb = 0.0, c2_gfb2 = 0.0, c2_minc = 0.0, c2_ac = 0.0, c2_ad = 0.0;
	if (cmb2)
	{
		auto q22b = [](u32 v) -> double {
			int32_t s = (v & 0x800000) ? int32_t(v) - 0x1000000 : int32_t(v);
			return double(s) / 4194304.0; };
		const bool bit1 = (dspcfg & 2) != 0;
		const double cs = bit1 ? 1.0 : 2.0;
		const double n441 = (bit1 ? 1.0 : 2.0) * double(m_dsp1->dsc_read(0x26));
		c2_dN = std::clamp(int(n441 * double(STREAM_RATE) / 44100.0 + 0.5), 1, 34999);
		auto rate_of = [&](u8 cell) { const double inc = double(m_dsp1->cram_read(cell) & 0xffffff) * cs;
			return std::clamp(inc * 44100.0 / 8388608.0, 0.02, 12.0) / double(STREAM_RATE); };
		auto fb_of = [&](u8 cell) { return std::clamp(q22b(m_dsp1->cram_read(cell)) * cs * 0.5, -0.95, 0.95); };
		if (cmb2 == 9)  { c2_gfb = fb_of(0x04); c2_minc = rate_of(0x00); }                      // +flanger
		if (cmb2 == 10) { c2_gfb = fb_of(0x04); c2_minc = rate_of(0x00); }                      // +vibrato
		if (cmb2 == 11) { c2_gfb = fb_of(0x00); c2_minc = rate_of(0x03);                        // +phaser
			c2_ac = std::clamp(q22b(m_dsp1->cram_read(0x0A)) * cs * 0.5, -0.95, 0.95);          // manual (centre)
			c2_ad = std::clamp(q22b(m_dsp1->cram_read(0x09)) * cs * 0.5,  0.0, 0.40); }          // sweep
		if (cmb2 == 12) { c2_gfb = fb_of(0x00); c2_gfb2 = fb_of(0x05); }                        // +s.delay (two)
	}
	// ---- HLE COMBO: PEQ + S.DELAY (DSPHLE == 13, TYPEIDX 30) ---------------------------
	// A single emphasis peaking band chained into the delay. Pinned by intervention, and it
	// reuses the STANDALONE EQ cell layout exactly: FREQ = cell 0x03 (2cos w0, moved by FC),
	// GAIN = cell 0x01 (moved by G; 0x05 = -2.0 the same EQ structural constant), DELAY
	// FEEDBACK L = cell 0x06, delay length = descriptor 0x26. Reconstruct one RBJ peaking
	// biquad (as the standalone EQ does) onto m_eq_l[0]/m_eq_r[0], with the per-band gain
	// slope picked by the detected centre frequency; the delay stage reuses m_dly.
	const bool peqsd = (dsphle == 13);
	int    pq_dN = 0;
	double pq_gfb = 0.0;
	if (peqsd)
	{
		auto q22e = [](u32 v) -> double {
			int32_t s = (v & 0x800000) ? int32_t(v) - 0x1000000 : int32_t(v);
			return double(s) / 4194304.0; };
		const bool bit1 = (dspcfg & 2) != 0;
		const double cs = bit1 ? 1.0 : 2.0;
		double c1 = q22e(m_dsp1->cram_read(0x01)) * cs;
		double c3 = q22e(m_dsp1->cram_read(0x03)) * cs;
		const double norm = (std::fabs(c3) <= 1.0) ? 2.0 : 1.0;   // operand -> cell scale
		c1 *= norm; c3 *= norm;
		const double cosw0 = std::clamp(c3 * 0.5, -0.9995, 0.9995);
		// per-band gain slope G by nearest decoded band centre (same table as the 5-band EQ)
		const double bc[5] = { 0.9954, 0.99055, 0.98, 0.95595, 0.89665 };
		const double bg[5] = { 465.8, 225.8, 114.2, 58.3, 30.5 };
		double G = bg[4]; double best = 1e9;
		for (int i = 0; i < 5; i++) { const double d = std::fabs(cosw0 - bc[i]); if (d < best) { best = d; G = bg[i]; } }
		const double asq = std::max(1.0 + G * (c1 - 0.5), 0.02);
		const double A = std::sqrt(asq), w0 = std::acos(cosw0), al = std::sin(w0) / 4.0;  // Q=2
		const double b0 = 1.0 + al * A, b1 = -2.0 * cosw0, b2 = 1.0 - al * A;
		const double a0 = 1.0 + al / A, a1 = -2.0 * cosw0, a2 = 1.0 - al / A;
		m_eq_l[0].set_coeffs(b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0, 1.0);
		m_eq_r[0].set_coeffs(b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0, 1.0);
		const double n441 = (bit1 ? 1.0 : 2.0) * double(m_dsp1->dsc_read(0x26));
		pq_dN = std::clamp(int(n441 * double(STREAM_RATE) / 44100.0 + 0.5), 1, 34999);
		pq_gfb = std::clamp(q22e(m_dsp1->cram_read(0x06)) * cs * 0.5, -0.95, 0.95);
	}
	// ---- HLE REVERB INSERT: reconstructed from the decoded reverb C-RAM (DSPHLE == 14) -
	// The unit-1 reverb coefficients are present in C-RAM every frame and are fully decoded
	// (reverb_listing.tsv): input scaling 0x90, damping 0x93, the REVERB-TIME/decay coeff
	// 0x97, diffuser-ladder gains 0x98..0x9C (5) and 0xA1..0xA4 (4), output-tail mix 0xA9.
	// The exact micro-topology is narrowed (comb-family) but not closed, so this is a
	// PREVIEW: the diffusion uses the DECODED ladder gains; the loop feedback tracks the
	// DECODED decay coeff 0x97 (so driving REVERB TIME changes the tail) mapped to a plausible
	// RT60 range -- the absolute RT60 awaits the topology/length decode. Default OFF.
	const bool rv_hle = (dsphle == 14);
	double rv_fb = 0.0, rv_wet = 0.0, rv_apg[2] = { 0.5, 0.5 };
	if (rv_hle)
	{
		auto q22v = [](u32 v) -> double {
			int32_t s = (v & 0x800000) ? int32_t(v) - 0x1000000 : int32_t(v);
			return double(s) / 4194304.0; };
		const bool bit1 = (dspcfg & 2) != 0;
		const double cs = bit1 ? 1.0 : 2.0;
		// decay coeff 0x97 (REVERB TIME) -> a plausible comb feedback 0.6..0.92 that rises with it
		const double decay = std::clamp(q22v(m_dsp1->cram_read(0x97)) * cs, 0.0, 1.0);   // ~0.4 default
		rv_fb = std::clamp(0.55 + 0.6 * decay, 0.55, 0.84);   // bounded for a stable decay
		// damping one-pole from the decoded HIGH-DAMP cell 0x93 (darker tails as it rises)
		const double damp = std::clamp(q22v(m_dsp1->cram_read(0x93)) * cs * 0.5, 0.0, 0.7);
		for (int i = 0; i < 4; i++) { m_rv_d_l[i].set_damping(damp); m_rv_d_r[i].set_damping(damp); }
		// two all-pass diffuser gains from the decoded ladder (operand scale, kept in range)
		rv_apg[0] = std::clamp(q22v(m_dsp1->cram_read(0x98)) * cs * 0.5, 0.3, 0.75);
		rv_apg[1] = std::clamp(q22v(m_dsp1->cram_read(0xA1)) * cs * 0.5, 0.3, 0.75);
		rv_wet = std::clamp(q22v(m_dsp1->cram_read(0xA9)) * cs, 0.15, 0.6);   // output-tail mix
	}
	// ---- HLE DISTORTION INSERT: AGC waveshaper (DSPHLE == 15) --------------------------
	// prog32_distortion.dsm: DRIVE pre-gain (C-RAM 0x00), a class-6 waveshaper nonlinearity,
	// output VOLUME (C-RAM 0x02), plus an AGC/envelope control source (SRC 0x1C). The DRIVE
	// and VOLUME gains are MEASURED from the decoded C-RAM; the clip curve is a labelled
	// SPECULATIVE stand-in (tanh) -- the class-6 table base is an OPEN decode, not undumped
	// (N-DISTORTION-NOT-UNDUMPED-2026-09-12.md). Default OFF.
	const bool dist_hle = (dsphle == 15);
	double dist_drive = 0.0, dist_vol = 0.0;
	if (dist_hle)
	{
		auto q22d = [](u32 v) -> double {
			int32_t s = (v & 0x800000) ? int32_t(v) - 0x1000000 : int32_t(v);
			return double(s) / 4194304.0; };
		const bool bit1 = (dspcfg & 2) != 0;
		const double cs = bit1 ? 1.0 : 2.0;
		const double c0 = std::fabs(q22d(m_dsp1->cram_read(0x00)) * cs);   // DRIVE (measured)
		const double c2 = std::fabs(q22d(m_dsp1->cram_read(0x02)) * cs);   // VOLUME (measured)
		// Map the decoded DRIVE coeff (cell 0x00) to the shaper pre-gain. The AGC normalises the
		// signal toward unity, so this directly sets how hard it hits tanh: DISTORTION (curve A)
		// is the HARDEST clip of the family, so the floor clips aggressively (a near-square tone)
		// and a larger decoded DRIVE pushes it further toward a full square wave.
		dist_drive = std::clamp(4.0 + 9.0 * c0, 4.0, 13.0);
		// VOLUME: the decoded output-level, kept in a sane makeup range.
		dist_vol = std::clamp(0.25 + 0.75 * c2, 0.25, 1.0);
	}
	// ==== HLE EXTRA EFFECTS (DSPHLE 0x10..0x19): refresh decoded params once per update ====
	// Each reconstructs a program's decoded TOPOLOGY driven by its C-RAM cells. Unlike the 15
	// intervention-pinned effects, most panel->cell ROLE mappings here are position-decoded
	// (INFERRED) per the disassembly, so these are labelled PREVIEWS; cells/lengths that ARE
	// measured (LFO/osc rates, multi-tap delay times, gated-reverb line lengths) are used directly.
	auto q22x = [](u32 v) -> double {
		int32_t s = (v & 0x800000) ? int32_t(v) - 0x1000000 : int32_t(v);
		return double(s) / 4194304.0; };
	const bool   x_bit1 = (dspcfg & 2) != 0;
	const double x_cs   = x_bit1 ? 1.0 : 2.0;                 // operand -> cell scale
	const double sr48   = double(STREAM_RATE) / 44100.0;      // 44.1k sample counts -> stream rate
	const double TWO_PI = 6.283185307179586, PI_C = 3.141592653589793;
	auto rate_hz = [&](u8 cell) -> double {                   // LFO/osc rate: inc*44100/2^23
		return double(m_dsp1->cram_read(cell) & 0xffffff) * x_cs * 44100.0 / 8388608.0; };

	// --- EXCITER (0x11, prog35): high band -> tanh (adds upper harmonics) -> +dry. DRIVE=0x00,
	//     +dry mix=0x09 (INFERRED). One-pole LP splits the band; tanh is the speculative shaper.
	const bool exc_hle = (dsphle == 0x11);
	double exc_drive = 0.0, exc_mix = 0.0;
	if (exc_hle)
	{
		exc_drive = std::clamp(3.0 + 24.0 * std::fabs(q22x(m_dsp1->cram_read(0x00)) * x_cs), 3.0, 30.0);
		exc_mix   = std::clamp(0.30 + 0.70 * std::fabs(q22x(m_dsp1->cram_read(0x09)) * x_cs), 0.30, 1.0);
		m_exc_lp_l.set_damping(0.64); m_exc_lp_r.set_damping(0.64);   // ~3.5 kHz band split
	}
	// --- ENHANCER (0x10, prog03): high-shelf emphasis + all-pass phase + the decoded ~350 ms slap
	//     (DELAY L = C-RAM 0x0B = 15435 samp, PROVEN). HIGH MIX=0x09 (INFERRED). Preview.
	const bool enh_hle = (dsphle == 0x10);
	int    enh_dN = 0; double enh_hi = 0.0, enh_wet = 0.0;
	if (enh_hle)
	{
		enh_dN  = std::clamp(int(double(m_dsp1->cram_read(0x0B) & 0xffffff) * x_cs * sr48 + 0.5), 1, 34999);
		enh_hi  = std::clamp(0.5 + 2.0 * std::fabs(q22x(m_dsp1->cram_read(0x09)) * x_cs), 0.5, 3.0);  // HIGH MIX boost
		enh_wet = 0.25;                                           // modest slap blend (DELAY is the anchor)
		m_enh_lp_l.set_damping(0.64); m_enh_lp_r.set_damping(0.64);
		m_enh_ap_l.set_a(0.6); m_enh_ap_r.set_a(0.6);
	}
	// --- AUTO WAH (0x12, prog52): NO LFO -- input envelope sweeps a resonant SVF cutoff. RESONANCE,
	//     MANUAL, SWEEP are SPECULATIVE (not pinned), so fixed musical defaults. Preview.
	const bool wah_hle = (dsphle == 0x12);
	double wah_q = 0.0;
	if (wah_hle) { wah_q = 0.85; }                               // resonance (SVF feedback)
	// --- AUTO PAN (0x13, prog48): quadrature LFO (rate = C-RAM 0x01, MEASURED ~1.2 Hz) pans L/R.
	const bool pan_hle = (dsphle == 0x13);
	double pan_inc = 0.0, pan_depth = 0.0;
	if (pan_hle)
	{
		pan_inc   = std::clamp(rate_hz(0x01), 0.05, 12.0) / double(STREAM_RATE);
		pan_depth = std::clamp(0.4 + 0.6 * std::fabs(q22x(m_dsp1->cram_read(0x00)) * x_cs), 0.4, 1.0);
	}
	// --- RING MODULATOR (0x14, prog54): carrier osc (rate = C-RAM 0x00, MEASURED ~1 kHz) x signal.
	const bool ring_hle = (dsphle == 0x14);
	double ring_inc = 0.0;
	if (ring_hle) { ring_inc = std::clamp(rate_hz(0x00), 20.0, 4000.0) / double(STREAM_RATE); }
	// --- MULTI TAP DELAY (0x15, prog10): 4 taps at the MEASURED host delays 6000/12000/18000/24000
	//     samp @44.1k, each panned; feedback 0x00, HIGH DAMP 0x08, tap gains 0x03..0x06 (INFERRED).
	const bool mtap_hle = (dsphle == 0x15);
	double mtap_fb = 0.0, mtap_g[4] = { 0, 0, 0, 0 }; int mtap_t[4] = { 0, 0, 0, 0 };
	if (mtap_hle)
	{
		const double base[4] = { 6000.0, 12000.0, 18000.0, 24000.0 };
		for (int i = 0; i < 4; i++) mtap_t[i] = std::clamp(int(base[i] * sr48 + 0.5), 1, 27999);
		mtap_fb = std::clamp(std::fabs(q22x(m_dsp1->cram_read(0x00)) * x_cs), 0.0, 0.7);
		for (int i = 0; i < 4; i++)
			mtap_g[i] = std::clamp(0.4 + 0.6 * std::fabs(q22x(m_dsp1->cram_read(u8(0x03 + i))) * x_cs), 0.2, 1.0);
		m_mtap_dmp_l.set_damping(0.35); m_mtap_dmp_r.set_damping(0.35);
	}
	// --- COMPRESSOR (0x16, prog36): square-law detector -> attack/release one-pole -> gain computer.
	//     THRESHOLD/RATIO = 0x04 (gain-computer op0x72), ATTACK/RELEASE = 0x02 smoother (INFERRED).
	const bool comp_hle = (dsphle == 0x16);
	double comp_thr = 0.0, comp_slope = 0.0, comp_atk = 0.0, comp_rel = 0.0, comp_makeup = 0.0;
	if (comp_hle)
	{
		comp_thr   = std::clamp(0.03 + 0.25 * std::fabs(q22x(m_dsp1->cram_read(0x04)) * x_cs), 0.03, 0.5);
		comp_slope = 0.75;                                       // 1 - 1/ratio (RATIO ~4:1); SPECULATIVE
		const double tc = std::clamp(std::fabs(q22x(m_dsp1->cram_read(0x02)) * x_cs), 0.0, 1.0);
		comp_atk   = std::exp(-1.0 / (double(STREAM_RATE) * (0.002 + 0.02 * tc)));   // 2..22 ms
		comp_rel   = std::exp(-1.0 / (double(STREAM_RATE) * 0.15));                  // 150 ms
		comp_makeup = 1.0 / (comp_thr + 0.2);                   // bring level back up after compression
		comp_makeup = std::clamp(comp_makeup, 1.0, 4.0);
	}
	// --- GATED REVERB (0x17, prog08): reverb tank (MEASURED line lengths) + envelope gate on the tail.
	//     HIGH DAMP = 0x07, GATE TIME = 0x15 (INFERRED). Dedicated comb/all-pass lines (own lengths).
	const bool grev_hle = (dsphle == 0x17);
	double grev_fb = 0.0, grev_apg = 0.0; int grev_cd[4] = { 0, 0, 0, 0 }, grev_ad[2] = { 0, 0 };
	double grev_gatethr = 0.0, grev_rel = 0.0;
	if (grev_hle)
	{
		const double cb[4] = { 680.0, 800.0, 1440.0, 1800.0 }, ab[2] = { 458.0, 100.0 };  // measured @44.1k
		for (int i = 0; i < 4; i++) grev_cd[i] = std::clamp(int(cb[i] * sr48 + 0.5), 1, 2099);
		for (int i = 0; i < 2; i++) grev_ad[i] = std::clamp(int(ab[i] * sr48 + 0.5), 1, 559);
		grev_fb  = 0.78;                                         // fixed short-tail feedback (gate cuts it)
		grev_apg = 0.5;
		const double damp = std::clamp(std::fabs(q22x(m_dsp1->cram_read(0x07)) * x_cs) * 0.5, 0.0, 0.7);
		for (int i = 0; i < 4; i++) { m_grev_d_l[i].set_damping(damp); m_grev_d_r[i].set_damping(damp); }
		grev_gatethr = 0.02;                                    // input level that holds the gate open
		// GATE TIME cell 0x15 -> gate release time (how fast the tail is chopped)
		const double gt = std::clamp(std::fabs(q22x(m_dsp1->cram_read(0x15)) * x_cs), 0.0, 1.0);
		grev_rel = std::exp(-1.0 / (double(STREAM_RATE) * (0.02 + 0.15 * gt)));        // 20..170 ms
	}
	// --- MIX UP (0x18, prog56): three LFOs (MEASURED 3.0/5.2/7.4 Hz = cells 0x00/0x02/0x04) modulate
	//     a short (~9 ms) delay; DEPTH = op0x66 0x0A (INFERRED). Rich multi-LFO chorus.
	const bool mix_hle = (dsphle == 0x18);
	double mix_inc[3] = { 0, 0, 0 }, mix_depth = 0.0, mix_base = 0.0, mix_wet = 0.0;
	if (mix_hle)
	{
		mix_inc[0] = std::clamp(rate_hz(0x00), 0.05, 12.0) / double(STREAM_RATE);
		mix_inc[1] = std::clamp(rate_hz(0x02), 0.05, 12.0) / double(STREAM_RATE);
		mix_inc[2] = std::clamp(rate_hz(0x04), 0.05, 12.0) / double(STREAM_RATE);
		mix_depth  = 120.0 * sr48;                              // ~2.7 ms sweep (short chorus)
		mix_base   = 400.0 * sr48;                              // ~9 ms base (the decoded line length)
		mix_wet    = std::clamp(0.3 + 0.6 * std::fabs(q22x(m_dsp1->cram_read(0x0A)) * x_cs), 0.3, 0.9);
	}
	// --- ROTARY SPEAKER (0x19, prog15): crossover (bass/treble) + two Doppler-swept+AM rotors. The
	//     rotor ROTATION RATE is NOT in the program (host-supplied, undecoded), so CANONICAL Leslie
	//     speeds are used (SPECULATIVE); the Doppler delays (7.26/3.63 ms) are MEASURED. DRIVE=0x00.
	const bool rot_hle = (dsphle == 0x19);
	double rot_tinc = 0.0, rot_binc = 0.0, rot_tdep = 0.0, rot_bdep = 0.0; int rot_tbase = 0, rot_bbase = 0;
	if (rot_hle)
	{
		rot_tinc  = 6.8 / double(STREAM_RATE);                  // treble horn ~6.8 Hz (fast), canonical
		rot_binc  = 5.7 / double(STREAM_RATE);                  // bass drum ~5.7 Hz (fast), canonical
		rot_tbase = int(320.0 * sr48 + 0.5);                    // measured Doppler line (7.26 ms)
		rot_bbase = int(320.0 * sr48 + 0.5);
		rot_tdep  = 40.0 * sr48;                                // Doppler depth (vibrato)
		rot_bdep  = 24.0 * sr48;
		m_rot_lp_l.set_damping(0.88); m_rot_lp_r.set_damping(0.88);   // ~800 Hz crossover
	}
	// ==== HLE PEQ+X and AUTO-WAH+DELAY combos (DSPHLE 0x1a..0x22) ======================
	// Each chains a PEQ emphasis biquad with a 2nd block (the disasm pins the PEQ section base:
	// FREQ = base+3, GAIN = base+1). Reuses the single-select members (m_eq[0]=PEQ, m_eq[1]=tone,
	// the delay/chorus/flanger/vibrato lines, the compressor/distortion state). Labelled previews.
	const bool pc_hle   = (dsphle == 0x1a);   // PEQ + chorus (prog71, PEQ base 0x02)
	const bool pf_hle   = (dsphle == 0x1b);   // PEQ + flanger (prog73, base 0x04)
	const bool pv_hle   = (dsphle == 0x1c);   // PEQ + vibrato (prog74, base 0x04)
	const bool pcmp_hle = (dsphle == 0x1d);   // PEQ + compressor (prog75, base 0x00)
	const bool pcd_hle  = (dsphle == 0x1e);   // PEQ + compr + distortion (prog96)
	const bool pco_hle  = (dsphle == 0x1f);   // PEQ + compr + overdrive (prog97)
	const bool pdd_hle  = (dsphle == 0x20);   // PEQ + distortion + delay (prog98)
	const bool pod_hle  = (dsphle == 0x21);   // PEQ + overdrive + delay (prog99)
	const bool awd_hle  = (dsphle == 0x22);   // auto-wah + delay (prog70, no PEQ)
	const bool cmbx = pc_hle || pf_hle || pv_hle || pcmp_hle || pcd_hle || pco_hle || pdd_hle || pod_hle || awd_hle;
	double cx_cinc = 0.0, cx_depth = 0.0, cx_wet = 0.0, cx_fb = 0.0;        // modulation 2nd-block
	double cx_drive = 0.0, cx_vol = 0.0; bool cx_tone = false;             // dist/overdrive 2nd-block
	double cx_thr = 0.0, cx_slope = 0.0, cx_atk = 0.0, cx_rel = 0.0, cx_mk = 0.0;  // compressor
	int    cx_dN = 0; double cx_dfb = 0.0; bool cx_peq = false, cx_wah = false;
	if (cmbx)
	{
		// PEQ emphasis biquad design (same RBJ reconstruction as the standalone PEQ / PEQ+S.DELAY),
		// loaded into m_eq[0]; section base differs per program.
		auto design_peq = [&](u8 base) {
			double c1 = q22x(m_dsp1->cram_read(u8(base + 1))) * x_cs;   // GAIN = base+1
			double c3 = q22x(m_dsp1->cram_read(u8(base + 3))) * x_cs;   // FREQ = base+3 (2cos w0)
			const double nrm = (std::fabs(c3) <= 1.0) ? 2.0 : 1.0; c1 *= nrm; c3 *= nrm;
			const double cw = std::clamp(c3 * 0.5, -0.9995, 0.9995);
			const double bc[5] = { 0.9954, 0.99055, 0.98, 0.95595, 0.89665 };
			const double bg[5] = { 465.8, 225.8, 114.2, 58.3, 30.5 };
			double G = bg[4], best = 1e9;
			for (int i = 0; i < 5; i++) { const double d = std::fabs(cw - bc[i]); if (d < best) { best = d; G = bg[i]; } }
			const double asq = std::max(1.0 + G * (c1 - 0.5), 0.02);
			const double A = std::sqrt(asq), w0 = std::acos(cw), al = std::sin(w0) / 4.0;
			const double b0 = 1.0 + al * A, b1 = -2.0 * cw, b2 = 1.0 - al * A;
			const double a0 = 1.0 + al / A, a1 = -2.0 * cw, a2 = 1.0 - al / A;
			m_eq_l[0].set_coeffs(b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0, 1.0);
			m_eq_r[0].set_coeffs(b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0, 1.0);
		};
		auto comp_setup = [&](u8 thrcell) {
			cx_thr = std::clamp(0.03 + 0.25 * std::fabs(q22x(m_dsp1->cram_read(thrcell)) * x_cs), 0.03, 0.5);
			cx_slope = 0.75;
			cx_atk = std::exp(-1.0 / (double(STREAM_RATE) * 0.006));
			cx_rel = std::exp(-1.0 / (double(STREAM_RATE) * 0.15));
			cx_mk = std::clamp(1.0 / (cx_thr + 0.2), 1.0, 4.0);
		};
		auto delay_setup = [&]() {   // delay from descriptor 0x26 (single-delay convention)
			const double draw = double(m_dsp1->dsc_read(0x26));
			const double n441 = x_bit1 ? draw : 2.0 * draw;
			cx_dN = std::clamp(int(n441 * double(STREAM_RATE) / 44100.0 + 0.5), 1, 34999);
			cx_dfb = 0.35;
		};
		if (pc_hle)   { cx_peq = true; design_peq(0x02); cx_cinc = std::clamp(rate_hz(0x00),0.05,12.0)/double(STREAM_RATE); cx_depth = 200.0*sr48; cx_wet = 0.5; }
		if (pf_hle)   { cx_peq = true; design_peq(0x04); cx_cinc = std::clamp(rate_hz(0x00),0.02,12.0)/double(STREAM_RATE); cx_depth = 120.0*sr48; cx_fb = std::clamp(std::fabs(q22x(m_dsp1->cram_read(0x0E))*x_cs)*0.5,0.0,0.9); }
		if (pv_hle)   { cx_peq = true; design_peq(0x04); cx_cinc = std::clamp(rate_hz(0x00),0.02,12.0)/double(STREAM_RATE); cx_depth = 180.0*sr48; cx_wet = 1.0; }
		if (pcmp_hle) { cx_peq = true; design_peq(0x00); comp_setup(0x0A); }
		if (pcd_hle)  { cx_peq = true; design_peq(0x00); comp_setup(0x0A); cx_drive = std::clamp(4.0+9.0*std::fabs(q22x(m_dsp1->cram_read(0x0F))*x_cs),4.0,13.0); cx_vol = 0.8; }
		if (pco_hle)  { cx_peq = true; design_peq(0x00); comp_setup(0x0A); cx_drive = std::clamp(3.0+7.0*std::fabs(q22x(m_dsp1->cram_read(0x0F))*x_cs),3.0,10.0); cx_vol = 0.8; cx_tone = true; }
		if (pdd_hle)  { cx_peq = true; design_peq(0x00); cx_drive = std::clamp(4.0+9.0*std::fabs(q22x(m_dsp1->cram_read(0x06))*x_cs),4.0,13.0); cx_vol = 0.8; delay_setup(); }
		if (pod_hle)  { cx_peq = true; design_peq(0x00); cx_drive = std::clamp(3.0+7.0*std::fabs(q22x(m_dsp1->cram_read(0x06))*x_cs),3.0,10.0); cx_vol = 0.8; cx_tone = true; delay_setup(); }
		if (awd_hle)  { cx_wah = true; delay_setup(); }
		if (cx_tone) { m_eq_l[1].set_coeffs(0.30,0.30,0.0,-0.40,0.0,1.0); m_eq_r[1].set_coeffs(0.30,0.30,0.0,-0.40,0.0,1.0); }  // ~4 kHz tone LP
	}
	// ---- DIAGNOSTIC RENDER MODE ------------------------------------------------------
	// bit 0 of the driver's "TGMODE" port: 0 = real PCM (normal), 1 = synthesised sine.
	// Read ONCE per update for the same reason as dspcfg above -- it costs nothing per
	// sample, and it can be flipped from the MAME menu mid-note with one update of latency.
	//
	// The two modes differ at EXACTLY ONE `if` below, around the sample-generation seam.
	// Everything else -- voice allocation, note on/off, pitch tracking, the amplitude EG,
	// the TVF, panning, the mixer, the R2s silence interlock -- is literally the same code,
	// which is what makes an A/B meaningful: it separates "the sample data or its
	// addressing is wrong" from "the machinery around it is wrong".
	//
	// ⚠ TWO THINGS THE A/B DOES NOT HOLD CONSTANT, by construction:
	//  * LOUDNESS. The wave ROM is peak-normalised with a ~5.4 dB median crest factor, so a
	//    sine matched to its RMS is ~6 dB below it in peak. See SINE_PEAK in the header.
	//  * VOICE ALLOCATION. Voices whose PCM probe finds silence are skipped entirely in PCM
	//    mode but SOUND in sine mode, so eg_running -- which status_r reports back to the
	//    firmware's voice manager -- can differ. A sine-mode capture is a faithful proxy for
	//    the pitch/envelope/mix machinery, NOT for voice allocation.
	const uint8_t render_mode = m_render_mode.read_safe(0) & 3;
	const bool sine_all = (render_mode == RENDER_SINE);
	// RENDER_SINE_SUB substitutes a sine for exactly the voices RENDER_PCM would mute, so the
	// two arms cover disjoint voice sets and the undumped mute below is skipped in this mode.
	const bool sine_sub = (render_mode == RENDER_SINE_SUB);
	// ---- DIAGNOSTIC PROBE, TGMODE bit 1 (see kn5000.cpp) ------------------------------
	// Is the sine-mode stall a FEEDBACK LOOP through status_r()? The firmware has no
	// note-off input: it generates 0x7E00 (FREE) from the active-voice bitmap this device
	// reports, and that bitmap is the eg_running latch, cleared only by genuine rendered
	// silence. A voice whose EG sustains at a non-zero level and whose source does not
	// decay therefore reports "busy" forever -- status_r()'s own comment calls such a voice
	// "structurally unreclaimable, for any hold duration".
	//
	// This bit breaks the loop at exactly one point: a voice whose LAST EG segment has run
	// to its target is reported silent regardless of what it is still rendering.
	//
	// ⚠ RESULT (2026-08-05): REFUTED. Turning this on does free the stuck voices -- the
	// residual drops from rms 4.3 to 1.2 -- but the demo still does NOT resume. So the
	// status_r() feedback loop is NOT what stalls sine mode. Kept as a knob because it
	// isolates that one mechanism cleanly; it is NOT a fix and must not be used as one.
	// See notes/kn5000-tonegen-sine-mode.md for where the evidence actually points.
	const bool free_on_eg_done = m_eg_free_probe;
	//  ★ bit 1 = the SPECULATIVE ISA (guessed semantics).  See kn5000.cpp DSPCFG.
	if (m_dsp1.found())
		m_dsp1->set_speculative((dspcfg & 2) != 0);
	//  ★★★★ §228: with the insert OFF, the LRCK accumulator and the held return
	//  are cleared ONCE per update, not per sample -- so the default path pays
	//  nothing and cannot inherit a stale wet sample when the gate is switched
	//  on mid-session.
	if (!dsp_on)
	{
		m_dsp1_phase = 0;
		m_dsp1_wet[0] = m_dsp1_wet[1] = 0;
	}

	// Voice census (LOG_CENSUS): counted on the FIRST sample of each update only, so it
	// costs nothing per sample, and reported once per second of machine time.
	if (VERBOSE & LOG_CENSUS)
	{
		int n_active = 0, n_eg = 0, n_key = 0;
		for (int ch = 0; ch < NUM_VOICES; ch++)
		{
			if (m_voice[ch].active)     n_active++;
			if (m_voice[ch].eg_running) n_eg++;
			if (m_voice[ch].key_on)     n_key++;
		}
		const double now = machine().time().as_double();
		if (now - m_census_last >= 1.0)
		{
			m_census_last = now;
			LOGMASKED(LOG_CENSUS, "tonegen census t=%.1f mode=%s active=%d eg_running=%d key_on=%d nopcm=%u\n",
				now, sine_all ? "SINE" : (sine_sub ? "SSUB" : "PCM "), n_active, n_eg, n_key, m_census_nopcm);
			LOGMASKED(LOG_CENSUS, "tonegen clears  keyoffcmd=%u norender=%u nopcm_ilock=%u release=%u interlock=%u\n",
				m_census_clr[0], m_census_clr[1], m_census_clr[2], m_census_clr[3], m_census_clr[4]);
			// Per-voice envelope state for the first few live voices: is the EG actually
			// reaching silence, or was PCM decay hiding a stuck envelope?
			int shown = 0;
			for (int ch = 0; ch < NUM_VOICES && shown < 6; ch++)
			{
				const voice_t &q = m_voice[ch];
				if (!q.active) continue;
				shown++;
				LOGMASKED(LOG_CENSUS, "   v%02d key=%d eg_run=%d eg_lvl=%7.2f tgt=%7.2f step=%9.6f seg=%d env=%3u rel=%u hold=%u sil=%u gain=%.6f\n",
					ch, q.key_on ? 1 : 0, q.eg_running ? 1 : 0, q.eg_level, q.eg_target, q.eg_step,
					q.eg_seg, q.env_level, q.release_counter, q.hold_counter, q.silent_samples,
					double(eg_level_to_gain(q.eg_level)));
			}
			m_census_nopcm = 0;
		}
	}

	for (int s = 0; s < stream.samples(); s++)
	{
		int32_t mix_l = 0;
		int32_t mix_r = 0;
		// Free-running output-sample clock for the KN5000_NOTELOG envelope profile. Kept
		// outside the voice loop so it counts OUTPUT samples, not rendered voice-samples.
		m_nl_sampclock++;

		for (int ch = 0; ch < NUM_VOICES; ch++)
		{
			voice_t &v = m_voice[ch];
			if (!v.active)
			{
				// A voice that is not rendered contributes exactly 0, so its "previous
				// contribution" must be 0 as well -- otherwise re-activation would be
				// scored as a step against a stale value (LOG_GLITCH; compiled out at 0).
				if (VERBOSE & LOG_GLITCH) m_glitch_prev[ch][0] = m_glitch_prev[ch][1] = 0;
				continue;
			}

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
					if (VERBOSE & LOG_CENSUS) m_census_clr[1]++;
					v.eg_running = false;   // a voice that is no longer rendered is silent
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
			// ⚠ THIS PROBE RUNS IN BOTH MODES, ON PURPOSE.
			// It does not ask "what should this voice sound like", it asks "did this voice's
			// wave selection resolve to a real recording at all" -- an ALLOCATION question.
			// Its answer decides whether the voice takes the audible path (and so keeps
			// eg_running set through the silence interlock) or the compact silent path (which
			// clears eg_running), and eg_running is exactly what status_r() reports back to
			// the firmware's voice manager.
			//
			// An earlier revision short-circuited it in sine mode so that every voice sounded.
			// MEASURED consequence: voices that PCM mode retires were held forever, the
			// firmware ran out of channels, and the Feature Demo went silent from ~t=40s while
			// PCM mode played on. Keeping the probe shared makes voice allocation IDENTICAL in
			// the two modes, which is what makes the A/B worth anything.
			//
			// So sine mode still reads these <=64 probe samples. That is a lifecycle decision,
			// not audio: no PCM sample ever reaches the output in sine mode.
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
				if (VERBOSE & LOG_CENSUS) m_census_nopcm++;
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
				// It renders exactly nothing, so it IS silent: run the same interlock the
				// audible path uses, so the firmware can reclaim the channel.
				if (++v.silent_samples >= SILENT_HOLDOFF)
				{ if (VERBOSE & LOG_CENSUS) m_census_clr[2]++; v.eg_running = false; }
				if (!v.active)
					v.eg_running = false;
				if (VERBOSE & LOG_GLITCH) m_glitch_prev[ch][0] = m_glitch_prev[ch][1] = 0;
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
			// ---- THE SEAM: the ONE place the two render modes differ ------------------
			// Everything above and everything below is shared verbatim. Sine mode reads no
			// wave-ROM PCM and uses no wave geometry -- not wave_offset, not the loop, not
			// wave_samples -- only its own Q32 phase, advanced by an increment derived from
			// the same absolute frequency the PCM path resamples to (see update_pitch).
			int32_t sample;
			// LOG_GLITCH bookkeeping: the sample-path state that a click has to be explained
			// by. Compiled out entirely when VERBOSE has bit 7 clear.
			uint32_t g_off_in = 0, g_pos = 0, g_frac = 0;
			int32_t  g_s0 = 0, g_s1 = 0;
			bool     g_wrap = false, g_clamp = false;
			if (VERBOSE & LOG_GLITCH) g_off_in = v.wave_offset;
			// THE seam between the render modes -- one condition, nothing else differs.
			if (sine_all || (sine_sub && v.wave_undumped))
			{
				sample = sine_sample(v.sine_phase);
				v.sine_phase += v.sine_inc;   // free-running; sine_inc == 0 => silence
			}
			else
			{
				uint32_t loop_len = (v.loop_end > v.loop_start) ? (v.loop_end - v.loop_start) : 0;
				uint32_t sample_pos = v.wave_offset >> 16;
				uint32_t frac = v.wave_offset & 0xFFFF;

				if (sample_pos >= v.loop_end)
				{
					if (VERBOSE & LOG_GLITCH) g_wrap = true;
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
					{
						if (VERBOSE & LOG_GLITCH) g_clamp = true;
						sample_pos = v.wave_samples ? v.wave_samples - 1 : 0;
					}
					uint32_t byte_pos = v.wave_start + sample_pos * 2;
					s0 = read_waveform_sample(byte_pos);
					uint32_t next_pos = sample_pos + 1;
					if (loop_len && next_pos >= v.loop_end)
						next_pos = v.loop_start;               // wrap interp to loop start
					if (next_pos >= v.wave_samples)
						next_pos = v.wave_samples ? v.wave_samples - 1 : 0;
					s1 = read_waveform_sample(v.wave_start + next_pos * 2);
				}

				sample = s0 + ((s1 - s0) * int32_t(frac >> 1)) / 32768;
				if (VERBOSE & LOG_GLITCH) { g_s0 = s0; g_s1 = s1; g_pos = sample_pos; g_frac = frac; }
			}

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

			// ---- AMPLITUDE ENVELOPE GENERATOR (GAP CAL-1) --------------------------------
			// Advance the running segment's level toward its target at the segment's own
			// rate, in LEVEL units — which, because the level code is a log amplitude at 16
			// counts per octave, is a ramp that is linear in dB. A segment whose rate is 0
			// HOLDS (derived, see eg_rate_to_step): that is what lets a held piano note park
			// at its sustain level for as long as the key is down instead of decaying away,
			// and it is also why a rhythm patch — SUST1 == SUST2 with DECAY1 pinned at the
			// clamp floor 4 in 197/197 measured rhythm note-ons — is a flat gate that leaves
			// the contour entirely to the sample.
			if (v.eg_step > 0.0)
			{
				if (v.eg_level < v.eg_target)
				{
					v.eg_level += v.eg_step;
					if (v.eg_level >= v.eg_target) { v.eg_level = v.eg_target; if (v.eg_seg < 2) { notelog_seg_advance(ch); load_eg_segment(ch, v.eg_seg + 1); } }
				}
				else if (v.eg_level > v.eg_target)
				{
					v.eg_level -= v.eg_step;
					if (v.eg_level <= v.eg_target) { v.eg_level = v.eg_target; if (v.eg_seg < 2) { notelog_seg_advance(ch); load_eg_segment(ch, v.eg_seg + 1); } }
				}
				else if (v.eg_seg < 2)
				{
					notelog_seg_advance(ch);
					load_eg_segment(ch, v.eg_seg + 1);
				}
			}
			sample = int32_t(float(sample) * eg_level_to_gain(v.eg_level));

			// EXPERIMENT ONLY (KN5000_LVL080=on): the per-voice output level from +0x080.
			// gain080 is 1.0 whenever the switch is off, but the multiply is still skipped
			// so the default arm is bit-identical to the tree before this switch existed.
			if (m_use_level080)
				sample = int32_t(float(sample) * v.gain080);

			// Apply the release fade (GAP LIFE-2 is UNRESOLVED — see the heuristic in
			// data_w()). The EG above holds at whatever level the key-up burst left it, so
			// this fade starts from the HELD level and can only fall: the "release starts
			// from the held level" property of commit d3457eb is now emergent rather than a
			// special case, and the release burst can no longer raise a note's level because
			// its bit-7 word is not taken as a segment target (see update_voice_params).
			if (v.release_counter > 0)
			{
				sample = sample * int32_t(v.release_counter) / 2400;
				v.release_counter--;
				if (v.release_counter == 0 && v.hold_counter == 0)
				{
					v.active = false;
					if (VERBOSE & LOG_CENSUS) m_census_clr[3]++;
					v.eg_running = false;
				}
			}
			else if (!v.key_on)
			{
				// Released AND the release fade has completed: the voice must stay SILENT.
				// hold_counter keeps it "active" ~100ms purely so the firmware's status
				// polling still sees it, but that is a bookkeeping lifetime, NOT audio.
				sample = 0;
			}

			// Stereo. volume_l/volume_r are now PURE PAN gains (+0x180, see
			// update_voice_params); loudness is the EG's job. The balance law has
			// max(gL) = max(gR) = 1.0, so panning can only ever LOWER a per-channel peak.
			int32_t out_l = (sample * int32_t(v.volume_l)) >> 15;
			int32_t out_r = (sample * int32_t(v.volume_r)) >> 15;

			// ---- WE DO NOT HAVE THIS ROM, SO WE DO NOT PLAY IT --------------------------
			// SILENCE HERE MEANS "IC304/305/306 ARE UNDUMPED", NOT "this voice is quiet".
			// The socket is loaded with a BAD_DUMP copy of IC307, so rendering it emits a
			// real KN5000 recording that is not the one this note asked for — audibly wrong
			// material at full level, which is worse than an honest gap. Sine mode is exempt
			// BY DESIGN: it never reads PCM, so it cannot play the wrong recording, and it
			// is where you go to hear these notes' timing, pitch and envelopes.
			//
			// Placed AFTER the pan and BEFORE the mix, so it removes the voice from the
			// OUTPUT and nothing else: the EG, the wave pointer, the release/hold counters
			// and the silence interlock below all run on the unmuted `sample`, so voice
			// allocation and everything status_r() reports back to the firmware are
			// bit-identical to the unmuted arm. A mute that changed the voice lifecycle
			// would make the two arms different experiments, not one experiment with a
			// switch (this is the same rule the has_pcm_data probe above follows).
			if (m_mute_undumped && render_mode == RENDER_PCM && v.wave_undumped)
			{
				out_l = 0;
				out_r = 0;
			}

			mix_l += out_l;
			mix_r += out_r;

			// PER-NOTE-ON CAPTURE (KN5000_NOTELOG): the OUTCOME half of the row. Read-only
			// with respect to everything the render uses, so it cannot change the audio.
			if (m_notelog && m_nl[ch].open)
			{
				notelog_rec_t &r = m_nl[ch];
				const int32_t a = std::max(std::abs(out_l), std::abs(out_r));
				if (a > r.peak) r.peak = a;
				const double m = 0.5 * (double(out_l) + double(out_r));
				r.sumsq += m * m;
				r.nsamp++;
				const uint64_t bkt = (m_nl_sampclock - r.s0) / notelog_rec_t::PROF_SAMPLES;
				if (bkt < uint64_t(notelog_rec_t::NPROF))
				{
					if (a > r.prof[bkt]) r.prof[bkt] = a;
					r.eglvl[bkt] = int16_t(std::lround(v.eg_level));
					r.egseg[bkt] = int8_t(v.eg_seg);
				}
			}

			// ---- LOG_GLITCH: PER-VOICE click attribution (VERBOSE bit 7, default off) ----
			// Counted per CHUNK so the census survives a run of any length; LOG_GLITCHEV adds
			// one line per event with the full state behind it.
			if (VERBOSE & LOG_GLITCH)
			{
				const int32_t dl = out_l - m_glitch_prev[ch][0];
				const int32_t dr = out_r - m_glitch_prev[ch][1];
				if (std::abs(dl) > GLITCH_THRESH || std::abs(dr) > GLITCH_THRESH)
				{
					const uint32_t key = (uint32_t(v.wave_bank) << 20) | (uint32_t(v.wave_page) << 16)
						| (uint32_t(v.wave_chunk) & 0xFFFF);
					glitch_stat_t &g = m_glitch_chunk[key];
					const uint32_t mag = uint32_t(std::max(std::abs(dl), std::abs(dr)));
					g.events++; g.sum_d += mag;
					g.max_d = std::max(g.max_d, mag);
					g.wraps += g_wrap ? 1 : 0;
					g.clamps += g_clamp ? 1 : 0;
					g.samples = v.wave_samples; g.period = v.pitch_period; g.real = v.wave_real;
					g.max_step = std::max(g.max_step, v.pitch_step);
					m_glitch_total++;
					LOGMASKED(LOG_GLITCHEV,
						"glitch t=%.6f v%02d d=%+7d/%+7d out=%7d/%7d smp=%7d real=%d b%dp%dc%-4d "
						"N=%-6u P=%-5u lp=[%u:%u] pos=%-6u off=%08X step=%08X wrap=%d clamp=%d "
						"s0=%6d s1=%6d frac=%5u env=%3d eg=%.2f gain=%.6f vol=%d/%d\n",
						stream.start_time().as_double() + double(s) / double(STREAM_RATE),
						ch, dl, dr, out_l, out_r, sample, v.wave_real ? 1 : 0,
						v.wave_bank, v.wave_page, v.wave_chunk,
						uint32_t(v.wave_samples), uint32_t(v.pitch_period),
						uint32_t(v.loop_start), uint32_t(v.loop_end),
						g_pos, g_off_in, v.pitch_step, g_wrap ? 1 : 0, g_clamp ? 1 : 0,
						g_s0, g_s1, g_frac, int(v.env_level), v.eg_level,
						double(eg_level_to_gain(v.eg_level)), int(v.volume_l), int(v.volume_r));
				}
				m_glitch_prev[ch][0] = out_l;
				m_glitch_prev[ch][1] = out_r;
			}

			// ---- R2s: the calibration-independent SILENCE INTERLOCK ----------------------
			// A voice reports itself silent to the firmware only after its own rendered
			// contribution has stayed below half an output LSB continuously for one full
			// bank-poll period (MEASURED 24.58 ms per bank read x 4 banks = 98.33 ms). The
			// two numbers are not tuning knobs: 0.5 LSB is the output quantum and 98.33 ms
			// is the measured poll period. Together they make the teardown provably
			// inaudible — a teardown can only fire on a poll that read 0, and on that poll
			// the voice was already contributing exactly nothing.
			{
				const int64_t mag = int64_t(std::abs(sample)) * int64_t(std::max(v.volume_l, v.volume_r));
				const bool eg_done = free_on_eg_done && v.eg_seg >= 2 && v.eg_level <= v.eg_target;
				if (mag >= (int64_t(1) << 14) && !eg_done)   // >= 0.5 LSB of the 16-bit output
					v.silent_samples = 0;
				else if (++v.silent_samples >= SILENT_HOLDOFF)
				{ if (VERBOSE & LOG_CENSUS) m_census_clr[4]++; v.eg_running = false; }
			}

			// Advance position
			v.wave_offset += v.pitch_step;
		}

		// ---- OUTPUT HEADROOM ------------------------------------------------------------
		//
		// THE HEADROOM BELONGS UPSTREAM, IN THE LEVEL LAW — not in a global trim. The
		// firmware's own declared per-voice ceiling is 0xFF (LABEL_026FDD / LABEL_023328
		// clamp every level to [0, 0xFF]) while a real patch at a normal velocity programs
		// 0xE5 = 229 (MEASURED, Piano at velocity 100). Real notes therefore sit below the
		// firmware's maximum BY CONSTRUCTION, and that gap is the hardware's per-voice
		// margin — but it only exists in the render because the derived level law refers
		// gain to 255 (see eg_level_to_gain). The old fitted law referred it to 231 and
		// clamped, which threw the margin away by pinning every level >= 231 to full scale;
		// the unconditional 0.70 trim below then paid a flat 3.1 dB on the whole programme
		// to buy it back.
		//
		// So: no trim. MEASURED on a dense captured passage, 95.6 % of non-silent samples
		// are below 0.75 x FS and only 0.564 % exceed full scale — a constant 3.1 dB tax on
		// 100 % of the programme to protect half a percent of it is the wrong trade. What
		// stays is the soft knee, raised to 0.85: below it the sum passes through exactly
		// unchanged (which it never did before), above it a tanh saturates smoothly into
		// (-1,1) with no hard corner and no wrap.
		//
		// The knee is CALIBRATED — IC303's own saturation point is undumped — but it is
		// BOUNDED by the data: it must sit at or above the level a single full-scale voice
		// reaches (so single notes stay linear) and low enough that the over-scale tail is
		// compressed rather than clipped.
		//
		// NOT done, deliberately: no voice-count normalisation and no auto-gain. There is no
		// hardware mechanism for either — 64 voices sum into one stereo pair (one PCM69AU),
		// the 13 global registers are written once at boot, and MAIN VOLUME is analog — and
		// it would make a single note change loudness depending on what else is sounding.
		auto softclip = [](int32_t acc) -> float
		{
			constexpr float K = 0.85f;                 // linear region: |x| <= K is not saturated
			float x = float(acc) / 32768.0f;
			float a = std::fabs(x);
			if (a <= K)
				return x;
			float sgn = (x < 0.0f) ? -1.0f : 1.0f;
			return sgn * (K + (1.0f - K) * std::tanh((a - K) / (1.0f - K)));
		};

		// ---- THE IC311 SEND / RETURN --------------------------------------------------
		//
		// The dry mix above is FINISHED and is NOT touched here. Everything below can only
		// ADD, which is what the board does: the main mix leaves this chip on SDO0 -- a bus
		// IC311 is not on -- while SDOA/SDOB/SDO1 are COPIES that go out to the DSP and come
		// back on SDIA/SDIB. MEASURED, service manual pp. 34/35.
		//
		// It is guaranteed three times over that this cannot break the sound: by the
		// HARDWARE (the insert topology above), by the CODE (mix_l/mix_r are computed above
		// and the wet is a separate accumulator added at the end), and by the GATE (default
		// off => run_frame() is not even called).
		int32_t wet_l = 0;
		int32_t wet_r = 0;

		// ★★★★ §228 -- ONE FRAME PER LRCK PERIOD, NOT PER RENDERED SAMPLE.
		//
		// `lrck_edge' is true on exactly DSP_FRAME_RATE samples of every
		// STREAM_RATE, with no drift: 44100/48000 = 147/160 is exact, so the
		// accumulator is periodic in 160 samples and issues 147 frames.
		//
		// ⚠ THE MEASUREMENT THAT FORCED THIS, from disk and with no run: every
		// archived arm through §227 reports 1 440 001 frames on a
		// `-seconds_to_run 30' vehicle = 48 000.0 frames/s exactly, and its
		// settled window 1 440 000 - 420 000 = 1 020 000 is precisely the
		// 706 040 quiet + 313 960 loud that §S1 splits.  So the old clock was
		// not approximately 48 000, it WAS 48 000.
		// (short-circuits when the insert is off, so the default path pays nothing)
		const bool lrck_edge = dsp_on && [this]()
		{
			m_dsp1_phase += m_dsp1_hz;
			if (m_dsp1_phase < STREAM_RATE) return false;
			m_dsp1_phase -= STREAM_RATE;
			return true;
		}();

		if (lrck_edge)
		{
			// ---- format: the tone generator's mix accumulator is in 16-bit units (the
			// softclip below divides by 32768); IC311's IDB is 24 bits wide and its
			// coefficient format is signed Q0.23. So full scale maps to full scale with a
			// shift of 8, and the return shifts back. That factor is FORCED by the two
			// formats, not chosen.
			auto to24 = [](int32_t v) -> int32_t
			{
				int64_t x = int64_t(v) * 256;
				if (x >  0x7fffff) x =  0x7fffff;
				if (x < -0x800000) x = -0x800000;
				return int32_t(x);
			};

			int32_t di[3][2], dout[3][2];

			// *** EDUCATED GUESS G-2 -- THE SEND LEVELS ARE PLACEHOLDERS ***
			// WHAT IS DECIDED: a UNITY stereo send of the finished dry mix.
			// WHY: the per-voice send levels are genuinely NOT established. They are NOT
			// the per-voice registers +0x8C0 / +0x900..+0x9C0 -- those were checked and are
			// envelope-generator stage words written in (seg0, seg1) pairs (see the
			// register decode above), and the effect-depth controllers CC 0x91/0x97/0x9B
			// never reach this chip at all. Unity is the only level that adds no invented
			// structure.
			// WHAT WOULD SETTLE IT: the 0x130000 register block is the candidate -- a
			// 4-channel x 8-register file written by DSP_Init_Channels (sub-CPU 0x01FC95)
			// and DSP_Write_Channel (0x01FCDE), which is associated with IC311 but is NOT
			// its uC-IF. Tap it in MAME while moving the DSP EFFECT / REVERB depth sliders
			// and diff, the same live-capture method that bound the parameter names.
			// WHAT CHANGES IF IT IS WRONG: the WET BALANCE, and the fact that today
			// changing a part's DSP depth does not change the wet level at all. The
			// mechanism -- a stereo send at LRCK rate, a stereo return added to the mix --
			// stays exactly as it is; only the numbers move. Drop-in replaceable.
			//
			// *** EDUCATED GUESS G-3 -- WHICH PORT EACH BLOCK SERVES IS UNKNOWN ***
			// WHAT IS DECIDED: feed the SAME dry stereo pair to all three wired inputs
			// DI1/DI2/DI3, and sum the wired returns.
			// WHY: all three DI and all three DO are wired on this board (MEASURED), but
			// which of the microcode's two opening blocks (I-RAM 0..11) reads which PORT,
			// and which of the closing words (I-RAM 73..78) writes which port, is not
			// decoded -- the port index is expected to be a small field in those 12 words
			// and that field has not been located.
			// WHAT WOULD SETTLE IT: resolving that field; the prediction on record is that
			// it takes exactly three distinct values across those words.
			// WHAT CHANGES IF IT IS WRONG: which effect unit hears what. With one dry
			// source for everything, a per-port routing error is currently invisible.
			//  ★ §31 2026-07-28: CHARACTERISE THE RAILING INPUT.  The DSP's input audit
			//  peaks at exactly 0x800000 -- to24()'s NEGATIVE CLAMP -- whenever a note
			//  sounds.  to24 multiplies by 256, so it clamps whenever |mix| >= 32768,
			//  and mix_l/mix_r here are PRE-SOFTCLIP and unbounded.  Peak alone cannot
			//  say whether that is a rare transient or a square wave, so count.
			for (int32_t m : { mix_l, mix_r })
			{
				m_insta_n++;
				const int32_t a = std::abs(m);
				if (a > m_insta_peak) m_insta_peak = a;
				if (a >= 32768) m_insta_clip++;
				if (a >= 65536) m_insta_clip2x++;
				m_insta_sum += a;
			}
			const int32_t sl = to24(mix_l);
			const int32_t sr = to24(mix_r);
			for (int port = 0; port < 3; port++)
			{
				di[port][0] = sl;   // DI1/DI2/DI3, LEFT  (LRCK phase 0)
				di[port][1] = sr;   // DI1/DI2/DI3, RIGHT (LRCK phase 1)
			}

			// One LRCK period. Returns false -- with dout already zeroed -- if ANY word of
			// the frame trapped, because a partially-executed effect frame is arbitrary,
			// not "slightly wrong". Today that is every frame.
			const bool kept = m_dsp1->run_frame(di, dout);
			m_dsp1_frames++;
			if (kept)
				m_dsp1_kept++;

			// *** G-4 -- RESOLVED 2026-07-28: DO3 IS THE HD-AE5000 AUDIO EXTENSION ***
			// WHAT IS DECIDED: sum DO1 and DO2 only. Unchanged -- but this is no longer a
			// guess, and the reason has changed from "unknown" to "known and elsewhere".
			// WHY: DO1 -> SDIA and DO2 -> SDIB come back into THIS chip and are therefore
			// part of this chip's mix by construction (MEASURED). DO3 (pin 25, R331) leaves
			// the tone-generator block entirely, and the service manual's schematics say
			// where it goes:
			//
			//     DO3  -> extension connector (HSO) pin 62
			//     LRCK -> extension connector (HSO) pin 61
			//
			// That connector takes exactly one board, the optional HD-AE5000, whose "AE" is
			// Audio Extension: it provides the separate bass/drum outputs (three
			// selections -- Drums L/R, Drums+Bass mixed stereo, Drums L + Bass R). Per
			// Technics' own material those outputs are DIRECT OUT, with no volume control
			// from the KN5000, at the same level as the line outputs.
			// So DO3 is a SEPARATE PHYSICAL OUTPUT, not a component of this mix. Excluding
			// it here is correct, and summing it in would have been wrong -- it would have
			// folded the direct-out feed back into the main L/R.
			// PRIOR GUESS G-4 named "the CN2/CN3 option-connector region (HD-AE5000 side)"
			// as the leading candidate under WHAT WOULD SETTLE IT. That is what it was.
			// SOURCE: KN5000 service manual schematics + HD-AE5000 promotional material,
			// both supplied by Felipe (hardware testimony outranks inference here).
			// See src/devices/bus/technics/kn5000/hdae5000.cpp for the full note.
			// STILL NOT MODELLED: the extension board does not render DO3 -- feature::SOUND
			// is declared unemulated there. When it is, DO3 feeds IT, never this sum.
			//  ★ §228: LATCH the return.  It is held until the next LRCK edge --
			//  a zero-order hold, declared, and confined to the wet path.
			m_dsp1_wet[0] = (dout[0][0] + dout[1][0]) >> 8;   // DO1 L + DO2 L -> SDIA
			m_dsp1_wet[1] = (dout[0][1] + dout[1][1]) >> 8;   // DO1 R + DO2 R -> SDIB

			// KNOWN APPROXIMATION, declared: on real hardware an INSERT-type effect
			// (distortion, compressor) presumably has its dry part REMOVED from the main
			// mix inside this chip, which we cannot model until the send levels above are
			// found. So with the gate on and a working insert effect, the part would be
			// heard dry PLUS wet rather than wet only.
		}

		if (dsp_on)
		{
			wet_l = m_dsp1_wet[0];
			wet_r = m_dsp1_wet[1];
		}

		// ---- HLE EQ INSERT: filter the dry mix through the 5-band cascade ----------------
		// EXPERIMENTAL, default OFF (see eq_hle above). The panel EQ is an INSERT (not a
		// send/return), so it replaces mix_l/mix_r in place with the filtered signal. The
		// biquads run in double at the mix's own normalised scale (int32 / 32768 == the same
		// scale softclip uses). State (z^-1) persists across stream updates in m_eq_l/r.
		if (eq_hle)
		{
			double yl = double(mix_l) / 32768.0;
			double yr = double(mix_r) / 32768.0;
			for (int band = 0; band < 5; band++)
			{
				yl = m_eq_l[band].process_one(yl);
				yr = m_eq_r[band].process_one(yr);
			}
			mix_l = int32_t(yl * 32768.0);
			mix_r = int32_t(yr * 32768.0);
		}

		// ---- HLE SINGLE-DELAY INSERT: feedback delay line, replaces mix in place ----------
		// EXPERIMENTAL, default OFF (see dly_hle above). Standard feedback delay per channel:
		//   tap = line[n-N];  line[n] = s + g*tap;  out = (1-mix)*s + mix*tap.
		// N/g/mix were read once per update above; the line state persists across updates so
		// the echoes ring continuously. Runs AFTER the EQ insert (EQ -> delay), same scale.
		if (dly_hle)
		{
			const double sl = double(mix_l) / 32768.0, sr = double(mix_r) / 32768.0;
			const double tl = m_dly_l.read(double(dly_N)), tr = m_dly_r.read(double(dly_N));
			m_dly_l.write(sl + dly_gl * tl);
			m_dly_r.write(sr + dly_gr * tr);
			mix_l = int32_t(((1.0 - dly_mix) * sl + dly_mix * tl) * 32768.0);
			mix_r = int32_t(((1.0 - dly_mix) * sr + dly_mix * tr) * 32768.0);
		}

		// ---- HLE CHORUS INSERT: quadrature LFO-swept delay, replaces mix in place ---------
		// EXPERIMENTAL, default OFF (dsphle == 3). Per channel: write the dry into a short
		// line, read it back at two taps whose delay is swept by one LFO's sine and cosine
		// (the chip's two quadrature table reads of one phase accumulator), sum the two wet
		// voices, and crossfade with the dry by the decoded wet gain. The shared phase and
		// the line state persist across updates so the sweep is continuous. cho_* were read
		// once per update above; the LFO advances once per output sample here.
		if (cho_hle)
		{
			m_cho_phase += cho_inc;
			if (m_cho_phase >= 1.0) m_cho_phase -= 1.0;
			const double s = std::sin(2.0 * M_PI * m_cho_phase);
			const double c = std::cos(2.0 * M_PI * m_cho_phase);
			const double dA = cho_base + cho_depth * (0.5 + 0.5 * s);
			const double dB = cho_base + cho_depth * (0.5 + 0.5 * c);
			const double sl = double(mix_l) / 32768.0, sr = double(mix_r) / 32768.0;
			m_cho_l.write(sl); m_cho_r.write(sr);
			const double wl = 0.5 * (m_cho_l.read(dA) + m_cho_l.read(dB));
			const double wr = 0.5 * (m_cho_r.read(dA) + m_cho_r.read(dB));
			mix_l = int32_t(((1.0 - cho_wet) * sl + cho_wet * wl) * 32768.0);
			mix_r = int32_t(((1.0 - cho_wet) * sr + cho_wet * wr) * 32768.0);
		}

		// ---- HLE FLANGER INSERT: LFO-swept delay WITH feedback, replaces mix in place -----
		// EXPERIMENTAL, default OFF (dsphle == 4). Like the chorus but a SINGLE swept tap fed
		// back into the line (resonance = the decoded feedback), which is what turns the
		// moving comb into the deep, resonant flange sweep. 50/50 dry/wet for deep notches.
		if (fl_hle)
		{
			m_fl_phase += fl_inc;
			if (m_fl_phase >= 1.0) m_fl_phase -= 1.0;
			const double d = fl_base + fl_depth * (0.5 + 0.5 * std::sin(2.0 * M_PI * m_fl_phase));
			const double sl = double(mix_l) / 32768.0, sr = double(mix_r) / 32768.0;
			const double tl = m_fl_l.read(d), tr = m_fl_r.read(d);
			m_fl_l.write(sl + fl_fb * tl);
			m_fl_r.write(sr + fl_fb * tr);
			mix_l = int32_t((0.5 * sl + 0.5 * tl) * 32768.0);
			mix_r = int32_t((0.5 * sr + 0.5 * tr) * 32768.0);
		}

		// ---- HLE PHASER INSERT: swept all-pass cascade + feedback, replaces mix in place --
		// EXPERIMENTAL, default OFF (dsphle == 5). All PH_STAGES all-pass sections share one
		// coefficient a swept by the LFO around the MANUAL centre; the cascade output is fed
		// back into its input (resonance) and mixed 50/50 with the dry, so the frequency-
		// dependent phase shift creates notches that sweep at the LFO rate.
		if (ph_hle)
		{
			m_ph_phase += ph_inc;
			if (m_ph_phase >= 1.0) m_ph_phase -= 1.0;
			const double a = std::clamp(ph_ac + ph_ad * std::sin(2.0 * M_PI * m_ph_phase), -0.98, 0.98);
			for (int i = 0; i < PH_STAGES; i++) { m_ph_l[i].set_a(a); m_ph_r[i].set_a(a); }
			const double sl = double(mix_l) / 32768.0, sr = double(mix_r) / 32768.0;
			double xl = sl + ph_fb * m_ph_fbl, xr = sr + ph_fb * m_ph_fbr;
			for (int i = 0; i < PH_STAGES; i++) { xl = m_ph_l[i].process_one(xl); xr = m_ph_r[i].process_one(xr); }
			m_ph_fbl = xl; m_ph_fbr = xr;
			mix_l = int32_t((0.5 * sl + 0.5 * xl) * 32768.0);
			mix_r = int32_t((0.5 * sr + 0.5 * xr) * 32768.0);
		}

		// ---- HLE ENSEMBLE INSERT: 3-voice LFO-swept delay, replaces mix in place ----------
		// EXPERIMENTAL, default OFF (dsphle == 6). One line per channel read at three taps
		// (the decoded per-voice delays), each swept by the LFO at a staggered phase so the
		// three detuned voices spread -- the ensemble shimmer. Summed and mixed 50/50 dry.
		if (ens_hle)
		{
			m_ens_phase += ens_inc;
			if (m_ens_phase >= 1.0) m_ens_phase -= 1.0;
			const double sl = double(mix_l) / 32768.0, sr = double(mix_r) / 32768.0;
			m_ens_l.write(sl); m_ens_r.write(sr);
			double wl = 0.0, wr = 0.0;
			for (int v = 0; v < 3; v++)
			{
				const double ph = m_ens_phase + double(v) / 3.0;   // stagger the voices
				const double m = 0.75 + 0.25 * std::sin(2.0 * M_PI * ph);
				wl += m_ens_l.read(std::max(2.0, ens_tap[v] * m));
				wr += m_ens_r.read(std::max(2.0, ens_tap[v] * m));
			}
			wl /= 3.0; wr /= 3.0;
			mix_l = int32_t((0.5 * sl + 0.5 * wl) * 32768.0);
			mix_r = int32_t((0.5 * sr + 0.5 * wr) * 32768.0);
		}

		// ---- HLE VIBRATO INSERT: single LFO-swept delay tap (pitch modulation) ------------
		// EXPERIMENTAL, default OFF (dsphle == 7). A single swept read tap; a mostly-wet mix
		// so the ear hears the pitch wobble (a vibrato), not the dry-vs-wet beating of a
		// chorus. Rate is faster (~4 Hz), matching a vibrato.
		if (vib_hle)
		{
			m_vib_phase += vib_inc;
			if (m_vib_phase >= 1.0) m_vib_phase -= 1.0;
			const double sl = double(mix_l) / 32768.0, sr = double(mix_r) / 32768.0;
			m_vib_l.write(sl); m_vib_r.write(sr);
			const double d = vib_depth + vib_depth * (0.5 + 0.5 * std::sin(2.0 * M_PI * m_vib_phase));
			const double tl = m_vib_l.read(std::max(2.0, d)), tr = m_vib_r.read(std::max(2.0, d));
			const double w = std::max(vib_wet, 0.5);               // vibrato is mostly wet
			mix_l = int32_t(((1.0 - w) * sl + w * tl) * 32768.0);
			mix_r = int32_t(((1.0 - w) * sr + w * tr) * 32768.0);
		}

		// ---- HLE COMBO: S.DELAY + CHORUS (delay stage -> chorus stage) --------------------
		// EXPERIMENTAL, default OFF (dsphle == 8). Reuses the standalone delay line (m_dly)
		// then the chorus line (m_cho); only one effect is ever selected, so sharing is safe.
		// Delay: feedback delay at the combo's descriptor length + feedback cell, 50/50 mix.
		// Chorus: the delay output run through a 2-voice quadrature LFO-swept delay (rate cell
		// 0x00), then mixed with the delayed signal. Proves the combi chaining end to end.
		if (cmb_sdcho)
		{
			const double sl = double(mix_l) / 32768.0, sr = double(mix_r) / 32768.0;
			// stage 1: single delay
			const double dtl = m_dly_l.read(double(cmb_dN)), dtr = m_dly_r.read(double(cmb_dN));
			m_dly_l.write(sl + cmb_gfb * dtl);
			m_dly_r.write(sr + cmb_gfb * dtr);
			const double dl = 0.5 * sl + 0.5 * dtl, dr = 0.5 * sr + 0.5 * dtr;
			// stage 2: chorus on the delayed signal
			m_cho_phase += cmb_cinc;
			if (m_cho_phase >= 1.0) m_cho_phase -= 1.0;
			const double cs2 = std::sin(2.0 * M_PI * m_cho_phase), cc2 = std::cos(2.0 * M_PI * m_cho_phase);
			m_cho_l.write(dl); m_cho_r.write(dr);
			const double wl = 0.5 * (m_cho_l.read(cmb_csweep * (1.0 + 0.5 * cs2)) + m_cho_l.read(cmb_csweep * (1.0 + 0.5 * cc2)));
			const double wr = 0.5 * (m_cho_r.read(cmb_csweep * (1.0 + 0.5 * cs2)) + m_cho_r.read(cmb_csweep * (1.0 + 0.5 * cc2)));
			mix_l = int32_t((0.6 * dl + 0.4 * wl) * 32768.0);
			mix_r = int32_t((0.6 * dr + 0.4 * wr) * 32768.0);
		}

		// ---- HLE COMBOS 2: S.DELAY + {FLANGER, VIBRATO, PHASER, S.DELAY} ------------------
		// EXPERIMENTAL, default OFF (dsphle 9..12). Stage 1 is the shared feedback delay; stage
		// 2 is the second block run on the delayed signal, reusing that block's own state (only
		// one effect is ever selected). Fixed feedback/sweep are used where the combo layout
		// does not separately expose them; the validated per-combo quantity is the mod RATE.
		if (cmb2)
		{
			const double sl = double(mix_l) / 32768.0, sr = double(mix_r) / 32768.0;
			const double dtl = m_dly_l.read(double(c2_dN)), dtr = m_dly_r.read(double(c2_dN));
			m_dly_l.write(sl + c2_gfb * dtl);
			m_dly_r.write(sr + c2_gfb * dtr);
			double dl = 0.5 * sl + 0.5 * dtl, dr = 0.5 * sr + 0.5 * dtr;
			double ol = dl, orr = dr;
			if (cmb2 == 9)             // + FLANGER (feedback delay, resonance ~0.3)
			{
				m_fl_phase += c2_minc; if (m_fl_phase >= 1.0) m_fl_phase -= 1.0;
				const double sw = 200.0 * double(STREAM_RATE) / 44100.0;
				const double d = 2.0 + sw * (0.5 + 0.5 * std::sin(2.0 * M_PI * m_fl_phase));
				const double tl = m_fl_l.read(d), tr = m_fl_r.read(d);
				m_fl_l.write(dl + 0.3 * tl); m_fl_r.write(dr + 0.3 * tr);
				ol = 0.5 * dl + 0.5 * tl; orr = 0.5 * dr + 0.5 * tr;
			}
			else if (cmb2 == 10)       // + VIBRATO (single swept tap, mostly wet)
			{
				m_vib_phase += c2_minc; if (m_vib_phase >= 1.0) m_vib_phase -= 1.0;
				const double sw = 120.0 * double(STREAM_RATE) / 44100.0;
				const double d = sw + sw * (0.5 + 0.5 * std::sin(2.0 * M_PI * m_vib_phase));
				m_vib_l.write(dl); m_vib_r.write(dr);
				ol = 0.4 * dl + 0.6 * m_vib_l.read(d); orr = 0.4 * dr + 0.6 * m_vib_r.read(d);
			}
			else if (cmb2 == 11)       // + PHASER (swept all-pass cascade + feedback)
			{
				m_ph_phase += c2_minc; if (m_ph_phase >= 1.0) m_ph_phase -= 1.0;
				const double a = std::clamp(c2_ac + c2_ad * std::sin(2.0 * M_PI * m_ph_phase), -0.98, 0.98);
				for (int i = 0; i < PH_STAGES; i++) { m_ph_l[i].set_a(a); m_ph_r[i].set_a(a); }
				double xl = dl + 0.3 * m_ph_fbl, xr = dr + 0.3 * m_ph_fbr;
				for (int i = 0; i < PH_STAGES; i++) { xl = m_ph_l[i].process_one(xl); xr = m_ph_r[i].process_one(xr); }
				m_ph_fbl = xl; m_ph_fbr = xr;
				ol = 0.5 * dl + 0.5 * xl; orr = 0.5 * dr + 0.5 * xr;
			}
			else if (cmb2 == 12)       // + S.DELAY (a second feedback delay in series)
			{
				const double t2l = m_dly2_l.read(double(c2_dN)), t2r = m_dly2_r.read(double(c2_dN));
				m_dly2_l.write(dl + c2_gfb2 * t2l);
				m_dly2_r.write(dr + c2_gfb2 * t2r);
				ol = 0.5 * dl + 0.5 * t2l; orr = 0.5 * dr + 0.5 * t2r;
			}
			mix_l = int32_t(ol * 32768.0);
			mix_r = int32_t(orr * 32768.0);
		}

		// ---- HLE COMBO: PEQ + S.DELAY (emphasis biquad -> feedback delay) -----------------
		// EXPERIMENTAL, default OFF (dsphle == 13). Stage 1 = the single emphasis peaking band
		// (reconstructed onto m_eq_l[0]), stage 2 = the feedback delay (reusing m_dly). So the
		// delayed signal carries the EQ emphasis, and the echoes repeat the emphasised tone.
		if (peqsd)
		{
			const double sl = double(mix_l) / 32768.0, sr = double(mix_r) / 32768.0;
			const double el = m_eq_l[0].process_one(sl), er = m_eq_r[0].process_one(sr);
			const double dtl = m_dly_l.read(double(pq_dN)), dtr = m_dly_r.read(double(pq_dN));
			m_dly_l.write(el + pq_gfb * dtl);
			m_dly_r.write(er + pq_gfb * dtr);
			mix_l = int32_t((0.5 * el + 0.5 * dtl) * 32768.0);
			mix_r = int32_t((0.5 * er + 0.5 * dtr) * 32768.0);
		}

		// ---- HLE REVERB INSERT: four PARALLEL combs -> two all-pass diffusers -------------
		// EXPERIMENTAL, default OFF (dsphle == 14). A reconstruction from the DECODED reverb
		// coefficients (see refresh above). Four damped comb filters IN PARALLEL (Freeverb
		// form) give a stable decaying tail -- feedback tracks the decoded REVERB-TIME coeff
		// 0x97; the two Schroeder all-pass stages (decoded diffuser gains) smear it. Parallel
		// (not series) to stay unconditionally stable; the chip's exact comb-family topology
		// is the open decode, so this is a PREVIEW, not a topology claim. Decoded mix 0xA9.
		if (rv_hle)
		{
			const int CD_L[4] = { 1557, 1617, 1693, 1781 }, CD_R[4] = { 1579, 1639, 1711, 1801 };
			const int AD_L[2] = { 556, 225 }, AD_R[2] = { 579, 241 };
			const double sl = double(mix_l) / 32768.0, sr = double(mix_r) / 32768.0;
			// small input gain into the comb bank so the combs' recirculation gain 1/(1-fb)
			// does not blow the level up (Freeverb's fixed-gain trick)
			const double il = 1.2 * m_rv_pre_l.read(1800.0), ir = 1.2 * m_rv_pre_r.read(1800.0);
			m_rv_pre_l.write(sl); m_rv_pre_r.write(sr);
			double xl = 0.0, xr = 0.0;
			for (int c = 0; c < 4; c++)   // parallel comb bank (each recirculates the input)
			{
				const double tl = m_rv_c_l[c].read(double(CD_L[c])), tr = m_rv_c_r[c].read(double(CD_R[c]));
				m_rv_c_l[c].write(il + rv_fb * m_rv_d_l[c].process_one(tl));
				m_rv_c_r[c].write(ir + rv_fb * m_rv_d_r[c].process_one(tr));
				xl += tl; xr += tr;
			}
			for (int a = 0; a < 2; a++)   // unity-gain Schroeder all-pass diffusers
			{
				const double dl = m_rv_a_l[a].read(double(AD_L[a])), dr = m_rv_a_r[a].read(double(AD_R[a]));
				const double yl = -rv_apg[a] * xl + dl, yr = -rv_apg[a] * xr + dr;
				m_rv_a_l[a].write(xl + rv_apg[a] * yl);
				m_rv_a_r[a].write(xr + rv_apg[a] * yr);
				xl = yl; xr = yr;
			}
			mix_l = int32_t(((1.0 - rv_wet) * sl + rv_wet * xl) * 32768.0);
			mix_r = int32_t(((1.0 - rv_wet) * sr + rv_wet * xr) * 32768.0);
		}

		// ---- HLE DISTORTION INSERT: AGC waveshaper, replaces mix in place -----------------
		// EXPERIMENTAL, default OFF (dsphle == 15). DRIVE pre-gain and VOLUME are MEASURED from
		// the decoded C-RAM (see refresh above); the clip curve is a labelled SPECULATIVE tanh
		// stand-in (the class-6 table base is an open decode, NOT undumped). A slow peak-envelope
		// follower per channel gives the AGC (SRC 0x1C in the program): it normalises the pre-gain
		// so the shaper compresses/sustains rather than only railing, which is what "AGC waveshaper"
		// means. Harmonic generation from the tanh is the validating A/B.
		if (dist_hle)
		{
			const double sl = double(mix_l) / 32768.0, sr = double(mix_r) / 32768.0;
			// AGC: a slow peak-envelope follower NORMALISES the signal to a roughly constant
			// level before the shaper (this is what an "AGC waveshaper" does -- it is why the
			// effect sustains and clips consistently regardless of how loud the note is). A
			// small floor keeps true silence silent (no noise pumping).
			m_dist_env_l = std::max(std::fabs(sl), m_dist_env_l * 0.9993);
			m_dist_env_r = std::max(std::fabs(sr), m_dist_env_r * 0.9993);
			const double norm_l = sl / (m_dist_env_l + 0.02);   // peak ~1 during a sustained note
			const double norm_r = sr / (m_dist_env_r + 0.02);
			// DRIVE (decoded) sets how hard the normalised signal hits the shaper; tanh is the
			// labelled SPECULATIVE clip curve. VOLUME (decoded) is the output makeup gain.
			const double wl = std::tanh(norm_l * dist_drive) * dist_vol;
			const double wr = std::tanh(norm_r * dist_drive) * dist_vol;
			mix_l = int32_t(std::clamp(wl, -1.0, 1.0) * 32767.0);
			mix_r = int32_t(std::clamp(wr, -1.0, 1.0) * 32767.0);
		}
		// ==== HLE EXTRA EFFECTS inserts (DSPHLE 0x10..0x19): reconstruct each decoded topology ====
		// Default OFF; labelled previews (see the refresh blocks above for the decode/grading).
		if (exc_hle)   // EXCITER: high band -> tanh (upper harmonics) -> added to the dry signal
		{
			const double xl = double(mix_l) / 32768.0, xr = double(mix_r) / 32768.0;
			const double hl = xl - m_exc_lp_l.process_one(xl), hr = xr - m_exc_lp_r.process_one(xr);
			const double yl = xl + exc_mix * std::tanh(hl * exc_drive);
			const double yr = xr + exc_mix * std::tanh(hr * exc_drive);
			mix_l = int32_t(std::clamp(yl, -1.0, 1.0) * 32767.0);
			mix_r = int32_t(std::clamp(yr, -1.0, 1.0) * 32767.0);
		}
		if (enh_hle)   // ENHANCER: high-shelf emphasis + all-pass phase + decoded ~350 ms slap
		{
			const double xl = double(mix_l) / 32768.0, xr = double(mix_r) / 32768.0;
			const double ehl = xl + (enh_hi - 1.0) * (xl - m_enh_lp_l.process_one(xl));
			const double ehr = xr + (enh_hi - 1.0) * (xr - m_enh_lp_r.process_one(xr));
			const double phl = m_enh_ap_l.process_one(ehl), phr = m_enh_ap_r.process_one(ehr);
			const double dl = m_enh_l.read(double(enh_dN)), dr = m_enh_r.read(double(enh_dN));
			m_enh_l.write(phl); m_enh_r.write(phr);
			mix_l = int32_t(std::clamp(phl + enh_wet * dl, -1.0, 1.0) * 32767.0);
			mix_r = int32_t(std::clamp(phr + enh_wet * dr, -1.0, 1.0) * 32767.0);
		}
		if (wah_hle)   // AUTO WAH: input envelope sweeps a resonant state-variable filter cutoff
		{
			const double xl = double(mix_l) / 32768.0, xr = double(mix_r) / 32768.0;
			m_wah_env_l = std::max(std::fabs(xl), m_wah_env_l * 0.9995);
			m_wah_env_r = std::max(std::fabs(xr), m_wah_env_r * 0.9995);
			const double fcl = 300.0 + std::clamp(m_wah_env_l, 0.0, 1.0) * 3500.0;
			const double fcr = 300.0 + std::clamp(m_wah_env_r, 0.0, 1.0) * 3500.0;
			const double fl = 2.0 * std::sin(PI_C * std::min(fcl, 0.45 * STREAM_RATE) / double(STREAM_RATE));
			const double fr = 2.0 * std::sin(PI_C * std::min(fcr, 0.45 * STREAM_RATE) / double(STREAM_RATE));
			const double dmp = 1.0 - wah_q;
			m_wah_lp_l += fl * m_wah_bp_l; const double hpl = xl - m_wah_lp_l - dmp * m_wah_bp_l; m_wah_bp_l += fl * hpl;
			m_wah_lp_r += fr * m_wah_bp_r; const double hpr = xr - m_wah_lp_r - dmp * m_wah_bp_r; m_wah_bp_r += fr * hpr;
			mix_l = int32_t(std::clamp(m_wah_bp_l, -1.0, 1.0) * 32767.0);
			mix_r = int32_t(std::clamp(m_wah_bp_r, -1.0, 1.0) * 32767.0);
		}
		if (pan_hle)   // AUTO PAN: quadrature LFO pans L/R in antiphase
		{
			const double xl = double(mix_l) / 32768.0, xr = double(mix_r) / 32768.0;
			const double s = std::sin(TWO_PI * m_pan_phase);
			m_pan_phase += pan_inc; if (m_pan_phase >= 1.0) m_pan_phase -= 1.0;
			const double gl = 1.0 - pan_depth * 0.5 * (1.0 - s), gr = 1.0 - pan_depth * 0.5 * (1.0 + s);
			mix_l = int32_t(std::clamp(xl * gl, -1.0, 1.0) * 32767.0);
			mix_r = int32_t(std::clamp(xr * gr, -1.0, 1.0) * 32767.0);
		}
		if (ring_hle)  // RING MODULATOR: multiply by a carrier oscillator (~1 kHz) -> sidebands
		{
			const double xl = double(mix_l) / 32768.0, xr = double(mix_r) / 32768.0;
			const double c = std::sin(TWO_PI * m_ring_phase);
			m_ring_phase += ring_inc; if (m_ring_phase >= 1.0) m_ring_phase -= 1.0;
			mix_l = int32_t(std::clamp(xl * c, -1.0, 1.0) * 32767.0);
			mix_r = int32_t(std::clamp(xr * c, -1.0, 1.0) * 32767.0);
		}
		if (mtap_hle)  // MULTI TAP DELAY: 4 taps at the measured 136/272/408/544 ms, alternately panned
		{
			const double xl = double(mix_l) / 32768.0, xr = double(mix_r) / 32768.0;
			double sl = 0.0, sr = 0.0;
			for (int i = 0; i < 4; i++)
			{
				const double t = m_mtap_l.read(double(mtap_t[i])), u = m_mtap_r.read(double(mtap_t[i]));
				const double panl = (i & 1) ? 0.4 : 1.0, panr = (i & 1) ? 1.0 : 0.4;   // alternate L/R
				sl += mtap_g[i] * panl * t; sr += mtap_g[i] * panr * u;
			}
			m_mtap_l.write(xl + mtap_fb * m_mtap_dmp_l.process_one(m_mtap_l.read(double(mtap_t[3]))));
			m_mtap_r.write(xr + mtap_fb * m_mtap_dmp_r.process_one(m_mtap_r.read(double(mtap_t[3]))));
			mix_l = int32_t(std::clamp(xl + 0.5 * sl, -1.0, 1.0) * 32767.0);
			mix_r = int32_t(std::clamp(xr + 0.5 * sr, -1.0, 1.0) * 32767.0);
		}
		if (comp_hle)  // COMPRESSOR: square-law detector -> attack/release smoother -> gain computer
		{
			const double xl = double(mix_l) / 32768.0, xr = double(mix_r) / 32768.0;
			const double rl = xl * xl, rr = xr * xr;
			const double cl = (rl > m_comp_env_l) ? comp_atk : comp_rel;
			m_comp_env_l = rl + cl * (m_comp_env_l - rl);
			const double cr = (rr > m_comp_env_r) ? comp_atk : comp_rel;
			m_comp_env_r = rr + cr * (m_comp_env_r - rr);
			auto gain = [&](double e2) -> double {
				const double e = std::sqrt(std::max(e2, 0.0));
				if (e <= comp_thr || e < 1e-6) return comp_makeup;
				return comp_makeup * std::pow(comp_thr / e, comp_slope); };
			mix_l = int32_t(std::clamp(xl * gain(m_comp_env_l), -1.0, 1.0) * 32767.0);
			mix_r = int32_t(std::clamp(xr * gain(m_comp_env_r), -1.0, 1.0) * 32767.0);
		}
		if (grev_hle)  // GATED REVERB: reverb tank (measured lengths) + envelope gate chopping the tail
		{
			const double xl = double(mix_l) / 32768.0, xr = double(mix_r) / 32768.0;
			const double ein = std::max(std::fabs(xl), std::fabs(xr));
			m_grev_env = std::max(ein, m_grev_env * 0.999);
			const double target = (m_grev_env > grev_gatethr) ? 1.0 : 0.0;
			if (target >= m_grev_gain) m_grev_gain = target;                      // open instantly
			else m_grev_gain = target + grev_rel * (m_grev_gain - target);        // GATE TIME release
			double wl = 0.0, wr = 0.0;
			for (int c = 0; c < 4; c++)
			{
				const double tl = m_grev_c_l[c].read(double(grev_cd[c])), tr = m_grev_c_r[c].read(double(grev_cd[c]));
				m_grev_c_l[c].write(xl + grev_fb * m_grev_d_l[c].process_one(tl));
				m_grev_c_r[c].write(xr + grev_fb * m_grev_d_r[c].process_one(tr));
				wl += tl; wr += tr;
			}
			for (int a = 0; a < 2; a++)
			{
				const double dl = m_grev_a_l[a].read(double(grev_ad[a])), dr = m_grev_a_r[a].read(double(grev_ad[a]));
				const double yl = -grev_apg * wl + dl, yr = -grev_apg * wr + dr;
				m_grev_a_l[a].write(wl + grev_apg * yl); m_grev_a_r[a].write(wr + grev_apg * yr);
				wl = yl; wr = yr;
			}
			mix_l = int32_t(std::clamp(xl + 0.6 * m_grev_gain * wl, -1.0, 1.0) * 32767.0);
			mix_r = int32_t(std::clamp(xr + 0.6 * m_grev_gain * wr, -1.0, 1.0) * 32767.0);
		}
		if (mix_hle)   // MIX UP: three LFOs (3.0/5.2/7.4 Hz) modulate a short delay -- rich chorus
		{
			const double xl = double(mix_l) / 32768.0, xr = double(mix_r) / 32768.0;
			const double s0 = std::sin(TWO_PI * m_mix_ph[0]), s1 = std::sin(TWO_PI * m_mix_ph[1]), s2 = std::sin(TWO_PI * m_mix_ph[2]);
			for (int i = 0; i < 3; i++) { m_mix_ph[i] += mix_inc[i]; if (m_mix_ph[i] >= 1.0) m_mix_ph[i] -= 1.0; }
			const double tapl = mix_base + mix_depth * (s0 + s1) * 0.5, tapr = mix_base + mix_depth * (s0 + s2) * 0.5;
			const double dl = m_mix_l.read(tapl), dr = m_mix_r.read(tapr);
			m_mix_l.write(xl); m_mix_r.write(xr);
			mix_l = int32_t(std::clamp(xl * (1.0 - mix_wet) + dl * mix_wet, -1.0, 1.0) * 32767.0);
			mix_r = int32_t(std::clamp(xr * (1.0 - mix_wet) + dr * mix_wet, -1.0, 1.0) * 32767.0);
		}
		if (rot_hle)   // ROTARY SPEAKER: crossover + two Doppler-swept, amplitude-modulated rotors
		{
			const double x = 0.5 * (double(mix_l) + double(mix_r)) / 32768.0;
			const double low = m_rot_lp_l.process_one(x), high = x - low;
			const double ts = std::sin(TWO_PI * m_rot_tph), bs = std::sin(TWO_PI * m_rot_bph);
			m_rot_tph += rot_tinc; if (m_rot_tph >= 1.0) m_rot_tph -= 1.0;
			m_rot_bph += rot_binc; if (m_rot_bph >= 1.0) m_rot_bph -= 1.0;
			const double ttap = rot_tbase + rot_tdep * 0.5 * (1.0 + ts), btap = rot_bbase + rot_bdep * 0.5 * (1.0 + bs);
			m_rot_t_l.write(high); m_rot_t_r.write(high); m_rot_b_l.write(low); m_rot_b_r.write(low);
			const double thl = m_rot_t_l.read(ttap), thr = m_rot_t_r.read(ttap + 18.0);
			const double bl = m_rot_b_l.read(btap), br = m_rot_b_r.read(btap + 10.0);
			const double yl = thl * (0.6 + 0.4 * ts) + bl * (0.7 + 0.3 * bs);
			const double yr = thr * (0.6 - 0.4 * ts) + br * (0.7 - 0.3 * bs);
			mix_l = int32_t(std::clamp(yl, -1.0, 1.0) * 32767.0);
			mix_r = int32_t(std::clamp(yr, -1.0, 1.0) * 32767.0);
		}
		if (cmbx)      // PEQ+X / auto-wah+delay combos: emphasis biquad -> 2nd block(s), chained
		{
			double xl = double(mix_l) / 32768.0, xr = double(mix_r) / 32768.0;
			if (cx_peq) { xl = m_eq_l[0].process_one(xl); xr = m_eq_r[0].process_one(xr); }   // PEQ stage
			if (pc_hle)          // chorus (quadrature LFO-swept delay)
			{
				const double s = std::sin(TWO_PI * m_cho_phase), cq = std::cos(TWO_PI * m_cho_phase);
				m_cho_phase += cx_cinc; if (m_cho_phase >= 1.0) m_cho_phase -= 1.0;
				const double dl = m_cho_l.read(cx_depth * (1.0 + s) + 2.0), dr = m_cho_r.read(cx_depth * (1.0 + cq) + 2.0);
				m_cho_l.write(xl); m_cho_r.write(xr);
				xl = xl * (1.0 - cx_wet) + dl * cx_wet; xr = xr * (1.0 - cx_wet) + dr * cx_wet;
			}
			else if (pf_hle)     // flanger (swept delay + feedback)
			{
				const double s = std::sin(TWO_PI * m_fl_phase); m_fl_phase += cx_cinc; if (m_fl_phase >= 1.0) m_fl_phase -= 1.0;
				const double tap = cx_depth * (1.0 + s) + 2.0;
				const double dl = m_fl_l.read(tap), dr = m_fl_r.read(tap);
				m_fl_l.write(xl + cx_fb * dl); m_fl_r.write(xr + cx_fb * dr);
				xl = 0.5 * (xl + dl); xr = 0.5 * (xr + dr);
			}
			else if (pv_hle)     // vibrato (100% wet swept delay = pitch modulation)
			{
				const double s = std::sin(TWO_PI * m_vib_phase); m_vib_phase += cx_cinc; if (m_vib_phase >= 1.0) m_vib_phase -= 1.0;
				const double tap = cx_depth * (1.0 + s) + 2.0;
				const double dl = m_vib_l.read(tap), dr = m_vib_r.read(tap);
				m_vib_l.write(xl); m_vib_r.write(xr);
				xl = dl; xr = dr;
			}
			if (pcmp_hle || pcd_hle || pco_hle)    // compressor
			{
				const double rl = xl * xl, rr = xr * xr;
				const double cl = (rl > m_comp_env_l) ? cx_atk : cx_rel; m_comp_env_l = rl + cl * (m_comp_env_l - rl);
				const double cr = (rr > m_comp_env_r) ? cx_atk : cx_rel; m_comp_env_r = rr + cr * (m_comp_env_r - rr);
				auto g = [&](double e2) -> double { const double e = std::sqrt(std::max(e2, 0.0)); return (e <= cx_thr || e < 1e-6) ? cx_mk : cx_mk * std::pow(cx_thr / e, cx_slope); };
				xl *= g(m_comp_env_l); xr *= g(m_comp_env_r);
			}
			if (pcd_hle || pco_hle || pdd_hle || pod_hle)    // distortion / overdrive waveshaper
			{
				xl = std::tanh(xl * cx_drive) * cx_vol; xr = std::tanh(xr * cx_drive) * cx_vol;
				if (cx_tone) { xl = m_eq_l[1].process_one(xl); xr = m_eq_r[1].process_one(xr); }   // overdrive tone
			}
			if (cx_wah)    // auto-wah: envelope-swept resonant SVF
			{
				m_wah_env_l = std::max(std::fabs(xl), m_wah_env_l * 0.9995);
				m_wah_env_r = std::max(std::fabs(xr), m_wah_env_r * 0.9995);
				const double fcl = 300.0 + std::clamp(m_wah_env_l, 0.0, 1.0) * 3500.0, fcr = 300.0 + std::clamp(m_wah_env_r, 0.0, 1.0) * 3500.0;
				const double fl = 2.0 * std::sin(PI_C * std::min(fcl, 0.45 * STREAM_RATE) / double(STREAM_RATE));
				const double fr = 2.0 * std::sin(PI_C * std::min(fcr, 0.45 * STREAM_RATE) / double(STREAM_RATE));
				m_wah_lp_l += fl * m_wah_bp_l; const double hpl = xl - m_wah_lp_l - 0.15 * m_wah_bp_l; m_wah_bp_l += fl * hpl;
				m_wah_lp_r += fr * m_wah_bp_r; const double hpr = xr - m_wah_lp_r - 0.15 * m_wah_bp_r; m_wah_bp_r += fr * hpr;
				xl = m_wah_bp_l; xr = m_wah_bp_r;
			}
			if (pdd_hle || pod_hle || awd_hle)    // feedback delay stage
			{
				const double dl = m_dly_l.read(double(cx_dN)), dr = m_dly_r.read(double(cx_dN));
				m_dly_l.write(xl + cx_dfb * dl); m_dly_r.write(xr + cx_dfb * dr);
				xl = 0.6 * xl + 0.5 * dl; xr = 0.6 * xr + 0.5 * dr;
			}
			mix_l = int32_t(std::clamp(xl, -1.0, 1.0) * 32767.0);
			mix_r = int32_t(std::clamp(xr, -1.0, 1.0) * 32767.0);
		}

		const float fin_l = softclip(mix_l + wet_l);
		const float fin_r = softclip(mix_r + wet_r);

		// ---- LOG_GLITCH: MIX-level click, with the per-voice breakdown that caused it ----
		// Runs on the FINAL sample the stream emits and names, on the same line, the voices
		// whose own contribution moved most at that sample -- so the attribution is closed
		// inside the device and needs no alignment against an external capture.
		if (VERBOSE & LOG_GLITCH)
		{
			const int32_t o_l = int32_t(fin_l * 32768.0f), o_r = int32_t(fin_r * 32768.0f);
			const int32_t dl = o_l - m_glitch_mix[0], dr = o_r - m_glitch_mix[1];
			if (std::abs(dl) > 8000 || std::abs(dr) > 8000)
			{
				m_mixclick_total++;
				std::string who;
				for (int q = 0; q < NUM_VOICES; q++)
				{
					const int32_t ql = m_glitch_prev[q][0] - m_glitch_prev2[q][0];
					const int32_t qr = m_glitch_prev[q][1] - m_glitch_prev2[q][1];
					if (std::abs(ql) > 1000 || std::abs(qr) > 1000)
						who += string_format(" v%02d(%+d/%+d,b%dp%dc%d,N=%u,P=%u,step=%.2fx,real=%d)",
							q, ql, qr, m_voice[q].wave_bank, m_voice[q].wave_page, m_voice[q].wave_chunk,
							uint32_t(m_voice[q].wave_samples), uint32_t(m_voice[q].pitch_period),
							double(m_voice[q].pitch_step) / 65536.0, m_voice[q].wave_real ? 1 : 0);
				}
				LOGMASKED(LOG_GLITCHEV, "mixclick t=%.6f d=%+7d/%+7d out=%7d/%7d by:%s\n",
					stream.start_time().as_double() + double(s) / double(STREAM_RATE),
					dl, dr, o_l, o_r, who.empty() ? " (none above 1000)" : who.c_str());
			}
			m_glitch_mix[0] = o_l;
			m_glitch_mix[1] = o_r;
			std::memcpy(m_glitch_prev2, m_glitch_prev, sizeof(m_glitch_prev));
		}

		if (VERBOSE & LOG_WINDOW)
		{
			const double tnow = stream.start_time().as_double() + double(s) / double(STREAM_RATE);
			if (tnow >= WINDOW_T0 && tnow <= WINDOW_T1)
			{
				std::string who;
				for (int q = 0; q < NUM_VOICES; q++)
					if (m_glitch_prev[q][0] || m_glitch_prev[q][1])
						who += string_format(" v%02d(%d/%d,b%dp%dc%d,N=%u,P=%u,step=%.2fx)",
							q, m_glitch_prev[q][0], m_glitch_prev[q][1],
							m_voice[q].wave_bank, m_voice[q].wave_page, m_voice[q].wave_chunk,
							uint32_t(m_voice[q].wave_samples), uint32_t(m_voice[q].pitch_period),
							double(m_voice[q].pitch_step) / 65536.0);
				LOGMASKED(LOG_WINDOW, "win t=%.6f out=%d/%d mix=%d/%d%s\n", tnow,
					int32_t(fin_l * 32768.0f), int32_t(fin_r * 32768.0f), mix_l, mix_r, who.c_str());
			}
		}

		stream.put(0, s, sound_stream::sample_t(fin_l));
		stream.put(1, s, sound_stream::sample_t(fin_r));
	}
}
