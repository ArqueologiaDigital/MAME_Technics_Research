"""Size the 21065L's internal data region from what the program uses.

QUESTION IT ANSWERS
  "How big is this part's internal data memory?"

  An earlier pass in this session answered it from an assumed geometry -- the
  part's documented internal window is 0x8000-0xFFFF, so the map was shrunk to
  0x09000-0x0FFFF. That was wrong, and wrong in a way nothing cheap catches: the
  file still compiles, all fifteen commits still build, all five machines still
  boot and -validate still passes. Only playing a note shows it, because the
  effect kernel's working data lands in the part that was unmapped and the DSP
  then produces silence.

  Measured instead, from one run with a chord held (notes/dsp-frame-budget/):
  1642 distinct unmapped addresses in 0x10000-0x1FFFF, 886,587 writes. The
  highest the kernel reaches is 0x1FFE6. So the region is 0x09000-0x1FFFF, and
  that is where it was before.

  Still open, and NOT this change: the kernel also makes 1,566,833 accesses to
  0x42A9 and 19,619 to 0x434B, both below 0x08000 and unmapped in every version
  of this device. Pre-existing, recorded, not diagnosed.

RUN   python3 sharc_sram_extent.py     (from the PR worktree root)
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


edit('src/devices/cpu/sharc/sharc.cpp', [
    ("	map(0x09000, 0x0ffff).rw(FUNC(adsp21065l_device::pm_data_r), FUNC(adsp21065l_device::pm_data_w));",
     "	map(0x09000, 0x1ffff).rw(FUNC(adsp21065l_device::pm_data_r), FUNC(adsp21065l_device::pm_data_w));"),
    ("	map(0x09000, 0x0ffff).rw(FUNC(adsp21065l_device::dm_data_r), FUNC(adsp21065l_device::dm_data_w));",
     "	map(0x09000, 0x1ffff).rw(FUNC(adsp21065l_device::dm_data_r), FUNC(adsp21065l_device::dm_data_w));"),
])
edit('src/devices/cpu/sharc/sharc.h', [
    ("""	// The part's internal memory window is 0x08000-0x0FFFF; 0x20000 up is external.
	static constexpr offs_t DATA_SRAM_WORDS = 0x0ffff - 0x09000 + 1;""",
     """	// Sized from what the uploaded program actually reaches (0x1FFE6), not from an
	// assumed geometry. 0x20000 up is external memory and belongs to the board.
	static constexpr offs_t DATA_SRAM_WORDS = 0x1ffff - 0x09000 + 1;"""),
])
print('ok')
