// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    KN6000/KN6500 tone generator -- firmware-driven audio output

    The SX-KN6000 and SX-KN6500 carry ONE tone-generator LSI, IC213
    `D82398GD001`, with 64 voice slots behind a single register window at
    0x98050000/2. Like the KN7000's pair of `C1BB00000709` chips it is driven
    entirely by the firmware's own voice engine, so every register write is
    routed here from the driver's io_w and turned into a voice event.

    Only the KN6000-SPECIFIC half lives here: the register NUMBERING. The
    voice/envelope model, the effect gains, the wave pack and the audio
    stream are shared with the KN7000 in the base class (kn_tonegen.h),
    which documents the firmware evidence that the two chips share one
    driver architecture.

    HOW THE NUMBERING WAS RECOVERED (static RE, 2026-07-20; the live
    cross-check is tools/kn6000_tg_probe.lua). The firmware enumerates its
    own register map for us: the note-on routine at 0x484948CB is a straight
    BLIT of a 0xA0-byte shadow register image (0x50043100 + slot*0xA0) into
    the chip, one `call 0x4849465B` per register, each with the destination
    OR-ed in as a literal. Reading those literals off in order yields the
    complete per-voice map with no guessing:

      cls 0x0000        idx 0    GATE            (0x87FF note-on / 0x8000 key-up)
      cls 0x0001-0x000F          shadow +0x02..+0x2A, halfword per register
      cls 0x0400/0x0401          shadow +0x2C/+0x2E
      cls 0x5000        <- shadow +0x74  (32-bit: high half extends the index)
      cls 0x5400        <- shadow +0x78  (32-bit)
      cls 0x5800        <- shadow +0x7C  (32-bit) -- the gate-on pitch INIT
      cls 0x0800..0x080D         shadow +0x30..+0x3E
      cls 0x1000..0x3000         shadow +0x40..+0x60 (32-bit each)
      cls 0x4000        <- shadow +0x64  per-voice LEVEL
      cls 0x4400..0x4C00         shadow +0x68..+0x70
      cls 0x5C00..0x6400         shadow +0x80..+0x88
      cls 0x8000..0x9000         shadow +0x8C..+0x9C  per-voice wave/sample params

    Every byte of the 0xA0-byte shadow record is accounted for, which is what
    makes this a map rather than a sample.

    The AMPLITUDE ENVELOPE sits at cls 0x0004/0x0005/0x0006 -- proven by the
    literals, not by position: the damp routine at 0x484947B3 writes the same
    0xA280/0xA200 pair the KN7000 writes to its r0/r1, and the mute routine at
    0x484946DC writes the same 0xC000 to 0x0005/0x0006. So the KN6000's
    envelope banks are the KN7000's shifted by +4 (banks at 4/8/C rather than
    0/4/8), and the release burst hits {4,5,8,9,C,D} where the KN7000 hits
    {0,1,4,5,8,9} -- the first two registers of each of the three banks in
    both cases. The gate is the one register that genuinely MOVES: r3 on the
    KN7000, r0 here.

    PITCH. As on the KN7000 the chip's pitch register is sample-zone-relative,
    not absolute musical pitch, so it cannot be sounded directly. The musical
    pitch comes from the firmware's OWN computed value in the library voice
    record, resolved by the driver and passed in as note_x256 -- exactly the
    mechanism the KN7000 uses. The KN6000's record initialiser at 0x48493D80
    writes the same three fields with the same semantics as the KN7000's
    (+0x08 = 0x80|(pitch16>>8) active|note, +0x0A base pitch16, +0x0C
    notePitch16), in a 0xB4-stride record -- the same stride as the KN7000's
    array at 0x500AF940. That correspondence is what unblocked this device:
    the KN6000's note->pitch computation never had to be reversed, because the
    firmware publishes its result in a record whose layout we already
    understood. (The array the driver reads is the per-TG-SLOT copy at
    0x5027AF28, not the library array at 0x502858F8, which is indexed by note
    element rather than by slot -- see kn7000.cpp's resolve comment.)

    The four (KN6000) / six (KN6500) PCM wave ROMs are undumped, so the timbre
    is a placeholder sine -- but pitch, polyphony, note timing and the
    7-parameter amplitude envelope all come from the firmware's own register
    writes and are authentic.

    Cross-model comparison: notes/kn6000-tonegen-spec.md
    Live cross-check:       tools/kn6000_tg_probe.lua

***************************************************************************/

#ifndef MAME_MATSUSHITA_KN6000_TONEGEN_H
#define MAME_MATSUSHITA_KN6000_TONEGEN_H

#pragma once

#include "kn_tonegen.h"

DECLARE_DEVICE_TYPE(KN6000_TONEGEN, kn6000_tonegen_device)

class kn6000_tonegen_device : public kn_tonegen_base_device
{
public:
	// 64 voice slots in ONE chip (IC213) behind a single window -- no chip select,
	// so the driver always calls tg_write() with tg = 1 (the 0x98050000 window).
	kn6000_tonegen_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock = 0)
		: kn_tonegen_base_device(mconfig, KN6000_TONEGEN, tag, owner, clock, 64)
	{ }

	virtual void tg_write(int tg, uint16_t addr, uint16_t data, int32_t note_x256 = -1, int rec_type = -1) override;
};

#endif // MAME_MATSUSHITA_KN6000_TONEGEN_H
