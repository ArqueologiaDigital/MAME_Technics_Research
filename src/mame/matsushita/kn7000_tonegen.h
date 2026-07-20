// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    KN7000 tone generator -- firmware-driven audio output

    High-level model of the KN7000's TWO tone-generator LSIs (IC201 master +
    IC205 sub, both `C1BB00000709`), driven by the real firmware voice engine:
    every TG register write the firmware performs is routed here from the
    driver's io_w and turned into a voice event.

    The four PCM wave ROMs (IC203/4/7/8) are undumped, so the timbre is a
    placeholder (a sine, or a donor sample from the optional synthetic wave
    pack). Everything else -- pitch, polyphony, note timing, the 7-parameter
    amplitude envelope, the per-part effect-send matrix -- comes from the
    firmware's own register writes and is authentic.

    Split out of kn7000.cpp (2026-07-20) so the tone generator is a device in
    its own file, mirroring the control-panel split (kn7000_cpanel.*).

    Register semantics: notes/tg-voice-register-semantics.md
    Envelope decode:    notes/tg-envelope-sweep-results.md
    Pitch pipeline:     notes/tg-pitch-pipeline.md
    Per-part sends:     notes/per-part-depth-bank.md
    Cross-model (why this is NOT yet shared with the KN6000/KN6500 tone
    generator, and what a future kn6000_tonegen_device needs):
                        notes/kn6000-tonegen-spec.md

***************************************************************************/

#ifndef MAME_MATSUSHITA_KN7000_TONEGEN_H
#define MAME_MATSUSHITA_KN7000_TONEGEN_H

#pragma once

#include <atomic>
#include <vector>



DECLARE_DEVICE_TYPE(KN7000_TONEGEN, kn7000_tonegen_device)

// ---------------------------------------------------------------------------
// kn7000_tonegen_device -- FIRMWARE-DRIVEN audio output (Phase C, Stage 2).
//
// The real tone generators (IC201/IC205) play PCM from the four undumped wave ROMs.
// This device does not have those samples, but it IS driven by the real firmware
// voice engine: every tone-generator register write is routed to tg_write(), and we
// render a placeholder sine per voice using the firmware's own pitch (class 0x2401)
// and note-on/off gating (0x2401 write / 0x0001=0xC000 mute). So pitch, polyphony,
// timing and note events are authentic; only the timbre is a stand-in until the wave
// ROMs are dumped. The path (stream, speakers, DAC) is proven; the machine is
// MACHINE_IMPERFECT_SOUND. See notes/tg-voice-register-semantics.md.
// ---------------------------------------------------------------------------
class kn7000_tonegen_device : public device_t, public device_sound_interface
{
public:
	kn7000_tonegen_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock = 0)
		: device_t(mconfig, KN7000_TONEGEN, tag, owner, clock)
		, device_sound_interface(mconfig, *this)
	{ }

	// Kept for the key-bed input hook (kn7000_state::kbd_key). No longer synthesizes
	// directly: with the TG-enable gate open the FIRMWARE drives every voice through
	// tg_write() below, so keying a second sine here would double the notes.
	void note_on(uint8_t)  { }
	void note_off(uint8_t) { }

	// Stage 2 -- FIRMWARE-DRIVEN synthesis. Every tone-generator register write (both
	// TGs) is routed here from io_w. Once the TG-enable gate is open (see the
	// 0x98070000 strap in io_r) the firmware programs a full per-voice block on each
	// note and we render audio from these registers:
	//   * class 0x2400/0x2401 = the pitch register: an 18-bit SAMPLE-ZONE-RELATIVE
	//     log-pitch, pitch18 = ((class bit0)<<16) | data, at 0x400/semitone. It is
	//     NOT absolute musical pitch: the firmware bakes each tone's element-
	//     descriptor tuning (zone center key, key-scale exponent, coarse/fine) into
	//     the value (lib pitch pipeline: init 0x4C030FB9, runtime 0x4C031127,
	//     transform ((pitch16+0x1800)<<2)&0x3FFFF, write primitive 0x4C036F98), so
	//     each tone sits at a different offset and unpitched drums use a constant.
	//     The MUSICAL pitch therefore comes from the caller (io_w) which resolves it
	//     from the library's voice record (notePitch16, see tg_pitch_resolve()); the
	//     raw pitch18 is kept as the per-note reference so later rewrites on a held
	//     voice apply as RELATIVE bends (vibrato/portamento/pitch bend).
	//     A pitch write on an idle voice gates it ON (attack); on a held voice it is
	//     a bend, not a retrigger (new notes are always preceded by the mute).
	//   * class 0x0001 = 0xC000 = the voice mute the firmware writes on note-off /
	//     voice-steal -> gate the voice OFF (release).
	// Timbre is a placeholder sine: the real PCM wave ROMs (IC203/4/7/8) are undumped,
	// so authentic samples are not yet possible. addr = [group:6][channel:6][index:4].
	// note_x256: musical pitch in 1/256-semitone units resolved from the firmware's
	// voice record by the caller, or -1 if unavailable (fall back to the legacy
	// keybed-anchored absolute decode of pitch18).
	// Envelope stages (see notes/tg-envelope-sweep-results.md). The firmware's 7-param
	// amplitude EG: ATTACK to PEAK (r0), DCY1 toward SUS1 (r1), DCY2 toward SUS2 (r2),
	// RELEASE to silence on the r3 gate-off / managed r0 burst / 0xC000 steal.
	enum : uint8_t { ST_ATTACK = 0, ST_DECAY1, ST_DECAY2, ST_RELEASE };

	// PROVISIONAL chip rate-byte -> seconds law (higher byte = faster; sweep-calibrated
	// anchors: piano ATK 0xD2 -> 9 ms, piano DCY1 0x39 -> 1.8 s, damp burst 0x91 -> 85 ms,
	// organ rA 0xAE -> 31 ms, pad rA 0x04 -> ~11 s).
	static double eg_tau(uint8_t rate);

	void tg_write(int tg, uint16_t addr, uint16_t data, int32_t note_x256 = -1, int rec_type = -1);

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
	// positives). Model: tag each voice with the key that caused it (the most recent MAKE
	// within 60 ms), and on that key's BREAK release the gate-follow voices it started.
	// (Chord edge case: keys pressed near-simultaneously could mis-tag; acceptable for
	// the placeholder.)
	void key_context(uint8_t key) { m_ctx_key = key; m_ctx_time = machine().time().as_double(); }
	void key_break(uint8_t key);

