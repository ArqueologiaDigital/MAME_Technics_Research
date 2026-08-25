-- QUESTION: with the machine idling on "ALL INITIAL SETTING!", can ANY single
-- panel position make the firmware REDRAW THE SCREEN?
--
-- wsa1_ui_blockers.lua measured that the LCD write count freezes at 33623 the
-- moment the message is painted (t~=75 s) and never moves again over the next
-- 120 emulated seconds, while CPU 1's main loop keeps turning at ~14,000
-- passes per second.  So the machine is idle, not wedged, and the question is
-- what input it is idle FOR.
--
-- The screen state lives in four bytes of CPU 1 RAM, from the dispatcher at
-- prom_a 0xF864FA / 0xF864B0:
--   (0x2078) current / (0x2079) requested  screen of family A, table 0xF86EC1,
--                                          48 entries, bound `cp L,0x2F`
--   (0x207C) current / (0x207D) requested  screen of family B, table 0xF86F41,
--                                          224 entries, bound `cp L,0xDF`
-- A transition is "current != requested"; the dispatcher then calls
-- table[old]+4 (leave) and table[new]+0 (enter).
--
-- So per press we report: LCD writes, SC1BUF writes (did the panel frame even
-- go out?), and all four screen bytes.  A press that changes ANY of them is a
-- press the firmware acted on.
--
-- Run:
--   cd ~/compartilhado/kn7000_mame_build
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 230 -window \
--       -autoboot_script .../wsa1_ui_press_sweep.lua

local START_S     = 30       -- with the prescaler fix the UI is up by t=25 s
local HOLD_FRAMES = 24
local GAP_FRAMES  = 24

_G.lcd, _G.sc1 = 0, 0
local m = manager.machine
_G.sp = m.devices[":cpu1"].spaces["program"]
_G.taps = {}
_G.taps[1] = _G.sp:install_write_tap(0x790000, 0x790001, "lcd",
	function (o, d, k) _G.lcd = _G.lcd + 1 return d end)
_G.taps[2] = _G.sp:install_write_tap(0x000054, 0x000055, "sc1",
	function (o, d, k) if (k & 0x00ff) ~= 0 then _G.sc1 = _G.sc1 + 1 end return d end)
-- ⚠ THE SC1BUF TAP ABOVE COUNTS TRANSMITS ONLY.  A button arrives on the
-- RECEIVE side, so two more signals are needed to tell "the firmware never saw
-- it" from "it saw it and had nothing to draw":
--   * SC1 state byte RAM 0x2A80 going to 0x20 -- only INT6_SC1_PeerRequest
--     (prom_b 0xF5AC0A) writes that value, so it counts INT6 dispatches;
--   * the panel's own button shadow at RAM 0x2B20..0x2B3F, which
--     SC1_RxOp0_ThreeByte (0xF5B0FD) XORs each received segment mask against.
_G.int6, _G.shadow = 0, 0
_G.taps[3] = _G.sp:install_write_tap(0x002a80, 0x002a81, "st",
	function (o, d, k) if (k & 0x00ff) ~= 0 and (d & 0xff) == 0x20 then
		_G.int6 = _G.int6 + 1 end return d end)
_G.taps[4] = _G.sp:install_write_tap(0x002b20, 0x002b3f, "shadow",
	function (o, d, k) _G.shadow = _G.shadow + 1 return d end)

local function scr()
	return string.format("%02X/%02X %02X/%02X",
		_G.sp:read_u8(0x2078), _G.sp:read_u8(0x2079),
		_G.sp:read_u8(0x207c), _G.sp:read_u8(0x207d))
end

_G.list = {}
for tag, port in pairs(m.ioport.ports) do
	if tag:find("CP_SEG") then
		for name, field in pairs(port.fields) do
			_G.list[#_G.list+1] = { tag = tag, name = name, field = field }
		end
	end
end
table.sort(_G.list, function (a, b)
	if a.tag == b.tag then return a.name < b.name end
	return a.tag < b.tag
end)
print(string.format("SWEEP: %d panel positions", #_G.list))

_G.idx, _G.phase, _G.timer = 0, "wait", 0
_G.baselcd, _G.basesc1, _G.basescr, _G.acted = 0, 0, "", 0
_G.sub = emu.add_machine_frame_notifier(function ()
	if m.time:as_double() < START_S then return end
	if _G.phase == "wait" then
		_G.idx = _G.idx + 1
		if _G.idx > #_G.list then
			if _G.phase ~= "done" then
				_G.phase = "done"
				print(string.format(
					"SWEEP COMPLETE: %d of %d presses changed the screen state or repainted",
					_G.acted, #_G.list))
			end
			return
		end
		local e = _G.list[_G.idx]
		_G.baselcd, _G.basesc1, _G.basescr = _G.lcd, _G.sc1, scr()
		_G.baseint6, _G.baseshadow = _G.int6, _G.shadow
		e.field:set_value(1)
		_G.phase, _G.timer = "hold", HOLD_FRAMES
	elseif _G.phase == "hold" then
		_G.timer = _G.timer - 1
		if _G.timer <= 0 then
			_G.list[_G.idx].field:set_value(0)
			_G.phase, _G.timer = "gap", GAP_FRAMES
		end
	elseif _G.phase == "gap" then
		_G.timer = _G.timer - 1
		if _G.timer <= 0 then
			local e = _G.list[_G.idx]
			local dl, ds, s = _G.lcd - _G.baselcd, _G.sc1 - _G.basesc1, scr()
			local di, dh = _G.int6 - _G.baseint6, _G.shadow - _G.baseshadow
			local changed = (dl ~= 0) or (s ~= _G.basescr) or (dh ~= 0)
			if changed then _G.acted = _G.acted + 1 end
			print(string.format(
				"PRESS t=%6.1f %-9s %-16s dLCD=%-6d dSC1=%-4d dINT6=%-3d dSHADOW=%-3d scr %s -> %s%s",
				m.time:as_double(), e.tag, e.name, dl, ds, di, dh, _G.basescr, s,
				changed and "   *** ACTED" or ""))
			if changed then m.video:snapshot() end
			_G.phase = "wait"
		end
	end
end)
