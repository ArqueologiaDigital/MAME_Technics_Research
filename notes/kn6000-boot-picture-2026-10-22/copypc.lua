-- copypc.lua: for table-ROM reads between 2.8 s and 3.7 s, log each distinct (PC, 256-byte block) the first
-- time it occurs, with the time, to find the boot picture copy and what it read before it.
local mac  = manager.machine
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
local function now() return mac.time.seconds + mac.time.attoseconds / 1e18 end
_G.CP = { seen = {}, n = 0 }
_G.CP.tap = prog:install_read_tap(0x48000000, 0x483fffff, "copypc", function(offset, data, mask)
	local t = now()
	if t < 2.2 or t > 3.7 then return nil end
	local pc = cpu.state["PC"].value
	local key = string.format("%08x %08x", pc, offset & 0xffffff00)
	if not _G.CP.seen[key] and _G.CP.n < 400 then
		_G.CP.seen[key] = true; _G.CP.n = _G.CP.n + 1
		emu.print_error(string.format("CP %.4f pc=%08x off=%08x data=%08x mask=%08x", t, pc, offset, data, mask))
	end
	return nil
end)
_G.CP.h = emu.add_machine_frame_notifier(function() if now() > 3.8 then mac:exit() end end)
