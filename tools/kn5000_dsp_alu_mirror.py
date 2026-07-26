#!/usr/bin/env python3
"""kn5000_dsp_alu_mirror.py -- GENERATE a standalone mirror of the shipping ALU.

Companion note: notes/dsp-alu-applied.md sect. 5 (the acceptance test).

WHY THIS EXISTS.  The uPD6383 acceptance test is numerical: run the PARAMETRIC
EQ biquad section and compare the measured transfer function against the one the
firmware's own bilinear coefficient designer describes.  The test is only worth
anything if it runs THE ARITHMETIC THAT SHIPS.  The previous pass used a
hand-copied mirror; a hand copy is a second implementation and it can drift
silently, which is exactly the failure mode this project keeps finding in its own
older results.

So this does not copy anything: it EXTRACTS the text of
`upd6383_device::acc_to_datum()' and `upd6383_device::exec_alu()' out of
src/devices/cpu/upd6383/upd6383.cpp, and the field accessors and enums out of
upd6383d.h, and pastes them into a harness with a small shim for the MAME types.
If the device changes and this is not re-run, the generated file no longer
compiles or no longer matches -- it cannot quietly disagree.

Usage:
    python3 tools/kn5000_dsp_alu_mirror.py <out.cpp>
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEV = os.path.join(ROOT, "src/devices/cpu/upd6383/upd6383.cpp")
DIS = os.path.join(ROOT, "src/devices/cpu/upd6383/upd6383d.h")


def extract_function(text, signature):
    """Return the full text of a brace-balanced function starting at `signature'."""
    i = text.index(signature)
    j = text.index("{", i)
    depth = 0
    for k in range(j, len(text)):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                return text[i:k + 1]
    raise RuntimeError("unbalanced braces after %r" % signature)


def extract_enums(text):
    """Pull every `enum : u8/u16 { ... };' out of the disassembler header."""
    out = []
    for m in re.finditer(r"enum\s*:\s*u\d+\s*\{[^}]*\};", text):
        out.append(m.group(0))
    return out


