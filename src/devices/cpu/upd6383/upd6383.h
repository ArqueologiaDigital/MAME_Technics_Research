// license:BSD-3-Clause
// copyright-holders:Felipe Sanches
/***************************************************************************

    upd6383.h

    NEC uPD6383GF digital signal processor.

    *** DRAFT.  NOT WORKING.  NO AUDIO IN PRACTICE. ***

    See upd6383.cpp for the full explanation.  In one line: the instruction set
    of this chip is not decoded, this device executes the word forms that are,
    executes the ADDRESS GENERATOR of every word whose class4 decodes it (the
    signed pointer post-increment and the coefficient cursor -- neither reads
    lo12), traps and logs every word whose arithmetic is unknown, and produces
    NO AUDIO.  It exists so that MAME's own tooling can read the microcode
    corpus, so that the host uploads land in a real I-RAM, and so that the
    remaining unknowns become a frequency-ranked worklist.

    It IS instantiated by the Technics KN5000 (as a subdevice of the DSP1 host
    glue), and it is instantiated DISABLED **as a CPU** (set_disable(), no
    scheduler time).  Since 2026-07-26 there is also a second, OPT-IN entry
    point -- run_frame(), one LRCK period, called by the tone generator once per
    output sample -- behind a default-OFF driver option.  It still produces no
    audio, and it still produces the WORKLIST: which word blocks audio first.
    See notes/dsp-audiopath-wired.md.

    SINCE THE K6 DECODE, A SAMPLE DOES ENTER THE CHIP.  The kernel's audio input
    stage has its ADDRESSING executed, so the DI latches are deposited in D-RAM
    and the microcode really reads them -- MEASURED every frame by an audit that
    can fail.  Its ALU is NOT decoded, so those words are counted as PARTIAL,
    not decoded, and a frame containing one is discarded exactly like a frame
    that trapped -- the audible result is still the dry sound, by construction.

    ★ SINCE 2026-07-26 THE ADDRESS GENERATOR RUNS FOR THE WHOLE FRAME, not just
    for those twelve words.  Restricting it was a defect, not a safety property:
    the words that DO execute were reading D-RAM and C-RAM through a generator
    that had skipped every undecoded word's contribution.  MEASURED: over the
    cold-boot frame the pointer's net displacement moved from -259 to -135 and
    the coefficient cursor from 37 advances to 73.  notes/dsp-frame-advance.md.

***************************************************************************/

#ifndef MAME_CPU_UPD6383_UPD6383_H
#define MAME_CPU_UPD6383_UPD6383_H

#pragma once

#include "upd6383d.h"

#include <map>
#include <vector>

//**************************************************************************
//  ENUMERATIONS
//**************************************************************************

// address spaces.  The chip has four distinct memories (CDJ-500 service manual
// block diagram, p. 1-15); MAME's four space slots map onto them one for one.
// The first three are ON-CHIP and are mapped by the device itself; only
// AS_DELAY is external and must be provided by the machine config.
enum
{
	AS_IRAM  = AS_PROGRAM,  // ON-CHIP 384 x 36, host-uploaded instruction RAM
	AS_CRAM  = AS_DATA,     // ON-CHIP 256 x 24, coefficient side of the IDB
	AS_DRAM  = AS_IO,       // ON-CHIP 256 x 24, state/data side of the IDB
	AS_DELAY = 3            // OFF-CHIP DRAM digital delay, up to 128K x 16
};

// debugger state indices
enum
{
	UPD6383_PC = 1,
	UPD6383_IW,             // PC expressed in 36-bit words (PC / 5)
	UPD6383_ACC,
	UPD6383_P,
	UPD6383_K,
	UPD6383_L,
	UPD6383_TA,
	UPD6383_TB,
	UPD6383_CURSOR,
	UPD6383_CP,
	UPD6383_DP,
	UPD6383_BP1,
	UPD6383_BP2,
	UPD6383_PR1,
	UPD6383_PR2,
	UPD6383_BNK,
	UPD6383_STA,
	UPD6383_CNT,
	UPD6383_UCPC,
	UPD6383_LC1,
	UPD6383_LC2,
	UPD6383_LC3,
	UPD6383_TR0,
	UPD6383_TR1,
	UPD6383_TR2,
	UPD6383_TR3,
	UPD6383_GF,
	UPD6383_RQ,
	UPD6383_OVC,
	UPD6383_DSC,            // the delay-DESCRIPTOR pointer (lo12 selector 0x25)
	UPD6383_VEC0,           // per-unit CALL VECTOR, unit 0 (lo12 0x445)
	UPD6383_VEC1            // ...and unit 1 (lo12 0x446)
};

//**************************************************************************
//  TYPE DEFINITIONS
//**************************************************************************

class upd6383_device : public cpu_device
{
public:
	upd6383_device(const machine_config &mconfig, const char *tag, device_t *owner, u32 clock);

