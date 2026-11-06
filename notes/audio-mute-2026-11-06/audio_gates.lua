-- audio_gates.lua -- question: does the driver's speaker output follow PMUT, SPSW and the D/A
-- converter's mode words, and is a note played in normal operation as loud as before they were
-- modelled?
--
-- The lines (technics-roms-disasm kn7000/notes/audio-mute-probes/README.md, section 1):
--   PMUT  GPIO byte 0x36008004 bit 2 (1 = the power amplifiers' bias rail +15PM on)
--   SPSW  IC25 latch, byte 0x98060000 bit 1 (1 = the FETs ahead of the headphone and speaker
--         stages conduct); the firmware's shadow of the latch is 0x50005214 in program 941 (the
--         default) and 0x5000520C in program 893 (-bios v13: run with SHADOW=0x5000520C)
--   DAC   IC311's mode port on the latch: bit 3 CS (DAC.ML), bit 4 MC, bit 5 MDI
--
-- Logged, with the emulated time (seconds from power-on, the same clock as -wavwrite):
--   PMUT <t> <old> -> <new>          bit 2 of 0x36008004 changed
--   SPSW <t> <old> -> <new>          bit 1 of the 0x98060000 latch changed
--   DACWORD <t> <word> ...           a 16-bit word clocked into IC311, decoded here from the bus
--                                    (CS falling .. CS rising, MDI sampled on MC rising)
--   DACREG <name> <values>           the converter device's own registers 16-20 and attenuator
--                                    state, read from its save-state items at the end
--   WINDOW <name> <t0> <t1>          a span the analysis (gate_windows.py) measures
--
-- Timeline (program 941, BIOS v16): boot; then key C4 held for 1 s in five windows, each 3 s
-- apart, from T0 (default 20 s):
--   W1-normal    nothing forced
--   W2-pmut-low  the probe clears PMUT (a write to 0x36008004, as the firmware's own bclr) 0.2 s
--                before the key and sets it again 0.2 s after: the failure the probe must see
--                (sound with PMUT low) is what the build before the change gives here
--   W3-normal    sound must be back
--   W4-spsw-low  the probe clears SPSW in the firmware's shadow and the latch, as the M3
--                0x600009 handler does with a 0, and sets it back afterwards
--   W5-normal
--   W6-nmi       the key is pressed, then POWER OFF pulses NMI: the firmware's NMI handler
--                clears PMUT, then sets the power latch; the driver exits 100 ms later
-- Windows measure the held key from 0.1 s after key-down to 0.9 s (W6: up to the NMI, then
-- from PMUT falling to the exit).
--
-- Command: see README.md.
local mac = manager.machine
local cpu = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]
local OUT = io.open(os.getenv("OUT") or "audio_gates.txt", "w")
local function log(s) OUT:write(s .. "\n"); OUT:flush(); print(s) end
local T0 = tonumber(os.getenv("T0") or "20")
local SHADOW = tonumber(os.getenv("SHADOW") or "0x50005214")
local KEY = os.getenv("KEY") or "C4"

local function now() return mac.time.seconds + mac.time.attoseconds / 1e18 end

-- byte of a bus write at the lane of address `want` (little-endian 32-bit bus)
local function lane(off, data, mask, want)
	local sh = ((want - (off & ~3)) & 3) * 8
	if ((mask >> sh) & 0xff) == 0 then return nil end
	return (data >> sh) & 0xff
end

local pmut, spsw, latch = -1, -1, -1
local sh_word, sh_bits, cs_low = 0, 0, false
local t_pmut_fall = nil

_G.AG = {}
_G.AG.tp = prog:install_write_tap(0x36008004, 0x36008007, "pmut", function(off, data, mask)
	local b = lane(off, data, mask, 0x36008004)
	if b == nil then return nil end
	local v = (b >> 2) & 1
	if v ~= pmut then
		log(("PMUT %9.4f %d -> %d"):format(now(), pmut, v))
		if v == 0 then t_pmut_fall = now() end
		pmut = v
	end
	return nil
end)
_G.AG.tl = prog:install_write_tap(0x98060000, 0x98060003, "latch", function(off, data, mask)
	local b = lane(off, data, mask, 0x98060000)
	if b == nil then return nil end
	local old = latch
	local s = (b >> 1) & 1
	if s ~= spsw then log(("SPSW %9.4f %d -> %d"):format(now(), spsw, s)); spsw = s end
	if old >= 0 then
		local cs, mc, mdi = (b >> 3) & 1, (b >> 4) & 1, (b >> 5) & 1
		local ocs, omc = (old >> 3) & 1, (old >> 4) & 1
		if ocs == 1 and cs == 0 then cs_low, sh_word, sh_bits = true, 0, 0 end
		if cs_low and cs == 0 and omc == 0 and mc == 1 then
			sh_word = ((sh_word << 1) | mdi) & 0xffff; sh_bits = sh_bits + 1
		end
		if cs_low and ocs == 0 and cs == 1 then
			log(("DACWORD %9.4f %04X (%d bits) rw %d reg %d data %02X"):format(now(), sh_word, sh_bits,
				sh_word >> 15, (sh_word >> 8) & 0x7f, sh_word & 0xff))
			cs_low = false
		end
	end
	latch = b
	return nil
end)
log("taps armed at power-on: 0x36008004 (PMUT), 0x98060000 (IC25 latch)")

