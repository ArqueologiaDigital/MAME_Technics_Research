-- planes.lua: dump the KN6000's UI index plane (0x5020042c), companion plane (0x50225c2c), CLUT
-- (0x5024f458) and composited LCD (0x9ce00000) at T_DUMP seconds, then exit.
local mac  = manager.machine
local prog = mac.devices[":maincpu"].spaces["program"]
local T = tonumber(os.getenv("T_DUMP")) or 4.5
local OUT = os.getenv("OUT_DIR") or "."
local function dump(name, base, len)
	local f = io.open(OUT .. "/" .. name, "wb")
	local t = {}
	for i = 0, len - 1 do t[#t + 1] = string.char(prog:read_u8(base + i)) if #t == 4096 then f:write(table.concat(t)) t = {} end end
	f:write(table.concat(t)); f:close()
end
_G.PL = emu.add_machine_frame_notifier(function()
	if _G.PL_done or (mac.time.seconds + mac.time.attoseconds / 1e18) < T then return end
	_G.PL_done = true
	dump("index.bin", 0x5020042c, 0x25800)
	dump("companion.bin", 0x50225c2c, 0x25800)
	dump("clut.bin", 0x5024f458, 0x200)
	dump("lcd.bin", 0x9ce00000, 640 * 240 * 2)
	dump("table.bin", 0x48000000, 0x26000)
	mac.video:snapshot()
	mac:exit()
end)
