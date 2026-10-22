-- tgseq.lua -- every tone-generator write by the KN5000 sub CPU (0x100000-0x100003) from TG_FROM seconds to
-- TG_TO, written as "offset data" lines (no times) to TG_OUT, to compare two runs' note streams in order.
local mac = manager.machine
local sub = mac.devices[":subcpu"].spaces["program"]
local FROM, TO = tonumber(os.getenv("TG_FROM")) or 0, tonumber(os.getenv("TG_TO")) or 1e9
local f = io.open(os.getenv("TG_OUT"), "w")
_G.TS = { n = 0 }
_G.TS.tap = sub:install_write_tap(0x100000, 0x100003, "tgseq", function(off, data, mask)
	local t = mac.time:as_double()
	if t < FROM or t > TO then return end
	_G.TS.n = _G.TS.n + 1
	f:write(string.format("%06x %04x %04x\n", off, data, mask))
end)
_G.TS.h = emu.add_machine_stop_notifier(function() f:close(); emu.print_error("TGSEQ writes=" .. _G.TS.n) end)