local function fld(name)   -- exact field name first, then a prefix ("POWER OFF (run ...)")
	for _, p in pairs(mac.ioport.ports) do
		for n, f in pairs(p.fields) do if n == name then return f end end
	end
	for _, p in pairs(mac.ioport.ports) do
		for n, f in pairs(p.fields) do if n:find(name, 1, true) == 1 then return f end end
	end
end

-- the converter device's own registers, read from its save-state items
local function dump_dac()
	local dev = mac.devices[":dac"]
	if not dev then log("DACREG none (no :dac device)"); return end
	local names = {}
	for name, _ in pairs(dev.items) do names[#names + 1] = name end
	table.sort(names)
	for _, name in ipairs(names) do
		local it = emu.item(dev.items[name])
		local vals = {}
		for i = 0, it.count - 1 do vals[#vals + 1] = ("%X"):format(it:read(i)) end
		log(("DACREG %s %s"):format(name, table.concat(vals, " ")))
	end
end

local acts = {}
local function at(t, desc, fn) acts[#acts + 1] = {t = t, desc = desc, fn = fn} end
local function key(t, v) at(t, (v == 1 and "DOWN " or "UP ") .. KEY, function()
	local f = fld(KEY); if f then f:set_value(v) else log("NOFIELD " .. KEY) end end) end
local function window(name, t)
	key(t, 1); key(t + 1.0, 0)
	at(t, "window " .. name, function() log(("WINDOW %s %.4f %.4f"):format(name, t + 0.1, t + 0.9)) end)
end
local function p04(bit2) return function()
	local v = prog:read_u8(0x36008004)
	prog:write_u8(0x36008004, bit2 == 1 and (v | 4) or (v & ~4))
end end
local function spsw_set(bit1) return function()
	local v = prog:read_u8(SHADOW)
	v = bit1 == 1 and (v | 2) or (v & ~2)
	prog:write_u8(SHADOW, v)
	prog:write_u8(0x98060000, v)
end end

at(T0 - 1, "state", function() log(("STATE home PMUT %d SPSW %d latch %02X"):format(pmut, spsw, latch & 0xff)); dump_dac() end)
window("W1-normal", T0)
at(T0 + 2.8, "PMUT forced 0", p04(0))
window("W2-pmut-low", T0 + 3)
at(T0 + 4.2, "PMUT forced 1", p04(1))
window("W3-normal", T0 + 6)
at(T0 + 8.8, "SPSW forced 0", spsw_set(0))
window("W4-spsw-low", T0 + 9)
at(T0 + 10.2, "SPSW forced 1", spsw_set(1))
window("W5-normal", T0 + 12)
local TN = T0 + 15
key(TN, 1)
at(TN + 0.5, "POWER OFF", function()
	log(("WINDOW W6-before-nmi %.4f %.4f"):format(TN + 0.1, TN + 0.5))
	log(("NMI %9.4f"):format(now()))
	dump_dac()
	local f = fld("POWER OFF"); if f then f:set_value(1) else log("NOFIELD POWER OFF") end
end)
-- the driver exits 100 ms after the NMI; this logs what came before
_G.AG.stop = emu.add_machine_stop_notifier(function()
	if t_pmut_fall and t_pmut_fall > TN then
		log(("WINDOW W6-after-pmut %.4f %.4f"):format(t_pmut_fall + 0.001, now()))
	end
	log(("END %9.4f PMUT %d SPSW %d"):format(now(), pmut, spsw))
	OUT:close()
end)
at(TN + 5, "timeout", function() log("ERR no exit after POWER OFF"); mac:exit() end)

table.sort(acts, function(a, b) return a.t < b.t end)
local i = 1
_G.AG.h = emu.add_machine_frame_notifier(function()
	local t = now()
	while i <= #acts and t >= acts[i].t do
		local a = acts[i]; i = i + 1
		local ok, err = pcall(a.fn)
		if not ok then log("ERR " .. a.desc .. ": " .. tostring(err)) else log(("[%7.3f] %s"):format(t, a.desc)) end
	end
end)
