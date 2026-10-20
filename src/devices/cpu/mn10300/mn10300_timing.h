// license:BSD-3-Clause
// copyright-holders:Felipe Sanches
/*
    MN103002A (AM31 core) timing model: THE CALIBRATION TABLE.

    Every number the core charges for time lives in this file, so calibrating the
    model against the instrument is an edit here and nowhere else. Each entry says
    where it comes from:

      [M p.N]  Matsushita, "MN1030/MN103S Series Instruction Manual" (Pub.No.13250-040E,
               kn7000_scratchpad_snapshot/mn103s_manual.pdf), printed page N. Cycle counts
               cite the instruction's own page in chapter 2 (the appendix, pp.160-182,
               repeats them with that page number); they are the AM31 values, which assume
               "no pipeline stall" and, for a part with caches, "when accessing cachable
               area, cache is always hit" (p.25). The MN103002A is the manual's named AM31
               part (p.2, "CPU Cores").
      [D]      the MN103002A datasheet abstracts (datasheetarchive.com): instruction
               cache 4 KB 2-way, data cache 4 KB 2-way; 15 ns minimum instruction time
               at 66 MHz in "4-fold" (x4 PLL) mode.
      [FW]     the KN7000 firmware's own use of the part (addresses in program.asm,
               technics-roms-disasm/kn7000/disasm, the v16/941 image).
      [CAL]    fitted to a measurement on Felipe's instrument (notes/cpu-timing-2026-10-20/).
      GUESS    no source; a placeholder that pass 9 or the Another World profiler must
               replace. Each one says what would measure it.

    notes/cpu-timing-2026-10-20/README.md explains the model, the evidence and what
    each calibration run gave.
*/

#ifndef MAME_CPU_MN10300_MN10300_TIMING_H
#define MAME_CPU_MN10300_MN10300_TIMING_H

#pragma once

#include <array>
#include <cstdint>

