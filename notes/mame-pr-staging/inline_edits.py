"""The kn7000.cpp edits made directly at the prompt, captured so the commit
split can replay them. Same (old, new) form as the other polish scripts."""


def shift(text, n):
    out = []
    for line in text.split('\n'):
        if n < 0:
            out.append(line[min(-n, len(line) - len(line.lstrip('\t'))):])
        else:
            out.append(('\t' * n + line) if line.strip() else line)
    return '\n'.join(out)


def edit(path, pairs):
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        for d in (0, -1, 1, -2, 2):
            cand = shift(old, d)
            if cand in s:
                s = s.replace(cand, shift(new, d), 1)
                break
        else:
            raise AssertionError('%s MISSING: %r' % (path, old[:80]))
    open(path, 'w').write(s)
    print('rewrote', path)


edit('src/mame/matsushita/kn7000.cpp', [
# one save_item per line
("""		save_item(NAME(m_rx));   save_item(NAME(m_rxraw));   save_item(NAME(m_tx));
		save_item(NAME(m_rx_rd)); save_item(NAME(m_rx_wr));
		save_item(NAME(m_tx_rd)); save_item(NAME(m_tx_wr));
		save_item(NAME(m_dsp_active)); save_item(NAME(m_tx_primed)); save_item(NAME(m_tx_last));
""",
 """		save_item(NAME(m_rx));
		save_item(NAME(m_rxraw));
		save_item(NAME(m_tx));
		save_item(NAME(m_rx_rd));
		save_item(NAME(m_rx_wr));
		save_item(NAME(m_tx_rd));
		save_item(NAME(m_tx_wr));
		save_item(NAME(m_dsp_active));
		save_item(NAME(m_tx_primed));
		save_item(NAME(m_tx_last));
"""),
# the frame-tick comment had lost its indentation
("""	// Audio frame tick: pulse the effects DSP's IRQ0 (the kernel's frame interrupt). We only
// ASSERT: the SHARC core clears the pending bit when it *takes* the interrupt, so one edge
// is delivered per tick without a matching CLEAR. IRQ0 is edge-configured by the kernel
// (MODE2 0x18011) and its ISR (PM 0x8020) sets R13=1 to hand a frame to the main loop.
""",
 """	// Audio frame tick: pulse the effects DSP's IRQ0, the kernel's frame interrupt. Only the
	// assert is needed -- the SHARC clears the pending bit when it takes the interrupt, so one
	// edge is delivered per tick. The kernel configures IRQ0 edge-triggered (MODE2 0x18011) and
	// its handler at PM 0x8020 sets R13=1 to hand a frame to the main loop.
"""),
# likewise the tone-generator register-file block
("""	// Tone generators (main 0x98040000 / sub 0x98050000): register-indirect,
// write-only from the firmware. Address latched at base+0, data written at
// base+2 -> reg[address]. Voice registers are group<<8|bank<<6|channel
// (< 0x1000); the 0xFC0x system-refresh group is accepted but not stored.
""",
 """	// Tone generators (main 0x98040000 / sub 0x98050000): register-indirect,
	// write-only from the firmware. Address latched at base+0, data written at
	// base+2 -> reg[address]. Voice registers are group<<8|bank<<6|channel
	// (< 0x1000); the 0xFC0x system-refresh group is accepted but not stored.
"""),
("""	uint16_t m_tg_reg[2][0x10000] = { };       // captured voice-register file (FULL 16-bit address
	                                           // space -- the old [0x1000] + <0x1000 gate silently
	                                           // dropped the per-voice pitch/key-on writes at 0x2000+)
""",
 """	uint16_t m_tg_reg[2][0x10000] = { };       // captured voice-register file, full 16-bit space
"""),
# the board-supplied reset state, and the machine-config comments around it
("""// SD transport state, polled for the PLAY/PAUSE lamp: 1 playing, 2 paused, 0 stopped.
""",
 """// Initial stack pointer: the firmware image is linked against it and its startup
// code runs before establishing one.
constexpr offs_t RESET_SP              = 0x50021CF8;

// SD transport state, polled for the PLAY/PAUSE lamp: 1 playing, 2 paused, 0 stopped.
"""),
("""	// Panasonic MN103002A (MN10300/AM33 core), IC4 on MAIN 1/5.
	// Clock tree (SX-KN7000 service manual, SCHEMATIC DIAGRAM-1): a 16.0 MHz
	MN10300(config, m_maincpu, 16_MHz_XTAL * 2);
	m_maincpu->set_addrmap(AS_PROGRAM, &kn7000_state::maincpu_mem);

	// On-chip INTC (now modeled in the core): configure the per-level maskable
	// vectors -- the firmware installs two distinct handlers in its self-loaded
	for (int level = 0; level < 8; level++)
		m_maincpu->set_maskable_vector(level,
				level == 6 ? fw::KN7000_IRQ_SCHEDULER : fw::KN7000_IRQ_DISPATCH);
	// Board policy hooks out of the core INTC (see the "board-policy hooks"
	m_maincpu->intc_ack_cb().set([this](uint8_t group) {
""",
 """	// Panasonic MN103002A (MN10300/AM33 core), IC4 on MAIN 1/5. A 16.0 MHz
	// crystal feeds the on-chip PLL, which doubles it (service manual,
	// SCHEMATIC DIAGRAM-1).
	MN10300(config, m_maincpu, 16_MHz_XTAL * 2);
	m_maincpu->set_addrmap(AS_PROGRAM, &kn7000_state::maincpu_mem);
	m_maincpu->set_reset_pc(0x48400000);   // program flash base
	m_maincpu->set_reset_sp(fw::RESET_SP);

	// Per-level maskable vectors: the firmware installs a quick dispatcher for
	// the device levels and a scheduler entry for the level-6 system tick.
	for (int level = 0; level < 8; level++)
		m_maincpu->set_maskable_vector(level,
				level == 6 ? fw::KN7000_IRQ_SCHEDULER : fw::KN7000_IRQ_DISPATCH);

	// Group 0x11 (panel transfer complete) is level-like until serviced: if a
	// completion landed before the ISR's ack wiped it, re-deliver it after.
	m_maincpu->intc_ack_cb().set([this](uint8_t group) {
"""),
("""	// (MIDI-1 0x12, MIDI-2 0x14 -- see notes/panel-serial-protocol.md #6).
""",
 """	// (MIDI-1 0x12, MIDI-2 0x14).
"""),
])
