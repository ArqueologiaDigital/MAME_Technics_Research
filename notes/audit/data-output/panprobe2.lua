-- CAUSAL test: poke the per-slot pan byte BEFORE note-on; predict +0x180 == poked value.
local mac = manager.machine
local sub = mac.devices[":subcpu"]
local sp  = sub.spaces["program"]
local function now() local mt = mac.time; return mt.seconds + mt.attoseconds/1e18 end
OUT = io.open(os.getenv("PP_OUT") or "panprobe2.txt", "w")
LATCH = 0; ARMED = false
TAP = sp:install_write_tap(0x100000, 0x100003, "pp2", function(off, data, mask)
	if off == 0x100000 then LATCH = data & 0xffff
	elseif off == 0x100002 and ARMED then
		local g = LATCH & 0xFFC0
		if g == 0x0180 or g == 0x0000 or g == 0x0040 or g == 0x0800 then
			OUT:write(string.format("%.6f %04X %04X\n", now(), LATCH, data & 0xffff))
		end
	end
	return nil
end)
local function setkey(port, name, v)
	local p = mac.ioport.ports[port]; if not p then return false end
	for _, f in pairs(p.fields) do if f.name == name then f:set_value(v); return true end end
	return false
end
local T0 = tonumber(os.getenv("PP_T0") or "22")
local st = 0
emu.register_periodic(function()
	local t = now()
	if st == 0 and t >= T0 then
		st = 1; ARMED = true; OUT:write("# ARM\n")
	elseif st == 1 and t >= T0 + 0.10 then
		st = 2
		-- slot0 subrec 0x0413D6, slot1 subrec 0x0413FB  (channel 0)
		sp:write_u8(0x0413D6+0x23, 0x2A); sp:write_u8(0x0413D6+0x24, 0x2A)
		sp:write_u8(0x0413FB+0x23, 0x55); sp:write_u8(0x0413FB+0x24, 0x55)
		OUT:write("# POKE slot0<-2A slot1<-55  (PREDICT: +0180=002A, +0181=0055)\n")
	elseif st == 2 and t >= T0 + 0.30 then
		st = 3; OUT:write("# KEYDOWN ok="..tostring(setkey(":KEY2","C4",1)).."\n")
	elseif st == 3 and t >= T0 + 1.50 then
		st = 4; OUT:write("# KEYUP\n"); setkey(":KEY2","C4",0)
	elseif st == 4 and t >= T0 + 2.50 then
		st = 5; OUT:write("# DONE\n"); OUT:close(); print("PP2 DONE"); mac:exit()
	end
end)
