// license:BSD-3-Clause
// copyright-holders:Felipe Correa da Silva Sanches
//
// Standalone driver for upd6383_disassembler, so the microprogram corpus can be
// disassembled without building unidasm (which a FOCUSED MAME build does not produce:
// unidasm.cpp references every disassembler in the tree, and a focused build compiles
// only the ones its drivers use).  In a full build, `unidasm -arch upd6383 <image>'
// does the same job -- build.sh registers the arch there too.
//
// Build against an existing kn7000_mame_build tree:
//   cd ../kn7000_mame_build
//   g++ -std=c++20 -O1 -DMAME_DEBUG -DMAME_PROFILER -DCRLF=2 -DLSB_FIRST \
//       -DFLAC__NO_DLL -DPUGIXML_HEADER_ONLY -DASMJIT_STATIC \
//       -I src/osd -I src/emu -I src/devices -I src/lib -I src/lib/util -I 3rdparty \
//       -I build/generated/emu -I 3rdparty/asio/include -I 3rdparty/expat/lib \
//       -o /tmp/dasmharness ../kn7000_mame/tools/kn5000_dsp_dasm_harness.cpp \
//       build/linux_gcc/obj/x64/Release/src/devices/cpu/upd6383/upd6383d.o \
//       build/linux_gcc/bin/x64/Release/libemu.a build/linux_gcc/bin/x64/Release/libutils.a -lpthread
//
// Usage:  dasmharness algo00.bin algo01.bin ...

#include "emu.h"
#include "cpu/upd6383/upd6383d.h"
#include <cstdio>
#include <vector>

class buf : public util::disasm_interface::data_buffer
{
public:
	std::vector<u8> d;
	virtual u8  r8(offs_t pc) const override { return pc < d.size() ? d[pc] : 0; }
	virtual u16 r16(offs_t pc) const override { return 0; }
	virtual u32 r32(offs_t pc) const override { return 0; }
	virtual u64 r64(offs_t pc) const override { return 0; }
};

int main(int argc, char **argv)
{
	for (int a = 1; a < argc; a++)
	{
		FILE *f = fopen(argv[a], "rb");
		if (!f) continue;
		buf b; int c;
		while ((c = fgetc(f)) != EOF) b.d.push_back(u8(c));
		fclose(f);
		upd6383_disassembler dasm;
		printf("=== %s (%u words)\n", argv[a], unsigned(b.d.size() / 5));
		for (offs_t pc = 0; pc + 5 <= b.d.size(); pc += 5)
		{
			std::ostringstream s;
			dasm.disassemble(s, pc, b, b);
			printf("%4u  %s\n", unsigned(pc / 5), s.str().c_str());
		}
	}
	return 0;
}
