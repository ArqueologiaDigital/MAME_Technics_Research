-- subtick.lua -- the sub CPU's 32-bit audio tick counter (sub RAM 0x1040, Timer_AudioTick_Handler) and its PC,
-- every 0.5 s from ST_FROM: does the sub CPU still run at all?
local mac = manager.machine
local cpu = mac.devices[":subcpu"]
local sub = cpu.spaces["program"]
_G.ST = { next = tonumber(os.getenv("ST_FROM")) or 26 }
_G.ST.h = emu.add_machine_frame_notifier(function()
	local t = mac.time:as_double()
	if t < _G.ST.next then return end
	_G.ST.next = t + 0.5
	emu.print_error(string.format("SUBTICK %.1f tick=%d pc=%06x", t, sub:read_u32(0x1040), cpu.state["PC"].value))
end)
