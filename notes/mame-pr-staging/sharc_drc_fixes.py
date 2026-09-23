"""Three correctness fixes in the shared 2106x DRC, before the commit is split.

Each was re-verified here against the source rather than taken on report.

1. ALUSAT WAS BAKED AT TRANSLATION TIME AND NEVER INVALIDATED.
   MODE1.ALUSAT was read when a block was compiled, with the three MODE1
   immediate generators storing cache_dirty to cover a change. That does not
   cover the status-stack pop -- POP STS, and the automatic pop on returning
   from interrupts 6-8 -- which rewrites m_core->mode1 with no such store; and
   cache_dirty is only examined once per timeslice (execute_run_drc), so even
   the covered path keeps running stale blocks for the rest of the quantum.
   A program that sets ALUSAT in a handler and pops the old MODE1 on return
   then gets silently wrong arithmetic, DRC-only, diverging from the
   interpreter -- which tests the bit per operation. Read it at runtime, as
   the interpreter does, and drop the three cache_dirty stores.

2. I4-I7 USED AS UML SCRATCH.
   sharc.cpp:758 says "I0-3 used by the DRC, rest can be assigned to fast
   registers", and the regmap assigns SHARC R0-R3 to I4-I7 when the backend has
   the registers. Upstream's DRC uses I4-I7 exactly zero times. It is latent
   only because DISABLE_FAST_REGISTERS is 1. The signed-average path is already
   wrong on any backend with direct_iregs > 4: it writes I4 and the next line
   re-reads REG(fxa), which IS I4. Moved to I8/I9, which this core never maps
   (it assigns at most I4-I7).

3. MN TAKEN FROM THE WRONG HALF FOR FRACTIONAL RESULTS.
   The new general fixed multiplier set MN from bit 31 of the 64-bit result. For
   the fractional forms the delivered value is MR1, bits 63:32. Upstream's own
   fractional multipliers (compute_mul_ssfr_add/_sub) pass the ALREADY-SHIFTED
   32-bit value to SET_FLAG_MN, so upstream's convention is the sign of the
   DELIVERED value -- and the commit's own SAT handler 43 lines above already
   writes `frac ? 63 : 31`. Both engines now follow it.

RUN   python3 sharc_drc_fixes.py       (from the PR worktree root)
PASS  prints "ok"; every replacement is asserted.
"""


def edit(path, pairs):
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        assert old in s, '%s MISSING: %r' % (path, old[:100])
        s = s.replace(old, new, 1)
    open(path, 'w').write(s)
    print('rewrote', path)


DRC = 'src/devices/cpu/sharc/sharcdrc.cpp'

# ---- 1. ALUSAT at runtime ---------------------------------------------------
edit(DRC, [
("""// MODE1 ALUSAT tail for fixed-point ALU results (TRM B-6): expects the WRAPPED result
// in I6 and the captured overflow flag (0/1) in I7; writes dst, then clamps it to
// 0x7FFFFFFF / 0x80000000 when saturation mode is on and the op overflowed. The KN7000
// effects kernel runs with ALUSAT set; every interpreter compute_* fixed ALU op
// saturates, so every native DRC emission must too (asymmetry here is what turned the
// effect LFO reflect logic into full-scale rail bounces).
void adsp21062_device::generate_fixed_alusat_tail(drcuml_block &block, compiler_state &compiler, const opcode_desc *desc, uml::parameter dst, bool fix_flags)
{
	UML_MOV(block, dst, I6);
	// TRANSLATION-TIME SPECIALIZATION: MODE1.ALUSAT changes exactly once in this firmware
	// (boot BIT SET). The mode1-write generators below flush the cache whenever the bit
	// could change, so compiled code may safely bake the current state in -- zero overhead
	// when saturation is off, and no per-op MODE1 load when it is on.
	if (!(m_core->mode1 & MODE1_ALUSAT))
		return;
	uml::code_label const no_sat = compiler.labelnum++;
	UML_TEST(block, I7, 1);
	UML_JMPc(block, uml::COND_Z, no_sat);
	UML_SAR(block, I6, I6, 31);
	UML_XOR(block, dst, I6, 0x80000000);                       // wrapped<0 -> 0x7FFFFFFF else 0x80000000
""",
 """// MODE1 ALUSAT tail for fixed-point ALU results (TRM B-6): expects the WRAPPED result
// in I8 and the captured overflow flag (0/1) in I9; writes dst, then clamps it to
// 0x7FFFFFFF / 0x80000000 when saturation mode is on and the op overflowed. Every
// interpreter compute_* fixed ALU op saturates, so every native DRC emission must too.
void adsp21062_device::generate_fixed_alusat_tail(drcuml_block &block, compiler_state &compiler, const opcode_desc *desc, uml::parameter dst, bool fix_flags)
{
	UML_MOV(block, dst, I8);
	// MODE1.ALUSAT is read at RUNTIME, like the interpreter does. Baking it in at
	// translation time would need every path that rewrites MODE1 to invalidate the
	// cache, and the status-stack pop does not -- nor could it usefully, since
	// cache_dirty is only examined once per timeslice.
	uml::code_label const no_sat = compiler.labelnum++;
	UML_TEST(block, MODE1, MODE1_ALUSAT);
	UML_JMPc(block, uml::COND_Z, no_sat);
	UML_TEST(block, I9, 1);
	UML_JMPc(block, uml::COND_Z, no_sat);
	UML_SAR(block, I8, I8, 31);
	UML_XOR(block, dst, I8, 0x80000000);                       // wrapped<0 -> 0x7FFFFFFF else 0x80000000
"""),
# the parallel-ALU bake site
("""					if (alu == 0) UML_ADD(block, I6, REG(fxa), REG(fya));
					else          UML_SUB(block, I6, REG(fxa), REG(fya));
					UML_MOV(block, I7, 0);
					UML_SETc(block, uml::COND_V, I7);      // overflow, for ALUSAT
					UML_MOV(block, REG(fa), I6);
					if (m_core->mode1 & MODE1_ALUSAT)      // baked at translation time (cache flushes on ALUSAT change)
					{
						uml::code_label const nsat = compiler.labelnum++;
						UML_TEST(block, I7, 1);
						UML_JMPc(block, uml::COND_Z, nsat);
						UML_SAR(block, I6, I6, 31);
						UML_XOR(block, REG(fa), I6, 0x80000000);   // wrapped<0 -> 0x7FFFFFFF else 0x80000000
						UML_LABEL(block, nsat);
					}
""",
 """					if (alu == 0) UML_ADD(block, I8, REG(fxa), REG(fya));
					else          UML_SUB(block, I8, REG(fxa), REG(fya));
					UML_MOV(block, I9, 0);
					UML_SETc(block, uml::COND_V, I9);      // overflow, for ALUSAT
					UML_MOV(block, REG(fa), I8);
					{
						uml::code_label const nsat = compiler.labelnum++;
						UML_TEST(block, MODE1, MODE1_ALUSAT);
						UML_JMPc(block, uml::COND_Z, nsat);
						UML_TEST(block, I9, 1);
						UML_JMPc(block, uml::COND_Z, nsat);
						UML_SAR(block, I8, I8, 31);
						UML_XOR(block, REG(fa), I8, 0x80000000);   // wrapped<0 -> 0x7FFFFFFF else 0x80000000
						UML_LABEL(block, nsat);
					}
"""),
# Rn = ABS Rx
("""						// Mirrors interpreter compute_abs exactly: overflow only for
						// Rx == 0x80000000 (AV + sticky AOS, clamped to 0x7FFFFFFF when ALUSAT
						// -- baked at translation time like generate_fixed_alusat_tail, the
						// cache is flushed on ALUSAT changes); AS = sign of the INPUT, AZ/AN
						// from the (possibly saturated) result, AC/AI/AF cleared.
""",
 """						// Mirrors interpreter compute_abs exactly: overflow only for
						// Rx == 0x80000000 (AV + sticky AOS, clamped to 0x7FFFFFFF in ALUSAT
						// mode); AS = sign of the INPUT, AZ/AN from the (possibly saturated)
						// result, AC/AI/AF cleared.
"""),
("""						if (m_core->mode1 & MODE1_ALUSAT)
							UML_MOV(block, I0, 0x7fffffff);
						UML_JMP(block, done);
""",
 """						UML_TEST(block, MODE1, MODE1_ALUSAT);
						UML_MOVc(block, uml::COND_NZ, I0, 0x7fffffff);
						UML_JMP(block, done);
"""),
])

