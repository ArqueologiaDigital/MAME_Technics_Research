-- ringptr.lua -- the panel RX ring's write and read indices every RP_STEP (0.2) s from RP_FROM to RP_TO
-- (RINGPTR lines). RP_WR / RP_RD (hex) default to v8..v10's 0x8D9F / 0x8D9D; v7 0x8D03 / 0x8D01;
-- v5, v6 0x8CDF / 0x8CDD (each version's receive code, found by its bytes).
local mac = manager.machine
local mem = mac.devices[":maincpu"].spaces["program"]
local FROM, TO = tonumber(os.getenv("RP_FROM")) or 24.8, tonumber(os.getenv("RP_TO")) or 27
local WR, RD = tonumber(os.getenv("RP_WR") or "8d9f", 16), tonumber(os.getenv("RP_RD") or "8d9d", 16)
local STEP = tonumber(os.getenv("RP_STEP")) or 0.2
_G.RP = { next = FROM }
_G.RP.h = emu.add_machine_frame_notifier(function()
	local t = mac.time:as_double()
	if t < _G.RP.next or t > TO then return end
	_G.RP.next = t + STEP
	emu.print_error(string.format("RINGPTR %.2f wr=%d rd=%d", t, mem:read_u16(WR), mem:read_u16(RD)))
end)
