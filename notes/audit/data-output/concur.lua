-- Voice-concurrency probe: how many IC303 voices are gated ON at the same time
-- during a dense passage (accompaniment + right-hand chord).
local mac = manager.machine
local sub = mac.devices[":subcpu"]
local sp  = sub.spaces["program"]
local function now() local mt = mac.time; return mt.seconds + mt.attoseconds/1e18 end
OUT = io.open(os.getenv("CC_OUT") or "concur.txt", "w")
LATCH = 0
ON = {}
for i = 0, 63 do ON[i] = false end
NOW_ON = 0; PEAK = 0; PEAK_T = 0
HIST = {}
TAP = sp:install_write_tap(0x100000, 0x100003, "cc", function(off, data, mask)
	if off == 0x100000 then LATCH = data & 0xffff
	elseif off == 0x100002 then
		local a = LATCH
		if (a & 0xFFC0) == 0x0000 then          -- group 0 bank 0 = the GATE register
			local ch = a & 0x3F
			local d = data & 0xffff
			if d == 0x7E00 then
				if ON[ch] then ON[ch] = false; NOW_ON = NOW_ON - 1 end
			elseif (d & 0xFF00) == 0x8100 or d == 0xF0FF then
				if not ON[ch] then ON[ch] = true; NOW_ON = NOW_ON + 1 end
			end
			if NOW_ON > PEAK then PEAK = NOW_ON; PEAK_T = now() end
			HIST[NOW_ON] = (HIST[NOW_ON] or 0) + 1
		end
	end
	return nil
end)
local function press(port, name, v)
	local p = mac.ioport.ports[port]; if not p then return false end
	for _, f in pairs(p.fields) do if f.name == name then f:set_value(v); return true end end
	return false
end
local T0 = tonumber(os.getenv("CC_T0") or "22")
local st = 0
emu.register_periodic(function()
	local t = now()
	if st == 0 and t >= T0 then
		st = 1; OUT:write("# START/STOP ok="..tostring(press(":cpanel:CPR_SEG8","START/STOP",1)).."\n")
	elseif st == 1 and t >= T0 + 0.15 then
		st = 2; press(":cpanel:CPR_SEG8","START/STOP",0)
	elseif st == 2 and t >= T0 + 1.0 then
		st = 3
		press(":KEY0","C2",1); press(":KEY0","E2",1); press(":KEY0","G2",1)
		OUT:write("# LH chord C2-E2-G2\n")
	elseif st == 3 and t >= T0 + 3.0 then
		st = 4
		press(":KEY2","C4",1); press(":KEY2","E4",1); press(":KEY2","G4",1)
		press(":KEY3","C5",1); press(":KEY3","E5",1); press(":KEY3","G5",1)
		OUT:write("# RH 6-note chord\n")
	elseif st == 4 and t >= T0 + 25.0 then
		st = 5
		OUT:write(string.format("# PEAK simultaneous gated voices = %d at t=%.3f\n", PEAK, PEAK_T))
		local keys = {}
		for k,_ in pairs(HIST) do keys[#keys+1] = k end
		table.sort(keys)
		for _,k in ipairs(keys) do OUT:write(string.format("HIST %2d %d\n", k, HIST[k])) end
		OUT:write("# DONE\n"); OUT:close(); print("CONCUR PEAK="..PEAK); mac:exit()
	end
end)
