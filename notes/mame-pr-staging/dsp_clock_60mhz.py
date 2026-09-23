"""Run the effects DSP at the speed grade printed on the part.

QUESTION IT ANSWERS
  "Is the DSP clock the hardware's figure, or a number chosen to make the
   emulation keep up?"

  IC306 is marked S21065LKS240. The KS-240 grade is 60 MHz core / 240 MFLOPS,
  and the board's X301 is ~30 MHz doubled. 66 MHz had been set so the effects
  kernel completed 44,100 frames per second -- a frame-budget threshold, not a
  rating -- and the comment two lines above still said 60, so the file
  contradicted itself.

RUN   python3 dsp_clock_60mhz.py      (from the PR worktree root)
PASS  prints "ok".
"""


def edit(path, pairs):
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        assert old in s, '%s MISSING: %r' % (path, old[:90])
        s = s.replace(old, new, 1)
    open(path, 'w').write(s)
    print('rewrote', path)


edit('src/mame/matsushita/kn7000.cpp', [
("""	// IC306 effects DSP -- Analog Devices ADSP-21065L SHARC (part S21065LKS240, ~60 MHz),
	// host-booted by the MN10300 over the 0x98000000 (index) / 0x9C000000 (data) port.
	ADSP21065L(config, m_dsp, 66'000'000);   // IC306, rated and run at 66 MHz
""",
 """	// IC306 effects DSP -- Analog Devices ADSP-21065L SHARC, host-booted by the
	// MN10300 over the 0x98000000 (index) / 0x9C000000 (data) port. The part is
	// marked S21065LKS240: the KS-240 grade is 60 MHz core, 240 MFLOPS.
	ADSP21065L(config, m_dsp, 60'000'000);
"""),
])
print('ok')
