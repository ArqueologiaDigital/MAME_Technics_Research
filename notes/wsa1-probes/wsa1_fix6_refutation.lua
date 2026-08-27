-- Adversarial re-check of the "OVERLAY FIX 6" report (SX-WSA1R, 2026-08-27).
--
-- QUESTION IT ANSWERS: with the FIX 6 x perfect_quantum grid switched at run
-- time (notes/wsa1-probes/wsa1_fix6_ab.patch: TLCS_NO_FIX6 / WSA1_NO_PQ), which
-- of the two changes actually moves the link, and does FIX 6 cost any OTHER
-- interrupt its dispatches?
--
-- EVERY COUNTER IS DISPATCH- OR ADDRESS-EXACT, and none of them is a tap on a
-- routine entry (RDOP() prefetches m_pc+3, tlcs900.cpp:81-99, so an entry tap
-- fires three bytes early and aliases the routine before it):
--   * an interrupt dispatch is the ONLY thing that reads the vector table
--     (m_pc.d = RDMEML(0xffff00 + vector)), so a read tap on one table entry is
--     an exact per-vector dispatch counter, on either CPU.  Verified against the
--     ROM: 0xFFFF28 -> jp 0xF8E47F (INT0_LinkByte), 0xFFFF80 -> jp 0xF8E54F
--     (INTTC3_LinkDmaDone), 0xFFFF7C -> jp 0xF8E52D (INTTC2).
--   * INTTC3 entries are ALSO counted as reads of the selector word 0x6007DA,
--     which `ld BC,(0x6007da)` at 0xF8E555 reads unconditionally two
--     instructions into the handler.  The two must agree.
--   * DMA0V..DMA3V are told apart by byte address (0x7C..0x7F), on both CPUs,
--     and every armed VALUE is recorded: (v & 0x1F) << 2 outside 0x28..0x70 is
--     a vector FIX 6 masks but tlcs900_process_hdma() refuses to serve.
--
-- Run (from ~/compartilhado/kn7000_mame_build):
--   [TLCS_NO_FIX6=1] [WSA1_NO_PQ=1] DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms \
--       -skip_gameinfo -str 100 -window -autoboot_delay 1 \
--       -autoboot_script .../wsa1_fix6_refutation.lua
local m   = manager.machine
local sp1 = m.devices[":cpu1"].spaces["program"]
local sp2 = m.devices[":cpu2"].spaces["program"]
local taps = {}
local function T(t) taps[#taps+1] = t end

local VEC = { [0x28]="INT0", [0x38]="INT7", [0x74]="INTTC0", [0x78]="INTTC1",
              [0x7c]="INTTC2", [0x80]="INTTC3", [0x48]="INTT2", [0x34]="INT6" }

local disp = { cpu1 = {}, cpu2 = {} }
for v,_ in pairs(VEC) do disp.cpu1[v] = 0 ; disp.cpu2[v] = 0 end

local function vec_taps(sp, who)
	for v,_ in pairs(VEC) do
		-- the dispatch does RDMEML(0xffff00+v): a 4-byte read starting at the
		-- entry.  Tap only the FIRST byte so one dispatch counts once.
		-- ⚠ a tap on a 16-bit space must END on an odd address, so the range is
		-- the vector's low WORD (bytes +0/+1).  RDMEML(0xffff00+v) is a dword
		-- read = two word accesses, at +0 and +2, so this fires exactly once per
		-- dispatch and never overlaps the neighbouring vector four bytes away.
		T(sp:install_read_tap(0xffff00 + v, 0xffff01 + v, "v", function (off, data, mask)
			disp[who][v] = disp[who][v] + 1 ; return data end))
	end
end
vec_taps(sp1, "cpu1")
vec_taps(sp2, "cpu2")

-- DMAnV arms, per CPU, per register, per value
local arms = { cpu1 = {}, cpu2 = {} }
local function dmav_tap(sp, who)
	T(sp:install_write_tap(0x00007c, 0x00007f, "dmav", function (off, data, mask)
		local lo  = (mask & 0x00ff) ~= 0
		local reg = (off & ~1) | (lo and 0 or 1)
		local val = lo and (data & 0xff) or ((data >> 8) & 0xff)
		local k = string.format("DMA%dV=0x%02X", reg - 0x7c, val)
		arms[who][k] = (arms[who][k] or 0) + 1
		return data
	end))
end
dmav_tap(sp1, "cpu1")
dmav_tap(sp2, "cpu2")

-- the two one-byte latches
local c1_rd, c1_wr, c2_rd, c2_wr, sel_rd = 0, 0, 0, 0, 0
local sel_hist = {}
T(sp1:install_read_tap (0x7c0000, 0x7c0001, "c1r", function (o,d,k) c1_rd = c1_rd + 1 ; return d end))
T(sp1:install_write_tap(0x7c0000, 0x7c0001, "c1w", function (o,d,k) c1_wr = c1_wr + 1 ; return d end))
T(sp2:install_read_tap (0x100000, 0x100001, "c2r", function (o,d,k) c2_rd = c2_rd + 1 ; return d end))
T(sp2:install_write_tap(0x100000, 0x100001, "c2w", function (o,d,k) c2_wr = c2_wr + 1 ; return d end))
T(sp1:install_read_tap (0x6007da, 0x6007db, "sel", function (o,d,k)
	sel_rd = sel_rd + 1
	local v = d & 0xffff ; sel_hist[v] = (sel_hist[v] or 0) + 1 ; return d end))

_G.wsa1_fix6_taps = taps

local AT = tonumber(os.getenv("REPORT_AT") or "95")
local done = false
_G.wsa1_fix6_rep = emu.add_machine_frame_notifier(function ()
	if done or m.time:as_double() < AT then return end
	done = true
	local P = emu.print_error
	P("================ FIX6 REFUTATION ================")
	P(string.format("ENV     TLCS_NO_FIX6=%s  WSA1_NO_PQ=%s  t=%.1f",
		tostring(os.getenv("TLCS_NO_FIX6")), tostring(os.getenv("WSA1_NO_PQ")), m.time:as_double()))
	for _,who in ipairs({"cpu1","cpu2"}) do
		local t = {}
		for v,n in pairs(VEC) do t[#t+1] = string.format("%s(0x%02X)=%d", n, v, disp[who][v]) end
		table.sort(t)
		P(string.format("DISPATCH %s  %s", who, table.concat(t, " ")))
	end
	for _,who in ipairs({"cpu1","cpu2"}) do
		local t = {} ; for k,v in pairs(arms[who]) do t[#t+1] = k .. " x" .. v end
		table.sort(t)
		P(string.format("ARMS     %s  %s", who, table.concat(t, "  ")))
	end
	P(string.format("LINK     cpu2->cpu1: written=%d read=%d   cpu1->cpu2: written=%d read=%d",
		c2_wr, c1_rd, c1_wr, c2_rd))
	local t = {} ; for k,v in pairs(sel_hist) do t[#t+1] = string.format("sel%d:%d", k, v) end
	table.sort(t)
	P(string.format("INTTC3   selector reads (0x6007DA) = %d   %s", sel_rd, table.concat(t, " ")))
	P("================ END ================")
end)
