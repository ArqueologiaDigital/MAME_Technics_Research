// license:BSD-3-Clause
// copyright-holders:Felipe Sanches
/*
    Panasonic MN10300 (AM33) CPU core - WORK IN PROGRESS

    Boilerplate lifted from src/devices/cpu/mn10200/mn10200.cpp and adapted for
    the 32-bit MN10300/AM33. The disassembler already exists next door
    (mn103dasm.{cpp,h}) and is reused for the debugger.

    STATUS: this is an early, UNTESTED draft. The device scaffold (memory space,
    state registration, reset, disassembler hookup) is complete; execute_run()
    implements a first batch of the single-byte opcode group plus the most common
    prefixed forms (32-bit immediate load, add-to-SP), enough to start stepping
    through the KN7000 boot/init code in the debugger. Every unimplemented opcode
    logs and is skipped. Instruction semantics follow the spec derived from
    mn103dasm.cpp; see the many TODO markers.

    Encoding rules (hold everywhere):
      * destination register = low 2 bits [1:0] of the operand byte;
        source register = bits [3:2].
      * PC-relative targets are relative to the START of the instruction.
      * multi-byte immediates/displacements are little-endian.
*/

#include "emu.h"
#include "mn10300.h"
#include "mn103dasm.h"           // reuse the existing MN10300 disassembler
#include "mn10300_insn_length.h" // validated length table (shared with tests/)


// PSW flag bits. The low nibble (Z,N,C,V) is definite and load-bearing; the
// interrupt-control bits are provisional and must be confirmed against the
// MN103E/AM33 manual before implementing interrupts / rti.
enum mn10300_flag
{
	FLAG_ZF = 0x0001, // zero
	FLAG_NF = 0x0002, // negative (result bit31)
	FLAG_CF = 0x0004, // carry / borrow
	FLAG_VF = 0x0008, // signed overflow
	FLAG_IE = 0x0800  // interrupt enable (TODO: confirm)
};


DEFINE_DEVICE_TYPE(MN10300, mn10300_device, "mn10300", "Panasonic MN10300")


//**************************************************************************
//  construction / device plumbing
//**************************************************************************

mn10300_device::mn10300_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: cpu_device(mconfig, MN10300, tag, owner, clock)
	// Flat 32-bit little-endian space, 32-bit data bus. The KN7000 peripherals
	// (program flash @0x48400000, table flash @0x48000000, work RAM @0x50000000,
	// picture flash @0x57800000, I/O banks) are decoded by the machine driver's
	// external address map, so no internal address_map is supplied here.
	, m_program_config("program", ENDIANNESS_LITTLE, 32, 32, 0)
	, m_program(nullptr)
	, m_pc(0), m_sp(0), m_mdr(0), m_psw(0), m_lir(0), m_lar(0)
	, m_icount(0)
{
	std::fill(std::begin(m_d), std::end(m_d), 0);
	std::fill(std::begin(m_a), std::end(m_a), 0);
}

device_memory_interface::space_config_vector mn10300_device::memory_space_config() const
{
	return space_config_vector { std::make_pair(AS_PROGRAM, &m_program_config) };
}

std::unique_ptr<util::disasm_interface> mn10300_device::create_disassembler()
{
	return std::make_unique<mn10300_disassembler>();
}

void mn10300_device::device_start()
{
	m_program = &space(AS_PROGRAM);

	save_item(NAME(m_pc));
	save_item(NAME(m_d));
	save_item(NAME(m_a));
	save_item(NAME(m_sp));
	save_item(NAME(m_mdr));
	save_item(NAME(m_psw));
	save_item(NAME(m_lir));
	save_item(NAME(m_lar));

	state_add(MN10300_PC,  "PC",  m_pc ).formatstr("%08X");
	state_add(MN10300_SP,  "SP",  m_sp ).formatstr("%08X");
	state_add(MN10300_MDR, "MDR", m_mdr).formatstr("%08X");
	state_add(MN10300_D0,  "D0",  m_d[0]).formatstr("%08X");
	state_add(MN10300_D1,  "D1",  m_d[1]).formatstr("%08X");
	state_add(MN10300_D2,  "D2",  m_d[2]).formatstr("%08X");
	state_add(MN10300_D3,  "D3",  m_d[3]).formatstr("%08X");
	state_add(MN10300_A0,  "A0",  m_a[0]).formatstr("%08X");
	state_add(MN10300_A1,  "A1",  m_a[1]).formatstr("%08X");
	state_add(MN10300_A2,  "A2",  m_a[2]).formatstr("%08X");
	state_add(MN10300_A3,  "A3",  m_a[3]).formatstr("%08X");
	state_add(MN10300_PSW, "PSW", m_psw).formatstr("%04X");

	state_add(STATE_GENPC,     "GENPC",    m_pc).noshow();
	state_add(STATE_GENPCBASE, "CURPC",    m_pc).noshow();
	state_add(STATE_GENFLAGS,  "GENFLAGS", m_psw).formatstr("%4s").noshow();

	set_icountptr(m_icount);
}

void mn10300_device::device_reset()
{
	// KN7000: program flash maps at 0x48400000 and file offset 0 is
	// "jmp 0x4840FF7E", so the first fetched instruction is at the flash base.
	// TODO: if the boot/library ROM @0x4C000000 is dumped, the true reset PC
	// may originate there instead.
	m_pc  = 0x48400000;
	m_sp  = 0x50021CF8;   // initial SP established by the KN7000 firmware
	m_psw = 0;
	m_mdr = 0;
	std::fill(std::begin(m_d), std::end(m_d), 0);
	std::fill(std::begin(m_a), std::end(m_a), 0);
}

