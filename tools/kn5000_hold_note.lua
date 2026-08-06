-- KN5000: select a SOUND GROUP, then HOLD ONE KEY for several seconds. Repeatable over a
-- LIST of sound groups in a single run.
--
-- This is the reproduction rig for Felipe's 2026-08-06 report ("all strings decay after a
-- very short sustain interval while the key is held"). A single held key is the whole
-- test: with one note sounding and nothing else, the rendered output IS the per-voice
-- amplitude envelope, so `-wavwrite` alone answers "does a held note sustain?".
--
-- It drives the KEY BED (the `KEY0..KEY4` ioports the driver turns into
-- push_keybed_event()), which is the same path a host MIDI controller takes through
-- kbd_midi_rx() -- so it exercises the true_note >= 0 voices Felipe is playing.
--
-- It also taps the raw tone-generator bus (sub-CPU 0x100000/0x100002) over every hold, so
-- the register traffic DURING the hold is recorded rather than inferred. That is what
-- decides whether the firmware re-programs an envelope segment while the key is down.
--
-- env:
--   KN5_SOUNDSEQ  comma list of sound groups to sweep, in order
--                 (strings,pad,organ,brass,flute,sax,synth,guitar,piano,none)
--                 default: strings
--   KN5_T0        when the first selection happens          (default 14.0)
--   KN5_HOLD      seconds to hold the key                   (default 8.0)
--   KN5_SETTLE    seconds between the selection and the key (default 3.0)
--   KN5_GAP       seconds of silence after each release     (default 2.0)
--   KN5_KEYPORT   KEY0..KEY4                                (default KEY2 = C4..B4)
--   KN5_KEYMASK   bit within that port                      (default 0x001 = C4)
--   KN5_BUSLOG    file for the raw bus trace                (default none)
--   KN5_MARKS     file listing "sound t_on t_off" per step  (default none)
--   KN5_POKEMASK  bit of a SECOND key struck DURING the hold (default 0 = off)
--   KN5_POKE_AT   comma list of offsets from t_on at which to strike it
--   KN5_POKE_DUR  how long the poke key is held             (default 0.25)
--
-- The POKE is not decoration. Felipe plays from a MIDI controller, i.e. he holds notes
-- WHILE PLAYING OTHERS, and the firmware's `Voice_Reload_Levels` re-emits a six-register
-- level burst on every sounding channel of a part whenever anything about that part's
-- levels changes. The HLE's key-release heuristic triggers on exactly one of those
-- registers (+0x900), so a burst caused by a NEW note would end an OLD held note. A
-- single isolated held note cannot see that defect at all; this is what makes it visible.
--
-- The MARKS file is what makes the WAV analysable without guessing: every hold's exact
-- emulated start and end are written down as the run makes them.

local mach = manager.machine
local V    = mach.video
local function T() return mach.time.seconds + mach.time.attoseconds/1e18 end

local SEQ_S   = os.getenv("KN5_SOUNDSEQ") or "strings"
local T0      = tonumber(os.getenv("KN5_T0")     or "14.0")
local HOLD    = tonumber(os.getenv("KN5_HOLD")   or "8.0")
local SETTLE  = tonumber(os.getenv("KN5_SETTLE") or "3.0")
local GAP     = tonumber(os.getenv("KN5_GAP")    or "2.0")
local KEYPORT = os.getenv("KN5_KEYPORT") or "KEY2"
local KEYMASK = tonumber(os.getenv("KN5_KEYMASK") or "1")
local BUSLOG  = os.getenv("KN5_BUSLOG")
local MARKS   = os.getenv("KN5_MARKS")
local POKEMASK = tonumber(os.getenv("KN5_POKEMASK") or "0")
local POKEDUR  = tonumber(os.getenv("KN5_POKE_DUR") or "0.25")
local POKEAT   = {}
for s in (os.getenv("KN5_POKE_AT") or ""):gmatch("[^,]+") do POKEAT[#POKEAT+1] = tonumber(s) end
table.sort(POKEAT)

-- SOUND GROUP buttons, straight off kn5000_cpanel.cpp's PORT_NAMEs (the authoritative
-- physical scan-matrix names).
local SOUNDBTN = {
	piano   = { "CPR_SEG2", 0x01, "PIANO" },
	guitar  = { "CPR_SEG2", 0x02, "GUITAR" },
	strings = { "CPR_SEG2", 0x04, "STRINGS & VOCAL" },
	brass   = { "CPR_SEG2", 0x08, "BRASS" },
	flute   = { "CPR_SEG2", 0x10, "FLUTE" },
	sax     = { "CPR_SEG2", 0x20, "SAX & REED" },
	organ   = { "CPR_SEG1", 0x01, "ORGAN & ACCORDION" },
	pad     = { "CPR_SEG1", 0x02, "ORCHESTRAL PAD" },
	synth   = { "CPR_SEG1", 0x04, "SYNTH" },
	none    = nil,
}

