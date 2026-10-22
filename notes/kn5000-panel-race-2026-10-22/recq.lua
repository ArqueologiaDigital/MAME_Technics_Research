-- recq.lua -- writes to the panel record queue at 0x8E94 (v8-v10: {event index, state, changed}) from REC_FROM s.
local mac = manager.machine
local cpu = mac.devices[":maincpu"]
local mem = cpu.spaces["program"]
local FROM = tonumber(os.getenv("REC_FROM")) or 24.9
_G.RQ = { n = 0 }
_G.RQ.tap = mem:install_write_tap(0x8e94, 0x8ecf, "recq", function(off, data, mask)
	local t = mac.time:as_double()
	if t < FROM or _G.RQ.n > 40 then return end
	_G.RQ.n = _G.RQ.n + 1
	emu.print_error(string.format("RECQ %.4f off=%06x data=%04x mask=%04x pc=%06x", t, off, data, mask, cpu.state["PC"].value))
end)