void mn10300_device::state_import(const device_state_entry &entry) { }
void mn10300_device::state_export(const device_state_entry &entry) { }

void mn10300_device::state_string_export(const device_state_entry &entry, std::string &str) const
{
	if (entry.index() == STATE_GENFLAGS)
		str = string_format("%c%c%c%c",
			m_psw & FLAG_VF ? 'V' : '-',
			m_psw & FLAG_CF ? 'C' : '-',
			m_psw & FLAG_NF ? 'N' : '-',
			m_psw & FLAG_ZF ? 'Z' : '-');
}


//**************************************************************************
//  interrupts (stubs)
//**************************************************************************

void mn10300_device::execute_set_input(int inputnum, int state)
{
	// TODO(MN10300): latch external IRQ line and flag pending for check_irq().
}
void mn10300_device::take_irq(int level, int group) { /* TODO */ }
void mn10300_device::check_irq() { /* TODO */ }


//**************************************************************************
//  flag helpers (32-bit)
//**************************************************************************

inline void mn10300_device::set_nz32(uint32_t r)
{
	m_psw &= ~(FLAG_ZF | FLAG_NF);
	if (r == 0)          m_psw |= FLAG_ZF;
	if (r & 0x80000000u) m_psw |= FLAG_NF;
}

// r = a + b + carry_in; sets Z,N,C,V; returns the 32-bit result.
inline uint32_t mn10300_device::do_add(uint32_t a, uint32_t b, uint32_t carry_in)
{
	uint64_t wide = (uint64_t)a + (uint64_t)b + carry_in;
	uint32_t r = (uint32_t)wide;
	m_psw &= ~(FLAG_ZF | FLAG_NF | FLAG_CF | FLAG_VF);
	if (r == 0)                              m_psw |= FLAG_ZF;
	if (r & 0x80000000u)                     m_psw |= FLAG_NF;
	if (wide > 0xFFFFFFFFull)                m_psw |= FLAG_CF;
	if ((~(a ^ b) & (a ^ r)) & 0x80000000u)  m_psw |= FLAG_VF;
	return r;
}

// r = a - b - borrow_in; sets Z,N,C(borrow),V; returns the 32-bit result.
inline uint32_t mn10300_device::do_sub(uint32_t a, uint32_t b, uint32_t borrow_in)
{
	uint64_t wide = (uint64_t)a - (uint64_t)b - borrow_in;
	uint32_t r = (uint32_t)wide;
	m_psw &= ~(FLAG_ZF | FLAG_NF | FLAG_CF | FLAG_VF);
	if (r == 0)                             m_psw |= FLAG_ZF;
	if (r & 0x80000000u)                    m_psw |= FLAG_NF;
	if ((wide >> 32) & 1)                   m_psw |= FLAG_CF; // borrow
	if (((a ^ b) & (a ^ r)) & 0x80000000u)  m_psw |= FLAG_VF;
	return r;
}

// Condition test for the C0..C9 b<cc> family (indices into f_conds order:
// blt,bgt,bge,ble,bcs,bhi,bcc,bls,beq,bne).
inline bool mn10300_device::test_cond(int cc)
{
	const bool Z = m_psw & FLAG_ZF, N = m_psw & FLAG_NF;
	const bool C = m_psw & FLAG_CF, V = m_psw & FLAG_VF;
	switch (cc)
	{
		case 0: return (N ^ V);            // blt
		case 1: return !((N ^ V) || Z);    // bgt
		case 2: return !(N ^ V);           // bge
		case 3: return ((N ^ V) || Z);     // ble
		case 4: return C;                  // bcs / blo
		case 5: return !(C || Z);          // bhi
		case 6: return !C;                 // bcc / bhs
		case 7: return (C || Z);           // bls
		case 8: return Z;                  // beq
		case 9: return !Z;                 // bne
	}
	return false;
}

inline void mn10300_device::push32(uint32_t val)
{
	m_sp -= 4;
	write_mem32(m_sp, val);
}
inline uint32_t mn10300_device::pop32()
{
	uint32_t v = read_mem32(m_sp);
	m_sp += 4;
	return v;
}


//**************************************************************************
//  execute
//**************************************************************************