local seq = {}
for s in SEQ_S:gmatch("[^,]+") do seq[#seq+1] = s:lower() end

local function setbtn(tag, mk, v)
	local port = mach.ioport.ports[":cpanel:" .. tag]
	if not port then emu.print_info("### MISSING PORT " .. tag); return end
	for _, f in pairs(port.fields) do if f.mask == mk then f:set_value(v) end end
end

local function setkeymask(mk, v)
	local port = mach.ioport.ports[":" .. KEYPORT]
	if not port then emu.print_info("### MISSING KEY PORT " .. KEYPORT); return end
	for _, f in pairs(port.fields) do if f.mask == mk then f:set_value(v); return end end
	emu.print_info(string.format("### MISSING KEY FIELD 0x%03X", mk))
end
local function setkey(v) setkeymask(KEYMASK, v) end

-- ---- raw tone-generator bus tap -------------------------------------------------------
-- Held in a GLOBAL: a tap that is only a local is silently reaped by the GC.
local busf, latch, bus_on = nil, 0, false
if BUSLOG then
	busf = io.open(BUSLOG, "w")
	busf:write("# t addr data  (raw tone-generator bus writes, held notes only)\n")
	local space = mach.devices[":subcpu"].spaces["program"]
	_G._tgtap = space:install_write_tap(0x100000, 0x100003, "tgbus", function(offset, data, mask)
		if not bus_on then return end
		if offset == 0x100000 then
			latch = data & 0xFFFF
		elseif offset == 0x100002 then
			busf:write(string.format("%.6f %04X %04X\n", T(), latch, data & 0xFFFF))
		end
	end)
end
local markf = MARKS and io.open(MARKS, "w") or nil
if markf then markf:write("# sound t_on t_off\n") end

emu.print_info(string.format("### HOLD SWEEP seq=%s T0=%.1f hold=%.1f settle=%.1f gap=%.1f key=%s/0x%03X",
	SEQ_S, T0, HOLD, SETTLE, GAP, KEYPORT, KEYMASK))

local idx, phase, base, sec, t_on = 1, "wait", 0.0, 0, 0.0
local btn = nil

_G._hold = emu.register_frame_done(function()
 pcall(function()
	local t = T()
	if t >= sec then
		sec = sec + 2
		emu.print_info(string.format("### t=%d phase=%s step=%d/%d", math.floor(t), phase, idx, #seq))
	end

	if phase == "wait" then
		if t >= T0 then phase = "select"; base = t end

	elseif phase == "select" then
		if idx > #seq then phase = "done"; return end
		btn = SOUNDBTN[seq[idx]]
		V:snapshot()
		if btn then
			setbtn(btn[1], btn[2], 1)
			emu.print_info(string.format("### t=%.2f PRESS %s (%s)", t, btn[3], seq[idx]))
		else
			emu.print_info(string.format("### t=%.2f no button for '%s' -- default sound", t, seq[idx]))
		end
		phase = "selhold"; base = t

	elseif phase == "selhold" then
		if t >= base + 0.30 then
			if btn then setbtn(btn[1], btn[2], 0) end
			phase = "settle"; base = t
		end

	elseif phase == "settle" then
		if t >= base + SETTLE then
			V:snapshot()
			bus_on = true
			setkey(1); t_on = t
			emu.print_info(string.format("### t=%.6f KEY ON  (%s)", t, seq[idx]))
			phase = "held"; base = t
		end

	elseif phase == "held" then
		-- strike a SECOND key partway through the hold (see KN5_POKE_AT above)
		if POKEMASK ~= 0 then
			for i, off in ipairs(POKEAT) do
				if t >= t_on + off and not _G["_poke" .. i] then
					_G["_poke" .. i] = true
					setkeymask(POKEMASK, 1)
					emu.print_info(string.format("### t=%.6f POKE ON  (+%.2f)", t, off))
				end
				if t >= t_on + off + POKEDUR and not _G["_pokeoff" .. i] then
					_G["_pokeoff" .. i] = true
					setkeymask(POKEMASK, 0)
					emu.print_info(string.format("### t=%.6f POKE OFF (+%.2f)", t, off))
				end
			end
		end
		if t >= base + HOLD / 2 and not _G._midsnap then _G._midsnap = true; V:snapshot() end
		if t >= base + HOLD then
			-- The key bed is LEVEL-driven with edge detection in keybed_scan(): the field
			-- must be HELD at 1 for the whole hold, and dropping it to 0 is the note-off.
			setkey(0)
			emu.print_info(string.format("### t=%.6f KEY OFF (%s)", t, seq[idx]))
			if markf then markf:write(string.format("%s %.6f %.6f\n", seq[idx], t_on, t)); markf:flush() end
			_G._midsnap = nil
			for i = 1, #POKEAT do _G["_poke" .. i] = nil; _G["_pokeoff" .. i] = nil end
			phase = "gap"; base = t
		end

	elseif phase == "gap" then
		if t >= base + GAP then
			bus_on = false
			if busf then busf:flush() end
			idx = idx + 1; phase = "select"; base = t
		end
	end
 end)
end)
emu.print_info("### kn5000_hold_note.lua loaded")
