-- Is CPU 1's millisecond tick counter at RAM 0x0080 actually ADVANCING?
--
-- prom_b's delay family (0xF5AA62 / 0xF5AA79 / 0xF5AA90) all work the same way:
-- snapshot the word at 0x0080 into 0x2A8E, then poll 0x0080 until it has moved
-- by 2, 6 or 0x33 ticks.  If 0x0080 never advances, every one of those delays
-- is an INFINITE loop, and boot stops at whichever one it reached first.
--
-- Signal: the "val" column.  Advancing => the timer interrupt is running.
-- Pinned => the tick source is dead and the delay can never retire.
_G.wr = 0
local sp = manager.machine.devices[":cpu1"].spaces["program"]
_G.tap = sp:install_write_tap(0x000080, 0x000081, "tickw",
	function (offset, data, mask) _G.wr = _G.wr + 1 return data end)

_G.n = 0
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.n = _G.n + 1
	if (_G.n % 30) ~= 0 then return end
	print(string.format("t=%6.2f  (0x80)=%5d  writes=%d  cpu1pc=%06X",
		manager.machine.time:as_double(),
		sp:read_u16(0x000080), _G.wr,
		manager.machine.devices[":cpu1"].state["CURPC"].value))
end)
