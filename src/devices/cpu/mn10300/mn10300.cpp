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
	, m_pc(0), m_sp(0), m_mdr(0), m_psw(0)
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
		case 0xFC: execute_fc(); break;   // imm32 / disp32 forms (mov imm32,reg etc.)
		case 0xF8: execute_f8(); break;   // imm8 / disp8 forms (incl. add imm8,sp)

		// TODO(MN10300): 0xF0,0xF1,0xF2,0xF3,0xF4,0xF5,0xF6,0xF9,0xFA,0xFB,0xFD,0xFE
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


// Register-list transfer for movm / call / ret.
//
// TODO(MN10300): the register-mask bit->register mapping is only partly known.
// Per the disassembler, bits 7..4 = D2,D3,A2,A3 (reliable); bits 3..0 index AM33
// extended-register groups the disassembler did NOT resolve. Getting the push
// order and SP adjustment right is critical (a wrong guess corrupts every stack
// frame). Implemented conservatively for the reliable bits; the low bits and the
// exact order MUST be confirmed against the MN103E/AM33 manual and observed
// boot-code behaviour before this core can run real code.
void mn10300_device::store_regs(uint8_t mask)  // push
{
	if (mask & 0x80) push32(m_d[2]);
	if (mask & 0x40) push32(m_d[3]);
	if (mask & 0x20) push32(m_a[2]);
	if (mask & 0x10) push32(m_a[3]);
	// TODO: bits 0x08..0x01 (D0,D1,A0,A1 / extended groups), exact order.
}
void mn10300_device::load_regs(uint8_t mask)   // pop (reverse order)
{
	if (mask & 0x10) m_a[3] = pop32();
	if (mask & 0x20) m_a[2] = pop32();
	if (mask & 0x40) m_d[3] = pop32();
	if (mask & 0x80) m_d[2] = pop32();
	// TODO: matching low-bit handling.
}
