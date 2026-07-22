// license:BSD-3-Clause
// copyright-holders:Felipe Sanches
/***************************************************************************

    upd6383.h

    NEC uPD6383GF digital signal processor.

    *** DRAFT.  NOT WORKING.  NO AUDIO. ***

    See upd6383.cpp for the full explanation.  In one line: the instruction set
    of this chip is not decoded, this device executes the six word forms that
    are, traps and logs every other word, and produces NO AUDIO.  It exists so
    that MAME's own tooling can read the microcode corpus, so that the host
    uploads land in a real I-RAM, and so that the remaining unknowns become a
    frequency-ranked worklist.

    It IS instantiated by the Technics KN5000 (as a subdevice of the DSP1 host
    glue), but it is instantiated DISABLED: the uC-IF is exercised, nothing
    executes.  Enabling execution needs an ISA, not a decision.

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
	UPD6383_OVC
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
	u8  m_cp, m_dp;         // pointers, per the block diagram
	u8  m_bp1, m_bp2;
	u8  m_pr1, m_pr2;
	u8  m_bnk;              // BNK-R
	u16 m_lc1, m_lc2, m_lc3;
	u32 m_tr[4];            // TR0..TR3
	u8  m_gf, m_rq;         // host flags
	u8  m_ovc;              // overflow control
	u8  m_frame_done;       // set by the terminator landmark (see .cpp)

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
	u64 m_trap_total;
	std::map<u64, u64> m_trap_hist;
};

DECLARE_DEVICE_TYPE(UPD6383, upd6383_device)

#endif // MAME_CPU_UPD6383_UPD6383_H
