-- subram_use.lua -- which 4 KB pages of the sub CPU's 1 MB DRAM are written, from SR_FROM s (after the boot's own
-- clear and payload load) to SR_TO s: SUBRAM lines at SR_TO, one per run of written pages, then the unwritten runs.
-- For finding sub DRAM free enough to hold code and sounds of ours (technics-docs kn5000-dsp-sample-playback-research).
local mac = manager.machine
local sub = mac.devices[":subcpu"].spaces["program"]
local A, B = tonumber(os.getenv("SR_FROM")) or 30, tonumber(os.getenv("SR_TO")) or 60
local seen, done = {}, false
_G.SR = {}
_G.SR.tap = sub:install_write_tap(0x000000, 0x0fffff, "subram_use", function(off, data, mask)
	local t = mac.time:as_double()
	if t >= A and t <= B then seen[off >> 12] = true end
end)
local function runs(want)
	local out, start = {}, nil
	for p = 0, 256 do
		local hit = p < 256 and ((seen[p] or false) == want)
		if hit and not start then start = p end
		if not hit and start then out[#out + 1] = string.format("%05X-%05X", start << 12, (p << 12) - 1); start = nil end
	end
	return table.concat(out, " ")
end
_G.SR.h = emu.add_machine_frame_notifier(function()
	if done or mac.time:as_double() < B then return end
	done = true
	emu.print_error("SUBRAM written   " .. runs(true))
	emu.print_error("SUBRAM unwritten " .. runs(false))
end)
