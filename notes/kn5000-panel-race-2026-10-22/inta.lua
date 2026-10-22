-- inta.lua -- between IN_FROM and IN_TO seconds: each SC1BUF access with the CPU's interrupt mask (CURFLAGS = SR, bits 14:12)
-- and INTEAB, and each INTA service (the handler's first instruction clears 0x8D98, v8..v10), as INTA lines.
local mac = manager.machine
local cpu = mac.devices[":maincpu"]
local mem = cpu.spaces["program"]
local FROM, TO = tonumber(os.getenv("IN_FROM")), tonumber(os.getenv("IN_TO"))
local function on() local t = mac.time:as_double(); return t >= FROM and t <= TO, t end
local function st() local sr = cpu.state["CURFLAGS"].value; return string.format("iff=%d inteab=%02x pc=%06x", (sr >> 12) & 7, mem:read_u8(0xe3), cpu.state["PC"].value) end
_G.IN = {}
_G.IN.w = mem:install_write_tap(0xd4, 0xd5, "in_w", function(off, data, mask)
	local ok, t = on(); if not ok or (mask & 0x00ff) == 0 then return end
	emu.print_error(string.format("INTA %.6f TX %02x %s", t, data & 0xff, st()))
end)
_G.IN.r = mem:install_read_tap(0xd4, 0xd5, "in_r", function(off, data, mask)
	local ok, t = on(); if not ok or (mask & 0x00ff) == 0 then return end
	emu.print_error(string.format("INTA %.6f RX %02x %s", t, data & 0xff, st()))
end)
_G.IN.s = mem:install_write_tap(0x8d98, 0x8d99, "in_s", function(off, data, mask)
	local ok, t = on(); if not ok then return end
	emu.print_error(string.format("INTA %.6f SERVICE %s", t, st()))
end)
