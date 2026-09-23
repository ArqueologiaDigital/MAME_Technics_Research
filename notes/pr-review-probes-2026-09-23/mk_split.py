#!/usr/bin/env python3
"""Question answered: how many lines does the abstract-base + concrete
mn103002a_device split actually cost, measured rather than guessed?
Applies the mn10200/mn1020012a pattern to a COPY of the three files and
leaves them for `diff -u` against the originals.  Usage: mk_split.py <dir>"""
import sys, io, os
d = sys.argv[1]

# ---- mn10300.h -------------------------------------------------------------
p = os.path.join(d, "mn10300.h"); s = open(p).read()

s = s.replace(
"""public:
	// construction/destruction (single concrete, instantiable device)
	mn10300_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock);
""",
"""public:
""", 1)

s = s.replace(
"""protected:
	// device_t overrides""",
"""protected:
	// construction/destruction (abstract base; a concrete part supplies its map)
	mn10300_device(const machine_config &mconfig, device_type type, const char *tag, device_t *owner, uint32_t clock, address_map_constructor program);

	// The MN103002A's on-chip peripheral complement.
	void mn103002a_internal_map(address_map &map) ATTR_COLD;

	// device_t overrides""", 1)

s = s.replace("""	void internal_map(address_map &map) ATTR_COLD;
""", "", 1)

s = s.replace(
"""DECLARE_DEVICE_TYPE(MN10300, mn10300_device)""",
"""class mn103002a_device : public mn10300_device
{
public:
	mn103002a_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock);
};

DECLARE_DEVICE_TYPE(MN103002A, mn103002a_device)""", 1)
open(p, "w").write(s)

# ---- mn10300.cpp -----------------------------------------------------------
p = os.path.join(d, "mn10300.cpp"); s = open(p).read()
s = s.replace(
'DEFINE_DEVICE_TYPE(MN10300, mn10300_device, "mn10300", "Panasonic MN10300")',
'DEFINE_DEVICE_TYPE(MN103002A, mn103002a_device, "mn103002a", "Panasonic MN103002A")', 1)
s = s.replace(
"""mn10300_device::mn10300_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: cpu_device(mconfig, MN10300, tag, owner, clock)""",
"""mn10300_device::mn10300_device(const machine_config &mconfig, device_type type, const char *tag, device_t *owner, uint32_t clock, address_map_constructor program)
	: cpu_device(mconfig, type, tag, owner, clock)""", 1)
s = s.replace(
"""	, m_program_config("program", ENDIANNESS_LITTLE, 32, 32, 0, address_map_constructor(FUNC(mn10300_device::internal_map), this))""",
"""	, m_program_config("program", ENDIANNESS_LITTLE, 32, 32, 0, program)""", 1)
s = s.replace(
"""void mn10300_device::internal_map(address_map &map)""",
"""void mn10300_device::mn103002a_internal_map(address_map &map)""", 1)
# the concrete part
s = s.replace(
"""device_memory_interface::space_config_vector mn10300_device::memory_space_config() const""",
"""mn103002a_device::mn103002a_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: mn10300_device(mconfig, MN103002A, tag, owner, clock, address_map_constructor(FUNC(mn103002a_device::mn103002a_internal_map), this))
{ }


device_memory_interface::space_config_vector mn10300_device::memory_space_config() const""", 1)
open(p, "w").write(s)

# ---- kn7000.cpp ------------------------------------------------------------
p = os.path.join(d, "kn7000.cpp"); s = open(p).read()
s = s.replace("	MN10300(config, m_maincpu, 16_MHz_XTAL * 2);",
              "	MN103002A(config, m_maincpu, 16_MHz_XTAL * 2);", 1)
open(p, "w").write(s)
