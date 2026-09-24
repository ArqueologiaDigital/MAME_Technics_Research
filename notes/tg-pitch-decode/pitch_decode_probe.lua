-- What does the TG pitch register actually encode, and can the musical note be
-- recovered from the REGISTER STREAM alone?
--
-- WHY
--   kn7000.cpp resolves a note-on's musical pitch by reading the firmware's voice
--   record out of CPU work RAM at a hardcoded address (KN7000_VOICE_RECORDS et al).
--   That crosses a chip boundary the hardware does not have, and the constant is a
--   property of the firmware BUILD -- the KN6000 and KN6500 differ by 12 bytes. If
--   the note is recoverable from what the firmware WRITES TO THE CHIP, the lookup
--   can go.
--
-- METHOD
--   Raw-bus write taps on both TGs, so this sees exactly what the chip sees and is
--   unaffected by any driver-side capture gate. Per voice it tracks the aux word
--   (register class 0x1C02, carrying bank/zone) and, on each pitch write (class
--   0x2400, bit0 = p18 bit16), emits one row:
--
--     tg slot v p18 aux bank zone np16 rectype active
--
--   np16/rectype are read from the firmware's own voice record -- the thing we want
--   to stop needing. They are the GROUND TRUTH column here, not an input: the whole
--   question is whether np16 is a function of the other columns.
--
--   The prediction to test is the one the driver's fallback already makes:
--       np16 == 24576 + (p18 - 0x1C838)/4
--   i.e. 1024 pitch18 units per semitone, MIDI 96 at p18 = 0x1C838. Any residual is
--   what the lookup is really supplying; if that residual is a function of
--   (bank, zone) it is recoverable, because bank and zone arrive through registers.
--
-- ENV  PD_OUT   output TSV (required)
--      PD_BASE  voice-record base, default 0x500AF940 (KN7000)
-- RUN  as an -autoboot_script with -str; press DEMO to get a wide voice spread.

local mac  = manager.machine
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]

PD = PD or {}
PD.out  = assert(os.getenv("PD_OUT"), "PD_OUT not set")
PD.base = tonumber(os.getenv("PD_BASE") or "0x500AF940")
PD.rows = {}
PD.aux  = {}
PD.addr = {0, 0}
PD.n    = 0

local function record(slot)
	local rec = PD.base + slot * 0xB4
	local ok, active = pcall(function() return prog:read_u8(rec + 0x08) end)
	if not ok then return nil, nil, 0 end
	local np16 = prog:read_u16(rec + 0x0C)
	local rt   = prog:read_u16(rec + 0x02) & 0x7C
	return np16, rt, ((active & 0x80) ~= 0) and 1 or 0
end

local function tap(base, tg)
	prog:install_write_tap(base, base + 3, "pd" .. tg, function(off, data, mask)
		if (mask & 0x0000ffff) ~= 0 then PD.addr[tg + 1] = data & 0xffff end
		if (mask & 0xffff0000) ~= 0 then
			local a = PD.addr[tg + 1]
			local d = (data >> 16) & 0xffff
			if (a & 0xff00) == 0xfc00 then return nil end      -- idle/status refresh
			local s   = (a >> 4) & 0x3F
			local v   = (tg << 6) | s
			local cls = a & 0xFC0F
			if cls == 0x1C02 then
				PD.aux[v] = d
			elseif (a & 0xFC0E) == 0x2400 then
				local p18  = ((a & 1) << 16) | d
				local slot = (tg == 0) and (s | 0x40) or s
				local np16, rt, active = record(slot)
				if np16 then
					PD.n = PD.n + 1
					local aux = PD.aux[v] or 0
					PD.rows[#PD.rows + 1] = string.format(
						"%d\t%d\t%d\t%d\t%04X\t%d\t%d\t%d\t%d\t%d",
						tg, slot, v, p18, aux, (aux >> 12) & 3, aux & 0xFF, np16, rt, active)
				end
			end
		end
		return nil
	end)
end
tap(0x98040000, 0)   -- main TG
tap(0x98050000, 1)   -- sub TG

PD.flush = function ()
	local f = io.open(PD.out, "w")
	f:write("tg\tslot\tv\tp18\taux\tbank\tzone\tnp16\trectype\tactive\n")
	f:write(table.concat(PD.rows, "\n"))
	f:write("\n")
	f:close()
	emu.print_error(string.format("PITCH PROBE: %d pitch writes captured -> %s", PD.n, PD.out))
end

-- Drive the demo song: it exercises far more voices than a keybed scale would.
local acts, i = {}, 1
local function at(t, fn) acts[#acts + 1] = { t = t, fn = fn } end
local function press(t, tag, mask, hold)
	at(t, function()
		local p = mac.ioport.ports[tag]
		if p then for _, fl in pairs(p.fields) do if fl.mask == mask then fl:set_value(1) end end end
	end)
	at(t + (hold or 0.35), function()
		local p = mac.ioport.ports[tag]
		if p then for _, fl in pairs(p.fields) do if fl.mask == mask then fl:clear_value() end end end
	end)
end
local T = tonumber(os.getenv("PD_DEMO_AT") or "23")
press(T,       ":cpanel:CPL_SEG6", 0x40)     -- DEMO
press(T + 4.0, ":cpanel:CPL_SEG0", 0x10)     -- START/STOP, in case it needs a start
-- A run that captures only the boot-time clear of all 128 voices looks exactly like
-- a run where the decode question is unanswerable. Snapshot the screen and print the
-- running count so the difference is visible.
for k = 1, 12 do
	at(T + k * 10.0, function ()
		emu.print_error(string.format("PITCH PROBE: t=%.0f  %d pitch writes so far", T + k * 10.0, PD.n))
	end)
end
at(tonumber(os.getenv("PD_UNTIL") or "115") - 1.0, function () mac.video:snapshot() end)
at(tonumber(os.getenv("PD_UNTIL") or "115"), function() PD.flush(); mac:exit() end)

PD.timer = emu.register_periodic(function()
	local now = mac.time.seconds + mac.time.attoseconds / 1e18
	while i <= #acts and now >= acts[i].t do local a = acts[i]; i = i + 1; a.fn() end
end)
