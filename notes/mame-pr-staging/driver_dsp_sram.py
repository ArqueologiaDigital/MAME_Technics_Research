"""Give the board's DSP SRAM back to the board.

QUESTION IT ANSWERS
  "The 21065L device no longer maps 0x20000 up. Who does?"

  IC307/IC308 are the KN7000's own external SRAM for the effects DSP, so the
  driver maps them, as it does every other memory on the board. The effects
  kernel clears its delay-line buffers there at boot and the reverb and echo
  effects run out of them.

RUN   python3 driver_dsp_sram.py     (from the PR worktree root)
PASS  prints "ok".
"""


# Only the commit that instantiates the DSP has a caller for this map; landing it
# earlier trips -Werror=unused-function on the three commits in between.
GUARD = "ADSP21065L(config, m_dsp"


def edit(path, pairs):
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        assert old in s, '%s MISSING: %r' % (path, old[:100])
        s = s.replace(old, new, 1)
    open(path, 'w').write(s)
    print('rewrote', path)


edit('src/mame/matsushita/kn7000.cpp', [
("""	void maincpu_mem(address_map &map) ATTR_COLD;
""",
 """	void maincpu_mem(address_map &map) ATTR_COLD;
	void dsp_data_mem(address_map &map) ATTR_COLD;
"""),
("""	m_dsp->set_boot_mode(adsp21065l_device::BOOT_MODE_HOST);
""",
 """	m_dsp->set_boot_mode(adsp21065l_device::BOOT_MODE_HOST);
	m_dsp->set_addrmap(AS_DATA, &kn7000_state::dsp_data_mem);
"""),
])

# The map goes next to the CPU's own.
edit('src/mame/matsushita/kn7000.cpp', [
("""// Read one sample word out of a wave ROM through the tone generator's own port.""",
 """// IC307/IC308, the effects DSP's external SRAM. On the 21065L, 0x20000 is where
// external memory begins; the effects kernel clears its delay-line buffers there at
// boot and the reverb and echo effects run out of them.
void kn7000_state::dsp_data_mem(address_map &map)
{
	map(0x20000, 0xfffff).ram();
}


// Read one sample word out of a wave ROM through the tone generator's own port."""),
])
print('ok')
