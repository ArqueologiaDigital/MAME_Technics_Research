-- Does CPU 1's CPU steal the link byte that micro-DMA channel 3 was armed for?
-- (SX-WSA1R, 2026-08-27 -- third probe in the "Sound Name *****" chain)
--
-- ESTABLISHED by wsa1_udma3_audit.lua and wsa1_int0_race.lua:
--   * INTTC3_LinkDmaDone never runs -- not twelve times, ZERO times;
--   * exactly one message is received all boot, at t = 70.843: header 0xC0,
--     channel 3 armed DMAC3=1 DMAD3=0x6007B3 DMAS3=0x7C0000 DMAM3=0x00,
--     DMA3V = 0x0A;
--   * CPU 2 then writes the payload byte 0xFB into the latch and NOBODY EVER
--     READS IT: CPU 1's whole run contains one read of 0x7C0000;
--   * across the entire wedge INTE0AD reads 0x81 -- bit 3, INT0's request
--     flip-flop and the channel's trigger, is CLEAR.
--
-- So the request was raised and then consumed by something that was not the DMA
-- engine.  The only other consumer is tlcs900_check_irqs(), which dispatches
-- INT0 to the CPU and clears the same bit -- and it runs at the TOP of
-- execute_run()'s loop while tlcs900_check_hdma() runs at the BOTTOM
-- (tlcs900.cpp:283-327).  Neither function looks at m_dma_vector[], so nothing
-- in this core gives micro-DMA priority over the CPU for a shared vector.
--
-- THE EXACT COUNTER THIS PROBE USES: an interrupt dispatch is the ONLY thing
-- that reads the vector table.  tlcs900_check_irqs() does
-- `m_pc.d = RDMEML(0xffff00 + vector)` (tmp95c061.cpp:604), so a read tap on
-- 0xFFFF28-0xFFFF2B counts INT0 dispatches TO THE CPU exactly, with no
-- prefetch aliasing -- unlike a tap on a handler's entry byte, which RDOP()'s
-- four-byte prefetch window makes ambiguous.  0xFFFF7C and 0xFFFF80 do the same
-- for INTTC2 and INTTC3.
--
-- PREDICTION IF THE STEAL IS REAL: two reads of 0xFFFF28, the second one AFTER
-- CPU 2's payload write, with no read of 0x7C0000 following it -- because
-- INT0_LinkByte's first act is `bit 2,(P7)` at 0xF8E489 and it returns without
-- touching the port when that bit is set.
--
-- Run:
--   cd ~/compartilhado/kn7000_mame_build
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 74 -window \
--       -autoboot_delay 1 \
--       -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_int0_steal.lua

local m    = manager.machine
local cpu1 = m.devices[":cpu1"]
local sp1  = cpu1.spaces["program"]
local sp2  = m.devices[":cpu2"].spaces["program"]
local taps = {}

local function now() return m.time:as_double() end
local function P(fmt, ...) emu.print_error(string.format(fmt, ...)) end
local function ctx()
	-- P7 (0x13) reads back the driven bits plus CPU 2's PA0/PA1 (cpu1_p7_r);
	-- INTE0AD (0x70) bit 3 is INT0's request flip-flop.
	local p7 = sp1:read_u8(0x13)
	local e  = sp1:read_u8(0x70)
	return string.format("P7=0x%02X(b1=%d b2=%d b3=%d) INTE0AD=0x%02X(req=%d) DMAC3=%d",
		p7, (p7>>1)&1, (p7>>2)&1, (p7>>3)&1, e, (e>>3)&1, cpu1.state["DMAC3"].value)
end

local n = {}
local function bump(k) n[k] = (n[k] or 0) + 1 ; return n[k] end

local VEC = {[0xffff28]="INT0", [0xffff7c]="INTTC2", [0xffff80]="INTTC3",
             [0xffff48]="INTT2", [0xffff44]="INTT1"}
for base, name in pairs(VEC) do
	taps[#taps+1] = sp1:install_read_tap(base, base + 3, "v" .. name,
		function (off, data, mask)
			if off ~= base then return data end          -- one line per dispatch
			local c = bump(name)
			if now() > 69.0 or name == "INT0" or name == "INTTC3" then
				P("t=%8.4f  DISPATCH %-6s #%d   %s", now(), name, c, ctx())
			end
			return data
		end)
end

taps[#taps+1] = sp2:install_write_tap(0x100000, 0x100001, "c2w", function (off, data, mask)
	P("t=%8.4f  CPU2 -> latch 0x%02X   (#%d)", now(), data & 0xff, bump("c2w")) ; return data
end)
taps[#taps+1] = sp1:install_read_tap(0x7c0000, 0x7c0001, "c1r", function (off, data, mask)
	P("t=%8.4f  CPU1 reads latch -> 0x%02X   (#%d)  %s", now(), data & 0xff, bump("c1r"), ctx())
	return data
end)
taps[#taps+1] = sp1:install_write_tap(0x00007c, 0x00007f, "dmav", function (off, data, mask)
	local lo = (mask & 0x00ff) ~= 0
	if (((off & ~1) | (lo and 0 or 1)) == 0x7f) then
		P("t=%8.4f  DMA3V := 0x%02X   %s", now(),
			lo and (data & 0xff) or ((data >> 8) & 0xff), ctx())
	end
	return data
end)
_G.wsa1_steal_taps = taps

local done = false
_G.wsa1_steal_rep = emu.add_machine_frame_notifier(function ()
	if done or m.time.seconds < 73 then return end
	done = true
	P("======== dispatch totals ========")
	local k = {} ; for a, _ in pairs(n) do k[#k+1] = a end ; table.sort(k)
	for _, a in ipairs(k) do P("  %-8s %d", a, n[a]) end
end)
