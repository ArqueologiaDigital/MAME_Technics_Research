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

	// proven to be a FIELD (all values exercised), meaning UNKNOWN
	static constexpr u16 hi_f98(u16 hi) { return (hi >> 8) & 3; }   // ARITY 3: 1713/493/766/2

	// ---------------------------------------------------------------
	//  hi12[3:1] = THE ACCUMULATOR OPERATION.
	//
	//  THIS IS THE ADJUDICATION OF THREE CONCURRENT ANALYSES, and it FALSIFIES
	//  the framing the work started from ("lo12 is the ALU field").  The
	//  operation is NOT in lo12.  FORCED, by a minimal pair that the biquad
	//  could not see (notes/dsp-alu-crossval.md B1, re-derived in
	//  notes/dsp-alu-applied.md sect. 2):
	//
	//      092.A.dd.200  and  094.A.dd.200  are identical in class4, in addr8
	//      and in ALL TWELVE lo12 BITS; they differ only in hi12[3:1] (1 vs 2).
	//      In 12 of 20 images they address the SAME D-RAM cell with the pointer
	//      frozen, and they consume C-RAM[+0] = 0x000072 and C-RAM[+1] =
	//      0x7FFFFF.  That cell has to end up a 0.6 Hz ramp -- and 114/2^23 *
	//      44100 = 0.5993 Hz, so the two constants ARE an increment and a
	//      2^23 wrap.  No single binary operation applied twice with those two
	//      constants makes a ramp (+ - * min max and or xor: all give ~22 kHz
	//      or a constant, MEASURED).  So the two words compute DIFFERENT
	//      things, and the only field that differs is this one.
	//
	//  Its three low codes are the ones the PARAMETRIC EQ biquad exercises, and
	//  reading them this way reproduces that block's transfer function to the
	//  last bit (notes/dsp-alu-biquad.md sect. 7-A8 measured the equivalence;
	//  what is new is that the LFO REMOVES the alternative).  The product
	//  register is NOT consumed by the add: it holds until the next multiply.
	// ---------------------------------------------------------------
	static constexpr u16 hi_f31(u16 hi) { return (hi >> 1) & 7; }   // 8/8 values seen

	enum : u16 {
		HI_ACC_LOAD = 0,    // acc <- P
		HI_ACC_ADD  = 1,    // acc <- acc + P
		HI_ACC_HOLD = 2     // acc unchanged -- ONLY established on class 8
	};

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
	//  lo12 -- THE OPERAND ROUTING.  NOT the operation: see hi_f31() above.
	//
	//  Three concurrent, independent analyses converged on the SAME field map
	//  -- notes/dsp-alu-structure.md (vocabulary statistics: 55 Hamming-1 pairs
	//  against a popcount-matched null of 15.2 +/- 3.7, z = +10.8, so lo12 is a
	//  horizontal microword exactly as hi12 is), notes/dsp-alu-biquad.md (the
	//  PARAMETRIC EQ section, whose transfer function is known independently
	//  from the firmware's own bilinear coefficient designer) and
	//  notes/dsp-alu-crossval.md (the all-pass, the LFO and the input stage).
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
	static constexpr u8 lo_act(u64 w) { return u8(w & 0x1f); }
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
		LO_ACT_ST_BUS = 0x07,   // mem[ptr] <- bus
		LO_ACT_NONE_2 = 0x12,   // no temp/memory side effect
		LO_ACT_CAP_TA = 0x13,   // tempA <- bus
		LO_ACT_CAP_TB = 0x14,   // tempB <- bus
		LO_ACT_NONE_5 = 0x15    // ditto -- how it differs from 0x12 is OPEN
	};

	static constexpr bool lo_src_anchored(u8 s)
	{
		return s == LO_SRC_MEM || s == LO_SRC_ACC || s == LO_SRC_TA || s == LO_SRC_TB;
	}

	static constexpr bool lo_act_anchored(u8 a)
	{
		return a == LO_ACT_ST_BUS || a == LO_ACT_NONE_2 || a == LO_ACT_CAP_TA
				|| a == LO_ACT_CAP_TB || a == LO_ACT_NONE_5;
	}

	// ---------------------------------------------------------------
	//  THE EXECUTABLE PREDICATE -- three guards, each with its own evidence,
	//  and NOTHING outside their conjunction.
	//
	//  This REPLACES an eight-value lo12 whitelist that had a real defect: it
	//  tested lo12 ALONE, so it also executed `880.1.20.407', `900.1.60.1D5'
	//  and `800.1.60.1D5' -- CLASS-1 words that R1's constraint solve FORCED to
	//  be external delay-RAM accesses (dsp/analysis/r1-allpass-motif.md) -- as
	//  though they were ordinary on-chip arithmetic.  A DRAM word executed as
	//  arithmetic is exactly the plausible-but-wrong behaviour this device
	//  exists to refuse.  MEASURED: 116 corpus words leave the executable set
	//  because of the class and operation guards, and 154 join it because the
	//  routing fields are now read as FIELDS.  (notes/dsp-alu-applied.md.)
	//
	//  1. CLASS.  Only 2 (pointer post-increment), A (post-increment + one
	//     coefficient) and 8 (the post-sum step) are on-chip datapath classes.
	//     In classes 1/3/5/6 the addr8 is a bracket code, unit index or table
	//     selector, NOT a pointer delta (MEASURED, kn5000-dsp-pointer.md), and
	//     class 1 is where the external-DRAM bracket lives.  Zero corpus words
	//     of any other class pass the routing guard anyway, so this costs
	//     nothing and prevents the category error above.
	//  2. ROUTING.  Both halves of lo12 must be anchored, and neither the
	//     pointer-mode bit (5) nor the G bit (11) may be set.
	//  3. OPERATION.  hi12[3:1] must be one the biquad determines.  HI_ACC_HOLD
	//     is admitted ONLY on class 8: that is the one word the biquad shows it
	//     on, "the accumulator is unchanged there" is what the reconstruction
	//     DETERMINES, and the LFO says the same code does something visible
	//     elsewhere (notes/dsp-alu-applied.md sect. 2.3 enumerates the two
	//     survivors, a 2^23 AND and a conditional subtract -- both of which ARE
	//     the identity on a completed biquad sum, which is why executing this
	//     one word as "unchanged" is correct under either).
	// ---------------------------------------------------------------
	static constexpr bool alu_decoded(u64 w)
	{
		const u8 cl = class4(w);
		if (cl != 2 && cl != 8 && cl != 0xa)
			return false;
		if (lo12(w) & 0x800)                    // G
			return false;
		if (lo_ptrmode(w))                      // M
			return false;
		if (!lo_src_anchored(lo_src(w)) || !lo_act_anchored(lo_act(w)))
			return false;

		switch (hi_f31(hi12(w)))
		{
		case HI_ACC_LOAD: case HI_ACC_ADD: return true;
		case HI_ACC_HOLD: return cl == 8;
		default: return false;
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
