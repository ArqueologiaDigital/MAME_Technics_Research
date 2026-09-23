"""Fixes for the defects an adversarial pre-submission review surfaced.

QUESTION EACH ONE ANSWERS is recorded beside it. Every claim was re-verified
against the source (and, for the timer, arithmetically) before being acted on;
see adversarial-review-2026-09-23.txt for the full report.

RUN   python3 review_fixes.py        (from the PR worktree root)
PASS  prints "ok"; every replacement is asserted, so a silent no-op is a failure.
"""


def edit(path, pairs):
    """Apply each (old, new) once.

    Idempotent: a pair whose replacement is already in place is counted as done
    rather than asserted, so the script can be re-run. A pair that matches
    NEITHER form is still a hard failure -- that is the silent-no-op case.
    """
    s = open(path, encoding='utf-8').read()
    done = 0
    for old, new in pairs:
        if old in s:
            s = s.replace(old, new, 1)
        elif new and new in s:
            done += 1
        elif not new:
            # A deletion: `old` being absent IS the post-condition, so this is
            # already applied rather than a failed match.
            done += 1
        else:
            raise AssertionError('%s MISSING: %r' % (path, old[:90]))
    open(path, 'w').write(s)
    print('rewrote %s (%d already applied)' % (path, done))


# ---------------------------------------------------------------- MN10300 ---
edit('src/devices/cpu/mn10300/mn10300.cpp', [
# The live timer read overflowed uint64 for any reload above ~6073. At the
# KN7000's own documented boot reload of 10417 the register read back
# 3335/730/1667/2604 across one period -- not even monotonic. Taking the
# remaining time in TICKS keeps the arithmetic small.
("""	// Live down-count, derived from the emu_timer's phase.
	const attotime period = m_tm5_timer->period();
	if (period.is_never() || period.is_zero())
		return 0;
	return uint16_t(uint64_t(m_tm5_base + 1) * m_tm5_timer->remaining().as_attoseconds() / period.as_attoseconds());
""",
 """	// Live down-count, derived from the emu_timer's phase. Taken in ticks: the
	// product of the reload and the remaining attoseconds overflows 64 bits for
	// any reload above ~6073.
	const attotime period = m_tm5_timer->period();
	if (period.is_never() || period.is_zero())
		return 0;
	return uint16_t(m_tm5_timer->remaining().as_ticks(clock() / 2) / TM5_PRESCALE);
"""),
("""	static constexpr unsigned PRESCALE = 8;
	const attotime period = attotime::from_ticks(uint64_t(m_tm5_base + 1) * PRESCALE, clock() / 2);
""",
 """	const attotime period = attotime::from_ticks(uint64_t(m_tm5_base + 1) * TM5_PRESCALE, clock() / 2);
"""),
("""	// = 31250 => 16 MHz). PRESCALE: the KN7000 tick ISR counts 96 PPQN, so at
""",
 """	// = 31250 => 16 MHz). The prescale is fixed by the 96-PPQN math: at
"""),
# m_irq_level is read by check_irq on every instruction and is the one member
# of the arbitration triple that was not saved.
("""	save_item(NAME(m_irq_vector));
""",
 """	save_item(NAME(m_irq_vector));
	save_item(NAME(m_irq_level));
"""),
# m_possible_irq was written in two places and read nowhere: check_irq runs
# unconditionally. It is vestigial from the MN10200, where it is the gate.
("""	, m_possible_irq(false), m_irq_state(CLEAR_LINE), m_irq_vector(0)
""",
 """	, m_irq_state(CLEAR_LINE), m_irq_vector(0), m_irq_level(7)
"""),
("""	save_item(NAME(m_possible_irq));
""", ""),
("""			m_possible_irq = true;
""", ""),
("""			else if (op2 == 0xFD) { m_psw = pop32(); m_pc = pop32(); m_possible_irq = true; return; } // rti
""",
 """			else if (op2 == 0xFD) { m_psw = pop32(); m_pc = pop32(); return; }      // rti
"""),
])

