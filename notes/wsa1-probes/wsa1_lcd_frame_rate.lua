-- What refresh rate does the SED1330 run at once the firmware's SYSTEM SET has
-- been accepted?
--
-- WHY IT MATTERS: sed1330_device only uses its clock() for one thing --
-- screen().configure(..., clocks_to_attotime(TC/R * L/F * 9)) when SYSTEM SET's
-- L/F byte arrives.  The driver passed 0 until the service manual's X2 (8 MHz,
-- across IC7's OSC1/OSC2 on sheet II-9/II-10) was read off the sheet, and with
-- 0 the screen kept its nominal 60 Hz.  This measures what 8 MHz gives.
--
--   ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 14 -window \
--       -autoboot_script .../wsa1_lcd_frame_rate.lua
--
-- MEASURED 2026-09-03, on the build of the day: 600 frames in 8.748000 s of
-- emulated time = 68.5871 Hz, which is 8000000 / (54 * 240 * 9) exactly -- so
-- the firmware's SYSTEM SET asks for TC/R = 54 characters and L/F = 240 lines.
-- Frames 1-99 are skipped because the first ~30 of them run at the screen's
-- nominal rate, before SYSTEM SET arrives at t = 0.4999 s.
--
-- The rendered image does NOT change with the clock: snapshots at the same
-- boot point, taken with wsa1_screen_series.lua before and after, are
-- pixel-identical (PIL ImageChops difference bbox = None).
_G.n, _G.t100 = 0, nil
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.n = _G.n + 1
	local t = manager.machine.time:as_double()
	if _G.n == 100 then _G.t100 = t end
	if _G.n == 700 then
		print(string.format("RATE steady: 600 frames in %.6f s -> %.4f Hz",
			t - _G.t100, 600 / (t - _G.t100)))
	end
end)
