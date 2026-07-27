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
           bits 3:1 THE ACCUMULATOR OPERATION (notes/dsp-alu-applied.md).
                    Three of the eight codes are read -- 0 = acc <- P,
                    1 = acc += P, 2 = acc unchanged (established on class 8
                    only) -- and the other five are still unknown.  FORCED
                    into hi12 and out of lo12 by the LFO's 092/094 minimal
                    pair, which is identical in class4, addr8 and all twelve
                    lo12 bits.  Still rendered `f31=n' in the field dump, on
                    purpose: see hi12_text().
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

    *** FETCH IS NOT ADVANCE *** (K4, FORCED -- dsp/analysis/k4-cursor.md item I)
        bit 23 says a coefficient is FETCHED.  ONLY `class4 == 0xA' moves the
        cursor on.  The PARAMETRIC EQ body carries TEN class-8 words
        (804.8.16.415) inside a cursor map proven to the bit at 6 cells per band;
        if class 8 advanced, band k would start at cell 7k and all 60 named roles
        would shift.  So the `cur+' annotation this file used to print on every
        bit-23 word is WRONG on class 8: it now prints `cur+' only where the
        cursor really advances and `cur' where it merely fetches.

    ABSOLUTE C-RAM COEFFICIENT ADDRESSES (MEASURED, disassemble() below):
        Every CLASS-A word (class4 == 0xA, C-format excluded) reads one
        coefficient from the on-chip COEFFICIENT RAM (C-RAM) through the implicit
        cursor.  The cursor's BASE is 0x00 for the unit-0 body and 0x90 for the
        unit-1 body -- MEASURED in the captured uC-IF stream -- and it advances +1
        per class-A word, reset by the `...021' rewind (biquad-map.md sect. 2).
        So a class-A word's coefficient has a KNOWN ABSOLUTE C-RAM address:
        base + (number of class-A words since the last rewind or program start).
        This disassembler prints it as `; C-RAM[0xNN]'.  It is emitted ONLY for
        class-A words (the strict coefficient-consumer predicate, NOT bit 23,
        which would over-count the class-8 post-sum step); and ONLY for the
        COEFFICIENT space -- no absolute is invented for the D-RAM state operand,
        whose origin is OPEN again (K3 withdrew the `0x821' assignment and the
        adjudication then falsified its `0x827' replacement, 0 of 85 streams).
        NB the REBASE between units is FORCED to be a per-unit COEFFICIENT-BASE
        REGISTER, not an instruction immediate: an exhaustive search of every
        contiguous 8-to-16-bit field of the ten words that can perform it finds
        the value 0x90 NOWHERE (k4-cursor.md item C/D).

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

      THE REGISTER-LOAD FAMILY -- ONE ROUTE PLUS A MODIFIER, not four codes
          PROVEN BY CONSTRUCTION (dsp/analysis/k3-pointers.md sect. 1.1): the
          Sub CPU writers assemble the low byte of lo12 first and then do a
          literal `INC 8, WA' into byte 3's low nibble, i.e. they build
          `lo12 = 0x800 | 0x021' and `lo12 = 0x800 | 0x025'.  lo12[7:0] is the
          REGISTER SELECTOR and bit 11 is a MODIFIER ("addr8 carries a payload"),
          class4 is left 0 by the writer, and the payload is exactly 8 bits
          because the writer hard-zeroes the nibble above it.  hi12 is NOT part
          of the form -- it is the usual horizontal microword, which is how
          `859.0.86.822' can be the same register write PLUS the bit-4 store.

          NN.821  ldptr   #$NN   a C-RAM POINTER.  MEASURED: its three
                  in-program payloads 0x70 / 0x50 / 0x90 are three of the four
                  structural bases of the host's own C-RAM map (P ~ 4e-6).
                  ★ It is NOT the coefficient cursor -- FORCED -- and it is NOT
                  the D-RAM operand pointer, which WITHDRAWS
                  notes/kn5000-dsp-pointer.md headline 2.
          NN.825  ldptr.d #$NN   the DELAY-DESCRIPTOR pointer, tag-0x4C space.
                  PROVEN BY CONSTRUCTION in both halves (encoding from writer
                  LABEL_038922, space from R3).
          00.021  rstcur         resets the implicit coefficient cursor to its
                  per-unit base.  VERIFIED against algo39 (PARAMETRIC EQ), whose
                  class-A count at its ten section starts runs
                  0,6,12,18,24 | rstcur | 0,6,12,18,24.
          NN.820 / NN.822 / NN.827   the register is OPEN.  NOT decoded -- and
                  `0x827' is where the D-RAM origin was parked until the
                  adjudication falsified it (0 of 85 streams).

      C40.x.xx.445 / .446             setvec  unitN,#A
          The per-unit CALL VECTOR.  DETERMINED (K5 sect. 2.4): lo12 0x445/0x446
          are the ONLY two I-RAM words the host ever rewrites (I-RAM 64 and 71),
          they are written by EFF_Link / EFF_Disconnect indexed by effect unit,
          and the four values are 84/42 (unit 0) and 200/50 (unit 1) -- the load
          address of every unit-0 / unit-1 body (91/91 streams) and the first
          word of that unit's own header setup block.  The ROM's own boot-default
          spelling of these two slots is `011.9.0E.445' / `011.9.0F.446', whose
          SOURCE field is open; those are annotated, not decoded.

      THE ALU -- lo12 ROUTES, hi12[3:1] OPERATES
          notes/dsp-alu-applied.md, which reconciles three concurrent analyses
          (dsp-alu-structure.md, dsp-alu-biquad.md, dsp-alu-crossval.md).  The
          headline FALSIFIES what all three set out to do: lo12 is NOT the ALU
          field.  It is a second horizontal microword carrying the OPERAND
          ROUTING; the accumulator operation is in hi12[3:1].

              L    := src[ lo12[10:6] ]  07 mem[p]  10 acc  19 tempA  1A tempB
              if hi12 bit 4 :  mem[p] <- acc ; acc := 0     (store AND CLEAR)
              hi12[3:1] :  0 -> acc <- P   1 -> acc += P   2 -> acc unchanged
              lo12[4:0] :  13 -> tempA <- L   14 -> tempB <- L   07 -> mem[p] <- L
              if class4 == A :  P := coef[cursor++] * L
              if class4 & 7 == 2 :  p += (s8)addr8

          P is NOT consumed by the add: an MPLY output latch holds until the
          next multiply, and hi12[3:1] decides whether this word takes it.

          EVIDENCE, TWO INDEPENDENT BLOCKS.
          (a) The PARAMETRIC EQ's nine-word biquad section is the only block in
          the corpus whose arithmetic is known independently -- the firmware
          designs its coefficients with its own tan()-based bilinear designer
          (notes/kn5000-dsp-biquad-coeffs.md, PROVEN BY CONSTRUCTION), so the
          transfer function it must compute is known exactly.  The model above,
          run on eight distinct ROM coefficient banks in eleven section
          instances across four programs, reproduces it to max 0.094 dB /
          4.0 deg, and the residual falls with signal level -- i.e. it is
          24-bit state quantisation, not a structural error.  Removing either
          of the two non-obvious parts -- the accumulator CLEAR that rides on
          hi12 bit 4, or the one-bit right shift on the tempB path -- costs
          57 dB and 77 dB.
          (b) The LFO phase accumulator is what puts the operation in hi12 and
          not in lo12.  `092.A.dd.200' and `094.A.dd.200' are identical in
          class4, addr8 and ALL TWELVE lo12 BITS and differ only in hi12[3:1];
          in 12 of 20 images they hit the same D-RAM cell with the pointer
          frozen, and they consume C-RAM[+0] = 0x000072 and C-RAM[+1] =
          0x7FFFFF.  114/2^23 * 44100 = 0.5993 Hz, so those two constants are
          an increment and a 2^23 wrap -- and no single operation applied twice
          with both of them makes a ramp.  FORCED.

          This SUPERSEDES the three hi12-specific forms it grew out of
          (202.A.dd.1D5 mac, 202.A.dd.1D4 mac.lb, 212.A.dd.407 mulst), which
          the 19,674,720-point search of notes/kn5000-dsp-semantics.md sect. 3.1
          determined.  Nothing that search determined is contradicted; what
          changes is that its per-word "accumulator op" table was an artefact of
          a hypothesis space that never offered a store-and-clear, and that its
          144 residual survivors are cut to 1 by the ENCODING (words [2] and [4]
          of the section are the same 36-bit word except for addr8, so they
          cannot carry two different latch stores).

          STILL OPEN.  In lo12: bit 4, 14 of the 18 observed SRC codes, 19 of
          the 24 observed ACTION codes (including the two largest, 0x00 and
          0x0E), and the difference between ACTION 0x12 and 0x15 -- the biquad
          cannot see it, because 0x412 always carries hi12 bit 4 in it and
          0x415 never does.  In hi12: five of the eight [3:1] codes, and
          whether code 2 is a no-op or a wrap that does not fire.

    EXPLICITLY NOT DECODED, and why they still get a comment: the terminator,
    the external delay-DRAM family, the all-pass core, the LFO read, class 8,
    the internal register file, and the biquad words whose reading the search
    left constrained-to-two.  Those are MEASURED *landmarks* with UNKNOWN or
    only PARTLY known semantics; they are annotated, never given a mnemonic.

    *** LABELS WITHDRAWN FROM THIS FILE (2026-07-26 sync pass) ***
    Each of these was emitted for months and each is now known to be wrong.  A
    wrong decode costs more than a missing one, so they are listed rather than
    quietly deleted (dsp/analysis/isa-adjudication.md sect. 9 is the queue this
    pass drains):

      * `hi12 == 0xC40 -> envelope / level detector'.  FALSIFIED at ALL 61
        SITES; it fired on the reverb tank, on CHORUS and on the frame
        terminator's neighbours.  The family is a 13-bit IMMEDIATE LOAD.
      * `880.1.60 / 880.1.20 -> external-DRAM bracket OPEN / CLOSE'.  They are a
        READ and a WRITE (FORCED, R1 F1), and `addr8' does not select the
        direction at all (R3 sect. 6.3).
      * `880.1.30 -> framing word, carries no DRAM information'.  It is the
        FIRST DRAM ACCESS of a body, 37 of 38 distinct images (R3 sect. 6.2).
      * `012.2.00.680 -> d_in <- x + t (the WRITE)' and `000.2.00.419 ->
        y <- d_out - t'.  TWO assignments survive the constraint search; these
        were printed as if settled.
      * `hi12 == 0x212 -> writes mem[ptr], CLASS-INDEPENDENT'.  Bit 4's target
        is MODE-DEPENDENT; the universal reading manufactures four dead stores
        in the 23-word output stage (R2).
      * `hi12[11:8] == 0xA -> host-poke data form'.  `0A aa bb cc dd' is a
        HOST-STREAM packet, not an instruction, and the rule fired on genuine
        in-program words (A00.0.00.041 in CHORUS, A3C.D.9F.287 at I-RAM 78).
      * `cur+' on every bit-23 word.  FETCH IS NOT ADVANCE (K4) -- see above.
      * the C-format family predicate `(hi12 & 0xFFE) == 0xC40'.  That is the
        PAYLOAD rule; the FORMAT is `hi12[11:8] == 0xC'.  Conflating them is
        what let `C00.A.47.407' be decoded and executed as arithmetic.

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
//  NAMED CELLS OF THE INTERNAL REGISTER FILE (addressing mode 1 without the
//  format escape).  ★ BIT 7 OF THE INDEX IS THE EFFECT UNIT -- K4 item G,
//  FORCED, and it resolves the class-1 addr8 lead K6 opened: over the 91
//  well-formed parameter streams the `000.1.NN.000' register selects split
//  perfectly, 368 packets / 23 distinct NN ALL < 0x80 in unit-0 streams and
//  60 / 5 ALL >= 0x80 in unit-1 streams, with 5 of 5 unit-1 numbers being a
//  unit-0 number + 0x80; and the boot blob writes the matched pair
//  000.1.06.000 / 000.1.86.000 back to back.
//
//  NOTE WHAT THIS IS *NOT*: the delay-DRAM sub-ops 0x20 / 0x30 / 0x60 are
//  discriminated by hi12 (the FORMAT ESCAPE), NOT by addr8 bit 7 -- bit 7
//  misclassifies 3 of 324 while the escape classifies 324/324
//  (dsp/analysis/r2-output.md sect. 1.1, k4-cursor.md sect. 3).
// ---------------------------------------------------------------------------
struct reg_role
{
	u8          index;
	const char *role;
};

