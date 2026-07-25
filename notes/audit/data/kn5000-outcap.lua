-- OUTPUT-PATH audit capture: every IC303 register write the sub-CPU makes.
-- Taps the SUB-CPU bus at 0x100000 (address latch) / 0x100002 (data) so we see
-- EXACTLY what the chip sees.  No rebuild needed.
--
-- IMPORTANT: the tap handle MUST be kept alive in a global, otherwise Lua GC
-- collects it and the tap silently stops firing (that is why the earlier
-- tgcap.lua run reported n=0).
local mac = manager.machine
local sub = mac.devices[":subcpu"]
local sp  = sub.spaces["program"]
local function now() local mt = mac.time; return mt.seconds + mt.attoseconds/1e18 end

OUT   = io.open(os.getenv("OUTCAP_OUT") or "outcap.txt", "w")
LATCH = 0
NW    = 0        -- writes seen since boot (never armed)
NREC  = 0        -- writes recorded
ARMED = false

TAP = sp:install_write_tap(0x100000, 0x100003, "outcap", function(off, data, mask)
	if off == 0x100000 then
		LATCH = data & 0xffff
	elseif off == 0x100002 then
		NW = NW + 1
		if ARMED and NREC < 300000 then
			NREC = NREC + 1
			OUT:write(string.format("%.6f %04X %04X\n", now(), LATCH, data & 0xffff))
		end
	end
	return nil
end)

-- Boot-time global-config writes happen long before we arm, so record those
-- unconditionally (they are the 13 globals: 0x0200-0x0205, 0x0C00-0x0C05, 0x0E00).
TAPG = sp:install_write_tap(0x100002, 0x100003, "outcapg", function(off, data, mask)
	local a = LATCH
	if (a >= 0x0200 and a <= 0x020F) or (a >= 0x0C00 and a <= 0x0C0F) or a == 0x0E00 then
		OUT:write(string.format("%.6f GLOBAL %04X %04X\n", now(), a, data & 0xffff))
	end
	return nil
end)

local function setkey(port, name, v)
	local p = mac.ioport.ports[port]
	if not p then return false end
	for _, f in pairs(p.fields) do
		if f.name == name then f:set_value(v); return true end
	end
	return false
end

local T0 = tonumber(os.getenv("OUTCAP_T0") or "22")
local st = 0
emu.register_periodic(function()
	local t = now()
	if st == 0 and t >= T0 then
		st = 1; ARMED = true
		OUT:write(string.format("# ARM t=%.6f writes_before_arm=%d\n", t, NW))
	elseif st == 1 and t >= T0 + 0.30 then
		st = 2
		OUT:write(string.format("# KEYDOWN C4 t=%.6f ok=%s\n", t, tostring(setkey(":KEY2", "C4", 1))))
	elseif st == 2 and t >= T0 + 2.30 then
		st = 3
		OUT:write(string.format("# KEYUP C4 t=%.6f\n", t))
		setkey(":KEY2", "C4", 0)
	elseif st == 3 and t >= T0 + 4.30 then
		st = 4
		OUT:write(string.format("# DONE t=%.6f nrec=%d nw=%d\n", t, NREC, NW))
		OUT:close()
		print("OUTCAP DONE nrec=" .. NREC .. " nw=" .. NW)
		mac:exit()
	end
end)
