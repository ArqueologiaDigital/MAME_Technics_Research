-- Why does micro-DMA channel 3 "complete twelve times" when no link message is
-- in flight?  (SX-WSA1R, 2026-08-27)
--
-- The claim under test comes from wsa1_link_stage.lua, which reported
--   INT0_LinkByte 2 runs / DMA3V 11 writes / INTTC3_LinkDmaDone 12 runs.
-- Every one of those three counters was read through a tap whose range covers
-- more than the thing it names:
--   * a read tap on 0xF8E54E-0xF8E54F names INTTC3's entry byte (0xF8E54F) but
--     also covers INTTC2_uDMA2Done's `reti` (0xF8E54E) -- and RDOP() prefetches
--     m_pc+3 (tlcs900.cpp:81-99), so executing INTTC2's LAST FOUR BYTES already
--     reads 0xF8E54F;
--   * a read tap on 0xF8E47E-0xF8E47F does the same to INT0_LinkByte;
--   * a write tap on 0x7E-0x7F covers DMA2V (0x7E) as well as DMA3V (0x7F), and
--     the transmit block writes `ldio DMA2V,0x12` from nine different sites.
--
-- This probe measures the same three quantities WITHOUT range aliasing, in the
-- same run as the old ones, so the two can be compared directly.
--
-- EXACT counters used here, and why each is exact:
--   INTTC3 entries  = reads of the selector word (0x6007DA).  `ldw_da bc,
--                     (0x6007da)` at 0xF8E555 is the ONLY read of that address
--                     in prom_a, prom_b or prom_c -- proved by
--                     wsa1_udma3_xref.py, which lists all twelve references.
--   DMA3V writes    = writes whose byte address is 0x7F, told apart from 0x7E
--                     by the tap's offset.
--   channel-3 bytes = reads of the link port 0x7C0000.  Micro-DMA goes through
--                     the address space (RDMEM -> m_program->read_byte), so the
--                     tap sees CPU reads and DMA reads alike; the CPU reads it
--                     exactly once per message, at 0xF8E494.
--   DMAC3 samples   = writes of (0x6007DF).  Link_ServiceTask stores the live
--                     DMAC3 there every pass (0xF8E63F call uDMA3_GetCount ->
--                     0xF8E643 stw_da), which is the only window onto a control
--                     register that no memory tap can see.
--
-- Run:
--   cd ~/compartilhado/kn7000_mame_build
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 100 -window \
--       -autoboot_delay 1 \
--       -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_udma3_audit.lua

