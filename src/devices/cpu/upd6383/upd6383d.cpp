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

    *** hi12 IS NOT AN OPCODE ***  (notes/kn5000-dsp-hi12.md, 2026-07-22)
        It is a HORIZONTAL MICROWORD of independent enable bits.  MEASURED by
        Hamming-distance-1 closure: the 54 observed values contain 77 HD-1
        pairs against a popcount-matched null of 43.4 +/- 4.3 (z = +7.9),
        spread over ALL TWELVE bit positions, and two sub-fields are complete
        (bits[3:1] shows 8/8 values under prefix 0x02_, bits[9:8] 4/4 on the
        ..02 base).  Consequently EVERY word here renders hi12 as decoded
        FLAGS PLUS AN EXPLICIT RESIDUE -- never as an opaque number.  A reader
        then sees which bits are set and which are still unexplained, instead
        of 54 opaque values.

           bit 11   FORMAT ESCAPE     bits[10:0] mean something else.  MEASURED
                                      as an escape and not a modifier: removing
                                      it leaves a legal hi12 in only 1 of 9
                                      cases, against 9 of 9 for bits 10 and 4.
           bit 10   END OF PROGRAM    when bit 11 is clear.  See is_end().
           bits 9:8 a proven FIELD, MEANING UNKNOWN (rendered f98=n).  It is
                    NOT an accumulator-op selector -- that was measured and
                    FAILED (hi12.md sect. 8), so no guess is rendered.
           bit 7    SPECULATIVE "index/address domain"; rendered as residue.
           bits 6,5 no reading; rendered as residue.
           bit 4    WRITE ACCUMULATOR -> mem[ptr].  See below.
           bits 3:1 a proven FIELD, MEANING UNKNOWN (rendered f31=n).
           bit 0    "addr8 is an absolute immediate", PROVEN BY CONSTRUCTION
                    for 0x801 only; rendered as residue.

    bit 4 = WRITE THE ACCUMULATOR TO mem[ptr] (MEASURED, hi12.md sect. 4).
        Two investigations that were not looking at bit 4 supply the labels and
        both land the same way: 0x212 = mulst (writes) is 0x202 = mac (does
        not) plus bit 4, and 0x092 = phase accumulate (must write the phase
        back) is 0x082 = LFO read plus bit 4.  The CONTROL is absence and it
        passes: excluding terminators, 0 of 410 words carry bit 4 in the
        classes whose addr8 is provably not a pointer (1, 3, 5, 6, 8), against
        94 expected.  FLAGGED EXCEPTION: the five `612.1.**.000' terminators
        carry bit 4 while their addr8 is a unit index -- annotated below,
        deliberately not explained away.
        ONE BIT OF A 36-BIT WORD IS NOT A DECODE: bit-4 words still print with
        the `?' prefix and stay on the worklist.

    bit 23 = CURSOR-FETCH ENABLE, not multiply-enable (CORRECTION, axes.md):
        18 of the phaser's 20 all-pass sections contain no cursor-fetching
        word at all and they still need gains, so bit 23 cannot be gating the
        multiplier.

    ABSOLUTE C-RAM COEFFICIENT ADDRESSES (MEASURED, disassemble() below):
        Every CLASS-A word (class4 == 0xA) reads one coefficient from the on-chip
        COEFFICIENT RAM (C-RAM) through the implicit cursor.  The cursor's BASE is
        0x00 -- MEASURED across all 16 swept effects in the captured uC-IF stream,
        which frame every coefficient upload identically with `801.0.00.821'
        (notes/kn5000-dsp-origin-capture.md) -- and it advances +1 per class-A
        word, reset to 0 by the `801.0.00.021' rewind (biquad-map.md sect. 2).
        So a class-A word's coefficient has a KNOWN ABSOLUTE C-RAM address:
        0x00 + (number of class-A words since the last rewind or program start).
        This disassembler prints it as `; C-RAM[0xNN]'.  It is emitted ONLY for
        class-A words (the strict coefficient-consumer predicate, NOT bit 23,
        which would over-count the class-8 post-sum step); and ONLY for the
        COEFFICIENT space -- no absolute is invented for the D-RAM state operand,
        whose base (the header's 0x70/0x6C per unit) is still unpinned
        (notes/kn5000-dsp-addressing.md sect. 5, notes/kn5000-dsp-spaces.md).

    WHAT IS EMITTED
        * a real mnemonic ONLY for the forms listed in DECODED FORMS below,
          each of which carries its source of evidence in a comment;
        * `?word 0x0XXXXXXXXX' for everything else, always with the field
          breakdown AND the hi12 flag/residue rendering, plus a structural
          annotation where the corpus has one.  The `?' prefix is deliberately
          greppable: it is the worklist.

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

	// END OF PROGRAM is hi12 bit 10 (bit 11 clear), and the halting word STILL
	// DOES ITS WORK (MEASURED, notes/kn5000-dsp-hi12.md sect. 3): 38 such words
	// in 2974, exactly one per image, all 38 the final word, and stripping the
	// bit leaves an ordinary working hi12 in 9 of 9 cases.  This RETIRES the
	// old `class4==1 && addr8 in {0E,0F}' test, which was recognising a
	// correlate: that addr8 is the UNIT INDEX (confirmed three independent
	// ways, notes/kn5000-dsp-header.md sect. 3), not the halt.
	if (upd6383_disassembler::is_end(word))
	{
		// The UNIT-TAGGED form carries a transfer of control; the untagged
		// form does not.  PROVEN BY CONSTRUCTION (notes/kn5000-dsp-headerdecode.md
		// sect. 2): the header loads registers 821/827/825 TWICE, at I-RAM 42-44
		// and again at 50-52, so unit 0's body must run between them and return --
		// I-RAM 49 is the only word in the window that can transfer.  Conversely
		// the untagged end-of-block words FALL THROUGH, because I-RAM 42-44 is
		// reachable only by falling through I-RAM 41, which is one of them.
		if (cl == 1 && ad == 0x0e)
			return "END OF BLOCK, unit 0 -- CALL/RETURN -- and still performs the rest of the word";
		if (cl == 1 && ad == 0x0f)
			return "END OF BLOCK, unit 1 -- CALL/RETURN -- and still performs the rest of the word";
		return "END OF BLOCK (falls through) -- and still performs the rest of the word";
	}

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

	// The reverb diffuser's 2-permutation, BROKEN by bit 4 (hi12.md sect. 4.4).
	// -semantics.md sect. 6 left "one is d_in <- x+t, the other y <- d_out-t"
	// constrained to two.  Only 0x012 carries bit 4, so 012 is the write -- and
	// it sits immediately before 880.1.20.655, the DRAM-WRITE half of the
	// bracket, a positional corroboration the bit-4 argument did not use.
	// Nine of each in algo 16, one per diffuser.
	if (word == 0x012200680ULL)
		return "all-pass: d_in <- x + t (the WRITE), bit 4 breaks the 2-permutation";
	if (word == 0x000200419ULL)
		return "all-pass: y <- d_out - t (its partner)";

	// The LFO phase accumulator, DECODED as an idiom (notes/kn5000-dsp-chorus.md
	// sect. 2.2, and the wrap constant 29/29 in hi12.md): the increment is
	// f/44100 in Q0.23 and the wrap constant is 0x7FFFFF.
	if (hi == 0x092 && cl == 0xa && lo == 0x200)
		return "LFO: phase += increment (increment = f/44100 in Q0.23)";
	if (hi == 0x094 && cl == 0xa && lo == 0x200)
		return "LFO: phase wrap, consumes the constant 0x7FFFFF (29/29)";

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
		return "LFO / modulation-source read (INFERRED)";
	if (hi == 0xc40)
		return "envelope / level detector (INFERRED)";

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

	// hi12 = 0x212 is the write to mem[ptr] in EVERY class, not just class A
	// (GENERALISED by bit 4 -- notes/kn5000-dsp-hi12.md sect. 7).  The plain
	// store 212.2.00.000 occurs 103 times over 32 of 38 images and needs
	// nothing from lo12 at all, which is itself the corroboration that the
	// store is named in hi12 and not in lo12.
	if (word == 0x212200000ULL)
		return "plain store: mem[ptr] <- acc (nothing asked of lo12)";
	if (hi == 0x212)
		return "writes mem[ptr] (bit 4), class-independent";

	// the same gain multiply in two effect families that agree on nothing else:
	// the phaser's all-pass (102.2.<k>.1CD, gain via mem[ptr]) and the reverb
	// diffuser's (102.A.00.64B, gain via the cursor).  MEASURED that hi12 is
	// CONSTANT across the two while class4 and lo12 both change
	// (notes/kn5000-dsp-axes.md sect. 2.5).
	if (hi == 0x102)
		return "gain multiply (same op in phaser all-pass and reverb diffuser)";

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
//  hi12_text - the horizontal microword, as FLAGS + an explicit RESIDUE
//-------------------------------------------------

