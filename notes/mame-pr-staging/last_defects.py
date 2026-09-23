"""Four more defects from the review, each re-verified against the source.

RUN   python3 last_defects.py        (from the PR worktree root)
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
            raise AssertionError('%s MISSING: %r' % (path, old[:100]))
    open(path, 'w').write(s)
    print('rewrote', path)


# 1. AN INVENTED HARDWARE IDENTIFIER. The host register returned 0x1065 as the
#    DSP's ID with "exact value TBD" beside it -- a number made up to look like
#    a part number. Nothing reads it (the boot probe checks register 0), so
#    report that it is unknown instead of inventing one.
edit('src/mame/matsushita/kn7000.cpp', [
# 0. A replacement in the comment-completion pass left the half-sentence it was
#    meant to finish sitting above the new one.
("""	// Answer the host register read selected by the latched index. The boot probe
	// The boot probe reads register 0 and requires 0x20 to consider the DSP alive.
""",
 """	// Answer the host register read selected by the latched index. The boot probe
	// reads register 0 and requires 0x20 to consider the DSP alive.
"""),
("""	case 0x0B: return 0x1065;    // ID/version readback (plausible 21065L id; exact value TBD)
""",
 """	case 0x0B:                   // ID/version readback; the real value is not known
		logerror("%s: effects DSP ID register read\\n", machine().describe_context());
		return 0x0000;
"""),
])

# 2. A BYTE WRITE TO THE TIMER RELOAD STORED A HALF-FORMED WORD. tm45_base_w
#    took mem_mask and dropped it, so movbu to either half of TM5BR wrote the
#    other half as zero.
edit('src/devices/cpu/mn10300/mn10300.cpp', [
("""void mn10300_device::tm45_base_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	if (offset)
		tm5_base_w(data);
}
""",
 """void mn10300_device::tm45_base_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	if (offset)
	{
		uint16_t base = m_tm5_base;
		COMBINE_DATA(&base);      // a byte write must keep the other half
		tm5_base_w(base);
	}
}
"""),
# 3. Empty overrides that only restate the base class's defaults.
("""void mn10300_device::state_import(const device_state_entry &entry) { }
void mn10300_device::state_export(const device_state_entry &entry) { }

""", ""),
])

edit('src/devices/cpu/mn10300/mn10300.h', [
("""	virtual void state_import(const device_state_entry &entry) override;
	virtual void state_export(const device_state_entry &entry) override;
""", ""),
# 4. Design rationale belongs in the PR description, and "the HLE" names
#    something that exists nowhere in MAME's tree.
("""	// LOWEST level value (highest priority). Quirks preserved from the HLE:
""",
 """	// LOWEST level value (highest priority). Quirks:
"""),
("""	// Modeled in the core, following the MN10200 core's precedent (its on-chip
	// serial lives in mn10200_device::m_serial[] behind an internal address map).
	// Reverse-engineered from software that drives it; no datasheet was available.
""",
 """	// Reverse-engineered from software that drives it; no datasheet was available.
"""),
])

# 5. TWO OVERCLAIMS. Both sites state "is a bus mirror of the program ROM" as an
#    established hardware fact. The evidence is one crt0 read, and what the code
#    actually models is a one-shot fill at machine_start. Say what was observed.
edit('src/mame/matsushita/kn7000.cpp', [
("""	// KN6000/KN6500: unlike the KN7000 (which self-loads its library), the
	// "library" at 0x4C000000/0x8C000000 is a bus mirror of the program ROM.
	// Populate the aliased libram from the program ROM so the boot finds it.
""",
 """	// KN6000/KN6500: unlike the KN7000, which self-loads its library, these
	// firmwares read the library at 0x4C000000/0x8C000000 without ever writing
	// it. What backs that window on the board is not established; filling it from
	// the program ROM here is what makes the boot find what it reads.
"""),
("""// KN6000/KN6500 reuse the KN7000 machine, but their library ROM at 0x4C000000 is
// a bus mirror of the program ROM (populated in machine_start), not self-loaded.
""",
 """// KN6000/KN6500 reuse the KN7000 machine, but their firmware expects the library
// at 0x4C000000 to be populated already rather than self-loading it; machine_start
// fills it from the program ROM.
"""),
])

# 6. LOGGING MACHINERY WITH NO CALLER. kn_cpanel.cpp defines VERBOSE and pulls in
#    logmacro.h without a single LOG call; kn7000_cpanel.cpp declares four
#    categories and uses one.
edit('src/mame/matsushita/kn_cpanel.cpp', [
("""#include "kn_cpanel.h"

#define VERBOSE 0
#include "logmacro.h"

""",
 """#include "kn_cpanel.h"

"""),
])
edit('src/mame/matsushita/kn7000_cpanel.cpp', [
("""#define LOG_COMMANDS (1U << 1)
#define LOG_SERIAL   (1U << 2)
#define LOG_BUTTONS  (1U << 3)
#define LOG_LEDS     (1U << 4)
""",
 """#define LOG_LEDS (1U << 4)
"""),
])

# 7. CONSTANT PREDICATES AND DEAD FINDERS. dsp_present() and tg_sound_enabled()
#    are literal `return true` with three sites branching on them; m_vram is a
#    required_shared_ptr with no use but its own two declarations; MAX_VOICES is
#    declared and never read, while the arrays below it are hardcoded [128].
edit('src/mame/matsushita/kn7000.cpp', [
("""		, m_vram(*this, "vram")
""", ""),
("""	required_shared_ptr<uint32_t> m_vram;        // LCD V-RAM window at 0x90000000
""", ""),
("""	bool     dsp_present() { return true; }        // IC306 ADSP-21065L is always fitted
	bool     tg_sound_enabled() { return true; }   // IC201/IC205 tone generators are always fitted
""", ""),
("""		return 0x8000 | (tg_sound_enabled() ? 0x0006 : 0) | (m_rearsw->read() & 0x1000);
""",
 """		return 0x8000 | 0x0006 | (m_rearsw->read() & 0x1000);
"""),
("""	if (!dsp_present())
		return 0;
	// Answer the host register read""",
 """	// Answer the host register read"""),
("""	if (!dsp_present())
		return;
	// Host boot: decode""",
 """	// Host boot: decode"""),
])
edit('src/mame/matsushita/kn_tonegen.h', [
("""	static constexpr int MAX_VOICES = 128;   // the KN7000, the largest of the family

""", ""),
])
print('ok')