const reg_role REGISTER_ROLE[] =
{
	{ 0x06, "per-unit OUTPUT LEVEL (PROVEN BY CONSTRUCTION -- the last four host actions of cold boot are setvec unit1,#200 / setvec unit0,#84 / reg 0x06 <- +0.500000 / reg 0x86 <- +0.183992, both cleared at reset)" },
	{ 0x86, "per-unit OUTPUT LEVEL (PROVEN BY CONSTRUCTION -- see 0x06)" },
	{ 0x50, "base of the per-unit STATE BLOCK (MEASURED: in 87 of 91 parameter streams the host's tag-0x15 zero-fill is a CONTIGUOUS run based here; PARAMETRIC EQ's is the 40-cell one, 0x50..0x77 = 5 bands x 2 ch x 4 Direct-Form-I state words)" },
	{ 0xd0, "base of the per-unit STATE BLOCK (MEASURED -- see 0x50; unit 1's run is 3 cells in all 12 reverbs)" }
};

// ---------------------------------------------------------------------------
//  structural annotations -- MEASURED landmarks whose SEMANTICS are unknown
//
//  ★ PRECEDENCE IS LOAD-BEARING.  The C-FORMAT rule must come BEFORE every rule
//  keyed on lo12, class4 or addr8, because in that family class4|addr8 are not a
//  class and a pointer -- they are immediate data.  This file used to have the
//  C-format test at the BOTTOM and got away with it only because the delay-DRAM
//  rule tested `hi12 == 0x880' exactly; widening that family to R2's real
//  predicate makes it a live bug the same day (the reverb's C40.1.80.000
//  matches).  That is precisely the error R3 made and the adjudication caught
//  (dsp/analysis/isa-adjudication.md sect. 1, sect. 7).
//
//  The ONE rule above it is the K6 input-stage whitelist, which matches by exact
//  36-bit word value over twelve individually-reviewed words -- including the
//  one C-format word of the stage, whose role string says what it is.
// ---------------------------------------------------------------------------
std::string annotate(u64 word, int at)
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

	// ---- C-FORMAT FIRST.  bits [24:12] are ONE 13-bit immediate -------------
	if (upd6383_disassembler::c_format(word))
	{
		const u8 a = upd6383_disassembler::c_a(word);
		const u8 b = upd6383_disassembler::c_b(word);

		if (upd6383_disassembler::is_setvec(word))
			return "";                      // decoded(); never reaches here

		// THE PAYLOAD RULE IS FAMILY-LOCAL (K3 sect. 5.3): `A = imm13 >> 5' is
		// MEASURED 57/57 inside (hi12 & 0xFFE) == 0xC40 and 2/11 outside, so the
		// A/B split is asserted only here.  It is NOT extended to
		// C00/C04/C0A/C16/C42/C4A/C64.
		if (upd6383_disassembler::is_c40(word))
			return util::string_format(
					"C-format IMMEDIATE LOAD: A=%d B=%d (imm13 0x%04X = %d*32, MEASURED 57/57 in "
					"this sub-family); destination register lo12=%03X UNKNOWN",
					a, b, upd6383_disassembler::c_imm13(word), a, lo);

		if (hi == 0xc00)
		{
			const char *own = (at >= 0 && a == at) ? "= its own I-RAM address" : "(I-RAM index?)";
			return util::string_format(
					"WAIT / SYNC (INFERRED): A=%d %s, B=%d = the event; both C00 words in the "
					"machine encode their own address (2/2)", a, own, b);
		}

		if (lo == 0x820 || lo == 0x825 || lo == 0x827 || lo == 0x822)
			return util::string_format(
					"C-format word with a pointer-load lo12; the A/B split is NOT established for "
					"this sub-family (B in {0,17,18,23}) -- residue A=%d B=%d shown for the record",
					a, b);

		return util::string_format(
				"C-format: bits [24:12] are one 13-bit IMMEDIATE reaching into hi12 bit 0, not "
				"class+addr; A=%d B=%d", a, b);
	}

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

	// ---- external delay DRAM.  ADDRESS SOURCE and DIRECTION known; the CELL is
	//      still an implicit cursor, so these stay TIER 2 and keep trapping.
	//
	// THE DIRECTION IS NOW FORCED, AND IT IS THE REVERSE OF WHAT THIS FILE USED
	// TO PRINT (dsp/analysis/adjudication-round5.md).  Both sides are named:
	//   * the FIELD: over the 133 non-C-format equal-value descriptor pairs, of
	//     every boolean function of every named field only `addr8' bit 6 and its
	//     own global flip reach zero violations, and bit by bit over all 36 bits
	//     exactly one does (dram-direction.md item B, an exhaustive enumeration).
	//   * the MAP: three POLARITY-FREE oracles -- op-0x67 taps of one algorithm
	//     share a direction; a tap and its own line base oppose; equal-value
	//     pairs oppose -- are simultaneously perfect at exactly ONE of thirteen
	//     phases, the IDENTITY (adjudication-round5 sect. 1; permutation null
	//     0 of 2000).  Phase and polarity are ONE parameter, which is why the
	//     phase had to be settled by tests that cannot see a polarity.
	//   * the POLARITY, twice over: (a) MULTI TAP DELAY has FOUR op-0x67 taps
	//     sharing ONE line base and a multi-tap is one write and N reads -- the
	//     four taps carry addr8 0x20/0x30, the shared base carries 0x60;
	//     (b) at a boundary shared by two ladder segments the READ must take the
	//     aged word BEFORE the write overwrites it, and the earlier access of
	//     all 133 opposite-bit pairs carries bit 6 = 0.
	//   * R1 F1 said the opposite and is FALSIFIED AS STATED, not outvoted: its
	//     acceptance test 2 and F6 bound the DRAM read latency to inside one
	//     8-word repetition, and the descriptor addresses need TWENTY words, so
	//     read_slot = 4 was outside the searched model class.
	//   * R3 sect. 6.3, which this file quoted as REFUTING the addr8 rule,
	//     refutes only its old POLARITY.  Its MULTI TAP observation is (a).
	if (upd6383_disassembler::is_dram(word))
	{
		const std::string base =
				"external delay-DRAM access; address = DESCRIPTOR_CELL[k] + G, from the host bank "
				"behind pointer ...825 / tag 0x4C (R3, PROVEN BY CONSTRUCTION) -- the k-th class-1 "
				"escape word of a body takes the k-th cell of that body's own descriptor block (the "
				"IDENTITY map, FORCED in adjudication-round5 sect. 1), so the address is NOT in "
				"this word";

		std::string role, extra;
		if (ad == 0x20 || ad == 0x30)
		{
			role = "READ";
			extra = "; this end moves with the user's DELAY (ms) knob, and the delay is "
					"READ_CELL - WRITE_CELL";
			if (ad == 0x30)
				extra += "; addr8 0x30 also marks the FIRST DRAM access of a body, 37 of 38 "
						"distinct images (R3 sect. 6.2)";
		}
		else if (ad == 0x60)
		{
			role = "WRITE";
			extra = "; the line BASE -- MULTI TAP DELAY's four taps share exactly one of these, "
					"which is what forces the polarity";
		}
		else
		{
			return base + util::string_format(". DIRECTION OUT OF SCOPE: addr8 0x%02X is outside "
					"the 0x20 / 0x30 / 0x60 the rule was validated on", ad);
		}
		return "external delay-DRAM " + role + " (FORCED, adjudication-round5 sect. 3 -- addr8 bit "
				"6 is the direction field and 0x60 is the WRITE; this REVERSES R1 F1, which bounded "
				"the read latency to one repetition when the descriptors need twenty words)"
				+ extra + ". " + base;
	}

	// ---- the reverb all-pass core (dsp/analysis/r1-allpass-motif.md) --------
	// NOT decoded: TWO role assignments survive the constraint search, and the
	// corpus RANKS -- but does not prove -- the one in which mem[ptr] stages the
	// DRAM write.  The old family-A-only readings ("d_in <- x + t (the WRITE)" /
	// "y <- d_out - t") were printed as if settled; they are WITHDRAWN.
	if (word == 0x104200000ULL)
		return "all-pass core slot 1/6 -- role NOT settled (family B: acc += P; family A: no job at "
				"all).  Outside the reverb all 8 sites follow a class-A multiply-and-store";
	if (word == 0x000200419ULL)
		return "all-pass core slot 2/6 -- one accumulate step; which one is NOT settled";
	if (word == 0x012200680ULL)
		return "all-pass core slot 3/6 -- the bit-4 store takes the accumulator BEFORE this word's "
				"own ALU step (FORCED, R1 F2)";
	if (hi == 0x102 && cl == 0xa && lo == 0x64b)
		return "all-pass core slot 6/6 -- class-A multiply whose multiplicand is a SUM OF TWO "
				"REGISTERS, so lo12 0x64B is a fourth multiplicand route beside mac (0x1D5) and "
				"mulst (0x407) (FORCED under a 2-input ALU, R1 F8)";

	// ---- the per-unit CALL VECTOR, in its canned boot-default source form ---
	if (upd6383_disassembler::is_vector_lo12(lo))
		return util::string_format(
				"writes the unit-%d CALL VECTOR (I-RAM %d) -- DETERMINED destination; this SOURCE "
				"form is the canned boot default, its source field is OPEN",
				upd6383_disassembler::vector_unit(lo), (lo == 0x445) ? 64 : 71);

	// The LFO phase accumulator, DECODED as an idiom (notes/kn5000-dsp-chorus.md
	// sect. 2.2, and the wrap constant 29/29 in hi12.md): the increment is
	// f/44100 in Q0.23 and the wrap constant is 0x7FFFFF.  This PAIR is what
	// forced the accumulator operation into hi12 -- the two words are identical
	// in class4, addr8 and every bit of lo12 (notes/dsp-alu-applied.md sect. 2).
	// The wrap word's own operation is still open, with exactly two survivors:
	// a 2^23 AND and a conditional subtract, both giving 0.5993 Hz on the
	// MEASURED C-RAM[0x00] = 0x72.  Neither is executed.
	if (hi == 0x092 && cl == 0xa && lo == 0x200)
		return "LFO: phase += increment (increment = f/44100 in Q0.23)";
	if (hi == 0x094 && cl == 0xa && lo == 0x200)
		return "LFO: phase wrap, consumes 0x7FFFFF (29/29); AND vs sub-if-ge OPEN";

	// ---- mode 1 WITHOUT the escape = the internal REGISTER FILE -------------
	// R2 sect. 1: the index space is shared with the host's own `000.1.NN.000',
	// which the host stream proves auto-increments.  bit 7 of the index is the
	// EFFECT UNIT (K4 item G, FORCED -- see the REGISTER_ROLE table above).
	// Class 1 and class 9 (= mode 1 plus the cursor fetch) both land here.
	if ((cl & 7) == 1)
	{
		for (const auto &r : REGISTER_ROLE)
			if (r.index == ad)
				return util::string_format("internal register file [%02X] -- %s, unit %d",
						ad, r.role, BIT(ad, 7));
		return util::string_format(
				"internal register file [%02X], unit %d (bit 7 = the unit); this index has no named "
				"role yet", ad, BIT(ad, 7));
	}

	// ---- the REGISTER-LOAD family: one route (lo12[7:0]) plus a MODIFIER ----
	// PROVEN BY CONSTRUCTION that bit 11 is a separate flag (K3 sect. 1.1); the
	// decoded members are handled by decoded() and never reach here, so what is
	// left is the OPEN selectors -- and `859.0.86.822', which is a register write
	// that ALSO carries the bit-4 store.
	if (upd6383_disassembler::is_regload(word))
	{
		// ★ A CONFLICT BETWEEN TWO COMMITTED READINGS, REPORTED NOT RESOLVED.
		// K3 sect. 5.2 says `859.0.86.822' "both names a register AND carries
		// the store", because hi12 bit 4 is set.  But hi12 bit 11 -- the FORMAT
		// ESCAPE -- is set too, and this decoder's own escape rule says that
		// inside the escape bits[10:0] mean something else, which is why
		// hi12_text() does not print `ST' here.  Both cannot be right.  The word
		// is the ONLY site, so neither reading has a second data point.
		const bool esc = (hi & upd6383_disassembler::HI_ESC) != 0;
		return util::string_format(
				"register write: selector lo12[7:0]=%02X, %s (bit 11 is a SEPARATE FLAG -- the "
				"firmware builds it with a literal `INC 8, WA' on top of the low byte).  This "
				"selector's register is OPEN%s",
				upd6383_disassembler::lo_sel(word),
				upd6383_disassembler::lo_imm(word) ? "payload = addr8" : "no payload",
				!(hi & upd6383_disassembler::HI_ST) ? ""
				: esc ? "; hi12 bit 4 is set BUT SO IS THE FORMAT ESCAPE (bit 11), and inside the "
						"escape this decoder does not read bit 4 as the store -- K3 sect. 5.2 reads "
						"it as a store anyway.  CONFLICT, 1 site, UNRESOLVED"
					  : "; and hi12 bit 4 is SET, so it also stores -- to a target that is "
						"mode-dependent and unproven off mode 2 (R2)");
	}

	if (lo == 0x839)
		return "lo12 0x839 -- selector OPEN (K3 sect. 5.4: 'sub-op 3 on register 1' under one field "
				"reading, a sixth register under the other); 2 sites in 3057";

	// class 8: occurs in filter-bearing images and nowhere else (MCC +0.947).
	// The constraint search fixes its POSITION -- between "the sum is complete"
	// and "the sum becomes stored state" -- but not its operation
	// (notes/kn5000-dsp-semantics.md sect. 3.3, sect. 6)
	if (cl == 8)
		return "class 8: post-sum step (rescale/round/saturate?), OPERATION UNKNOWN";

	// hi12 families with corpus-wide roles but no decode.
	// ★ WITHDRAWN HERE: `hi12 == 0xC40 -> envelope / level detector'.  FALSIFIED
	// at ALL 61 SITES (dsp/analysis/k5-output-stage.md sect. 2.3) -- it fired on
	// the reverb tank, on CHORUS and on the frame terminator's neighbours.  The
	// family is a 13-bit IMMEDIATE LOAD and is rendered by the C-format block at
	// the top of this function.
	if (hi == 0x082)
		return "LFO / modulation-source read (INFERRED)";

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

	// The plain store 212.2.00.000 occurs 103 times over 32 of 38 images and needs
	// nothing from lo12 at all, which is itself the corroboration that the store
	// is named in hi12 and not in lo12.  Its TIMING is FORCED (R1 F2): the store
	// takes the accumulator BEFORE the word's own ALU step.
	if (word == 0x212200000ULL)
		return "plain store: mem[ptr] <- acc, taken BEFORE this word's ALU step (FORCED)";

	// ★ WITHDRAWN: `hi12 == 0x212 -> writes mem[ptr], CLASS-INDEPENDENT'.  R2
	// falsified it -- bit 4's TARGET is MODE-DEPENDENT and mem[ptr] is the MODE-2
	// target.  Two mode-1 bit-4 words (w64/w71) have a DETERMINED destination in
	// the REGISTER space, and w60/w61 are adjacent mode-1 stores with no
	// pointer-moving word between them, so under a universal mem[ptr] reading the
	// first is provably dead: the old rule manufactured FOUR DEAD STORES in the
	// 23-word output stage.  Bit 4 is now rendered as the flag `ST' by
	// hi12_text() and given no target unless the mode supplies one.
	if (hi == 0x212 && (cl & 7) == 2)
		return "writes mem[ptr] (bit 4); mode 2, so the target IS the pointer";

	// the same gain multiply in two effect families that agree on nothing else:
	// the phaser's all-pass (102.2.<k>.1CD, gain via mem[ptr]) and the reverb
	// diffuser's (102.A.00.64B, gain via the cursor).  MEASURED that hi12 is
	// CONSTANT across the two while class4 and lo12 both change
	// (notes/kn5000-dsp-axes.md sect. 2.5).
	if (hi == 0x102)
		return "gain multiply (same op in phaser all-pass and reverb diffuser)";

	// ★ WITHDRAWN: `hi12[11:8] == 0xA -> host-poke data form'.  `0A aa bb cc dd'
	// is a HOST-STREAM coefficient packet, not an instruction (PROVEN BY
	// CONSTRUCTION from the Sub CPU writers, dsp/analysis/k5-output-stage.md
	// sect. 1.3), and the rule fired on genuine IN-PROGRAM words where it is
	// meaningless -- A00.0.00.041 in CHORUS and A3C.D.9F.287 at I-RAM 78.  Host
	// packets belong to a host-stream viewer, not to an instruction decoder.
	// (The C-format rule that used to sit beside it is now at the TOP of this
	// function, where its precedence is load-bearing.)
	return "";
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

	// a proven field, deliberately rendered as named-but-unexplained
	if (hi_f98(hi)) { sep(); util::stream_format(s, "f98=%d", hi_f98(hi)); }

	// hi12[3:1] = THE ACCUMULATOR OPERATION (notes/dsp-alu-applied.md), but it
	// stays rendered as the neutral `f31=n' HERE ON PURPOSE.  hi12_text() is a
	// field dump and it is printed for EVERY word, including the class-1
	// external-DRAM words and the escape forms this decode does not reach;
	// printing "acc+=P" on one of those would assert a semantic the word has
	// not been shown to have.  The operation is named in the MNEMONIC instead,
	// which is emitted only for words decoded() admits.
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

	// THE REGISTER-LOAD FAMILY, as ONE ROUTE PLUS A MODIFIER (K3, PROVEN BY
	// CONSTRUCTION).  Three members have both a register and a modifier reading:
	//     sel 0x21 + payload -> ldptr    (a C-RAM pointer, NOT the cursor)
	//     sel 0x21, no payload -> rstcur (the implicit coefficient cursor)
	//     sel 0x25 + payload -> ldptr.d  (the delay-DESCRIPTOR pointer, tag 0x4C)
	// The rest of the family -- selectors 0x20 / 0x22 / 0x27 -- is OPEN and keeps
	// trapping, as does any member carrying the bit-4 store (859.0.86.822).
	if (is_ldptr(word) || is_rstcur(word) || is_ldptrd(word)) return true;

	// setvec -- the per-unit CALL VECTOR write.  DETERMINED destination (K5);
	// the SOURCE field of the canned boot-default form is OPEN, which is why
	// only the C-format `is_setvec' spelling is decoded and the ROM's own
	// `011.9.0E.445' / `011.9.0F.446' are annotated but not.
	if (is_setvec(word)) return true;

	// THE ALU.  alu_decoded() carries the whole predicate and its evidence: a
	// FORMAT guard, a CLASS guard, a ROUTING guard on both halves of lo12, a
	// STORE-TARGET guard, and an OPERATION guard on hi12[3:1].  It replaces a
	// lo12-only whitelist that, because it looked at nothing else, also executed
	// class-1 external delay-RAM words as on-chip arithmetic
	// (notes/dsp-alu-applied.md sect. 3).
	if (alu_decoded(word))
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

