-- What VALUE does the KN5000 firmware write to the tone generator's pitch register,
-- and for which note?
--
-- WHY
--   The KN7000's wave ROMs are NO_DUMP, so its driver cannot turn the chip's pitch
--   word into a frequency and currently reads the firmware's answer out of CPU RAM.
--   The KN5000 is the same manufacturer's earlier sampler with the SAME
--   index-not-address design AND a genuine wave-ROM dump, so what its firmware puts
--   on the pitch register is the best available evidence for what the KN7000's
--   equivalent constant should be.
--
--   ⚠ The prior RE claim -- "16-bit semitone-ratio from table 0x01217D, 0x8000 =
--   1.0x, computed in ToneGen_Calc_Pitch 0x03D11F" -- does NOT hold: that routine
--   has since been re-identified as Keybed_Decode_Event, and a scale-free search of
--   every KN5000 ROM finds no equal-temperament ratio table in any endianness. So
--   this measures the register instead of trusting the note.
--
-- METHOD
--   The KN5000 tone generator is an address-latch + data port pair at sub-CPU
--   0x100000 (latch) / 0x100002 (data). Tap both, reconstruct (reg, value), and log
--   every write while a known key is held. Per the format doc the pitch increment is
--   the per-voice register at +0x0040 (group 0, bank 1).
--
-- ENV  K5_OUT (required)  K5_START (default 40)  K5_HOLD 0.6  K5_GAP 0.3
-- RUN  kn5000 -autoboot_script this -str <past the end>

local mac  = manager.machine
local cpu  = mac.devices[":maincpu"] or mac.devices[":subcpu"]
K5 = K5 or {}
K5.out   = assert(os.getenv("K5_OUT"), "K5_OUT not set")
K5.rows, K5.n = {}, 0
K5.key, K5.midi = "-", -1
K5.latch = 0

-- the tone generator hangs off the SUB cpu
local sub = mac.devices[":subcpu"]
if not sub then
	for tag, dev in pairs(mac.devices) do
		if tag:match("sub") then sub = dev break end
	end
end
local prog = (sub or cpu).spaces["program"]

prog:install_write_tap(0x100000, 0x100001, "k5lat", function(off, data, mask)
	K5.latch = data & 0xffff; return nil end)
prog:install_write_tap(0x100002, 0x100003, "k5dat", function(off, data, mask)
	K5.n = K5.n + 1
	if K5.midi >= 0 then
		K5.rows[#K5.rows + 1] = string.format("%s\t%d\t%04X\t%04X", K5.key, K5.midi, K5.latch, data & 0xffff)
	end
	return nil
end)

-- keybed
local SEMI = { C=0, ["C#"]=1, D=2, ["D#"]=3, E=4, F=5, ["F#"]=6, G=7, ["G#"]=8, A=9, ["A#"]=10, B=11 }
local keys = {}
for tag, port in pairs(mac.ioport.ports) do
	if tag:match("KEY") then
		for _, f in pairs(port.fields) do
			local l, o, sh = f.name:match("^([A-G])(%d)(#?)$")
			if l then keys[#keys+1] = { tag=tag, mask=f.mask, name=f.name,
			                            midi=(tonumber(o)+1)*12 + SEMI[l..sh] } end
		end
	end
end
table.sort(keys, function(a,b) return a.midi < b.midi end)
emu.print_error(string.format("KN5000 PITCH PROBE: %d keys found", #keys))

local acts, ai = {}, 1
local function at(t, fn) acts[#acts+1] = {t=t, fn=fn} end
local t = tonumber(os.getenv("K5_START") or "40")
local HOLD = tonumber(os.getenv("K5_HOLD") or "0.6")
local GAP  = tonumber(os.getenv("K5_GAP")  or "0.3")
-- one octave, every semitone, plus octave anchors
local want = {}
for _, k in ipairs(keys) do
	if (k.midi >= 60 and k.midi <= 72) or k.midi % 12 == 0 then want[#want+1] = k end
end
for _, k in ipairs(want) do
	local kk = k
	at(t, function()
		K5.key, K5.midi = kk.name, kk.midi
		local p = mac.ioport.ports[kk.tag]
		for _, f in pairs(p.fields) do if f.mask == kk.mask then f:set_value(1) end end
	end)
	at(t + HOLD, function()
		local p = mac.ioport.ports[kk.tag]
		for _, f in pairs(p.fields) do if f.mask == kk.mask then f:clear_value() end end
		K5.key, K5.midi = "-", -1
	end)
	t = t + HOLD + GAP
end
at(t + 2.0, function()
	local f = io.open(K5.out, "w")
	f:write("key\tmidi\treg\tvalue\n")
	f:write(table.concat(K5.rows, "\n") .. "\n")
	f:close()
	emu.print_error(string.format("KN5000 PITCH PROBE FINAL: %d TG writes, %d with a key held -> %s",
		K5.n, #K5.rows, K5.out))
	mac:exit()
end)
emu.print_error(string.format("KN5000 PITCH PROBE: %d keys to play, ends t=%.1f", #want, t+2.0))
K5.timer = emu.register_periodic(function()
	local now = mac.time.seconds + mac.time.attoseconds/1e18
	while ai <= #acts and now >= acts[ai].t do local a = acts[ai]; ai = ai + 1; a.fn() end
end)
