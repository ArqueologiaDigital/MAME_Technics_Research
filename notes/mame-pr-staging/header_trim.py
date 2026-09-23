"""Last cut on the MN10300 header, against the density tell.

QUESTION IT ANSWERS
  "mn10300.h sits at 38% comment lines where its closest sibling mn10200.h is
   10%. What of that is not hardware documentation?"

  Most of it IS: two blocks, 50 lines, documenting an on-chip interrupt
  controller and three serial channels that have no datasheet and were read off
  the software that drives them. Cutting those would repeat the mistake this
  session already made once -- deleting real hardware knowledge to move a
  number. They stay, and the PR description says why the file is dense.

  What comes out is the part the house rule actually names: archaeology through
  MAME's own internals. A note about `execute_input_lines()` having been removed
  from the base class, and a citation of src/emu/addrmap.cpp for why an internal
  map takes priority, are both addressed to the reviewer of the diff rather than
  to the next reader of the file.

  Also corrected here: execute_max_cycles() advertised 24 with a TODO while
  execute_run() charges 1 per instruction and take_irq a flat 7, so nothing can
  cost more than 8. An advertised bound no instruction can reach is not a TODO,
  it is a wrong number.

RUN   python3 header_trim.py       (from the PR worktree root)
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


edit('src/devices/cpu/mn10300/mn10300.h', [
("""	virtual uint32_t execute_max_cycles() const noexcept override { return 24; } // TODO(MN10300): real worst-case opcode+IRQ cycles
	// (device_execute_interface::execute_input_lines() was removed from MAME;
	//  the input-line count is implicit. MN10300_MAX_EXT_IRQ lines are still used
	//  via set_input_line/execute_set_input.)
""",
 """	// Timing is uncalibrated: execute_run charges one cycle per instruction and
	// take_irq a flat seven, so nothing costs more than eight.
	virtual uint32_t execute_max_cycles() const noexcept override { return 8; }
"""),
("""	// Flat 32-bit little-endian space with a 32-bit data bus. The internal map
	// decodes the on-chip peripherals: the INTC (0x34000100-0x340002FF), the
	// SIO (0x34000800-0x3400082F) and the TM4/TM5 timer windows (0x34001080/
	// 0x34001090/0x340010A0, 4 bytes each); the rest of the machine is mapped
	// by the driver. MAME appends a device's internal map AFTER the driver's
	// map ("last so it takes priority" -- src/emu/addrmap.cpp), so these
	// windows layer cleanly over any driver-side entries.
""",
 """	// Flat 32-bit little-endian space with a 32-bit data bus. The internal map
	// decodes the on-chip peripherals: the INTC (0x34000100-0x340002FF), the
	// SIO (0x34000800-0x3400082F) and the TM4/TM5 timer windows (0x34001080/
	// 0x34001090/0x340010A0, 4 bytes each); the machine maps the rest.
"""),
])
print('ok')
