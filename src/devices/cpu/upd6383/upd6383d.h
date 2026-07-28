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
	//  THE C-FORMAT -- TWO DIFFERENT PREDICATES, AND CONFLATING THEM HAS
	//  ALREADY COST THIS PROJECT TWO COMMITTED RESULTS.
	//  (dsp/analysis/isa-adjudication.md sect. 1, sect. 3.)
	//
	//  In `hi12[11:8] == 0xC' there is no class4 and no addr8: bits [24:12] are
	//  ONE 13-bit immediate that reaches one bit INTO hi12 (which is why the
	//  unit-1 link value reads 0xC41 and not 0xC40).
	//
	//    c_format()  hi12[11:8] == 0xC        THE FORMAT.  68 words of 3057.
	//        Decides whether class4/addr8 exist at all, so it must be tested
	//        BEFORE any rule keyed on either.  Forced three ways: R2's
	//        addressing-mode census reproduces row for row ONLY under it;
	//        classes 3/7/B/E/F are empty ONLY under it (narrow, the corpus's one
	//        apparent "class 3" is C04.3.12.820, a header POINTER-LOAD word);
	//        and both C00 words carry a non-zero B while encoding their own
	//        I-RAM address (76*32+4 at I-RAM 76, 82*32+7 at I-RAM 82).
	//    is_c40()    (hi12 & 0xFFE) == 0xC40  THE PAYLOAD RULE.  57 words.
	//        Only INSIDE it is imm13 a multiple of 32 -- 57/57 in, 2/11 out
	//        (MEASURED, dsp/analysis/k3-pointers.md sect. 5.3) -- so only there
	//        is the payload the 8-bit field [24:17] with B == 0.  The rule is
	//        FAMILY-LOCAL and must NOT be extended to C00/C04/C0A/C16/C42/C4A/C64.
	//
	//  ONE LIVE DEFECT THIS FIXES, MEASURED: `C00.A.47.407' -- the frame
	//  terminator at I-RAM 82 -- passed the old alu_decoded() and was rendered
	//  and executed as an ordinary class-A multiply-and-store, because nothing
	//  tested the format.  It is one word of 3057, and it is the last word of
	//  every frame.
	// ---------------------------------------------------------------
	static constexpr bool c_format(u64 w) { return (hi12(w) & 0xf00) == 0xc00; }
	static constexpr bool is_c40(u64 w)   { return (hi12(w) & 0xffe) == 0xc40; }
	static constexpr u16  c_imm13(u64 w)  { return u16((w >> 12) & 0x1fff); }
	static constexpr u8   c_a(u64 w)      { return u8((w >> 17) & 0xff); }   // payload
	static constexpr u8   c_b(u64 w)      { return u8((w >> 12) & 0x1f); }   // 5-bit sub-field

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

	// ---------------------------------------------------------------
	//  lo12 BIT 11 IS A FIELD, NOT PART OF AN OPCODE.
	//  PROVEN BY CONSTRUCTION (dsp/analysis/k3-pointers.md sect. 1.1 item 2):
	//  the Sub CPU writer at LABEL_0387E6 assembles the low byte first and then
	//  does a literal `INC 8, WA' into byte 3's low nibble, i.e. it builds
	//  `lo12 = 0x800 | 0x021' and `lo12 = 0x800 | 0x025'.  So `0x021' (rstcur)
	//  and `0x821' (ldptr) are ONE ROUTE PLUS A MODIFIER -- they differ in
	//  exactly one bit of the whole 36-bit word -- and must never be modelled as
	//  two unrelated 12-bit codes.  lo_sel() is the route, lo_imm() the modifier.
	// ---------------------------------------------------------------
	static constexpr u8   lo_sel(u64 w) { return u8(lo12(w) & 0xff); }        // the register SELECTOR
	static constexpr bool lo_imm(u64 w) { return BIT(w, 11); }                // "addr8 carries a payload"
	static constexpr u8   lo_mid(u64 w) { return u8((lo12(w) >> 8) & 7); }    // residue: 0 in all 10 corpus sites

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
	// observed codes were pinned by the biquad; TWO MORE are pinned here by a
	// three-context adjudication, and the rest are OPEN and this decoder does
	// not guess them.
	//
	// ★ LO_ACT_ACC_BUS (0x00) -- THE LARGEST CODE IN THE FIELD (820 corpus
	// words, 170 distinct) AND THE ONE THAT RECONCILES TWO PASSES THAT
	// CONTRADICTED EACH OTHER.  dsp/analysis/acc-adder.md:
	//     * the LFO ramp (29 blocks, 16 programs, 0.2..1000 Hz) DETERMINED
	//       `acc <- bus' taken BEFORE the hi12[3:1] operation;
	//     * SINGLE DELAY (algo 9) DETERMINED `acc += bus' taken AFTER it.
	// Neither pass enumerated the other's ORDER, and no sequential order
	// satisfies both.  What both contexts actually demand is the SAME
	// EXPRESSION at the word where their sum forms -- `acc = bus + P' -- once at
	// hi12[3:1] == 1 and once at hi12[3:1] == 0.  So the ACTION is not a step
	// before or after the operation: it is a SELECTOR ON THE SAME ADDER, and it
	// substitutes the operand bus for the accumulator's own feedback term.  See
	// upd6383.cpp exec_alu().  ★ THE ADDER ITSELF IS FORCED.
	//
	// ⚠ ONE OF THE ADDER'S TWO LEGS HAS BEEN WITHDRAWN, 2026-07-27
	// (analysis/adjudication-round6.md sect. 3).  The argument above is a
	// RECONCILIATION of the LFO ramp with SINGLE DELAY, and SINGLE DELAY's
	// harness wires the delay line at the polarity adjudication-round5 item D
	// REVERSED, so its half of the reconciliation is void.  The adder is
	// RETAINED -- it is not refuted, the LFO leg is untouched, and it is the
	// plurality (27 of 33) in the three-context solve even in the reversed
	// model -- but "FORCED" now stands on ONE context and must be re-derived
	// against a TWO-ADDRESS delay line before it is quoted as a two-context
	// forcing again.
	//
	// ⚠ WHICH accumulator half `0x00' selects is CONSISTENT, NOT FORCED --
	// CORRECTED 2026-07-27, dsp/analysis/action00-discriminator.md.  This comment
	// used to read "FORCED: the one reading that survives the LFO, SINGLE DELAY
	// *and* the biquad".  Two of those three are BLIND to the question and always
	// were: on an ACTION-0x00 word with hi12[3:1] == 0 `load' (bus + P) and `add'
	// (0 + P + bus) are THE SAME EXPRESSION, SINGLE DELAY's ACTION-0x00 word is
	// exactly that shape, and the biquad carries no ACTION-0x00 word at all
	// (MEASURED: its ACTION codes are 07 12 13 14 15).  The 18/18 was ONE context,
	// the LFO, plus a store-timing pin -- and it breaks on a gate nobody had
	// enumerated (a bit-7-SUPPRESSED store whose CLEAR is deferred to the END of
	// the word): the same three-context solve then has 33 survivors, `load' x15,
	// `add' x12, `rload' x6.  ★ AND THE TWO QUESTIONS ARE ONE: in all 33, `add'
	// and `rload' occur ONLY on a late-clearing gate and `load' on any of five.
	// `load' SHIPS because it is the plurality and the only reading compatible
	// with every surviving gate -- withdrawing it would re-trap 107 corpus words
	// that no evidence falsifies -- but it is CONSISTENT and must not be cited as
	// FORCED.  (The reverb comb of analysis/schroeder-topology.md forces `load'
	// too, but only INSIDE a topology hypothesis, so it does not restore the
	// label.)
	//
	// ★ LO_ACT_CAP_TA2 (0x19) -- a SECOND CAPTURE PAIR beside 0x13/0x14
	// (0x19 = 0x13 + 6, 0x1A = 0x14 + 6).  It reads tempA <- bus, it SHIPS, and
	// ⛔ ITS FORCING IS WITHDRAWN -- 2026-07-27,
	// analysis/adjudication-round6.md sect. 3.  READ THAT BEFORE QUOTING ANY
	// NUMBER BELOW.
	//
	// WHAT THIS COMMENT USED TO SAY, and why both halves fall together:
	//   (a) "FORCED 72/72 by SINGLE DELAY once the order above is fixed
	//       (108/108 in the wider space of analysis/action00-discriminator.md
	//       sect. 7, both windows and both input-mix settings)";
	//   (b) "IT SURVIVED A CHALLENGE AND THE CHALLENGE IS WITHDRAWN" --
	//       analysis/schroeder-topology.md sect. 0-C's comb core conditionally
	//       FALSIFIES this reading (STRICT survivors force `tempB <- bus',
	//       112/112), and analysis/blocking-read.md withdrew that challenge
	//       because the comb search "omitted the BLOCKING read (land = -1),
	//       which is the read model SINGLE DELAY itself FORCES 5145/5145".
	//
	// ⛔ THE PREMISE UNDER BOTH IS FALSIFIED.  analysis/dram-datapath.md sect.
	// 3.1 re-attributes that 5145/5145: it read SINGLE DELAY under the OLD
	// delay-DRAM polarity, and adjudication-round5 item D REVERSED it
	// (addr8 0x20/0x30 = READ, 0x60 = WRITE).  Round 6 then checked the thing
	// nobody had: the SINGLE DELAY harnesses themselves.
	// `action00_discriminate.sd_run' and `acc_adjudicate.sd_run' BOTH hard-code
	//     if (addr8(w) & 0xf0) == 0x20: line.write(bus) else: dr = line.read()
	// -- the delay line wired BACKWARDS relative to the FORCED direction.  And
	// SINGLE DELAY is the ONLY published ALU context carrying delay-DRAM words:
	// of the 94 corpus ACTION-0x19 sites, 92 sit in DRAM-carrying images and the
	// only DRAM-free one is algo 88, which analysis/second-dsp-and-ready.md
	// showed is an IC310 (MN19413) stream, not an IC311 program at all.  It is
	// also the ONLY context that constrains 0x19 (the biquad carries no 0x19,
	// the LFO does not enumerate it).
	//
	// RE-RUN AT THE CORRECTED POLARITY THE SAME HARNESS SCORES 0 OF 5832 -- and
	// that zero is NOT a refutation either.  Its `Line' reads and writes ONE
	// cell and advances once per frame, so it silently requires READ-before-
	// WRITE in program order; corrected, SINGLE DELAY's w5 (0x60) WRITES and its
	// w9 (0x20) READS, so the read returns the value written in that very frame
	// -- delay 0, the loop is gone.  DEMONSTRATED, not argued.
	//
	// ⇒ THE 108 AND THE 0 ARE BOTH ARTEFACTS.  ACTION 0x19's determination is
	// UNFORCED, and schroeder-topology.md sect. 0-C's conditional challenge is
	// RE-OPENED (its withdrawal had no other support).
	//
	// ★ WHY THE SEMANTIC IS RETAINED ANYWAY, stated so nobody mistakes it for a
	// forcing: nothing REFUTES `tempA <- bus'; what fell is the evidence for it.
	// Withdrawing it would re-trap corpus words on the authority of a harness
	// that provably cannot model the corrected machine -- a method-rule-1 defect
	// pointing the other way.  It is therefore CONSISTENT, like LO_ACT_ACC_BUS
	// above, and MUST NOT be cited as FORCED.
	//
	// ═══════════════════════════════════════════════════════════════════════
	// ★ ROUND 7 RESOLUTION -- analysis/adjudication-round8.md.
	// The paragraph that used to end here said "what re-derives it is a
	// TWO-ADDRESS delay line ... which no tool in dsp/tools has yet.  That is
	// round 6's rank-1 experiment."  ** BOTH HALVES ARE NOW FALSE. **
	//   (a) The line EXISTS: dsp/tools/delayline.py, audited independently by
	//       dsp/tools/adjudicate8.py `harness' -- it delays by ra-wa at both
	//       access orders, says YES to a textbook comb and NO to that comb's
	//       D+1 twin, and represents all 324 ROM lines (324/324 positive D).
	//   (b) IT DOES NOT RE-DERIVE THE FORCING AND CANNOT.  At the FORCED
	//       polarity both of SINGLE DELAY's loops cross w21..w24 (ACTIONs
	//       0x0D/0x0E, undecoded), so no executable window contains a delay
	//       loop.  Every cell of {forced,published} x {push_read,push_any,
	//       latency,blocking} x 4 windows x 7776 machines reads "-- NONE --"
	//       at the forced polarity: AN ABSENCE OF A SEARCH, NOT A ZERO.
	//   (c) And round 6's diagnosis of the 108 is CORRECTED: on a genuine
	//       two-address line the published-polarity window still scores 108,
	//       the SAME 108 machines.  It was a POLARITY artefact all along, not
	//       a memory artefact.
	// WHAT IS MEASURED, by a corpus route containing no delay line at all:
	// ACTION 0x19 is followed by a word SOURCING tempA at a tight modal lag of
	// 1, in 74 of 89 distinct-image sites (base rate 16.0%, best-of-2000
	// ACTION-shuffled null 42.7%).  ⚠ NOT "401 of 402 / 99.8%" -- that counts
	// one word position once per ALGORITHM sharing the image, a 4.79x
	// replication.  DESTINATION = tempA, MEASURED.  SOURCE (bus vs acc) was
	// never tested by any of it and stays OPEN.
	// ⚠ "a SECOND CAPTURE PAIR beside 0x13/0x14" is UNSUPPORTED: 0x13's tempA
	// reader sits at lag EXACTLY 8 (35/40, base rate 5.1%) and 0x19's at lag 1
	// -- disjoint -- and 9 of 38 images use both.  Not refuted; unsupported.
	// ⇒ IT KEEPS SHIPPING under the owner's 2026-07-27 decision.
	// ═══════════════════════════════════════════════════════════════════════
	enum : u8 {
		LO_ACT_ACC_BUS = 0x00,  // the accumulator's input term comes from the BUS
		LO_ACT_ST_BUS  = 0x07,  // mem[ptr] <- bus
		LO_ACT_NONE_2  = 0x12,  // no temp/memory side effect
		LO_ACT_CAP_TA  = 0x13,  // tempA <- bus
		LO_ACT_CAP_TB  = 0x14,  // tempB <- bus
		LO_ACT_NONE_5  = 0x15,  // ditto -- how it differs from 0x12 is OPEN
		LO_ACT_CAP_TA2 = 0x19   // tempA <- ??? : ships on the OWNER'S DECISION
		                        // of 2026-07-27.  !! The DESTINATION is NOT
		                        // MEASURED.  This comment used to claim it was
		                        // ("74/89, lag 1"); that statistic FAILS ITS
		                        // OWN CALIBRATION 0 of 2 -- for 0x13 (tempA)
		                        // tempA and tempB tie and mem beats both, and
		                        // for 0x14 (tempB) the WRONG temporary wins by
		                        // 20 points.  It sees motif adjacency, not
		                        // dataflow.  0x19's profile is the cleanest of
		                        // the three, but "cleanest" is not a
		                        // calibrated criterion.  SUCCESSION survives;
		                        // destination does not.  SOURCE open; "second
		                        // capture pair beside 0x13" is UNSUPPORTED.
		                        // See kn5000-roms-disasm analysis/
		                        // capture-signature.md (tools/capture_sig.py)
	};

	static constexpr bool lo_src_anchored(u8 s)
	{
		return s == LO_SRC_MEM || s == LO_SRC_ACC || s == LO_SRC_TA || s == LO_SRC_TB;
	}

	static constexpr bool lo_act_anchored(u8 a)
	{
		return a == LO_ACT_ACC_BUS || a == LO_ACT_ST_BUS || a == LO_ACT_NONE_2
				|| a == LO_ACT_CAP_TA || a == LO_ACT_CAP_TB || a == LO_ACT_NONE_5
				|| a == LO_ACT_CAP_TA2;
	}

	// ---------------------------------------------------------------
	//  ★ hi12 BIT 7 GATES THE BIT-4 STORE.
	//
	//  The biquad validated "bit 4 stores the accumulator and clears it" to
	//  0.094 dB -- but MEASURED, PARAMETRIC EQ contains ZERO words carrying bit 4
	//  and bit 7 together, and all 22 of its store words are (bit7 = 0,
	//  hi12[3:1] = 1).  So the 57 dB never reached the 180 corpus words that have
	//  bit 4 WITH bit 7, and the LFO -- whose three words are all bit7 = 1 --
	//  cannot run at all if they store: 0 of 276480 machines
	//  (dsp/analysis/lfo-ramp.md Part II sect. 8.3), re-confirmed here at 0 of
	//  181440 in a differently-parameterised space.
	//
	//  Three gates survive that falsification, and they AGREE on:
	//      bit7 == 0                     -> store and clear   (the biquad's case)
	//      bit7 == 1 && hi12[3:1] == 1   -> NO STORE
	//      bit7 == 1 && hi12[3:1] == 2   -> store and clear
	//  They DISAGREE on whether the suppressed case still CLEARS, and on what
	//  happens at bit7 == 1 with hi12[3:1] outside {1,2} (13 corpus words, nine
	//  of them the COMPRESSOR's envelope step at hi12[3:1] == 5).  So the device
	//  executes the agreed part and TRAPS the rest -- see alu_decoded().
	//
	//  ★ 2026-07-27, ROUND-4 ADJUDICATION (dsp/analysis/adjudication-round4.md).
	//  Three things above are now measured rather than assumed, and one of them
	//  cost the escape clause in alu_decoded():
	//
	//   1. bit 7 REALLY IS IN THE CONDITION, and that is now FORCED rather than
	//      assumed.  Classes (0,1) and (1,1) differ in bit 7 and in nothing
	//      else; the biquad needs (0,1) to store (suppressing it is 51.090 dB
	//      wrong) and the LFO needs (1,1) not to.  store-gate.md item C runs
	//      all NINE conditions of its enumeration against both witnesses and
	//      exactly TWO survive -- `b7 & f31 == 1' (this one) and
	//      `b7 & f31 != 2'.  They differ only where hi12[3:1] is outside {1,2},
	//      which alu_decoded() refuses anyway, so the choice costs ZERO words.
	//
	//   2. WHAT THE SUPPRESSED CASE DOES is FORCED only NEGATIVELY.  Over
	//      19 758 816 machines, 17 928 survive the LFO and NOT ONE writes
	//      mem[ptr] at class (1,1) -- but 21 of 33 effects survive, in three
	//      families: `no memory access', `store -> elsewhere', and ★ `LOAD',
	//      i.e. bit 7 as a memory-port DIRECTION bit.  This code implements
	//      "no store, no clear", which is one point inside that set.  It is
	//      sound ONLY because alu_decoded() now refuses every class-(1,1)
	//      store word outright (guard 7 below).
	//
	//   3. THE "13 CORPUS WORDS" IS CORRECT AND store-gate.md item F's
	//      falsification of it IS WITHDRAWN.  Both numbers are right and they
	//      count different sets: 13 over the 3057-word corpus this comment
	//      names (38 distinct body images PLUS the 83-word resident kernel),
	//      11 over the 38 body images alone, which is what gate_settle.py's
	//      images() walks.  The kernel contributes the other 2.
	//      MEASURED: adjudicate4.py mirror.
	//      What SURVIVES from item F is the price: of those 13, ten trap on
	//      hi12[3:1] > 2 and the other three (`090.A.00.1D5', `090.2.FB.40E',
	//      `090.A.01.1C8') are refused by guard 7 -- so settling the CONDITION
	//      changes the emulated machine by ZERO words.
	// ---------------------------------------------------------------
	static constexpr u16 HI_B7 = 1 << 7;

	static constexpr bool st_suppressed(u64 w)
	{
		return (hi12(w) & HI_B7) && hi_f31(hi12(w)) == 1;
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
	//     class 1 is where the external delay-DRAM family lives (this line said
	//     "the external-DRAM bracket" until 2026-07-26; the OPEN/CLOSE bracket
	//     reading is withdrawn -- R1 FORCED that the pair is a READ and a WRITE.
	//     The GUARD is unaffected: it only ever cared that class 1's addr8 is
	//     not a pointer delta).  Zero corpus words
	//     of any other class pass the routing guard anyway, so this costs
	//     nothing and prevents the category error above.
	//  2. ROUTING.  Both halves of lo12 must be anchored, and neither the
	//     pointer-mode bit (5) nor the bit-11 MODIFIER may be set.  Bit 11 is
	//     rejected because it is UNMODELLED on an ALU route, NOT because it is
	//     part of an opcode: PROVEN BY CONSTRUCTION it is a separately-assembled
	//     flag (see lo_imm()), so `0x021' and `0x821' are one route plus a
	//     modifier.  A future decode of the modifier widens this guard; it does
	//     not add two new codes.
	//  3. OPERATION.  hi12[3:1] must be one the biquad determines.  HI_ACC_HOLD
	//     is admitted ONLY on class 8: that is the one word the biquad shows it
	//     on, "the accumulator is unchanged there" is what the reconstruction
	//     DETERMINES, and the LFO says the same code does something visible
	//     elsewhere (notes/dsp-alu-applied.md sect. 2.3 enumerates the two
	//     survivors, a 2^23 AND and a conditional subtract -- both of which ARE
	//     the identity on a completed biquad sum, which is why executing this
	//     one word as "unchanged" is correct under either).
	//  4. FORMAT.  A C-format word has no class4 and no addr8 at all, so every
	//     guard below is meaningless there.  MEASURED, and it BIT: without this
	//     test `C00.A.47.407' -- the frame terminator -- reads as class A with an
	//     anchored route (src 0x10 = acc, action 0x07 = store the bus) and an
	//     hi12[3:1] of 0, and was executed as a multiply-and-store.  One word of
	//     3057, and the last word of every frame.
	//  5. STORE TARGET.  hi12 bit 4's destination is MODE-DEPENDENT and mem[ptr]
	//     is the MODE-2 target (R2, dsp/analysis/r2-output.md sect. 1/4.4 -- the
	//     universal reading manufactures four dead stores in the 23-word output
	//     stage).  A bit-4 word outside mode 2 therefore has an UNPROVEN
	//     destination and must keep trapping.  MEASURED: this removes ZERO words
	//     from the executable set -- no class-8 word in the corpus carries bit 4
	//     -- so it costs nothing and closes the hole before it opens.
	//  6. ...AND THE SAME IS TRUE OF ACTION 0x07, which is the DEFECT TWIN of
	//     guard 5 and was left open by it.  `LO_ACT_ST_BUS' means "write the
	//     operand to A DESTINATION", and which destination is again the MODE:
	//     `2C7' on a mode-1 escape word is the external DELAY-RAM write, and the
	//     output stage's four `L=07' words (`087 0C7 107 287') write the register
	//     /port space (dsp-alu-structure.md sect. 6).  exec_alu() writes mem[ptr]
	//     for this action unconditionally, and class 8 is MODE 0 -- so a class-8
	//     `L=07' word would have been an invented D-RAM write.
	//     PREDICT-THEN-CHECK: predicted this was already firing; it is NOT.
	//     MEASURED over the 3057-word corpus -- of the 303 executing `L=07' words,
	//     303 are mode 2 and 0 are not.  So, exactly like guard 5, this costs ZERO
	//     words and closes a hole before it opens rather than fixing a live bug.
	//     ★ AND IT NOW HAS A POSITIVE REASON, not just a precautionary one
	//     (dsp/analysis/output-stage-decode.md item J, FORCED).  On a MODE-1 word
	//     ACTION 0x07 does NOT write `reg[addr8]': the output stage's `w72' is
	//     `000.1.06.087' and register 0x06 is the unit-0 OUTPUT LEVEL, written
	//     once by the firmware's EFF_VolumeLoop after linking (PROVEN BY
	//     CONSTRUCTION) and carrying the user's effect depth.  If ACTION 0x07 on
	//     a mode-1 word wrote the addressed register, that depth would survive
	//     exactly ONE frame.  So the guard is not merely cheap -- widening it
	//     would be wrong.  (Stated escape, not excluded: SRC 0x02, undecoded,
	//     might carry the level itself and make the write an identity.)
	//  7. ★ THE BIT-4 STORE GATE, and it is the first guard here that COSTS
	//     WORDS.  hi12 bit 7 suppresses the store (see HI_B7 above).  A bit-4
	//     word carrying bit 7 executes ONLY at hi12[3:1] == 2; everything else
	//     traps.
	//
	//     ★ THIS USED TO CARRY AN ESCAPE CLAUSE AND THE ESCAPE IS WITHDRAWN
	//     (2026-07-27, dsp/analysis/adjudication-round4.md sect. 6).  It read:
	//
	//        "bit7 && hi12[3:1] == 1 -> the store is suppressed (3 of 3), but
	//         whether the CLEAR still fires is disputed.  It is UNOBSERVABLE
	//         exactly when the ACTION is LO_ACT_ACC_BUS, because that
	//         substitutes the bus for the accumulator's own feedback term and
	//         the old accumulator cannot reach the result."
	//
	//     The argument is UNDER-ENUMERATED.  It covers the two gates whose
	//     clear is taken BEFORE the ALU or not at all; it does NOT cover
	//     `b7_f31_1_clrlate', the third surviving gate, which defers the clear
	//     to AFTER the word's own ALU step.  A clear taken after the ALU sets
	//     the result to zero WHATEVER the ACTION was, so it is visible at
	//     exactly the words the escape admitted.  store-gate.md sect. 4 makes
	//     this worse rather than better: the class-(1,1) survivor set is 21
	//     effects and its first family is `-/clr:{never,before,after}'.
	//
	//     The word must therefore keep trapping (the standing rule: losing a
	//     decode is acceptable, shipping a guess is not).
	//
	//     ★ AND THE PRICE IS ONE WORD, MEASURED, NOT 107.  The old comment said
	//     "138 at (1,1) of which 107 carry ACTION 0x00 and execute".  They do
	//     not execute: 106 of the 107 are refused by the SRC/ACTION anchoring
	//     guard above (SRC 0x1C x46, SRC 0x00 x31, SRC 0x08 x29, ACTION 0x1A,
	//     ACTION 0x0E -- store-gate.md item G).  Exactly ONE corpus word ever
	//     reached the escape: `092.A.01.1C0', the LFO ramp step at header
	//     I-RAM 37, slot 37 of the cold-boot frame.  It becomes PARTIAL.
	//
	//     MEASURED over the 3057-word corpus: 708 words carry bit 4 -- 528 at
	//     bit7 = 0 (unchanged), 29 at (bit7, f31) = (1, 2) (unchanged, and none
	//     of them decodes today), 138 at (1, 1) (ALL trap now; 1 of them used
	//     to execute), and 13 at (1, f31 outside {1,2}) which trap.
	//     (The old "707/527" was one word short; adjudicate4.py mirror prints
	//     the census for the full corpus, the bodies and the kernel separately.)
	// ---------------------------------------------------------------
	//======================================================================
	//  ★★★ THE SPECULATIVE ISA -- OPT-IN, DEFAULT OFF, 2026-07-28.
	//
	//  Everything this predicate admits BEYOND alu_decoded() is a RESEARCHED
	//  GUESS, not a decoding.  It exists because a frame is discarded the moment
	//  ANY word traps, so applying settled fields one at a time can never make
	//  the emulated DSP audible: with the conservative gate, 100.00 % of
	//  1 200 001 frames trapped and 0 returns were usable.
	//
	//  Of the 123 distinct word forms the device traps, the research model
	//  executes 58 under the shipped semantics and 114 with these readings --
	//  so 56 forms are researched but unapplied, and they are what this admits.
	//
	//  EVERY reading here is recorded, with its evidence and its label, in
	//  kn5000-roms-disasm/dsp/analysis/unblocking-and-discriminators.md.  The
	//  strongest (f31 == 2 does not write P) reproduces 14 of 19 ROM LFO ramp
	//  constants against 11; most of the rest have NO independent support at all
	//  and were chosen only because they let the corpus execute.
	//
	//  ⛔ DO NOT PROMOTE ANY OF THIS INTO alu_decoded() WITHOUT ITS OWN EVIDENCE.
	//======================================================================
	static constexpr bool alu_decoded_speculative(u64 w)
	{
		if (alu_decoded(w))
			return true;
		if (c_format(w))
			return true;                        // 13-bit immediate -> acc (dest OPEN)
		if (lo12(w) & 0x800)
			return true;                        // the alternate lo12 encoding:
		                                        // addressing only, no ALU effect
		const u8 cl = class4(w);
		if (cl != 2 && cl != 8 && cl != 0xa && cl != 1 && cl != 4 && cl != 9)
			return false;
		return true;
	}

	static constexpr bool alu_decoded(u64 w)
	{
		if (c_format(w))                        // bits [24:12] are one immediate
			return false;
		const u8 cl = class4(w);
		if (cl != 2 && cl != 8 && cl != 0xa)
			return false;
		if (lo12(w) & 0x800)                    // the bit-11 MODIFIER: see lo_imm().
			return false;                       // Not part of the code -- simply not
		if (lo_ptrmode(w))                      // modelled on an ALU route yet.
			return false;
		if (!lo_src_anchored(lo_src(w)) || !lo_act_anchored(lo_act(w)))
			return false;
		if ((hi12(w) & HI_ST) && (class4(w) & 7) != 2)
			return false;                       // bit-4 target unproven off mode 2
		if (lo_act(w) == LO_ACT_ST_BUS && (class4(w) & 7) != 2)
			return false;                       // ...and neither is action 07's

		if ((hi12(w) & HI_ST) && (hi12(w) & HI_B7))
		{
			// guard 7 -- the ONLY case the surviving gates settle is
			// hi12[3:1] == 2.  The ACTION-0x00 escape at hi12[3:1] == 1 was
			// withdrawn 2026-07-27: a clear deferred past the ALU is visible
			// there too, so the case is not settled.  See above.
			if (hi_f31(hi12(w)) != 2)
				return false;
		}

		switch (hi_f31(hi12(w)))
		{
		case HI_ACC_LOAD: case HI_ACC_ADD: return true;
		case HI_ACC_HOLD: return cl == 8;
		default: return false;
		}
	}

	// ---------------------------------------------------------------
	//  THE REGISTER-LOAD FAMILY -- `hi12 == 0x801' IS NOT AN ALU OPCODE.
	//
	//  K3 (dsp/analysis/k3-pointers.md sect. 8 item 1): with class4 == 0 and a
	//  `0x_2x' selector this word is a REGISTER WRITE and nothing else.  Nine
	//  corpus words carry hi12 == 0x801 (6 header, 2 output stage, 1 body) and a
	//  tenth, `859.0.86.822', is the same form with other microword bits set.
	//  They must be dropped from any lo12-as-ALU-route modelling -- which the
	//  class guard above already does, but only by accident of class4 == 0;
	//  naming the family makes the exclusion deliberate and survivable.
	//
	//  hi12 is NOT part of the predicate.  It cannot be: `859.0.86.822' is the
	//  same register-write form and its hi12 is 0x859, because hi12 is a
	//  horizontal microword and this word ALSO carries bit 4 (the store).  That
	//  combination is exactly why it is NOT decoded below: it names a register
	//  AND carries a store whose target, off mode 2, is unproven.  It traps.
	//
	//  WHICH register each selector names:
	//      0x21   a C-RAM POINTER -- MEASURED (K3 sect. 4.1): its three in-program
	//             payloads 0x70 / 0x50 / 0x90 are three of the FOUR structural
	//             bases of the host's own C-RAM map, P ~ 4e-6 under a uniform
	//             null.  It is NOT the implicit coefficient cursor -- FORCED
	//             (K3 sect. 4.2): if it were, CHORUS's `094.A.00.200' would read
	//             C-RAM[0x71] instead of the wrap constant the host puts at
	//             C-RAM[0x01].  So C-RAM has at least two independent pointers.
	//             ★ This WITHDRAWS "the body's operand pointer is the 0x821
	//             register" (notes/kn5000-dsp-pointer.md headline 2).
	//      0x25   the DELAY-DESCRIPTOR pointer, tag-0x4C space -- PROVEN BY
	//             CONSTRUCTION in both halves (encoding from Sub CPU writer
	//             LABEL_038922, space from R3).
	//      0x20 / 0x22 / 0x27   OPEN.  0x27's D-RAM-origin assignment was
	//             FALSIFIED (0 of 85 streams; isa-adjudication.md sect. 5.1).
	//
	//  ★ A RESIDUAL TENSION, STATED RATHER THAN SMOOTHED OVER.  Selector 0x21
	//  WITHOUT the modifier is the cursor rewind -- MEASURED on algo 39
	//  (PARAMETRIC EQ), whose class-A count at its ten section starts runs
	//  0,6,12,18,24 | rstcur | 0,6,12,18,24.  Selector 0x21 WITH the modifier
	//  loads a pointer that is FORCED not to be that cursor.  Two readings
	//  survive and neither is picked here:
	//      (a) 0x21 names the C-RAM ADDRESSING UNIT, and the modifier chooses
	//          "load the payload into the pointer" vs "rewind the cursor";
	//      (b) in this family bit 11 IS part of the selector after all, and the
	//          `INC 8, WA' construction is only how the assembler spells it.
	//  What is settled either way: they are not two unrelated 12-bit codes, and
	//  the write targets are different registers.
	// ---------------------------------------------------------------
	enum : u8 {
		LO_SEL_CP  = 0x21,      // a C-RAM pointer (NOT the cursor)
		LO_SEL_DSC = 0x25       // the delay-descriptor pointer (tag 0x4C)
	};

	static constexpr bool is_regload(u64 w)
	{
		if (c_format(w))            return false;
		if (class4(w) != 0)         return false;   // the writer hard-zeroes this nibble
		if (lo_mid(w) != 0)         return false;   // 0 at all 10 corpus sites
		switch (lo_sel(w))
		{
		case 0x20: case 0x21: case 0x22: case 0x25: case 0x27: return true;
		default: return false;
		}
	}

	// the three whose REGISTER and MODIFIER are both established.  The store bit
	// disqualifies: a register write that also stores is a register write with an
	// UNPROVEN second effect (see 859.0.86.822 above).
	static constexpr bool is_ldptr(u64 w)
	{ return is_regload(w) && !(hi12(w) & HI_ST) && lo_sel(w) == LO_SEL_CP && lo_imm(w); }
	static constexpr bool is_rstcur(u64 w)
	{ return is_regload(w) && !(hi12(w) & HI_ST) && lo_sel(w) == LO_SEL_CP && !lo_imm(w); }
	static constexpr bool is_ldptrd(u64 w)
	{ return is_regload(w) && !(hi12(w) & HI_ST) && lo_sel(w) == LO_SEL_DSC && lo_imm(w); }

	// ---------------------------------------------------------------
	//  THE PER-UNIT CALL VECTOR (K5, dsp/analysis/k5-output-stage.md sect. 2.4).
	//  DETERMINED: lo12 0x445 / 0x446 are the ONLY two I-RAM words the host ever
	//  rewrites (I-RAM 64 and 71), they are written by EFF_Link / EFF_Disconnect
	//  indexed by effect unit, and the four values decode to 84/42 (unit 0) and
	//  200/50 (unit 1) -- the I-RAM load address of every unit-0 / unit-1 body
	//  (91/91 streams) and the first word of that unit's own header setup block.
	//  The SOURCE field is open; the DESTINATION is not.
	// ---------------------------------------------------------------
	static constexpr bool is_vector_lo12(u16 lo) { return lo == 0x445 || lo == 0x446; }
	static constexpr int  vector_unit(u16 lo)    { return (lo == 0x446) ? 1 : 0; }
	static constexpr bool is_setvec(u64 w)       { return is_c40(w) && is_vector_lo12(lo12(w)); }

	// ---------------------------------------------------------------
	//  THE EXTERNAL DELAY-DRAM FAMILY -- and why the C-format guard is not
	//  optional.  R2's predicate is `addressing mode 1 WITH the format escape'
	//  and it is exceptionless over the corpus (mode 1 without the escape is the
	//  internal register file, 324/324).  But `hi12[11:8] == 0xC' ALWAYS carries
	//  bit 11, so without a C-format guard three immediate loads walk straight
	//  in -- C40.1.80.000, C40.1.E0.451, C4A.1.C0.820 -- and that is exactly the
	//  contamination that FALSIFIED R3's cursor-counting headline
	//  (isa-adjudication.md sect. 1: C40.1.80.000 and C40.2.C0.000 are the SAME
	//  instruction on the SAME destination register, differing only in the
	//  immediate; they read class4 1 and 2 because bit 8 of that immediate
	//  differs).  ANY predicate that selects DRAM words by class4 alone is wrong.
	//  NOT decoded: the address is a descriptor cell reached through an implicit
	//  cursor, so it is not in the word.
	//
	//  DIRECTION -- FORCED, and it is the REVERSE of what this file used to say
	//  (dsp/analysis/adjudication-round5.md; the reasoning is spelled out beside
	//  the annotation in upd6383d.cpp).  `addr8' bit 6 selects it and 0x60 is the
	//  WRITE.  Applied ONLY over the addr8 values the rule was validated on --
	//  0x20 and 0x30 are READ, 0x60 is WRITE, anything else keeps trapping.
	// ---------------------------------------------------------------
	static constexpr bool is_dram(u64 w)
	{ return (hi12(w) & HI_ESC) && class4(w) == 1 && !c_format(w); }

	//  'R' = delay-DRAM read, 'W' = write, 0 = outside the validated addr8 set.
	static constexpr char dram_dir(u64 w)
	{ return (addr8(w) == 0x20 || addr8(w) == 0x30) ? 'R' : (addr8(w) == 0x60) ? 'W' : 0; }

	// bit 23 (== class4 bit 3) is the CURSOR-FETCH enable.  It is NOT a
	// multiply enable -- that reading was CORRECTED: 18 of the phaser's 20
	// all-pass sections contain no cursor-fetching word at all and they still
	// need gains (notes/kn5000-dsp-axes.md sect. 2.2, sect. 1).  NOT in the
	// C-format family: there bit 23 is a bit of the 13-bit immediate.
	static constexpr bool cursor_fetch(u64 w) { return BIT(w, 23) && !c_format(w); }

	// ---------------------------------------------------------------
	//  ★ FETCH IS NOT ADVANCE (K4, FORCED -- dsp/analysis/k4-cursor.md item I).
	//
	//  bit 23 says a coefficient is FETCHED; only `class4 == 0xA' moves the
	//  cursor ON.  The PARAMETRIC EQ body has TEN class-8 words (804.8.16.415,
	//  one per biquad section) sitting inside a cursor map proven to the bit at
	//  6 cells per band; if class 8 advanced, band k would start at cell 7k
	//  instead of 6k and all 60 named roles would shift.  So the `cur+'
	//  annotation on a class-8 word is WRONG -- it must read `cur'.
	//
	//  MEASURED, and split by region because a core must not over-generalise:
	//      BODIES (2974 words)  bit 23 by class:  8 -> 42,  A -> 822, nothing else
	//      KERNEL    (83 words)  8 -> 2, 9 -> 4, A -> 21, C -> 1, D -> 1
	//  K4's claim is body-scoped and exact; `bit 23 => class 8 or A' is NOT true
	//  of the kernel.  The C-format guard also matters here: 3 of the kernel's
	//  bit-23 words are C-format, where class4 is immediate data.
	// ---------------------------------------------------------------
	static constexpr bool coeff_consumer(u64 w) { return class4(w) == 0xa && !c_format(w); }

	// ---------------------------------------------------------------
	//  ★ THE ADDRESS GENERATOR IS DECODED EVEN WHERE THE ALU IS NOT.
	//
	//  Two of this machine's addressing effects do not read `lo12' AT ALL:
	//
	//      ptr_postinc()     `class4 & 7 == 2'  ->  p += (s8)addr8   [MEASURED]
	//      coeff_consumer()  `class4 == 0xA'    ->  cursor++         [FORCED, K4]
	//
	//  They therefore do not need the ALU decode, and K6 already relied on exactly
	//  that to walk the input stage's pointer.  Restricting them to the twelve
	//  whitelisted words was NOT a safety property -- it was a LIVE DEFECT, and of
	//  the same family as the one the ALU pass caught: the ~92 words that DO
	//  execute were addressing D-RAM and C-RAM through a generator that had
	//  skipped every undecoded word's contribution.
	//
	//  MEASURED on the cold-boot frame (285 slots, kernel + CHORUS + ROOM REVERB):
	//  the pointer's net displacement was -259 with only the executing words
	//  moving it and is -135 with every word moving it, and the coefficient cursor
	//  advanced 37 times instead of 73.  So a decoded `mac (p),c+' late in the
	//  frame was reading a D-RAM cell ~124 away from the right one and a
	//  coefficient ~36 cells early.  Neither number is a rounding error.
	//
	//  WHAT IS DELIBERATELY *NOT* GENERALISED: hi12 bit 4 (the accumulator store).
	//  That one needs a CORRECT ACCUMULATOR, and the accumulator of a frame full
	//  of undecoded words is not the chip's -- so performing it would write
	//  invented data into real cells.  It stays confined to the K6 twelve, where
	//  the note established which cells it can reach.  The line is: EXECUTE WHAT
	//  ADDRESSES, NEVER WHAT COMPUTES.
	// ---------------------------------------------------------------
	static constexpr bool ptr_postinc(u64 w) { return !c_format(w) && (class4(w) & 7) == 2; }

	// does this word have ANY modelled addressing effect?  A word that has none
	// (a delay-DRAM access, a table lookup, a register-file word) executes
	// NOTHING and stays a pure trap -- its own addressing is undecoded too.
	static constexpr bool has_addressing(u64 w)
	{ return ptr_postinc(w) || coeff_consumer(w) || cursor_fetch(w); }

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
	// device's trap-and-log path uses it).  `at' is the word's I-RAM index when
	// the caller knows it and -1 when it does not; ONLY the C00 self-address
	// check reads it (both C00 words in the machine encode their own address as
	// A*32 + B, 2/2 -- see annotate()).
	static std::string text(u64 word, int at = -1);
};

#endif // MAME_CPU_UPD6383_UPD6383D_H
