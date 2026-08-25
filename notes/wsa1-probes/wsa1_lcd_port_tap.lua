-- Is the SED1330 port at 0x790000/1 touched at all during boot?
-- Taps MUST be kept in globals or the GC silently removes them.
_G.hits = 0
local sp = manager.machine.devices[":cpu1"].spaces["program"]
_G.wtap = sp:install_write_tap(0x790000, 0x790001, "lcdw", function (offset, data, mask)
	_G.hits = _G.hits + 1
	if _G.hits <= 40 then
		print(string.format("LCDTAP w %06X = %04X mask %04X", offset, data, mask))
	end
	return data
end)
_G.rtap = sp:install_read_tap(0x790000, 0x790001, "lcdr", function (offset, data, mask)
	_G.hits = _G.hits + 1
	if _G.hits <= 40 then
		print(string.format("LCDTAP r %06X -> %04X mask %04X", offset, data, mask))
	end
	return data
end)
_G.n = 0
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.n = _G.n + 1
	if (_G.n % 60) == 0 then print(string.format("LCDTAP t=%ds total accesses = %d", _G.n // 60, _G.hits)) end
end)