void mn10300_device::execute_run()
{
	do
	{
		debugger_instruction_hook(m_pc);

		const uint32_t start_pc = m_pc;   // PC-relative targets use the insn start
		const uint8_t op = read_arg8(m_pc);
		m_pc += 1;

		const int dst = op & 3;           // low field
		const int src = (op >> 2) & 3;    // bits[3:2]

		switch (op)
		{
		// ---- clr dD (D = bits[3:2]) ----
		case 0x00: case 0x04: case 0x08: case 0x0C:
			m_d[src] = 0;
			m_psw = (m_psw & ~(FLAG_NF | FLAG_CF | FLAG_VF)) | FLAG_ZF;
			break;

		// ---- extb/extbu/exth/exthu dD ----
		case 0x10: case 0x11: case 0x12: case 0x13: m_d[dst] = (int32_t)(int8_t)m_d[dst]; break;
		case 0x14: case 0x15: case 0x16: case 0x17: m_d[dst] &= 0x000000FF; break;
		case 0x18: case 0x19: case 0x1A: case 0x1B: m_d[dst] = (int32_t)(int16_t)m_d[dst]; break;
		case 0x1C: case 0x1D: case 0x1E: case 0x1F: m_d[dst] &= 0x0000FFFF; break;

		// ---- add imm8,aD / add imm8,dD (imm8 sign-extended) ----
		case 0x20: case 0x21: case 0x22: case 0x23:
			m_a[dst] = do_add(m_a[dst], (int32_t)(int8_t)read_arg8(m_pc), 0); m_pc += 1; break;
		case 0x28: case 0x29: case 0x2A: case 0x2B:
			m_d[dst] = do_add(m_d[dst], (int32_t)(int8_t)read_arg8(m_pc), 0); m_pc += 1; break;

		// ---- mov imm16,aD (zx) / mov imm16,dD (sx) ----
		case 0x24: case 0x25: case 0x26: case 0x27:
			m_a[dst] = read_arg16(m_pc); m_pc += 2; break;
		case 0x2C: case 0x2D: case 0x2E: case 0x2F:
			m_d[dst] = (int32_t)(int16_t)read_arg16(m_pc); m_pc += 2; break;

		// ---- mov sp,aD ----
		case 0x3C: case 0x3D: case 0x3E: case 0x3F: m_a[dst] = m_sp; break;

		// ---- inc dD (flags) / inc aD (no flags) (D = bits[3:2]) ----
		case 0x40: case 0x44: case 0x48: case 0x4C: m_d[src] = do_add(m_d[src], 1, 0); break;
		case 0x41: case 0x45: case 0x49: case 0x4D: m_a[src] += 1; break;

		// ---- mov dD/aD,(disp8,sp)  (disp8 unsigned) ----
		case 0x42: case 0x46: case 0x4A: case 0x4E:
			write_mem32(m_sp + read_arg8(m_pc), m_d[src]); m_pc += 1; break;
		case 0x43: case 0x47: case 0x4B: case 0x4F:
			write_mem32(m_sp + read_arg8(m_pc), m_a[src]); m_pc += 1; break;

		// ---- inc4 aD (no flags) / asl2 dD ----
		case 0x50: case 0x51: case 0x52: case 0x53: m_a[dst] += 4; break;
		case 0x54: case 0x55: case 0x56: case 0x57: m_d[dst] <<= 2; set_nz32(m_d[dst]); break;

		// ---- mov (disp8,sp),dD / (disp8,sp),aD  (disp8 unsigned) ----
		case 0x58: case 0x59: case 0x5A: case 0x5B:
			m_d[dst] = read_mem32(m_sp + read_arg8(m_pc)); m_pc += 1; break;
		case 0x5C: case 0x5D: case 0x5E: case 0x5F:
			m_a[dst] = read_mem32(m_sp + read_arg8(m_pc)); m_pc += 1; break;

		// ---- mov dS,(aM) (0x60-0x6F) / mov (aM),dD (0x70-0x7F), 32-bit ----
		case 0x60: case 0x61: case 0x62: case 0x63: case 0x64: case 0x65: case 0x66: case 0x67:
		case 0x68: case 0x69: case 0x6A: case 0x6B: case 0x6C: case 0x6D: case 0x6E: case 0x6F:
			write_mem32(m_a[dst], m_d[src]); break;
		case 0x70: case 0x71: case 0x72: case 0x73: case 0x74: case 0x75: case 0x76: case 0x77:
		case 0x78: case 0x79: case 0x7A: case 0x7B: case 0x7C: case 0x7D: case 0x7E: case 0x7F:
			m_d[src] = read_mem32(m_a[dst]); break;

		// ---- mov imm8,dD (src==dst) / mov dS,dD ----
		case 0x80: case 0x85: case 0x8A: case 0x8F:
			m_d[dst] = (int32_t)(int8_t)read_arg8(m_pc); m_pc += 1; break;
		case 0x81: case 0x82: case 0x83: case 0x84: case 0x86: case 0x87: case 0x88:
		case 0x89: case 0x8B: case 0x8C: case 0x8D: case 0x8E:
			m_d[dst] = m_d[src]; break;

		// ---- mov imm8,aD (zx, src==dst) / mov aS,aD ----
		case 0x90: case 0x95: case 0x9A: case 0x9F:
			m_a[dst] = (uint8_t)read_arg8(m_pc); m_pc += 1; break;
		case 0x91: case 0x92: case 0x93: case 0x94: case 0x96: case 0x97: case 0x98:
		case 0x99: case 0x9B: case 0x9C: case 0x9D: case 0x9E:
			m_a[dst] = m_a[src]; break;

		// ---- cmp imm8,dD (sx, src==dst) / cmp dS,dD ----
		case 0xA0: case 0xA5: case 0xAA: case 0xAF:
			do_sub(m_d[dst], (int32_t)(int8_t)read_arg8(m_pc), 0); m_pc += 1; break;
		case 0xA1: case 0xA2: case 0xA3: case 0xA4: case 0xA6: case 0xA7: case 0xA8:
		case 0xA9: case 0xAB: case 0xAC: case 0xAD: case 0xAE:
			do_sub(m_d[dst], m_d[src], 0); break;

		// ---- cmp imm8,aD (zx, src==dst) / cmp aS,aD ----
		case 0xB0: case 0xB5: case 0xBA: case 0xBF:
			do_sub(m_a[dst], (uint8_t)read_arg8(m_pc), 0); m_pc += 1; break;
		case 0xB1: case 0xB2: case 0xB3: case 0xB4: case 0xB6: case 0xB7: case 0xB8:
		case 0xB9: case 0xBB: case 0xBC: case 0xBD: case 0xBE:
			do_sub(m_a[dst], m_a[src], 0); break;

		// ---- conditional branches / bra (disp8, target = start_pc + sx8) ----
		case 0xC0: case 0xC1: case 0xC2: case 0xC3: case 0xC4:
		case 0xC5: case 0xC6: case 0xC7: case 0xC8: case 0xC9:
		{
			int8_t disp = (int8_t)read_arg8(m_pc); m_pc += 1;
			if (test_cond(op & 0x0F)) m_pc = start_pc + disp;
			break;
		}
		case 0xCA: // bra
		{
			int8_t disp = (int8_t)read_arg8(m_pc); m_pc = start_pc + disp; break;
		}

		// ---- nop ----
		case 0xCB: break;

		// ---- jmp disp16 ----
		case 0xCC:
			m_pc = start_pc + (int32_t)(int16_t)read_arg16(m_pc); break;

		// ---- call disp16, regs, imm8 ----
		case 0xCD:
		{
			int16_t disp = (int16_t)read_arg16(m_pc);
			uint8_t regs = read_arg8(m_pc + 2);
			uint8_t adj  = read_arg8(m_pc + 3);
			uint32_t ret = m_pc + 4;      // return past this 5-byte instruction
			push32(ret);
			store_regs(regs);             // TODO: confirm mask/order (see store_regs)
			m_sp -= adj;
			m_pc = start_pc + disp;
			break;
		}

		// ---- movm (sp),regs (pop) / movm regs,(sp) (push) ----
		case 0xCE: load_regs(read_arg8(m_pc)); m_pc += 1; break;
		case 0xCF: store_regs(read_arg8(m_pc)); m_pc += 1; break;

		// ---- jmp disp32 (reset vector uses this) ----
		case 0xDC:
			m_pc = start_pc + read_arg32(m_pc); break;

		// ---- call disp32, regs, imm8 ----
		case 0xDD:
		{
			uint32_t disp = read_arg32(m_pc);
			uint8_t regs = read_arg8(m_pc + 4);
			uint8_t adj  = read_arg8(m_pc + 5);
			uint32_t ret = m_pc + 6;
			push32(ret);
			store_regs(regs);
			m_sp -= adj;
			m_pc = start_pc + disp;
			break;
		}

		// ---- ret / retf regs, imm8 ----
		case 0xDE: // retf - TODO: retf uses an MDR-cached return address; approximated as ret
		case 0xDF:
		{
			uint8_t regs = read_arg8(m_pc);
			uint8_t adj  = read_arg8(m_pc + 1);
			m_sp += adj;
			load_regs(regs);
			m_pc = pop32();
			break;
		}

		// ---- add dS,dD ----
		case 0xE0: case 0xE1: case 0xE2: case 0xE3: case 0xE4: case 0xE5: case 0xE6: case 0xE7:
		case 0xE8: case 0xE9: case 0xEA: case 0xEB: case 0xEC: case 0xED: case 0xEE: case 0xEF:
			m_d[dst] = do_add(m_d[dst], m_d[src], 0); break;

		// ---- prefixed groups ----
		case 0xF0: execute_f0(); break;   // reg-indirect moves + call/jmp/ret (aM)
		case 0xF1: execute_f1(); break;   // cross-type reg-reg arithmetic
		case 0xF2: execute_f2(); break;   // logical / mul / div / shift / special regs
		case 0xF3: execute_f3(); break;   // 32-bit indexed load/store
		case 0xF4: execute_f4(); break;   // byte/half indexed load/store
		case 0xF8: execute_f8(); break;   // imm8 / disp8 forms (incl. add imm8,sp)
		case 0xFA: execute_fa(); break;   // imm16 / disp16 forms
		case 0xFC: execute_fc(); break;   // imm32 / disp32 forms (mov imm32,reg etc.)
		case 0xFE: execute_fe(); break;   // bit ops on absolute address

		// TODO(MN10300): 0xF5,0xF6 (udf/coprocessor), 0xF9,0xFB,0xFD (udf imm) --
		// these fall through to the length-correct skip below until needed.
		default:
			// Not implemented yet. Advance PC by the (validated) real length so
			// the fetch stream stays aligned and the machine remains steppable
			// during bring-up. This treats the opcode as a no-op rather than a
			// trap -- correct results require the real implementation.
			m_pc = start_pc + mn10300_insn_length(op, read_arg8(start_pc + 1));
			logerror("MN10300: unimplemented opcode %02X @ PC=%08X (skipped %d bytes)\n",
				op, start_pc, (int)(m_pc - start_pc));
			break;
		}

		// TODO(MN10300): real per-instruction cycle counts.
		m_icount -= 1;

	} while (m_icount > 0);
}