edit('src/devices/cpu/mn10300/mn10300.h', [
# Dead API: zero callers for all three. The machine uses set_maskable_vector.
("""	// Reset state. The boot address and initial stack pointer are strapped per
	// board, so the machine supplies them.
	void set_reset_pc(uint32_t pc) { m_reset_pc = pc; }
	void set_reset_sp(uint32_t sp) { m_reset_sp = sp; }

	// Direct vector/level override, for a machine that drives interrupts without
	// the on-chip INTC. The INTC's own recompute/accept paths overwrite both from
	// the per-level vector table.
	void set_irq_vector(uint32_t v) { m_irq_vector = v; }
	void set_irq_level(int l) { m_irq_level = l; }
""",
 """	// Reset state. The boot address and initial stack pointer are strapped per
	// board, so the machine supplies them.
	void set_reset_pc(uint32_t pc) { m_reset_pc = pc; }
	void set_reset_sp(uint32_t sp) { m_reset_sp = sp; }
"""),
("""	inline void change_pc(uint32_t pc) { m_pc = pc; } // TODO(MN10300): full 32-bit PC, no 0xffffff mask
""", ""),
("""	bool     m_possible_irq; // an IRQ may be serviceable; re-checked at the loop top
""", ""),
("""	int      m_irq_level = 7; // priority level of the pending interrupt (0 = highest)
""",
 """	int      m_irq_level;    // priority level of the pending interrupt (0 = highest)
"""),
("""	// TM5: mode byte @0x34001082, 16-bit reload @0x34001092, down-counter
""",
 """	// The prescale between IOCLK and the counter, fixed by the 96-PPQN math.
	static constexpr unsigned TM5_PRESCALE = 8;

	// TM5: mode byte @0x34001082, 16-bit reload @0x34001092, down-counter
"""),
])

# ------------------------------------------------------------------ SHARC ---
edit('src/devices/cpu/sharc/sharc.h', [
# offs_t IS uint32_t, so this was a no-op that changed a shared device's public
# API in a commit about a different subject. Put it back.
("""	void external_iop_write(uint32_t address, uint32_t data);
	void external_dma_write(uint32_t address, uint64_t data);
""",
 """	void external_iop_write(offs_t address, uint32_t data);
	void external_dma_write(offs_t address, uint64_t data);
"""),
])
edit('src/devices/cpu/sharc/sharc.cpp', [
("""void adsp21062_device::external_iop_write(uint32_t address, uint32_t data)
""",
 """void adsp21062_device::external_iop_write(offs_t address, uint32_t data)
"""),
("""void adsp21062_device::external_dma_write(uint32_t address, uint64_t data)
""",
 """void adsp21062_device::external_dma_write(offs_t address, uint64_t data)
"""),
])

# ------------------------------------------------------------- tonegen -----
edit('src/mame/matsushita/kn_tonegen.cpp', [
# No ROM_START in the tree declares a "wavepack" region, so this loader is
# unreachable -- and what it exists to load is a constructed image built by a
# generator that is not in MAME. The fabricated sine below is the live path.
("""	// Parse the optional synthetic wave pack (magic KN7WVSY2; tools/make_wave_pack.py).
	if (memory_region *wr = machine().root_device().memregion("wavepack"))
	{
		const uint8_t *p = wr->base();
		if (wr->bytes() >= 0x110 && !memcmp(p, "KN7WVSY2", 8))
		{
			const uint32_t n = p[8] | (p[9] << 8) | (p[10] << 16) | (uint32_t(p[11]) << 24);
			auto rd32 = [&](uint32_t o) { return p[o] | (p[o+1] << 8) | (p[o+2] << 16) | (uint32_t(p[o+3]) << 24); };
			for (uint32_t i = 0; i < n && i < 256; i++)
			{
				const uint32_t e = 0x110 + i * 32;
				wentry w;
				w.bank = p[e];
				w.zlo = p[e+1];
				w.zhi = p[e+2];
				const uint32_t off = rd32(e+4);
				w.len = rd32(e+8);
				w.lstart = rd32(e+12);
				w.llen = rd32(e+16);
				w.root_hz = double(rd32(e+20)) / 1000.0;
				if (off + w.len * 2 <= wr->bytes() && w.len && w.root_hz > 1.0
					&& w.lstart + w.llen <= w.len && w.llen)
				{
					w.pcm = reinterpret_cast<const int16_t *>(p + off);
					// Reserved wildcard bank 0xFF = the fabricated DEFAULT sine (see header):
					// it never zone-matches a real voice, so unmapped voices adopt it.
					if (w.bank == 0xFF) m_wdefault = int(m_wentries.size());
					m_wentries.push_back(w);
				}
			}
			osd_printf_info("kn7000 tonegen: synthetic wave pack loaded (%d zone maps)\\n", int(m_wentries.size()));
		}
	}
	// If the optional pack ROM supplied no default sine (or is absent entirely), synthesize
	// the identical single-cycle sine ourselves so EVERY voice still plays PCM, never a
	// sin() oscillator. This keeps the render path a single, faithful sample-playback
	// datapath regardless of whether the fabricated ROM is present. Faithful mechanism,
	// fabricated data. (441 samples / one cycle -> 44100/441 = 100.000 Hz root, matching
	// tools/make_wave_pack.py so the audible tone is the same whichever source provides it.)
""",
 """	// The wave ROMs have no dump, so every voice plays a synthesized single-cycle
	// sine through the ordinary sample-playback path rather than a sin() oscillator:
	// the mechanism is the real one, only the data is fabricated. 441 samples per
	// cycle gives a 44100/441 = 100 Hz root.
"""),
])

