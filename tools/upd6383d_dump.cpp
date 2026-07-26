// license:BSD-3-Clause
// copyright-holders:Felipe Sanches
/***************************************************************************

    upd6383d_dump.cpp -- MIRROR-AGREEMENT HARNESS for the uPD6383 disassembler.

    The KN5000 effects-DSP ISA is described by TWO deliberately identical
    disassemblers:

        src/devices/cpu/upd6383/upd6383d.{cpp,h}      (MAME, C++)
        kn5000-roms-disasm/dsp/tools/dsp_disasm.py    (the living ISA reference)

    They have drifted apart before -- and each time, the drift was invisible
    because nothing ever ran them side by side.  This program is the missing
    half: it reads `<iram_index> <10-hex-nibble word>' lines on stdin and prints
    `upd6383_disassembler::text(word, at)' for each, so the Python mirror's
    output can be diffed against it line for line over the whole 3057-word
    corpus.  It executes nothing and models no hardware.

    BUILD (inside the disposable MAME build tree, which already compiles the
    disassembler; tools/upd6383d_diff.sh does this for you):

        g++ -std=c++20 -O1 -I src/osd -I src/emu -I src/devices -I src/lib \
            -I src/lib/util -I 3rdparty -I build/generated/emu \
            -DCRLF=2 -DLSB_FIRST \
            tools/upd6383d_dump.cpp src/devices/cpu/upd6383/upd6383d.cpp \
            src/lib/util/disasmintf.cpp -o upd6383d_dump

***************************************************************************/

#include "emu.h"
#include "cpu/upd6383/upd6383d.h"

#include <cstdio>
#include <iostream>
#include <string>

int main()
{
	std::string line;
	while (std::getline(std::cin, line))
	{
		if (line.empty() || line[0] == '#')
			continue;

		long long at = -1;
		unsigned long long w = 0;
		if (std::sscanf(line.c_str(), "%lld %llx", &at, &w) != 2)
		{
			std::fprintf(stderr, "upd6383d_dump: cannot parse '%s'\n", line.c_str());
			return 2;
		}

		std::cout << upd6383_disassembler::text(u64(w) & 0xfffffffffULL, int(at)) << '\n';
	}
	return 0;
}
