-- Capture (p18, aux, voice-record note) triples while the auto-accompaniment plays.
--
-- WHY THIS NOTE SOURCE
--   Two earlier acquisition attempts produced no usable rows, and each ruled a route
--   out rather than leaving it a suspicion:
--     * DEMO -- the KN7000's demo is a picture slideshow. 256 pitch writes, all
--       p18=0 across exactly 128 slots: the boot-time clear of every voice.
--     * the KEY BED -- a read tap on the voice-event FIFO at 0x98050004 counted
--       ZERO reads across six key presses while the firmware issued 12458 TG data
--       writes. The firmware simply never polls that FIFO in this state, so no key
--       press can become a note.
--   The machine's own rhythm accompaniment does not need either path.
--
-- WHAT IS BEING TESTED
--   The driver resolves a note-on's pitch by reading the firmware's voice record out
--   of CPU RAM. If the record's note is an affine function of what the chip is TOLD
--   -- p18, and the bank/zone carried in the aux word -- the lookup is redundant.
--   Prediction from the driver's own fallback:  np16 = 24576 + (p18 - 0x1C838)/4.
--   The residual from that is what the lookup actually supplies.
--
--   Rows are only kept when the record is ACTIVE (+0x08 bit7). An inactive record
--   reads as zeros, and a fit over zeros is perfect and meaningless.
--
-- ENV  RP_OUT (required)  RP_BASE (default 0x500AF940)  RP_START (default 55)
--      RP_UNTIL (default 170)

local mac  = manager.machine
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]

RP = RP or {}
RP.out   = assert(os.getenv("RP_OUT"), "RP_OUT not set")
RP.base  = tonumber(os.getenv("RP_BASE") or "0x500AF940")
RP.rows, RP.aux, RP.addr = {}, {}, {0, 0}
RP.n, RP.kept = 0, 0

local function tap(base, tg)
	prog:install_write_tap(base, base + 3, "rp" .. tg, function(off, data, mask)
		if (mask & 0x0000ffff) ~= 0 then RP.addr[tg + 1] = data & 0xffff end
		if (mask & 0xffff0000) ~= 0 then
			local a = RP.addr[tg + 1]
			local d = (data >> 16) & 0xffff
			if (a & 0xff00) == 0xfc00 then return nil end
			local s, cls = (a >> 4) & 0x3F, a & 0xFC0F
			local v = (tg << 6) | s
			if cls == 0x1C02 then
				RP.aux[v] = d
			elseif (a & 0xFC0E) == 0x2400 then
				RP.n = RP.n + 1
				local slot = (tg == 0) and (s | 0x40) or s
				local rec  = RP.base + slot * 0xB4
				local act  = prog:read_u8(rec + 0x08)
				if (act & 0x80) ~= 0 then
					local np16 = prog:read_u16(rec + 0x0C)
					local rt   = prog:read_u16(rec + 0x02) & 0x7C
					local aux  = RP.aux[v] or 0
					local p18  = ((a & 1) << 16) | d
					RP.kept = RP.kept + 1
					RP.rows[#RP.rows + 1] = string.format("%d\t%d\t%d\t%d\t%04X\t%d\t%d\t%d\t%d",
						tg, slot, v, p18, aux, (aux >> 12) & 3, aux & 0xFF, np16, rt)
				end
			end
		end
		return nil
	end)
end
tap(0x98040000, 0)
tap(0x98050000, 1)

local acts, ai = {}, 1
local function at(t, fn) acts[#acts + 1] = { t = t, fn = fn } end
local function press(t, tag, mask)
	at(t, function ()
		local p = mac.ioport.ports[tag]
		if p then for _, f in pairs(p.fields) do if f.mask == mask then f:set_value(1) end end end
	end)
	at(t + 0.35, function ()
		local p = mac.ioport.ports[tag]
		if p then for _, f in pairs(p.fields) do if f.mask == mask then f:clear_value() end end end
	end)
end

local T = tonumber(os.getenv("RP_START") or "55")
press(T,       ":cpanel:CPL_SEG2", 0x80)   -- 8 & 16 BEAT rhythm group
press(T + 3.0, ":cpanel:CPL_SEG0", 0x10)   -- START/STOP
for k = 1, 12 do
	at(T + 5.0 + k * 8.0, function ()
		emu.print_error(string.format("RHYTHM PROBE: t=%.0f  %d pitch writes, %d with an ACTIVE record",
			T + 5.0 + k * 8.0, RP.n, RP.kept))
	end)
end
local U = tonumber(os.getenv("RP_UNTIL") or "170")
at(U - 1.0, function () mac.video:snapshot() end)
at(U, function ()
	local f = io.open(RP.out, "w")
	f:write("tg\tslot\tv\tp18\taux\tbank\tzone\tnp16\trectype\n")
	f:write(table.concat(RP.rows, "\n") .. "\n")
	f:close()
	emu.print_error(string.format("RHYTHM PROBE FINAL: %d pitch writes, %d kept -> %s", RP.n, RP.kept, RP.out))
	mac:exit()
end)

RP.timer = emu.register_periodic(function ()
	local now = mac.time.seconds + mac.time.attoseconds / 1e18
	while ai <= #acts and now >= acts[ai].t do local a = acts[ai]; ai = ai + 1; a.fn() end
end)
