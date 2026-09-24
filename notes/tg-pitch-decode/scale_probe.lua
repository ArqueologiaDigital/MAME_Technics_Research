-- Can the musical note be recovered from the TG REGISTER STREAM alone?
--
-- WHY THIS SHAPE OF EXPERIMENT
--   The driver currently answers "what note is this?" by reading the firmware's
--   voice record out of CPU work RAM at a hardcoded, build-specific address. To
--   decide whether that lookup is necessary, do NOT compare it against another
--   derived number -- press a key whose NAME is the note and see what the chip is
--   told. MAME's keybed ioports are named C2, C2#, D2 ... C7, so the ground truth
--   is the input, not a second guess.
--
--   An earlier attempt drove the DEMO button instead. The KN7000's demo is a
--   picture slideshow: it produced 256 pitch writes, all p18=0 across exactly 128
--   slots -- the boot-time clear of every voice -- and nothing after. Fitting that
--   would have "worked" perfectly and meant nothing, which is why every row here
--   carries the key that produced it and rows with no key are dropped.
--
-- METHOD
--   Raw-bus write taps on both TGs. Press each key in turn, hold, release. On every
--   pitch write (class 0x2400, bit0 = p18 bit16) emit:
--       key note_midi tg slot v p18 aux bank zone
--   Optionally repeat the scale for several SOUND GROUP selections, so a per-zone
--   offset -- if there is one -- shows up as a family of parallel lines.
--
-- ENV  SC_OUT    output TSV (required)
--      SC_START  emulated seconds before the first key, default 60
--      SC_HOLD   key hold, default 0.45   SC_GAP gap, default 0.25
--      SC_SOUNDS comma-separated "tag:mask" sound buttons to cycle, default none
-- RUN  as -autoboot_script with -str comfortably past the end.

local mac  = manager.machine
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]

SC = SC or {}
SC.out   = assert(os.getenv("SC_OUT"), "SC_OUT not set")
SC.start = tonumber(os.getenv("SC_START") or "60")
SC.hold  = tonumber(os.getenv("SC_HOLD")  or "0.45")
SC.gap   = tonumber(os.getenv("SC_GAP")   or "0.25")
SC.rows, SC.aux, SC.addr = {}, {}, {0, 0}
SC.key, SC.keymidi, SC.sound = "-", -1, "default"
SC.n, SC.kept = 0, 0

-- Collect the keybed: tag, mask, name -> MIDI number. C2 is MIDI 36 on this keybed
-- naming (C4 = middle C = 60), so name -> semitone is mechanical.
local SEMI = { C = 0, ["C#"] = 1, D = 2, ["D#"] = 3, E = 4, F = 5,
               ["F#"] = 6, G = 7, ["G#"] = 8, A = 9, ["A#"] = 10, B = 11 }
SC.keys = {}
for tag, port in pairs(mac.ioport.ports) do
	if tag:match("^:KEYS%d") then
		for _, f in pairs(port.fields) do
			local letter, octave, sharp = f.name:match("^([A-G])(%d)(#?)$")
			if letter then
				local midi = (tonumber(octave) + 1) * 12 + SEMI[letter .. sharp]
				SC.keys[#SC.keys + 1] = { tag = tag, mask = f.mask, name = f.name, midi = midi }
			end
		end
	end
end
table.sort(SC.keys, function (a, b) return a.midi < b.midi end)
emu.print_error(string.format("SCALE PROBE: %d keys, %s..%s",
	#SC.keys, SC.keys[1] and SC.keys[1].name or "?", SC.keys[#SC.keys] and SC.keys[#SC.keys].name or "?"))

local function setkey(k, v)
	local p = mac.ioport.ports[k.tag]
	if not p then return end
	for _, f in pairs(p.fields) do
		if f.mask == k.mask then if v == 1 then f:set_value(1) else f:clear_value() end end
	end
end

local function tap(base, tg)
	prog:install_write_tap(base, base + 3, "sc" .. tg, function(off, data, mask)
		if (mask & 0x0000ffff) ~= 0 then SC.addr[tg + 1] = data & 0xffff end
		if (mask & 0xffff0000) ~= 0 then
			local a = SC.addr[tg + 1]
			local d = (data >> 16) & 0xffff
			if (a & 0xff00) == 0xfc00 then return nil end
			local s, cls = (a >> 4) & 0x3F, a & 0xFC0F
			local v = (tg << 6) | s
			if cls == 0x1C02 then
				SC.aux[v] = d
			elseif (a & 0xFC0E) == 0x2400 then
				SC.n = SC.n + 1
				if SC.keymidi >= 0 then                       -- drop anything with no key held
					SC.kept = SC.kept + 1
					local aux  = SC.aux[v] or 0
					local p18  = ((a & 1) << 16) | d
					local slot = (tg == 0) and (s | 0x40) or s
					SC.rows[#SC.rows + 1] = string.format(
						"%s\t%s\t%d\t%d\t%d\t%d\t%d\t%04X\t%d\t%d",
						SC.sound, SC.key, SC.keymidi, tg, slot, v, p18, aux, (aux >> 12) & 3, aux & 0xFF)
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

local t = SC.start
local sounds = {}
for spec in (os.getenv("SC_SOUNDS") or ""):gmatch("[^,]+") do
	local tg, mk = spec:match("^(.+):(%x+)$")
	if tg then sounds[#sounds + 1] = { tag = tg, mask = tonumber(mk, 16), name = spec } end
end
if #sounds == 0 then sounds = { { name = "default" } } end

for _, snd in ipairs(sounds) do
	if snd.tag then
		local tag, mask, nm = snd.tag, snd.mask, snd.name
		at(t, function ()
			SC.sound = nm
			local p = mac.ioport.ports[tag]
			if p then for _, f in pairs(p.fields) do if f.mask == mask then f:set_value(1) end end end
		end)
		at(t + 0.35, function ()
			local p = mac.ioport.ports[tag]
			if p then for _, f in pairs(p.fields) do if f.mask == mask then f:clear_value() end end end
		end)
		t = t + 2.5
	end
	for _, k in ipairs(SC.keys) do
		local kk = k
		at(t, function () SC.key, SC.keymidi = kk.name, kk.midi; setkey(kk, 1) end)
		at(t + SC.hold, function () setkey(kk, 0); SC.key, SC.keymidi = "-", -1 end)
		t = t + SC.hold + SC.gap
	end
	t = t + 1.0
end

at(t + 1.0, function () mac.video:snapshot() end)
at(t + 2.0, function ()
	local f = io.open(SC.out, "w")
	f:write("sound\tkey\tmidi\ttg\tslot\tv\tp18\taux\tbank\tzone\n")
	f:write(table.concat(SC.rows, "\n") .. "\n")
	f:close()
	emu.print_error(string.format("SCALE PROBE: %d pitch writes, %d with a key held -> %s",
		SC.n, SC.kept, SC.out))
	mac:exit()
end)
emu.print_error(string.format("SCALE PROBE: scale ends at t=%.1f s", t + 2.0))

SC.timer = emu.register_periodic(function ()
	local now = mac.time.seconds + mac.time.attoseconds / 1e18
	while ai <= #acts and now >= acts[ai].t do local a = acts[ai]; ai = ai + 1; a.fn() end
end)
