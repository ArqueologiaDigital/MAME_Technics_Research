// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    KN7000 tone generator -- firmware-driven audio output

    The KN7000's TWO tone-generator LSIs (IC201 master + IC205 sub, both
    `C1BB00000709`), driven by the real firmware voice engine: every TG
    register write the firmware performs is routed here from the driver's
    io_w and turned into a voice event.

    Only the KN7000-SPECIFIC half lives here: the register NUMBERING -- which
    plane and which per-voice register index means what -- and the two-chip
    slot mapping. The voice/envelope model, the effect-send gains, the wave
    pack and the audio stream are shared with the other MN10300 models and
    live in the base class (kn_tonegen.h / kn_tonegen.cpp), which documents
    the firmware evidence for that split.

    The four PCM wave ROMs (IC203/4/7/8) are undumped, so the timbre is a
    placeholder (a sine, or a donor sample from the optional synthetic wave
    pack). Everything else -- pitch, polyphony, note timing, the 7-parameter
    amplitude envelope, the per-part effect-send matrix -- comes from the
    firmware's own register writes and is authentic.

    Register semantics: notes/tg-voice-register-semantics.md
    Envelope decode:    notes/tg-envelope-sweep-results.md
    Pitch pipeline:     notes/tg-pitch-pipeline.md
    Per-part sends:     notes/per-part-depth-bank.md
    Cross-model:        notes/kn6000-tonegen-spec.md

***************************************************************************/

#ifndef MAME_MATSUSHITA_KN7000_TONEGEN_H
#define MAME_MATSUSHITA_KN7000_TONEGEN_H

#pragma once

#include "kn_tonegen.h"

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
class kn7000_tonegen_device : public kn_tonegen_base_device
{
public:
	// 128 voices: 64 per chip, slot bit 6 selecting sub (IC205) or master (IC201).
	kn7000_tonegen_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock = 0)
		: kn_tonegen_base_device(mconfig, KN7000_TONEGEN, tag, owner, clock, 128)
	{ }


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
	void tg_write(int tg, uint16_t addr, uint16_t data, int32_t note_x256 = -1, int rec_type = -1);

};

#endif // MAME_MATSUSHITA_KN7000_TONEGEN_H
