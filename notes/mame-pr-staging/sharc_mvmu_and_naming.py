"""Emit MV/MU in the new fixed-point multiplier, and name the internal-RAM base.

QUESTION (a) ANSWERS
  "Does the new single-function multiplier/MAC emitter disagree with the
   interpreter about MV and MU?"

  Yes. The interpreter's general fixed multiplier computes both; the emitter
  wrote literal zero into each. The sequences below mirror SET_FLAG_MV and
  SET_FLAG_MU bit for bit, including their 64-bit-MR approximation -- the MU
  block is character-for-character the one already at sharcdrc.cpp:5462.

  The old comment justified the zeros with a bit-identical reverb A/B. That is
  weak evidence for a flag nobody reads, by this project's own rule that a
  difference from silence is not a signal, and the same comment's "dead flags
  cost nothing" is false: drcfe seeds the liveness mask with everything set at a
  sequence end, so the last definer in each sequence always pays.

  ⚠ NOT the reason to do it: for the KN7000 these flags are unobservable -- 0 MV
  conditions and 0 multiplier-flag ASTAT reads in 6499 instruction words across
  the whole download pool, against a positive control that finds IF MS x20,
  IF AV x7, IF GE x40. The reason is that ops 0x70/0xb0/0xb2 were ALREADY LIVE
  upstream with the DRC emitting no multiplier flags at all while the interpreter
  computed them, so this makes the two engines agree for the first time. Whether
  a merged driver executes those ops is NOT measured, and the commit message must
  not claim it does.

QUESTION (b) ANSWERS
  "sharcfe.cpp decides which page holds internal PROGRAM memory by consulting an
   accessor named for the interrupt vector table. Rename it?"

  Add rather than rename: irq_vector_base() has two genuine interrupt-vector
  users. internal_ram_base() is the thing the frontend actually wants, and on
  every 2106x variant the vector table sits at the base of internal memory, so
  one is expressed in terms of the other.

RUN   python3 sharc_mvmu_and_naming.py     (from the PR worktree root)
PASS  prints "ok".
"""


def edit(path, pairs):
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        if old in s:
            s = s.replace(old, new, 1)
        elif not new or new in s:
            continue
        else:
            raise AssertionError('%s MISSING: %r' % (path, old[:110]))
    open(path, 'w').write(s)
    print('rewrote', path)


edit('src/devices/cpu/sharc/sharcdrc.cpp', [
("""					// Multiplier flags: interpreter clears MN/MV/MU/MI then sets MN from the result;
					// MV/MU stay clear here (bit-identical reverb A/B confirms the kernel doesn't read
					// them on this path). Gated on liveness so dead flags cost nothing.
					if (MI_CALC_REQUIRED) UML_MOV(block, ASTAT_MI, 0);
					if (MV_CALC_REQUIRED) UML_MOV(block, ASTAT_MV, 0);
					if (MU_CALC_REQUIRED) UML_MOV(block, ASTAT_MU, 0);
""",
 """					// Multiplier flags, mirroring the interpreter's SET_FLAG_* bit for bit --
					// including their 64-bit-MR approximation, since MAME models MR without the
					// MR2 stage. Liveness-gated, so only the last definer in a sequence pays.
					if (MI_CALC_REQUIRED) UML_MOV(block, ASTAT_MI, 0);
					// MV = the high half is neither 0 nor all-ones, i.e. uint32_t(high + 1) > 1.
					if (MV_CALC_REQUIRED)
					{
						UML_DSHR(block, I0, I2, 32);
						UML_ADD(block, I0, I0, 1);
						UML_CMP(block, I0, 1);
						UML_SETc(block, uml::COND_A, ASTAT_MV);
					}
					// MU = high half zero and low half non-zero.
					if (MU_CALC_REQUIRED)
					{
						UML_DTEST(block, I2, 0xffffffff00000000ULL);
						UML_SETc(block, uml::COND_Z, I0);
						UML_TEST(block, I2, 0xffffffff);
						UML_SETc(block, uml::COND_NZ, I1);
						UML_AND(block, ASTAT_MU, I0, I1);
					}
"""),
])

edit('src/devices/cpu/sharc/sharc.h', [
("""	virtual uint32_t irq_vector_base() const { return 0x20000; }""",
 """	// Base of internal memory. The interrupt vector table sits here on every
	// variant, and it is also the 128 KiB page the DRC frontend's loop map covers.
	virtual uint32_t internal_ram_base() const { return 0x20000; }
	uint32_t irq_vector_base() const { return internal_ram_base(); }"""),
("""	virtual uint32_t irq_vector_base() const override { return 0x8000; }""",
 """	virtual uint32_t internal_ram_base() const override { return 0x8000; }"""),
])
print('ok')


# The frontend repeated the same expression and the same trailing comment four
# times. Cache the page once, with the comment on the member.
import re
# HARVEST_GUARD: replay_polish.py executes this with I/O stubbed to return '',
# so bail out before the raw-file section rather than assert on an empty read.
if __name__ != '__main__':
    raise SystemExit(0)
p = 'src/devices/cpu/sharc/sharcfe.h'
s = open(p, encoding='utf-8').read()
old = '\tadsp21062_device *m_sharc;'
new = ('\tadsp21062_device *m_sharc;\n'
       '\t// Which 128 KiB page holds internal program memory: 0x20000 on the 2M/4M\n'
       '\t// parts, 0x8000 on the 21065L. The loop map is indexed by pc & 0x1ffff.\n'
       '\tuint32_t const m_pm_page;')
assert old in s or 'm_pm_page' in s
if 'm_pm_page' not in s:
    s = s.replace(old, new, 1)
    open(p, 'w').write(s)
print('rewrote', p)

p = 'src/devices/cpu/sharc/sharcfe.cpp'
s = open(p, encoding='utf-8').read()
n = s.count('if (l2 != (m_sharc->irq_vector_base() >> 17))   // internal-memory window (0x20000 on 2106x, 0x8000 on 21065L)')
assert n in (0, 4), 'expected 4 sites, found %d' % n
s = s.replace('if (l2 != (m_sharc->irq_vector_base() >> 17))   // internal-memory window (0x20000 on 2106x, 0x8000 on 21065L)',
              'if (l2 != m_pm_page)')
open(p, 'w').write(s)
print('rewrote %s (%d sites folded)' % (p, n))
