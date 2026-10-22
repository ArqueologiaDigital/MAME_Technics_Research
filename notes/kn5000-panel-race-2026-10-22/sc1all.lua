-- sc1all.lua -- every SC1BUF (0xD4) write (TX) and read (RX) by the main CPU up to ALL_TO seconds, as SC1 lines
-- (time, direction, byte, PC), plus the RX ring's write index (0x8D9F, v8..v10) after each read.
local mac = manager.machine
local cpu = mac.devices[":maincpu"]
local mem = cpu.spaces["program"]
local TO = tonumber(os.getenv("ALL_TO")) or 22
_G.SA = {}
local function lane(off, mask) local sh = (0xd4 - off) * 8; if sh < 0 or sh > 8 or (mask >> sh) & 0xff == 0 then return nil end return sh end
_G.SA.r = mem:install_read_tap(0xd4, 0xd5, "sc1r", function(off, data, mask)
	local t = mac.time:as_double(); if t > TO then return end
	local sh = lane(off, mask); if not sh then return end
	emu.print_error(string.format("SC1 %.5f RX %02x pc=%06x", t, (data >> sh) & 0xff, cpu.state["PC"].value))
end)
_G.SA.w = mem:install_write_tap(0xd4, 0xd5, "sc1w", function(off, data, mask)
	local t = mac.time:as_double(); if t > TO then return end
	local sh = lane(off, mask); if not sh then return end
	emu.print_error(string.format("SC1 %.5f TX %02x pc=%06x", t, (data >> sh) & 0xff, cpu.state["PC"].value))
end)
