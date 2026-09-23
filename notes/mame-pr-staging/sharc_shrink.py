"""Take out of the SHARC change everything that is not the work.

QUESTION IT ANSWERS
  "Of the 931 lines this commit adds to a shared CPU core, how many actually
   have to be there?"

Four groups come out:

1. BEHAVIOUR-NEUTRAL CHURN in sharcops.hxx. Eight `UIREG(x)` uses were
   hand-expanded to `(uint32_t)REG(x)` -- the macro's own expansion, and the
   macro is kept anyway. And `std::rotl(x, shift)` was split into rotr/rotl on
   the sign of the shift: std::rotl is DEFINED for a negative shift (it rotates
   the other way), so the split is behaviour-identical, and `-shift` is UB for
   INT_MIN, which std::rotl never is. Reverted: seven of the eleven hunks in the
   one file where the substantive work lives were noise hiding the rest.

2. DEAD API on the shared device. dm_index_reg(), sport_tx_buffer(),
   sport_rx_buffer(), m_sport_tx/m_sport_rx and the DMA transfer-control-block
   decode that exists only to fill them: zero callers tree-wide. dm_index_reg()
   in particular lands on adsp21062_device, which eight existing drivers use,
   duplicates state_add(SHARC_I0 + i, ...) that upstream already provides, and
   is documented entirely in terms of what one effects kernel keeps in I4.

3. AN UNEXPLAINED REWRITE OF A SHARED ASSERT. `std::has_single_bit(len)` became
   `!(len & (len - 1))`. Those differ at exactly one input, 0 -- which is what
   the 21065L produces, since it declares no blocks. The bit trick existed only
   to get the new device through the base device_start. The assert is restored
   and the exemption is stated instead of hidden.

4. A BOARD'S MEMORY INSIDE A CPU DEVICE. data_65l() mapped 0x20000-0xFFFFF as
   RAM, commented "External SRAM (IC307/IC308)". On the 21065L 0x20000 is where
   EXTERNAL memory begins, and a device's internal map is constructed last, so no
   driver could ever override it. The internal map now covers only the part's
   documented internal window, 0x08000-0x0FFFF, and the board's SRAM moves to the
   driver.

RUN   python3 sharc_shrink.py       (from the PR worktree root)
PASS  prints "ok"; every replacement is asserted.
"""


def edit(path, pairs):
    """Idempotent: a pair already applied is counted done, not asserted."""
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        if old in s:
            s = s.replace(old, new, 1)
        elif not new or new in s:
            continue
        else:
            raise AssertionError('%s MISSING: %r' % (path, old[:100]))
    open(path, 'w').write(s)
    print('rewrote', path)


# ---- 1. revert the churn ----------------------------------------------------
OPS = 'src/devices/cpu/sharc/sharcops.hxx'
s = open(OPS, encoding='utf-8').read()
n = s.count('(uint32_t)REG(rx)')
assert n in (0, 8), 'expected 8 hand-expansions (or 0, already reverted), found %d' % n
s = s.replace('(uint32_t)REG(rx)', 'UIREG(rx)')
s = s.replace('#define UIREG(x)    uint32_t(m_core->r[x].r)   // unsigned view, for std::rotl/std::rotr',
              '#define UIREG(x)    uint32_t(m_core->r[x].r)')
open(OPS, 'w').write(s)
print('reverted %d UIREG hand-expansions' % n)

edit(OPS, [
# std::rotl already rotates the other way for a negative shift.
("""						int const shift = REG(ry);
						if (shift < 0)
						{
							REG(rn) = std::rotr(UIREG(rx), -shift);
						}
						else
						{
							REG(rn) = std::rotl(UIREG(rx), shift);
							if (shift > 0)
							{
								m_core->astat |= SV;
							}
						}
""",
 """						int const shift = REG(ry);
						REG(rn) = std::rotl(UIREG(rx), shift);
						if (shift > 0)
						{
							m_core->astat |= SV;
						}
"""),
])

# ---- 3. restore the shared assert -------------------------------------------
edit('src/devices/cpu/sharc/sharc.cpp', [
("""	assert(m_blocks[0].length() == m_blocks[1].length());
	assert(!(m_blocks[0].length() & (m_blocks[0].length() - 1)));
""",
 """	// The 21065L declares no memory blocks, so it reaches here with length 0.
	assert(!m_blocks[0] || (m_blocks[0].length() == m_blocks[1].length()
			&& std::has_single_bit(m_blocks[0].length())));
"""),
])

