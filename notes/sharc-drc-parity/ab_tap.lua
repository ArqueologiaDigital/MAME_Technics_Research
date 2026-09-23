-- Screen-state tap for the SHARC A/B: dump the exact framebuffer at fixed frame
-- numbers, then exit.
--
-- QUESTION IT ANSWERS
--   "Does an existing SHARC machine draw the same thing before and after the
--    submission's changes to src/devices/cpu/sharc?"
--   On every one of these boards the SHARC is the geometry/3D processor, so the
--   screen is where a core change shows up. Comparing framebuffers rather than
--   PNGs keeps the answer independent of the PNG encoder.
--
-- WHY THE GLOBALS
--   emu.add_machine_frame_notifier() returns a subscription. Drop it and the GC
--   collects it, the tap silently stops firing, and every run then "matches".
--   Everything is parked in AB so that cannot happen.
--
-- ENV
--   AB_OUT    directory for the dumps (required)
--   AB_MARKS  comma-separated frame numbers, default 600,1200,1800,2400,3000
--   AB_PRESS  comma-separated <frame>:<substring>, e.g. "1500:test,2100:service".
--             At <frame> every input field whose name contains <substring> (case
--             insensitive) is asserted, and released 30 frames later. Without this
--             these boards sit on a POST prompt -- gticlub on "DEVICE ERROR
--             (STEERING WHEEL) / PUSH TEST SWITCH TO SKIP", gradius4 on "RTC
--             CHECKSUM ERROR! / PRESS TEST SWITCH TO CONTINUE" -- and never reach
--             the attract mode where the SHARC draws geometry. A run that never
--             leaves a text prompt is not much of a test of a 3D coprocessor.
--             Which fields were found is written to fields.txt, so a press that
--             matched nothing is visible rather than silent.
--
-- OUTPUT   <AB_OUT>/f<frame>.raw  -- width*height*4 bytes, native RGB32
--          <AB_OUT>/f<frame>.png  -- the same frame, to look at
--          <AB_OUT>/marks.txt     -- one line per mark actually written

AB = AB or {}
AB.out = os.getenv("AB_OUT")
AB.frame = 0
AB.marks = {}
AB.hit = {}
for m in string.gmatch(os.getenv("AB_MARKS") or "600,1200,1800,2400,3000", "[^,]+") do
	AB.marks[#AB.marks + 1] = tonumber(m)
end
AB.last = AB.marks[#AB.marks]

AB.press = {}
AB.held = {}
AB.log = {}
for item in string.gmatch(os.getenv("AB_PRESS") or "", "[^,]+") do
	local fr, what = string.match(item, "^(%d+):(.+)$")
	if fr then AB.press[#AB.press + 1] = { frame = tonumber(fr), what = string.lower(what) } end
end

AB.assert_fields = function (what)
	local n = 0
	for _, port in pairs(manager.machine.ioport.ports) do
		for name, field in pairs(port.fields) do
			if string.find(string.lower(name), what, 1, true) then
				field:set_value(1)
				AB.held[#AB.held + 1] = { f = field, until_frame = AB.frame + 30 }
				AB.log[#AB.log + 1] = string.format("%d press %s", AB.frame, name)
				n = n + 1
			end
		end
	end
	if n == 0 then AB.log[#AB.log + 1] = string.format("%d press %s MATCHED NOTHING", AB.frame, what) end
end

AB.screen = nil
for _, s in pairs(manager.machine.screens) do AB.screen = s break end

AB.dump = function (n)
	if not AB.screen then return end
	local pix, w, h = AB.screen:pixels()
	local f = io.open(string.format("%s/f%04d.raw", AB.out, n), "wb")
	if f then f:write(pix) f:close() end
	AB.screen:snapshot(string.format("%s/f%04d.png", AB.out, n))
	AB.hit[#AB.hit + 1] = string.format("%d %dx%d %d", n, w, h, #pix)
end

AB.sub = emu.add_machine_frame_notifier(function ()
	AB.frame = AB.frame + 1
	for _, p in ipairs(AB.press) do
		if AB.frame == p.frame then AB.assert_fields(p.what) end
	end
	local keep = {}
	for _, h in ipairs(AB.held) do
		if AB.frame >= h.until_frame then h.f:set_value(0) else keep[#keep + 1] = h end
	end
	AB.held = keep
	for _, m in ipairs(AB.marks) do
		if AB.frame == m then AB.dump(m) end
	end
	if AB.frame >= AB.last then
		local f = io.open(AB.out .. "/marks.txt", "w")
		if f then f:write(table.concat(AB.hit, "\n") .. "\n") f:close() end
		local g = io.open(AB.out .. "/fields.txt", "w")
		if g then g:write(table.concat(AB.log, "\n") .. "\n") g:close() end
		manager.machine:exit()
	end
end)
