"""Give the MN10300 core its own interrupt vector registers (IVAR0-IVAR6).

QUESTION IT ANSWERS
  "The driver hands the CPU a seven-entry vector table through
   set_maskable_vector(). Is the vector really board policy?"

  No. IVAR0..IVAR6 are registers of the CPU, not of the board: seven 16-bit
  registers at 0x20000000 + n*4, one per maskable interrupt level, holding the
  low 16 bits of that level's entry point. Two independent sources agree:

    * Matsushita, MN1030/MN103S instruction manual. The vector table example
      equates IVAR0..IVAR6 to 0x20000000..0x20000018 and stores each handler
      with movhu, commented "Set to lower 16 bits of entry point for level
      interrupt handler"; the nonmaskable handler is assembled at
      `org 0x40000008`; and the memory-layout chapter states that the one
      assignment common to every memory mode "is the location of the reset
      vector. It is always at 0x40000000."
    * GNU's mn10300 simulator, sim/mn10300/dv-mn103cpu.c, models the same
      block -- unsigned16 interrupt_vector[7] decoded at 0x000/0x004/.../0x018
      of a register block based at 0x20000000 -- and delivers a level
      interrupt to `0x40000000 + interrupt_vector[pending_level]`.

  So the core decodes the registers itself (its internal map already carries
  the INTC and SIO, and the manual's map puts 0x20000000-0x3FFFFFFF in the
  same on-chip peripheral region), and the machine supplies one address: the
  base its decode puts the vector at. That also makes the vector real save
  state -- m_level_vector was configuration and was deliberately not saved,
  so a save state taken on these machines restored a vector of whatever the
  config happened to set, never what the firmware had programmed.

  Measured, all five firmwares (notes/irq-vector-probes/): IVAR0..IVAR6 are
  written zero exactly once at boot and never again through any encoding, so
  one entry serves all seven levels and the emulated behaviour is unchanged.

RUN   python3 mn10300_ivar.py        (from the PR worktree root)
PASS  the driver builds; kn7000 still reaches its play screen.
"""

H = 'src/devices/cpu/mn10300/mn10300.h'
C = 'src/devices/cpu/mn10300/mn10300.cpp'
TARGET = 'src/mame/matsushita/kn7000.cpp'


def edit(path, pairs):
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        if old not in s:
            raise SystemExit('NOT FOUND in %s: %r' % (path, old[:70]))
        s = s.replace(old, new, 1)
    open(path, 'w').write(s)


# ---------------------------------------------------------------- CPU header
edit(H, [
("""\t// Per-level maskable vector table (see the delivery note above).
\tvoid set_maskable_vector(int level, uint32_t vector) { m_level_vector[level & 7] = vector; }
""",
 """\t// Where this board's decode puts the CPU's vector base (see ivar_w).
\tvoid set_vector_base(uint32_t base) { m_vector_base = base; }
"""),
("""\tuint32_t m_level_vector[8];  // per-level maskable vector (board-configured)
""",
 """\tuint16_t ivar_r(offs_t offset, uint16_t mem_mask = ~0);
\tvoid ivar_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);

\tuint16_t m_ivar[7] = { };    // IVAR0..IVAR6 @ 0x20000000 + level*4
\tuint32_t m_vector_base = 0x40000000;  // board decode; 0x40000000 architecturally
"""),
])

