-- porta.lua -- writes to the main CPU's port A (bit 0 = the sub CPU's reset, low = held) from PA_FROM: PORTA lines.
local mac = manager.machine
local cpu = mac.devices[":maincpu"]
local mem = cpu.spaces["program"]
local A = tonumber(os.getenv("PA_ADDR") or "28", 16)
_G.PA = { n = 0 }
_G.PA.tap = mem:install_write_tap(A & ~1, A | 1, "pa", function(off, data, mask)
	if mac.time:as_double() < (tonumber(os.getenv("PA_FROM")) or 20) or _G.PA.n > 20 then return end
	local sh = (A - off) * 8
	if (mask >> sh) & 0xff == 0 then return end
	_G.PA.n = _G.PA.n + 1
	emu.print_error(string.format("PORTA %.5f %02x pc=%06x", mac.time:as_double(), (data >> sh) & 0xff, cpu.state["PC"].value))
end)
