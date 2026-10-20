// license:BSD-3-Clause
// copyright-holders:Felipe Sanches
/*
    MN103002A (AM31 core) timing model: THE CALIBRATION TABLE.

    Every number the core charges for time lives in this file, so calibrating the
    model against the instrument is an edit here and nowhere else. Times are in
    QUARTER cycles of the 64 MHz core clock (the unit's pass 9 resolves below a
    cycle); Q(x) turns cycles into quarters. Each entry says where it comes from:

      [P9 NAME] Felipe's KN7000 (PROGRAM 893), the CPU timing probe (pass 9), test NAME,
               as decoded in technics_roms .../real_dump_v1.3_b893/pass9-check-2026-10-20.txt
               (cycles at 64.02 MHz). The private CPUTIME.BIN is beside it.
      [M p.N]  Matsushita, "MN1030/MN103S Series Instruction Manual" (Pub.No.13250-040E,
               kn7000_scratchpad_snapshot/mn103s_manual.pdf), printed page N, the AM31
               values, which assume "no pipeline stall" and, on a part with caches, that
               the cache always hits (p.25). The MN103002A is its AM31 part (p.2).
      [D]      the MN103002A datasheet abstracts (datasheetarchive.com): I and D caches,
               4 KB 2-way each; 66 MHz in "4-fold" (x4 PLL) mode.
      [FW]     the KN7000 firmware's own use of the part (program.asm, 941 addresses).
      GUESS    not measured; says what would measure it.

    notes/cpu-timing-2026-10-20/README.md has the model, the evidence and the
    calibration runs (pass 9 and pass 8 in this emulator against the unit).
*/

#ifndef MAME_CPU_MN10300_MN10300_TIMING_H
#define MAME_CPU_MN10300_MN10300_TIMING_H

#pragma once

#include <array>
#include <cstdint>