	// ---------------------------------------------------------------
	//  THE PARALLEL uC-IF (P/S pin high).  One byte at a time, with C/D
	//  selecting command (false) or data (true).  This is a property of the
	//  CHIP, not of any one product, so it lives here rather than in a
	//  driver-side wrapper: the upload protocol is the same wherever the part
	//  is used.  Command 0x01 = write I-RAM, and that is the only command
	//  whose payload layout is established (see upd6383.cpp).
	// ---------------------------------------------------------------
	void host_w(bool cd, u8 data);

	// ---------------------------------------------------------------
	//  THE SERIAL AUDIO PORTS -- ONE LRCK PERIOD (see upd6383.cpp).
	//
	//  di[port][ch] / do_[port][ch]: port 0..2 = DI1..DI3 / DO1..DO3,
	//  ch 0 = LEFT, ch 1 = RIGHT.  Both are 24-bit two's complement
	//  (the chip's IDB is 24 bits wide) carried sign-extended in s32.
	//  This is a PIN-LEVEL interface of the real part: the CDJ-500
	//  block diagram (p. 1-15) draws a pair of 24-bit latches behind
	//  every DI/DO line (DI1L-R/DI1R-R ... DO3L-R/DO3R-R), with L/R
	//  designated by LRCKI (pin 18).  No caller may reach past it.
	//
	//  RETURNS TRUE only when the frame ran to the frame-wait word with
	//  ZERO traps AND ZERO PARTIALS, i.e. only when every word of the
	//  frame was executed as decoded.  A K6 input-stage word counts
	//  against this exactly like a trap: its addressing is right, its
	//  arithmetic is unknown, so the accumulator it leaves is not the
	//  chip's.  On FALSE, do_ has already been zeroed: a
	//  partially-executed frame is not "slightly wrong" audio, it is
	//  arbitrary, and this project's standing rule is that
	//  plausible-but-wrong sound is worse than silence.
	// ---------------------------------------------------------------
	bool run_frame(const s32 (&di)[3][2], s32 (&do_)[3][2]);

	//  ★ SPECULATIVE-ISA GATE, default OFF.  See upd6383d.h
	//  alu_decoded_speculative(): everything it admits beyond alu_decoded() is a
	//  researched GUESS.  The driver drives this from bit 1 of the DSPCFG port.
	void set_speculative(bool on) { m_speculative = on; }

	// Frame instrumentation.  Diagnostics, NOT machine state -- the point of
	// the experimental audio path today is to tell us WHICH WORDS BLOCK AUDIO.
	u64 frames_run() const       { return m_frames_run; }
	u64 frames_trapped() const   { return m_frames_trapped; }
	u64 frames_partial() const   { return m_frames_partial; }
	u64 frames_capped() const    { return m_frames_capped; }
	u64 frames_overrun() const   { return m_frames_overrun; }
	u32 last_frame_slots() const { return m_last_slots; }
	u32 last_frame_traps() const { return m_last_traps; }
	void dump_frame_report() const ATTR_COLD;

	// THE INPUT-STAGE AUDIT.  A self-checking measurement, not a claim: every
	// frame, compare the value the microcode's port-read words actually took out
	// of D-RAM against the sample this device latched off the DI pins.  It CAN
	// fail -- point the deposit one cell away and `mismatched' becomes every
	// frame -- which is the whole reason it is here rather than an assertion in
	// a note.  See dump_frame_report().
	u64 input_frames() const     { return m_in_frames; }
	u64 input_matched() const    { return m_in_ok; }
	u64 input_mismatched() const { return m_in_bad; }
	u64 input_nonzero() const    { return m_in_nonzero; }

	// Only the request flags are modelled: RQ1-RQ3 are host-written and
	// testable by the COND field of an instruction, GF1-GF3 are set by
	// instructions and read by the host (CDJ-500 pin table, pins 83-88).
	// Neither the COND field nor the instructions that touch GF have been
	// located, so these are storage only.
	void rq_w(u8 data) { m_rq = data & 7; }
	u8 gf_r() const { return m_gf; }

	// diagnostic: label the microprogram currently resident, so the trap log
	// can say WHICH program an undecoded word came from
	void set_program_id(u32 id) { m_program_id = id; }

	// diagnostic: dump the undecoded-word histogram to the error log
	void dump_trap_histogram() const ATTR_COLD;

	// RESEARCH INSTRUMENTATION: walk the RESIDENT I-RAM under the decoded
	// subset and write a per-word log of (I-RAM index, word, hi12 flags,
	// signed addr8, the three candidate pointers, any would-be store).  This
	// is the address-bus trace notes/kn5000-dsp-hi12.md sect. 5.4 asked for,
	// and it is what located the pointer loads in the common header -- a
	// region every static search had excluded by construction.  It changes no
	// device state, executes nothing, and produces no audio.
	void write_pointer_trace(const char *path) ATTR_COLD;

	// RESEARCH INSTRUMENTATION.  Record every uC-IF byte and write the host
	// upload stream out at exit as <basename>.{bin,txt}.  This is how the
	// microprogram corpus was obtained in the first place and it is what
	// notes/data/kn5000_dsp1_upload_coldboot.txt was produced by, so it is
	// kept -- but it is capture, not chip behaviour, and it does nothing
	// unless a machine config asks for it.
	void set_capture_file(const char *basename) { m_capture_base = basename; }

