-- WSA1R placeholder-sine render + amplitude-envelope test.
--
-- QUESTION THIS ANSWERS: does the tone generator's placeholder sine backend
-- (wsa1_tonegen.cpp) render gated voices at the right pitch, scale them by the
-- OUTPUT LEVEL register, and silence a channel left in its idle marker?
--
-- Notes do not reach the tone generator on their own yet (the CPU2->CPU1 link
-- wedges), so this injects a few note-ons the way the firmware would, through
-- the SAME port the driver hooks (0x0010C000 on CPU 2): PITCH (chan+0x0400),
-- OUTPUT LEVEL (chan+0x0080), the two envelope-marker halves (chan+0x0800 /
-- chan+0x0840), and the block-0 gate (0x8100).  Pair it with -wavwrite.
--
-- THREE VOICES, EACH A CONTROL FOR THE ENVELOPE MODEL:
--   voice 0  A4  unity level (0x0FF4), non-idle  -> LOUD
--   voice 1  C#5 unity level BUT the idle marker -> SILENT (idle beats the gate)
--   voice 2  E5  level 2 octaves down (0x0DF4)   -> ~1/4 amplitude
-- So a correct capture has a strong 440 Hz, a much weaker 659 Hz, and NOTHING
-- at 554 Hz; and the no-autoboot null is silent from ~2 s.
--
-- RUN (from the build tree, visible video, ~6 emulated seconds):
--   ./kn7000 wsa1r -rompath <roms> -window -skip_gameinfo \
--       -autoboot_script tools/rigs/wsa1_tg_sine_test.lua -autoboot_delay 2 \
--       -wavwrite out.wav -seconds_to_run 6
--
-- MEASURED 2026-09-05 (48 kHz capture, steady window 3.5..5.5 s, left channel):
--   A4 440 Hz (unity)      magnitude 2949   -- LOUD
--   C#5 554 Hz (idle)      magnitude 2.5    -- SILENT (ratio 0.0008: idle beats gate)
--   E5 659 Hz (-2 octaves) magnitude 740    -- ratio 0.2507 to A4 (expected 0.25)
-- and with the level+idle model the boot init is SILENT (0..1.5 s RMS 0), where
-- the fixed-amplitude placeholder had a loud 0..1.5 s transient.

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

	local defs = {
		{ ch = 0, note = 69, level = 0x0ff4, e0 = 0x8000, e1 = 0x8000 }, -- LOUD
		{ ch = 1, note = 73, level = 0x0ff4, e0 = 0xff80, e1 = 0xff00 }, -- IDLE -> silent
		{ ch = 2, note = 76, level = 0x0df4, e0 = 0x8000, e1 = 0x8000 }, -- ~1/4
	}
	for _, d in ipairs(defs) do
		wr(0x0400 + d.ch, d.note * 256)  -- PITCH
		wr(0x0080 + d.ch, d.level)       -- OUTPUT LEVEL
		wr(0x0800 + d.ch, d.e0)          -- envelope marker halves
		wr(0x0840 + d.ch, d.e1)
		wr(0x0000 + d.ch, 0x8100)        -- block-0 GATE on
	end
	print("WSA1R-TG-TEST: gated 3 voices (loud A4, idle C#5, quiet E5) via 0x0010C000")
end)
