-- KN6000 layout click-through test.
--
-- Verifies the thing that was actually broken: that the button a user clicks IN THE ARTWORK sends
-- the matrix cell its silkscreen legend names.  The script is driven by a list of
-- (legend, inputtag, inputmask) triples extracted from src/mame/layout/kn6000.lay itself -- i.e.
-- from the drawn element, not from the driver -- so pressing them is equivalent to clicking the
-- element at that legend.  After each press a snapshot is taken; the screen the firmware opens is
-- the evidence.
--
--   ../kn7000_mame_build/kn7000 kn6000 -rompath ./roms -window -skip_gameinfo \
--       -autoboot_script tools/kn6000_layout_clicktest.lua -autoboot_delay 1

local PRESSES = {}          -- filled from KN6000_CLICKTEST env: "LEGEND|tag|mask;..."
local spec = os.getenv("KN6000_CLICKTEST") or ""
for item in spec:gmatch("[^;]+") do
	local legend, tag, mask = item:match("^([^|]+)|([^|]+)|([^|]+)$")
	if legend then PRESSES[#PRESSES + 1] = { legend = legend, tag = tag, mask = tonumber(mask) } end
end

local BOOT_S   = tonumber(os.getenv("KN6000_BOOT_S") or "26")
local HOLD_S   = 0.35
local SETTLE_S = 2.5

local function now()
	local t = manager.machine.time
	return t.seconds + t.attoseconds / 1e18
end

local idx, phase, t0 = 1, "boot", nil
local function port(tag) return manager.machine.ioport.ports[":cpanel:" .. tag] end

emu.register_periodic(function()
	local t = now()
	if phase == "boot" then
		if t < BOOT_S then return end
		manager.machine.video:snapshot()
		print(string.format("[clicktest] t=%.1f BOOT snapshot", t))
		phase, t0 = "press", t
	elseif phase == "press" then
		local p = PRESSES[idx]
		if not p then
			print("[clicktest] done"); manager.machine:exit(); phase = "end"; return
		end
		local pt = port(p.tag)
		if not pt then print("[clicktest] NO SUCH PORT " .. p.tag); idx = idx + 1; return end
		for _, f in pairs(pt.fields) do
			if f.mask == p.mask then f:set_value(1) end
		end
		print(string.format("[clicktest] t=%.1f PRESS %-24s %s mask=0x%02x", t, p.legend, p.tag, p.mask))
		phase, t0 = "hold", t
	elseif phase == "hold" and t - t0 > HOLD_S then
		local p = PRESSES[idx]
		for _, f in pairs(port(p.tag).fields) do
			if f.mask == p.mask then f:set_value(0) end
		end
		phase, t0 = "settle", t
	elseif phase == "settle" and t - t0 > SETTLE_S then
		manager.machine.video:snapshot()
		print(string.format("[clicktest] t=%.1f SNAP after %s", t, PRESSES[idx].legend))
		idx = idx + 1
		phase, t0 = "press", t
	end
end)