	// I-RAM capacity, in 36-bit instruction words
	static constexpr int IRAM_WORDS = 384;

	// ---------------------------------------------------------------
	//  FRAME LANDMARKS.  Mixed provenance -- read the label on each one.
	//  FRAME_WAIT_WORD and the two entry points are OBSERVED positions/word
	//  values in the live KN5000 I-RAM (not decodes); FRAME_SLOT_CAP is NOT a
	//  measurement at all, it is a safety limit this model invents.  See
	//  run_frame() in the .cpp for the evidence and for what each is guessing.
	// ---------------------------------------------------------------
	// OBSERVED: C00.A.47.407 -- the last word of the frame, I-RAM 82.
	static constexpr u64 FRAME_WAIT_WORD = 0xc00a47407ULL;
	// INVENTED BY THIS MODEL -- not a property of the chip.  A hard slot cap so
	// a mis-decode cannot hang MAME.  Its VALUE is bounded by measurements (the
	// corpus executes 256..326 slots per frame and I-RAM holds 384 words, so no
	// honest frame can reach it), but the cap itself is ours.
	static constexpr u32 FRAME_SLOT_CAP = IRAM_WORDS;
	// Body entry points for the two effect units, OBSERVED in every captured
	// upload (unit tag 0x0E -> I-RAM 84, 0x0F -> I-RAM 200).
	static constexpr u32 UNIT0_ENTRY = 84;
	static constexpr u32 UNIT1_ENTRY = 200;

	// ---------------------------------------------------------------
	//  ★ THE PER-UNIT D-RAM BASE.  base = 0x05 | (unit << 7).
	//
	//  FORCED, and it is the number this device was missing.  Full derivation:
	//  dsp/analysis/output-stage-decode.md items A/B/D; re-derived from the ROM
	//  before it was applied (notes/dsp-allpass-rerun-applied.md sect. 2).
	//
	//  WHAT IS FORCED, in three steps:
	//    1. The mode-1 REGISTER INDEX and the mode-2 POINTER address ONE 256-cell
	//       RAM (isa-adjudication.md sect. 6 enumerated it; this is its test).
	//    2. Under (1) the body's entry pointer is over-determined.  Two host-side
	//       derivations: PARAMETRIC EQ's 40-cell contiguous run must align with
	//       the host's 40-cell zero-fill block, which has exactly ONE alignment
	//       and no free parameter (E + 75 = 0x50); and min(host zero-fill) is
	//       0x05 in 79 of 79 unit-0 streams and 0x85 in 12 of 12 unit-1 streams.
	//       ★ And one HOST-FREE derivation, added when this was applied: the
	//       shared 83-word kernel names six mode-1 absolute indices in the
	//       unit-1 half (0x85, 0x8A, 0x8C, 0x8D, 0x8F, 0xD0) and the reverb
	//       body's own mode-2 pointer walk reaches ALL SIX at exactly ONE origin
	//       of 256 -- 0x85.  Control over all 256 origins: mean 0.33, sd 0.85,
	//       sole winner.  That is the microcode agreeing with itself, with no
	//       host data in it at all, and it is what makes (1) a measurement
	//       rather than a preference.  (Unit 0 the same way: 119 hits, rank 1
	//       of 256, z = +4.5 -- weaker, because the low cells sit near the walk
	//       start and E = 0x03/0x04/0x06 score 90..93.)
	//    3. net(body0) takes EIGHT different values across the 37 unit-0 images
	//       (-16, -9, -7, -5, -4, +5, +6, +112), so the unit-1 base CANNOT be
	//       reached by walking from the unit-0 base: a REBASE between the two
	//       CALLs is forced to exist.  Its value is in no instruction immediate
	//       (0 nibble-aligned hits in I-RAM 50..58; at chance over every
	//       contiguous 8-bit field), so it is a REGISTER, which is exactly what
	//       K4 item D and closure-pointer.md D' forced for the coefficient
	//       cursor and could not put a number on.
	//
	//  WHAT IS *NOT* FORCED: the SITE.  The rebase is forced to lie between the
	//  last pointer-moving word before a body and that body's first word; within
	//  that window nothing selects an instruction.  This device sites it AT THE
	//  CALL, which is the choice that reproduces the closure arithmetic with the
	//  MEASURED base values (delta(55..58) = +2, so siting it at K4's favourite
	//  candidate `800.1.60.00B' at I-RAM 54 would need the value 0x83, not
	//  0x85 -- also not an immediate anywhere).  Every admissible siting gives
	//  the SAME pointer at body entry, which is the only thing this model uses.
	//
	//  CONSEQUENCE, and it is a prediction that was checked after the fact: the
	//  frame then CLOSES.  0x85 + net(reverb -133) + delta(60..82 -1) = 0xFF, and
	//  0xFF + delta(0..44 +6) = 0x05 = the unit-0 base again.  So "the +121
	//  closure residue is an open defect" is WITHDRAWN: it had stood since the
	//  ADVANCE pass and it was never an ALU defect at all -- it is what walking
	//  ONE pointer through a machine that rebases per unit produces.  It is 0.
	// ---------------------------------------------------------------
	static constexpr u8 DRAM_UNIT_BASE   = 0x05;   // FORCED (see above)
	static constexpr u8 DRAM_UNIT_STRIDE = 0x80;   // FORCED: E1 - E0, = R2's unit bit

