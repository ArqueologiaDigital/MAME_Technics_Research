-- WSA1R placeholder-sine render test.
--
-- QUESTION THIS ANSWERS: does the tone generator's placeholder sine backend
-- (wsa1_tonegen.cpp) actually produce non-silent audio when a voice is gated?
--
-- Notes do not reach the tone generator on their own yet -- the CPU2->CPU1 link
-- wedges (see wsa1.cpp) -- so this injects a few note-ons the way the firmware
-- would, through the SAME port the driver hooks (0x0010C000 on CPU 2): the PITCH
-- register (chan+0x0400) and the block-0 gate latch (0x8100).  Pair it with
-- -wavwrite and the capture must be non-silent; -seconds_to_run bounds the run.
--
-- RUN (from the build tree, visible video, ~6 emulated seconds):
--   ./kn7000 wsa1r -rompath <roms> -window -skip_gameinfo \
--       -autoboot_script tools/rigs/wsa1_tg_sine_test.lua -autoboot_delay 2 \
--       -wavwrite out.wav -seconds_to_run 6
-- PASS = out.wav has clearly non-zero RMS after the gate fires.
--
-- MEASURED 2026-09-05 (48 kHz capture, 0.5 s RMS windows, left channel):
--   gated run:  boot 0..1.5 s ~8000, then the triad steady ~7220 from 2.5 s on;
--               Goertzel at 440/554/659 Hz ~4.24e8 each, off-target (300/750 Hz)
--               3-4 orders of magnitude lower -- the three gated pitches, nothing else.
--   null run (no autoboot_script): identical boot 0..1.5 s, then RMS 0 from 2.0 s.
-- So the placeholder is SILENT at idle and sounds the gated notes at the right
-- pitch; the 0..1.5 s boot transient is the firmware gating voices during init
-- (real hardware would silence those with the amplitude envelope, not modelled).

local fired  = false
local frames = 0

-- Held in a global: a frame notifier that is only a local is garbage-collected
-- and silently stops firing.
_G._wsa1tg = emu.add_machine_frame_notifier(function()
	frames = frames + 1
	if fired or frames < 30 then return end   -- let the machine settle first
	fired = true

	local sp = manager.machine.devices[":cpu2"].spaces["program"]
	local function wr(reg, val)
		sp:write_u16(0x10c000, reg)   -- register select (tg_addr_w)
		sp:write_u16(0x10c002, val)   -- register data   (tg_data_w)
	end

	-- An A-major triad: A4, C#5, E5, in 1/256-semitone pitch units.
	local notes = { 69, 73, 76 }
	for i, n in ipairs(notes) do
		local ch = i - 1
		wr(0x0400 + ch, n * 256)   -- PITCH
		wr(0x0080 + ch, 0x0800)    -- OUTPUT LEVEL (value not used by the placeholder)
		wr(0x0000 + ch, 0x8100)    -- block-0 GATE on -> sets the busy latch
	end
	print("WSA1R-TG-TEST: gated 3 voices (A major triad) via 0x0010C000")
end)