# the three cache_dirty stores existed only to cover the bake
s = open(DRC, encoding='utf-8').read()
STORE = """	// ALUSAT is baked into compiled fixed-ALU code (generate_fixed_alusat_tail): if this
	// write could change the bit relative to the compiled assumption, flush the cache so
	// the next timeslice recompiles with the new mode. MODE1 writes are rare (boot-time).
	if ((data & MODE1_ALUSAT) || (m_core->mode1 & MODE1_ALUSAT))
		UML_MOV(block, mem(&m_core->cache_dirty), 1);
"""
n = s.count(STORE)
assert n == 3, 'expected the three MODE1 immediate generators, found %d' % n
open(DRC, 'w').write(s.replace(STORE, ''))
print('dropped %d translation-time ALUSAT cache flushes' % n)

# ---- 2. scratch registers this core can never map ---------------------------
import re
s = open(DRC, encoding='utf-8').read()
before = len(re.findall(r'\bI[4-7]\b', s))
s = re.sub(r'\bI4\b', 'I8', s)
s = re.sub(r'\bI6\b', 'I8', s)
s = re.sub(r'\bI7\b', 'I9', s)
after = len(re.findall(r'\bI[4-7]\b', s))
assert before and after == 0, 'expected every I4-I7 use to move (%d -> %d)' % (before, after)
open(DRC, 'w').write(s)
print('moved %d I4/I6/I7 scratch uses to I8/I9' % before)

# ---- 3. MN from the delivered half ------------------------------------------
edit('src/devices/cpu/sharc/sharcops.hxx', [
("""						CLEAR_MULTIPLIER_FLAGS();
						SET_FLAG_MN(uint32_t(result));
						SET_FLAG_MV(result);
						SET_FLAG_MU(result);
""",
 """						CLEAR_MULTIPLIER_FLAGS();
						// MN is the sign of the DELIVERED value: the fractional forms hand
						// over MR1, bits 63:32. Upstream's own fractional multipliers pass
						// the already-shifted word to SET_FLAG_MN for the same reason.
						SET_FLAG_MN(uint32_t(frac ? (uint64_t(result) >> 32) : uint64_t(result)));
						SET_FLAG_MV(result);
						SET_FLAG_MU(result);
"""),
])

edit(DRC, [
("""					if (MN_CALC_REQUIRED) { UML_TEST(block, I2, 0x80000000U); UML_SETc(block, uml::COND_NZ, ASTAT_MN); }
""",
 """					// MN is the sign of the delivered half -- bits 63:32 for fractional.
					if (MN_CALC_REQUIRED)
					{
						UML_DTEST(block, I2, 1ULL << (frac ? 63 : 31));
						UML_SETc(block, uml::COND_NZ, ASTAT_MN);
					}
"""),
])
print('ok')
