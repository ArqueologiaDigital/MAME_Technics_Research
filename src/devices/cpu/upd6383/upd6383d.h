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

	// ---------------------------------------------------------------
	//  hi12 IS NOT AN OPCODE.  It is a HORIZONTAL MICROWORD of independent
	//  enable bits (MEASURED, notes/kn5000-dsp-hi12.md sect. 2): the 54
	//  observed values contain 77 Hamming-distance-1 pairs against a
	//  popcount-matched null of 43.4 +/- 4.3, z = +7.9, spread over all
	//  twelve bit positions.  So it is rendered as FLAGS PLUS A RESIDUE,
	//  never as an opaque 12-bit number.
	// ---------------------------------------------------------------
	static constexpr u16 HI_ESC = 1 << 11;  // FORMAT ESCAPE (bits[10:0] mean something else)
	static constexpr u16 HI_END = 1 << 10;  // END OF BLOCK, only when HI_ESC is clear
	static constexpr u16 HI_ST  = 1 << 4;   // WRITE ACCUMULATOR -> mem[ptr]

	// proven to be FIELDS (all values exercised), meaning UNKNOWN
	static constexpr u16 hi_f98(u16 hi) { return (hi >> 8) & 3; }   // ARITY 3: 1713/493/766/2
	static constexpr u16 hi_f31(u16 hi) { return (hi >> 1) & 7; }   // 8/8 values seen

	// bits with no reading at all: 7, 6, 5, 0 (plus 10 inside the escape)
	static constexpr u16 hi_residue(u16 hi)
	{
		u16 known = HI_ESC | HI_ST | 0x300 | 0x00e;      // esc, store, f98, f31
		if (!(hi & HI_ESC))
			known |= HI_END;                            // END only outside the escape
		return hi & ~known;
	}

	// "END ST f98=2 f31=1 ?7 res=080" -- flags, named-but-unexplained fields,
	// and the explicit residue of bits nothing accounts for
	static std::string hi12_text(u16 hi);

	// bit 23 (== class4 bit 3) is the CURSOR-FETCH enable.  It is NOT a
	// multiply enable -- that reading was CORRECTED: 18 of the phaser's 20
	// all-pass sections contain no cursor-fetching word at all and they still
	// need gains (notes/kn5000-dsp-axes.md sect. 2.2, sect. 1).
	static constexpr bool cursor_fetch(u64 w) { return BIT(w, 23); }

	// COEFFICIENT CONSUMER = class4 == 0xA (MEASURED, notes/kn5000-dsp-biquad-map.md
	// sect. 2, cursor-general.md sect. 1).  This is a STRICTER predicate than
	// cursor_fetch()/bit 23: the implicit coefficient cursor advances by exactly
	// one per CLASS-A word, and the bank the loader uploads holds `class-A + 1'
	// words in 26 of 38 images -- a test class 8 (also bit-23) fails, so class 8
	// does NOT advance the cursor (it is the biquad's post-sum step, which is why
	// the make-up gain still lands on slot NN+5, semantics.md sect. 3).  Every
	// class-A word reads ONE coefficient from C-RAM at the current cursor position.
	static constexpr bool coeff_consumer(u64 w) { return class4(w) == 0xa; }

	// the implicit coefficient cursor is reset to its base by this rewind word
	// (MEASURED, biquad-map.md sect. 2.1: `801.0.00.021' sends the cursor back to
	// 0; algo 39's two channels share coefficients across it).
	static constexpr bool is_rstcur(u64 w)
	{
		return hi12(w) == 0x801 && class4(w) == 0 && addr8(w) == 0x00 && lo12(w) == 0x021;
	}

	// true when this word is one of the (few) forms the corpus has decoded
	static bool decoded(u64 word);

	// ---------------------------------------------------------------
	//  K6 -- THE AUDIO INPUT STAGE.  ADDRESSING DECODED, ALU NOT.
	//
	//  The twelve words of the shared kernel's input stage (I-RAM 0..11) have a
	//  FORCED addressing effect and an OPEN arithmetic one
	//  (notes/dsp-k6-input-stage.md sect. 3, sect. 7).  That is a THIRD state,
	//  not a second: they are not `decoded()' -- the value they leave in the
	//  accumulator is unknown -- but their pointer walk, their store enable and
	//  their cursor fetch are all MEASURED, and executing just that much is what
	//  lets a sample enter the chip.
	//
	//  Matched by EXACT 36-bit WORD VALUE, never by I-RAM position.  MEASURED:
	//  each of the twelve occurs exactly once in the 60-word header and ZERO
	//  times in the 2974-word body corpus, with a single exception -- the
	//  epilogue's w79 is byte-identical to the header's w3, which is the note's
	//  own frame-closure loop (sect. 5) and is meant to execute in both places.
	//  So the whitelist cannot reach a word this decode did not cover.
	// ---------------------------------------------------------------
	static bool addressing_only(u64 word);

	// non-null for the words above: the role string the trace prints
	static const char *input_stage_role(u64 word);

	// True for the two words whose D-RAM operand IS an audio input latch --
	// `iw4' (header w4) and `iw8' (header w8).  There is no "read DI"
	// OPCODE on this chip: the port-ness is entirely in the ADDRESS, which is
	// why every opcode-level search for an I/O instruction came up empty
	// (notes/dsp-k6-input-stage.md sect. 7).  `right' is set false for the
	// first block's latch and true for the second's.
	static bool is_input_latch_read(u64 word, bool &right);

	// bit 10 with bit 11 clear = END OF BLOCK.  MEASURED: 38 such words in
	// 2974 body words, exactly one per image and every one of them the FINAL
	// word; but FOURTEEN in the 60-word common header and ZERO in the 23-word
	// epilogue at I-RAM 60..82.  So it is NOT a halt and NOT a commit -- a body
	// performs many stores yet carries it once.  Its default action is FALL
	// THROUGH; a transfer happens only when the word also carries a UNIT TAG
	// (class4 == 1 && addr8 in {0E,0F}).  notes/kn5000-dsp-headerdecode.md.
	// Stripping the bit leaves an ordinary working hi12 in 9 of 9 cases, so the
	// word still does its datapath work.
	static constexpr bool is_end(u64 word)
	{
		const u16 hi = hi12(word);
		return (hi & HI_END) && !(hi & HI_ESC);
	}

	// one-line text for `word', usable outside a disassembly context (the
	// device's trap-and-log path uses it)
	static std::string text(u64 word);
};

#endif // MAME_CPU_UPD6383_UPD6383D_H
