-- tabtap.lua: which table-ROM (0x48000000-0x483fffff) offsets the KN6000 reads, per 0.1 s of boot.
-- Writes TABTAP lines to stderr: time slot, read count, and the 4 KB blocks read with counts.
local mac  = manager.machine
local prog = mac.devices[":maincpu"].spaces["program"]
_G.TT = { slot = {}, cur = -1 }
local function now() return mac.time.seconds + mac.time.attoseconds / 1e18 end
_G.TT.tap = prog:install_read_tap(0x48000000, 0x483fffff, "tabtap", function(offset, data, mask)
	local s = math.floor(now() * 10)
	local e = _G.TT.slot[s]
	if not e then e = { n = 0, blk = {} }; _G.TT.slot[s] = e end
	e.n = e.n + 1
	local b = offset & 0xfffff000
	e.blk[b] = (e.blk[b] or 0) + 1
	return nil
end)
_G.TT.h = emu.add_machine_frame_notifier(function()
	local t = now()
	if t < 12.2 or _G.TT.done then return end
	_G.TT.done = true
	local ks = {}
	for s, _ in pairs(_G.TT.slot) do ks[#ks + 1] = s end
	table.sort(ks)
	for _, s in ipairs(ks) do
		local e = _G.TT.slot[s]
		local bl = {}
		for b, n in pairs(e.blk) do bl[#bl + 1] = string.format("%08x:%d", b, n) end
		table.sort(bl)
		emu.print_error(string.format("TABTAP %5.1f n=%d %s", s / 10, e.n, table.concat(bl, " ")))
	end
	mac:exit()
end)
