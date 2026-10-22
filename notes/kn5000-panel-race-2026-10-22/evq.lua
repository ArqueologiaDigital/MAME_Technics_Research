-- evq.lua -- log every write to the KN5000 firmware's panel event queue (16 x 4 bytes at 0xC039, written by
-- PanelEvent_Post, the same code and address in v9 and v10) and to its count (0x8E8E), from EV_FROM seconds.
local mac = manager.machine
local cpu = mac.devices[":maincpu"]
local mem = cpu.spaces["program"]
local FROM = tonumber(os.getenv("EV_FROM")) or 24
_G.EQ = { n = 0 }
_G.EQ.tap = mem:install_write_tap(0xc038, 0xc079, "evq", function(off, data, mask)
	local t = mac.time:as_double()
	if t < FROM or _G.EQ.n > 200 then return end
	if off == 0xc038 and mask == 0xff00 and (data & 0xff00) == 0xff00 then return end	-- the idle 0xFF marker
	_G.EQ.n = _G.EQ.n + 1
	emu.print_error(string.format("EVQ %.4f off=%06x data=%04x mask=%04x pc=%06x", t, off, data, mask, cpu.state["PC"].value))
end)
