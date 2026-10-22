-- sc1rx.lua -- every byte the main CPU reads from SC1BUF (0xD4) from RX_FROM seconds on, as SC1RX lines
-- (time, byte, PC), up to RX_MAX; to compare what the firmware receives for one button press.
local mac = manager.machine
local cpu = mac.devices[":maincpu"]
local mem = cpu.spaces["program"]
local FROM, MAX = tonumber(os.getenv("RX_FROM")) or 40, tonumber(os.getenv("RX_MAX")) or 200
_G.RX = { n = 0 }
_G.RX.tap = mem:install_read_tap(0xd4, 0xd5, "sc1rx", function(off, data, mask)
	local t = mac.time:as_double()
	if t < FROM or _G.RX.n >= MAX then return end
	local sh = (0xd4 - off) * 8
	if sh < 0 or sh > 8 or (mask >> sh) & 0xff == 0 then return end
	_G.RX.n = _G.RX.n + 1
	emu.print_error(string.format("SC1RX %.4f %02x pc=%06x", t, (data >> sh) & 0xff, cpu.state["PC"].value))
end)