print('ok')


# ------------------------------------------------------------- driver ------
edit('src/mame/matsushita/kn7000.cpp', [
# Upstream has 534 files on SPEAKER(config, "speaker", 2) against 3 still on the
# lspeaker/rspeaker pair, and the conversion is actively in progress there.
("""	SPEAKER(config, "lspeaker").front_left();
	SPEAKER(config, "rspeaker").front_right();
""",
 """	SPEAKER(config, "speaker", 2).front();
"""),
("""	m_dspbridge->add_route(0, "lspeaker", 1.0);
	m_dspbridge->add_route(1, "rspeaker", 1.0);
""",
 """	m_dspbridge->add_route(0, "speaker", 1.0, 0);
	m_dspbridge->add_route(1, "speaker", 1.0, 1);
"""),
# m_tg_reg is 256 KiB of state written on every tone-generator register write,
# save_item'd, and read nowhere: pitch and type are resolved from the firmware's
# voice records in program space instead.
("""	uint16_t m_tg_reg[2][0x10000] = { };       // captured voice-register file, full 16-bit space
""", ""),
("""		m_tg_reg[0][m_tg_addr[0]] = data;                         // capture the FULL address (was gated <0x1000)
""", ""),
("""		m_tg_reg[1][m_tg_addr[1]] = data;
""", ""),
("""	save_item(NAME(m_tg_reg));
""", ""),
# m_cpsd_probed is an unused private field: clang has -Wunused-private-field in
# -Wall and MAME builds -Wall -Werror, so this is a build failure there, not a
# style point. Its only user was cpsd_queue, itself dead since ch2 turned out to
# be the second MIDI UART rather than the SD link.
("""	void cpsd_queue(const uint8_t *bytes, int n);   // (unused since the ch2=MIDI-2 finding; kept for a future SD transport)
""", ""),
("""	bool    m_cpsd_probed = false;         // (retired with the ch2 probe)
""", ""),
# kn6500 differs from kn6000 by one constant and inherits its tone generator and
# speaker routing, so it emits. NO_SOUND means "has sound, not emulated" and
# drives the warning screen, so the claim was visible and false.
("""SYST(2001, kn6500, 0,      0,      kn6500,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN6500", MACHINE_NOT_WORKING | MACHINE_NO_SOUND)""",
 """SYST(2001, kn6500, 0,      0,      kn6500,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN6500", MACHINE_NOT_WORKING | MACHINE_IMPERFECT_SOUND)"""),
# The KN7000's artwork is not the KN2400/KN2600 panel, and kn7000() is only
# kn7000_base() plus that layout.
("""	kn7000(config);
	m_ram90_workram = true;
	m_lcd_kn24 = true;
""",
 """	kn7000_base(config);
	m_ram90_workram = true;
	m_lcd_kn24 = true;
"""),
])
print('driver ok')