	// ---------------------------------------------------------------
	//  WHERE THE INCOMING SAMPLES LAND (K6, notes/dsp-k6-input-stage.md).
	//
	//  ★ THE LABEL ON THIS PARAGRAPH WAS DOWNGRADED ON 2026-07-26 -- see
	//  dsp/analysis/retraction-sweep.md, premise P9.  It used to read "FORCED,
	//  and the only part of this that is".  The argument ran: over the whole
	//  frame -- the 60-word header, the 23-word epilogue AND all 38 body images,
	//  3057 words -- exactly TWO D-RAM cells are READ AND NEVER WRITTEN, at
	//  offsets +2 and +5 from the data pointer at PC-restart; a cell a program
	//  reads and never writes is supplied from outside the instruction stream;
	//  so those two cells ARE the audio input latches.
	//
	//  THE "NEVER WRITTEN" HALF DOES NOT SURVIVE.  It was measured with the
	//  bodies given an origin of their own, via the reading that `801.0.NN.821'
	//  loads the data pointer -- which K3 WITHDREW (0x821 addresses C-RAM,
	//  FORCED).  With the pointer shared across the CALL boundary,
	//  dsp/analysis/closure-pointer.md item F MEASURED 79 of 79 unit-0 images
	//  entering X+0..X+6 and 10 of 79 touching an input latch.
	//
	//  WHAT STILL STANDS, and why this code is unchanged: the two cells are read
	//  at +2 / +5 (MEASURED, and origin-free -- it is a pointer-rule walk of the
	//  twelve words), the deposit here happens at FRAME START, and the kernel
	//  reads them in words 4 and 8, before any body runs.  A body that scribbles
	//  on the window later in the frame cannot corrupt the read that already
	//  happened, and the next frame re-deposits.  The identification of the two
	//  cells as the input latches is therefore now INFERRED (STRONG) rather than
	//  FORCED -- and it is not asserted anywhere: the audit below is a
	//  COMPARISON against what this device latched off the DI pins, so if the
	//  identification is wrong the audit says MISMATCHED instead of lying.
	//
	//  EDUCATED GUESS, clearly labelled, on top of that: WHICH latch is which.
	//  The two are read by the kernel's two parallel blocks, one PC sweep happens
	//  per LRCK period, and the effect return is stereo (the reverb's coefficient
	//  bank has MEASURED mirrored L/R output tails) -- so the two blocks are the
	//  LEFT and RIGHT channel chains rather than two ports, and this board's
	//  microcode reads ONE of its three wired DI ports.  Which port is NOT
	//  decidable from the microcode: the latch->cell map is a chip property.
	//  DI1 is assumed.  Today that assumption is unobservable, because the
	//  driver feeds the same dry stereo pair to all three DI ports (G-3).
	//  WHAT WOULD SETTLE IT: one address-bus trace against real hardware, or the
	//  uPD6383 datasheet's D-RAM memory map.
	// ---------------------------------------------------------------
	static constexpr int IN_PORT       = 0;   // DI1 -- EDUCATED GUESS
	static constexpr u8  IN_LATCH_L_OFF = 2;  // FORCED (the cell header w4 reads)
	static constexpr u8  IN_LATCH_R_OFF = 5;  // FORCED (the cell header w8 reads)

protected:
	// device_t implementation
	virtual void device_start() override ATTR_COLD;
	virtual void device_reset() override ATTR_COLD;
	virtual void device_stop() override ATTR_COLD;

	// device_execute_interface implementation
	virtual u32 execute_min_cycles() const noexcept override { return 1; }
	virtual u32 execute_max_cycles() const noexcept override { return 1; }
	virtual void execute_run() override;

	// device_memory_interface implementation
	virtual space_config_vector memory_space_config() const override;

	// device_state_interface implementation
	virtual void state_string_export(const device_state_entry &entry, std::string &str) const override;

	// device_disasm_interface implementation
	virtual std::unique_ptr<util::disasm_interface> create_disassembler() override;

private:
	u64 fetch(offs_t pc);
	void trap(u64 word, offs_t pc) ATTR_COLD;
	void latch_inputs_to_dram();
	// `k6' = one of the twelve whitelisted input-stage words, which additionally
	// perform their hi12 bit-4 store (see the comment on the definition).
	void exec_addressing_only(u64 word, bool k6);
	void exec_alu_k6(u64 word);     // ★ the K6 input stage's arithmetic (row 18)
	void exec_decoded(u64 word);
	void exec_alu(u64 word);

