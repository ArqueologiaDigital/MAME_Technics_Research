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

    WHAT IS EMITTED -- THREE STATES, NOT TWO
        * a real mnemonic ONLY for the forms listed in DECODED FORMS below,
          each of which carries its source of evidence in a comment;
        * `~word 0x0XXXXXXXXX  {addr: ...}' for the twelve K6 AUDIO INPUT STAGE
          words, whose ADDRESSING is decoded and executed while their ALU is
          still open (notes/dsp-k6-input-stage.md).  The `{addr:}' group is what
          the device really performs: the store enable, the cursor fetch and the
          signed pointer post-increment.  NO MNEMONIC is invented for them --
          naming an operation nobody has decoded is exactly what this file
          refuses to do;
        * `?word 0x0XXXXXXXXX' for everything else, always with the field
          breakdown AND the hi12 flag/residue rendering, plus a structural
          annotation where the corpus has one.  The `?' prefix is deliberately
          greppable: it is the worklist, and it stays the worklist -- a `~word'
          is progress, not an answer.

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

      THE lo12 ALU -- eight values, one uniform operation
          notes/dsp-alu-biquad.md.  lo12 is not an opcode either: two of its
          sub-fields are decoded and the machine needs no per-word accumulator
          op at all.  Every word does the SAME thing:

              L    := bus[ lo12[7:6] ]     00 acc  01 tempA  02 tempB  03 mem[p]
              if hi12 bit 4 :  mem[p] <- acc ; acc := 0     (store AND CLEAR)
              acc  += P ; P := 0                            (P is consumed)
              lo12[3:0] :  3 -> tempA <- L    4 -> tempB <- L    7 -> mem[p] <- L
              if class4 == A :  P := coef[cursor++] * L
              if class4 & 7 == 2 :  p += (s8)addr8

          The eight lo12 values this covers are 1D3/1D4/1D5 (bus = mem[p]),
          407/412/415 (bus = acc), 647 (bus = tempA) and 687 (bus = tempB).
          They are 1146 of the 3057 corpus words.

          EVIDENCE.  The PARAMETRIC EQ's nine-word biquad section is the only
          block in the corpus whose arithmetic is known independently -- the
          firmware designs its coefficients with its own tan()-based bilinear
          designer (notes/kn5000-dsp-biquad-coeffs.md, PROVEN BY CONSTRUCTION),
          so the transfer function it must compute is known exactly.  Running
          the model above on eleven real ROM coefficient banks reproduces that
          transfer function to max 0.074 dB / 4.0 deg, and the residual falls
          with signal level, i.e. it is 24-bit state quantisation and not a
          structural error.  Removing either of the two non-obvious parts --
          the accumulator CLEAR that rides on hi12 bit 4, or the one-bit right
          shift on the tempB path -- costs 57 dB and 77 dB respectively.

          This SUPERSEDES the three hi12-specific forms it grew out of
          (202.A.dd.1D5 mac, 202.A.dd.1D4 mac.lb, 212.A.dd.407 mulst), which
          the 19,674,720-point search of notes/kn5000-dsp-semantics.md sect. 3.1
          determined.  Nothing that search determined is contradicted; what
          changes is that its per-word "accumulator op" table was an artefact of
          a hypothesis space that never offered a store-and-clear, and that its
          144 residual survivors are cut to 1 by the ENCODING (words [2] and [4]
          of the section are the same 36-bit word except for addr8, so they
          cannot carry two different latch stores).

          STILL OPEN inside lo12: bits[11:8], bit 4, and the difference between
          OP codes 0x2 and 0x5 -- the biquad cannot see it, because 0x412 always
          carries hi12 bit 4 in it and 0x415 never does.

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
//  K6 -- THE AUDIO INPUT STAGE, I-RAM 0..11 (notes/dsp-k6-input-stage.md)
//
//  ADDRESSING DECODED, ALU NOT.  Every one of these twelve words has a FORCED
//  pointer/store/cursor effect and an OPEN arithmetic one, so they get their own
//  classification rather than being lumped in with either the decoded forms or
//  the worklist.  The cell names are relative to `X', the data pointer at
//  PC-restart; the note's pointer walk (sect. 3) is reproduced in the comments
//  so a reader can check the table without the note in hand.
//
//  `iw1' is a C-format word: no class4, no addr8, no memory operand and no
//  cursor effect, so there is nothing for it to do to the input path.  Its
//  13-bit immediate 0x0E0 = 7 x 32 names I-RAM 7, the first word of the second
//  block.  It is listed here as an explicit SAFE NO-OP rather than left to trap,
//  because a trap would stop the frame's accounting dead in the middle of a
//  stage whose other eleven words are understood.
// ---------------------------------------------------------------------------
struct k6_input_word
{
	u64         word;
	const char *role;
};

