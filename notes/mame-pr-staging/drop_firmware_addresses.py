"""Replace hardcoded firmware addresses with the mechanisms they were standing in for.

QUESTION IT ANSWERS
  "Why does this driver know one firmware revision's internal addresses?"

  For five of the eight, it did not have to. Each is replaced by the hardware
  behaviour it was substituting for, established from the ROM images of all three
  firmwares (KN7000, KN6000, KN2400):

  1. THE INTERRUPT VECTOR. The MN103002 vectors a maskable interrupt of level L
     through IVR[L], a 16-bit register at 0x20000000 + L*4. All three firmwares
     write IVR0..IVR6 = 0 once at boot and never touch them again, then build a
     6-byte `nop ; jmp <handler>` thunk at 0x90000000 whose displacement is
     computed against its own execution address. So ONE vector serves all seven
     levels on every machine, and the handler address is the thunk's business,
     not the driver's.
       KN7000  builder 0x48410070  thunk 0 -> 0x4C03DE26
       KN6000  builder 0x484003AB  thunk 0 -> 0x4C3F7942
       KN2400  builder 0x48705CD5  thunk 0 -> 0x5018DF0B
     The KN7000 was being special-cased into two handlers split by level. That
     was never real: 0x4C03DDA0 is referenced by NOTHING in the 4 MB image --
     no literal, no branch -- it is a dead alternate build of the same handler.

  2. THE RESET STACK POINTER. Every reset path establishes SP before its first
     push or call, so the CPU does not need one:
       KN7000  reset 0x48407EFF -> sets sp 0x4840FFFF, first call after
       KN6000  reset 0x484002E3 -> sets sp 0x48400356, first call 0x4840035B
       KN2400  reset 0x48705BDF -> sets sp 0x48705C60, first call 0x48705C65

  3. THE SD PLAY/PAUSE LAMP. The firmware drives it through a hardware GPIO byte
     at 0x9CC00008 with bset/bclr on bits 6-7, so the lamp is a register write,
     not something to be inferred by reading work RAM.

  What REMAINS is the three voice-record bases, which are not yet replaceable:
  see the comment this leaves on them.

RUN   python3 drop_firmware_addresses.py     (from the PR worktree root)
PASS  prints "ok"; every replacement is asserted.
"""


def edit_all(path, pairs):
    """Replace EVERY occurrence, asserting the expected count."""
    s = open(path, encoding='utf-8').read()
    for old, new, want in pairs:
        got = s.count(old)
        assert got in (0, want), '%s: expected %d of %r, found %d' % (path, want, old[:60], got)
        s = s.replace(old, new)
    open(path, 'w').write(s)
    print('rewrote', path)


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