# ------------------------------------------------------------------- CPU .cpp
edit(C, [
# no longer a configuration array to clear
("""\tstd::fill(std::begin(m_level_vector), std::end(m_level_vector), 0);
""", ""),

# internal map: the CPU's own register block
("""// Internal address map: the on-chip INTC, SIO and TM4/TM5 timer blocks.
""",
 """// Internal address map: the interrupt vector registers, INTC, SIO and TM4/TM5.
"""),
("""// Flat 32-bit little-endian space with a 32-bit data bus. This decodes the
// on-chip peripherals -- the INTC (0x34000100-0x340002FF), the SIO
// (0x34000800-0x3400082F) and the TM4/TM5 timer windows (0x34001080/0x34001090/
// 0x340010A0, 4 bytes each) -- and the machine maps the rest.
void mn10300_device::mn103002a_internal_map(address_map &map)
{
""",
 """// Flat 32-bit little-endian space with a 32-bit data bus. This decodes the
// on-chip peripherals -- IVAR0-IVAR6 (0x20000000-0x2000001B), the INTC
// (0x34000100-0x340002FF), the SIO (0x34000800-0x3400082F) and the TM4/TM5
// timer windows (0x34001080/0x34001090/0x340010A0, 4 bytes each) -- and the
// machine maps the rest.
void mn10300_device::mn103002a_internal_map(address_map &map)
{
\tmap(0x20000000, 0x2000001b).rw(FUNC(mn10300_device::ivar_r), FUNC(mn10300_device::ivar_w));
"""),

# save state: the vector file is runtime state now
("""\t// (m_level_vector is machine configuration, not runtime state; m_tm5_timer
\t// is a device-allocated emu_timer and is save-stated automatically.)
""",
 """\tsave_item(NAME(m_ivar));
\t// (m_tm5_timer is a device-allocated emu_timer and is save-stated
\t// automatically.)
"""),

# the INTC block's closing note
("""// Vector delivery: the AM33 vectors each interrupt LEVEL through its own
// handler address. That mapping is board policy: the machine fills the
// per-level table with set_maskable_vector().
""",
 """// Vector delivery: each interrupt LEVEL carries its own handler address, in
// the IVAR register file below.
"""),

# arbitration sites
("""\t\tconst int level = (m_gxicr[g] >> 12) & 7;
\t\t// Vector selection is board policy: a per-level table the machine fills
\t\t// in (see intc_recompute for why the level split matters).
\t\tm_irq_vector = m_level_vector[level];
\t\tm_irq_level = level;
""",
 """\t\tconst int level = (m_gxicr[g] >> 12) & 7;
\t\tm_irq_vector = level_vector(level);
\t\tm_irq_level = level;
"""),
("""\t// The AM33 selects a maskable interrupt's vector per LEVEL, through the IVR
\t// register file. The machine supplies the resulting per-level table
\t// (set_maskable_vector); a system that programs every IVR alike fills it with
\t// one repeated entry.
\tconst int g = intc_pending_group();
\tif (g)
\t{
\t\tconst int level = (m_gxicr[g] >> 12) & 7;
\t\tm_irq_vector = m_level_vector[level];
\t\tm_irq_level = level;
\t}
""",
 """\tconst int g = intc_pending_group();
\tif (g)
\t{
\t\tconst int level = (m_gxicr[g] >> 12) & 7;
\t\tm_irq_vector = level_vector(level);
\t\tm_irq_level = level;
\t}
"""),
])

# The register block itself, inserted ahead of the INTC implementation. This is
# raw I/O rather than an edit() pair, so it is guarded: replay_polish.py harvests
# this script with open() stubbed out, and must reach the driver pairs below.
s = open(C, encoding='utf-8').read()
ANCHOR = """//**************************************************************************
//  on-chip interrupt controller (INTC) @ 0x34000100
//**************************************************************************"""
IVAR = """//**************************************************************************
//  interrupt vector registers (IVAR0-IVAR6) @ 0x20000000
//**************************************************************************
//
// Seven 16-bit registers, IVARn at 0x20000000 + n*4, one per maskable interrupt
// level: a level-n interrupt vectors to m_vector_base + IVAR[n], the register
// holding only the low 16 bits of the entry point. Reset enters at the base and
// a nonmaskable interrupt at base + 8. The upper half of each four-byte slot is
// unimplemented. Levels run 0 (highest priority) to 6; level 7 is the idle
// value of PSW.IM and has no register, and check_irq requires level < PSW.IM,
// so it is never delivered.
//
// The base is 0x40000000 on the parts the documentation covers, which is also
// where the reset vector always sits, so a board that boots from a ROM there
// gets a vector table at the bottom of its ROM. A machine whose decode differs
// says so with set_vector_base().

uint16_t mn10300_device::ivar_r(offs_t offset, uint16_t mem_mask)
{
\treturn (offset & 1) ? 0 : m_ivar[offset >> 1];
}

void mn10300_device::ivar_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
\tif (!(offset & 1))
\t\tCOMBINE_DATA(&m_ivar[offset >> 1]);
}

uint32_t mn10300_device::level_vector(int level) const
{
\treturn (level < 7) ? m_vector_base + m_ivar[level] : 0;
}


"""
if s:
    assert s.count(ANCHOR) == 1
    s = s.replace(ANCHOR, IVAR + ANCHOR, 1)
    open(C, 'w').write(s)

