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

	// ---------------------------------------------------------------
	//  lo12 -- THE ALU FIELD.  Two sub-fields are decoded; the rest is open.
	//  (notes/dsp-alu-biquad.md, which derives the ARITHMETIC from the
	//  PARAMETRIC EQ biquad -- the one block whose transfer function is known
	//  exactly, from the firmware's own bilinear designer.  The FIELD
	//  BOUNDARIES below are the ones two concurrent, independent analyses
	//  converged on: notes/dsp-alu-structure.md, from the vocabulary
	//  statistics, and notes/dsp-alu-crossval.md, from the all-pass, the LFO
	//  and the input stage.)
	//
	//      11 10           6 5 4              0
	//     +--+--------------+-+----------------+
	//     |G |     SRC      |M|     ACTION     |
	//     +--+--------------+-+----------------+
	//
	//  bit 5 (M) partitions the field: the eleven lo12 values that carry it
	//  (0x021 rstcur, 0x820/821/822/825/827, 0x839, 0x864, 0x8BC, 0x921, 0xC63)
	//  are EXACTLY the pointer-register / cursor / table-lookup family and
	//  nothing else -- 96 of 3057 corpus words -- and bit 11 (G) is locked to
	//  it (95 of 96).  MEASURED, and it is the only bit of lo12 that is never
	//  toggled alone in the 55 Hamming-distance-1 pairs of the vocabulary.
	// ---------------------------------------------------------------
	static constexpr u8 lo_src(u64 w) { return u8((w >> 6) & 0x1f); }
	static constexpr u8 lo_op(u64 w)  { return u8(w & 0x1f); }
	static constexpr bool lo_ptrmode(u64 w) { return BIT(w, 5); }

	// lo12[10:6] = THE OPERAND-SOURCE SELECT -- which register or bus supplies
	// the word's operand.  Four of its eighteen observed codes are anchored;
	// they are the four the biquad section FORCES, and they are exactly the
	// four things the CDJ-500 block diagram's datapath can put on that bus.
	// CONSISTENT with the corpus elsewhere: 0x64B -- the reverb diffuser
	// multiply that R1's constraint solve proved cannot read mem[p] and cannot
	// read the incoming accumulator -- is LO_SRC_TA, which is the one route R1
	// could name only as "something else".
	//
	// The field is FIVE bits, not two.  A 2-bit reading agrees on every code
	// used here, but corpus-wide it would merge the delay-RAM operand into
	// mem[ptr] (0x0B vs 0x07) and the LFO into the accumulator (0x08/0x1C vs
	// 0x10) -- separations that are 0-of-106 / 87-of-87 clean.
	// (notes/dsp-alu-structure.md sect. 5.)
	enum : u8 {
		LO_SRC_MEM = 0x07,      // mem[ptr]
		LO_SRC_ACC = 0x10,      // the accumulator
		LO_SRC_TA  = 0x19,      // temporary register A
		LO_SRC_TB  = 0x1a       // temporary register B
	};

	// lo12[4:0] = the ACTION -- what is done with the operand.  Five of its 24
	// observed codes are pinned by the biquad; the rest are OPEN and this
	// decoder does not guess them.
	enum : u8 {
		LO_OP_ST_BUS = 0x07,    // mem[ptr] <- bus
		LO_OP_NONE_2 = 0x12,    // no temp/memory side effect
		LO_OP_CAP_TA = 0x13,    // tempA <- bus
		LO_OP_CAP_TB = 0x14,    // tempB <- bus
		LO_OP_NONE_5 = 0x15     // ditto -- how it differs from 0x12 is OPEN
	};

	// THE EIGHT lo12 VALUES THE BIQUAD PINS, and deliberately no more.
	//
	// The SRC and OP fields above are read as fields, but bits[11:8] and bit 4
	// are still open, so a word that shares an OP nibble while differing in
	// those bits is NOT the same instruction as far as this decoder knows.
	// Whitelisting the eight exact values keeps the claim exactly as wide as
	// the evidence: they are the eight lo12 values of the PARAMETRIC EQ
	// section, whose arithmetic is verified against the firmware's own biquad
	// designer.  They are also, by a wide margin, the most common values in the
	// corpus -- 1146 of 3057 words (37.5 %) -- so the restriction costs little.
	static constexpr bool alu_decoded(u64 w)
	{
		switch (lo12(w))
		{
		case 0x1d3: case 0x1d4: case 0x1d5:     // src = mem[ptr]
		case 0x407: case 0x412: case 0x415:     // src = acc
		case 0x647:                             // src = tempA
		case 0x687:                             // src = tempB
			return true;
		default:
			return false;
		}
	}

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