	// THE FIXED POINT (notes/dsp-alu-biquad.md sect. 5).  What is FORCED is
	// only the TOTAL: a coefficient is scaled by 2^22 (Q1.22 -- MEASURED from
	// the firmware's own scale constants) while a datum is Q0.23, so the
	// product must be brought back down by 22 bits somewhere between the
	// multiplier and the memory.  WHERE the 22 is split between the multiplier
	// output and the accumulator read is NOT determined -- every split from 2
	// to 12 gives numerically identical results on all eleven ROM coefficient
	// banks.  6 is chosen because it keeps the whole 48-bit product inside the
	// 44-bit ALU with room for the five-term sum, which is the only physical
	// consideration that discriminates at all.
	static constexpr int P_SHIFT   = 6;
	static constexpr int ACC_SHIFT = 22 - P_SHIFT;
	static s32 acc_to_datum(u64 acc);
	void capture_byte(bool cd, u8 data);
	void capture_flush();
	void capture_write_files() ATTR_COLD;

	// The three ON-CHIP memories.  I-RAM 384x36, C-RAM 256x24 and D-RAM 256x24
	// are inside the package (CDJ-500 block diagram, p. 1-15): they sit on the
	// internal 24-bit IDB and no pin exposes them, so the device supplies them
	// itself and no machine config may override them.  The FOURTH space,
	// AS_DELAY, is deliberately NOT mapped here -- it is off-chip (see the
	// header comment) and belongs to whoever wires the board.
	void iram_map(address_map &map) ATTR_COLD;
	void cram_map(address_map &map) ATTR_COLD;
	void dram_map(address_map &map) ATTR_COLD;

	const address_space_config m_iram_config;
	const address_space_config m_cram_config;
	const address_space_config m_dram_config;
	const address_space_config m_delay_config;

	memory_access<11, 0, 0, ENDIANNESS_BIG>::cache m_iram;
	memory_access<10, 2, -2, ENDIANNESS_BIG>::specific m_cram;
	memory_access<10, 2, -2, ENDIANNESS_BIG>::specific m_dram;
	memory_access<18, 1, -1, ENDIANNESS_BIG>::specific m_delay;

	int m_icount;

	// --- the register file, bounded by the CDJ-500 block diagram ---
	u32 m_pc;               // byte address into I-RAM (5 bytes per word)
	u32 m_stack[2];         // STACK1, STACK2 -- a 2-level stack, no more
	u32 m_ucpc;
	u32 m_sta;              // STA-R
	u32 m_cnt;              // CNT-R
	u64 m_acc;              // ACCA (44 bits)
	u64 m_accb;             // ACCB (44 bits)
	u64 m_p;                // MPLY product register
	u32 m_k, m_l;           // multiplier input latches
	u32 m_ta, m_tb;         // the two carry latches used by the biquad section
	u8  m_cursor;           // implicit coefficient cursor (MEASURED behaviour)
	// m_cp is the register `ldptr' (lo12 selector 0x21) writes.  MEASURED that
	// it addresses C-RAM; FORCED that it is NEITHER the cursor above NOR the
	// D-RAM operand pointer below (dsp/analysis/k3-pointers.md sect. 4).  Naming
	// it CP -- the CDJ-500 block diagram's COEFFICIENT POINTER -- is an EDUCATED
	// GUESS on top of that.
	// m_dp is the D-RAM operand pointer.  ★ NOTHING LOADS IT: the origin is OPEN
	// (K3's `0x827' candidate was falsified at 0 of 85 streams), so it moves
	// only by the signed post-increments of the words that execute.
	u8  m_cp, m_dp;         // pointers, per the block diagram
	u8  m_dsc;              // the DELAY-DESCRIPTOR pointer, tag-0x4C space
	                        // (`ldptr.d', lo12 selector 0x25 -- PROVEN BY
	                        // CONSTRUCTION).  Written, not yet read: the DRAM
	                        // words that consume descriptor cells are undecoded.
	u8  m_vec[2];           // the per-unit CALL VECTOR registers (K5).  Written
	                        // by setvec; the call sequencer deliberately still
	                        // uses its OBSERVED target table -- see exec_decoded().
	u8  m_bp1, m_bp2;
	u8  m_pr1, m_pr2;
	u8  m_bnk;              // BNK-R
	u16 m_lc1, m_lc2, m_lc3;
	u32 m_tr[4];            // TR0..TR3
	u8  m_gf, m_rq;         // host flags
	u8  m_ovc;              // overflow control
	u8  m_frame_done;       // set by the terminator landmark (see .cpp)
	u8  m_sp;               // stack pointer into m_stack -- 0..2 (the chip has
	                        // STACK1/STACK2 and nothing deeper)

	// --- the serial audio latches, DI1L-R .. DO3R-R on the CDJ-500 block
	//     diagram (p. 1-15).  Real chip state, so save_item()ed.
	s32 m_di[3][2];
	s32 m_do[3][2];

