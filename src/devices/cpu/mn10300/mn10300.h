// license:BSD-3-Clause
// copyright-holders:Felipe Sanches
/*
    Panasonic MN10300 (AM33) CPU core - SKELETON

    Derived from the MAME MN10200 CPU device (src/devices/cpu/mn10200/).
    Only the device boilerplate is filled in; the instruction decoder in
    execute_run() is a stub. Everything that differs from the MN10200 is
    flagged with TODO(MN10300).
*/

#ifndef MAME_CPU_MN10300_MN10300_H
#define MAME_CPU_MN10300_MN10300_H

#pragma once

// Debugger/state-table indices (unique, non-zero; value order is cosmetic)
enum
{
	MN10300_PC = 1,
	MN10300_PSW,
	MN10300_MDR,
	MN10300_SP,
	MN10300_D0, MN10300_D1, MN10300_D2, MN10300_D3,
	MN10300_A0, MN10300_A1, MN10300_A2, MN10300_A3
	// TODO(MN10300/AM33): E0..E7, MDRQ, LIR/LAR, MCRH/MCRL/MCVF, SSP/MSP/USP, ...
};

// External interrupt input lines (placeholder; wire to KN7000 IRQ sources)
enum
{
	MN10300_IRQ0 = 0,
	MN10300_IRQ1,
	MN10300_IRQ2,
	// TODO(MN10300): real NMI + maskable IRQ-group layout
	MN10300_MAX_EXT_IRQ
};


class mn10300_device : public cpu_device
{
public:
	// construction/destruction (single concrete, instantiable device)
	mn10300_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock);

	// The driver's interrupt controller tells the core where the AM33 maskable
	// interrupt vector points (set once at machine start). Input line 0 is the
	// single maskable interrupt.
	void set_irq_vector(uint32_t v) { m_irq_vector = v; }
	void set_irq_level(int l) { m_irq_level = l; }

protected:
	// device_t overrides
	virtual void device_start() override ATTR_COLD;
	virtual void device_reset() override ATTR_COLD;

	// device_execute_interface overrides
	virtual uint32_t execute_min_cycles() const noexcept override { return 1; }
	virtual uint32_t execute_max_cycles() const noexcept override { return 24; } // TODO(MN10300): real worst-case opcode+IRQ cycles
	// (device_execute_interface::execute_input_lines() was removed from MAME;
	//  the input-line count is implicit. MN10300_MAX_EXT_IRQ lines are still used
	//  via set_input_line/execute_set_input.)
	virtual void execute_run() override;
	virtual void execute_set_input(int inputnum, int state) override;
	// TODO(MN10300): the MN10200 overrides execute_clocks_to_cycles/cycles_to_clocks
	// for its internal /2 divider. Only add those if the KN7000 MN10300 clocking
	// requires it; otherwise the 1:1 base-class defaults are correct.

	// device_memory_interface overrides
	virtual space_config_vector memory_space_config() const override;

	// device_state_interface overrides
	virtual void state_import(const device_state_entry &entry) override;
	virtual void state_export(const device_state_entry &entry) override;
	virtual void state_string_export(const device_state_entry &entry, std::string &str) const override;

	// device_disasm_interface overrides
	virtual std::unique_ptr<util::disasm_interface> create_disassembler() override;

