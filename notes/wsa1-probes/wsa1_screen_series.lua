-- What does the panel show as the boot proceeds?  Takes a snapshot every 15
-- emulated seconds (into snap/wsa1r/) and prints the LCD write count with it,
-- so a still frame can be told apart from a screen that is still being drawn.
_G.w, _G.r = 0, 0
local sp = manager.machine.devices[":cpu1"].spaces["program"]
_G.tw = sp:install_write_tap(0x790000, 0x790001, "lcdw",
	function (o, d, m) _G.w = _G.w + 1 return d end)
_G.tr = sp:install_read_tap(0x790000, 0x790001, "lcdr",
	function (o, d, m) _G.r = _G.r + 1 return d end)

_G.n, _G.shots = 0, 0
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.n = _G.n + 1
	if (_G.n % 900) ~= 0 then return end          -- 15 s at 60 fps
	_G.shots = _G.shots + 1
	manager.machine.video:snapshot()
	print(string.format("SHOT %d  t=%6.1f  lcd_w=%d lcd_r=%d  cpu1pc=%06X",
		_G.shots, manager.machine.time:as_double(), _G.w, _G.r,
		manager.machine.devices[":cpu1"].state["CURPC"].value))
end)
