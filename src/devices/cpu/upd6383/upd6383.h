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
	s32 acc_to_datum(u64 acc) const;   // §114: reads m_specmask, no longer static
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

	// ★★★ §97 SPECULATIVE (mask bit 23): MODE-1 `addr8' AND MODE-2 `mem[ptr]'
	//  ARE NOT THE SAME MEMORY, so they must not be the same array.
	//
	//  §96 resolved the §71/§86 conflict by noting that this core resolves both
	//  routes onto ONE 256-cell array.  That is what makes the conflict: §71
	//  measured the host writing REGISTER 0x06 (the unit-0 output level) and §86
	//  measured the kernel writing D-RAM CELL 0x06 (audio scratch).  Both are
	//  right; the alias is ours.
	//
	//  WHY THEY CANNOT BE ONE MEMORY -- the argument needs no pointer walk, and
	//  it is not new, only extended.  `output-stage-decode.md' item J is FORCED:
	//  a mode-1 ACTION-0x07 word does NOT write reg[addr8], because the output
	//  stage's w72 is `000.1.06.087', register 0x06 is the host-programmed
	//  output level (EFF_VolumeLoop, PROVEN BY CONSTRUCTION), and if that word
	//  wrote, "that depth would survive exactly ONE frame".  Guard 6 in the
	//  disassembler rests on that.  Under the alias the kernel's own mode-2
	//  scratch stores overwrite the same cell EVERY frame -- the same
	//  impossibility item J already rejected, only worse.  So: two memories.
	//
	//  CORROBORATION, and it is the kind that costs a hack rather than adding
	//  one: exec_alu()'s ACTION-0x07 store carries a `host_reg' guard on cells
	//  0x06/0x86 whose own comment reads "⛔ A GUARD, NOT A DECODE: it
	//  suppresses the symptom so the level survives".  Under the split that
	//  guard is unreachable by construction -- a mode-2 store cannot address the
	//  register file at all.  An acknowledged symptom-suppressor disappearing is
	//  evidence for the model that removes it.
	//
	//  FURTHER, ALREADY ON RECORD: `register-space.md' C2 found four mode-1
	//  cells (0x0F, 0x8C, 0x8D, 0x8F) that the host never initialises -- in 100
	//  canned streams AND the live cold-boot capture -- and concluded "a cell
	//  the host never initialises is not state the host owns; it behaves like a
	//  hardware register or port".  Ports do not live in working memory.
	//
	//  SHAPE: corpus-wide the mode-1 route names 8 distinct cells across 48 of
	//  3057 words; the mode-2 route reaches 129 cells across 3440 accesses.
	//  A register file and a memory (dsp/tools/mode_alias.py).
	//
	//  WHAT IS *NOT* CLAIMED: the two spaces' sizes, whether the register file
	//  is 256 deep or much smaller with the index truncated, and whether bit 7
	//  of a register index is the unit select here as it is in D-RAM.  256 is
	//  chosen to make the change a routing change and nothing else.
	u32 m_rf[256];          // the mode-1 / host-tag-0x15 REGISTER FILE

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
	//  ★ §104: FULL PER-SLOT QUIET/LOUD SPLIT.  §81's 12 hand-placed probes cannot
	//  find a transition they were not placed on; this records EVERY slot, split by
	//  whether the frame carried input, for three quantities at once:
	//    acc  -- the accumulator AFTER the slot ran (same convention as §81)
	//    mem  -- the D-RAM cell UNDER THE POINTER BEFORE the slot ran (the value the
	//            word would read in mode 2 -- a RESIDENCY census, not a write census)
	//    L    -- the operand bus the decode actually selected (m_last_l)
	//  The three columns separate "the cell is dead" from "the cell is live but the
	//  SRC decode does not pick it up" from "the operand arrives and the ALU drops it".
	u32  m_sp_nq[384] = {}, m_sp_nr[384] = {};
	s64  m_sp_accq_lo[384] = {}, m_sp_accq_hi[384] = {};
	s64  m_sp_accr_lo[384] = {}, m_sp_accr_hi[384] = {};
	s32  m_sp_memq_lo[384] = {}, m_sp_memq_hi[384] = {};
	s32  m_sp_memr_lo[384] = {}, m_sp_memr_hi[384] = {};
	s32  m_sp_lq_lo[384] = {}, m_sp_lq_hi[384] = {};
	s32  m_sp_lr_lo[384] = {}, m_sp_lr_hi[384] = {};
	u8   m_sp_dp[384] = {};
	u64  m_sp_word[384] = {};
	//  ★ §104 A/B, diagnostic only, off unless UPD6383_AB_NOSTORE08=1 in the env.
	bool m_ab_nostore08 = false;
	u32  m_ab_nostore08_n = 0;
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
	                 s32 ta; s32 tb; u8 cur; u32 coef; s32 l; bool mul;
	                 s64 accb; bool u1; };
	trace_t m_trace[400] = {};
	u32  m_trace_n = 0;
	bool m_trace_armed = false, m_trace_done = false;
	//  ★ §128: frame at which the time-ordered trace arms.  Settable via
	//  UPD6383_TRACE_FRAME so a panel-SELECTED effect (which cannot load before the
	//  boot settles, ~19 s) can be traced instead of the cold-boot default.
	u64  m_trace_frame = 420000;
	//  ★ §130 fired-count for the per-unit coefficient-cursor rebase (mask bit 38).
	//  Every gate must log one: it is what distinguishes a real null arm from a
	//  gate that silently never ran.
	u64  m_cursor_rebase_n = 0;

	// ---- §133 THE BANK-ENTRY DEMULTIPLEXER ---------------------------------------
	//  Decodes PARAMETRIC EQ's two five-word bank entries (ACT 0x0D, ACT 0x0E,
	//  f31=4, f31=5) WITHOUT needing the chip audible and WITHOUT needing the
	//  `SRC 0x08' clobber fixed: a known, per-frame-distinct stimulus is injected
	//  straight into D-RAM 0x05/0x0F at the unit-0 body CALL -- downstream of the
	//  clobber -- and the 40 Direct-Form-I state cells 0x50..0x77 are read back as
	//  a bit-exact witness of what the entry left in P.  §131: the accumulator
	//  CANNOT carry the sample across the entry (every entry word is f31=0,
	//  `acc <- P'), so P is the only conduit and the four unknowns compete for it.
	//
	//  Mask bits (39+; 35-37 = §121's selector, 38 = §130's rebase):
	//    39      injector on
	//    40      inject DIFFERENT sequences into 0x05 and 0x0F (else the same)
	//    41      in-device SWEEP: drive the four selectors from the trial counter
	//    42-44   static ACT 0x0D destination        45-47  static ACT 0x0E destination
	//    48-49   static f31=4 reading               50-51  static f31=5 reading
	//    52      suppress the blanket tempA capture when the action's selector is set
	static constexpr u32 BX_TRIAL_FRAMES = 64;
	static constexpr u32 BX_TRIALS       = 1024;   // 8 x 8 x 4 x 4
	bool m_bx_on = false, m_bx_distinct = false, m_bx_sweep = false, m_bx_supp_ta = false;
	u32  m_bx_sel0d = 0, m_bx_sel0e = 0, m_bx_f4 = 0, m_bx_f5 = 0;
	bool m_bx_armed = false;
	u32  m_bx_trial = 0, m_bx_tframe = 0;
	u32  m_bx_prev[40] = {};
	u32  m_bx_nz = 0, m_bx_chg = 0, m_bx_f1s = 0, m_bx_f1t = 0;
	u32  m_bx_f2s = 0, m_bx_f2t = 0, m_bx_shift = 0, m_bx_shmax = 0;
	u64  m_bx_inj_n = 0, m_bx_act0e_n = 0, m_bx_f4_n = 0, m_bx_f5_n = 0, m_bx_supp_n = 0;
	static u32 bx_stim(u32 n, bool second)
	{   //  non-repeating over the 64-frame trial, and the two streams never collide,
		//  so "which cell did the entry feed from" is decidable bit-exactly.  Small
		//  enough that the cascade's x2 make-up cannot rail a 24-bit cell.
		return second ? (0x018000u + n * 0x000203u) : (0x010000u + n * 0x000101u);
	}
	void bx_frame_end();
	//  Reading 0 is "keep the current alias" and is handled by the caller, so this
	//  only maps 1..3.  LOAD/ADD/HOLD are the three accumulator ops the ISA already
	//  has (upd6383d.h:123-125); HOLD is otherwise only established on class 8, so
	//  admitting it here for f31 >= 4 is exactly the kind of extension this test is
	//  meant to decide rather than assume.
	static u16 bx_f31_op(u32 r)
	{
		return (r == 1) ? 0u : (r == 2) ? 1u : 2u;   // LOAD / ADD / HOLD
	}
	u8   m_st07_dest[8] = {}, m_st07_ptr[8] = {}, m_st07_src[8] = {};
	s32  m_st07_val[8] = {}; u32 m_st07n = 0;
	//======================================================================
	//  ★★★ §109 (2026-07-30) THE STORE-SITE PROBE -- INSTRUMENTATION ONLY.
	//
	//  The question it answers: for a NAMED set of slots, WHERE does the store
	//  land, WHICH code path performs it, and WHICH decode predicate admitted the
	//  word.  Every previous statement about kernel iw30/iw32 was derived from a
	//  static walk plus a per-cell census (§96) -- neither of which observes the
	//  pointer at the store, and neither of which distinguishes "guard 7 refuses
	//  this word" from "a guard SEVEN GUARDS EARLIER refuses it, so guard 7 is
	//  never consulted".  alu_decoded() is a conjunction: only its first failure
	//  is observable, and §109 measures which one that is.
	//
	//  Per probe slot it records: the word, the pointer BEFORE the slot, the
	//  pointer AFTER it, the execution path taken, the four decode predicates,
	//  and up to four distinct (path, address) store events with value ranges.
	//======================================================================
	static constexpr u32 SPROBE_MAX = 16;
	static constexpr u32 SPROBE_ST  = 4;
	struct sprobe_t {
		u16 iw = 0xffff; u64 word = 0; u32 n_exec = 0;
		u8  dp_pre = 0, dp_post = 0;
		u8  path = 0xff;        // 0 decoded(), 1 speculative catch-all, 2 PARTIAL, 3 TRAP
		u8  decoded = 0;        // alu_decoded()
		u8  gfail = 0xff;       // alu_guard_fail() -- the FIRST failing guard
		u8  supp = 0;           // st_suppressed()
		u8  g7 = 0;             // guard7_would_refuse()
		u32 nst = 0;
		u8  st_site[SPROBE_ST] = {}, st_addr[SPROBE_ST] = {};
		s32 st_lo[SPROBE_ST] = {}, st_hi[SPROBE_ST] = {};
		u32 st_n[SPROBE_ST] = {};
	};
	sprobe_t m_sprobe[SPROBE_MAX] = {};
	int  m_sprobe_cur = -1;         // index of the slot currently executing, or -1
	static int sprobe_idx(u16 iw);
	void store_probe(u8 addr, s32 val, u8 site);
	//  ★ §109 mask bit 28 (0x10000000): ACTION 0x07's mode-2 store lands on the
	//  POST-increment cell instead of the pre-increment one.  DIAGNOSTIC, default
	//  OFF, with a FIRED COUNT so a silent no-op can never be read as a null.
	u32  m_act07_post_n = 0, m_act07_post_k6_n = 0;
	//  ★★★ §119 mask bit 34 (0x400000000): THE MEMORY-TO-MEMORY MOVE.
	//  A mode-2 ACTION-0x07 store whose SOURCE is itself a memory read (SRC 0x00 or
	//  SRC 0x11, both = mem[m_dp]) targets the POST-increment cell.
	//  WHY THESE TWO AND NOT THE OTHER SIX: under the shipped PRE-increment target
	//  such a word is `mem[dp] <- mem[dp]' -- an IDENTITY, for every one of its 56
	//  corpus sites, in every program.  A word form that is unconditionally a no-op
	//  is a decode failure, and the degeneracy is a property of the ENCODING (source
	//  and destination naming the same cell), not something fitted to the LFO.
	//  The six other sources (0x10 acc x256, 0x1A x43, 0x19 x41, 0x0B x46 ...) name
	//  something that is NOT the destination cell, so they stay PRE -- which leaves
	//  §109's PRE anchors iw34 and iw88 (both SRC 0x10) untouched.  That is the whole
	//  difference from bit 28, which moved all 9 768 960 stores and killed the ramp
	//  by letting iw88 (`000.2.F4.407', SRC 0x10 = acc) land on the phase cell.
	//  ⛔ SCOPE: rests on §113 (bit 18) reading SRC 0x11 as mem[ptr].  Under the
	//  shipped SRC 0x11 = ACCB reading the degeneracy argument covers only the four
	//  SRC 0x00 words and this gate is unmotivated.
	//  DEFAULT OFF.  FIRED COUNT below so a silent no-op cannot pass for a null.
	u32  m_act07_memmove_n = 0, m_act07_memmove_nz = 0;
	//  ★★★ §109 mask bit 29 (0x20000000): THE OTHER SURVIVING STORE GATE.
	//  store-gate.md item C ran all nine conditions of its enumeration against both
	//  known-mathematics witnesses and exactly TWO survive:
	//      b7 && f31 == 1   (SHIPPED, st_suppressed())
	//      b7 && f31 != 2   (co-equal, never applied)
	//  They differ on exactly 13 corpus words, and kernel iw30 (f31 = 5) is one of
	//  them: under the shipped arm it stores, under the co-equal arm it does not.
	//  ⛔ NOT A FIX and NOT A TIE-BREAK -- it makes the OTHER arm of an open tie
	//  measurable, so "iw30 stores" can be reported as a gate CHOICE rather than as
	//  chip behaviour.  Default OFF, with a FIRED COUNT.
	//  It is applied at BOTH store gates (exec_alu and the K6 input-stage path),
	//  because the two must never disagree -- that identity is the reason
	//  st_suppressed() is called in both places at all.
	bool st_suppressed_live(u64 w);
	u32  m_stgate_alt_n = 0;        // times the two conditions DISAGREED on a word
	//  ★ §109 cross-frame LFO phase witness: the value the body's LFO block finds
	//  resident in the phase cell, sampled at body-0 iw89, over consecutive frames.
	s32  m_lfo_phase[8] = {}; u32 m_lfo_phase_n = 0;
	u32  m_lfo_phase_frame[8] = {};
	//  ★ §119 RULE-8 TRACKING WITNESS.  "It stopped being constant" is not a result;
	//  the destination must carry THE PHASE.  These sample mem[m_dp] on the SAME
	//  frames as the iw89 phase witness, at the two cells the CHORUS delay branch
	//  reads: iw94 (dp = 0x10, the cell iw92's move targets under bit 34) and iw95
	//  (dp = 0x50, the per-voice cell feeding the 0x44C port and the delay read).
	s32  m_lfo_dst[8] = {};  u32 m_lfo_dst_n = 0;   // iw94's mem[dp]
	s32  m_lfo_tap[8] = {};  u32 m_lfo_tap_n = 0;   // iw95's mem[dp]
	u8   m_lfo_dst_dp[8] = {}, m_lfo_tap_dp[8] = {};
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
	//  ★★★ §44: DEFAULT 0x14C -- bit 2 coeff_fetch, bit 3 deferred presentation,
	//  bit 6 level from C-RAM, bit 8 tap-table.  With these four the chip produces
	//  a non-zero output for the first time.  Bits 0/1 (§28 ACCB) and 4 (§40
	//  latched-K) and 7 (§43 level-select) are OFF and each measurably destroys it.
	//  ★ §52: default 0x54C.  Bit 9 (delay descriptors from the CURSOR, §47) is
	//  RETIRED: cursor_fetch and is_dram are DISJOINT across all 91 programs
	//  (0 overlap, 1590 fetch-only, 834 dram-only), so a delay word never fetches
	//  from the cursor and bit 9 fed a pointer those words do not use.
	//  ★★★ §55, 2026-07-29, ON THE OWNER'S INSTRUCTION: default 0x5DF.
	//  Bits 0/1 (ACCB + f31[2]), 4 (latched-K) and 7 (level-select) are RESTORED.
	//  They were switched off for failing a WHOLE-CHAIN test applied to SINGLE
	//  changes -- a bar almost no individual reading can clear, so their failures
	//  carried no information.  Each is independently motivated: the CDJ-500 block
	//  diagram PROVES two accumulators, so modelling one is wrong by construction;
	//  m_k/m_l are declared "multiplier input latches" and the multiply bypassed
	//  them; and r2-output.md §3.1 calls w77 the word that "aims a POINTER at reg
	//  0x86", which §42 proved holds the level.
	//  Bit 9 stays OFF -- it is SPECIFICALLY refuted (cursor_fetch and is_dram are
	//  disjoint across 91 programs), which is evidence about that reading rather
	//  than about the chain.  That is the distinction this default encodes.
	//  ★★★ §71: bit 6 (level from C-RAM) REMOVED from the default -- §42 is REFUTED.
	//  The host DOES write the per-unit output level to D-RAM; it read 0 only because
	//  the poke port was dropped (§56).  Now that P1.1 works, D-RAM 0x06 = 0x200000
	//  (+0.25) and 0x86 = 0x0BC685 (+0.091996), exactly HALF the documented cold-boot
	//  values +0.5 / +0.183992 -- matching r3-delaydram.md's "host payload is 2x the
	//  raw three bytes".  The ORIGINAL code was right; my §42 fix compensated for a
	//  different bug.  Default 0x5DF -> 0x59F.
	//  ★ §84: bit 8 (§44's tap-table guard) RETIRED from the default -- it returns
	//  before the multiply, so it suppressed the kernel's arithmetic, and §72 proved
	//  its premise false (0 of 91 algorithms write 0x50..0x8B).  Bit 17 relocates the
	//  cursor onto the bank the host actually fills, which is the correct successor.
	// ★ §100 RETIRES BIT 5.  Decoding SRC 0x02 as reg[addr8] makes w72 an identity,
	// so the level survives with NO guard: mask 0x19F440F (guard OFF, bit 24 ON)
	// gives unit0 0x200000 on 452 160 frames, where 0x9F440F gives 0x000000 on 0.
	// The guard was the correct INTERIM state -- its own comment asked for exactly
	// this ("A GUARD, NOT A DECODE") -- and a decode replacing it is the outcome it
	// was holding the place for.  Bit 5 remains available for bisection.
	//
	// (superseded, kept for the record) bit 5 (0x20, the mode-1 store guard): it was
	// INERT while mode-1 stores went to D-RAM, and became LOAD-BEARING the moment
	// they were routed to the register file -- without it iw72 (`000.1.06.087',
	// SRC 0x02, which this core does not decode and evaluates as 0) zeroes the
	// unit-0 level on every frame, exactly as item J predicted.  483 840
	// zero-stores suppressed over 16 s.
	//
	// ⚠ THE GUARD IS NARROWER THAN THE DEFECT.  It tests `d07 == 0x06 || d07 ==
	// 0x86' only.  iw70 (`2A6.1.85.0C7') carries SRC 0x03 -- also undecoded, also
	// evaluated as 0 -- and stores to register 0x85, which register-space.md C2
	// lists as host-primed.  Nothing reads reg 0x85 today so there is no live
	// harm, but we are writing a value we did not decode into a host parameter.
	// Widening the guard to "any mode-1 store whose SRC is undecoded" is the
	// principled form and is NOT done here: it is a separate change with its own
	// measurement, not a free rider on this one.
	//
	// bit 23 (§97) is ON by default: the two-space reading is FORCED by item J,
	// and the A/B raised the unit-0 output level from 0x000000 on 100% of frames
	// to the host's value on 452 160, with no rise in the §54 DC leak.
	// ★ §111: bit 31 ON by default -- the host payload is 2x the raw three bytes.
	// Two independent known-right answers hit exactly: unit-0 level 0x200000 ->
	// 0x400000 (+0.5, the documented cold boot) and the CHORUS LFO increment
	// 57 -> 114 (= 0x72, lfo-ramp.md at 11 sites, 0.5993 Hz).
	//  ⚠ WIDENED TO u64 (§114): every bit 0..31 now has a consumer, and the one
	//  apparent exception -- bit 18 -- was SET in the default, which is exactly how
	//  §113 came to be gated behind a bit that was already on and never tested.
	//  A free-bit search must check BOTH "no consumer in code" AND "clear in the
	//  default".  New experiments take bit 32 and up.
	//  ★ bit 18 is CLEARED here, so §113 (SRC 0x11 = mem[ptr]) is now genuinely OFF
	//  and can finally be A/B'd.  It has no other consumer, so clearing it restores
	//  the pre-§113 behaviour rather than changing anything else.
	// ★ §116: bits 25 (class-A ACT-07 latches P), 29 (store-gate co-equal survivor)
	// and 33 (selector-0x27 -> per-unit OVC, bit 3 selects wrap) join the default.
	// Jointly they make the CHORUS LFO phase ramp for the first time; each has its
	// own local justification (see §112, store-gate.md item C, §115/§116) and each
	// is individually removable.  Still HALF RATE -- see §114 on 2^23 vs 2^24.
	// §118: bit 18 (§113, SRC 0x11 = mem[ptr]) rejoins the default -- now VALIDLY
	// tested, since §114 freed it from the default and gave it a real null arm.
	// §121: bit 18 (§113) REMOVED -- it has no discriminating evidence (§119) and it
	// actively destroys the audio deposit: iw11 (400.2.01.447, SRC 0x11 + ACT 0x07)
	// becomes mem[0x05] <- mem[0x05], a self-copy, instead of depositing the
	// accumulator.  Bit 34 (mem-source ACT-07 words are MOVES) joins instead: it
	// gives the LFO ramp WITHOUT bit 18, and both §119 verifiers granted the
	// mechanism even while refuting its consumer conclusion.
	// §130: bit 38 (the PER-UNIT COEFFICIENT-CURSOR REBASE) JOINS the default.
	// Without it body 0's cursor enters at 0x71 and PARAMETRIC EQ's first bank walks
	// C-RAM TABLE B -- the delay-tap ADDRESS table, step 0x4BE = 1214, clamped
	// 0x7FFF -- so the program multiplies audio by tap addresses.  Only its second
	// bank was correct, and only because w58 = rstcur re-bases the cursor by hand.
	// Gated on a pre-registered, bit-exact prediction that came in exactly:
	//   P1 bank 1 (iw84..) now fetches C-RAM 0x00..0x1D in order, bit-identical to
	//      bank 2's stream -- both banks read the same coefficients (§127 §4);
	//   P2 bank 2 UNCHANGED (the control whose answer was known: the gate must be a
	//      no-op where rstcur already did the job) -- confirmed;
	//   P3 unit 1 rebases to 0x90, not 0x00 -- confirmed, cursor 90/91/92/93.
	// Fired-count 5 148 920 (2 body CALLs per frame), so this is not a silent no-op.
	// Backed by cram-unit-base.md item A, MEASURED over 91 programs / 1546 class-A
	// words: unit-1 reverbs resolve 33/33 at base 0x90 and 0/33 at 0x00, and the
	// rival "always add 0x90" is rejected 79/79 on unit 0.
	// ⚠ CONSEQUENCE: unit 1's output changes (620 866 -> 1 064 113 non-zero
	// presentations, peak +1543433 -> -1543434) because the reverb now reads its
	// real coefficient bank.  NEEDS A LISTEN.
	// ⚠ AND: every earlier measurement taken inside a BODY was taken against
	// tap-table values standing in for coefficients.  Re-check body-0 findings
	// before quoting them.
	// §144: the §133 READINGS JOIN THE DEFAULT, together with the §142 unit-aware
	// accumulator write they depend on.  sel0D = 1 (ACT 0x0D = acc <- bus), sel0E = 7
	// (ACT 0x0E = P <- bus at the multiply's scale), bit 52 (excuse them from the
	// blanket tempA capture) and bit 56 (write the PER-UNIT accumulator).
	//   0x46A39B440F | (1<<42) | (7<<45) | (1<<52) | (1<<56) = 0x110E446A39B440F
	// §135 refused to ship these because they railed unit 1 at -0x800000 on 98.9% of
	// presentations.  §143 §3 found why: MY OWN destination menu was unit-blind, so
	// in unit 1 the pair wrote ACCA while the SRC 0x10 reader read ACCB.  With bit 56
	// the arm returns to the default's statistics -- 1 062 933 non-zero vs 1 064 113
	// (0.1%), DC leak 34.64% vs 34.69% -- and frames still close 320/320, 0 traps.
	// Three pre-registered predictions all hit: fired-count 0 -> 7 690 128; the
	// railing stops; and DO1 is UNCHANGED (the known-answer control, since unit 0
	// uses m_acc either way).
	// ⚠ ONE REAL DIFFERENCE REMAINS AND IT NEEDS A LISTEN: unit 1's peak flips sign,
	// -1 543 434 -> +1 543 433.  Both are rails (§143 §2 measured the DEFAULT already
	// railed at 0x7FFFFF<<16 exactly), so this is a polarity change between two
	// railed states, not a change from clean audio to clipped -- but it is audible
	// behaviour in the only audible unit and it is not mine to call.
	// §156: `SRC 0x00 = C-RAM[cursor]' (bit 59, gated on f98==1 AND coefficient-
	// consuming) and THE DELAY-TAP MODULATION PATH (bit 60) join the default.
	//   0x110E446A39B440F | (1<<59) | (1<<60) = 0x1910E446A39B440F
	// Together they make CHORUS's delay tap sweep by EXACTLY +/-240 samples -- the
	// depth the ROM designs at C-RAM[0x02] -- reproducing the 160..640 containment
	// window inside a 1040-sample line that §152 computed FROM THE ROM ALONE before
	// any of this existed.  Neither is observable without the other: tapmod without
	// coef rails at 0x7FFFFF (§154), and §148 had graded coef "inert downstream"
	// because its consumer did not yet exist.
	// Regression, clean cold-boot vehicle (data/PREDICT_156.md), all four pass:
	//   285/285 decoded, 0 PARTIAL, 0 TRAP | tap sweeps +/-240 | DO1/DO2 UNCHANGED
	//   at 0 non-zero, §70 ACCA min == max == 0 | DC leak 0.00%, verdict SILENT.
	// ⚠ THIS MAKES NOTHING AUDIBLE.  It models a swept delay for the first time; the
	// chip stays silent for reasons upstream (§141/§150: w73 zeroes the accumulator
	// despite a formed product).  Shipped on the mechanism, not on a sound.
	// ⚠ AND THE WAVEFORM IS UNDECODED: the census measures the excursion's EXTENT,
	// not its SHAPE OVER TIME.  Two anomalies stand unfitted -- DEPTH's 0.5 gain is
	// not applied (measured +/-240, not +/-120), and one cell sweeps -240..0.
	// §161: A DELAY WORD'S `addr8' IS A DIRECTION FIELD, NOT A STORE ADDRESS
	// (bit 61) joins the default.
	//   0x1910E446A39B440F | (1<<61) = 0x3910E446A39B440F
	// ACTION 0x07's mode-1 store took its destination from addr8(word).  On a
	// class-1 ESCAPE word that field is the delay direction code -- FORCED by
	// adjudication-round5 item D at 276/276 (bit 6 selects; 0x20/0x30 READ,
	// 0x60 WRITE) -- so it cannot also be a destination.  CHORUS's four delay
	// READs `880.1.20.2C7' therefore stored to register cell 0x20, which is LFO
	// WAVETABLE INDEX 3.
	// A/B on the cold-boot CHORUS vehicle, all four pre-registered falsifiers:
	//   F1 aim:   §161 FIRED 4 515 636 == §153's tapmod count IN THE SAME RUN.
	//             Same four words, exactly -- the other 22 addr8==0x20 words in
	//             the frame carry ACT 0x15/0x0B and never reach that line.
	//   F2 value: cell 0x20 restored to 0x5E2382, window 35/36 -> 36/36.  The
	//             table is 36 entries and the sine's period is 24, so index 3
	//             and index 27 are the SAME PHASE: cell 0x38 already held
	//             0x5E2382 in the control, undisturbed.  BIT-IDENTICAL.
	//   F3 collat:the store is re-aimed to m_dp, not deleted, so it could have
	//             punched a new hole.  Full non-zero-cell diff vs the control is
	//             exactly one added line, `20=5E2382'.  Nothing else moved.
	//   F4 null:  control (bit 61 clear) still 35/36 with 0x20 = 000000, FIRED 0.
	// The recovered table is 0.9500000 x 2^23 x sin(2*pi*k/24 + 0.100000 rad) to
	// within 2 LSB over all 36 entries -- amplitude and phase both fell out of a
	// least-squares fit, neither was assumed.
	// ⚠ This does NOT make the chip audible and does NOT implement class 6.  It
	// removes the reason class 6 could not be built: the table is its data.
	// §188: RESTORE THE HOST PAYLOAD'S LSB (bit 63) joins the default.
	//   0x3910E446A39B440F | (1<<63) = 0xB910E446A39B440F
	// `k5-output-stage.md' item 9 and `k3-pointers.md' §1.1 item 3 both give the
	// packet decode as V = ((aa&0x7F)<<17)|(bb<<9)|(cc<<1)|(dd>>7) -- PROVEN BY
	// CONSTRUCTION off the firmware's own writers.  §111's x2 reproduced the three
	// shifts but DROPPED `dd>>7', so a third of every host-programmed quantity in
	// this device was 1 LSB low.
	// ★ Verified against the LFO sine the host uploads, all numbers pre-registered
	// in data/PREDICT_188.md BEFORE the run, scored against the ideal
	// round(0.95 * 2^23 * sin(2*pi*k/24 + 0.1)):
	//     control       max|err| 2 LSB   RMS 1.291   mean -1.000   negative 16/24
	//     bit 63 armed  max|err| 1 LSB   RMS 0.707   mean -0.500   negative 12/24
	// RMS 0.707 = 1/sqrt(2) is exactly the RMS of uniform +/-0.5 rounding: the
	// residual is now pure quantisation, i.e. the table is reproduced as exactly as
	// a 24-bit integer can represent it.
	// ★★ And the 12 cells that moved match the capture's tag-bit-7 pattern
	// BIT-FOR-BIT: 011000000011100111111100.  Cells whose packet had the bit clear
	// are bit-identical (the null half).
	// ⚠ Output is unchanged and silent -- this is a 1-LSB parameter correction, not
	// an audio fix.
	u64  m_specmask = 0xb910e446a39b440f;
	//  ★ §33: what the pointer actually WAS when the header words read the latch,
	//  against m_in_base (the pointer at frame start, which the deposit uses).
	u32  m_dbg_once = 0; u32 m_dbg213 = 0; u32 m_dbg_pres = 0;
	u32  m_tap_n = 0; u32 m_dr_reads = 0, m_dr_reads_nz = 0;
	//  ★★★ §59 P1.1 -- THE HOST POKE PORT.  cmd 0x01 address 0x0160 is a PORT, not an
	//  I-RAM address (host-side.md C4).  Its payload is a byte stream of 5-byte units:
	//  a 0x0A marker introduces a DATA packet (24-bit datum + tag byte), anything else
	//  is a 36-bit instruction word that aims a write pointer.
	//  Tags (C4/A4): 0x15 = D-RAM register file, 0x4C/0xCC = descriptor bank
	//  (0x80 = direction), 0x26 = C-RAM.  Auto-increment +1, PROVEN BY CONSTRUCTION.
	u8   m_poke[8] = {}; u32 m_poke_n = 0;
	u8   m_dram_wp = 0, m_dsc_wp = 0;
	u32  m_pk_dram = 0, m_pk_dsc = 0, m_pk_cram = 0, m_pk_other = 0, m_pk_ptr = 0;
	u32  m_pk_tag[256] = {};
	//  ★★★ §60 P1.2 -- THE DESCRIPTOR BANK IS ITS OWN SPACE.
	//  r3-delaydram.md: "descriptor bank is its own space (tag 0x4C via pointer ...825)",
	//  with its own writer LABEL_038922 byte-for-byte matching the coefficient writer.
	//  Writing descriptors into D-RAM let the microcode's own stores clobber them --
	//  measured: the host wrote 43 descriptors and the delay port still read 0x0000.
	u16  m_dscbank[256] = {};
	//  ★ §61 P2.1: per-UNIT presentation census.  Every §43-53 measurement was
	//  DO1-only because m_accb was never written (§56); unit 1 needs its own column.
	u32  m_pres_u[2] = {}, m_pres_u_nz[2] = {}; s32 m_pres_u_peak[2] = {};
	//  ★ §70: is the presented accumulator a HARD CONSTANT?  Track min and max of
	//  ACCA-at-w73, split by whether the frame had input.  If min == max in both
	//  columns the input never reaches the accumulation at all.
	s64  m_pa_min[2] = { INT64_MAX, INT64_MAX }, m_pa_max[2] = { INT64_MIN, INT64_MIN };
	u32  m_pa_n[2] = {};
	u32 m_dly_w_nz = 0, m_dly_dbg = 0;
	//  ★ §81: where does the input STOP?  Probe the accumulator at four points and
	//  split the range by whether the frame carried input.  A probe whose quiet and
	//  loud ranges are identical has not seen the input.
	s64  m_pr_min[12] = { INT64_MAX, INT64_MAX, INT64_MAX, INT64_MAX, INT64_MAX, INT64_MAX,
	                    INT64_MAX, INT64_MAX, INT64_MAX, INT64_MAX, INT64_MAX, INT64_MAX };
	s64  m_pr_max[12] = { INT64_MIN, INT64_MIN, INT64_MIN, INT64_MIN, INT64_MIN, INT64_MIN,
	                    INT64_MIN, INT64_MIN, INT64_MIN, INT64_MIN, INT64_MIN, INT64_MIN };
	s64  m_pq_min[12] = { INT64_MAX, INT64_MAX, INT64_MAX, INT64_MAX, INT64_MAX, INT64_MAX,
	                    INT64_MAX, INT64_MAX, INT64_MAX, INT64_MAX, INT64_MAX, INT64_MAX };
	s64  m_pq_max[12] = { INT64_MIN, INT64_MIN, INT64_MIN, INT64_MIN, INT64_MIN, INT64_MIN,
	                    INT64_MIN, INT64_MIN, INT64_MIN, INT64_MIN, INT64_MIN, INT64_MIN };
	//  ★ §86: which D-RAM cells does the KERNEL write, and do their values depend on
	//  the input?  Per cell, the value range split by whether the frame had input.
	//  A cell whose quiet and loud ranges DIFFER is carrying the audio.
	s32  m_kq_min[256], m_kq_max[256], m_kl_min[256], m_kl_max[256];
	u32  m_kw_n[256] = {};
	u16  m_kw_who[40] = {}; u8 m_kw_cell[40] = {}; u64 m_kw_word[40] = {}; u32 m_kw_who_n = 0;
	void kwatch(u8 cell, s32 v);
	//  ★★★ §98: THE POINTER WINDOW, MEASURED LIVE.
	//  §97 answered "are mode-1 and mode-2 the same memory?" partly from a STATIC
	//  walk that then failed its own calibration against the live trace (6 of 7
	//  writers, plus 4 invented) -- so every window figure it produced is
	//  discredited, including the one §97 leaned on ("the kernel's window is
	//  0x01..0x07, so 0x06 is inside it and 0x86 is not").  That reading happened
	//  to match the observed damage, which is exactly when a discredited
	//  instrument is most dangerous.  This measures the window instead.
	//
	//  Per REGION and per cell, how many mode-2 (pointer) reads and writes land
	//  there.  Regions follow the MEASURED execution order, not the I-RAM order:
	//      kernel A  iw   0.. 49      body 0    iw  84..199
	//      kernel B  iw  50.. 59      body 1    iw 200..332
	//      epilogue  iw  60.. 82
	//  Mode-1 accesses are counted SEPARATELY (m_rw_*) so the two spaces can be
	//  compared side by side rather than pooled -- pooling them is the defect
	//  §97 removed.
	enum : u32 { PW_KERNEL_A = 0, PW_BODY0 = 1, PW_KERNEL_B = 2, PW_BODY1 = 3,
	             PW_EPILOGUE = 4, PW_NREGION = 5 };
	u32  m_pw_rd[PW_NREGION][256] = {}, m_pw_wr[PW_NREGION][256] = {};
	u32  m_rw_rd[PW_NREGION][256] = {}, m_rw_wr[PW_NREGION][256] = {};
	void pwatch(u8 cell, bool wr, bool mode1 = false);
	//  ★★★ §99: COMPLETE THE §97 SPLIT ON THE STORE SIDE.
	//  §97 routed the mode-1 READ and the host's tag-0x15 writes to m_rf and left
	//  the two STORE sites writing m_dram unconditionally.  §98 measured what that
	//  costs: the ONLY outside writer of body 1's input cell 0x85 is `2A6.1.85.0C7'
	//  at iw70 -- a MODE-1 word -- and kernel B's stray 0x8A is `000.1.8A.007' at
	//  iw58, also mode-1.  Both are mode-1 stores landing in the pointer-walked
	//  D-RAM, which is precisely the category error §97 diagnosed.
	//
	//  WHERE THEY GO INSTEAD is the open part, and the two established readings
	//  disagree, so this is written to let the machine decide:
	//    * guard 6 says mode-1 `L=07' words "write the register/port space"
	//    * item J says w72 (`000.1.06.087') must NOT write reg[0x06], or the user's
	//      effect depth "would survive exactly ONE frame" -- with a STATED ESCAPE:
	//      "SRC 0x02, undecoded, might carry the level itself and make the write an
	//      identity".
	//  Routing mode-1 stores to m_rf tests exactly that escape, and it has a live
	//  failure mode: if the store is not an identity, the unit-0 level stops being
	//  0x200000 and the §41 counter collapses.  That is the measurement.
	u32  m_rf_st[256] = {};
	u32  m_act0d_n = 0;         // §121: ACT 0x0D words routed to the selected dest
	u32  m_ovc_loads = 0;       // §116: selector-0x27 loads of the mode register
	u32  m_ovc_hist[256] = {};  // §116: which payloads it was loaded with
	mutable u32 m_wrap_n = 0;   // §114: accumulator stores wrapped instead of clamped
	u32  m_src11_mem_n = 0;     // §113: SRC 0x11 reads honoured as mem[ptr]
	u32  m_act07_latchp_n = 0;  // §112: class-A ACT-07 words that latched P
	//  §136: the same words routed to the MULTIPLIER INPUT latch instead (mask bit 54).
	//  m_k/m_l (:451) are the input latches and m_p (:450) is the product register --
	//  the split this reading needs is already in the type system; §112 writes the
	//  wrong half of it.  ⚠ Coupled to §40 (bit 4): writing m_k does nothing unless
	//  the multiply reads m_k, which only §40 makes it do.
	u32  m_act07_latchk_n = 0;
	//  §138 (mask bit 55): LOAD-from-an-unformed-product treated as HOLD, everywhere
	//  rather than only on delay words (§83's gate has `m_in_dram').  The epilogue is
	//  where this matters: 1 class-A word in 23, so no multiply issues there, and
	//  iw65..72 erase the body's result before w73 presents it.
	u64  m_stale_load_n = 0;
	//  §142: the per-unit accumulator write for the ACT 0x0D / 0x0E destination
	//  menu.  Mask bit 56 makes it unit-aware, matching the SRC 0x10 reader at
	//  upd6383.cpp:2143 and the §62 convention (bit 14) that unit 1 uses ACCB.
	//  With the bit clear the old, unit-blind behaviour is reproduced exactly, so
	//  every §133/§135 measurement stays comparable.
	u64  m_acc_w_unit1_n = 0;
	//  §145: SRC 0x00 read as C-RAM[cursor] instead of mem[ptr] (mask bit 57).
	u64  m_src00_coef_n = 0;
	//  §161: delay words whose ACT-07 store was re-aimed off the direction field.
	u64  m_dlystore_fix_n = 0;
	//  §164 read-only probe: per-D-RAM-cell ramp census (range AND change count --
	//  a range alone cannot distinguish a ramp from two alternating constants).
	s32  m_rampmin[0x100] = {}, m_rampmax[0x100] = {}, m_rampprev[0x100] = {};
	u64  m_rampchg[0x100] = {};
	u64  m_rampwrap[0x100] = {};   // §196: LFO wrap events per cell
	//  §162 read-only probe: per-class-6-site census of the candidate index sources.
	int  m_c6_n = 0;
	u64  m_c6_word[8] = {};
	u64  m_c6_hits[8] = {};
	s64  m_c6_amin[8] = {}, m_c6_amax[8] = {};
	u32  m_c6_pmin[8] = {}, m_c6_pmax[8] = {};
	u32  m_c6_cmin[8] = {}, m_c6_cmax[8] = {};
	//  §167: the temporaries at the class-6 site.  m_tb is §166's candidate index;
	//  the change-count is what makes it a test (a range alone cannot rule out two
	//  alternating constants).
	s64  m_c6_tbmin[8] = {}, m_c6_tbmax[8] = {}, m_c6_tbprev[8] = {};
	u64  m_c6_tbchg[8] = {};
	s64  m_c6_tamin[8] = {}, m_c6_tamax[8] = {};
	s64  m_c6_kmin[8]  = {}, m_c6_kmax[8]  = {};
	s64  m_c6_lmin[8]  = {}, m_c6_lmax[8]  = {};
	//  §175: identity of the last writer of m_p, so "P is zero at the lookup" can
	//  name WHICH site left it that way rather than being attributed by reasoning.
	//  §180 PTRD-A: lo12 == 0x1C0 does not move the pointer (mask bit 62).
	bool ptrd_a_suppressed(u64 word);
	u64  m_ptrd_a_n = 0;
	//  §193: the f31 = 4 window, keyed by I-RAM slot (122..130).
	void f31_probe(u64 word);
	u64  m_f31_word[9] = {}, m_f31_hits[9] = {}, m_f31_achg[9] = {};
	s64  m_f31_amin[9] = {}, m_f31_amax[9] = {}, m_f31_aprev[9] = {};
	u64  m_f31_reject = 0;
	u32  m_f31_smin[9] = {}, m_f31_smax[9] = {};
	//  §191: the pointer at every bit-11 word, with a change count.
	void b11_probe(u64 word);
	int  m_b11_n = 0;
	u64  m_b11_word[24] = {}, m_b11_hits[24] = {}, m_b11_dchg[24] = {};
	u32  m_b11_dmin[24] = {}, m_b11_dmax[24] = {}, m_b11_dprev[24] = {};
	//  §188: host payload LSB restoration counters.
	u64  m_pk_lsb_n = 0, m_pk_lsb_seen = 0;
	u64  m_pk_0b_n = 0;   // §197
	//  §200: rotation sign + the write-timestamp census (the ONLY probe that can grade it).
	//  §201 SHIPPED ON by default: adjudication-round5.md §1 FORCES the IDENTITY map
	//  -- the k-th class-1 escape consumer takes the k-th cell of ITS OWN BODY's
	//  descriptor block -- and m_delay_ix was frame-global, so body 1 continued body
	//  0's count.  Measured consequence: the descriptor indices move from
	//  0x29..0x33 to 0x26..0x30 (the block §189 measured live as CHORUS's), and
	//  frames_since_written goes from 0..0 on EVERY line to 240 / 480 / 640 samples
	//  (5.44 / 10.88 / 14.51 ms).  The delay lines have length for the first time.
	//  Override with UPD6383_BODYIX=0.
	//  §204: the consumer-to-cell map, first pass only, per body.
	int  m_c2c_n[2] = {};
	u8   m_c2c_ix[2][16] = {};
	u8   m_c2c_dsc[2][16] = {};    // ★ §209: the cell NUMBER, recorded where it was used
	u16  m_c2c_iw[2][16] = {}, m_c2c_cell[2][16] = {};
	//  §204 SHIPPED ON.  r3-delaydram.md §6.1 FORCES that C40.1.80.000 consumes a
	//  descriptor cell (all 8 exact solutions; 28 non-C + 4 C-format = 32 = n).
	//  §203 could not grade it -- the delay census only reports lines that resolve.
	//  The §204 consumer-to-cell census does: with the gate OFF, consumers iw26 and
	//  iw46 BOTH read descriptor value 0x1041 -- two consumers, one cell.  With it
	//  ON, iw46 advances to index 3 and reads 0x05A0: every consumer gets a distinct
	//  cell, which is what the identity map requires.  Override UPD6383_CFMTIX=0.
	bool m_cfmtix = true;
	u64  m_cfmtix_n = 0;   // §203
	bool m_bodyix = true;
	u64  m_bodyix_n = 0;   // §201
	//  §202 SHIPPED ON: the delay rotation SWEEPS DOWN.  round5 §3 FORCES
	//  delay = READ_CELL - WRITE_CELL; with G rising a read returns a FUTURE sample.
	//  ★ The proof is bit-exact and was NOT the falsifier I pre-registered (I predicted
	//  the complement 65536-D and got neither that nor the old values): with the sign
	//  falling the measured delays equal the ROM'"'"'s OWN descriptor cells --
	//      dsc 28 -> 4161 = 0x1041 = descriptor cell 0x27
	//      dsc 30 -> 3120 = 0x0C30 = descriptor cell 0x2F
	//  at two independent lines, against §189'"'"'s live dump taken for another purpose.
	//  Override with UPD6383_ROTSIGN=0.
	bool m_rotsign = true;
	u64  m_rotsign_n = 0;
	//========================================================================
	//  ★★★ §209: THE PER-UNIT DESCRIPTOR RING.
	//
	//  The descriptor BASE is not a register.  `data/DSCBASE_findings.md' closes
	//  the register family by ARITHMETIC: a base register means
	//  base_u = s*F_u + b (mod 256), the offset b CANCELS on subtraction, so the
	//  whole test is whether s*d = 38 (mod 256) is solvable -- iff gcd(d,256)|38.
	//  38 = 2*19 and gcd(d,256) is a power of two, so d must be odd or = 2 (mod 4).
	//      0x827 d=8    0x821 d=32    w45/w53 addr8 d=48    ALL IMPOSSIBLE.
	//  Also eliminated: the body's own first D-RAM word (`880.1.30.00B' is
	//  consumer 0 on BOTH units -- the same 36 bits cannot yield 0x26 and 0x00)
	//  and the host write pointer (m_dsc_wp ends 0x30, order-dependent).
	//
	//  ★ What survives (`dram-unit-cursor.md', 2026-07-27): the base is PER-UNIT
	//  STATE ESTABLISHED AT THE CALL -- a per-unit RING on the ONE shared cursor.
	//  Its sweep: 4440 survivors of 766 576 machines, and in EVERY one
	//  B1 = 0x00 and L1 <= 0x26.  Unit 1's ring ENDS WHERE UNIT 0's BLOCK BEGINS,
	//  so the single immediate 0x25 that `ldptr.d' loads for BOTH units means
	//  "one below unit 0's base" to unit 0 and "the last cell of my ring" to
	//  unit 1 -- one pre-increment delivers 0x26 to one and wraps 0x00 to the
	//  other.  That is why no FIELD of the word could ever carry the difference.
	//
	//  ⚠⚠ A HARDWIRED TWO-ENTRY BASE TABLE indexed by the unit is OBSERVATIONALLY
	//  TIED with the ring and this device does NOT claim which it is: separating
	//  them needs a unit-1 block longer than 38 cells and the corpus maximum is
	//  32 (all twelve reverbs).  The ring is implemented because it gives the
	//  immediate 0x25 a job; that is parsimony, NOT evidence.
	//
	//  Two INDEPENDENT env gates, so the two halves are scored separately (the
	//  u64 spec mask is exhausted; UPD6383_BODYIX/CFMTIX precedent):
	//      UPD6383_DSCPRE   pre-increment: the cell is m_dsc + m_delay_ix + 1
	//      UPD6383_DSCRING  the per-unit ring, [0x00,0x26) unit 1, [0x26,0x40) unit 0
	//  ⚠ The wrap fires ONLY on passing the ring TOP.  A cursor loaded BELOW its
	//  own base (unit 0's 0x25) is not clamped up -- that is the whole mechanism,
	//  and it is why RING is INERT for unit 0 (a pre-registered falsifier: if
	//  body 0 moves when only RING is toggled, the reading is wrong).
	//
	//  ★ FREE PARAMETERS, not measured, printed so they are never read as forced:
	//  the sweep pins L1 only to 0x20..0x26 (= 0x26 under the MOD flavour alone),
	//  B0 is unconstrained in 0x00..0x26 and L0 only bounded to 0x3A..0x41.  No
	//  shipped algorithm reaches either bound, so no run can move them.
	//  0x00/0x26/0x40 is the 38+26 = 64 partition of `dram-unit-cursor.md' item G.
	static constexpr u8 DSC_RING1_BASE = 0x00, DSC_RING1_TOP = 0x26;
	static constexpr u8 DSC_RING0_BASE = 0x26, DSC_RING0_TOP = 0x40;
	bool m_dscpre  = true;
	bool m_dscring = true;
	u64  m_dscpre_n = 0;     // times the pre-increment was applied
	u64  m_dscring_seen = 0; // times the ring path was evaluated at all
	u64  m_dscring_n = 0;    // times the wrap actually CHANGED the cell
	u64  m_dscring_u1 = 0;   // of those, on unit 1
	//  THE descriptor cell a consumer takes.  Every probe below must use THIS and
	//  not re-derive a label: §207/§208 -- the old `u8(m_dsc + m_delay_ix)' label
	//  was +1 for body consumers (it was read AFTER the increment at :1927) and
	//  §202 quoted two "bit-exact" numbers through it.
	u8 dsc_cell()
	{
		u32 raw = u32(m_dsc) + u32(m_delay_ix);
		if (m_dscpre) { raw++; m_dscpre_n++; }
		if (!m_dscring) return u8(raw);
		m_dscring_seen++;
		//  ★ The unit is the one the device ALREADY establishes at the CALL for
		//  the per-unit D-RAM rebase (DRAM_UNIT_BASE) -- no new chip-boundary
		//  violation, nothing reaches into another device's memory, and the unit
		//  is available at the chip's own CALL interface.  In this corpus the
		//  census's own `m_cur_iw >= 200' partition is IDENTICAL (kernel < 84 and
		//  body 0 at 84..199 are unit 0; body 1 starts at 200), so the choice is
		//  not load-bearing for any number reported here.
		const u8 B = m_cur_unit1 ? DSC_RING1_BASE : DSC_RING0_BASE;
		const u8 L = m_cur_unit1 ? DSC_RING1_TOP  : DSC_RING0_TOP;
		if (raw >= L)
		{
			raw = u32(B) + (raw - L) % u32(L - B);
			m_dscring_n++;
			if (m_cur_unit1) m_dscring_u1++;
		}
		return u8(raw);
	}
	std::unique_ptr<u32[]> m_dts_store;
	u32 *m_dts = nullptr;
	//  §209: 12 slots saturated the moment the two units stopped aliasing onto one
	//  sequence -- with the ring, body 1 reads 0x00..0x1F and body 0 0x26..0x2F, so
	//  a 12-entry census can no longer see every line.  32.
	static constexpr int AGE_SLOTS = 32;
	int  m_age_n = 0;
	u8   m_age_dsc[AGE_SLOTS] = {};
	u32  m_age_min[AGE_SLOTS] = {}, m_age_max[AGE_SLOTS] = {};
	u64  m_age_hits[AGE_SLOTS] = {};
	//  §186: which m_rf cells the host tag-0x15 stream actually targets.
	u32  m_hostw_cell[0x100] = {}, m_hostw_nz[0x100] = {};
	u8   m_pw = 0;
	u32  m_c6_pwseen[8] = {};
	//  §175: the SAME census keyed PER WORD -- the pooled form cannot see one dead
	//  site among 36 million live firings.
	int  m_a15w_n = 0;
	u64  m_a15w_word[24] = {}, m_a15w_hits[24] = {}, m_a15w_cnz[24] = {}, m_a15w_lnz[24] = {};
	s64  m_a15w_cmin[24] = {}, m_a15w_cmax[24] = {};
	s64  m_a15w_lmin[24] = {}, m_a15w_lmax[24] = {};
	s64  m_a15w_pmin[24] = {}, m_a15w_pmax[24] = {};
	u32  m_a15w_dmin[24] = {}, m_a15w_dmax[24] = {};   // §176 F2: the pointer per site
	//  §174: the operands AT the class-A ACT-0x15 multiply (not at its consumer).
	u64  m_a15_n = 0, m_a15_cchg = 0, m_a15_lchg = 0, m_a15_cnz = 0, m_a15_lnz = 0;
	s64  m_a15_cmin = 0, m_a15_cmax = 0, m_a15_cprev = 0;
	s64  m_a15_lmin = 0, m_a15_lmax = 0, m_a15_lprev = 0;
	s64  m_a15_pmin = 0, m_a15_pmax = 0;
	//  §169: the product register at the class-6 site, with its change count.
	s64  m_c6_pmin2[8] = {}, m_c6_pmax2[8] = {}, m_c6_pprev[8] = {};
	u64  m_c6_pchg[8]  = {};
	//  ★★★ §153 (mask bit 60): THE DELAY-TAP MODULATION REGISTER.
	//  §152: `lo12 == 0x44C' is "apply the modulation offset" (kn5000-dsp-chorus.md
	//  §3.1/§3.2, 2026-07-22), the class selecting interpolation -- CHORUS uses the
	//  C-format `C40.3.20.44C', ENSEMBLE the truncating `000.2.00.44C'.  The offset
	//  is a SAMPLE COUNT: ENHANCER's UI "DELAY L (ms)" = 350 lands as C-RAM 15435 =
	//  350 x 44100/1000 exactly, and `allocation = nominal tap + |depth|' holds
	//  exactly in four effects across two independent host streams.
	//  The device has had NO modulation register at all; the delay address was
	//  `cellv + m_frames_run' (the circular-buffer rotation G) and nothing else, so
	//  a swept delay could not exist (§149).
	s32  m_tapmod = 0;
	u64  m_tapmod_n = 0;
	//  per-descriptor-cell tap-address excursion census, so the sweep can be MEASURED
	//  rather than asserted: a correct depth gives range ~= 2 x |depth|.
	u32  m_tap_lo[64] = {}, m_tap_hi[64] = {}; bool m_tap_seen[64] = {};
	//  ★★★ §157: the SAME census, per I-RAM SLOT.  §155's per-descriptor-cell
	//  bucketing pools voices, and CHORUS's four ROM depths are +240 +240 -240 -240 --
	//  so a bucket holding one positive and one negative voice reports "-240..+240"
	//  with NO sweep at all.  Per slot, each voice is alone: a real sweep still shows
	//  a range, pooled constants collapse to range 0.
	s32  m_tapslot_lo[384] = {}, m_tapslot_hi[384] = {}; bool m_tapslot_seen[384] = {};
	void bx_acc_w(s64 L, bool add)
	{
		u64 &dst = (m_speculative && (m_specmask & (1ull << 56))
				&& (m_specmask & 0x4000) && m_cur_unit1) ? m_accb : m_acc;
		if (&dst == &m_accb) m_acc_w_unit1_n++;
		if (add) dst += u64(L) << ACC_SHIFT; else dst = u64(L) << ACC_SHIFT;
	}
	u32  m_pk_x2_n = 0;         // §111: host packets whose payload was doubled
	u32  m_k6_act07_fix_n = 0;  // §110: K6 ACT-07 stores re-pointed to pre-increment
	u32  m_mirror06_n = 0;  // §106 diagnostic: 0x06 writes mirrored into 0x05
	u32  m_src02_n = 0;     // §100: times SRC 0x02 read the addressed register
	void store_mode(u8 mode, u8 dest, u32 v);
	static u32 pw_region(u16 iw);
	static const char *pw_name(u32 r);
	u32 m_latch_n=0, m_latch_nz=0, m_pub_try=0, m_pub_hit=0, m_pub_nz=0;
	u32 m_dly_alu = 0, m_dly_noalu = 0, m_dly_alu_0b = 0;
	u32 m_dr_pend = 0; bool m_dr_pend_v = false;
	u32 m_dr_line[64] = {}; bool m_dr_line_v[64] = {};   // ★ §78 per-line outstanding access   // ★ §76 the one outstanding access
	bool m_in_dram = false;   // ★ §74 re-entrancy guard
	bool m_poke_active = false;
	static constexpr u16 POKE_PORT = 0x0160;
	//  ★★★ §54 THE TRACKING TEST -- an in-core DC detector, so speculative readings can
	//  ACCUMULATE without a DC quietly passing for signal again.
	//  Per frame, classify (was the INPUT non-zero?) x (was the OUTPUT non-zero?):
	//      quiet-in / quiet-out  = correct silence
	//      quiet-in / LOUD-out   = ★ DC EVIDENCE. Any large count here is fatal.
	//      loud-in  / loud-out   = the chip is passing signal
	//      loud-in  / quiet-out  = the chip is eating it
	//  A reading that raises loud/loud WITHOUT raising quiet/loud is real progress even
	//  if the whole chain still does not sing.  This is the criterion an individual
	//  change can actually pass.
	u32  m_trk[2][2] = {};   // [input non-zero][output non-zero]
	s32  m_out_peak_quiet = 0, m_out_peak_loud = 0;
	bool m_frame_out_nz = false; s32 m_frame_out_peak = 0;
	//  ★★★ §49: THE ONE-DEEP READ PIPELINE (dram-datapath.md items A and E).
	//  A delay read's datum is NOT on its own bus (item A, FORCED) -- it lands
	//  `land' slots later, with land in [1,4] FORCED and 4 both the upper bound and
	//  the corpus mode over 111 reads (item E).  Modelled as a ring indexed by the
	//  slot counter: a read schedules its datum, and each slot delivers whatever was
	//  scheduled for it.  Without this m_dr is a single register that every read
	//  overwrites, so 20 of the ~21 reads per frame are destroyed unconsumed (§48).
	u32  m_dr_pipe[8] = {}; bool m_dr_pipe_v[8] = {};
	u32  m_slotn = 0, m_land = 4;
	u32  m_dr_landed = 0, m_dr_lost = 0;
	u32  m_dly_r = 0, m_dly_w = 0, m_dly_r_nz = 0, m_dly_cell_nz = 0, m_dly_n = 0;
	u8   m_dly_dsc[8] = {}, m_dly_dir[8] = {}; u32 m_dly_val[8] = {};
	u32  m_lvlguard_n = 0; u32 m_lvl_seen[2] = {}; u32 m_lvl_nz[2] = {};
	u32  m_latchguard_n = 0; u64 m_latchguard_word = 0;
	u16  m_cur_iw = 0; u32 m_latchguard_slot[384] = {};
	//  ★ §37: the shape of the frame-closure drift -- WHICH residues occur, and
	//  WHEN.  A drift confined to boot/program-load is not the same defect as one
	//  that recurs in steady state, and the run-wide min/max cannot tell them apart.
	u32  m_disp_hist[256] = {}; u64 m_disp_first = 0, m_disp_last = 0;
	u32  m_disp_bucket[16] = {}; u32 m_disp_open_run = 0, m_disp_open_run_max = 0;
	//  ★ §38: the 13 % of frames that never reach the wait word.  Same treatment:
	//  WHEN do they happen, and for OVERRUN, where did the PC run off?
	u32  m_cap_bucket[16] = {}, m_ovr_bucket[16] = {};
	u64  m_cap_first = 0, m_cap_last = 0, m_ovr_first = 0, m_ovr_last = 0;
	u32  m_ovr_slots_min = 0xffffffff, m_ovr_slots_max = 0;
	u32  m_cap_slots_min = 0xffffffff, m_cap_slots_max = 0;
	//  ★ §36: the residue -- which WORDS reach the latch, where they aim, and in
	//  which mode.  The slot attribution alone proved unreliable.
	u64  m_lg_word[8] = {}; u32 m_lg_cnt[8] = {}; u8 m_lg_dest[8] = {};
	u8   m_lg_mode[8] = {}; u16 m_lg_iw[8] = {}; u32 m_lg_n = 0;
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
