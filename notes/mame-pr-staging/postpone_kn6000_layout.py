"""Remove the KN6000/KN6500 artwork from a PR copy of kn7000.cpp.

Splits kn7000() into kn7000_base() (the shared machine) plus the KN7000's own
layout, so the KN6000/KN6500 can take the machine WITHOUT inheriting a layout
whose elements sit at KN7000 positions with KN7000 bindings.
"""
import sys
p = 'src/mame/matsushita/kn7000.cpp'
s = open(p, encoding='utf-8').read()

def cut(old, new=''):
    global s
    assert old in s, "MISSING: %r" % old[:70]
    s = s.replace(old, new, 1)

cut('#include "kn6000.lh"\n')
cut('\tvoid kn7000(machine_config &config) ATTR_COLD;\n',
    '\tvoid kn7000_base(machine_config &config) ATTR_COLD;\n'
    '\tvoid kn7000(machine_config &config) ATTR_COLD;\n')
cut('void kn7000_state::kn7000(machine_config &config)\n{',
    'void kn7000_state::kn7000_base(machine_config &config)\n{')
cut("""	// Clickable front-panel artwork: buttons bound to the ioports, LEDs bound to
	// the cpl_led/cpc_led/cpr_led outputs.
	config.set_default_layout(layout_kn7000);

""")

anchor = '// KN6000/KN6500 reuse the KN7000 machine, but their library ROM at 0x4C000000 is'
assert anchor in s, "kn6000 preamble missing"
s = s.replace(anchor,
"""void kn7000_state::kn7000(machine_config &config)
{
	kn7000_base(config);
	// Clickable front-panel artwork: buttons bound to the ioports, LEDs bound to
	// the cpl_led/cpc_led/cpr_led outputs.
	config.set_default_layout(layout_kn7000);
}

""" + anchor, 1)

cut('void kn7000_state::kn6000(machine_config &config)\n{\n\tkn7000(config);',
    'void kn7000_state::kn6000(machine_config &config)\n{\n\tkn7000_base(config);')
cut("""	// ...and its OWN artwork.  Installing the matrix alone was not enough: the default layout was
	// still layout_kn7000, so every clickable element on screen sat at a KN7000 position, carried a
	config.set_default_layout(layout_kn6000);
""",
"""	// No artwork: the KN6000/KN6500 panel layout is not finished, and the KN7000's
	// would put every clickable element at the wrong place with the wrong binding.
""")

assert 'layout_kn6000' not in s and 'kn6000.lh' not in s
open(p, 'w').write(s)
print("ok")
