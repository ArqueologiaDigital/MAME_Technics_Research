"""Split the CPU core into an abstract mn10300_device and a concrete MN103002A.

QUESTION IT ANSWERS
  "Should a device named for a whole family install one part's peripheral map?"

  No, and the shape to follow is one directory away: cpu/mn10200 is an abstract
  mn10200_device plus a concrete MN1020012A, with the internal map on the
  concrete part. The KN7000's CPU is an MN103002A, which is what the
  already-merged kn7000.cpp names in its commented-out placeholders.

  ⚠ The census argument for this is WEAKER than it first looked, and the honest
  version is: most MAME CPU device types that install an internal peripheral map
  are named for a concrete part; a handful are named for a core or a series --
  ARCA5, MN1880, XA -- and those are the cases where the actual part is not
  identified. Here it is identified, which is why the split applies. An earlier
  draft of this claimed "zero out of 28 precedent, MN10300 would be the first";
  that is false (ARCA5 is a licensable core, not a part) and must not be shipped.

  The driver keeps required_device<mn10300_device>, exactly as taito_zm.h does
  for MN1020012A, and scripts/src/cpu.lua keeps CPUS["MN10300"] -- MN10200 shows
  the build token is the family, not the device.

RUN   python3 split_mn103002a.py      (from the PR worktree root)
PASS  prints "ok"; the driver must still build and every machine still boot.
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


edit('src/devices/cpu/mn10300/mn10300.h', [
("""	mn10300_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock);
""", ""),
("""	void internal_map(address_map &map) ATTR_COLD;
""", ""),
("""protected:
	// device_t overrides
""",
 """protected:
	mn10300_device(const machine_config &mconfig, device_type type, const char *tag, device_t *owner,
			uint32_t clock, address_map_constructor program);

	// The MN103002A's on-chip peripheral complement: INTC at 0x34000100, SIO at
	// 0x34000800, and the TM4/TM5 timer windows.
	void mn103002a_internal_map(address_map &map) ATTR_COLD;

	// device_t overrides
"""),
("""DECLARE_DEVICE_TYPE(MN10300, mn10300_device)""",
 """// The concrete part in the Technics SX-KN series. The family base above carries
// the core; this carries the peripheral map, the way cpu/mn10200 splits
// mn10200_device from MN1020012A.
class mn103002a_device : public mn10300_device
{
public:
	mn103002a_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock);
};

DECLARE_DEVICE_TYPE(MN103002A, mn103002a_device)"""),
])

edit('src/devices/cpu/mn10300/mn10300.cpp', [
("""DEFINE_DEVICE_TYPE(MN10300, mn10300_device, "mn10300", "Panasonic MN10300")""",
 """DEFINE_DEVICE_TYPE(MN103002A, mn103002a_device, "mn103002a", "Panasonic MN103002A")"""),
("""mn10300_device::mn10300_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: cpu_device(mconfig, MN10300, tag, owner, clock)
	// Flat 32-bit little-endian space, 32-bit data bus. The internal map supplied
	// here decodes the on-chip peripherals (INTC, SIO, TM4/TM5 timers) and is
	// appended after the driver's map, so it takes priority over any overlapping
	// driver entry while leaving the surrounding mappings intact.
	, m_program_config("program", ENDIANNESS_LITTLE, 32, 32, 0, address_map_constructor(FUNC(mn10300_device::internal_map), this))
""",
 """mn103002a_device::mn103002a_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: mn10300_device(mconfig, MN103002A, tag, owner, clock,
			address_map_constructor(FUNC(mn103002a_device::mn103002a_internal_map), this))
{
}

mn10300_device::mn10300_device(const machine_config &mconfig, device_type type, const char *tag,
		device_t *owner, uint32_t clock, address_map_constructor program)
	: cpu_device(mconfig, type, tag, owner, clock)
	// Flat 32-bit little-endian space, 32-bit data bus. The concrete part supplies
	// the internal map, which is appended after the driver's map and so takes
	// priority over any overlapping driver entry.
	, m_program_config("program", ENDIANNESS_LITTLE, 32, 32, 0, program)
"""),
("""void mn10300_device::internal_map(address_map &map)""",
 """void mn10300_device::mn103002a_internal_map(address_map &map)"""),
])

edit('src/mame/matsushita/kn7000.cpp', [
("""	MN10300(config, m_maincpu, 16_MHz_XTAL * 2);""",
 """	MN103002A(config, m_maincpu, 16_MHz_XTAL * 2);"""),
])
print('ok')
