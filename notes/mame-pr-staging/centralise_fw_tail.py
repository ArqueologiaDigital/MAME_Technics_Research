"""The three sibling-model bindings centralise_fw.py rewrote with regexes,
expressed as literal (old, new) pairs so the commit split can replay them."""


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
("""	m_tg_recbase    = 0x5027AF28;      // vs the KN7000's 0x500AF940 (same 0xB4 stride);
	                                   // the per-SLOT copy, not the library array (see above)
""",
 """	m_tg_recbase    = fw::KN6000_VOICE_RECORDS;
"""),
("""	m_tg_recbase = 0x5027AF1C;
""",
 """	m_tg_recbase = fw::KN6500_VOICE_RECORDS;
"""),
("""// the per-TG-slot voice record sits at 0x5027AF1C rather than the KN6000's 0x5027AF28.
""",
 """// the per-TG-slot voice record sits one record earlier than the KN6000's.
"""),
])

# Both sibling machine configs route every maskable level to trampoline slot 0.
edit_all('src/mame/matsushita/kn7000.cpp', [
("""		m_maincpu->set_maskable_vector(level, 0x90000000);""",
 """		m_maincpu->set_maskable_vector(level, fw::TRAMPOLINE_SLOT0);""", 2),
])
print('ok')
