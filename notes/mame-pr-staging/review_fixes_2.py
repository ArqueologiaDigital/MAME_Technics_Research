"""The follow-up edits made at the prompt while clearing the review fixes:
the two ROM regions, the stranded SIO enumerator, the dead cpsd_queue body,
and the three build breaks the first pass left. Captured in the same
(old, new) form so the commit split can replay them."""


def edit_all(path, pairs):
    """Replace EVERY occurrence, asserting the expected count."""
    s = open(path, encoding='utf-8').read()
    for old, new, want in pairs:
        got = s.count(old)
        assert got == want, '%s: expected %d of %r, found %d' % (path, want, old[:60], got)
        s = s.replace(old, new)
    open(path, 'w').write(s)
    print('rewrote', path)


def edit(path, pairs):
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        assert old in s, '%s MISSING: %r' % (path, old[:90])
        s = s.replace(old, new, 1)
    open(path, 'w').write(s)
    print('rewrote', path)


edit('src/mame/matsushita/kn7000.cpp', [
# CPSD frame delivery on ch2: dead since ch2 turned out to be the second MIDI
# UART rather than the SD link.
("""// CPSD (SD sub-CPU) frame delivery on SIO ch2. Simpler than the panel path: the
// firmware has already seen bit7 of the status set (cpsd_queue makes it read set)
// and enabled the ch2 RX interrupt; each timer tick clocks one byte into the ch2
// RX FIFO and fires group 0x14, which the firmware's ISR reads from +9.
[[maybe_unused]] void kn7000_state::cpsd_queue(const uint8_t *bytes, int n)
{
	// Deliver the whole frame into the ch2 RX FIFO at once; one interrupt per byte.
	for (int i = 0; i < n; i++)
		m_maincpu->sio_rx_push(SIO_SD, bytes[i]);
}

""", ""),
("""	enum { SIO_PANEL = 0, SIO_MIDI1 = 1, SIO_MIDI2 = 2, SIO_SD = 2 };
""",
 """	enum { SIO_PANEL = 0, SIO_MIDI1 = 1, SIO_MIDI2 = 2 };
"""),
])

# The KN6000/KN6500 custom-data payloads are byte-identical in orientation to
# the KN7000's, and intelfsh reads the region with as_u16(), so a plain
# ROM_REGION loads them halfword-swapped and host-endianness-dependent.
edit_all('src/mame/matsushita/kn7000.cpp', [
("""	ROM_REGION(0x200000, "custom_data", ROMREGION_ERASEFF)""",
 """	ROM_REGION16_BE(0x200000, "custom_data", ROMREGION_ERASEFF)""", 2),
])
print('ok')