// 0xFC prefix: 32-bit immediate / displacement / absolute forms (6 bytes total
// for the reg-immediate cases). Only the common register-immediate ops are
// implemented; the (disp32,sp)/(abs32) load-store forms are TODO.
void mn10300_device::execute_fc()
{
	const uint32_t start_pc = m_pc - 1;
	const uint8_t op2 = read_arg8(m_pc);
	m_pc += 1;
	const int dst = op2 & 3;

	if (op2 >= 0xC0)
	{
		const uint32_t imm = read_arg32(m_pc); m_pc += 4;
		switch (op2 & 0xFC)
		{
			case 0xC0: m_d[dst] = do_add(m_d[dst], imm, 0); break;              // add imm32,dD
			case 0xD0: m_a[dst] = do_add(m_a[dst], imm, 0); break;              // add imm32,aD
			case 0xC4: m_d[dst] = do_sub(m_d[dst], imm, 0); break;              // sub imm32,dD
			case 0xD4: m_a[dst] = do_sub(m_a[dst], imm, 0); break;              // sub imm32,aD
			case 0xC8: do_sub(m_d[dst], imm, 0); break;                        // cmp imm32,dD
			case 0xD8: do_sub(m_a[dst], imm, 0); break;                        // cmp imm32,aD
			case 0xCC: m_d[dst] = imm; break;                                  // mov imm32,dD
			case 0xDC: m_a[dst] = imm; break;                                  // mov imm32,aD
			case 0xE0: m_d[dst] &= imm; set_nz32(m_d[dst]); m_psw &= ~FLAG_VF; break; // and
			case 0xE4: m_d[dst] |= imm; set_nz32(m_d[dst]); m_psw &= ~FLAG_VF; break; // or
			case 0xE8: m_d[dst] ^= imm; set_nz32(m_d[dst]); m_psw &= ~FLAG_VF; break; // xor
			case 0xFC:
				if (op2 == 0xFE) { m_sp = do_add(m_sp, read_arg32(m_pc), 0); m_pc += 4; } // add imm32,sp (no flags on real hw? see TODO)
				else logerror("MN10300: unimplemented FC %02X @ %08X\n", op2, start_pc);
				break;
			default:
				logerror("MN10300: unimplemented FC %02X @ %08X\n", op2, start_pc);
				break;
		}
	}
	else
	{
		// TODO(MN10300): FC op2 < 0xC0 = mov/movbu/movhu with (disp32,aM),
		// and the 0x80-0xBF (disp32,sp)/(abs32) load-store forms.
		logerror("MN10300: unimplemented FC %02X (disp32/abs32 move) @ %08X\n", op2, start_pc);
		m_pc += 4; // best-effort length so the stream stays roughly aligned
	}
}


