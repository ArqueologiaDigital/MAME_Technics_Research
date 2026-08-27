-- Is the 0xE1 answer's {LE32 dest, LE16 count} record CORRECT after the burst
-- quantum fix?  (SX-WSA1R, 2026-08-27)
--
-- QUESTION IT ANSWERS: the report that added perfect_quantum() says the link now
-- runs "essentially without loss".  The six bytes at 0x6007D3..0x6007D8 are the
-- one place where that can be judged instead of counted: INTTC3_Sel2_ArmPayload
-- (prom_a 0xF8E5AD) reads them with `ld BC,(0x6007d7)` (count) and
-- `ld XBC,(0x6007d3)` (destination) and arms micro-DMA channel 3 from them.  A
-- corrupt record shows up as an implausible count or a destination outside CPU
-- 1's RAM -- and then every byte CPU 2 sends afterwards is swallowed by a
-- runaway transfer that never completes, which looks like "the link carries
-- hundreds of bytes" in a byte counter.
--
-- Records every byte that lands in the six-byte record (time, address, value,
-- and whether the CPU or micro-DMA wrote it is NOT distinguishable from Lua, so
-- the time is what matters), then prints the assembled record at the moment
-- 0xF8E5AD reads it.
--
-- Run:
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 100 -window \
--       -autoboot_delay 1 -autoboot_script .../wsa1_e1_record.lua
local m   = manager.machine
local sp1 = m.devices[":cpu1"].spaces["program"]
local taps = {}
local rec = {}                 -- 0x6007D3..0x6007D8 -> last value
local wr  = {}                 -- log of writes, capped
local function now() return m.time:as_double() end

taps[#taps+1] = sp1:install_write_tap(0x6007d2, 0x6007d9, "rec", function (off, data, mask)
	for _, lane in ipairs({0, 1}) do
		if ((mask >> (lane * 8)) & 0xff) ~= 0 then
			local a = (off & ~1) | lane
			local v = (data >> (lane * 8)) & 0xff
			if a >= 0x6007d3 and a <= 0x6007d8 then
				rec[a] = v
				if #wr < 200 then
					wr[#wr+1] = string.format("t=%9.5f  (0x%06X) := 0x%02X", now(), a, v)
				end
			end
		end
	end
	return data
end)

local n_read = 0
taps[#taps+1] = sp1:install_read_tap(0x6007d2, 0x6007d9, "recrd", function (off, data, mask)
	-- the 32-bit destination read at 0x6007D3 is the one that identifies
	-- INTTC3_Sel2_ArmPayload; report once per pass over it
	if off > 0x6007d4 then return data end
	n_read = n_read + 1
	local b = {}
	for a = 0x6007d3, 0x6007d8 do b[#b+1] = rec[a] or -1 end
	local dest  = (b[4] < 0 or b[1] < 0) and -1 or (b[1] | (b[2] << 8) | (b[3] << 16) | (b[4] << 24))
	local count = (b[5] < 0 or b[6] < 0) and -1 or (b[5] | (b[6] << 8))
	emu.print_error(string.format(
		"t=%9.5f  E1 RECORD #%d  bytes=%02X %02X %02X %02X %02X %02X  dest=0x%08X count=%d (0x%04X)",
		now(), n_read, b[1] & 0xff, b[2] & 0xff, b[3] & 0xff, b[4] & 0xff, b[5] & 0xff, b[6] & 0xff,
		dest & 0xffffffff, count, count & 0xffff))
	return data
end)
_G.wsa1_e1_taps = taps

local done = false
_G.wsa1_e1_rep = emu.add_machine_frame_notifier(function ()
	if done or m.time:as_double() < (tonumber(os.getenv("REPORT_AT") or "95")) then return end
	done = true
	emu.print_error("======== E1 RECORD WRITE LOG (first " .. #wr .. ") ========")
	for i = 1, #wr do emu.print_error(wr[i]) end
	emu.print_error(string.format("======== reads of the record = %d ========", n_read))
end)