std::string upd6383_disassembler::text(u64 word, int at)
{
	std::ostringstream s;
	const u16 hi = hi12(word);
	const u8  cl = class4(word);
	const u8  ad = addr8(word);
	const u16 lo = lo12(word);
	const s8  dd = s8(ad);          // addr8 is a SIGNED pointer post-increment

	if (decoded(word))
	{
		if (is_setvec(word))
		{
			// the four values K5 DETERMINED: 84/42 (unit 0) and 200/50 (unit 1)
			const int unit = vector_unit(lo);
			const u8  a    = c_a(word);
			const char *m  = nullptr;
			if (unit == 0 && a ==  84) m = "LINK -- unit-0 body entry";
			if (unit == 0 && a ==  42) m = "DISCONNECT -- header unit-0 setup block (runs, returns, no body)";
			if (unit == 1 && a == 200) m = "LINK -- unit-1 body entry";
			if (unit == 1 && a ==  50) m = "DISCONNECT -- header unit-1 setup block (runs, returns, no body)";
			util::stream_format(s, "setvec  unit%d,#%d", unit, a);
			if (m != nullptr)
				util::stream_format(s, "   ; %s", m);
		}
		else if (hi == 0x000 && lo == 0x000)
			s << "nop";
		else if (is_ldptr(word))
			util::stream_format(s, "ldptr   #$%02x", ad);
		else if (is_ldptrd(word))
			util::stream_format(s, "ldptr.d #$%02x", ad);
		else if (is_rstcur(word))
			s << "rstcur";
		else
		{
			// THE ALU, rendered as the two fields it really is: the OPERATION
			// from hi12[3:1] and the ROUTING from lo12.  The optional
			// multiply / store / pointer controls live outside both.
			//     mnemonic = the accumulator op, then the lo12[4:0] side effect
			//     operand  = the lo12[10:6] bus source, then the pointer walk
			//
			// *** THE SOURCE IS LOOKED UP, NOT INDEXED.  It used to be
			// `SRC[lo_src(word)]' over a four-entry table, which became an
			// out-of-bounds read the moment lo_src() was widened from two bits
			// to five: the four ANCHORED codes are 0x07/0x10/0x19/0x1A and
			// every one of them is past the end of a 4-entry array.  Fixed
			// here; a switch cannot acquire that defect again. ***
			const char *sname;
			switch (lo_src(word))
			{
			case LO_SRC_MEM: sname = "(p)"; break;
			case LO_SRC_ACC: sname = "acc"; break;
			case LO_SRC_TA:  sname = "ta";  break;
			case LO_SRC_TB:  sname = "tb";  break;
			default:         sname = "?";   break;      // unreachable: decoded()
			}

			const char *mn;
			switch (hi_f31(hi))
			{
			case HI_ACC_LOAD: mn = "ld";   break;       // acc <- P
			case HI_ACC_ADD:  mn = "mac";  break;       // acc += P
			default:          mn = "post"; break;       // class-8 post-sum step
			}

			std::string suffix;
			switch (lo_act(word))
			{
			case LO_ACT_CAP_TA:  suffix = ".ta";  break; // tempA <- bus
			case LO_ACT_CAP_TA2: suffix = ".ta2"; break; // ...the second encoding
			case LO_ACT_CAP_TB:  suffix = ".tb";  break; // tempB <- bus
			case LO_ACT_ST_BUS:  suffix = ".st";  break; // mem[ptr] <- bus
			// ★ the accumulator's own input term comes from the BUS, so the
			// hi12[3:1] prefix loses its meaning here: `ld.b' and `mac.b' both
			// compute `bus + P'.  Both are printed, because hi12[3:1] IS a field
			// and the listing renders fields; the equality is the finding, not a
			// reason to hide one of them.
			case LO_ACT_ACC_BUS: suffix = ".b";   break;
			default:             suffix = "";     break;
			}

			std::string mnem = std::string(mn) + suffix;
			while (mnem.size() < 7)
				mnem += ' ';
			util::stream_format(s, "%s %s", mnem, sname);
			// ★ FETCH IS NOT ADVANCE, in the MNEMONIC too.  `,c+' = fetches one
			// coefficient AND post-increments the cursor (class A).  `,c' =
			// bit 23 is set so a coefficient IS fetched, but the cursor does not
			// move (class 8, K4 FORCED) -- and this model gives that word no
			// multiply either, because the biquad reproduces to 0.094 dB with
			// class 8 doing none.  Saying nothing at all, which is what this
			// branch used to do, hid the fetch on all 35 sites of 804.8.16.415.
			if (coeff_consumer(word))
				s << ",c+";
			else if (cursor_fetch(word))
				s << ",c";
			if ((cl & 7) == 2)
				util::stream_format(s, ",(p)%+d", dd);
			if (hi & HI_ST)
				s << (st_suppressed(word) ? " ; store SUPPRESSED (bit7)"
										  : " ; mem[p]<-acc, acc=0");

			// ★ END OF BLOCK SURVIVES THE DECODE.  A decoded word prints no
			// [annotation], and MEASURED that costs nothing on 381 of the 384
			// decoded words that carry one -- "writes mem[ptr] (bit 4)",
			// "P-consumer stores latch A/B", "read into carry latch A/B",
			// "gain multiply" and "class 8 post-sum step" are all things the
			// FIELD DECODE now says properly, and the two agree (lo12 0x1D4 =
			// src mem[p] + action CAP_TB IS "read into carry latch B").  The
			// remaining three are END-OF-BLOCK words, and that is a CONTROL-FLOW
			// fact orthogonal to the ALU: the word still performs its datapath
			// work AND ends the block.  Dropping it would lose a landmark.
			// (class 1 cannot reach here -- alu_decoded() admits only 2/8/A --
			// so the unit-tagged CALL/RETURN form is unreachable by construction.)
			if (is_end(word))
				s << ((hi & HI_ST) ? "; " : " ; ") << "END OF BLOCK (falls through)";
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

		// in the C-format family the printed class4|addr8 split is a FICTION --
		// say so, and show the immediate the bits really are
		if (c_format(word))
			util::stream_format(s, "  {C-fmt A=%d B=%d}", c_a(word), c_b(word));

		// What a `~word' actually DOES when the device executes it: the store
		// enable (hi12 bit 4), the cursor fetch (bit 23) and the signed pointer
		// post-increment, all MEASURED.  Printing it means the trace shows the
		// pointer walk instead of leaving a reader to recompute it.
		if (addr_only)
		{
			if (c_format(word))
				s << "  {addr: none -- C-format, SAFE NO-OP}";
			else
				util::stream_format(s, "  {addr: %s mem[p]%s, p%+d}",
						((hi & HI_ST) && !st_suppressed(word)) ? "ST" : "rd",
						cursor_fetch(word) ? (coeff_consumer(word) ? ", cur+" : ", cur") : "",
						int(dd));
		}

		// hi12 as FLAGS + RESIDUE.  This is the whole point of the rendering
		// change: instead of 54 opaque values a reader sees which enables are
		// set and which bits nothing accounts for.
		util::stream_format(s, "  hi12{%s}", hi12_text(hi));

		// ★ FETCH IS NOT ADVANCE (K4, FORCED).  bit 23 = CURSOR-FETCH enable
		// (CORRECTED reading -- NOT multiply-enable); only class4 == 0xA moves
		// the cursor on.  So `cur+' means "fetches AND advances" and `cur' means
		// "fetches, cursor stays put".  The old code printed `cur+' on every
		// bit-23 word, which is wrong on the PARAMETRIC EQ's ten class-8 words
		// and on every class-8 word in the corpus (42 of them).
		if (cursor_fetch(word))
			s << (coeff_consumer(word) ? " cur+" : " cur");

		const std::string note = annotate(word, at);
		if (!note.empty())
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

	// `at' is the word's I-RAM index.  It is only used by the C00 self-address
	// check, and it is correct exactly when the buffer starts at an I-RAM origin
	// -- which is how the corpus images are disassembled.
	stream << text(word, int(pc / WORD_BYTES));

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
