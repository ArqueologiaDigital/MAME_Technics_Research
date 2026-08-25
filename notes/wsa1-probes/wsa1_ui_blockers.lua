-- "What stands between ALL INITIAL SETTING! and a real user interface?"
--
-- One probe, five questions, so that a single long run answers all of them and
-- the answers are all from the SAME run:
--
--  1. WHERE does each processor spend its time?  60 Hz CURPC histogram, both
--     CPUs, printed cumulatively every 20 emulated seconds and once at the end.
--  2. IS the "ALL INITIAL SETTING!" screen being REDRAWN, or drawn once?
--     The string is prom_a ROM 0xF9422C..0xF9423F and only ShowAllInitialSetting
--     (0xF94210) points SWI7 service 8 at it, so counting data reads of those
--     bytes counts renders of that message.
--  3. IS CPU 1's MAIN LOOP turning?  0xF8203F is `tset 0,(0x98)`, executed once
--     per pass of the polled main loop at 0xF82028, and a `tset` WRITES.
--  4. DO the two defects under test show up?  (0x0080) is the 8-bit-timer tick
--     the whole firmware is written against; SFR 0x30-0x33 / 0x75 are TREG4/5
--     and INTET54, i.e. the 16-bit sequencer timer whose interrupt MAME never
--     raises.  Both are reported as counts and last values, never faked.
--  5. IS anything else moving?  LCD port, both link directions, CPU 2's key-scan
--     poll, CPU 2's tone-generator writes.
--
-- Run:
--   cd ~/compartilhado/kn7000_mame_build
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 200 -window \
--       -autoboot_script .../wsa1_ui_blockers.lua
--
-- MAME's Lua GC collects taps and notifiers that are not held in a global, so
-- everything here lives in _G.
_G.h1, _G.h2, _G.n = {}, {}, 0
_G.c = setmetatable({}, {__index = function () return 0 end})

local m   = manager.machine
local sp1 = m.devices[":cpu1"].spaces["program"]
local sp2 = m.devices[":cpu2"].spaces["program"]
_G.taps = {}

local function tap(sp, lo, hi, tag, rw)
	if rw ~= "w" then
		_G.taps[#_G.taps+1] = sp:install_read_tap(lo, hi, "r"..tag,
			function (o, d, k) _G.c[tag.."/r"] = _G.c[tag.."/r"] + 1 return d end)
	end
	if rw ~= "r" then
		_G.taps[#_G.taps+1] = sp:install_write_tap(lo, hi, "w"..tag,
			function (o, d, k) _G.c[tag.."/w"] = _G.c[tag.."/w"] + 1
				_G.last[tag] = d return d end)
	end
end
_G.last = {}

-- 2. the message string in prom_a ROM (CPU 1 program space)
tap(sp1, 0xf9422c, 0xf9423f, "msg", "r")
-- 3. the main loop's own tset
tap(sp1, 0x000098, 0x000099, "mainloop", "w")
-- 4a. the 8-bit timer tick counter
tap(sp1, 0x000080, 0x000081, "tick", "w")
-- 4b. the 16-bit sequencer timer's registers, both CPUs
tap(sp1, 0x000030, 0x000033, "treg45", "w")
tap(sp1, 0x000074, 0x000075, "intet54", "w")
tap(sp2, 0x000030, 0x000033, "c2treg45", "w")
-- 4c. interrupt DISPATCHES, counted at the vector fetch: the CPU reads the
--     4-byte vector out of prom_a on every dispatch, so a read tap on the slot
--     counts them.  0xFFFF44 INTT1, 0xFFFF4C INTT3, 0xFFFF50 INTTR4 (the
--     sequencer clock MAME could not raise before the 16-bit-timer fix).
tap(sp1, 0xffff44, 0xffff47, "intt1", "r")
tap(sp1, 0xffff4c, 0xffff4f, "intt3", "r")
tap(sp1, 0xffff50, 0xffff53, "inttr4", "r")
-- 5. the rest
tap(sp1, 0x790000, 0x790001, "lcd", "w")
tap(sp1, 0x7c0000, 0x7c0001, "link12", "w")
tap(sp2, 0x100000, 0x100001, "link21", "w")
tap(sp2, 0x108002, 0x108003, "keyscan", "r")
tap(sp2, 0x10c000, 0x10c001, "tg", "w")

local function top(h, tag, k)
	local a = {}
	for pc, v in pairs(h) do a[#a+1] = {pc, v} end
	table.sort(a, function (x, y) return x[2] > y[2] end)
	local s = ""
	for i = 1, math.min(k, #a) do s = s .. string.format(" %06X:%d", a[i][1], a[i][2]) end
	print("PC " .. tag .. s)
end

_G.sub = emu.add_machine_frame_notifier(function ()
	local p1 = m.devices[":cpu1"].state["CURPC"].value
	local p2 = m.devices[":cpu2"].state["CURPC"].value
	_G.h1[p1] = (_G.h1[p1] or 0) + 1
	_G.h2[p2] = (_G.h2[p2] or 0) + 1
	_G.n = _G.n + 1
	if (_G.n % 300) ~= 0 then return end   -- report every 5 emulated seconds
	print(string.format(
		"=== t=%6.1f  (0x0080)=%d (0x0097)=%02X (0x7FD1)=%02X  "
		.. "scrA %02X/%02X scrB %02X/%02X  samples=%d",
		m.time:as_double(), sp1:read_u16(0x80), sp1:read_u8(0x97),
		sp1:read_u8(0x7fd1),
		sp1:read_u8(0x2078), sp1:read_u8(0x2079),
		sp1:read_u8(0x207c), sp1:read_u8(0x207d), _G.n))
	local s = ""
	for _, k in ipairs({"msg/r","mainloop/w","tick/w","treg45/w","intet54/w",
	                    "intt1/r","intt3/r","inttr4/r",
	                    "c2treg45/w","lcd/w","link12/w","link21/w","keyscan/r","tg/w"}) do
		s = s .. string.format(" %s=%d", k, _G.c[k])
	end
	print("CNT" .. s)
	top(_G.h1, "cpu1", 8)
	top(_G.h2, "cpu2", 8)
end)

_G.stop = emu.add_machine_stop_notifier(function ()
	print("=== FINAL")
	top(_G.h1, "cpu1", 25)
	top(_G.h2, "cpu2", 25)
end)