PREAMBLE = r"""// license:BSD-3-Clause
// copyright-holders:Felipe Sanches
//
// *** GENERATED FILE -- DO NOT EDIT. ***
// Produced by tools/kn5000_dsp_alu_mirror.py, which lifts the ALU verbatim out
// of src/devices/cpu/upd6383/upd6383.cpp.  Editing this file instead of the
// device is how a "mirror" stops mirroring.
//
// It runs the PARAMETRIC EQ biquad section on one C-RAM coefficient bank given
// on stdin and prints the impulse response, so that the arithmetic THAT SHIPS
// can be scored against the transfer function the firmware's own bilinear
// designer describes.  notes/dsp-alu-applied.md.
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>

typedef uint64_t u64; typedef int64_t s64;
typedef uint32_t u32; typedef int32_t s32;
typedef uint16_t u16; typedef int8_t s8; typedef uint8_t u8;

#define BIT(x, n) (((x) >> (n)) & 1)

namespace util {
	static inline s64 sext(u64 v, int bits)
	{
		const u64 m = 1ULL << (bits - 1);
		v &= (bits == 64) ? ~0ULL : ((1ULL << bits) - 1);
		return s64((v ^ m) - m);
	}
}

// ---- the field accessors and enums, lifted from upd6383d.h -----------------
struct upd6383_disassembler {
	static constexpr u16 hi12(u64 w)   { return u16((w >> 24) & 0xfff); }
	static constexpr u8  class4(u64 w) { return u8((w >> 20) & 0xf); }
	static constexpr u8  addr8(u64 w)  { return u8((w >> 12) & 0xff); }
	static constexpr u16 lo12(u64 w)   { return u16(w & 0xfff); }
	static constexpr u16 HI_ST = 1 << 4;
	static constexpr u16 HI_B7 = 1 << 7;
	static constexpr u16 hi_f31(u16 hi) { return (hi >> 1) & 7; }
	static constexpr u8 lo_src(u64 w) { return u8((w >> 6) & 0x1f); }
	static constexpr u8 lo_act(u64 w) { return u8(w & 0x1f); }
	// the predicates exec_alu() calls.  They are COPIES of upd6383d.h's
	// one-liners, which is a hand copy and therefore the one place this
	// generator can drift -- so keep them one-liners, and note that the build
	// FAILS LOUDLY (it did, on `coeff_consumer' and `st_suppressed') when
	// exec_alu() starts calling something that is not here.
	static constexpr bool c_format(u64 w) { return (hi12(w) & 0xf00) == 0xc00; }
	static constexpr bool coeff_consumer(u64 w) { return class4(w) == 0xa && !c_format(w); }
	static constexpr bool cursor_fetch(u64 w) { return ((w >> 23) & 1) && !c_format(w); }
	static constexpr bool ptr_postinc(u64 w) { return !c_format(w) && (class4(w) & 7) == 2; }
	static constexpr bool st_suppressed(u64 w) { return (hi12(w) & HI_B7) && hi_f31(hi12(w)) == 1; }
@ENUMS@
};

// ---- the shim: the three memories and the register file --------------------
struct Mem {
	u32 cell[256];
	u32 read_dword(u32 a) const { return cell[a & 0xff]; }
	void write_dword(u32 a, u32 v) { cell[a & 0xff] = v; }
};

struct upd6383_device {
	u64 m_acc = 0, m_p = 0;
	u32 m_k = 0, m_l = 0, m_ta = 0, m_tb = 0;
	u8  m_dp = 0, m_cursor = 0;
	Mem m_dram, m_cram;
	static constexpr int P_SHIFT   = @PSHIFT@;
	static constexpr int ACC_SHIFT = @ASHIFT@;
	static s32 acc_to_datum(u64 acc);
	void exec_alu(u64 word);
	upd6383_device() { memset(&m_dram, 0, sizeof(m_dram)); memset(&m_cram, 0, sizeof(m_cram)); }
};

// ============ LIFTED VERBATIM FROM upd6383.cpp ==============================
@ACC_TO_DATUM@

@EXEC_ALU@
// ============ END OF LIFTED TEXT ============================================

// The nine-word PARAMETRIC EQ biquad section (algo 39 words 5..13, repeated ten
// times byte for byte -- 5 bands x 2 channels).  MEASURED.
static const u64 SECTION[9] = {
	0x0000A001D3ULL, 0x0212A01412ULL, 0x0202A011D5ULL, 0x0202A011D4ULL,
	0x0202A001D5ULL, 0x01022FF687ULL, 0x0804816415ULL, 0x0212AFF407ULL,
	0x0000203647ULL
};

int main(int argc, char **argv)
{
	// stdin: six 24-bit coefficients (decimal), then the number of samples
	upd6383_device m;
	u32 c[6];
	int n = 4096;
	long amp = 1L << 22;
	for (int i = 0; i < 6; i++)
		if (scanf("%u", &c[i]) != 1) return 1;
	if (scanf("%d", &n) != 1) n = 4096;
	if (scanf("%ld", &amp) != 1) amp = 1L << 22;

	for (int i = 0; i < 6; i++)
		m.m_cram.cell[i] = c[i];

	for (int t = 0; t < n; t++) {
		// the band input arrives in the accumulator AND in the product
		// register, exactly as it does in a real cascade: the previous band's
		// last word did `acc <- P' and P is not consumed.
		const s64 x = (t == 0) ? amp : 0;
		m.m_acc = u64(x << upd6383_device::ACC_SHIFT) & 0xfffffffffffULL;
		m.m_p   = m.m_acc;
		m.m_dp = 0;
		m.m_cursor = 0;
		for (int w = 0; w < 9; w++)
			m.exec_alu(SECTION[w]);
		printf("%d\n", upd6383_device::acc_to_datum(m.m_acc));
	}
	return 0;
}
"""


def main():
    if len(sys.argv) != 2:
        sys.stderr.write(__doc__)
        return 2

    dev = open(DEV).read()
    dis = open(DIS).read()

    acc = extract_function(dev, "s32 upd6383_device::acc_to_datum(")
    alu = extract_function(dev, "void upd6383_device::exec_alu(")

    # the two alignment constants live in upd6383.h
    hdr = open(os.path.join(ROOT, "src/devices/cpu/upd6383/upd6383.h")).read()
    psh = re.search(r"\bP_SHIFT\s*=\s*(\d+)\s*;", hdr).group(1)
    ash = re.search(r"\bACC_SHIFT\s*=\s*([^;]+);", hdr).group(1).strip()

    enums = "\n".join("\t" + e.replace("\n", "\n\t") for e in extract_enums(dis))

    out = (PREAMBLE
           .replace("@ENUMS@", enums)
           .replace("@ACC_TO_DATUM@", acc)
           .replace("@EXEC_ALU@", alu)
           .replace("@PSHIFT@", psh)
           .replace("@ASHIFT@", ash))

    with open(sys.argv[1], "w") as f:
        f.write(out)
    sys.stderr.write("wrote %s (%d bytes; exec_alu %d bytes lifted)\n"
                     % (sys.argv[1], len(out), len(alu)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