private:
	// ---- address space -----------------------------------------------------
	// TODO(MN10300): flat 32-bit little-endian space with a 32-bit data bus,
	// vs. MN10200's (ENDIANNESS_LITTLE, 16-bit data, 24-bit address).
	address_space_config m_program_config;
	address_space *m_program;

	// ---- architectural state ----------------------------------------------
	uint32_t m_pc;    // full 32-bit PC (MN10200 was 24-bit, masked to 0xffffff)
	uint32_t m_d[4];  // data registers D0..D3 (full 32-bit)
	uint32_t m_a[4];  // address registers A0..A3 (full 32-bit)
	uint32_t m_e[8];  // AM33 extended data registers E0..E7 (saved by movm ext groups)
	uint32_t m_sp;    // dedicated stack pointer (MN10200 reused A3 as the stack)
	uint32_t m_mdr;   // multiply/divide register (32-bit on MN10300; 16-bit on MN10200)
	uint32_t m_mdrq;  // AM33 extended multiply/quotient register (getx/putx)
	uint32_t m_mcrh;  // AM33 MAC accumulator high (getchx / putchclx / mac)
	uint32_t m_mcrl;  // AM33 MAC accumulator low  (getclx / putchclx / mac)
	uint32_t m_mcvf;  // AM33 MAC overflow flag
	uint16_t m_psw;   // processor status word
	uint32_t m_lir;   // loop-instruction register (setlb) - modelled for movm completeness
	uint32_t m_lar;   // loop-address register     (setlb)
	// TODO(MN10300/AM33): extended registers E0..E7, MDRQ, register banks.

	// ---- interrupt state ---------------------------------------------------
	// The on-chip interrupt controller is modelled in the driver (0x34000100
	// block); it drives the single maskable IRQ input line here and supplies the
	// address the AM33 maskable vector jumps to. On accept the core pushes PC+PSW
	// and clears IE; the (self-loaded library-ROM) handler reads IAGR, dispatches,
	// acks, and returns via rti. See notes/interrupt-mechanism.md.
	bool     m_possible_irq; // an IRQ may be serviceable; re-checked at the loop top
	int      m_irq_state;    // latched maskable IRQ line (execute_set_input)
	uint32_t m_irq_vector;   // where the maskable interrupt vectors to
	int      m_irq_level = 7; // priority level of the pending interrupt (0 = highest)

	int m_icount;     // remaining cycles this timeslice (MN10200 named this m_cycles)

	// ---- opcode/operand fetch (mirror MN10200: byte-assembled => alignment safe) ---
	inline uint8_t  read_arg8 (uint32_t address) { return m_program->read_byte(address); }
	inline uint16_t read_arg16(uint32_t address) { return m_program->read_byte(address) | (m_program->read_byte(address + 1) << 8); }
	inline uint32_t read_arg24(uint32_t address) { return m_program->read_byte(address) | (m_program->read_byte(address + 1) << 8) | (m_program->read_byte(address + 2) << 16); }
	inline uint32_t read_arg32(uint32_t address) { return read_arg24(address) | (m_program->read_byte(address + 3) << 24); } // TODO(MN10300): 32-bit imm/disp

	// ---- data-side memory accessors (32-bit bus) ---------------------------
	// TODO(MN10300): decide alignment policy; read_word/read_dword on a byte-
	// granular little-endian space handle any offset. MN10200 forced (addr & ~1).
	inline uint8_t  read_mem8 (uint32_t address) { return m_program->read_byte(address); }
	inline uint16_t read_mem16(uint32_t address) { return m_program->read_word(address); }
	inline uint32_t read_mem32(uint32_t address) { return m_program->read_dword(address); }
	inline void write_mem8 (uint32_t address, uint8_t  data) { m_program->write_byte(address, data); }
	inline void write_mem16(uint32_t address, uint16_t data) { m_program->write_word(address, data); }
	inline void write_mem32(uint32_t address, uint32_t data) { m_program->write_dword(address, data); }

	inline void change_pc(uint32_t pc) { m_pc = pc; } // TODO(MN10300): full 32-bit PC, no 0xffffff mask

	// ---- flag / arithmetic helpers (32-bit) --------------------------------
	inline void set_nz32(uint32_t r);
	inline uint32_t do_add(uint32_t a, uint32_t b, uint32_t carry_in);
	inline uint32_t do_sub(uint32_t a, uint32_t b, uint32_t borrow_in);
	inline bool test_cond(int cc);

	// ---- stack + register-list helpers -------------------------------------
	inline void push32(uint32_t val);
	inline uint32_t pop32();
	void store_regs(uint8_t mask);   // movm push (SP moves)
	void load_regs(uint8_t mask);    // movm pop  (SP moves)
	// call/ret/retf use the AM33 imm8-total frame convention: the return PC sits at
	// [SP] and the saved registers at fixed negative offsets below it; SP is moved
	// only by imm8. These write/read the register block at those offsets WITHOUT
	// moving SP (mirrors the GDB simulator's ret/retf offset walk).
	void store_regs_at(uint32_t base, uint8_t mask); // call: regs -> [base-4], [base-8], ...
	void load_regs_at(uint32_t base, uint8_t mask);  // ret/retf: [base-4], ... -> regs

	// ---- prefixed-opcode group handlers ------------------------------------
	void execute_f0();   // 0xF0: reg-indirect moves + call/jmp/ret (aM)
	void execute_f1();   // 0xF1: cross-type reg-reg arithmetic
	void execute_f2();   // 0xF2: logical / mul / div / shift / special-reg moves
	void execute_f3();   // 0xF3: 32-bit indexed load/store (dI,aM)
	void execute_f4();   // 0xF4: byte/half indexed load/store (dI,aM)
	void execute_f5();   // 0xF5: AM33 DSP puts (putx/putchclx) etc.
	void execute_f6();   // 0xF6: AM33 DSP ops (mulq/getx/getchx/getclx/sat...)
	void execute_f8();   // 0xF8: imm8  / disp8  forms
	void execute_fa();   // 0xFA: imm16 / disp16 forms
	void execute_fc();   // 0xFC: imm32 / disp32 / abs32 forms
	void execute_fe();   // 0xFE: bit ops on absolute address

	// shift/logical flag helpers
	inline void set_logic_flags(uint32_t r);   // and/or/xor/not: Z,N; clear V

	// typed memory transfer used by the F8/FA/FC (disp,aM)/(disp,sp)/(abs) moves.
	// type: 0/1 = 32-bit mov (a-reg iff a_reg), 2 = movbu (byte), 3 = movhu (half).
	inline void typed_load_store(int type, bool a_reg, int reg, uint32_t ea, bool store);
	inline void do_shift(int op, int dst, uint32_t count);  // 0=asl 1=lsr 2=asr

	// ---- interrupts (stubs) ------------------------------------------------
	void check_irq();
	void take_irq(int level, int group);
};

DECLARE_DEVICE_TYPE(MN10300, mn10300_device)

#endif // MAME_CPU_MN10300_MN10300_H