edit(H, [
("""\tuint16_t ivar_r(offs_t offset, uint16_t mem_mask = ~0);
""",
 """\tuint32_t level_vector(int level) const;   // m_vector_base + IVAR[level]
\tuint16_t ivar_r(offs_t offset, uint16_t mem_mask = ~0);
"""),
])

# -------------------------------------------------------------------- driver
edit(TARGET, [
("""// Every firmware builds its interrupt entry as a 6-byte `nop ; jmp handler` thunk
// at the base of work RAM, writing it through the 0x90000000 cache-through alias
// and computing the jump displacement for execution here. The MN103002 vectors a
// maskable interrupt of level L through IVR[L] at 0x20000000 + L*4, and all five
// firmwares write IVR0..IVR6 = 0 once at boot, so one entry serves all seven
// levels. The driver points the CPU at the thunk and the thunk supplies the
// handler.
constexpr offs_t IRQ_VECTOR_WINDOW = 0x50000000;
""",
 """// A maskable interrupt of level L vectors to <base> + IVAR[L]. Every firmware
// clears IVAR0..IVAR6 once at boot and builds a `nop ; jmp handler` thunk at the
// base of work RAM, computing the jump displacement for execution there -- so
// one entry serves all seven levels and the handler address stays the firmware's
// business. Nothing in the 4 MB image branches to the thunk, so it is reached
// from the vector; what decodes work RAM to the CPU's 0x40000000 vector base is
// a board question the available documentation does not answer.
constexpr offs_t IRQ_VECTOR_BASE = 0x50000000;
"""),
("""\t// One maskable vector serves every level: the firmware writes IVR0..IVR6 = 0
\t// and puts a jump to its handler in the vector window.
\tfor (int level = 0; level < 8; level++)
\t\tm_maincpu->set_maskable_vector(level, IRQ_VECTOR_WINDOW);
""",
 """\tm_maincpu->set_vector_base(IRQ_VECTOR_BASE);
"""),
("""\t// 0x90000000 is the cache-through alias of the work RAM at 0x50000000, the same
\t// one-bit window pair as 0x4C/0x8C and 0x44/0x84. The firmware writes code through
\t// it and executes it from the cached view: the interrupt vector thunk here, and the
\t// library at 0x8C000000/0x4C000000. The thunk builder computes its jump displacement
\t// against 0x50000001 -- the jmp's own address -- so the firmware itself asserts the
\t// two windows are the same storage.
""",
 """\t// External memory is visible twice: cachable at 0x40000000-0x7FFFFFFF and
\t// uncachable 0x40000000 above that, which is what the 0x50/0x90, 0x4C/0x8C and
\t// 0x44/0x84 pairs are. The firmware writes code through the uncachable view and
\t// executes it from the cachable one -- the interrupt vector thunk here, the
\t// library at 0x8C000000/0x4C000000.
"""),
])

print('mn10300_ivar: core + driver updated')