// 0xF8 prefix: imm8 / disp8 forms (3 bytes total). Only add imm8,sp and the
// byte/half SP-relative loads/stores that boot code uses are implemented.
void mn10300_device::execute_f8()
{
	const uint32_t start_pc = m_pc - 1;
	const uint8_t op2 = read_arg8(m_pc);
	m_pc += 1;
	const int8_t imm = (int8_t)read_arg8(m_pc);
	m_pc += 1;

	if (op2 == 0xFE)                       // add imm8,sp
	{
		m_sp = do_add(m_sp, (int32_t)imm, 0);
		return;
	}
	// TODO(MN10300): the remaining F8 forms (mov/movbu/movhu (disp8,aM),
	// shifts asl/lsr/asr imm8,dD, and/or/btst imm8,dD, ext branches).
	logerror("MN10300: unimplemented F8 %02X @ %08X\n", op2, start_pc);
}


inline void mn10300_device::set_logic_flags(uint32_t r)
{
	// and/or/xor/not: set Z,N; clear V (C left undefined -> cleared here).
	m_psw &= ~(FLAG_ZF | FLAG_NF | FLAG_CF | FLAG_VF);
	if (r == 0)          m_psw |= FLAG_ZF;
	if (r & 0x80000000u) m_psw |= FLAG_NF;
}


// 0xF0: reg-indirect moves and indirect call/jmp/ret. Always 2 bytes.
void mn10300_device::execute_f0()
{
	const uint32_t start_pc = m_pc - 1;
	const uint8_t op2 = read_arg8(m_pc);
	const int r  = (op2 >> 2) & 3;   // data/addr register field
	const int am = op2 & 3;          // base address register (aM)

	switch (op2 >> 4)
	{
		case 0x0: m_a[r] = read_mem32(m_a[am]); break;                 // mov (aM),aD
		case 0x4: m_d[r] = read_mem8 (m_a[am]); break;                 // movbu (aM),dD
		case 0x6: m_d[r] = read_mem16(m_a[am]); break;                 // movhu (aM),dD
		case 0x1: write_mem32(m_a[am], m_a[r]); break;                 // mov aS,(aM)
		case 0x5: write_mem8 (m_a[am], m_d[r]); break;                 // movbu dS,(aM)
		case 0x7: write_mem16(m_a[am], m_d[r]); break;                 // movhu dS,(aM)
		case 0x8: { uint8_t v = read_mem8(m_a[am]); m_psw = (m_psw & ~FLAG_ZF) | ((v & m_d[r]) ? 0 : FLAG_ZF); write_mem8(m_a[am], v | m_d[r]); break; } // bset
		case 0x9: { uint8_t v = read_mem8(m_a[am]); m_psw = (m_psw & ~FLAG_ZF) | ((v & m_d[r]) ? 0 : FLAG_ZF); write_mem8(m_a[am], v & ~m_d[r]); break; } // bclr
		case 0xF:
			// control-flow, selected by the whole op2 value
			if (op2 <= 0xF3)      { push32(start_pc + 2); m_pc = m_a[am]; return; } // calls (aM)
			else if (op2 <= 0xF7) { m_pc = m_a[am]; return; }                       // jmp (aM)
			else if (op2 == 0xFC) { m_pc = pop32(); return; }                       // rets
			// TODO(MN10300): FD rti (pop PC+PSW), FE trap
			else logerror("MN10300: unimplemented F0 %02X @ %08X\n", op2, start_pc);
			break;
		default:
			logerror("MN10300: unimplemented F0 %02X @ %08X\n", op2, start_pc);
			break;
	}
	m_pc = start_pc + 2;
}