	// --- parallel uC-IF receive state ---
	u8  m_host_cmd;         // most recent command byte
	u16 m_host_pos;         // data bytes seen since that command byte
	u16 m_host_addr;        // I-RAM word address being written (command 0x01)
	u8  m_host_word[upd6383_disassembler::WORD_BYTES];

	// diagnostics -- NOT machine state, deliberately not save_item()ed
	struct transfer
	{
		u8             cmd;
		std::vector<u8> payload;
	};
	const char        *m_capture_base;
	std::vector<transfer> m_transfers;
	transfer           m_capture_current;
	bool               m_capture_open;

	u32 m_program_id;
	bool m_speculative = false;     // ★ opt-in speculative ISA -- see set_speculative()
	u32  m_dr = 0;                  // ★ SPECULATIVE: the delay-DRAM data register.
	                                //   The chip must latch what a delay READ returns
	                                //   somewhere; SRC 0x0B is the only source code
	                                //   whose operand is otherwise unaccounted for.
	u64  m_pres_seen = 0, m_pres_nonzero = 0;   // ★ diagnostic: presentation words
	s32  m_pres_peak = 0;
	s64  m_pres_accpeak = 0;
	u8   m_cwr_hi = 0, m_cwr_word[3] = {0,0,0};   // ★ SPECULATIVE cmd-0x02 coefficient
	u16  m_cwr_port = 0;                          //   stream: port prefix and the
	u32  m_cwr = 0;
	//  ★ ACCUMULATOR PROFILE: peak |acc| seen at each I-RAM slot over the whole run.
	//  Answers "where does the signal die?" with a measurement instead of a search.
	s64  m_accprof[384] = {};
	u32  m_slotseen[384] = {};
	bool m_cur_unit1 = false;       // ★ which unit body is executing (row 27)
	bool m_in_k6 = false;           // ★ re-entrancy guard for exec_alu_k6()
	s64  m_cimm = 0;                              //   c-format immediate latch (row 5 test)
	u8   m_cram_wp = 0;                           //   the C-RAM write pointer, set by
	bool m_cram_wp_set = false;
	u32  m_cwr_runlen = 0, m_cwr_start = 0, m_nruns = 0;
	u8   m_run_base[32] = {}; u32 m_run_len[32] = {};
	u32  m_src_unread[32] = {};
	u8   m_epi_ptr_before = 0, m_epi_ptr[23] = {};
	//  ★ THE TIME-ORDERED FRAME TRACE.  Every wrong turn of 2026-07-28 came from
	//  reading a per-slot MAXIMUM as if it were a SEQUENCE.  This records ONE frame
	//  in EXECUTION ORDER: slot, word, pointer, the value under it, acc and P after.
	//  Armed once, on the first frame whose input sample is non-zero.
	//  ★ §29: L (the bus operand) and a multiply-issued flag, to separate "the
	//  multiply never runs" from "it runs and multiplies by zero".
	s32  m_last_l = 0; bool m_mul_issued = false;
	struct trace_t { u16 iw; u64 word; u8 dp; s32 mem; s64 acc; s64 p;
	                 s32 ta; s32 tb; u8 cur; u32 coef; s32 l; bool mul; };
	trace_t m_trace[400] = {};
	u32  m_trace_n = 0;
	bool m_trace_armed = false, m_trace_done = false;
	u8   m_st07_dest[8] = {}, m_st07_ptr[8] = {}, m_st07_src[8] = {};
	s32  m_st07_val[8] = {}; u32 m_st07n = 0;
	u32  m_dwr[256] = {}, m_dwr_nz[256] = {};
	u32  m_out_slot_writes[6] = {}, m_out_slot_nonzero[6] = {};
	//  ★ §25 diagnostic 2026-07-28: WHY are two of the three presentations always
	//  zero?  Remapping which PORT a zero lands on cannot create signal, so before
	//  testing the port hypothesis, record for each SRC code which REGISTER its word
	//  reads (addr8) and the peak value seen there.  0xffff = never executed.
	//  ★ §25 follow-up: WHO WRITES 0x8C / 0x8D?  Two of the three presentations read
	//  0x8D and it is always zero.  Watch every D-RAM store to those two cells.
	void watch_store(u32 addr, s32 val, u8 site);
	u32  m_watch_hits[4] = {}, m_watch_nz[4] = {};
	u8   m_watch_site[4] = {};
	//  ★ §31: slots 2/3 watch the INPUT LATCH cells.  Under the speculative gate the
	//  microcode reads 0x800000 back out of them while the tone generator writes a
	//  clean 0x4FD900 -- so something in here overwrites the input before it is read.
	u64  m_watch_word[4] = {}; u64 m_cur_word = 0;
	//  ★ §32 BISECTION MASK for the speculative rows added 2026-07-28, so ONE build
	//  can leave each out in turn.  Env UPD6383_SPEC (hex), default 0xF = all on.
	//     bit 0  ACCB + f31[2] accumulator select      (§28)
	//     bit 1  SRC 0x11 = ACCB  (else the old mem[ptr] guess)   (§28)
	//     bit 2  coeff_fetch split -- multiply on class4 bit 3    (§29)
	//     bit 3  deferred presentation (else present and return)  (§29)
	//  ★ DEFAULT 0xC, set by the §32 bisection: bits 2|3 (§29's two CODE-DEFECT fixes)
	//  ON; bits 0|1 (§28's ACCB reading) OFF.  Leave-one-out showed the accumulator
	//  saturation -- and the input-latch corruption it causes -- requires BOTH ACCB
	//  bits, and appears with neither §29 fix.  §28 already failed its own test; this
	//  makes it actively harmful, so it is off by default and kept only as a switch.
	u32  m_specmask = 0xc;
	//  ★ §33: what the pointer actually WAS when the header words read the latch,
	//  against m_in_base (the pointer at frame start, which the deposit uses).
	u32  m_dbg_once = 0;
	u32  m_latchguard_n = 0; u64 m_latchguard_word = 0;
	u8   m_in_readbase[2] = {}; u32 m_in_delta_hist[256] = {};
	u16  m_out_slot_reg[6]  = { 0xffff, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff };
	s32  m_out_slot_peak[6] = {};
	u64  m_out_slot_word[6] = {};
	//  ★ UN-RETIRED 2026-07-28.  This is the class 0xC / 0xD presentation path, and
	//  r2-output.md §3.2 identifies it as the CORRECT one: w73 (class C, addr8 0x00,
	//  unit 0 -> DO1) and w78 (class D, addr8 0x9F, unit 1 -> DO2).  It was retired
	//  over a double-count against the class-1 selector rule above -- but that rule
	//  is the one that is wrong (it hijacked three internal register writes), so the
	//  double-count was resolved in favour of the wrong member of the pair.
	//  ★★★ §27 SPECULATIVE 2026-07-28: THE SECOND ACCUMULATOR.
	//  effects-dsp.md's CDJ-500 block diagram, marked PROVEN, gives this ALU
	//  "two accumulators (ACCA / ACCB)".  Only one was modelled, which made the
	//  ENTIRE epilogue dead: 22 words, peak |acc| = 0 at every slot, while tempA
	//  visibly carried the unit result (504) straight through them.
	//  Unit 0 -> ACCA (m_acc), unit 1 -> ACCB (m_accb -- ALREADY DECLARED above at
	//  the register block, save-stated and reset, but never once read or written by
	//  the ALU until now).
	bool m_pres_pending = false; int m_pres_unit = 0;
	void do_presentation();
	bool m_row13 = true;       // ★ was RETIRED -- see the double-count check            // ★ A/B switch: do the class C/D presentation
	                                //   words ALSO write m_do?  (double-count check)
	s64  m_mulmax = 0; s32 m_mul_coef = 0, m_mul_L = 0; u8 m_mul_src = 0; u32 m_mul_iw = 0;
	s64  m_pprof[25] = {};
	u32  m_curprof[25] = {}; u8 m_curprof_seen[25] = {}; u32 m_curprof_n = 0;                   //   an `801.0.NN.821' ldptr word                               //   sequential C-RAM write pointer
	u8   m_delay_ix = 0;            // ★ SPECULATIVE: which descriptor cell the next
	                                //   delay-DRAM word consumes, reset each frame
	u64 m_trap_total;
	std::map<u64, u64> m_trap_hist;

