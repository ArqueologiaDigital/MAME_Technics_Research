// license:BSD-3-Clause
// copyright-holders:Felipe Sanches
/***************************************************************************

    upd6383d.cpp

    NEC uPD6383GF digital signal processor -- disassembler.

    *** DRAFT / RESEARCH INSTRUMENT.  THE INSTRUCTION SET IS NOT DECODED. ***

    The chip is the effects DSP of the Technics SX-KN5000 (IC311) and is
    documented -- block diagram and pin table only, no instruction set -- as
    IC302 of the Pioneer CDJ-500 service manual, pages 1-15..1-17.

    WORD FORMAT (MEASURED, notes/kn5000-dsp-encoding.md):
        36 bits, right-aligned big-endian in 5 bytes; bits 36..39 are always 0.
        Working field map (INFERRED, sect. 8 of the same note):

           35                    24 23  20 19        12 11                     0
          +------------------------+------+------------+------------------------+
          |         hi12           |class4|   addr8    |          lo12          |
          +------------------------+------+------------+------------------------+

        `class4' is NOT universal: inside the hi12[11:8]==0xC family and inside
        the host-poke region it is immediate DATA that spans bits [23:12]
        (MEASURED, notes/kn5000-dsp-header.md sect. 6).  This disassembler says
        so in a comment rather than pretending the nibble is a class there.

    WHAT IS EMITTED
        * a real mnemonic ONLY for the forms listed in DECODED FORMS below,
          each of which carries its source of evidence in a comment;
        * `?word 0x0XXXXXXXXX' for everything else, always with the field
          breakdown, plus a structural annotation where the corpus has one.
          The `?' prefix is deliberately greppable: it is the worklist.

    DECODED FORMS (and where each comes from)

      000.2.00.000                    nop
          PROVEN BY CONSTRUCTION: sub-CPU writer LABEL_038922 emits this exact
          bit pattern, setting the class4 nibble to 2 explicitly
          (notes/kn5000-dsp-class2-round2.md sect. 4, headline 7).

      801.0.NN.821                    ldptr   #$NN
          PROVEN BY CONSTRUCTION: the firmware builds these bytes at sub-CPU
          LABEL_0387E6; in the host poke region such a word is always the first
          of a burst, followed by 1..30 data words -- the classic "set the
          pointer, then stream values" idiom (notes/kn5000-dsp-parameters.md
          sect. 2, notes/kn5000-dsp-header.md sect. 7).
          NB: lo12 = 0x820/0x825/0x827 are INFERRED sibling forms selecting
          other pointer registers.  They are NOT decoded here -- inferring the
          family is not the same as knowing which register each one loads.

      801.0.00.021                    rstcur
          Resets the implicit coefficient cursor.  VERIFIED against algo39
          (PARAMETRIC EQ), whose class-A word count at its ten section starts
          runs 0,6,12,18,24 | rstcur | 0,6,12,18,24
          (notes/kn5000-dsp-biquad-map.md sect. 2, generalised and confirmed
          bank-size-wise over 26/38 images in notes/kn5000-dsp-cursor-general.md).

      202.A.dd.1D5                    mac     (p)+dd
      202.A.dd.1D4                    mac.lb  (p)+dd
      212.A.dd.407                    mulst   (p)+dd
          DETERMINED by the exhaustive constraint search of
          notes/kn5000-dsp-semantics.md sect. 3.1: of 19,674,720 enumerated
          semantic assignments, all 144 survivors agree on these three, and the
          recovered interpreter reproduces the transfer function of nine real
          ROM coefficient banks at max|err| = 0.000e+00 (sect. 4).
              mac    :  acc += P ; P = coef[cursor++] * mem[p] ; p += (s8)dd
              mac.lb :  as mac, and latch B <- mem[p]
              mulst  :  mem[p] <- acc ; P = coef[cursor++] * acc ; p += (s8)dd
          The search determined the words at their observed addr8 values (0x00,
          0x01, 0xFF).  Generalising over addr8 rests on the separately MEASURED
          fact that addr8 is a signed pointer post-increment
          (notes/kn5000-dsp-encoding.md sect. 4, the algo-32/34 minimal pair).

    EXPLICITLY NOT DECODED, and why they still get a comment: the terminator,
    the external-DRAM bracket, the all-pass marker, the LFO read, the envelope
    detector, class 8, and the biquad words whose reading the search left
    constrained-to-two.  Those are MEASURED *landmarks* with UNKNOWN semantics;
    they are annotated, never given a mnemonic.

***************************************************************************/

