"""Trim the internal-map comment, and say what the reset PC is.

QUESTION IT ANSWERS
  "What in these comments is for the reviewer rather than for the reader of the
   code six months from now?"

  Two things, both flagged on earlier Technics PRs (#15919, #16204) as belonging
  in the pull request description:

    * "Precedent: the MN10200 core hangs its on-chip peripherals off the same
      mechanism" -- an argument that a CPU device may have an internal map,
      addressed to whoever reviews this, not to the code.
    * "everything the pre-migration KN7000 driver left to its logging handlers
      ... still falls through to the machine map exactly as before" -- this
      project's own migration history, meaningless once merged.

  The block also opened twice, describing the same map in two sentences that had
  drifted apart. Twelve comment lines become six that say what is decoded here
  and why the timer windows are narrow.

  The reset PC gets the other half of the same fact the IVAR work established:
  the MN10300 resets to 0x40000000 invariably (manufacturer's manual, Memory
  Layout), so a board constant of 0x48400000 is where THIS board answers that
  address -- and the flash there does begin with the vector table, measured in
  notes/irq-vector-probes/vector_table_layout.py. The comment said only "program
  flash base", which does not explain why a shared CPU core needs a board to
  tell it where to start.

RUN   python3 trim_internal_map_comment.py   (from the PR worktree root)
PASS  the driver builds; comment density does not rise.
"""

C = 'src/devices/cpu/mn10300/mn10300.cpp'
TARGET = 'src/mame/matsushita/kn7000.cpp'


def edit(path, pairs):
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        if old not in s:
            raise SystemExit('NOT FOUND in %s: %r' % (path, old[:70]))
        s = s.replace(old, new, 1)
    open(path, 'w').write(s)


edit(C, [
("""// Internal address map: the interrupt vector registers, INTC, SIO and TM4/TM5.
// Precedent: the MN10200 core (mn1020012a_internal_map) hangs its on-chip
// peripherals off the same mechanism. The timer windows are deliberately
// narrow (4 bytes each, and the counter window is READ-only) so everything
// the pre-migration KN7000 driver left to its logging handlers -- the
// 0x1084-0x108F siblings, TMnBC writes, ... -- still falls through to the
// machine map exactly as before.
// Flat 32-bit little-endian space with a 32-bit data bus. This decodes the
// on-chip peripherals -- IVAR0-IVAR6 (0x20000000-0x2000001B), the INTC
// (0x34000100-0x340002FF), the SIO (0x34000800-0x3400082F) and the TM4/TM5
// timer windows (0x34001080/0x34001090/0x340010A0, 4 bytes each) -- and the
// machine maps the rest.
""",
 """// Internal address map, in a flat 32-bit little-endian space with a 32-bit data
// bus: IVAR0-IVAR6 (0x20000000-0x2000001B), the INTC (0x34000100-0x340002FF),
// the SIO (0x34000800-0x3400082F) and the TM4/TM5 timer windows (0x34001080,
// 0x34001090 and 0x340010A0, 4 bytes each, the counter window read-only). The
// machine maps the rest; the timer windows are narrow so that the undecoded
// registers beside them reach it rather than being swallowed here.
"""),
])

edit(TARGET, [
("""\tm_maincpu->set_reset_pc(0x48400000);   // program flash base
""",
 """\t// The MN10300 always resets to 0x40000000; this is where the board answers
\t// that, and the flash does begin with the vector table it implies.
\tm_maincpu->set_reset_pc(0x48400000);
"""),
])

print('trim_internal_map_comment: applied')

# Two more comments that explain this project's migration rather than the code.
edit(C, [
("""\t// Debugger notification (and any machine-registered acknowledge callback --
\t// none is needed now that the INTC latch lives here in intc_accept).
\tstandard_irq_callback(0, m_pc);
\t// The on-chip INTC freezes its arbitration result (group + vector) at the
\t// exact accept instant, like real hardware. NOTE: the PSW.IM level below
\t// deliberately uses the `level` PARAMETER (captured by check_irq before
\t// this re-arbitration) -- byte-exact with the pre-migration driver flow,
\t// where irq_ack updated m_irq_level after check_irq had read it.
\tintc_accept();
""",
 """\tstandard_irq_callback(0, m_pc);
\t// The INTC freezes its arbitration result -- group and vector -- at the accept
\t// instant. PSW.IM below takes the `level` PARAMETER, which check_irq captured
\t// before that re-arbitration, so a source arriving between the two does not
\t// change the mask the handler runs under.
\tintc_accept();
"""),
("""\t// Drive our own maskable input line through the standard (synchronized)
\t// set_input_line path -- identical timing to the pre-migration driver,
\t// whose INTC called m_maincpu->set_input_line from its handlers.
\tset_input_line(0, g ? ASSERT_LINE : CLEAR_LINE);
""",
 """\t// Drive our own maskable input line through the standard, synchronized path.
\tset_input_line(0, g ? ASSERT_LINE : CLEAR_LINE);
"""),
])

print('trim_internal_map_comment: migration archaeology removed')
