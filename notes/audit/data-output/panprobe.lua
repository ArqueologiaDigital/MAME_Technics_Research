-- PAN-PATH probe: prove partial_block[+1] / subrec[+0x23,+0x24] -> IC303 register +0x180.
local mac = manager.machine
local sub = mac.devices[":subcpu"]
local sp  = sub.spaces["program"]
local function now() local mt = mac.time; return mt.seconds + mt.attoseconds/1e18 end

OUT   = io.open(os.getenv("PP_OUT") or "panprobe.txt", "w")
LATCH = 0
ARMED = false

TAP = sp:install_write_tap(0x100000, 0x100003, "pp", function(off, data, mask)
	if off == 0x100000 then LATCH = data & 0xffff
	elseif off == 0x100002 then
		if ARMED then
			local a = LATCH
			-- record only the registers this probe is about, plus the gate
			local grp = a & 0xFFC0
			if grp == 0x0180 or grp == 0x0000 or grp == 0x0040 then
				OUT:write(string.format("%.6f %04X %04X\n", now(), a, data & 0xffff))
			end
		end
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

local function hex(addr, n)
	local t = {}
	for i = 0, n-1 do t[#t+1] = string.format("%02X", sp:read_u8(addr+i)) end
	return table.concat(t, " ")
end
local function rd32(a)
	return sp:read_u8(a) | (sp:read_u8(a+1)<<8) | (sp:read_u8(a+2)<<16) | (sp:read_u8(a+3)<<24)
end

local function dump(tag)
	OUT:write("### DUMP "..tag.." t="..string.format("%.4f", now()).."\n")
	for v = 0, 3 do
		local d = 0x04308E + 0x47*v
		OUT:write(string.format("VOICE %d desc=%06X : %s\n", v, d, hex(d, 0x47)))
		local ch  = sp:read_u8(d+0x04)
		local p17 = rd32(d+0x17)
		local p23 = rd32(d+0x23)
		local p27 = rd32(d+0x27)
		local r2b = sp:read_u8(d+0x2b) | (sp:read_u8(d+0x2c)<<8)
		OUT:write(string.format("  ch=%02X  +17=%06X (*=%02X, [-1]=%02X, [+1]=%02X)  +23=%06X  +27=%06X  +2b=%04X\n",
			ch, p17, sp:read_u8(p17), sp:read_u8(p17-1), sp:read_u8(p17+1), p23, p27, r2b))
		if ch < 0x1A then
			local cb = 0x041368 + ch*0x11F
			OUT:write(string.format("  chan_base=%06X  panCC[+0E]=%02X  mode[+26]=%02X\n",
				cb, sp:read_u8(cb+0x0E), sp:read_u8(cb+0x26)))
			for i = 0, 3 do
				local sr = cb + 0x6e + i*0x25
				OUT:write(string.format("   slot%d sr=%06X ptr=%06X ptr[+0]=%02X ptr[+1]=%02X  [+23]=%02X [+24]=%02X | %s\n",
					i, sr, rd32(sr), sp:read_u8(rd32(sr)), sp:read_u8(rd32(sr)+1),
					sp:read_u8(sr+0x23), sp:read_u8(sr+0x24), hex(sr, 0x25)))
			end
		end
	end
	OUT:flush()
end

local T0 = tonumber(os.getenv("PP_T0") or "22")
local st = 0
emu.register_periodic(function()
	local t = now()
	if st == 0 and t >= T0 then
		st = 1; ARMED = true
		OUT:write("# ARM\n")
	elseif st == 1 and t >= T0 + 0.30 then
		st = 2
		OUT:write("# KEYDOWN C4 ok="..tostring(setkey(":KEY2","C4",1)).."\n")
	elseif st == 2 and t >= T0 + 0.60 then
		st = 3
		dump("HELD")
	elseif st == 3 and t >= T0 + 0.90 then
		st = 4
		-- POKE: overwrite the pan byte of voice0's slot with 0x2A and voice1's with 0x55
		for v = 0, 1 do
			local d  = 0x04308E + 0x47*v
			local p27 = rd32(d+0x27)
			local val = (v == 0) and 0x2A or 0x55
			sp:write_u8(p27+0x23, val)
			sp:write_u8(p27+0x24, val)
			OUT:write(string.format("# POKE voice %d subrec %06X [+23]/[+24] <- %02X\n", v, p27, val))
		end
		OUT:flush()
	elseif st == 4 and t >= T0 + 3.00 then
		st = 5
		dump("AFTER-POKE")
		OUT:write("# KEYUP\n"); setkey(":KEY2","C4",0)
	elseif st == 5 and t >= T0 + 4.50 then
		st = 6
		OUT:write("# DONE\n"); OUT:close()
		print("PANPROBE DONE")
		mac:exit()
	end
end)