const k6_input_word K6_INPUT_STAGE[] =
{
	{ 0x09220120dULL, "K6 input stage, header w0: ST mem[X+0], p+1 -- the epilogue's w80/w81 read X+0 this same frame" },
	{ 0xc0a0e0000ULL, "K6 input stage, header w1: C-format, imm13 0x0E0 = 7*32 -> I-RAM 7 = block B; SAFE NO-OP (no memory, pointer or cursor effect)" },
	{ 0x084202680ULL, "K6 input stage, header w2: read mem[X+1], p+2 -- X+1 is the one-frame feedback cell the epilogue's w79 wrote" },
	{ 0x0122ff1ceULL, "K6 input stage, header w3 (= epilogue w79): ST mem[p], p-1; ALU UNKNOWN" },
	{ 0x2042021ceULL, "K6 input stage, header w4: *** THE PORT READ, block A *** mem[X+2] is an AUDIO INPUT LATCH (read-never-written by all 3057 words); p+2" },
	{ 0x202a00448ULL, "K6 input stage, header w5: read mem[X+4], p+0, cursor+1; ALU UNKNOWN" },
	{ 0x400a00419ULL, "K6 input stage, header w6: END OF BLOCK A (falls through), read mem[X+4], p+0, cursor+1" },
	{ 0x090a011c8ULL, "K6 input stage, header w7: ST mem[X+4], p+1, cursor+1 -- X+4 is a one-frame state cell (read at w5/w6, written here)" },
	{ 0x0842011c0ULL, "K6 input stage, header w8: *** THE PORT READ, block B *** mem[X+5] is an AUDIO INPUT LATCH; p+1" },
	{ 0x0122ff1d5ULL, "K6 input stage, header w9: ST mem[X+6], p-1 -- the only input-stage product the header's mix block consumes" },
	{ 0x282a01417ULL, "K6 input stage, header w10: read mem[X+5] a SECOND time, p+1, cursor+1; ALU UNKNOWN" },
	{ 0x400201447ULL, "K6 input stage, header w11: END OF BLOCK B (falls through), read mem[X+6], p+1 -- the pointer leaves at X+7" }
};

// the two whose D-RAM operand IS a latch (table indices 4 and 8 above)
constexpr u64 K6_PORT_READ_L = 0x2042021ceULL;      // 204.2.02.1CE, header w4, cell X+2
constexpr u64 K6_PORT_READ_R = 0x0842011c0ULL;      // 084.2.01.1C0, header w8, cell X+5

// ---------------------------------------------------------------------------
//  structural annotations -- MEASURED landmarks whose SEMANTICS are unknown
// ---------------------------------------------------------------------------
const char *annotate(u64 word)
{
	const u16 hi = upd6383_disassembler::hi12(word);
	const u8  cl = upd6383_disassembler::class4(word);
	const u8  ad = upd6383_disassembler::addr8(word);
	const u16 lo = upd6383_disassembler::lo12(word);

	// K6 first: these twelve words have a role the generic annotations below
	// would only blur (three of them would otherwise print as "END OF BLOCK"
	// or "C-format immediate" and nothing else).
	if (const char *k6 = upd6383_disassembler::input_stage_role(word))
		return k6;

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

	// THE ALU.  The three forms that used to be listed here individually --
	// 202.A.dd.1D5 mac, 202.A.dd.1D4 mac.lb, 212.A.dd.407 mulst -- are now
	// special cases of one field decode, and five more lo12 values come with
	// them (notes/dsp-alu-biquad.md).  The hi12/class4 restriction is dropped
	// on purpose: hi12 bit 4 (store) and class4 (multiply / pointer) were
	// already MEASURED as independent controls, so the three old forms were
	// never really hi12-specific -- they were lo12 forms observed at one hi12.
	if (alu_decoded(word) && !lo_ptrmode(word))
		return true;

	return false;
}