# ---- 4. the board's SRAM is the board's --------------------------------------
edit('src/devices/cpu/sharc/sharc.cpp', [
("""// Internal data memory + IOP registers. Records target DM 0x9800/0x9C40/0xC000/0xC302; cover
// them with plain RAM. IOP 0x00-0x00FF is stubbed (see iop65l_r/w). External SDRAM delay
// memory (0x80000+) is not modelled yet.
void adsp21065l_device::data_65l(address_map &map)
{
	map(0x00000, 0x000ff).rw(FUNC(adsp21065l_device::iop65l_r), FUNC(adsp21065l_device::iop65l_w));
	map(0x08000, 0x08fff).ram();                       // DM view of the code region (unused as data)
	// Data region (0x9000-0x1FFFF): shared with pgm_65l so a DM write is readable via the PM bus.
	map(0x09000, 0x1ffff).rw(FUNC(adsp21065l_device::dm_data_r), FUNC(adsp21065l_device::dm_data_w));
	// External SRAM (IC307/IC308, 2M): the effect kernel's boot-init clears delay-line buffers
	// here (e.g. B6 = 0x20000, ~0x456F0 words) and the reverb/echo effects use them. The 21065L
	// Technical Reference puts external memory at 0x20000+. Map generously.
	map(0x20000, 0xfffff).ram();
}
""",
 """// Internal data memory + IOP registers. IOP 0x00-0x00FF is stubbed (see iop65l_r/w).
// Anything from 0x20000 up is EXTERNAL memory and belongs to the board.
void adsp21065l_device::data_65l(address_map &map)
{
	map(0x00000, 0x000ff).rw(FUNC(adsp21065l_device::iop65l_r), FUNC(adsp21065l_device::iop65l_w));
	map(0x08000, 0x08fff).ram();                       // DM view of the code region (unused as data)
	// Data region: shared with pgm_65l so a DM write is readable via the PM bus.
	map(0x09000, 0x0ffff).rw(FUNC(adsp21065l_device::dm_data_r), FUNC(adsp21065l_device::dm_data_w));
}
"""),
("""	// Data region (0x9000-0x1FFFF): filter coefficients/state, PM-bus view of the SRAM that is
	// ALSO the DM-bus view -- shared with data_65l so PM(0x9800) == DM(0x9800). External memory
	// begins at 0x20000 (per the 21065L Technical Reference).
	map(0x09000, 0x1ffff).rw(FUNC(adsp21065l_device::pm_data_r), FUNC(adsp21065l_device::pm_data_w));
""",
 """	// Data region: filter coefficients and state. This is the PM-bus view of the same
	// SRAM data_65l presents on the DM bus, so PM(0x9800) == DM(0x9800).
	map(0x09000, 0x0ffff).rw(FUNC(adsp21065l_device::pm_data_r), FUNC(adsp21065l_device::pm_data_w));
"""),
])

edit('src/devices/cpu/sharc/sharc.h', [
("""	static constexpr offs_t DATA_SRAM_WORDS = 0x1ffff - 0x09000 + 1;   // 0x17000
""",
 """	// The part's internal memory window is 0x08000-0x0FFFF; 0x20000 up is external.
	static constexpr offs_t DATA_SRAM_WORDS = 0x0ffff - 0x09000 + 1;
"""),
])

# ---- 2. delete the dead API --------------------------------------------------
edit('src/devices/cpu/sharc/sharc.h', [
("""	uint32_t dm_index_reg(int n) const;
""", ""),
("""	// Base addresses of the running program's serial-audio DMA autobuffers, derived
	// at runtime from its DMA transfer-control blocks (see iop65l_w). [sport 0/1][A=0 / B=1].
	// TX = the SHARC's processed output (-> DAC); RX = its input (TG -> SHARC). 0 until set up.
	uint32_t sport_tx_buffer(int sport, int ab) const { return m_sport_tx[sport & 1][ab & 1]; }
	uint32_t sport_rx_buffer(int sport, int ab) const { return m_sport_rx[sport & 1][ab & 1]; }

""", ""),
("""	// SPORT audio DMA autobuffer bases (see sport_tx_buffer/sport_rx_buffer).
	uint32_t m_sport_tx[2][2] = { };
	uint32_t m_sport_rx[2][2] = { };

""", ""),
])

edit('src/devices/cpu/sharc/sharc.cpp', [
("""	save_item(NAME(m_sport_tx));
	save_item(NAME(m_sport_rx));
""", ""),
("""uint32_t adsp21062_device::dm_index_reg(int n) const
{
	return m_core->dag1.i[n & 7];
}

""", ""),
])
print('ok')


# ---- 2b. the DMA transfer-control-block decode that only fed the dead API ----
edit('src/devices/cpu/sharc/sharc.cpp', [
("""	// A program sets the SPORT-DMA chain-pointer (CP) registers; the
	// transfer-control block lives at internal address 0x8000 + (CP & 0x1FFFF), whose II
	// (internal index) field is the audio buffer base. Derive and cache those bases so the audio
	// in/out addresses are taken from the firmware's own descriptors, not assumed. Register map
	// (runtime-confirmed): 0x73/0x53 = SPORT0 TX A/B, 0x7B/0x5B = SPORT1 TX A/B, 0x63/0x33 =
	// SPORT0 RX A/B, 0x6B/0x3B = SPORT1 RX A/B.
	auto tcb_ii = [&](uint32_t cp) -> uint32_t {
		const offs_t tcb = 0x8000 + (cp & 0x1ffff);          // the II word of the TCB
		const offs_t i = tcb - DATA_SRAM_BASE;
		return (m_data_sram && i < DATA_SRAM_WORDS) ? m_data_sram[i] : 0;
	};
	switch (offset)
	{
	case 0x73: m_sport_tx[0][0] = tcb_ii(data); break;
	case 0x53: m_sport_tx[0][1] = tcb_ii(data); break;
	case 0x7b: m_sport_tx[1][0] = tcb_ii(data); break;
	case 0x5b: m_sport_tx[1][1] = tcb_ii(data); break;
	case 0x63: m_sport_rx[0][0] = tcb_ii(data); break;
	case 0x33: m_sport_rx[0][1] = tcb_ii(data); break;
	case 0x6b: m_sport_rx[1][0] = tcb_ii(data); break;
	case 0x3b: m_sport_rx[1][1] = tcb_ii(data); break;
	default: break;
	}
""", ""),
])
print('ok (dma tcb decode)')