#include "emu.h"
#include "upd6383d.h"


namespace {

// ---------------------------------------------------------------------------
//  structural annotations -- MEASURED landmarks whose SEMANTICS are unknown
// ---------------------------------------------------------------------------
const char *annotate(u64 word)
{
	const u16 hi = upd6383_disassembler::hi12(word);
	const u8  cl = upd6383_disassembler::class4(word);
	const u8  ad = upd6383_disassembler::addr8(word);
	const u16 lo = upd6383_disassembler::lo12(word);

	// end-of-program landmark: 91/91 final words, 0 occurrences elsewhere in
	// 2974 words; addr8 is a UNIT INDEX, not a branch target -- confirmed three
	// independent ways (notes/kn5000-dsp-header.md sect. 3)
	if (cl == 1 && ad == 0x0e)
		return "TERMINATOR, unit 0 -- end-of-frame or return, UNKNOWN";
	if (cl == 1 && ad == 0x0f)
		return "TERMINATOR, unit 1 -- end-of-frame or return, UNKNOWN";

	// external-DRAM (digital delay) bracket: predicts the DRAM-using effects at
	// MCC +0.944 over 38 images (notes/kn5000-dsp-class2-round2.md sect. 1.1)
	if (hi == 0x880 && cl == 1 && ad == 0x60)
		return "external-DRAM bracket OPEN (INFERRED)";
	if (hi == 0x880 && cl == 1 && ad == 0x20)
		return "external-DRAM bracket CLOSE (INFERRED)";
	if (hi == 0x880 && cl == 1 && ad == 0x30)
		return "framing word, carries no DRAM information (MEASURED)";

	// all-pass marker: present in every all-pass-bearing image and no other,
	// MCC +0.881; its POSITION differs between reverb and phaser, so which step
	// of the all-pass it performs is NOT established (class2-round2 sect. 1.3)
	if (word == 0x104200000ULL)
		return "all-pass marker -- step UNKNOWN";

	// pointer-load family siblings (INFERRED, header note sect. 7)
	if (lo == 0x820 || lo == 0x825 || lo == 0x827 || lo == 0x822)
		return "pointer-load family sibling, target register UNKNOWN";

	// class 8: occurs in filter-bearing images and nowhere else (MCC +0.947).
	// The constraint search fixes its POSITION -- between "the sum is complete"
	// and "the sum becomes stored state" -- but not its operation
	// (notes/kn5000-dsp-semantics.md sect. 3.3, sect. 6)
	if (cl == 8)
		return "class 8: post-sum step (rescale/round/saturate?), OPERATION UNKNOWN";

	// hi12 families with corpus-wide roles but no decode
	if (hi == 0x082)
		return "LFO read (INFERRED)";
	if (hi == 0xc40)
		return "envelope detector (INFERRED)";

	// the 3-word table-lookup idiom accounts for every class-4 and class-6 word
	// (53/53/53) and occurs in exactly the 25 images with an LFO or distortion
	// stage, MCC +1.000 (notes/kn5000-dsp-effect-map.md)
	if (cl == 6)
		return "table-lookup idiom, class-6 addr8 = table selector (INFERRED)";
	if (cl == 4 && hi == 0x012)
		return "table-lookup idiom, third word (INFERRED)";

	// P-consumers / carry latches, from the biquad section (semantics sect. 3.2)
	if (lo == 0x647)
		return "P-consumer, stores latch A (INFERRED)";
	if (lo == 0x687)
		return "P-consumer, stores latch B (INFERRED)";
	if (lo == 0x1d3)
		return "read into carry latch A (INFERRED)";
	if (lo == 0x1d4)
		return "read into carry latch B (INFERRED)";

	// class4 is immediate data, not a class, inside these families
	// (MEASURED, notes/kn5000-dsp-header.md sect. 6)
	if ((hi & 0xf00) == 0xc00)
		return "hi12[11:8]==C: bits [23:12] are a 12-bit IMMEDIATE, not class+addr";
	if ((hi & 0xf00) == 0xa00)
		return "hi12[11:8]==A: host-poke data form, bits [23:12] are immediate";

	return nullptr;
}

} // anonymous namespace