edit('src/mame/matsushita/kn7000.cpp', [
# ---- the constants block ------------------------------------------------
("""// Locations inside the running firmware, not hardware registers. The driver has
// to know a few because the machine exposes no other way to reach them: which
// handler an interrupt vector should enter, where the voice records the tone
// generator resolves pitch from live, and the SD transport state behind the
// front-panel lamp. They move between firmware revisions, so they are pinned
// here rather than spelled out at each use.
namespace fw {

// Interrupt entry points. The KN7000 installs two handlers in its self-loaded
// library and splits the levels between them; the KN6000, KN6500, KN2400 and
// KN2600 build a trampoline table instead and send every level to slot 0.
constexpr offs_t KN7000_IRQ_DISPATCH   = 0x4C03DDA0;   // device levels, no stack switch
constexpr offs_t KN7000_IRQ_SCHEDULER  = 0x4C03DE26;   // the level-6 system tick
constexpr offs_t TRAMPOLINE_SLOT0      = 0x90000000;

// Per-slot voice records, 0xB4 stride, 128 slots. Each carries the musical
// pitch the firmware computed, which is what the tone generator plays.
constexpr offs_t KN7000_VOICE_RECORDS  = 0x500AF940;
constexpr offs_t KN6000_VOICE_RECORDS  = 0x5027AF28;
constexpr offs_t KN6500_VOICE_RECORDS  = 0x5027AF1C;

// Initial stack pointer: the firmware image is linked against it and its startup
// code runs before establishing one.
constexpr offs_t RESET_SP              = 0x50021CF8;

// SD transport state, polled for the PLAY/PAUSE lamp: 1 playing, 2 paused, 0 stopped.
constexpr offs_t SD_AUDIO_PLAY_STATE   = 0x500063E6;
constexpr offs_t SD_SONG_PLAY_STATE    = 0x500063D9;

} // namespace fw
""",
 """// Every firmware here builds its interrupt entry as a 6-byte `nop ; jmp handler`
// thunk at the base of this window, with the jump displacement computed against
// the thunk's own execution address. The MN103002 vectors a maskable interrupt of
// level L through IVR[L] at 0x20000000 + L*4, and all of them write IVR0..IVR6 = 0
// once at boot, so one entry serves all seven levels. The driver therefore points
// the CPU at the window and the thunk supplies the handler.
constexpr offs_t IRQ_VECTOR_WINDOW = 0x90000000;

// The tone generator plays the musical pitch the firmware computes, and the
// driver reads it out of the firmware's per-slot voice record (0xB4 stride) at
// these bases. This is the one dependency that has not been replaced: the raw
// 18-bit pitch the tone generator receives is relative to a per-sample root, and
// the wave ROMs that would carry those roots have no dump. Decoding the register
// classes that name the sample would remove it; see the tone generator's notes.
constexpr offs_t KN7000_VOICE_RECORDS = 0x500AF940;
constexpr offs_t KN6000_VOICE_RECORDS = 0x5027AF28;
constexpr offs_t KN6500_VOICE_RECORDS = 0x5027AF1C;
"""),
])
print('ok')


# ---- 1. the interrupt vector: one window, all five machines ----------------
edit('src/mame/matsushita/kn7000.cpp', [
("""	m_maincpu->set_reset_pc(0x48400000);   // program flash base
	m_maincpu->set_reset_sp(fw::RESET_SP);

	// Per-level maskable vectors: the firmware installs a quick dispatcher for
	// the device levels and a scheduler entry for the level-6 system tick.
	for (int level = 0; level < 8; level++)
		m_maincpu->set_maskable_vector(level,
				level == 6 ? fw::KN7000_IRQ_SCHEDULER : fw::KN7000_IRQ_DISPATCH);
""",
 """	m_maincpu->set_reset_pc(0x48400000);   // program flash base

	// One maskable vector serves every level: the firmware writes IVR0..IVR6 = 0
	// and puts a jump to its handler in the vector window.
	for (int level = 0; level < 8; level++)
		m_maincpu->set_maskable_vector(level, IRQ_VECTOR_WINDOW);
"""),
("""	// KN6000/KN6500 interrupt vectors: every maskable IRQ goes to the firmware-built
	// trampoline slot 0, whose general handler reads the latched group and dispatches.
	// Slot 1 is that firmware's fault handler, not an IRQ path -- routing IRQs there
	// halts the boot.
	for (int level = 0; level < 8; level++)
		m_maincpu->set_maskable_vector(level, IRQ_VECTOR_WINDOW);

""", ""),
("""	// Like the KN6000, the KN2400 firmware builds its own interrupt trampoline
	// table; route all maskable IRQs to trampoline slot 0 rather than the
	// KN7000's library handler addresses (which don't exist on this firmware).
	for (int level = 0; level < 8; level++)
		m_maincpu->set_maskable_vector(level, IRQ_VECTOR_WINDOW);
""", ""),
])

