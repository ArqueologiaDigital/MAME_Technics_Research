-- Where does `Sound Name *****` come from, and how far does the real name get?
-- (SX-WSA1R, 2026-08-27)
--
-- QUESTION IT ANSWERS: the SOUND MODE screen prints the ROM fallback string at
-- prom_a 0xFC1C49 ("Sound Name *****", 16 bytes, no terminator).  prom_a says
-- exactly one instruction can put that pointer in front of the text service:
--
--     sub_FC1B81   ...
--       0xFC1B8E   ld XIY,0x00000800          request/answer buffer
--       0xFC1B93   call sub_FC1BB9            build {0x80, W, 0x04, A, 0, 0}
--                                             and post it on link stream 0
--       0xFC1B97   ld DE,0x11 ; ld C,0x00
--       0xFC1B9C   call sub_FC1BDC            collect the answer
--       0xFC1BA6   cp XIY,0xffffffff
--       0xFC1BAC   jr NZ,+5
--       0xFC1BAE   ld XIY,0x00fc1c49   <----  THE FALLBACK
--
-- sub_FC1BDC (0xFC1BDC) reads the answer one byte at a time through
-- Ring60480A_Get (prom_b slot T_F41CF4 -> prom_a 0xF84382, ring at 0x604800).
-- It first re-syncs on the SIX bytes of the request being echoed back
-- (`cp (XIX),A` at 0xFC1BF5), then copies DE = 0x11 = 17 bytes to 0x000810.
-- sub_FC1C29 gives up after 0xFFFF empty polls and returns XIY = -1.
--
-- So there are exactly four possible stopping points, and this probe separates
-- them by watching DATA accesses only (opcode fetches go through the CPU cache
-- and are not reliably tappable):
--
--   1. the request is never built        -> no write of 0x80 to 0x000800
--   2. the request never leaves CPU 1    -> no 0x05 0x80 .. on the 0x7C0000 wire
--   3. the answer never comes back       -> nothing put in ring 0x604800
--   4. the answer comes back but is rejected by the echo re-sync
--                                        -> ring traffic, but 0x000810 stays put
--
-- Counters, and why each is exact:
--   0x000800 writes   sub_FC1BB9 is the only code that stores 0x80 there
--                     (`ld (XIY),0x80` with XIY = 0x800).
--   0x000810..0x820   the 17-byte answer buffer; a write means step 4 passed.
--   0xFC1C48..0xFC1C5B / 0xFC1CC0..0xFC1CD3 reads = the fallback strings being
--                     FETCHED, with CURPC, which names the consumer.
--   0x604800..0x604909 = ring accesses (control block + 0x100 data bytes).
--   0x7C0000 writes / reads = the CPU 1 side of the wire; 0x100000 writes /
--                     reads = the CPU 2 side.
--
-- Run:
--   cd ~/compartilhado/kn7000_mame_build
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 100 -window \
--       -autoboot_delay 1 -snapshot_directory <dir> \
--       -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_soundname_path.lua
--
-- ⚠ every tap handle is held in a global: MAME's Lua GC silently collects taps
-- kept only in a local.

