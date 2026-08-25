-- CPU 1 sits in prom_b's 51-tick delay (0xF5AA90) while the tick counter runs
-- far past 51, so the delay must be RE-ENTERED by a caller that keeps retrying.
-- Two measurements settle it:
--
--  (a) every entry to a delay routine writes the snapshot word 0x2A8E, so
--      counting writes to 0x2A8E counts ENTRIES.  A rising count = a retry
--      loop; a count of 1 = one delay that genuinely never retires.
--  (b) a per-frame PC histogram with the delay's own instructions
--      (0xF5AA62-0xF5AAA8) excluded, which shows WHERE the retry loop lives.
_G.entries, _G.hist = 0, {}
local sp = manager.machine.devices[":cpu1"].spaces["program"]
_G.tap = sp:install_write_tap(0x002a8e, 0x002a8f, "snap",
	function (offset, data, mask) _G.entries = _G.entries + 1 return data end)

_G.n = 0
_G.sub = emu.add_machine_frame_notifier(function ()
	local pc = manager.machine.devices[":cpu1"].state["CURPC"].value
	if pc < 0xF5AA62 or pc > 0xF5AAA8 then          -- outside the delay itself
		_G.hist[pc] = (_G.hist[pc] or 0) + 1
	end
	_G.n = _G.n + 1
	if (_G.n % 120) ~= 0 then return end
	local a = {}
	for k, v in pairs(_G.hist) do a[#a+1] = {k, v} end
	table.sort(a, function (x, y) return x[2] > y[2] end)
	local s = ""
	for i = 1, math.min(8, #a) do s = s .. string.format(" %06X:%d", a[i][1], a[i][2]) end
	print(string.format("t=%5.1f delay_entries=%d  non-delay PCs:%s",
		manager.machine.time:as_double(), _G.entries, s))
end)
