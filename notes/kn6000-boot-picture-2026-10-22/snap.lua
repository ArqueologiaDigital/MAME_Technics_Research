-- snap.lua: save a snapshot every 0.1 s of emulated time for the first 12 s
local last = -1
emu.register_frame_done(function()
	local t = manager.machine.time:as_double()
	local slot = math.floor(t * 10)
	if slot ~= last and t < 12.0 then
		last = slot
		manager.machine.video:snapshot()
	end
	if t >= 12.2 then manager.machine:exit() end
end)
