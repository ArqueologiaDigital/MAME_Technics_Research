-- Is the inter-processor link carrying anything, and does a key press add to it?
--
-- The driver models the link as a one-byte latch in each direction:
--   CPU 1 writes 0x007C0000 -> CPU 2's INT0;  CPU 2 writes 0x00100000 -> CPU 1's.
-- KeyEvents_ToLink (prom_c 0xF98CB9) is supposed to push { 0x90, note, velocity }
-- to CPU 1 on channel 5, i.e. header (5 << 5) | (3 - 1) = 0xA2 followed by three
-- bytes, whenever the key scanner yields an event.
--
-- Signal: the running byte counts.  If tx stays at 0 for the whole boot, CPU 2
-- never sends at all and the fault is upstream of the keybed; if tx moves during
-- boot but not after a press, the fault is in KeyEvents_ToLink's send path.
_G.tx, _G.rx = 0, 0
_G.txlog, _G.rxlog = {}, {}
_G.mark = false

local cpu2 = manager.machine.devices[":cpu2"].spaces["program"]
local cpu1 = manager.machine.devices[":cpu1"].spaces["program"]

_G.t_tx = cpu2:install_write_tap(0x100000, 0x100001, "linkout", function (offset, data, mask)
	_G.tx = _G.tx + 1
	if _G.mark and #_G.txlog < 40 then _G.txlog[#_G.txlog + 1] = data & 0xff end
	return data
end)
_G.t_rx = cpu1:install_write_tap(0x7c0000, 0x7c0001, "linkin", function (offset, data, mask)
	_G.rx = _G.rx + 1
	if _G.mark and #_G.rxlog < 40 then _G.rxlog[#_G.rxlog + 1] = data & 0xff end
	return data
end)

local function hexlist(t)
	local s = {}
	for i = 1, #t do s[#s + 1] = string.format("%02X", t[i]) end
	return table.concat(s, " ")
end

_G.key = manager.machine.ioport.ports[":KEY2"].fields["C4"]
_G.p, _G.r = false, false
_G.n = 0
_G.sub = emu.add_machine_frame_notifier(function ()
	local t = manager.machine.time:as_double()
	if not _G.p and t >= 78.0 then
		_G.mark = true; _G.key:set_value(1); _G.p = true
		print(string.format("t=%6.2f  ---- C4 PRESSED; tx=%d rx=%d so far ----", t, _G.tx, _G.rx))
	end
	if not _G.r and t >= 80.0 then _G.key:set_value(0); _G.r = true end

	_G.n = _G.n + 1
	if (_G.n % 60) ~= 0 then return end
	print(string.format("t=%6.2f  cpu2->cpu1 bytes=%d  cpu1->cpu2 bytes=%d", t, _G.tx, _G.rx))
	if _G.mark then
		print("          after press, cpu2->cpu1: " .. hexlist(_G.txlog))
		print("          after press, cpu1->cpu2: " .. hexlist(_G.rxlog))
	end
end)