// 0xF1: cross-type reg-reg arithmetic (between data and address registers).
// Always 2 bytes. dst=bits[1:0], src=bits[3:2].
void mn10300_device::execute_f1()
{
	const uint32_t start_pc = m_pc - 1;
	const uint8_t op2 = read_arg8(m_pc);
	const int dst = op2 & 3, src = (op2 >> 2) & 3;
	const uint32_t C = (m_psw & FLAG_CF) ? 1 : 0;

	switch (op2 >> 4)
	{
		case 0x0: m_d[dst] = do_sub(m_d[dst], m_d[src], 0); break; // sub dS,dD
		case 0x1: m_d[dst] = do_sub(m_d[dst], m_a[src], 0); break; // sub aS,dD
		case 0x2: m_a[dst] = do_sub(m_a[dst], m_d[src], 0); break; // sub dS,aD
		case 0x3: m_a[dst] = do_sub(m_a[dst], m_a[src], 0); break; // sub aS,aD
		case 0x4: m_d[dst] = do_add(m_d[dst], m_d[src], C); break; // addc dS,dD
		case 0x5: m_d[dst] = do_add(m_d[dst], m_a[src], 0); break; // add aS,dD
		case 0x6: m_a[dst] = do_add(m_a[dst], m_d[src], 0); break; // add dS,aD
		case 0x7: m_a[dst] = do_add(m_a[dst], m_a[src], 0); break; // add aS,aD
		case 0x8: m_d[dst] = do_sub(m_d[dst], m_d[src], C); break; // subc dS,dD
		case 0x9: do_sub(m_d[dst], m_a[src], 0); break;            // cmp aS,dD
		case 0xA: do_sub(m_a[dst], m_d[src], 0); break;            // cmp dS,aD
		case 0xD: m_d[dst] = m_a[src]; break;                      // mov aS,dD
		case 0xE: m_a[dst] = m_d[src]; break;                      // mov dS,aD
		default:  logerror("MN10300: illegal F1 %02X @ %08X\n", op2, start_pc); break;
	}
	m_pc = start_pc + 2;
}


// 0xF2: logical / mul / div / shift / special-register moves. Always 2 bytes.
void mn10300_device::execute_f2()
{
	const uint32_t start_pc = m_pc - 1;
	const uint8_t op2 = read_arg8(m_pc);
	const int dst = op2 & 3, src = (op2 >> 2) & 3;

	switch (op2 >> 4)
	{
		case 0x0: m_d[dst] &= m_d[src]; set_logic_flags(m_d[dst]); break; // and
		case 0x1: m_d[dst] |= m_d[src]; set_logic_flags(m_d[dst]); break; // or
		case 0x2: m_d[dst] ^= m_d[src]; set_logic_flags(m_d[dst]); break; // xor
		case 0x3:
			if (op2 < 0x34) { m_d[dst] = ~m_d[dst]; set_logic_flags(m_d[dst]); } // not dD
			else logerror("MN10300: illegal F2 %02X @ %08X\n", op2, start_pc);
			break;
		case 0x4: { int64_t p = (int64_t)(int32_t)m_d[src] * (int32_t)m_d[dst]; m_d[dst] = (uint32_t)p; m_mdr = (uint32_t)(p >> 32); set_nz32(m_d[dst]); break; } // mul
		case 0x5: { uint64_t p = (uint64_t)m_d[src] * m_d[dst]; m_d[dst] = (uint32_t)p; m_mdr = (uint32_t)(p >> 32); set_nz32(m_d[dst]); break; } // mulu
		case 0x6: // div (signed): (MDR:dD) / dS
			if (m_d[src]) { int64_t num = ((int64_t)m_mdr << 32) | m_d[dst]; int32_t dv = (int32_t)m_d[src]; m_d[dst] = (uint32_t)(num / dv); m_mdr = (uint32_t)(num % dv); set_nz32(m_d[dst]); }
			else logerror("MN10300: div by zero @ %08X\n", start_pc); // TODO: real div-zero trap
			break;
		case 0x7: // divu (unsigned)
			if (m_d[src]) { uint64_t num = ((uint64_t)m_mdr << 32) | m_d[dst]; m_d[dst] = (uint32_t)(num / m_d[src]); m_mdr = (uint32_t)(num % m_d[src]); set_nz32(m_d[dst]); }
			else logerror("MN10300: divu by zero @ %08X\n", start_pc);
			break;
		case 0x8: // rol / ror dD (rotate through carry)
		{
			uint32_t c = (m_psw & FLAG_CF) ? 1 : 0;
			if (op2 < 0x84) { uint32_t nc = m_d[dst] >> 31; m_d[dst] = (m_d[dst] << 1) | c; m_psw = (m_psw & ~FLAG_CF) | (nc ? FLAG_CF : 0); } // rol
			else            { uint32_t nc = m_d[dst] & 1;   m_d[dst] = (m_d[dst] >> 1) | (c << 31); m_psw = (m_psw & ~FLAG_CF) | (nc ? FLAG_CF : 0); } // ror
			set_nz32(m_d[dst]);
			break;
		}
		case 0x9: case 0xA: case 0xB: // asl / lsr / asr dS,dD (shift dD by dS)
		{
			uint32_t n = m_d[src] & 0x1F;
			uint32_t carry = 0;
			if (n)
			{
				if ((op2 >> 4) == 0x9)      { carry = (m_d[dst] >> (32 - n)) & 1; m_d[dst] <<= n; }        // asl
				else if ((op2 >> 4) == 0xA) { carry = (m_d[dst] >> (n - 1)) & 1;  m_d[dst] >>= n; }         // lsr
				else                        { carry = (m_d[dst] >> (n - 1)) & 1;  m_d[dst] = (int32_t)m_d[dst] >> n; } // asr
			}
			m_psw = (m_psw & ~FLAG_CF) | (carry ? FLAG_CF : 0);
			set_nz32(m_d[dst]);
			break;
		}
		case 0xD:
			if (op2 < 0xD4) m_mdr = (m_d[dst] & 0x80000000u) ? 0xFFFFFFFFu : 0; // ext dD
			else logerror("MN10300: illegal F2 %02X @ %08X\n", op2, start_pc);
			break;
		case 0xE:
			if (op2 < 0xE4)      m_d[dst] = m_mdr;       // mov mdr,dD
			else if (op2 < 0xE8) m_d[dst] = m_psw;       // mov psw,dD
			else logerror("MN10300: illegal F2 %02X @ %08X\n", op2, start_pc);
			break;
		case 0xF:
			if (op2 & 2) { if (op2 & 1) m_psw = m_d[src]; else m_mdr = m_d[src]; } // mov dS,psw / mov dS,mdr
			else if ((op2 & 1) == 0) m_sp = m_a[src];                              // mov aS,sp
			else logerror("MN10300: illegal F2 %02X @ %08X\n", op2, start_pc);
			break;
		default: logerror("MN10300: unimplemented F2 %02X @ %08X\n", op2, start_pc); break;
	}
	m_pc = start_pc + 2;
}