local m    = manager.machine
local sp1  = m.devices[":cpu1"].spaces["program"]
local sp2  = m.devices[":cpu2"].spaces["program"]
local taps = {}
local function T(t) taps[#taps+1] = t end

local function now() return m.time:as_double() end

-- ---------------------------------------------------------------- event log
local log, LOGMAX = {}, 400
local function ev(fmt, ...)
	if #log < LOGMAX then log[#log+1] = string.format("t=%7.3f  " .. fmt, now(), ...) end
end

-- ------------------------------------------------------- exact counters ----
local n_dmav      = {[0x7c]=0, [0x7d]=0, [0x7e]=0, [0x7f]=0}
local dmav_vals   = {}                     -- "reg=val" -> count
local n_inttc3    = 0
local sel_hist    = {}                     -- selector value -> count
local n_port_rd   = 0                      -- every consumer of CPU 1's inbound latch
local n_port_wr   = 0
local wr_bytes    = {}
local n_dst_e2    = 0                      -- writes into 0x600788..0x600791
local n_dst_e1    = 0                      -- writes into 0x6007D3..0x6007D8
local n_dst_gen   = 0                      -- writes into 0x6007B3..0x6007D2
local dmac3       = {}                     -- (0x6007DF) samples, in order
local dmac3_lo    = nil                    -- low half, see the tap below
local counters    = {}                     -- 0x6007DB/DC/E1 last value
local p7_writes   = 0
local p7_last     = -1
local p7_bit1_lo  = nil                    -- time bit 1 last went low and stayed
local n_cpu2_wr   = 0                      -- = INT0 assertions on CPU 1
local n_cpu2_rd   = 0

-- ---------------------------------------------- legacy (aliased) counters --
local a_int0, a_inttc3, a_dma3v = 0, 0, 0

-- ================================================================= taps ====

-- DMA0V..DMA3V, told apart by byte address
T(sp1:install_write_tap(0x00007c, 0x00007f, "dmav", function (off, data, mask)
	local lo = (mask & 0x00ff) ~= 0
	local reg = (off & ~1) | (lo and 0 or 1)
	local val = lo and (data & 0xff) or ((data >> 8) & 0xff)
	n_dmav[reg] = (n_dmav[reg] or 0) + 1
	local k = string.format("DMA%dV=0x%02X", reg - 0x7c, val)
	dmav_vals[k] = (dmav_vals[k] or 0) + 1
	ev("ARM   %s", k)
	if reg == 0x7e or reg == 0x7f then a_dma3v = a_dma3v + 1 end
	return data
end))

-- INTTC3 entry + its selector: the one read of 0x6007DA
T(sp1:install_read_tap(0x6007da, 0x6007db, "sel", function (off, data, mask)
	n_inttc3 = n_inttc3 + 1
	local v = data & 0xffff
	sel_hist[v] = (sel_hist[v] or 0) + 1
	ev("INTTC3 selector=%d", v)
	return data
end))

-- the selector's writers and the link's error counters
T(sp1:install_write_tap(0x6007da, 0x6007e1, "linkvars", function (off, data, mask)
	local lo = (mask & 0x00ff) ~= 0
	local a  = (off & ~1) | (lo and 0 or 1)
	local v  = lo and (data & 0xff) or ((data >> 8) & 0xff)
	if a == 0x6007da then ev("SEL:= %d", v)
	elseif a == 0x6007df or a == 0x6007e0 then
		-- `stw_da (0x6007df), wa` (0xF8E643) is a 16-bit store to an ODD address,
		-- so WRMEMW -> write_word_unaligned splits it into two byte writes: the
		-- LOW half at 0x6007DF in the high lane, the HIGH half at 0x6007E0 in the
		-- low lane.  Reassemble, or the log reads 256 where DMAC3 is 1.
		if a == 0x6007df then dmac3_lo = v
		else
			dmac3[#dmac3+1] = (v << 8) | (dmac3_lo or 0)
			ev("DMAC3 sample=%d", dmac3[#dmac3])
		end
	elseif a == 0x6007db or a == 0x6007dc or a == 0x6007e1 then
		counters[a] = v ; ev("ERRCNT 0x%06X := %d", a, v)
	end
	return data
end))

-- CPU 1's inbound latch: CPU reads AND micro-DMA reads both land here
T(sp1:install_read_tap(0x7c0000, 0x7c0001, "portr", function (off, data, mask)
	n_port_rd = n_port_rd + 1
	ev("RD    port -> 0x%02X", data & 0xff)
	return data
end))
T(sp1:install_write_tap(0x7c0000, 0x7c0001, "portw", function (off, data, mask)
	n_port_wr = n_port_wr + 1
	local b = data & 0xff
	wr_bytes[b] = (wr_bytes[b] or 0) + 1
	return data
end))

-- the three micro-DMA channel-3 destination buffers
T(sp1:install_write_tap(0x600788, 0x600791, "dste2", function (off, data, mask)
	n_dst_e2 = n_dst_e2 + 1 ; ev("DMA-> 0x%06X", off) ; return data
end))
T(sp1:install_write_tap(0x6007b2, 0x6007d9, "dstgen", function (off, data, mask)
	local a = off
	if a >= 0x6007d3 and a <= 0x6007d8 then n_dst_e1 = n_dst_e1 + 1
	elseif a <= 0x6007d2 then n_dst_gen = n_dst_gen + 1 end
	return data
end))

-- P7 (0x13): bit 1 is the receiver-busy line
T(sp1:install_write_tap(0x000012, 0x000013, "p7", function (off, data, mask)
	if (mask & 0xff00) == 0 then return data end     -- low lane is P6
	local v = (data >> 8) & 0xff
	p7_writes = p7_writes + 1
	if v ~= p7_last then
		ev("P7:=  0x%02X  (bit1=%d)", v, (v >> 1) & 1)
		if ((v >> 1) & 1) == 0 then p7_bit1_lo = now() else p7_bit1_lo = nil end
		p7_last = v
	end
	return data
end))

-- CPU 2's side of the wire: every write is one INT0 assertion on CPU 1
T(sp2:install_write_tap(0x100000, 0x100001, "c2w", function (off, data, mask)
	n_cpu2_wr = n_cpu2_wr + 1 ; ev("CPU2  -> 0x%02X", data & 0xff) ; return data
end))
T(sp2:install_read_tap(0x100000, 0x100001, "c2r", function (off, data, mask)
	n_cpu2_rd = n_cpu2_rd + 1 ; return data
end))

-- ------------------------------------------- the OLD, aliasing taps, kept --
T(sp1:install_read_tap(0xf8e47e, 0xf8e47f, "old_int0", function (o, d, k)
	a_int0 = a_int0 + 1 ; return d end))
T(sp1:install_read_tap(0xf8e54e, 0xf8e54f, "old_tc3", function (o, d, k)
	a_inttc3 = a_inttc3 + 1 ; return d end))

_G.wsa1_udma3_taps = taps

-- =============================================================== report ====
local done = false
_G.wsa1_udma3_rep = emu.add_machine_frame_notifier(function ()
	if done or m.time.seconds < 95 then return end
	done = true
	local P = emu.print_error
	P("================ uDMA3 AUDIT ================")
	P(string.format("EXACT   DMA0V=%d DMA1V=%d DMA2V=%d DMA3V=%d",
		n_dmav[0x7c], n_dmav[0x7d], n_dmav[0x7e], n_dmav[0x7f]))
	local t = {} ; for k, v in pairs(dmav_vals) do t[#t+1] = k .. " x" .. v end
	table.sort(t) ; P("        arms: " .. table.concat(t, "  "))
	P(string.format("EXACT   INTTC3 entries (reads of 0x6007DA) = %d", n_inttc3))
	t = {} ; for k, v in pairs(sel_hist) do t[#t+1] = string.format("sel%d:%d", k, v) end
	table.sort(t) ; P("        " .. table.concat(t, " "))
	P(string.format("LEGACY  0xF8E47E-7F reads=%d   0xF8E54E-4F reads=%d   0x7E-7F writes=%d",
		a_int0, a_inttc3, a_dma3v))
	P(string.format("PORT    cpu1 reads of 0x7C0000 = %d   cpu1 writes = %d", n_port_rd, n_port_wr))
	t = {} ; for k, v in pairs(wr_bytes) do t[#t+1] = string.format("%02X:%d", k, v) end
	table.sort(t) ; P("        cpu1 sent: " .. table.concat(t, " "))
	P(string.format("PORT    cpu2 writes to 0x100000 = %d (= INT0 asserts on cpu1)   cpu2 reads = %d",
		n_cpu2_wr, n_cpu2_rd))
	P(string.format("DMA DST bytes landed: E2buf=%d  E1hdr=%d  genbuf=%d",
		n_dst_e2, n_dst_e1, n_dst_gen))
	t = {} ; for i = 1, math.min(#dmac3, 40) do t[#t+1] = tostring(dmac3[i]) end
	P(string.format("DMAC3   %d samples via (0x6007DF): %s", #dmac3, table.concat(t, " ")))
	P(string.format("ERRCNT  0x6007DB=%s 0x6007DC=%s 0x6007E1=%s",
		tostring(counters[0x6007db]), tostring(counters[0x6007dc]), tostring(counters[0x6007e1])))
	P(string.format("P7      writes=%d last=0x%02X  bit1 low since %s",
		p7_writes, p7_last & 0xff, tostring(p7_bit1_lo)))
	P("---- event log (first " .. LOGMAX .. ") ----")
	for i = 1, #log do P(log[i]) end
	P("================ END ================")
end)
