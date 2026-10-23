-- dspcfg.lua -- set the KN5000's "Effects DSP IC311" configuration (DSPCFG, a KN5000_ENABLE_DSP1 build only) to
-- DSPCFG_VALUE (default 1: on, decoded ISA only) at start, so the tone generator runs IC311 every frame and mixes
-- its return; prints DSPCFG lines.
local port = manager.machine.ioport.ports[":DSPCFG"]
local v = tonumber(os.getenv("DSPCFG_VALUE") or "1")
if not port then
	emu.print_error("DSPCFG no such port (not a KN5000_ENABLE_DSP1 build?)")
else
	for _, f in pairs(port.fields) do
		f:set_value(v)
		emu.print_error(string.format("DSPCFG %s <- %d", f.name, v))
	end
end
