-- LABELLED EXPERIMENT: what changes if CPU 2's DSP READY line (P9 bit 3) is
-- held high?  (SX-WSA1R, 2026-08-27)
--
-- ⚠ THIS IS A FAKE AND IT IS NOT IN THE DRIVER.  It exists to test ONE causal
-- claim, and it does it from Lua so that nothing has to be built or committed to
-- run it: a read tap on CPU 2's internal SFR 0x19 (P9) forces bit 3 of every
-- read to 1.
--
-- THE CLAIM: the sound name is missing because CPU 2 never gets to answer.
-- Measured chain (wsa1_soundname_path.lua, wsa1_name_request_window.lua):
--   t = 6.876   CPU 1 builds {80 00 04 00 00 00} at 0x000800 and posts it on
--               link stream 0 as `05 80 00 04 00 00 00`; CPU 2 reads all seven
--               bytes (header at prom_c 0xF99BD5, payload by micro-DMA);
--   t = 6.876   .. 7.576  CPU 1 polls ring 0x604800 65535 times.  Nothing is
--               ever PUT in that ring -- 0 writes in 110 s;
--   t = 7.576   XIY = 0xFFFFFFFF, prom_a 0xFC1BAE loads the fallback string;
--   t = 70.88   CPU 2's FIRST and only transmission of the boot.
-- and wsa1_cpu2_timeline.lua shows CPU 2's PC inside 0xF9A347-0xF9A490 for the
-- whole 80 s: the uPD6383GF microcode upload, whose per-byte handshake polls
-- P9 bit 3 with a 0x1F40 = 8000 iteration bound and, on an unbound MAME port
-- that reads 0, always burns the full bound and sets the firmware's timeout
-- flag at (0x00F35C).  The driver already names this (wsa1.cpp, "DELIBERATELY
-- NOT WIRED") and says it is only slow, not fatal.  This probe tests whether
-- "only slow" is true for the sound name.
--
-- Reports the same counters as wsa1_soundname_path.lua so the two runs compare
-- directly, plus (0x00F35C) -- the upload's own timeout flag -- and takes a
-- snapshot at each time in SNAP_AT (comma-separated, default "30,45,95").
--
-- Run:
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -window \
--       -snapshot_directory <dir> -autoboot_delay 1 \
--       -autoboot_script .../wsa1_dspready_experiment.lua
--
-- FAKE=0 disables the forcing, so the same script measures the control.
local m    = manager.machine
local sp1  = m.devices[":cpu1"].spaces["program"]
local sp2  = m.devices[":cpu2"].spaces["program"]
local FAKE = (os.getenv("FAKE") or "1") ~= "0"
local taps = {}
local function T(t) taps[#taps+1] = t end
local function now() return m.time:as_double() end

-- ---- the fake ------------------------------------------------------------
local n_p9 = 0
if FAKE then
	T(sp2:install_read_tap(0x000018, 0x000019, "p9", function (off, data, mask)
		if ((mask >> 8) & 0xff) ~= 0 then
			n_p9 = n_p9 + 1
			data = data | 0x0800          -- byte 0x19 (odd lane) bit 3
		end
		return data
	end))
end

-- ---- the same counters as wsa1_soundname_path.lua -------------------------
local n = { req = 0, ans = 0, fb = 0, ring_r = 0, ring_w = 0,
            w1 = 0, r1 = 0, w2 = 0, r2 = 0, tmo = 0 }
local ansbuf = {}
T(sp1:install_write_tap(0x000800, 0x000807, "req", function (off, data, mask)
	for lane = 0, 1 do
		if ((mask >> (lane * 8)) & 0xff) ~= 0 and ((off & ~1) | lane) == 0x800 then
			n.req = n.req + 1
		end
	end
	return data end))
T(sp1:install_write_tap(0x000810, 0x000821, "ans", function (off, data, mask)
	for lane = 0, 1 do
		if ((mask >> (lane * 8)) & 0xff) ~= 0 then
			n.ans = n.ans + 1
			ansbuf[(off & ~1) | lane] = (data >> (lane * 8)) & 0xff
		end
	end
	return data end))
T(sp1:install_read_tap(0xfc1c48, 0xfc1c5b, "fb", function (off, data, mask)
	n.fb = n.fb + 1 ; return data end))
T(sp1:install_read_tap(0x604800, 0x604909, "rr", function (off, data, mask)
	n.ring_r = n.ring_r + 1 ; return data end))
T(sp1:install_write_tap(0x604800, 0x604909, "rw", function (off, data, mask)
	n.ring_w = n.ring_w + 1 ; return data end))
T(sp1:install_write_tap(0x7c0000, 0x7c0001, "w1", function (o, d, k) n.w1 = n.w1 + 1 ; return d end))
T(sp1:install_read_tap (0x7c0000, 0x7c0001, "r1", function (o, d, k) n.r1 = n.r1 + 1 ; return d end))
T(sp2:install_write_tap(0x100000, 0x100001, "w2", function (o, d, k) n.w2 = n.w2 + 1 ; return d end))
T(sp2:install_read_tap (0x100000, 0x100001, "r2", function (o, d, k) n.r2 = n.r2 + 1 ; return d end))
-- CPU 2's microcode-upload timeout flag
T(sp2:install_write_tap(0x00f35c, 0x00f35d, "tmo", function (o, d, k)
	if (k & 0xff) ~= 0 and (d & 0xff) ~= 0 then n.tmo = n.tmo + 1 end ; return d end))
_G.wsa1_dsprdy_taps = taps

-- ---- snapshots + report ---------------------------------------------------
local ats = {}
for s in (os.getenv("SNAP_AT") or "30,45,95"):gmatch("[^,]+") do ats[#ats+1] = tonumber(s) end
table.sort(ats)
local next_at = 1

local function report(tag)
	local name = {}
	for a = 0x810, 0x820 do
		local v = ansbuf[a]
		name[#name+1] = v and ((v >= 0x20 and v < 0x7f) and string.format("%c", v) or ".") or "?"
	end
	emu.print_error(string.format(
		"DSPRDY t=%5.1f fake=%s p9reads=%d uploadTimeouts=%d | req=%d ansbuf=%d fallbackReads=%d ring r=%d w=%d | wire cpu1 w=%d r=%d cpu2 w=%d r=%d | 0x810='%s'",
		now(), tostring(FAKE), n_p9, n.tmo, n.req, n.ans, n.fb, n.ring_r, n.ring_w,
		n.w1, n.r1, n.w2, n.r2, table.concat(name)))
end

_G.wsa1_dsprdy_rep = emu.add_machine_frame_notifier(function ()
	if next_at > #ats then return end
	if now() < ats[next_at] then return end
	m.video:snapshot()
	report()
	next_at = next_at + 1
	if next_at > #ats then m:exit() end
end)
