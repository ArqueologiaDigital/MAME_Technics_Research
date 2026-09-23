"""0x90000000 is the work RAM's cache-through alias, not an LCD window.

QUESTION IT ANSWERS
  "What is the 0x90000000 window, and is the driver's map of it defensible?"

  It is the +0x40000000 cache-through view of the work RAM at 0x50000000. The
  firmware asserts that itself: the interrupt-thunk builder writes the thunk
  through 0x90000000 and computes the jump displacement against 0x50000001 --
  the jmp's own address -- which is correct at exactly one execution address.

  Three things were wrong, all measured (notes/pr-review-probes-2026-09-23/):

  1. The comment called it "LCD controller window (regs + trampolines)". The LCD
     is at 0x98xxxxxx/0x9Cxxxxxx and the driver maps it separately. Across all
     five images the only values in this window a real instruction dereferences
     are the two thunks, a 0x5AA5 warm-boot flag at +0x0E, and a clear of work
     RAM's exact 4 MiB extent from +0x10. The other 26 values with a 0x90 top
     byte -- bit-identical across three unrelated firmwares -- are loaded into
     data registers and passed as call arguments. ID constants, never addresses.

  2. The alias was applied to KN2400/KN2600 only. The thunk builder is
     byte-identical in all five firmwares, down to the same 0x50000001. What
     differs is only where each firmware's handler happens to live: the KN2400's
     is in work RAM, so its jump target had to resolve and the alias was added;
     the others' handlers are in the library region, whose 0x4C/0x8C mirror the
     driver already had for the self-load and which caught the jump by accident.

  3. The 128 MiB .ram().share("vram") is read by nothing (grep -c vram = 1) and
     swallows the picture flash at 0x97800000 that the driver's own comment says
     is left unmapped.

  With the alias unconditional, the vector can point at the CACHED base the
  firmware's arithmetic names, so every handler is reached at its literal
  address instead of at +0x40000000 -- and the second thunk stops being a jump
  into unmapped space (kn7000 0x484D77CF -> 0x884D77CF is not mapped today;
  latent only because the driver never asserts NMI).

RUN   python3 fix_memory_window.py       (from the PR worktree root)
PASS  prints "ok"; then every machine must still reach its play screen -- this
      change is behaviour-visible and the LCD pixel count is the gate.
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


edit('src/mame/matsushita/kn7000.cpp', [
("""	map(0x90000000, 0x97ffffff).ram().share("vram");   // LCD controller window (regs + trampolines)
	// KN2400/KN2600: 0x90000000..0x903fffff is the +0x40000000 write/execute ALIAS of the
	// 0x50000000 work RAM, the same one-bit window pair as 0x4C/0x8C and 0x44/0x84.
	if (m_ram90_workram)
		map(0x90000000, 0x903fffff).ram().share("workram");
""",
 """	// 0x90000000 is the cache-through alias of the work RAM at 0x50000000, the same
	// one-bit window pair as 0x4C/0x8C and 0x44/0x84. The firmware writes code through
	// it and executes it from the cached view: the interrupt vector thunk here, and the
	// library at 0x8C000000/0x4C000000. The thunk builder computes its jump displacement
	// against 0x50000001 -- the jmp's own address -- so the firmware itself asserts the
	// two windows are the same storage.
	map(0x90000000, 0x903fffff).ram().share("workram");
"""),
("""constexpr offs_t IRQ_VECTOR_WINDOW = 0x90000000;
""",
 """constexpr offs_t IRQ_VECTOR_WINDOW = 0x50000000;
"""),
# the window comment above it names the cached view now
("""// Every firmware here builds its interrupt entry as a 6-byte `nop ; jmp handler`
// thunk at the base of this window, with the jump displacement computed against
// the thunk's own execution address. The MN103002 vectors a maskable interrupt of
// level L through IVR[L] at 0x20000000 + L*4, and all of them write IVR0..IVR6 = 0
// once at boot, so one entry serves all seven levels. The driver therefore points
// the CPU at the window and the thunk supplies the handler.
""",
 """// Every firmware builds its interrupt entry as a 6-byte `nop ; jmp handler` thunk
// at the base of work RAM, writing it through the 0x90000000 cache-through alias
// and computing the jump displacement for execution here. The MN103002 vectors a
// maskable interrupt of level L through IVR[L] at 0x20000000 + L*4, and all five
// firmwares write IVR0..IVR6 = 0 once at boot, so one entry serves all seven
// levels. The driver points the CPU at the thunk and the thunk supplies the
// handler.
"""),
])
print('ok')


# the per-model flag has no user now: the alias is unconditional
edit('src/mame/matsushita/kn7000.cpp', [
("""	bool m_ram90_workram = false;                // KN2400/KN2600: 0x90000000 = +0x40000000 alias of work RAM (library self-loads via it)
""", ""),
("""	m_ram90_workram = true;
""", ""),
])
print('ok (flag removed)')
