-- Does this machine's firmware ever arm a micro-DMA start vector? (2026-08-27)
--
-- QUESTION IT ANSWERS: OVERLAY FIX 6 in tmp95c061.cpp only changes behaviour for
-- an interrupt whose vector matches a live DMAnV.  A machine that never writes
-- DMA0V..DMA3V (internal I/O 0x7C..0x7F) therefore CANNOT be affected by it, and
-- this probe is what clears -- or fails to clear -- the other tmp95c061 machines
-- in the build.  It also records the armed VALUES, because
-- (value & 0x1F) << 2 outside 0x28..0x70 is a vector FIX 6 masks while
-- tlcs900_process_hdma() refuses to serve it.
--
-- Run:
--   CPUS=":maincpu" REPORT_AT=20 DISPLAY=:0 ./kn7000 <machine> -rompath ./roms \
--       -skip_gameinfo -str 25 -window -autoboot_delay 1 \
--       -autoboot_script .../tlcs900_dmav_census.lua
local m = manager.machine
local taps = {}
local arms = {}
local total = 0
for tag in string.gmatch(os.getenv("CPUS") or ":maincpu", "[^,]+") do
	local dev = m.devices[tag]
	if dev then
		local sp = dev.spaces["program"]
		arms[tag] = {}
		taps[#taps+1] = sp:install_write_tap(0x00007c, 0x00007f, "dmav", function (off, data, mask)
			local lo  = (mask & 0x00ff) ~= 0
			local reg = (off & ~1) | (lo and 0 or 1)
			local val = lo and (data & 0xff) or ((data >> 8) & 0xff)
			local k = string.format("DMA%dV=0x%02X (vec 0x%02X)", reg - 0x7c, val, (val & 0x1f) << 2)
			arms[tag][k] = (arms[tag][k] or 0) + 1
			total = total + 1
			return data
		end)
	else
		emu.print_error("no such device: " .. tag)
	end
end
_G.dmav_taps = taps
local AT = tonumber(os.getenv("REPORT_AT") or "20")
local done = false
_G.dmav_rep = emu.add_machine_frame_notifier(function ()
	if done or m.time:as_double() < AT then return end
	done = true
	emu.print_error(string.format("======== DMAnV CENSUS %s t=%.1f total=%d ========",
		emu.romname(), m.time:as_double(), total))
	for tag, t in pairs(arms) do
		local l = {} ; for k, v in pairs(t) do l[#l+1] = k .. " x" .. v end
		table.sort(l)
		emu.print_error(string.format("  %s: %s", tag, #l > 0 and table.concat(l, "  ") or "NONE"))
	end
	emu.print_error("======== END ========")
end)
