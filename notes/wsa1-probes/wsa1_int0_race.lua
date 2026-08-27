-- Is CPU 1's INT0 request LOST when the link's second byte arrives?
-- (SX-WSA1R, 2026-08-27 -- follow-up to wsa1_udma3_audit.lua)
--
-- wsa1_udma3_audit.lua measured the whole receive path and found ONE exchange in
-- a 100 s boot, at t = 70.843:
--     CPU2 -> 0xC0 ; CPU 1 reads the port ; selector := 1 ; DMA3V := 0x0A ;
--     P7 bit 1 low ; CPU2 -> 0xFB   ... and then nothing at all.
-- DMAC3 stays at its armed value (1) for twelve Link_ServiceTask samples and the
-- watchdog aborts the receive at t = 72.012.  So the payload byte 0xFB was put
-- in the latch and the micro-DMA engine never fetched it -- CPU 1's whole run
-- contains exactly ONE read of 0x7C0000.
--
-- tlcs900_process_hdma() only moves a byte when the channel's TRIGGER FLIP-FLOP
-- is set; for DMA3V = 0x0A that is INTE0AD bit 3, INT0's own request bit
-- (tmp95c061.cpp:353-366).  This probe reads INTE0AD -- SFR 0x70, readable
-- through inte_r, tmp95c061.cpp:184 -- across the wedge, which separates the two
-- possible causes:
--
--   bit 3 CLEAR  -> the request was never delivered or was cancelled.  The
--                   suspect is the driver: cpu1_link_r() calls
--                   set_input_line(CLEAR_LINE), which is QUEUED, and CPU 2's
--                   next write queues an ASSERT behind it.
--   bit 3 SET    -> the request is there and the DMA engine is not acting on
--                   it, i.e. tlcs900_check_hdma()'s `(m_sr.b.h & 0x70) != 0x70`
--                   guard, or DMA3V, is the blocker.
--
-- Run:
--   cd ~/compartilhado/kn7000_mame_build
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 75 -window \
--       -autoboot_delay 1 \
--       -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_int0_race.lua

local m    = manager.machine
local cpu1 = m.devices[":cpu1"]
local cpu2 = m.devices[":cpu2"]
local sp1  = cpu1.spaces["program"]
local sp2  = cpu2.spaces["program"]
local taps = {}

local function now() return m.time:as_double() end
local function inte0ad() return sp1:read_u8(0x70) end
local function dmac3()   return cpu1.state["DMAC3"].value end
local function dmas3()   return cpu1.state["DMAS3"].value end
local function dmad3()   return cpu1.state["DMAD3"].value end
local function dmam3()   return cpu1.state["DMAM3"].value end

local out = {}
local function P(fmt, ...)
	local s = string.format(fmt, ...)
	out[#out+1] = s
	emu.print_error(s)
end
local function snap(tag)
	local e = inte0ad()
	P("t=%8.4f %-22s INTE0AD=0x%02X (INT0 req bit3=%d, level=%d)  DMAC3=%d "
	  .. "DMAS3=%06X DMAD3=%06X DMAM3=%02X",
	  now(), tag, e, (e >> 3) & 1, e & 7, dmac3(), dmas3(), dmad3(), dmam3())
end

taps[#taps+1] = sp2:install_write_tap(0x100000, 0x100001, "c2w", function (off, data, mask)
	P("t=%8.4f CPU2 WRITES 0x%02X to the latch", now(), data & 0xff)
	snap("  before cpu1 sees it")
	return data
end)
taps[#taps+1] = sp1:install_read_tap(0x7c0000, 0x7c0001, "c1r", function (off, data, mask)
	P("t=%8.4f CPU 1 READS the latch -> 0x%02X", now(), data & 0xff)
	return data
end)
taps[#taps+1] = sp1:install_write_tap(0x00007c, 0x00007f, "dmav", function (off, data, mask)
	local lo  = (mask & 0x00ff) ~= 0
	local reg = (off & ~1) | (lo and 0 or 1)
	if reg == 0x7f then
		P("t=%8.4f DMA3V := 0x%02X", now(), lo and (data & 0xff) or ((data >> 8) & 0xff))
		snap("  at the arm")
	end
	return data
end)
_G.wsa1_race_taps = taps

-- sample across the wedge
local last = -1
_G.wsa1_race_sampler = emu.add_machine_frame_notifier(function ()
	local t = now()
	if t < 70.0 or t > 73.5 then return end
	local n = math.floor(t * 20)         -- 20 samples a second
	if n == last then return end
	last = n
	snap("sample")
end)