// 0xF3: 32-bit indexed load/store, EA = aM + dI. Always 2 bytes.
void mn10300_device::execute_f3()
{
	const uint32_t start_pc = m_pc - 1;
	const uint8_t op2 = read_arg8(m_pc);
	const bool    store  = op2 & 0x40;
	const bool    a_reg  = op2 & 0x80;
	const int     reg    = (op2 >> 4) & 3;
	const int     dI     = (op2 >> 2) & 3;
	const int     am     = op2 & 3;
	const uint32_t ea    = m_a[am] + m_d[dI];

	if (store) write_mem32(ea, a_reg ? m_a[reg] : m_d[reg]);
	else      (a_reg ? m_a[reg] : m_d[reg]) = read_mem32(ea);
	m_pc = start_pc + 2;
}


// 0xF4: byte/half indexed load/store, EA = aM + dI. Always 2 bytes.
void mn10300_device::execute_f4()
{
	const uint32_t start_pc = m_pc - 1;
	const uint8_t op2 = read_arg8(m_pc);
	const bool    half   = op2 & 0x80;   // movhu vs movbu
	const bool    store  = op2 & 0x40;
	const int     reg    = (op2 >> 4) & 3;
	const int     dI     = (op2 >> 2) & 3;
	const int     am     = op2 & 3;
	const uint32_t ea    = m_a[am] + m_d[dI];

	if (store) { if (half) write_mem16(ea, m_d[reg]); else write_mem8(ea, m_d[reg]); }
	else       { m_d[reg] = half ? read_mem16(ea) : read_mem8(ea); }
	m_pc = start_pc + 2;
}


// 0xFA: imm16 / disp16 forms. Always 4 bytes (op, op2, imm16-lo, imm16-hi).
void mn10300_device::execute_fa()
{
	const uint32_t start_pc = m_pc - 1;
	const uint8_t op2 = read_arg8(m_pc);
	const uint16_t imm16 = read_arg16(m_pc + 1);   // operand at start+2
	const int dst = op2 & 3, src = (op2 >> 2) & 3;

	if (op2 < 0x80)
	{
		// mov/movbu/movhu (disp16,aM): type=bits[6:5], bit4=dir(store), reg=bits[3:2], aM=bits[1:0]
		const int type = (op2 >> 5) & 3;   // 0=mov.d 1=mov.a 2=movbu.d 3=movhu.d
		const bool store = op2 & 0x10;
		const int r = (op2 >> 2) & 3, am = op2 & 3;
		const uint32_t ea = m_a[am] + (int32_t)(int16_t)imm16;
		switch (type)
		{
			case 0: if (store) write_mem32(ea, m_d[r]); else m_d[r] = read_mem32(ea); break;
			case 1: if (store) write_mem32(ea, m_a[r]); else m_a[r] = read_mem32(ea); break;
			case 2: if (store) write_mem8 (ea, m_d[r]); else m_d[r] = read_mem8 (ea); break;
			case 3: if (store) write_mem16(ea, m_d[r]); else m_d[r] = read_mem16(ea); break;
		}
	}
	else
	{
		switch (op2 & 0xFC)
		{
			case 0xC0: m_d[dst] = do_add(m_d[dst], (int32_t)(int16_t)imm16, 0); break; // add imm16,dD (sx)
			case 0xD0: m_a[dst] = do_add(m_a[dst], (int32_t)(int16_t)imm16, 0); break; // add imm16,aD (sx)
			case 0xC8: do_sub(m_d[dst], (int32_t)(int16_t)imm16, 0); break;            // cmp imm16,dD (sx)
			case 0xD8: do_sub(m_a[dst], (uint32_t)imm16, 0); break;                    // cmp imm16,aD (zx)
			case 0xE0: m_d[dst] &= (uint32_t)imm16; set_logic_flags(m_d[dst]); break;  // and imm16,dD (zx)
			case 0xE4: m_d[dst] |= (uint32_t)imm16; set_logic_flags(m_d[dst]); break;  // or
			case 0xE8: m_d[dst] ^= (uint32_t)imm16; set_logic_flags(m_d[dst]); break;  // xor
			case 0xB0: m_a[dst] = read_mem32(m_sp + imm16); break;                     // mov (disp16,sp),aD
			case 0xB4: m_d[dst] = read_mem32(m_sp + imm16); break;                     // mov (disp16,sp),dD
			case 0xB8: m_d[dst] = read_mem8 (m_sp + imm16); break;                     // movbu (disp16,sp),dD
			case 0xBC: m_d[dst] = read_mem16(m_sp + imm16); break;                     // movhu (disp16,sp),dD
			case 0xA0: m_a[dst] = read_mem32(imm16); break;                            // mov (abs16),aD
			case 0xFC:
				if (op2 == 0xFE)      { m_sp += (int32_t)(int16_t)imm16; }             // add imm16,sp
				else if (op2 == 0xFF) { push32(start_pc + 4); m_pc = start_pc + (int32_t)(int16_t)imm16; return; } // calls (disp16)
				else if (op2 == 0xFC) { m_psw &= (uint32_t)imm16; }                    // and imm16,psw
				else if (op2 == 0xFD) { m_psw |= (uint32_t)imm16; }                    // or imm16,psw
				break;
			default:
				logerror("MN10300: unimplemented FA %02X @ %08X\n", op2, start_pc);
				break;
		}
	}
	m_pc = start_pc + 4;
}


