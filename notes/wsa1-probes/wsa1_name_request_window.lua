-- Does the sound-name REQUEST reach CPU 2, and what does CPU 2 do with it?
-- (SX-WSA1R, 2026-08-27)
--
-- QUESTION IT ANSWERS: wsa1_soundname_path.lua shows sub_FC1BB9 building the
-- six-byte request {0x80, 0x00, 0x04, 0x00, 0x00, 0x00} at 0x000800 exactly once
-- (t = 6.876), sub_FC1BDC then polling ring 0x604800 65535 times, and the ring
-- never receiving a single byte.  That leaves two very different faults:
--
--   * the request never leaves CPU 1  -- nothing to answer;
--   * the request arrives and CPU 2 does not answer it.
--
-- This puts BOTH directions of the 0x7C0000 / 0x100000 wire on one timeline over
-- a chosen window, with the value of every byte, so the framed message
-- `05 80 00 04 00 00 00` (header = (stream 0 << 5) | (6 - 1)) can be looked for
-- directly.  It also logs CPU 2's INT0 command byte store at (0x600780)'s
-- prom_c equivalent -- CPU 2's own copy is at 0x600780 in ITS space, which this
-- taps as well -- and CPU 2's writes to its outgoing latch.
--
-- WINDOW_FROM / WINDOW_TO in emulated seconds (default 6.5 .. 8.5, which brackets
-- the one request); STOP_AT ends the run.
--
-- Run:
--   cd ~/compartilhado/kn7000_mame_build
--   WINDOW_FROM=6.5 WINDOW_TO=8.5 STOP_AT=12 DISPLAY=:0 ./kn7000 wsa1r \
--       -rompath ./roms -skip_gameinfo -window -autoboot_delay 1 \
--       -autoboot_script .../wsa1_name_request_window.lua
--
-- ⚠ taps held in globals (MAME's Lua GC collects locals).
local m    = manager.machine
local sp1  = m.devices[":cpu1"].spaces["program"]
local sp2  = m.devices[":cpu2"].spaces["program"]
local FROM = tonumber(os.getenv("WINDOW_FROM") or "6.5")
local TO   = tonumber(os.getenv("WINDOW_TO")   or "8.5")
local STOP = tonumber(os.getenv("STOP_AT")     or "12")
local log, LOGMAX = {}, 2000
local taps = {}
local c = { w1 = 0, r2 = 0, w2 = 0, r1 = 0 }
local function ev(fmt, ...)
	local t = m.time:as_double()
	if t < FROM or t > TO then return end
	if #log < LOGMAX then log[#log+1] = string.format("t=%11.6f  " .. fmt, t, ...) end
end
local function pc(cpu) return m.devices[cpu].state["CURPC"].value end

taps[#taps+1] = sp1:install_write_tap(0x7c0000, 0x7c0001, "w1", function (o, d, k)
	c.w1 = c.w1 + 1 ; ev("CPU1 WRITE 0x%02X  (#%d)  pc=%06X", d & 0xff, c.w1, pc(":cpu1")) ; return d end)
taps[#taps+1] = sp2:install_read_tap(0x100000, 0x100001, "r2", function (o, d, k)
	c.r2 = c.r2 + 1 ; ev("      CPU2 READ  0x%02X  (#%d)  pc=%06X", d & 0xff, c.r2, pc(":cpu2")) ; return d end)
taps[#taps+1] = sp2:install_write_tap(0x100000, 0x100001, "w2", function (o, d, k)
	c.w2 = c.w2 + 1 ; ev("            CPU2 WRITE 0x%02X  (#%d)  pc=%06X", d & 0xff, c.w2, pc(":cpu2")) ; return d end)
taps[#taps+1] = sp1:install_read_tap(0x7c0000, 0x7c0001, "r1", function (o, d, k)
	c.r1 = c.r1 + 1 ; ev("                  CPU1 READ  0x%02X  (#%d)", d & 0xff, c.r1) ; return d end)

-- CPU 2's copy of the received command byte, and its own selector
taps[#taps+1] = sp2:install_write_tap(0x600780, 0x600781, "cmd2", function (o, d, k)
	if (k & 0xff) ~= 0 then ev("      CPU2 (0x600780) := 0x%02X  pc=%06X", d & 0xff, pc(":cpu2")) end
	return d end)
taps[#taps+1] = sp2:install_write_tap(0x6007da, 0x6007db, "sel2", function (o, d, k)
	if (k & 0xff) ~= 0 then ev("      CPU2 SELECTOR := %d", d & 0xff) end ; return d end)
-- the request buffer on CPU 1
taps[#taps+1] = sp1:install_write_tap(0x000800, 0x000807, "req", function (o, d, k)
	for lane = 0, 1 do
		if ((k >> (lane * 8)) & 0xff) ~= 0 then
			ev("CPU1 REQBUF (0x%04X) := 0x%02X  pc=%06X", (o & ~1) | lane,
			   (d >> (lane * 8)) & 0xff, pc(":cpu1"))
		end
	end
	return d end)
_G.wsa1_nrw_taps = taps

_G.wsa1_nrw_rep = emu.add_machine_frame_notifier(function ()
	if _G.wsa1_nrw_done or m.time:as_double() < STOP then return end
	_G.wsa1_nrw_done = true
	emu.print_error(string.format("======== NAME REQUEST WINDOW %.3f..%.3f  (%d events) ========", FROM, TO, #log))
	for i = 1, #log do emu.print_error(log[i]) end
	emu.print_error(string.format("======== totals to t=%.1f: cpu1 w=%d r=%d  cpu2 w=%d r=%d ========",
		m.time:as_double(), c.w1, c.r1, c.w2, c.r2))
	m:exit()
end)