//-------------------------------------------------
//  decoded - is this one of the established forms?
//-------------------------------------------------

bool upd6383_disassembler::decoded(u64 word)
{
	const u16 hi = hi12(word);
	const u8  cl = class4(word);
	const u8  ad = addr8(word);
	const u16 lo = lo12(word);

	if (hi == 0x000 && cl == 2 && ad == 0x00 && lo == 0x000) return true;  // nop
	if (hi == 0x801 && cl == 0 && lo == 0x821)               return true;  // ldptr
	if (hi == 0x801 && cl == 0 && ad == 0x00 && lo == 0x021) return true;  // rstcur
	if (hi == 0x202 && cl == 0xa && lo == 0x1d5)             return true;  // mac
	if (hi == 0x202 && cl == 0xa && lo == 0x1d4)             return true;  // mac.lb
	if (hi == 0x212 && cl == 0xa && lo == 0x407)             return true;  // mulst

	return false;
}


//-------------------------------------------------
//  text - one line for a single word
//-------------------------------------------------

std::string upd6383_disassembler::text(u64 word)
{
	std::ostringstream s;
	const u16 hi = hi12(word);
	const u8  cl = class4(word);
	const u8  ad = addr8(word);
	const u16 lo = lo12(word);
	const s8  dd = s8(ad);          // addr8 is a SIGNED pointer post-increment

	if (decoded(word))
	{
		if (hi == 0x000)
			s << "nop";
		else if (hi == 0x801 && lo == 0x821)
			util::stream_format(s, "ldptr   #$%02x", ad);
		else if (hi == 0x801)
			s << "rstcur";
		else if (hi == 0x202 && lo == 0x1d5)
			util::stream_format(s, "mac     (p)%+d", dd);
		else if (hi == 0x202)
			util::stream_format(s, "mac.lb  (p)%+d", dd);
		else
			util::stream_format(s, "mulst   (p)%+d", dd);
	}
	else
	{
		// the greppable form.  Ten nibbles: a 36-bit word prints as ten, not
		// nine -- an off-by-one-nibble trap that has cost this project time
		// before (notes/kn5000-dsp-encoding.md sect. 0).
		util::stream_format(s, "?word   0x%010X   ; %03X.%X.%02X.%03X",
				word & 0xfffffffffULL, hi, cl, ad, lo);

		const char *note = annotate(word);
		if (note != nullptr)
			util::stream_format(s, "  [%s]", note);
	}

	return s.str();
}


u32 upd6383_disassembler::opcode_alignment() const
{
	// the host uploads a byte stream of 5-byte records; PC is counted in bytes
	// here so that the same disassembler serves unidasm and the device
	return 1;
}


offs_t upd6383_disassembler::disassemble(std::ostream &stream, offs_t pc, const data_buffer &opcodes, const data_buffer &params)
{
	u64 word = 0;
	for (int i = 0; i < int(WORD_BYTES); i++)
		word = (word << 8) | opcodes.r8(pc + i);
	word &= 0xfffffffffULL;         // bits 36..39 are always zero (MEASURED)

	stream << text(word);

	return WORD_BYTES | SUPPORTED;
}