//  This is the rendering change the hi12 result forces.  Showing `0x092' tells
//  a reader nothing; showing `ST f31=1 ?7' tells them it is `0x082' plus the
//  store, which is exactly the measured relationship.  Where a bit has no
//  reading it appears as `?n' and is summed into `res=' -- so the unexplained
//  part of every word is visible and greppable rather than hidden inside a
//  number.

std::string upd6383_disassembler::hi12_text(u16 hi)
{
	std::ostringstream s;
	bool first = true;
	auto sep = [&s, &first]() { if (!first) s << ' '; first = false; };

	if (hi & HI_ESC)
	{
		// bit 11 is an ESCAPE, not a modifier: removing it leaves a legal hi12
		// in only 1 of 9 cases (MEASURED, hi12.md sect. 2.4).  Inside the
		// escape, bit 10 is NOT the end marker -- the control is 0xC40, which
		// carries bit 10 yet has mean normalised position 0.570, not 1.000.
		sep(); s << "ESC";
	}
	else if (hi & HI_END)
	{
		sep(); s << "END";
	}

	if ((hi & HI_ST) && !(hi & HI_ESC))
	{
		sep(); s << "ST";
	}

	// proven fields, deliberately rendered as named-but-unexplained
	if (hi_f98(hi)) { sep(); util::stream_format(s, "f98=%d", hi_f98(hi)); }
	if (hi_f31(hi)) { sep(); util::stream_format(s, "f31=%d", hi_f31(hi)); }

	const u16 res = hi_residue(hi);
	if (res)
	{
		for (int b = 11; b >= 0; b--)
			if (BIT(res, b)) { sep(); util::stream_format(s, "?%d", b); }
		sep(); util::stream_format(s, "res=%03X", res);
	}

	if (first)
		s << '-';           // hi12 == 0x000: every enable clear.  27.2 % of the
							// corpus, and the NOP is one of them -- which is
							// what a horizontal microword predicts and an
							// enumerated opcode does not.
	return s.str();
}


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

		// hi12 as FLAGS + RESIDUE.  This is the whole point of the rendering
		// change: instead of 54 opaque values a reader sees which enables are
		// set and which bits nothing accounts for.
		util::stream_format(s, "  hi12{%s}", hi12_text(hi));

		// bit 23 = CURSOR-FETCH enable (CORRECTED reading -- NOT multiply)
		if (cursor_fetch(word))
			s << " cur+";

		const char *note = annotate(word);
		if (note != nullptr)
			util::stream_format(s, "  [%s]", note);

		// FLAGGED EXCEPTION, reported rather than explained away: five
		// `612.1.**.000' words carry the accumulator store while their addr8
		// is the UNIT INDEX, not a pointer.  Either a terminator repurposes
		// addr8 or the halting store goes elsewhere.  It is the only blemish
		// on an otherwise clean bit-4 control (0 of 410), and the project has
		// had to retract results before that were quietly swept up.
		if (is_end(word) && (hi & HI_ST) && cl == 1 && (ad == 0x0e || ad == 0x0f))
			s << "  [!! bit 4 = store, yet addr8 is the unit index -- UNEXPLAINED]";
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

	// ABSOLUTE C-RAM COEFFICIENT ADDRESS (MEASURED -- see the header block).
	// A class-A word consumes the coefficient at cursor position 0x00 + k, where
	// k is the number of class-A words between the last cursor reset and this
	// word.  The cursor is stateful, so recover k by scanning BACKWARD from pc in
	// whole 5-byte words to the nearest `801.0.00.021' rewind (or the start of the
	// buffer, which is the program / per-frame origin where the base is 0x00).
	// Correct regardless of call order -- it does not rely on linear disassembly.
	if (coeff_consumer(word))
	{
		unsigned k = 0;
		for (offs_t p = pc; p >= WORD_BYTES; )
		{
			p -= WORD_BYTES;
			u64 prev = 0;
			for (int i = 0; i < int(WORD_BYTES); i++)
				prev = (prev << 8) | opcodes.r8(p + i);
			prev &= 0xfffffffffULL;
			if (is_rstcur(prev))
				break;              // cursor was reset here: k counts from 0 after it
			if (coeff_consumer(prev))
				k++;
		}
		util::stream_format(stream, "   ; C-RAM[0x%02x] (coeff, base 0x00 MEASURED)", k & 0xff);
	}

	return WORD_BYTES | SUPPORTED;
}
