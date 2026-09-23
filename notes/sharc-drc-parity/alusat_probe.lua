-- Is MODE1.ALUSAT ever set on an EXISTING SHARC machine?
--
-- QUESTION IT ANSWERS
--   The submission adds the MODE1.ALUSAT saturation tail to the DRC's fixed-point
--   ALU. That tail can only change what a machine computes while the bit is SET.
--   The framebuffer A/B says the six Konami machines draw the same thing before and
--   after -- which is consistent with two very different worlds: the tail runs and
--   is correct, or the bit is never set and the tail never runs. Inferring which
--   from a seeded defect is indirect. This reads the register.
--
-- METHOD  sample MODE1 on every SHARC in the machine, once per frame, and report the
--   OR of every value seen plus a count of frames with ALUSAT (bit 13, 0x2000) set.
--   Sampling per frame can miss a bit that is set and cleared within one frame, so
--   a zero here is "not observed at frame boundaries", not "never". The OR of all
--   MODE1 values seen is printed too, so a run that saw nothing at all -- a wrong
--   tag, a device that never ran -- is distinguishable from one that saw traffic
--   without the bit.
--
-- ENV  AS_OUT  output file (required)   AS_FRAMES  frames to sample, default 4500
-- RUN  as part of a normal -str run, same as ab_tap.lua.

AS = AS or {}
AS.out = os.getenv("AS_OUT")
AS.limit = tonumber(os.getenv("AS_FRAMES") or "4500")
AS.frame = 0
AS.ALUSAT = 0x2000
AS.cpus = {}
for tag, dev in pairs(manager.machine.devices) do
	local ok, st = pcall(function () return dev.state["MODE1"] end)
	if ok and st then AS.cpus[#AS.cpus + 1] = { tag = tag, st = st, seen = 0, hits = 0, samples = 0 } end
end

AS.sub = emu.add_machine_frame_notifier(function ()
	AS.frame = AS.frame + 1
	for _, c in ipairs(AS.cpus) do
		local v = c.st.value & 0xffffffff
		c.seen = c.seen | v
		c.samples = c.samples + 1
		if (v & AS.ALUSAT) ~= 0 then c.hits = c.hits + 1 end
	end
	if AS.frame >= AS.limit then
		local f = io.open(AS.out, "w")
		if #AS.cpus == 0 then
			f:write("NO DEVICE EXPOSES MODE1 -- the probe saw nothing, which is not a negative result\n")
		end
		for _, c in ipairs(AS.cpus) do
			f:write(string.format("%s\tsamples=%d\tMODE1_or=%08X\tALUSAT_frames=%d\n",
				c.tag, c.samples, c.seen, c.hits))
		end
		f:close()
		manager.machine:exit()
	end
end)
