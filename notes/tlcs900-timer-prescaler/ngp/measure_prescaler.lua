-- Measures phiT1 on a TMP95C061 without needing the machine to boot.
--
-- What question it answers: "does this build's prescaler give the ngp its
-- correct music clock?" That clock is timer 3 -> TO3 -> port A bit 3 -> Z80
-- interrupt (ngp_state::tlcs900_porta), so the timer 3 match rate IS the music
-- tempo. The ngp BIOS asks for ~498 Hz: it converts a requested period into
-- TREG3 by dividing by 20.48 us (ff2d5a: mul WA,1000; ff2d5e: div WA,0x5000)
-- and writes TREG3 = 0x62, i.e. 2007 us.
--
-- Why it programs the timer itself rather than letting the BIOS do it: the
-- console needs power-on plus language and date/time before it runs, and that
-- cannot be automated -- Lua set_value does not survive a frame, the BIOS polls
-- the power button through I/O 0x31 so a momentary press is invisible, and TO3
-- and the Z80 stay dormant until after power-on. Register writes DO reach the
-- device, so the timer can be driven directly.
--
-- Needs a build with the T3RATE counter patched into tmp95c061.cpp (see
-- README.md) and NGP_T3RATE=1 in the environment; read the rate from error.log
-- after running with -log.
--
--   NGP_T3RATE=1 ./<binary> ngp -rompath <roms> -skip_gameinfo -nothrottle \
--       -sound none -str 16 -autoboot_script <this file> -log
--
-- PASS: 489.9 Hz. The build that garbled ngp music measured 7836.7 Hz.
local function run()
	emu.wait(2.0)
	local sp = manager.machine.devices[":maincpu"].spaces["program"]
	sp:write_u8(0x28, 0x04)   -- T23MOD: timer 3 clock = phiT1
	sp:write_u8(0x27, 0x62)   -- TREG3 = 98, as the BIOS sets it
	sp:write_u8(0x20, 0x88)   -- TRUN: prescaler + timer 3
	print(string.format("PRE: programmed, TRUN reads %02X", sp:read_u8(0x20)))
	emu.wait(12.0)
	print(string.format("PRE: TRUN still %02X", sp:read_u8(0x20)))
	print("PRE-DONE")
end
_G.t = coroutine.create(run)
emu.register_periodic(function()
	if coroutine.status(_G.t) == "suspended" then
		local ok, e = coroutine.resume(_G.t); if not ok then print("PRE err " .. tostring(e)) end
	end
end)