	// --- THE AUDIO INPUT LATCHES, as they were presented to D-RAM this frame.
	//     m_in_base is the data pointer at PC-restart (`X' in the K6 note); the
	//     deposit addresses and values are kept so the audit can compare what
	//     the microcode read back against what was put there.
	u8  m_in_base;
	u8  m_in_addr[2];       // D-RAM cells written this frame (X+2, X+5)
	s32 m_in_val[2];        // the samples deposited there
	s32 m_in_seen[2];       // what the port-read words actually took out
	u8  m_in_seen_mask;     // bit 0 / bit 1: that port read executed this frame

	// --- FRAME DIAGNOSTICS.  Not machine state; deliberately not save_item()ed.
	u64 m_frames_run;
	u64 m_frames_trapped;   // frames that hit >= 1 undecoded word (return DISCARDED)
	u64 m_frames_partial;   // frames that hit >= 1 ADDRESSING-ONLY word (also discarded)
	u64 m_frames_capped;    // frames that ended on FRAME_SLOT_CAP, not on the wait word
	u64 m_frames_overrun;   // frames whose PC walked off the end of the 384-word I-RAM
	u32 m_last_slots;
	u32 m_last_traps;
	u32 m_last_partials;
	u64 m_partial_total;    // addressing-only words executed, all frames

