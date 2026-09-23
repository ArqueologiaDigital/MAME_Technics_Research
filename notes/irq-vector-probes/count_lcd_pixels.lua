-- Count the lit pixels of the LCD at a fixed frame, so a boot can be compared
-- against a control build rather than against "it looked right".
--
-- Q it answers: did this build reach its play screen, or a black screen?
-- Signal: pixels of screen ":screen" whose RGB is not 0x000000, at frame 700.
-- NULL:   the same build with the interrupt vector base moved off the firmware's
--         thunk reads 0 -- see README.md, "Runtime control". A count that cannot
--         reach 0 is not a measurement.
--
--   ./kn kn7000 -rompath <roms> -str 60 -nothrottle \
--       -autoboot_script notes/irq-vector-probes/count_lcd_pixels.lua \
--       -window -resolution 800x400
--
-- The notifier MUST be held in a global: a local is garbage-collected and the
-- tap silently stops firing.
local n = 0
_G.__tap = emu.add_machine_frame_notifier(function ()
	n = n + 1
	if n == 700 then
		local s = manager.machine.screens[":screen"]
		local lit = 0
		for y = 0, s.height - 1 do
			for x = 0, s.width - 1 do
				if (s:pixel(x, y) & 0xffffff) ~= 0 then lit = lit + 1 end
			end
		end
		print(string.format("LCDLIT %d of %d", lit, s.width * s.height))
		manager.machine:exit()
	end
end)