namespace mn10300_timing {

//**************************************************************************
//  1. Clocks
//**************************************************************************

// The core runs at fc = 16 MHz x 4 = 64 MHz (the driver's clock). [D] gives 66 MHz as
// the 4-fold maximum; the KN7000's X1 is 16.0 MHz. [CAL] pass 8's calibration loop
// (64 turns of `add -1,d0 ; bne`, 254 cycles by [M p.46, p.81]) takes about 5 us on the unit,
// which the manual's counts allow only at about 60 MHz or more (at 32 MHz it would take
// 9.4 us). IOCLK, the peripheral clock behind the timers and the serial ports, stays at
// 16 MHz: the firmware's MIDI baud divisor (TM3BR 0x3F) and its 1 kHz tick (TM4BR 0x7D0
// at IOCLK/8) both need exactly 16 MHz, and pass 8 saw TM4 count 2000 per millisecond.
constexpr unsigned IOCLK_DIV = 4;                 // IOCLK = fc / 4

//**************************************************************************
//  2. Instruction cycles  [M chapter 2 and appendix pp.160-182; AM31; cache hit, no stall]
//**************************************************************************

constexpr int C_1        = 1;   // register/immediate ALU (add, sub, cmp, and, or, xor, not, ext*,
                                //   shifts, rol/ror, inc, inc4, clr, mov reg/imm, mov psw/mdr),
                                //   and loads/stores with (An), (d8,An), (d16,An), (d8/d16,SP),
                                //   abs16, and (Di,Am) loads [M pp.26-80]
constexpr int C_LONG     = 2;   // the 6-byte forms: imm32/d32/abs32 operands [M pp.26-65]
constexpr int C_ST_INDEX = 2;   // stores to (Di,An): mov/movbu/movhu Dm,(Di,An), mov Am,(Di,An) [M pp.28, 31, 35]
constexpr int C_BCC      = 1;   // Bcc not taken [M p.81: "3/1"; not taken "depends on the instruction queue"]
constexpr int C_BCC_T    = 3;   // Bcc taken, BRA
constexpr int C_BEXT     = 2;   // bvc/bvs/bnc/bns not taken [M p.81: "4/2"]
constexpr int C_BEXT_T   = 4;   //   taken
constexpr int C_LCC_T    = 1;   // Lcc taken (back to the loop top) [M p.82: "1/2"]
constexpr int C_LCC      = 2;   // Lcc not taken (leaves the loop)
constexpr int C_LRA      = 1;   // lra [M p.82]
constexpr int C_SETLB    = 1;   // setlb [M p.83]
constexpr int C_JMP_D16  = 2;   // jmp (d16,PC) [M p.84]
constexpr int C_JMP_D32  = 3;   // jmp (d32,PC) [M p.84] (4 on the AM30)
constexpr int C_JMP_AN   = 3;   // jmp (An) [M p.84]
constexpr int C_CALL_D16 = 2;   // call (d16,PC): + 1 per saved register [M p.85]
constexpr int C_CALL_D32 = 3;   // call (d32,PC): + 1 per saved register, at least C_CALL_D32_MIN [M p.85]
constexpr int C_CALL_D32_MIN = 4;
constexpr int C_CALLS    = 3;   // calls (An), (d16,PC), (d32,PC) [M pp.87-88]
constexpr int C_RET      = 1;   // ret: 1 + registers restored, at least C_RET_MIN [M p.89]
constexpr int C_RET_MIN  = 5;
constexpr int C_RETF     = 1;   // retf: 1 + registers restored, at least C_RETF_MIN [M p.90]
constexpr int C_RETF_MIN = 2;
constexpr int C_RETS     = 5;   // rets [M p.91] (4 on the AM30)
constexpr int C_RTI      = 4;   // rti [M p.95]
constexpr int C_TRAP     = 4;   // trap [M p.96]
constexpr int C_MOVM_POP = 1;   // movm (SP),regs: 1 + registers [M p.38]
constexpr int C_MOVM_PUSH_MIN = 1; // movm regs,(SP): one per word stored, at least 1 [M p.39]
constexpr int C_BIT      = 5;   // bset/bclr Dm,(An) and imm8,(d8,An) [M pp.66-69]
constexpr int C_BIT_ABS  = 6;   // bset/bclr imm8,(abs32)
constexpr int C_BTST_D8  = 4;   // btst imm8,(d8,An) [M p.65]
constexpr int C_BTST_ABS = 5;   // btst imm8,(abs32) [M p.65]
constexpr int C_BIT_ABS16  = 5; // bset/bclr imm8,(abs16): "not used for AM30/AM31" [M pp.67, 69];
constexpr int C_BTST_ABS16 = 4; //   btst imm8,(abs16) likewise [M p.65]; the core runs them anyway

// mul/mulu: by the significant bytes of the multiplier Dn (0..4) [M pp.52-53]
constexpr std::array<int, 5> C_MUL = { 3, 13, 21, 29, 34 };
// div/divu: by the significant bytes of the dividend {MDR,Dn}; MDR counts in words [M pp.54-55]
constexpr std::array<int, 5> C_DIV = { 4, 14, 22, 30, 38 };

// User-defined instructions (udf, F5/F6/F9/FB/FD): the manual leaves their cycles to the
// part ("*", [M pp.98-99]); the MN103002A's extension unit is not documented anywhere we
// have. GUESS: 1 cycle, and 2 for its multiplies (mulq/mulqu and the udf00/udfu01
// immediate forms). Pass 9 can time them.
constexpr int C_UDF      = 1;
constexpr int C_UDF_MUL  = 2;

// Interrupt and NMI acceptance: not in the instruction manual. GUESS: 7 cycles plus the
// two stack writes (the value the core always charged).
constexpr int C_IRQ      = 7;

// Load-use stall [M pp.108-109, 120-121, 128]: an instruction that uses a register in the
// cycle after the load that fills it waits 2 cycles (cachable memory, DCBYPS = 0) or 1-2
// (other memory). The core does not track which registers the next instruction reads, so it
// charges this average once per single load (pops, movm and ret are not single loads).
// GUESS within the manual's 0..2 range; pass 9 can separate it.
constexpr int C_LOADUSE  = 1;

//**************************************************************************
//  3. Caches  [M p.11, p.25, p.103; D; FW]
//**************************************************************************
//
// The AM31 caches instructions and data for the cachable external space (0x00000000-
// 0x1FFFFFFF and 0x40000000-0x7FFFFFFF); 0x80000000-0xBFFFFFFF is the same memory
// uncached, and 0x20000000-0x3FFFFFFF (on-chip peripherals) is never cached [M p.11].
// Geometry: 4 KB, 2 ways [D], 16-byte lines, 128 sets: the firmware's data-cache purge
// (0x48402307) reads 0x80 entries 0x10 apart in each way's window, 0x28400000 and
// 0x28401000 [FW]. CHCTR (0x20000070) bits as the firmware drives them [FW 0x4840FFA6,
// 0x484022E0, 0x4841015B]: 0 ICEN, 1 DCEN, 2 ICBUSY, 3 DCBUSY, 4 ICINV, 5 DCINV,
// 6 write-through (0 = write-back; the purge is skipped when it is set); bit 7 is set by
// the boot (0x4841009F) and not modelled. A write miss in write-back mode allocates the
// line (GUESS: the manual does not say).
constexpr unsigned LINE_SHIFT = 4;                // 16-byte lines
constexpr unsigned SETS       = 128;
constexpr unsigned LINE_WORDS = 4;                // 32-bit words per line
constexpr uint16_t CHCTR_ICEN = 0x0001, CHCTR_DCEN = 0x0002, CHCTR_ICINV = 0x0010,
                   CHCTR_DCINV = 0x0020, CHCTR_DCWT = 0x0040;

//**************************************************************************
//  4. The external bus: chip selects and MEMCTR0-7
//**************************************************************************
//
// The external space is eight 64 MB chip selects, CSn at 0x40000000 + n * 0x4000000, the
// same memory again uncached at +0x40000000 (the KN7000 schematic multiplexes CS4-CS7 with
// A26-A28/A31, notes/table-rom-structure.md). MEMCTRn (0x32000020 + 2n, 16 bits) holds
// CSn's bus timing. Its layout is NOT documented anywhere we have; this is hypothesis H1,
// read off the values the firmware programs (0x484D7111, the full-TG branch the KN7000
// takes, and 0x4840FFDE):
//
//   n  window      what (KN7000 board)                           MEMCTRn  bits 12:8  bit 5
//   0  0x40000000  IC18 boot/rhythm mask ROM (x16), EXP slots    0x0904   9          16-bit
//   1  0x44000000  IC23 backup SRAM (x16)                        0x0804   8          16-bit
//   2  0x48000000  IC16/IC17 program+table flash (x32)           0x0824   8          32-bit
//   3  0x4C000000  IC14/IC15 fast SRAM, the library (x32)        0x0424   4          32-bit
//   4  0x50000000  IC12/IC13 work DRAM (x32)                     0x0865   8          32-bit (+bits 6, 0: DRAM)
//   5  0x54000000  IC21 flash, IC19 mask ROM, EXP (x16)          0x0004   0          16-bit
//   6  0x58000000  TGs, FDC, DSP index, strap (I/O, x16)         0x0000   0          16-bit
//   7  0x5C000000  LCD controller IC104, DSP data port (x16)     0x0002   0          16-bit, bit 1: external wait
//
// H1: bits 12:8 = wait states (the firmware masks exactly 0x1F00 when it raises CS3's to
// the maximum, 0x48404F3A), bit 5 = 32-bit bus (it is set on exactly the three 32-bit pairs),
// bit 1 = the device ends the cycle (ready line; only CS7, whose LCD controller and DSP
// host bridge have one: DSP.RDV), bit 0 = DRAM. Open: CS5's zero waits fit neither a mask
// ROM nor a flash; the 941 DSP accessor raises MEMCTR3 (CS3) around its 0x9C000000 access
// (CS7 by this map). Pass 9's per-region load/store costs test H1; where they disagree,
// replace the formula with the measured constants in CS_EXTRA.
constexpr int memctr_wait(uint16_t v)    { return (v >> 8) & 0x1f; }
constexpr bool memctr_bus32(uint16_t v)  { return v & 0x0020; }
constexpr bool memctr_extwait(uint16_t v){ return v & 0x0002; }
constexpr bool memctr_dram(uint16_t v)   { return v & 0x0001; }
// Before the firmware programs a chip select: GUESS the slowest setting, 16-bit.
constexpr uint16_t MEMCTR_RESET = 0x1f00;

// One bus transfer costs BUS_DIV * (BUS_BASE + waits) core cycles.
constexpr int BUS_DIV    = 2;   // core cycles per bus clock. GUESS: bus at fc/2 = 32 MHz
constexpr int BUS_BASE   = 2;   // bus clocks of a transfer with no wait state. GUESS
constexpr int DRAM_BURST = 2;   // bus clocks per further word of a line fill from DRAM (page mode). GUESS
constexpr int EXTWAIT    = 8;   // bus clocks a ready-terminated device (CS7) adds. GUESS: the
                                // Another World profiler's LCD-store costs measure it
// Per chip select, core cycles added to every transfer on top of the formula above:
// all 0 until a measurement says otherwise.
constexpr std::array<int, 8> CS_EXTRA = { 0, 0, 0, 0, 0, 0, 0, 0 };

//**************************************************************************
//  5. On-chip peripherals (0x20000000-0x3FFFFFFF)
//**************************************************************************
//
// Extra core cycles per access, by address bits 31:24. GUESS throughout: the CPU's own
// registers (0x20: IVAR, CHCTR) cost nothing extra; the bus controller and DMA (0x32) one
// cycle; the peripherals clocked by IOCLK (0x34: INTC, timers, serial; 0x36: ports) one
// IOCLK period. Pass 9 can time a peripheral register read.
constexpr int IO_CPU   = 0;
constexpr int IO_BUSCTL = 1;
constexpr int IO_PERIPH = 4;

constexpr int io_cost(uint32_t a)
{
	switch (a >> 24)
	{
	case 0x20: return IO_CPU;
	case 0x32: return IO_BUSCTL;
	case 0x34: case 0x36: return IO_PERIPH;
	default:   return IO_BUSCTL;
	}
}

//**************************************************************************
//  Region decode: what the core does for an address (by bits 31:26)
//**************************************************************************

enum region_kind : uint8_t { R_NONE = 0, R_IO = 1, R_CACHED = 2, R_UNCACHED = 3 };
constexpr uint8_t CS_NONE = 8;    // cachable/uncachable space no KN7000 chip select decodes

// region[addr >> 26] = kind << 4 | chip select
constexpr std::array<uint8_t, 64> make_regions()
{
	std::array<uint8_t, 64> r{};
	for (unsigned i = 0; i < 64; i++)
	{
		const uint32_t a = i << 26;
		if (a < 0x20000000u)      r[i] = (R_CACHED << 4) | CS_NONE;
		else if (a < 0x40000000u) r[i] = (R_IO << 4);
		else if (a < 0x60000000u) r[i] = (R_CACHED << 4) | ((a - 0x40000000u) >> 26);
		else if (a < 0x80000000u) r[i] = (R_CACHED << 4) | CS_NONE;
		else if (a < 0xa0000000u) r[i] = (R_UNCACHED << 4) | ((a - 0x80000000u) >> 26);
		else if (a < 0xc0000000u) r[i] = (R_UNCACHED << 4) | CS_NONE;
		else                      r[i] = (R_NONE << 4);
	}
	return r;
}
constexpr std::array<uint8_t, 64> REGIONS = make_regions();

//**************************************************************************
//  Fixed per-opcode costs, built from the constants above
//**************************************************************************
//
// 0 in a table means "the handler charges it" (control flow, data-dependent ops, prefixes).

// single-byte opcode space (0x00-0xEF; 0xF0-0xFF are prefixes or undefined)
constexpr std::array<uint8_t, 256> make_base()
{
	std::array<uint8_t, 256> t{};
	for (unsigned op = 0; op < 0x100; op++)
		t[op] = C_1;
	for (unsigned op = 0xc0; op <= 0xca; op++)
		t[op] = 0;                    // Bcc, bra: handler
	t[0xcc] = C_JMP_D16;
	t[0xcd] = t[0xce] = t[0xcf] = 0;  // call d16, movm: handler (register count)
	for (unsigned op = 0xd0; op <= 0xd9; op++)
		t[op] = 0;                    // Lcc: handler
	t[0xda] = C_LRA;
	t[0xdb] = C_SETLB;
	t[0xdc] = C_JMP_D32;
	t[0xdd] = t[0xde] = t[0xdf] = 0;  // call d32, retf, ret: handler
	for (unsigned op = 0xf0; op <= 0xff; op++)
		t[op] = 0;                    // prefixes charge their own; F7/FF undefined: handler
	return t;
}
constexpr std::array<uint8_t, 256> BASE = make_base();

// 0xF0 xx: indirect moves, bit ops, indirect control flow
constexpr std::array<uint8_t, 256> make_f0()
{
	std::array<uint8_t, 256> t{};
	for (unsigned op2 = 0; op2 < 0x100; op2++)
	{
		switch (op2 >> 4)
		{
		case 0x8: case 0x9: t[op2] = C_BIT; break;           // bset/bclr Dm,(An)
		case 0xf:
			t[op2] = (op2 <= 0xf3) ? C_CALLS                 // calls (An)
			       : (op2 <= 0xf7) ? C_JMP_AN                // jmp (An)
			       : (op2 == 0xfc) ? C_RETS
			       : (op2 == 0xfd) ? C_RTI
			       : (op2 == 0xfe) ? C_TRAP : C_1;
			break;
		default: t[op2] = C_1; break;                       // mov/movbu/movhu (Am)/(An)
		}
	}
	return t;
}
constexpr std::array<uint8_t, 256> F0 = make_f0();

// 0xF8 xx: imm8/d8 forms (bvc/bvs/bnc/bns charged by the handler)
constexpr std::array<uint8_t, 256> make_f8()
{
	std::array<uint8_t, 256> t{};
	for (unsigned op2 = 0; op2 < 0x100; op2++)
		t[op2] = ((op2 & 0xfc) == 0xe8) ? 0 : C_1;
	return t;
}
constexpr std::array<uint8_t, 256> F8 = make_f8();

// 0xFA xx: imm16/d16 forms
constexpr std::array<uint8_t, 256> make_fa()
{
	std::array<uint8_t, 256> t{};
	for (unsigned op2 = 0; op2 < 0x100; op2++)
	{
		const unsigned g = op2 & 0xfc;
		t[op2] = (g == 0xf0 || g == 0xf4) ? C_BIT          // bset/bclr imm8,(d8,An)
		       : (g == 0xf8) ? C_BTST_D8                     // btst imm8,(d8,An) [M p.65]
		       : (op2 == 0xff) ? C_CALLS                     // calls (d16,PC)
		       : C_1;
	}
	return t;
}
constexpr std::array<uint8_t, 256> FA = make_fa();

// 0xFC xx: imm32/d32/abs32 forms
constexpr std::array<uint8_t, 256> make_fc()
{
	std::array<uint8_t, 256> t{};
	for (unsigned op2 = 0; op2 < 0x100; op2++)
		t[op2] = (op2 == 0xff) ? C_CALLS : C_LONG;
	return t;
}
constexpr std::array<uint8_t, 256> FC = make_fc();

// Significant bytes of an operand, for mul/div [M p.52-55]
constexpr int sig_bytes_u(uint32_t v)
{
	return !v ? 0 : (v < 0x100u) ? 1 : (v < 0x10000u) ? 2 : (v < 0x1000000u) ? 3 : 4;
}
constexpr int sig_bytes_s(int32_t v)
{
	if (!v) return 0;
	const uint32_t m = (v < 0) ? ~uint32_t(v) : uint32_t(v);   // magnitude bits below the sign
	return (m < 0x80u) ? 1 : (m < 0x8000u) ? 2 : (m < 0x800000u) ? 3 : 4;
}

// Registers a movm/call/ret mask moves, in words: D2, D3, A2, A3 one each; bit 3 the seven
// {D0,D1,A0,A1,MDR,LIR,LAR}; bits 2/1/0 the AM33 extended groups the core also handles.
constexpr int mask_regs(uint8_t mask)
{
	return ((mask >> 7) & 1) + ((mask >> 6) & 1) + ((mask >> 5) & 1) + ((mask >> 4) & 1)
		+ ((mask & 0x08) ? 7 : 0) + ((mask & 0x04) ? 2 : 0) + ((mask & 0x02) ? 4 : 0) + ((mask & 0x01) ? 2 : 0);
}

} // namespace mn10300_timing

#endif // MAME_CPU_MN10300_MN10300_TIMING_H
