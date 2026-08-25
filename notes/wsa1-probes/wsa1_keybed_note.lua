-- Does a key press on the emulated keybed reach the firmware, and how far?
--
-- Presses middle C (ioport KEY2 bit 0, key 24, MIDI 60) at t = 78 s of emulated
-- time and releases it at t = 80 s, then reports every stage of the chain the
-- disassembly describes:
--
--   1. the scanner port at 0x00108000 hands CPU 2 a 16-bit event
--      (high byte = touch, low byte = bit 7 note-on | key number)
--   2. KeyEvents_ToLink (0xF98CB9) packs it as { 0x90, note, velocity } and
--      pushes it to CPU 1 on link channel 5 -- header (5 << 5) | (len - 1)
--   3. CPU 1 answers on link channel 0, which feeds CPU 2's ring at 0x00E2F1
--   4. MidiIn_ParseRingAndDispatch -> MidiNote_Dispatch -> the two 64-channel
--      parameter devices at 0x00104000 and 0x0010C000
--
-- Signal: ev / link5 / rx / tg all move after the press and not before.
-- Boot must have reached CPU 2's MAIN first, which is about t = 70 s here, so
-- run with -str 90 or more.
_G.ev, _G.tg, _G.dev104 = {}, 0, 0
_G.tx, _G.rx = {}, {}
_G.pressed = false

local cpu2 = manager.machine.devices[":cpu2"].spaces["program"]
local cpu1 = manager.machine.devices[":cpu1"].spaces["program"]

_G.t_ev = cpu2:install_read_tap(0x108000, 0x108001, "kbev", function (offset, data, mask)
	if data ~= 0 then _G.ev[#_G.ev + 1] = data end
	return data
end)
_G.t_tg = cpu2:install_write_tap(0x10c000, 0x10c003, "tgw", function (offset, data, mask)
	_G.tg = _G.tg + 1 return data
end)
_G.t_104 = cpu2:install_write_tap(0x104000, 0x104003, "d104w", function (offset, data, mask)
	_G.dev104 = _G.dev104 + 1 return data
end)
-- CPU 2 -> CPU 1 and CPU 1 -> CPU 2, one byte per access on the low lane.
_G.t_tx = cpu2:install_write_tap(0x100000, 0x100001, "linkout", function (offset, data, mask)
	if _G.pressed and #_G.tx < 24 then _G.tx[#_G.tx + 1] = data & 0xff end
	return data
end)
_G.t_rx = cpu1:install_write_tap(0x7c0000, 0x7c0001, "linkin", function (offset, data, mask)
	if _G.pressed and #_G.rx < 24 then _G.rx[#_G.rx + 1] = data & 0xff end
	return data
end)

local function hexlist(t)
	local s = {}
	for i = 1, #t do s[#s + 1] = string.format("%02X", t[i]) end
	return table.concat(s, " ")
end

_G.key = manager.machine.ioport.ports[":KEY2"].fields["C4"]
_G.done_press, _G.done_release = false, false

_G.n = 0
_G.sub = emu.add_machine_frame_notifier(function ()
	local t = manager.machine.time:as_double()

	if not _G.done_press and t >= 78.0 then
		_G.pressed = true
		_G.key:set_value(1)
		_G.done_press = true
		print(string.format("t=%6.2f  ---- C4 PRESSED (key 24, MIDI 60) ----", t))
		print(string.format("t=%6.2f  before: tg=%d dev104=%d events=%d", t, _G.tg, _G.dev104, #_G.ev))
	end
	if not _G.done_release and t >= 80.0 then
		_G.key:set_value(0)
		_G.done_release = true
		print(string.format("t=%6.2f  ---- C4 RELEASED ----", t))
	end

	_G.n = _G.n + 1
	if (_G.n % 60) ~= 0 then return end
	print(string.format("t=%6.2f  events=%d last=%s  tg=%d dev104=%d",
		t, #_G.ev,
		(#_G.ev > 0) and string.format("0x%04X", _G.ev[#_G.ev]) or "-",
		_G.tg, _G.dev104))
	if _G.pressed then
		print(string.format("          cpu2->cpu1: %s", hexlist(_G.tx)))
		print(string.format("          cpu1->cpu2: %s", hexlist(_G.rx)))
	end
end)
