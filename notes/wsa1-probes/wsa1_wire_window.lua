-- What exactly crosses the CPU 2 -> CPU 1 wire around the one 0xE1 answer?
-- (SX-WSA1R, 2026-08-27)
--
-- QUESTION IT ANSWERS: after the burst-quantum change the receive side still
-- arms micro-DMA channel 3 from a nonsense {dest,count} record
-- (wsa1_e1_record.lua: dest = 0x20107802, count = 17440, and the TLCS-900 has
-- only 24 address pins).  Two very different faults produce that:
--   * bytes LOST in the one-byte latch -- the record is a subset of what was
--     sent, and the cure is more interleaving;
--   * FRAMING -- every byte arrives, but the CPU/DMA boundary is off, so the
--     record is assembled from the wrong six bytes, and no amount of
--     interleaving helps.
-- The two are told apart by putting the sender's writes and the receiver's reads
-- on ONE timeline, which is what this prints.  Every write is logged with the
-- value; every read with the value it returned; a write whose value never
-- appears in a following read was overwritten (lost), a read whose value repeats
-- a previous read is a re-read of a stale latch.
--
-- WINDOW_FROM / WINDOW_TO (emulated seconds) bound the log so the interesting
-- exchange is not pushed out by the boot; the 0xE1 answer lands at t ~ 70.88.
--
-- Run:
--   WINDOW_FROM=70.5 WINDOW_TO=71.5 DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms \
--       -skip_gameinfo -str 100 -window -autoboot_delay 1 \
--       -autoboot_script .../wsa1_wire_window.lua
local m   = manager.machine
local sp1 = m.devices[":cpu1"].spaces["program"]
local sp2 = m.devices[":cpu2"].spaces["program"]
local FROM = tonumber(os.getenv("WINDOW_FROM") or "70.5")
local TO   = tonumber(os.getenv("WINDOW_TO")   or "71.5")
local log, LOGMAX = {}, 600
local taps = {}
local n_w, n_r = 0, 0
local function ev(fmt, ...)
	local t = m.time:as_double()
	if t < FROM or t > TO then return end
	if #log < LOGMAX then log[#log+1] = string.format("t=%11.6f  " .. fmt, t, ...) end
end
taps[#taps+1] = sp2:install_write_tap(0x100000, 0x100001, "w", function (o, d, k)
	n_w = n_w + 1 ; ev("CPU2 WRITE 0x%02X   (#%d)", d & 0xff, n_w) ; return d end)
taps[#taps+1] = sp1:install_read_tap(0x7c0000, 0x7c0001, "r", function (o, d, k)
	n_r = n_r + 1 ; ev("        CPU1 READ  0x%02X   (#%d)", d & 0xff, n_r) ; return d end)
-- the six-byte record and the selector, on the same timeline
taps[#taps+1] = sp1:install_write_tap(0x6007d2, 0x6007d9, "rec", function (o, d, k)
	for _, lane in ipairs({0, 1}) do
		if ((k >> (lane * 8)) & 0xff) ~= 0 then
			local a = (o & ~1) | lane
			if a >= 0x6007d3 and a <= 0x6007d8 then
				ev("                RECORD (0x%06X) := 0x%02X", a, (d >> (lane * 8)) & 0xff)
			end
		end
	end
	return d end)
taps[#taps+1] = sp1:install_write_tap(0x6007da, 0x6007db, "sel", function (o, d, k)
	if (k & 0xff) ~= 0 then ev("                SELECTOR := %d", d & 0xff) end ; return d end)
taps[#taps+1] = sp1:install_write_tap(0x00007e, 0x00007f, "dmav", function (o, d, k)
	local lo = (k & 0x00ff) ~= 0
	ev("                DMA%dV := 0x%02X", lo and 2 or 3, lo and (d & 0xff) or ((d >> 8) & 0xff))
	return d end)
_G.wsa1_wire_taps = taps
local done = false
_G.wsa1_wire_rep = emu.add_machine_frame_notifier(function ()
	if done or m.time:as_double() < TO + 1 then return end
	done = true
	emu.print_error(string.format("======== WIRE WINDOW %.3f..%.3f  (%d events, cpu2 writes=%d cpu1 reads=%d total) ========",
		FROM, TO, #log, n_w, n_r))
	for i = 1, #log do emu.print_error(log[i]) end
	emu.print_error("======== END ========")
end)
