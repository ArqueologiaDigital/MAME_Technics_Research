-- How far along the CPU 1 boot sequence at 0xF827C8 does the machine actually
-- get?  Each milestone below is a DATA access made by one identified step of
-- that sequence, so a read/write tap catches it (opcode fetches go through the
-- CPU cache and are NOT reliably tappable; data accesses are).
--
--   0x000080-0x000081  the tick counter the 0xF82804 wait loop polls
--                      (`cp (0x80),0x0384` / `jr C`) -- boot reached the wait
--   0x007620-0x007621  first word of checksum block 1 (routine 0xF82C80)
--   0x007fd0-0x007fd5  the checksum result flags + the two stored sums
--   0x617800-0x617801  first word of checksum block 2
--   0x790000-0x790001  the SED1330 status/data + data/command ports
--
-- Prints the first hit time for each, then a summary at 1 Hz.
_G.first, _G.count = {}, {}
_G.t0 = 0

local function note(tag)
	_G.count[tag] = (_G.count[tag] or 0) + 1
	if _G.first[tag] == nil then
		_G.first[tag] = manager.machine.time:as_double()
		print(string.format("MILESTONE %-10s first t=%.4f s  pc=%06X",
			tag, _G.first[tag],
			manager.machine.devices[":cpu1"].state["CURPC"].value))
	end
end

local sp = manager.machine.devices[":cpu1"].spaces["program"]
_G.taps = {}
local function watch(tag, lo, hi)
	_G.taps[#_G.taps+1] = sp:install_read_tap(lo, hi, "r_"..tag,
		function (offset, data, mask) note(tag.."/r") return data end)
	_G.taps[#_G.taps+1] = sp:install_write_tap(lo, hi, "w_"..tag,
		function (offset, data, mask) note(tag.."/w") return data end)
end

watch("tick",   0x000080, 0x000081)
watch("cksum1", 0x007620, 0x007621)
watch("flags",  0x007fd0, 0x007fd5)
watch("cksum2", 0x617800, 0x617801)
watch("LCD",    0x790000, 0x790001)

_G.n = 0
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.n = _G.n + 1
	if (_G.n % 60) ~= 0 then return end
	local s = ""
	for _, k in ipairs({"tick/r","cksum1/r","flags/r","flags/w","cksum2/r","LCD/r","LCD/w"}) do
		s = s .. string.format(" %s=%d", k, _G.count[k] or 0)
	end
	print(string.format("t=%5.1f%s  cpu1pc=%06X", manager.machine.time:as_double(), s,
		manager.machine.devices[":cpu1"].state["CURPC"].value))
end)