protected:
	// device_t / device_sound_interface overrides
	virtual void device_start() override ATTR_COLD;

	// Per-voice amplitude envelope DRIVEN BY THE FIRMWARE'S 7-param EG (r0/r1/r2 rate|level
	// pairs, resolved at note-on -- see tg_write and notes/tg-envelope-sweep-results.md).
	// Full stage chain: linear ATTACK to PEAK (r0), exponential DCY1 toward SUS1 (r1),
	// exponential DCY2 toward SUS2 (r2, the long-tail second stage), then exponential
	// RELEASE to silence when the gate drops (r3=0x8000 / managed r0 burst / steal mute).
	// A piano (SUS1=SUS2=0) genuinely decays to silence in two stages; an organ
	// (SUS1=SUS2=max) holds; an edited slow attack (r0 hi below ~0xD0) swells audibly.
	virtual void sound_stream_update(sound_stream &stream) override;

private:
	sound_stream *m_stream = nullptr;
	double   m_phase[128] = { };     // per-voice oscillator phase
	double   m_ton[128]   = { };     // note-on machine time (s) -- release detection
	uint16_t m_aux[128]   = { };     // per-voice aux/mode word (latch class 0x1C02; bit15 = gate-follow)
	uint8_t  m_mode[128]  = { };     // 0=MANAGED (firmware key-up burst) 1=GATE_FOLLOW 2=ONESHOT
	// SYNTHETIC wave-pack playback (kn7000_waves_synthetic.rom, optional). Entries map the
	// runtime sample select -- aux word bank (bits13:12) + zone (bits7:0) -- to donor PCM.
	struct wentry { uint8_t bank, zlo, zhi; const int16_t *pcm; uint32_t len, lstart, llen; double root_hz; };
	std::vector<wentry> m_wentries;
	int16_t  m_wsel[128];            // wave-pack entry per voice (-1 = sine fallback)
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
	                                  // overridden by the managed key-up burst's r0 rate)
	uint32_t m_tgwrites = 0;         // count of firmware pitch writes seen (0 = engine dormant)
};


#endif // MAME_MATSUSHITA_KN7000_TONEGEN_H
