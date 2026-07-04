// license:BSD-3-Clause
// copyright-holders:Felipe Sanches
/*
    Standalone MN10300 instruction-LENGTH decoder + validator.

    The single most error-prone part of a variable-length CPU core is advancing
    the program counter by exactly the right number of bytes per instruction. A
    wrong length desynchronises the whole fetch stream. This tiny program lets us
    verify that logic WITHOUT a full MAME build: it reimplements the MN10300
    instruction length (mirroring the structure of MAME's mn103dasm.cpp) and
    checks it, instruction-by-instruction, against MAME unidasm's own lengths
    over the real KN7000 program ROM.

    The mn10300_insn_length() function below is the reference the CPU core's
    execute_run() must agree with: every implemented opcode must consume exactly
    this many bytes.

    Build & run (see validate_lengths.sh):
        g++ -O2 -std=c++17 -o mn10300_length mn10300_length.cpp
        ./mn10300_length <program.rom> <ground_truth.txt>

    ground_truth.txt lines: "<file_offset_hex> <length> <illegal 0|1>"
    (generated from unidasm; see validate_lengths.sh).

    Known expected discrepancies, both accounted for by the validator:
      * 0xF4 (movbu/movhu indexed): unidasm's disassemble_f4 returns length 1,
        but the instruction is really 2 bytes (a documented disassembler bug).
        Our length (2) is correct; these lines are skipped.
      * illegal opcodes: unidasm prints "?" and returns length 1 for sub-opcodes
        it does not decode. Those lines are marked illegal and skipped (a CPU core
        would trap on them, so their "length" is irrelevant).
*/

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>

// The length decoder under test is the same header the CPU core uses.
#include "../src/devices/cpu/mn10300/mn10300_insn_length.h"


int main(int argc, char **argv)
{
	if (argc < 3) { fprintf(stderr, "usage: %s <program.rom> <ground_truth.txt>\n", argv[0]); return 2; }

	FILE *rf = fopen(argv[1], "rb");
	if (!rf) { perror("rom"); return 2; }
	fseek(rf, 0, SEEK_END); long sz = ftell(rf); fseek(rf, 0, SEEK_SET);
	std::vector<uint8_t> rom(sz);
	if (fread(rom.data(), 1, sz, rf) != (size_t)sz) { perror("read"); return 2; }
	fclose(rf);

	FILE *gt = fopen(argv[2], "r");
	if (!gt) { perror("gt"); return 2; }

	long total = 0, checked = 0, ok = 0, f4bug = 0, illegal = 0, bad = 0;
	long off; int len, ill;
	while (fscanf(gt, "%lx %d %d", &off, &len, &ill) == 3)
	{
		total++;
		if (off < 0 || off + 1 >= sz) continue;
		const uint8_t opc = rom[off];
		if (opc == 0xF4) { f4bug++; continue; }   // known unidasm bug
		if (ill)         { illegal++; continue; } // unidasm "?" -> core traps
		checked++;
		int mine = mn10300_insn_length(&rom[off]);
		if (mine == len) ok++;
		else { bad++; if (bad <= 20) printf("MISMATCH off=%06lx op=%02x mine=%d unidasm=%d\n", off, opc, mine, len); }
	}
	fclose(gt);

	printf("\nMN10300 length validation:\n");
	printf("  ground-truth instructions : %ld\n", total);
	printf("  F4 disassembler-bug lines : %ld (skipped; our length 2 is correct)\n", f4bug);
	printf("  illegal opcodes (unidasm ?) : %ld (skipped; core traps)\n", illegal);
	printf("  legal checked             : %ld\n", checked);
	printf("  matched                   : %ld\n", ok);
	printf("  MISMATCHES                : %ld\n", bad);
	return bad == 0 ? 0 : 1;
}