//-------------------------------------------------
//  addressing_only / input_stage_role / is_input_latch_read
//  -- K6: the twelve input-stage words, ADDRESSING decoded, ALU not
//-------------------------------------------------

const char *upd6383_disassembler::input_stage_role(u64 word)
{
	for (const auto &e : K6_INPUT_STAGE)
		if (e.word == (word & 0xfffffffffULL))
			return e.role;

	return nullptr;
}


bool upd6383_disassembler::addressing_only(u64 word)
{
	// The three states must stay distinguishable, so a word is `addressing
	// only' ONLY while it is not fully decoded.  That ordering used to be free
	// -- none of the twelve matched any of the six hi12-specific forms -- but
	// the lo12 ALU decode is a FIELD decode, and it claims the stage's
	// `012.A.dd.1D5' (which the old note explicitly excluded because its hi12
	// is 0x012 and not 0x202).  One of the twelve therefore graduates from
	// PARTIAL to DECODED, which is exactly the movement this classification
	// exists to measure.
	return input_stage_role(word) != nullptr && !decoded(word);
}


bool upd6383_disassembler::is_input_latch_read(u64 word, bool &right)
{
	const u64 w = word & 0xfffffffffULL;

	if (w == K6_PORT_READ_L) { right = false; return true; }
	if (w == K6_PORT_READ_R) { right = true;  return true; }

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
		if (hi == 0x000 && lo == 0x000)
			s << "nop";
		else if (hi == 0x801 && lo == 0x821)
			util::stream_format(s, "ldptr   #$%02x", ad);
		else if (hi == 0x801 && lo == 0x021)
			s << "rstcur";
		else
		{
			// THE UNIFORM ALU, rendered as what it is: one operation
			// (acc += P, P consumed) plus a bus source, a side effect and the
			// optional multiply/store/pointer controls that live OUTSIDE lo12.
			//     mnemonic  = mac (class A multiplies) / alu (it does not)
			//     operand   = the bus source, then the lo12[3:0] side effect
			static const char *const SRC[4] = { "acc", "ta", "tb", "(p)" };
			const char *mn = (cl == 0xa) ? "mac" : "alu";
			std::string suffix;
			switch (lo_op(word))
			{
			case LO_OP_CAP_TA: suffix = ".ta"; break;   // tempA <- bus
			case LO_OP_CAP_TB: suffix = ".tb"; break;   // tempB <- bus
			case LO_OP_ST_BUS: suffix = ".st"; break;   // mem[ptr] <- bus
			default:           suffix = "";    break;
			}
			std::string mnem = std::string(mn) + suffix;
			while (mnem.size() < 7)
				mnem += ' ';
			util::stream_format(s, "%s %s", mnem, SRC[lo_src(word)]);
			if ((cl & 7) == 2)
				util::stream_format(s, ",(p)%+d", dd);
			if (hi & HI_ST)
				s << " ; mem[p]<-acc, acc=0";
		}
	}
	else
	{
		// TWO greppable forms, because there are two kinds of not-decoded:
		//   `?word'  nothing is known -- the worklist, unchanged;
		//   `~word'  K6: the ADDRESSING is decoded and executed, the ALU is not.
		// Ten nibbles: a 36-bit word prints as ten, not nine -- an
		// off-by-one-nibble trap that has cost this project time before
		// (notes/kn5000-dsp-encoding.md sect. 0).
		const bool addr_only = addressing_only(word);

		util::stream_format(s, "%s   0x%010X   ; %03X.%X.%02X.%03X",
				addr_only ? "~word" : "?word", word & 0xfffffffffULL, hi, cl, ad, lo);

		// What a `~word' actually DOES when the device executes it: the store
		// enable (hi12 bit 4), the cursor fetch (class4 bit 3) and the signed
		// pointer post-increment, all MEASURED.  Printing it means the trace
		// shows the pointer walk instead of leaving a reader to recompute it.
		if (addr_only)
		{
			if ((hi & 0xf00) == 0xc00)
				s << "  {addr: none -- C-format, SAFE NO-OP}";
			else
				util::stream_format(s, "  {addr: %s mem[p]%s, p%+d}",
						(hi & HI_ST) ? "ST" : "rd", (cl & 8) ? ", cur+" : "", int(dd));
		}

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