local m   = manager.machine
local sp1 = m.devices[":cpu1"].spaces["program"]
local sp2 = m.devices[":cpu2"].spaces["program"]
local taps = {}
local function T(t) taps[#taps+1] = t end
local function now() return m.time:as_double() end
local function pc1() return m.devices[":cpu1"].state["CURPC"].value end

local log, LOGMAX = {}, 500
local function ev(fmt, ...)
	if #log < LOGMAX then log[#log+1] = string.format("t=%10.5f  " .. fmt, now(), ...) end
end

local n = { req = 0, ans = 0, fb_sound = 0, fb_combi = 0,
            ring_r = 0, ring_w = 0, w1 = 0, r1 = 0, w2 = 0, r2 = 0 }

-- byte-lane helper for the 16-bit spaces
local function lanes(off, data, mask, fn)
	for lane = 0, 1 do
		if ((mask >> (lane * 8)) & 0xff) ~= 0 then
			fn((off & ~1) | lane, (data >> (lane * 8)) & 0xff)
		end
	end
end

-- 1. the request buffer at 0x000800..0x000805 -------------------------------
T(sp1:install_write_tap(0x000800, 0x000807, "req", function (off, data, mask)
	lanes(off, data, mask, function (a, v)
		if a == 0x800 and v == 0x80 then n.req = n.req + 1 end
		ev("REQ  (0x%04X) := 0x%02X   pc=%06X", a, v, pc1())
	end)
	return data
end))

-- 2. the 17-byte answer buffer at 0x000810..0x000820 ------------------------
T(sp1:install_write_tap(0x000810, 0x000821, "ans", function (off, data, mask)
	lanes(off, data, mask, function (a, v)
		n.ans = n.ans + 1
		ev("ANS  (0x%04X) := 0x%02X %s pc=%06X", a, v,
		   (v >= 0x20 and v < 0x7f) and string.format("'%c'", v) or "   ", pc1())
	end)
	return data
end))

-- 3. the two ROM fallback strings -------------------------------------------
T(sp1:install_read_tap(0xfc1c48, 0xfc1c5b, "fbs", function (off, data, mask)
	n.fb_sound = n.fb_sound + 1
	if n.fb_sound <= 8 then ev("FALLBACK Sound Name read @0x%06X  pc=%06X", off, pc1()) end
	return data
end))
T(sp1:install_read_tap(0xfc1cc0, 0xfc1cd3, "fbc", function (off, data, mask)
	n.fb_combi = n.fb_combi + 1
	if n.fb_combi <= 8 then ev("FALLBACK Combi Name read @0x%06X  pc=%06X", off, pc1()) end
	return data
end))

-- 4. ring 0x604800 -----------------------------------------------------------
T(sp1:install_read_tap(0x604800, 0x604909, "ringr", function (off, data, mask)
	n.ring_r = n.ring_r + 1 ; return data end))
T(sp1:install_write_tap(0x604800, 0x604909, "ringw", function (off, data, mask)
	n.ring_w = n.ring_w + 1
	if n.ring_w <= 40 then
		lanes(off, data, mask, function (a, v) ev("RING (0x%06X) := 0x%02X  pc=%06X", a, v, pc1()) end)
	end
	return data end))

-- 5. both ends of the wire ---------------------------------------------------
local wire1, wire2 = {}, {}
T(sp1:install_write_tap(0x7c0000, 0x7c0001, "w1", function (off, data, mask)
	n.w1 = n.w1 + 1 ; if #wire1 < 900 then wire1[#wire1+1] = data & 0xff end ; return data end))
T(sp1:install_read_tap(0x7c0000, 0x7c0001, "r1", function (off, data, mask)
	n.r1 = n.r1 + 1 ; return data end))
T(sp2:install_write_tap(0x100000, 0x100001, "w2", function (off, data, mask)
	n.w2 = n.w2 + 1 ; if #wire2 < 900 then wire2[#wire2+1] = data & 0xff end ; return data end))
T(sp2:install_read_tap(0x100000, 0x100001, "r2", function (off, data, mask)
	n.r2 = n.r2 + 1 ; return data end))

_G.wsa1_sn_taps = taps

local function dump(name, t)
	local out = {}
	for i = 1, #t do
		out[#out+1] = string.format("%02X", t[i])
		if i % 32 == 0 then
			emu.print_error(string.format("%s[%4d] %s", name, i - 32, table.concat(out, " ")))
			out = {}
		end
	end
	if #out > 0 then
		emu.print_error(string.format("%s[%4d] %s", name, #t - #out, table.concat(out, " ")))
	end
end

local AT = tonumber(os.getenv("REPORT_AT") or "95")
_G.wsa1_sn_rep = emu.add_machine_frame_notifier(function ()
	if _G.wsa1_sn_done or now() < AT then return end
	_G.wsa1_sn_done = true
	emu.print_error("======== SOUND NAME PATH, t=" .. string.format("%.1f", now()) .. " ========")
	for i = 1, #log do emu.print_error(log[i]) end
	emu.print_error(string.format(
		"COUNTS  req0x80=%d  ansbuf_writes=%d  fallback_sound_reads=%d  fallback_combi_reads=%d",
		n.req, n.ans, n.fb_sound, n.fb_combi))
	emu.print_error(string.format(
		"COUNTS  ring604800 r=%d w=%d   wire cpu1 w=%d r=%d   cpu2 w=%d r=%d",
		n.ring_r, n.ring_w, n.w1, n.r1, n.w2, n.r2))
	dump("CPU1->CPU2", wire1)
	dump("CPU2->CPU1", wire2)
	if os.getenv("SNAP") then m.video:snapshot() end
	m:exit()
end)