	// ---- THE FRAME-CLOSURE MEASUREMENT -------------------------------------
	// The NET D-RAM pointer displacement over one frame.  It became visible the
	// moment `ldptr' stopped writing m_dp (K3 withdrew that assignment), and it
	// is worth far more as a measurement than the fixed pointer it replaced:
	//
	//   A COMPLETE frame must leave the pointer where it found it.  The host
	//   addresses D-RAM state by ABSOLUTE index -- its tag-0x15 zero-fill is a
	//   contiguous block based at register 0x50 / 0xD0 in 87 of 91 parameter
	//   streams -- so a body that walked its pointer a net non-zero amount per
	//   sample would drift off its own state block within seconds.  INFERRED
	//   (strong); it rests on the mode-1 register file and the mode-2 D-RAM
	//   being one 256-cell RAM, which isa-adjudication.md sect. 5.1 leaves OPEN.
	//
	// So NET == 0 is a falsifiable convergence criterion for the decode: every
	// word we cannot execute is a pointer move we do not make.  It is a
	// criterion that CAN fail, and today it does -- which is the point.
	s32 m_last_dp_delta;    // signed net displacement of the last frame
	u64 m_frames_dp_closed;   // COMPLETE frames whose net displacement was exactly 0
	u64 m_frames_dp_measured; // COMPLETE frames (reached the wait word) -- the denominator
	// min/max over the run: a CONSTANT residue is a fixed per-frame drift (which
	// the hardware cannot tolerate, so it falsifies part of the model), a VARYING
	// one says the frame's shape itself changes.  The two point at different bugs.
	s32 m_dp_delta_min, m_dp_delta_max;

	// --- THE PER-UNIT REBASE AUDIT (DRAM_UNIT_BASE, above)
	// How often the pointer the WALK delivers to a body entry already equals the
	// base the rebase writes.  For unit 1 this must be rare (net(body0) takes 8
	// values); for unit 0 the closure arithmetic says it must be essentially
	// always, and this is how that is measured rather than assumed.  A unit-0
	// number well below 100 % on complete frames would say the closure model is
	// wrong somewhere -- so this is a criterion that can fail, not a tally.
	u64 m_calls_u0, m_calls_u1;
	u64 m_rebase_agreed_u0, m_rebase_agreed_u1;

	// --- THE INPUT-STAGE AUDIT (see the accessors above)
	u64 m_in_frames;        // frames in which BOTH port-read words executed
	u64 m_in_ok;            // ... and read back exactly what was latched off DI
	u64 m_in_bad;           // ... and did not
	u64 m_in_nonzero;       // ... with a non-zero sample on the pins
	s32 m_in_peak;          // largest |sample| that entered and was consumed
	u32 m_in_log_left;      // LOG_INPUT budget for non-silent frames
	// WHERE the input window actually sat, over the whole run.  One bucket per
	// possible frame-entry pointer.  This is a MEASUREMENT with no criterion
	// baked into it -- it does not know what X "should" be -- and it exists
	// because the D-RAM map (output-stage-decode.md sect. 3.5) makes a checkable
	// prediction about it: with the per-unit rebase in force the frame must end,
	// and therefore restart, on 0xFF, which puts the two DI latches on cells
	// 0x01 and 0x04.  Before the rebase X drifted and the map could not be
	// tested at all.  Counted on COMPLETE frames only, for the same reason the
	// closure residue is.
	u32 m_in_base_hist[256];

	// Per-word trap accounting is a std::map lookup, and run_frame() is called
	// at the audio sample rate, so the full accounting runs only for a WINDOW of
	// frames after every I-RAM change (a new microprogram is the only thing that
	// can introduce a word we have not already seen).  Outside the window traps
	// are still COUNTED, just not histogrammed.
	static constexpr u32 FRAME_DETAIL_FRAMES = 256;
	u32 m_frame_detail_left;

	// LOG_INPUT budget: the first N frames in which a NON-SILENT sample entered.
	// Bounded on purpose -- at 48 kHz an unlimited per-frame log is a 200 MB file.
	static constexpr u32 INPUT_LOG_FRAMES = 8;

	// The most recent REPRESENTATIVE frame's trap sequence, in execution order.
	// This is the decoding worklist: "which word blocks audio, and in what
	// order".  A frame counts as representative only if it reached the frame-wait
	// word AND executed at least FRAME_ORDER_MIN_SLOTS -- the frames right after
	// reset run on an empty or half-uploaded I-RAM and are NOT representative
	// (the floor of a real frame is 216 words: 83 kernel + 133 reverb).
	// Captured only inside a detail window, so the cost is bounded.
	static constexpr int TRAP_ORDER_MAX = 48;
	static constexpr u32 FRAME_ORDER_MIN_SLOTS = 200;
	u32  m_order_iw[TRAP_ORDER_MAX];
	u64  m_order_word[TRAP_ORDER_MAX];
	u32  m_order_n;
	u32  m_order_total;     // traps in that frame, including the ones past TRAP_ORDER_MAX
	u32  m_order_slots;
	u32  m_order_before;    // slots executed before that frame's FIRST trap
	u32  m_order_partials;  // addressing-only words in that frame
	bool m_order_valid;
};

DECLARE_DEVICE_TYPE(UPD6383, upd6383_device)

#endif // MAME_CPU_UPD6383_UPD6383_H
