// license:BSD-3-Clause
// copyright-holders:Felipe Sanches
// Standalone mirror of upd6383_device::exec_alu(), byte-for-byte the same
// arithmetic, so that the C++ that ships can be compared against the Python
// model the decode was derived in.  Prints the impulse response of the
// PARAMETRIC EQ biquad section for one coefficient bank given on stdin.
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>

typedef uint64_t u64; typedef int64_t s64;
typedef uint32_t u32; typedef int32_t s32;
typedef uint16_t u16; typedef int8_t s8; typedef uint8_t u8;

static s64 sext(u64 v, int bits) {
	const u64 m = 1ULL << (bits - 1);
	v &= (bits == 64) ? ~0ULL : ((1ULL << bits) - 1);
	return s64((v ^ m) - m);
}

static const int P_SHIFT = 6, ACC_SHIFT = 22 - P_SHIFT;

struct Mach {
	u64 acc = 0, p = 0;
	u32 ta = 0, tb = 0;
	u8 dp = 0, cursor = 0;
	s32 dram[256] = {0};
	u32 cram[256] = {0};

	static s32 acc_to_datum(u64 acc) {
		const s64 v = sext(acc, 44) >> ACC_SHIFT;
		if (v >  0x7fffff) return  0x7fffff;
		if (v < -0x800000) return -0x800000;
		return s32(v);
	}

	void exec(u64 word) {
		const u16 hi = u16((word >> 24) & 0xfff);
		const u8  cl = u8((word >> 20) & 0xf);
		const s8  dd = s8((word >> 12) & 0xff);
		const u8  src = u8((word >> 6) & 0x1f);
		const u8  op = u8(word & 0x1f);

		s32 L = 0;
		switch (src) {
		case 0x10: L = acc_to_datum(acc); break;
		case 0x19: L = s32(sext(ta, 24)); break;
		case 0x1a: L = s32(sext(tb, 24)) >> 1; break;
		case 0x07: L = s32(sext(u32(dram[dp]) & 0xffffff, 24)); break;
		default: fprintf(stderr, "unanchored SRC %02X\n", src); exit(2);
		}

		if (hi & 0x010) { dram[dp] = acc_to_datum(acc); acc = 0; }

		acc = (acc + p) & 0xfffffffffffULL;
		p = 0;

		switch (op) {
		case 0x13: ta = u32(L) & 0xffffff; break;
		case 0x14: tb = u32(L) & 0xffffff; break;
		case 0x07: dram[dp] = s32(sext(u32(L) & 0xffffff, 24)); break;
		default: break;
		}

		if (cl == 0xa) {
			const u32 coef = cram[cursor] & 0xffffff;
			p = u64((sext(coef, 24) * s64(L)) >> P_SHIFT) & 0xfffffffffffULL;
			cursor++;
		}

		if ((cl & 7) == 2) dp = u8(dp + dd);
	}
};

static const u64 SECTION[9] = {
	0x0000A001D3ULL, 0x0212A01412ULL, 0x0202A011D5ULL, 0x0202A011D4ULL,
	0x0202A001D5ULL, 0x01022FF687ULL, 0x0804816415ULL, 0x0212AFF407ULL,
	0x0000203647ULL };

int main(int argc, char **argv) {
	if (argc < 8) { fprintf(stderr, "usage: %s c0..c5 nsamp [amp]\n", argv[0]); return 1; }
	Mach m;
	for (int i = 0; i < 6; i++) m.cram[i] = u32(strtoul(argv[1 + i], nullptr, 16));
	const int n = atoi(argv[7]);
	const s32 amp = (argc > 8) ? atoi(argv[8]) : (1 << 22);

	for (int k = 0; k < n; k++) {
		const s32 x = (k == 0) ? amp : 0;
		m.acc = u64(s64(x) << ACC_SHIFT) & 0xfffffffffffULL;
		m.dp = 0; m.cursor = 0;
		for (int i = 0; i < 9; i++) m.exec(SECTION[i]);
		printf("%d\n", Mach::acc_to_datum(m.acc));
	}
	return 0;
}
