-- What is CPU 2 doing for the first ~80 emulated seconds?  (SX-WSA1R, 2026-08-27)
--
-- QUESTION IT ANSWERS: wsa1_name_request_window.lua shows CPU 1 posting its one
-- sound-name request at t = 6.876 and CPU 2 reading all seven bytes of it, yet
-- CPU 2 writes NOTHING back to the link until t ~ 70.88 -- by which time CPU 1
-- has long since timed out (65535 empty polls of ring 0x604800, ~0.7 s) and
-- printed the "Sound Name *****" fallback.  So the question is what occupies
-- CPU 2 in between.
--
-- Samples CPU 2's PC (and CPU 1's, for contrast) once per emulated frame and
-- prints the top addresses of each BUCKET_S-second bucket, resetting the
-- histogram each time -- a running histogram hides a phase change, which is
-- exactly what is being looked for.
--
-- Run:
--   BUCKET_S=2 STOP_AT=80 DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms \
--       -skip_gameinfo -window -autoboot_delay 1 \
--       -autoboot_script .../wsa1_cpu2_timeline.lua
local m = manager.machine
local BUCKET = tonumber(os.getenv("BUCKET_S") or "2")
local STOP   = tonumber(os.getenv("STOP_AT")  or "80")
local h1, h2 = {}, {}
local bucket_end = BUCKET

local function top(h, tag, t)
	local a = {}
	for k, v in pairs(h) do a[#a+1] = {k, v} end
	table.sort(a, function (x, y) return x[2] > y[2] end)
	local s = ""
	for i = 1, math.min(6, #a) do s = s .. string.format(" %06X:%d", a[i][1], a[i][2]) end
	emu.print_error(string.format("t<%5.1f %s%s", t, tag, s))
end

_G.wsa1_c2tl = emu.add_machine_frame_notifier(function ()
	local t = m.time:as_double()
	local p1 = m.devices[":cpu1"].state["CURPC"].value
	local p2 = m.devices[":cpu2"].state["CURPC"].value
	h1[p1] = (h1[p1] or 0) + 1
	h2[p2] = (h2[p2] or 0) + 1
	if t < bucket_end then return end
	top(h1, "cpu1", bucket_end)
	top(h2, "cpu2", bucket_end)
	h1, h2 = {}, {}
	bucket_end = bucket_end + BUCKET
	if t >= STOP then m:exit() end
end)
