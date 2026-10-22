-- ringptr.lua -- the panel RX ring's write (0x8D9F) and read (0x8D9D) indices every 0.2 s from RP_FROM to RP_TO
-- (v8..v10 addresses; RINGPTR lines).
local mac = manager.machine
local mem = mac.devices[":maincpu"].spaces["program"]
local FROM, TO = tonumber(os.getenv("RP_FROM")) or 24.8, tonumber(os.getenv("RP_TO")) or 27
_G.RP = { next = FROM }
_G.RP.h = emu.add_machine_frame_notifier(function()
	local t = mac.time:as_double()
	if t < _G.RP.next or t > TO then return end
	_G.RP.next = t + 0.2
	emu.print_error(string.format("RINGPTR %.2f wr=%d rd=%d", t, mem:read_u16(0x8d9f), mem:read_u16(0x8d9d)))
end)
