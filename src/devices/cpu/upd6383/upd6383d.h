// license:BSD-3-Clause
// copyright-holders:Felipe Sanches
/***************************************************************************

    upd6383d.h

    NEC uPD6383GF digital signal processor -- disassembler.

    *** DRAFT / RESEARCH INSTRUMENT.  THE INSTRUCTION SET IS NOT DECODED. ***

    Only a handful of instruction forms have been established (see upd6383d.cpp
    for the per-form evidence).  EVERY other word is emitted in the explicit,
    greppable `?word 0x0XXXXXXXXX' form.  Do NOT invent mnemonics here: later
    work will be built on whatever this file claims.

***************************************************************************/

#ifndef MAME_CPU_UPD6383_UPD6383D_H
#define MAME_CPU_UPD6383_UPD6383D_H

#pragma once

#include <string>

class upd6383_disassembler : public util::disasm_interface
{
public:
	upd6383_disassembler() = default;
	virtual ~upd6383_disassembler() = default;

	virtual u32 opcode_alignment() const override;
	virtual offs_t disassemble(std::ostream &stream, offs_t pc, const data_buffer &opcodes, const data_buffer &params) override;

	// bytes per 36-bit instruction word, as uploaded by the host
	static constexpr u32 WORD_BYTES = 5;

	// field accessors -- the working field map (INFERRED, notes/kn5000-dsp-encoding.md sect. 8)
	//     hi12[35:24] . class4[23:20] . addr8[19:12] . lo12[11:0]
	static constexpr u16 hi12(u64 w)   { return u16((w >> 24) & 0xfff); }
	static constexpr u8  class4(u64 w) { return u8((w >> 20) & 0xf); }
	static constexpr u8  addr8(u64 w)  { return u8((w >> 12) & 0xff); }
	static constexpr u16 lo12(u64 w)   { return u16(w & 0xfff); }

	// true when this word is one of the (few) forms the corpus has decoded
	static bool decoded(u64 word);

	// one-line text for `word', usable outside a disassembly context (the
	// device's trap-and-log path uses it)
	static std::string text(u64 word);
};

#endif // MAME_CPU_UPD6383_UPD6383D_H
