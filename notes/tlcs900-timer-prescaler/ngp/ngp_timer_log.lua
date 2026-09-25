-- Logs every write the NGP BIOS makes to the TMP95C061's 8-bit timer registers,
-- to /tmp/ngp_timers.log, while a human drives the console.
--
-- Why a human: the console needs power-on plus language and date/time before it
-- boots normally with the splash and its tune, and neither Lua set_value nor
-- xdotool XTEST reaches the firmware's input reads -- MAME re-derives port
-- values from the physical input each frame. So the setup has to be done at the
-- keyboard, with this running.
--
-- What it answers: which timer, which prescaler tap and which compare value the
-- BIOS uses ONCE MUSIC IS PLAYING. A tap that only sees boot catches the setup
-- configuration, which need not be the one the sound engine runs on.
--
--   ./t9-refactored ngp -rompath ~/compartilhado/mame-roms -skip_gameinfo \
--       -autoboot_script <this file>
--
-- Then: F1, set language and date/time, let it boot to the splash and tune.
-- Quit with Esc. Read /tmp/ngp_timers.log.
local NAMES = {[0x20]="TRUN", [0x22]="TREG0", [0x23]="TREG1", [0x24]="T01MOD",
               [0x25]="TFFCR", [0x26]="TREG2", [0x27]="TREG3", [0x28]="T23MOD",
               [0x29]="TRDC"}
local f = io.open("/tmp/ngp_timers.log", "w")
local function emit(s)
	f:write(s .. "\n"); f:flush(); print(s)
end
local function decode(reg, v)
	if reg == "T23MOD" then
		local t3 = (v >> 2) & 3
		return " t3clk=" .. ({[0]="TO2TRG", [1]="phiT1", [2]="phiT16", [3]="phiT256"})[t3]
	elseif reg == "T01MOD" then
		local t1 = (v >> 2) & 3
		return " t1clk=" .. ({[0]="TO0TRG", [1]="phiT1", [2]="phiT16", [3]="phiT256"})[t1]
	elseif reg == "TRUN" then
		local on = {}
		for i = 0, 3 do if (v >> i) & 1 == 1 then on[#on+1] = "T" .. i end end
		if (v >> 7) & 1 == 1 then on[#on+1] = "PRESCALER" end
		return " running: " .. (#on > 0 and table.concat(on, ",") or "none")
	end
	return ""
end
local function run()
	emu.wait(1.0)
	local sp = manager.machine.devices[":maincpu"].spaces["program"]
	emit("# time_s  register  value  decode")
	_G.ngp_t8 = sp:install_write_tap(0x20, 0x29, "t8", function(offset, data, mask)
		local n = NAMES[offset]
		if n then
			emit(string.format("%8.3f  %-6s  %02X %s",
				manager.machine.time.seconds, n, data, decode(n, data)))
		end
	end)
	emit("# tap installed -- now power on (F1) and complete the setup")
end
_G.t = coroutine.create(run)
emu.register_periodic(function()
	if coroutine.status(_G.t) == "suspended" then
		local ok, e = coroutine.resume(_G.t); if not ok then print("err " .. tostring(e)) end
	end
end)
