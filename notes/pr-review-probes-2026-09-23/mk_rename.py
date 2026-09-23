#!/usr/bin/env python3
"""Question answered: how many lines does the CHEAP option cost -- keep the
family-named class mn10300_device, name only the DEFINE_DEVICE_TYPE and the
driver instantiation for the concrete part (the upstream lpc210x_device /
LPC2103 pattern)?  Usage: mk_rename.py <dir>"""
import sys, os
d = sys.argv[1]
p = os.path.join(d, "mn10300.h"); s = open(p).read()
s = s.replace("DECLARE_DEVICE_TYPE(MN10300, mn10300_device)",
              "DECLARE_DEVICE_TYPE(MN103002A, mn10300_device)", 1)
s = s.replace("	void internal_map(address_map &map) ATTR_COLD;",
              "	void mn103002a_internal_map(address_map &map) ATTR_COLD;", 1)
open(p, "w").write(s)
p = os.path.join(d, "mn10300.cpp"); s = open(p).read()
s = s.replace('DEFINE_DEVICE_TYPE(MN10300, mn10300_device, "mn10300", "Panasonic MN10300")',
              'DEFINE_DEVICE_TYPE(MN103002A, mn10300_device, "mn103002a", "Panasonic MN103002A")', 1)
s = s.replace("	: cpu_device(mconfig, MN10300, tag, owner, clock)",
              "	: cpu_device(mconfig, MN103002A, tag, owner, clock)", 1)
s = s.replace("address_map_constructor(FUNC(mn10300_device::internal_map), this)",
              "address_map_constructor(FUNC(mn10300_device::mn103002a_internal_map), this)", 1)
s = s.replace("void mn10300_device::internal_map(address_map &map)",
              "void mn10300_device::mn103002a_internal_map(address_map &map)", 1)
open(p, "w").write(s)
p = os.path.join(d, "kn7000.cpp"); s = open(p).read()
s = s.replace("	MN10300(config, m_maincpu, 16_MHz_XTAL * 2);",
              "	MN103002A(config, m_maincpu, 16_MHz_XTAL * 2);", 1)
open(p, "w").write(s)