// 0xFE: bit set/clear/test on an absolute address. 5 bytes (abs16) or 7 (abs32).
void mn10300_device::execute_fe()
{
	const uint32_t start_pc = m_pc - 1;
	const uint8_t op2 = read_arg8(m_pc);
	uint32_t addr; uint8_t imm8; int len;

	if (op2 <= 0x02)      { addr = read_arg32(m_pc + 1); imm8 = read_arg8(m_pc + 5); len = 7; }
	else if (op2 >= 0x80 && op2 <= 0x82) { addr = read_arg16(m_pc + 1); imm8 = read_arg8(m_pc + 3); len = 5; }
	else { logerror("MN10300: illegal FE %02X @ %08X\n", op2, start_pc); m_pc = start_pc + 2; return; }

	const uint8_t v = read_mem8(addr);
	m_psw = (m_psw & ~FLAG_ZF) | ((v & imm8) ? 0 : FLAG_ZF);
	const int kind = op2 & 0x0F;
	if (kind == 0x00)      write_mem8(addr, v | imm8);    // bset
	else if (kind == 0x01) write_mem8(addr, v & ~imm8);   // bclr
	// kind == 0x02: btst (no write)
	m_pc = start_pc + len;
}


// Register-list transfer for movm / call / ret.
//
// Register-mask bit -> register (from the disassembler's f_reg_spec and the
// MN10300 ISA):
//   bit 7 = D2   bit 6 = D3   bit 5 = A2   bit 4 = A3
//   bit 1 = the group {D0, D1, A0, A1, MDR, LIR, LAR}  (7 registers, 28 bytes)
//   bits 0, 2, 3 = AM33 extended-register groups the disassembler does not
//                  resolve (would need E0..E7 etc. and the AM33 manual).
//
// Empirical finding (analysis of every movm/ret in the KN7000 program ROM via
// unidasm): 22,771 of 22,808 movm/ret instructions (99.84%) use ONLY bits 4-7
// (D2/D3/A2/A3, the standard callee-saved set); the bit-1 group appears in ~6
// and the AM33 bits in ~30, essentially all inside data swept as code. Real
// function prologues use bits 4-7 exclusively, and the prologue mask always
// equals the epilogue ret mask (0 mismatches over 320 functions), so save/restore
// is symmetric. The bits-4-7 path therefore covers all real code; bit 1 is
// implemented for completeness; the AM33 bits are logged and left for the manual.
//
// push order = bit 7 -> bit 0 (D2 ends at the highest address); load pops in the
// exact reverse so SP and the saved values always round-trip.
void mn10300_device::store_regs(uint8_t mask)  // push (regs -> stack, SP down)
{
	if (mask & 0x80) push32(m_d[2]);
	if (mask & 0x40) push32(m_d[3]);
	if (mask & 0x20) push32(m_a[2]);
	if (mask & 0x10) push32(m_a[3]);
	if (mask & 0x0C) logerror("MN10300: movm AM33 ext regs (mask %02X) not modelled\n", mask);
	if (mask & 0x02) // {D0,D1,A0,A1,MDR,LIR,LAR}
	{
		push32(m_d[0]); push32(m_d[1]); push32(m_a[0]); push32(m_a[1]);
		push32(m_mdr);  push32(m_lir);  push32(m_lar);
	}
	if (mask & 0x01) logerror("MN10300: movm AM33 ext regs (mask %02X) not modelled\n", mask);
}
void mn10300_device::load_regs(uint8_t mask)   // pop (stack -> regs, SP up); exact reverse
{
	if (mask & 0x02)
	{
		m_lar = pop32(); m_lir = pop32(); m_mdr = pop32();
		m_a[1] = pop32(); m_a[0] = pop32(); m_d[1] = pop32(); m_d[0] = pop32();
	}
	if (mask & 0x10) m_a[3] = pop32();
	if (mask & 0x20) m_a[2] = pop32();
	if (mask & 0x40) m_d[3] = pop32();
	if (mask & 0x80) m_d[2] = pop32();
}