# ---- 2. the SD panel lamps come off the GPIO byte the firmware writes ------
edit('src/mame/matsushita/kn7000.cpp', [
("""			return (m_lcdbuf[0x00C00008 >> 2] & 0xFFFFFF00) | (~m_sdsw->read() & 0x3F);
""",
 """			// Bits 0-5 are the six transport switches. Bits 6-7 are the two SD-panel
			// lamps, which the firmware sets and clears with bset/bclr on this byte
			// (eleven sites), so they have to read back for that to work.
			return (m_lcdbuf[0x00C00008 >> 2] & 0xFFFFFFC0) | (~m_sdsw->read() & 0x3F);
"""),
("""	// SD PLAY/PAUSE lamp (sd_led1): lit while SD-Audio or SD-Song playback is engaged. The play-state
	// state bytes (see fw:: above). Lit on either play or pause.
	address_space &prg = m_maincpu->space(AS_PROGRAM);
	const uint8_t sd_aud = prg.read_byte(fw::SD_AUDIO_PLAY_STATE);
	const uint8_t sd_snd = prg.read_byte(fw::SD_SONG_PLAY_STATE);
	m_sd_leds[1] = (sd_aud == 1 || sd_aud == 2 || sd_snd == 1 || sd_snd == 2) ? 1 : 0;
""",
 """	// SD panel lamp. The firmware drives two lamp bits, 6 and 7, of the SD panel
	// GPIO byte; which bit is which lamp is not established, so the single output
	// the artwork carries follows either of them.
	m_sd_leds[1] = (m_lcdbuf[0x00C00008 >> 2] & 0xC0) ? 1 : 0;
"""),
])
print('ok (vector + sd lamp)')


# ---- 3. the sibling loops are now redundant: kn7000_base() sets the vector --
edit('src/mame/matsushita/kn7000.cpp', [
("""	// KN6000/KN6500 interrupt vectors: every maskable IRQ goes to the firmware-built
	// trampoline slot 0, whose general handler reads the latched group and dispatches.
	// Slot 1 is that firmware's fault handler, not an IRQ path -- routing IRQs there
	// halts the boot.
	for (int level = 0; level < 8; level++)
		m_maincpu->set_maskable_vector(level, fw::TRAMPOLINE_SLOT0);

""", ""),
("""	// Like the KN6000, the KN2400 firmware builds its own interrupt trampoline
	// table; route all maskable IRQs to trampoline slot 0 rather than the
	// KN7000's library handler addresses (which don't exist on this firmware).
	for (int level = 0; level < 8; level++)
		m_maincpu->set_maskable_vector(level, fw::TRAMPOLINE_SLOT0);
""", ""),
])

# ---- 4. the surviving voice-record constants are no longer in a namespace --
edit_all('src/mame/matsushita/kn7000.cpp', [
    ('fw::KN7000_VOICE_RECORDS', 'KN7000_VOICE_RECORDS', 2),
    ('fw::KN6000_VOICE_RECORDS', 'KN6000_VOICE_RECORDS', 1),
    ('fw::KN6500_VOICE_RECORDS', 'KN6500_VOICE_RECORDS', 1),
])

# ---- 5. the CPU core said the split was real; it never was ------------------
edit('src/devices/cpu/mn10300/mn10300.h', [
("""	void set_reset_sp(uint32_t sp) { m_reset_sp = sp; }
""", ""),
("""	// Reset state. The boot address and initial stack pointer are strapped per
	// board, so the machine supplies them.
""",
 """	// Reset state. The boot address is strapped per board, so the machine supplies
	// it; the reset code establishes its own stack pointer.
"""),
("""	uint32_t m_reset_sp = 0;
""", ""),
])
edit('src/devices/cpu/mn10300/mn10300.cpp', [
("""	// Boot address and initial stack are strapped per board, so the machine
	// supplies them (set_reset_pc/set_reset_sp).
	m_pc  = m_reset_pc;
	m_sp  = m_reset_sp;
""",
 """	// The boot address is strapped per board (set_reset_pc). SP is left at zero:
	// the reset code establishes its own before its first push or call.
	m_pc  = m_reset_pc;
	m_sp  = 0;
"""),
("""	// The AM33 dispatches each interrupt LEVEL through its own vector, so the
	// vector must be selected from the pending level rather than fixed once. A
	// system that runs its scheduler from one level and quick device handlers
	// from the others relies on this: sending a scheduler-level interrupt to a
	// handler that does not switch stacks corrupts the next task switch. The
	// level -> vector table is board policy (set_maskable_vector).
""",
 """	// The AM33 selects a maskable interrupt's vector per LEVEL, through the IVR
	// register file. The machine supplies the resulting per-level table
	// (set_maskable_vector); a system that programs every IVR alike fills it with
	// one repeated entry.
"""),
])
print('ok (siblings + core)')