namespace mn10300_timing {

constexpr int Q(double cycles) { return int(cycles * 4.0 + 0.5); }

//**************************************************************************
//  1. Clocks
//**************************************************************************

// fc = 16 MHz x 4 = 64 MHz (the driver's clock): [P9 ADD] 15.6 ns = 1 cycle at 64.02 MHz,
// the 4-fold mode of [D]. IOCLK, behind the timers and serial ports, is 16 MHz = fc / 4:
// the firmware's MIDI divisor (TM3BR 0x3F) and 1 kHz tick (TM4BR 0x7D0 at IOCLK / 8) need
// exactly that, and passes 8 and 9 saw TM4 count 2001 per millisecond.
constexpr unsigned IOCLK_DIV = 4;

//**************************************************************************
//  2. Instruction cycles: the execute part  [M chapter 2; P9]
//**************************************************************************
//
// What an instruction costs once its bytes are in the queue (section 3 adds the fetch).
// Where the unit differs from the manual it is the unit's value.

constexpr int C_1        = Q(1);    // ALU, mov reg/imm, ext*, shifts, inc, cmp, and loads/stores
                                    //   with (An), (d8/d16,An), (d8/d16,SP), abs16, (Di,Am) loads
                                    //   [M pp.26-80; P9 ADD AND MOVR INC ASL2 EXTB MI8 LDSP STSP]
constexpr int C_LONG     = Q(2);    // the 6-byte imm32/d32/abs32 forms [M pp.26-65]; with the
                                    //   fetch they take 2.75 [P9 MI32 LDAB]
constexpr int C_ST_INDEX = Q(2);    // stores to (Di,An) [M pp.28, 31, 35]
constexpr int C_BCC      = Q(1);    // Bcc not taken [M p.81: 1, "depends on the queue"]; + fetch, section 3
constexpr int C_BCC_T    = Q(3);    // Bcc taken, bra [P9 BNE BRA; M p.81]
constexpr int C_BEXT     = Q(2);    // bvc/bvs/bnc/bns not taken [M p.81]; + fetch as Bcc
constexpr int C_BEXT_T   = Q(4);    //   taken [M p.81]
constexpr int C_LCC_T    = Q(1);    // Lcc taken [P9 LBUF: add + lne = 2; M p.82]
constexpr int C_LCC      = Q(2);    // Lcc not taken [M p.82]
constexpr int C_LRA      = Q(1);    // [M p.82]
constexpr int C_SETLB    = Q(1);    // [M p.83]
constexpr int C_JMP_D16  = Q(3);    // jmp (d16,PC): 3.4 with the queue refill [P9 JMP 3.5]; [M p.84] 2
constexpr int C_JMP_D32  = Q(4);    // [M p.84] 3; + 1 as jmp d16. GUESS
constexpr int C_JMP_AN   = Q(3);    // [M p.84]
// call: [P9 CAL0 call + ret = 10, CAL4 with 4 registers = 13]; [M p.85] gives 2 + n (d16)
// and max(4, 3 + n) (d32). Taking ret from the manual (5, as [P9 CALS] rets), call d16 is
// max(5, 4 + n). d32 one more (GUESS).
constexpr int C_CALL_D16 = Q(4), C_CALL_D16_MIN = Q(5);
constexpr int C_CALL_D32 = Q(5), C_CALL_D32_MIN = Q(6);
constexpr int C_CALLS    = Q(4);    // calls (An), (d16,PC), (d32,PC) [P9 CALS, CRET]; [M pp.87-88] 3
constexpr int C_RET      = Q(1), C_RET_MIN = Q(5);    // ret: max(5, 1 + n) [M p.89; P9 CAL0]
constexpr int C_RETF     = Q(1), C_RETF_MIN = Q(4);   // retf: max(4, 1 + n) [P9 CALF]; [M p.90] min 2
constexpr int C_RETS     = Q(5);    // [M p.91; P9 CALS]
constexpr int C_RTI      = Q(4);    // [M p.95]
constexpr int C_TRAP     = Q(4);    // [M p.96]
constexpr int C_MOVM_POP = Q(1), C_MOVM_POP_MIN = Q(3);  // movm (SP),regs: max(3, 1 + n) [P9 MVM1 MVM4; M p.38: 1 + n]
constexpr int C_MOVM_PUSH_MIN = Q(1);                     // movm regs,(SP): max(1, words) [M p.39; P9 MVM4]
constexpr int C_BIT      = Q(5);    // bset/bclr Dm,(An), imm8,(d8,An) [M pp.66-69]
constexpr int C_BIT_ABS  = Q(6);    // bset/bclr imm8,(abs32)
constexpr int C_BTST_D8  = Q(4);    // btst imm8,(d8,An) [M p.65]
constexpr int C_BTST_ABS = Q(5);    // btst imm8,(abs32) [M p.65]
constexpr int C_BIT_ABS16  = Q(5);  // bset/bclr imm8,(abs16): "not used for AM30/AM31" [M pp.67, 69]
constexpr int C_BTST_ABS16 = Q(4);  //   btst imm8,(abs16) likewise [M p.65]

// mul/mulu by the multiplier's significant bytes, div/divu by the dividend's
// [M pp.52-55; P9 MUL0-4 MUU1/4 DIV1/4/N DVU1/4: exactly these]
constexpr std::array<int, 5> C_MUL = { Q(3), Q(13), Q(21), Q(29), Q(34) };
constexpr std::array<int, 5> C_DIV = { Q(4), Q(14), Q(22), Q(30), Q(38) };

// User-defined instructions (F5/F6/F9/FB/FD): "*" in [M pp.98-99], the part's extension
// unit, undocumented. GUESS: 1 cycle, 2 for its multiplies. Not in pass 9.
constexpr int C_UDF      = Q(1);
constexpr int C_UDF_MUL  = Q(2);

// Interrupt and NMI acceptance, beyond the two stack writes. GUESS (not in the manual).
constexpr int C_IRQ      = Q(7);

// Load-use [M pp.108-109, 120-121, 128; P9 LUDP 4 per load + use pair, LUIN 2]: an instruction
// that reads a register loaded by the one before waits until the load's write-back.
constexpr int LU_CACHED   = Q(2);   // cachable external memory [P9 LUDP]
constexpr int LU_WORD     = Q(1);   // other memory, word ([M p.128] LDUSE = 0). GUESS
constexpr int LU_SUBWORD  = Q(2);   // other memory, byte or halfword [M p.128]. GUESS

//**************************************************************************
//  3. The fetch queue  [P9; M p.103, pp.125-127]
//**************************************************************************
//
// The fetch unit reads 8-byte aligned blocks [M p.125]. Fitted to the straight-line tests
// (notes/cpu-timing-2026-10-20/fetch_fit.py): the queue holds 8 bytes and refills at 2.1
// bytes per cycle. An instruction waits until all its bytes are there. That gives 1-2 byte
// instructions 1 cycle, a run of 3-byte ones 1.25 and of 6-byte ones 2.75 [P9 LSRI MI16
// 1.25, MI32 LDAB 2.75], and a lone 4-byte one 1 [P9 LPW5].
// Control flow, fitted to [P9 JMP CAL0 CALF CALS CRET FLLG FLSH BEQ] (fetch_fit.py, part 2):
// a taken jump leaves the queue holding the target's 8-byte block from the target on, plus
// what a transfer slower than a taken branch (call, return: 4-5 cycles) fetched in its extra
// cycles; the next block arrives FQ_HOLD later. An untaken Bcc costs 1 cycle and FQ_UNTAKEN
// bytes of fetch (it fetched its target): a run of them takes 1.75 each [P9 BEQ], a lone one 1.
// Lcc refills from LIR, the loop's first 4 bytes [M p.107; P9 LBUF].
constexpr int FQ_UNIT = 40;         // queue bytes are counted in 1/40 byte
constexpr int FQ_RATE = 21;         // per quarter cycle: 2.1 bytes per cycle
constexpr int FQ_CAP  = 8 * FQ_UNIT;
constexpr int FQ_HOLD = Q(0.75);    // the block after a jump target's
constexpr int FQ_UNTAKEN = 2 * FQ_UNIT;

//**************************************************************************
//  4. Caches  [M p.11, p.25; D; FW; P9]
//**************************************************************************
//
// Cachable: 0x00000000-0x1FFFFFFF and 0x40000000-0x7FFFFFFF; 0x80000000-0xBFFFFFFF is the
// same memory uncached; 0x20000000-0x3FFFFFFF (on-chip) never cached [M p.11]. 4 KB, 2 ways
// [D], 16-byte lines, 128 sets: the firmware's purge reads 0x80 entries 0x10 apart in each
// way's window, 0x28400000 and 0x28401000 [FW 0x48402307]. CHCTR (0x20000070) [FW 0x4840FFA6,
// 0x484022E0, 0x4841015B]: 0 ICEN, 1 DCEN, 2/3 the caches' busy bits (the unit reads 1 while a
// cache is on: [P9] CHCTR = 0x8F), 4 ICINV, 5 DCINV, 6 write-through; bit 7 set at boot, not
// modelled. Write-back with allocation on a write miss: [P9 RAX4] a store to a new line costs
// a fill plus a write-back of the dirty victim (45.25 = 23.92 + 21.33).
constexpr unsigned LINE_SHIFT = 4;
constexpr unsigned SETS       = 128;
constexpr uint16_t CHCTR_ICEN = 0x0001, CHCTR_DCEN = 0x0002, CHCTR_ICINV = 0x0010,
                   CHCTR_DCINV = 0x0020, CHCTR_DCWT = 0x0040;
// An instruction-cache miss costs the line's fill from its chip select plus this: [P9 FL1L,
// TW1L] the first (cold) call of the flash routine and of its RAM copy cost 300 and 204 cycles
// more than a warm one, for the routine's lines.
constexpr int IFILL_EXTRA = Q(0);   // fitted in notes/cpu-timing-2026-10-20/

//**************************************************************************
//  5. The external bus, per chip select  [P9]
//**************************************************************************
//
// Eight 64 MB chip selects, CSn at 0x40000000 + n * 0x4000000 and uncached at +0x40000000
// (the schematic multiplexes CS4-CS7 with A26-A28/A31). Each cost is in quarter cycles
// BEYOND a cache hit (the instruction's own count already has the 1-cycle access): one
// uncached load or store of 8/16 bits and of 32 bits, a line fill (load miss), and writing a
// dirty line back. Measured values are [P9 test]; the rest is derived as noted.
struct cs_cost
{
	int rd16, rd32, wr16, wr32, fill, wb;
	int wait_ref;   // MEMCTR bits 12:8 when measured; -1: MEMCTR changes do not move it
	int xfers;      // bus transfers in a line fill (16 bytes: 4 on a 32-bit chip select, 8 on 16)
};

// MEMCTRn (0x32000020 + 2n) as the firmware leaves it [P9 registers]: 0x8904, 0x0804, 0x0824,
// 0x0424, 0x0865, 0x0004, 0x0000, 0x0002. Bits 12:8 do NOT give every chip select's waits:
// CS5 (0) costs what CS1 (8) does and CS6/CS7 (0) are the slowest. For CS0-CS3 the measured
// costs do follow them at about one core cycle per unit (CS3: 4 -> 4.5 per word, CS2: 8 -> 8,
// CS0: 9 -> 8 per halfword), so for those a firmware change of the field (941's DSP accessor
// sets MEMCTR3 = 0x924) moves each transfer by one cycle per unit (MEMCTR_STEP). GUESS beyond
// the values measured.
constexpr int MEMCTR_STEP = Q(1);
constexpr std::array<cs_cost, 8> CS = {{
	// CS0 0x40000000: IC18 boot/rhythm mask ROM, x16. [P9 BTW4] fill 64.07; a halfword
	//   transfer is 64/8 = 8 cycles (uncached reads not measured).
	{ Q(7), Q(15), Q(7), Q(15), Q(64.07), Q(64), 9, 8 },
	// CS1 0x44000000: IC23 backup SRAM, x16. [P9 SRL1/2 SRL4] 8.06 / 17.06 per load; stores
	//   and fills not measured: as loads, and a fill as CS5's (same per-transfer cost).
	{ Q(8.06), Q(17.06), Q(8.06), Q(17.06), Q(59.94), Q(59.94), 8, 8 },
	// CS2 0x48000000: IC16/IC17 program + table flash, x32. [P9 PRW4] fill 31.84 (the table
	//   half, [P9 TBW4] 28.56: FILL_TABLE_FLASH); single reads not measured: fill / 4.
	{ Q(7), Q(7), Q(7), Q(7), Q(31.84), Q(31.84), 8, 4 },
	// CS3 0x4C000000: IC14/IC15 fast SRAM, the library, x32. [P9 LBW4] fill 17.87; single
	//   accesses fill / 4.
	{ Q(3.5), Q(3.5), Q(3.5), Q(3.5), Q(17.87), Q(17.87), 4, 4 },
	// CS4 0x50000000: IC12/IC13 work DRAM, x32. [P9 RUL1-4 RUQ2/4] 5.18 per load of any width,
	//   [P9 RUS1-4 RUY4] 4.75 per store, [P9 RAW4] fill 23.92, [P9 RAX4] write-back 21.33.
	{ Q(5.18), Q(5.18), Q(4.75), Q(4.75), Q(23.92), Q(21.33), -1, 4 },
	// CS5 0x54000000: IC21 custom flash, IC19 picture ROM, EXP slots, x16. [P9 CUL1/2 CUL4]
	//   8.06 / 17.06 per load; [P9 C2W4] fill 59.94 (IC19 [P9 PIW4] 57.44: FILL_IC19).
	{ Q(8.06), Q(17.06), Q(8.06), Q(17.06), Q(59.94), Q(59.94), -1, 8 },
	// CS6 0x58000000: tone generators, FDC, DSP index, the strap, x16. [P9 STRP] 35.03 per
	//   halfword load; stores GUESS the same.
	{ Q(35.03), Q(71.06), Q(35.03), Q(71.06), Q(280), Q(280), -1, 8 },
	// CS7 0x5C000000: LCD controller IC104 (frame at 0x9CE00000), DSP data port, x16, ready-
	//   terminated. [P9 LCL2] 43.41 per halfword load, [P9 LCS2 LCS4] 27.13 / 55.88 per store;
	//   a word load as two halfwords ([P9 LCL4 LCQ4], 3.2 with 1 clean run of 64, are not used).
	//   The DSP data port is taken to cost what the LCD does. GUESS
	{ Q(43.41), Q(87.82), Q(27.13), Q(55.88), Q(347), Q(347), -1, 8 },
}};
// Stores to the I/O chip selects (CS6, CS7) are posted: the CPU goes on while the bus carries
// the store, and the next external access (load, line fill or write-back, another store) waits
// for it. Back to back, as pass 9 timed them, each store costs its full bus time either way.
// Inferred from pass 8: the firmware's DSP index write (a CS6 store, then cached code) re-latches
// in 1.69 us on the unit; with the store's 36 cycles paid in line it took 2.17 us here, posted
// 1.67. Work RAM's uncached stores are not: posted, the loop after [P9 RUS1-4 RUY4] would hide
// part of the last one, and the unit shows no such overlap (5.78 per store; 5.51 posted). GUESS
// beyond those two measurements.
constexpr unsigned POSTED_CS = 0xc0;          // chip selects whose uncached stores are posted
constexpr int FILL_TABLE_FLASH = Q(28.56);   // CS2 below 0x48400000 [P9 TBW4]
constexpr int FILL_IC19        = Q(57.44);   // CS5 at 0x57xxxxxx [P9 PIW4]
// The values pass 9 read; also the registers' reset values, which are unknown except that
// MEMCTR0 bit 15 is set at reset (the boot code keeps it, and the unit reads 0x8904).
constexpr std::array<uint16_t, 8> MEMCTR_INIT = { 0x8904, 0x0804, 0x0824, 0x0424, 0x0865, 0x0004, 0x0000, 0x0002 };
constexpr int memctr_wait(uint16_t v) { return (v >> 8) & 0x1f; }

//**************************************************************************
//  6. On-chip peripherals (0x20000000-0x3FFFFFFF)  [P9]
//**************************************************************************

constexpr int IO_SLOW = Q(6.99);    // 0x34xxxxxx (INTC, timers, serial) [P9 TMBC TMMD ICR];
                                    //   0x36xxxxxx (ports) assumed the same
constexpr int IO_FAST = Q(3.0);     // 0x20xxxxxx (CHCTR) [P9 CHC 2.99], 0x32xxxxxx (MEMCTR)
                                    //   [P9 MEM0 3.05]; the rest (0x28 purge window) assumed the same

constexpr int io_cost(uint32_t a)
{
	return ((a >> 24) == 0x34 || (a >> 24) == 0x36) ? IO_SLOW : IO_FAST;
}

//**************************************************************************
//  Region decode (by address bits 31:26)
//**************************************************************************

enum region_kind : uint8_t { R_NONE = 0, R_IO = 1, R_CACHED = 2, R_UNCACHED = 3 };
constexpr uint8_t CS_NONE = 8;    // space no KN7000 chip select decodes

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
//  Fixed per-opcode costs, from the constants above
//**************************************************************************
//
// 0 means the handler charges it (control flow, data-dependent ops, prefixes).

constexpr std::array<uint8_t, 256> make_base()
{
	std::array<uint8_t, 256> t{};
	for (unsigned op = 0; op < 0x100; op++)
		t[op] = C_1;
	for (unsigned op = 0xc0; op <= 0xca; op++)
		t[op] = 0;                    // Bcc, bra
	t[0xcc] = C_JMP_D16;
	t[0xcd] = t[0xce] = t[0xcf] = 0;  // call d16, movm (register count)
	for (unsigned op = 0xd0; op <= 0xd9; op++)
		t[op] = 0;                    // Lcc
	t[0xda] = C_LRA;
	t[0xdb] = C_SETLB;
	t[0xdc] = C_JMP_D32;
	t[0xdd] = t[0xde] = t[0xdf] = 0;  // call d32, retf, ret
	for (unsigned op = 0xf0; op <= 0xff; op++)
		t[op] = 0;                    // prefixes; F7/FF undefined
	return t;
}
constexpr std::array<uint8_t, 256> BASE = make_base();

constexpr std::array<uint8_t, 256> make_f0()
{
	std::array<uint8_t, 256> t{};
	for (unsigned op2 = 0; op2 < 0x100; op2++)
	{
		switch (op2 >> 4)
		{
		case 0x8: case 0x9: t[op2] = C_BIT; break;
		case 0xf:
			t[op2] = (op2 <= 0xf3) ? C_CALLS : (op2 <= 0xf7) ? C_JMP_AN
			       : (op2 == 0xfc) ? C_RETS : (op2 == 0xfd) ? C_RTI : (op2 == 0xfe) ? C_TRAP : C_1;
			break;
		default: t[op2] = C_1; break;
		}
	}
	return t;
}
constexpr std::array<uint8_t, 256> F0 = make_f0();

constexpr std::array<uint8_t, 256> make_f8()
{
	std::array<uint8_t, 256> t{};
	for (unsigned op2 = 0; op2 < 0x100; op2++)
		t[op2] = ((op2 & 0xfc) == 0xe8) ? 0 : C_1;     // bvc/bvs/bnc/bns: handler
	return t;
}
constexpr std::array<uint8_t, 256> F8 = make_f8();

constexpr std::array<uint8_t, 256> make_fa()
{
	std::array<uint8_t, 256> t{};
	for (unsigned op2 = 0; op2 < 0x100; op2++)
	{
		const unsigned g = op2 & 0xfc;
		t[op2] = (g == 0xf0 || g == 0xf4) ? C_BIT : (g == 0xf8) ? C_BTST_D8 : (op2 == 0xff) ? C_CALLS : C_1;
	}
	return t;
}
constexpr std::array<uint8_t, 256> FA = make_fa();

constexpr std::array<uint8_t, 256> make_fc()
{
	std::array<uint8_t, 256> t{};
	for (unsigned op2 = 0; op2 < 0x100; op2++)
		t[op2] = (op2 == 0xff) ? C_CALLS : C_LONG;
	return t;
}
constexpr std::array<uint8_t, 256> FC = make_fc();

constexpr int sig_bytes_u(uint32_t v)
{
	return !v ? 0 : (v < 0x100u) ? 1 : (v < 0x10000u) ? 2 : (v < 0x1000000u) ? 3 : 4;
}
constexpr int sig_bytes_s(int32_t v)
{
	if (!v) return 0;
	const uint32_t m = (v < 0) ? ~uint32_t(v) : uint32_t(v);
	return (m < 0x80u) ? 1 : (m < 0x8000u) ? 2 : (m < 0x800000u) ? 3 : 4;
}

// Registers a movm/call/ret mask moves: D2, D3, A2, A3 one each; bit 3 the seven
// {D0,D1,A0,A1,MDR,LIR,LAR}; bits 2/1/0 the AM33 extended groups the core also handles.
constexpr int mask_regs(uint8_t mask)
{
	return ((mask >> 7) & 1) + ((mask >> 6) & 1) + ((mask >> 5) & 1) + ((mask >> 4) & 1)
		+ ((mask & 0x08) ? 7 : 0) + ((mask & 0x04) ? 2 : 0) + ((mask & 0x02) ? 4 : 0) + ((mask & 0x01) ? 2 : 0);
}

// Register masks for the load-use check: bits 0-3 D0-D3, bits 4-7 A0-A3.
constexpr unsigned RD(int n) { return 1u << (n & 3); }
constexpr unsigned RA(int n) { return 0x10u << (n & 3); }

// The registers an instruction reads, from its first two bytes (asked only right after a load).
constexpr unsigned src_regs(uint8_t op, uint8_t op2)
{
	const int lo = op & 3, hi = (op >> 2) & 3;
	if (op < 0xf0)
	{
		switch (op >> 4)
		{
		case 0x0: return lo ? RD(hi) : 0;                          // store Dm,(abs16) / clr
		case 0x1: return RD(lo);                                   // ext*
		case 0x2: return (op < 0x24) ? RA(lo) : (op >= 0x28 && op < 0x2c) ? RD(lo) : 0;
		case 0x3: return 0;                                        // loads (abs16), mov sp,An
		case 0x4: return (lo == 0 || lo == 2) ? RD(hi) : RA(hi);   // inc, mov Rm,(d8,SP)
		case 0x5: return (op < 0x54) ? RA(lo) : (op < 0x58) ? RD(lo) : 0;
		case 0x6: return RD(hi) | RA(lo);                          // mov Dm,(An)
		case 0x7: return RA(lo);                                   // mov (Am),Dn
		case 0x8: return (hi == lo) ? 0 : RD(hi);                  // mov imm8 / mov Dm,Dn
		case 0x9: return (hi == lo) ? 0 : RA(hi);
		case 0xa: return RD(hi) | RD(lo);                          // cmp
		case 0xb: return RA(hi) | RA(lo);
		case 0xe: return RD(hi) | RD(lo);                          // add Dm,Dn
		default:  return 0;                                        // branches, call/ret, movm
		}
	}
	const int d = op2 & 3, s = (op2 >> 2) & 3;
	switch (op)
	{
	case 0xf0:
		switch (op2 >> 4)
		{
		case 0x0: case 0x4: case 0x6: case 0xf: return RA(d);    // loads (Am), calls/jmp (An)
		case 0x1: return RA(s) | RA(d);
		case 0x5: case 0x7: case 0x8: case 0x9: return RD(s) | RA(d);
		default: return 0;
		}
	case 0xf1: case 0xf2: case 0xf5: case 0xf6:
		return RD(s) | RD(d) | RA(s) | RA(d);
	case 0xf3: return RA(d) | RD(s) | ((op2 & 0x40) ? ((op2 & 0x80) ? RA(op2 >> 4) : RD(op2 >> 4)) : 0);
	case 0xf4: return RA(d) | RD(s) | ((op2 & 0x40) ? RD(op2 >> 4) : 0);
	case 0xf8: case 0xfa: case 0xfc:
		if (op2 < 0x80)                                          // (d,Am): a store also reads its register
			return RA(d) | ((op2 & 0x10) ? ((((op2 >> 5) & 3) == 1) ? RA(s) : RD(s)) : 0);
		if (op2 < 0xa0)                                          // stores to (d,SP)/(abs)
			return RD(s) | RA(s);
		if (op2 < 0xc0)                                          // loads from (d,SP)/(abs)
			return 0;
		return RD(d) | RA(d);                                    // ALU with immediates, bit ops
	case 0xf9: case 0xfb: case 0xfd:
		return RD(d);
	default:
		return 0;
	}
}

} // namespace mn10300_timing

#endif // MAME_CPU_MN10300_MN10300_TIMING_H
