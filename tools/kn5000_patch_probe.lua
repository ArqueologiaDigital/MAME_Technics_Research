-- KN5000: select a SPECIFIC PATCH (sound group + LCD page + LCD soft key), then either
-- HOLD one key or play a CHROMATIC SWEEP. Repeatable over a list of patches in one run.
--
-- This is the reproduction rig for Felipe's 2026-08-06 report, which is localised to named
-- patches rather than to sound groups:
--
--   * "Jazz Flute" (FLUTE group, LCD LEFT 2): notes Db4..F#4 (MIDI 61..66) sound ONE
--     OCTAVE HIGH; the rest of the keyboard is right.  -> KN5_PROBE=sweep
--   * almost all of ORGAN & ACCORDION pages 1/2 and 2/2 decay while the key is held, but
--     Rock Organ (p2/2 LEFT 4) and Chapel Organ (p1/2 LEFT 3) sustain correctly.
--     -> KN5_PROBE=hold, and the two good patches are the WITHIN-GROUP CONTROL.
--   * "Theatre Novelty" (p2/2 RIGHT 3) is silent.  -> KN5_PROBE=hold, read bank/wave_real.
--
-- kn5000_hold_note.lua could only reach the FIRST patch of a sound group, so it could not
-- see any of this. The LCD soft keys and PAGE UP/DOWN are fully mapped in kn5000_cpanel.cpp
-- (physical scan-matrix names, the authoritative source), so patch selection is lookup.
--
-- The per-note-on facts (wave bank/page/chunk, wave_real, measured period, true_note,
-- pitch_step, the three EG words, and the note's own peak/rms) are recorded by the driver's
-- KN5000_NOTELOG, not by this script -- so the script only has to press buttons and write
-- down WHEN it pressed them.
--
-- env:
--   KN5_PATCHSEQ  comma list of patch specs, in order. One spec is
--                     group[+][:key]
--                 group = piano guitar strings brass flute sax organ pad synth
--                 '+'   = press PAGE UP once after selecting the group (page 2/2)
--                 key   = L1..L5 / R1..R5, the LCD soft key (omit = leave as-is)
--                 e.g.  flute:L2  organ:L3  organ+:L4  organ+:R3
--   KN5_PROBE     hold | sweep                              (default hold)
--   KN5_T0        when the first selection happens          (default 14.0)
--   KN5_SETTLE    seconds between the last press and the key(default 2.5)
--   KN5_GAP       seconds of silence after each patch       (default 1.5)
--
--   hold mode:  KN5_HOLD    seconds to hold                 (default 6.0)
--               KN5_KEYPORT/KN5_KEYMASK  which key          (default KEY2/0x001 = C4)
--   sweep mode: KN5_LO/KN5_HI  inclusive MIDI range         (default 55..72)
--               KN5_DUR     seconds each note is held       (default 0.60)
--               KN5_REST    seconds of silence between notes(default 0.30)
--
-- The keybed is 61 keys as six ioports of 12 bits: MIDI = 36 + 12*port + bit. That is the
-- SAME path a host MIDI controller takes (kbd_midi_rx -> push_keybed_event), so these are
-- true_note >= 0 voices -- exactly the ones Felipe is playing.

local mach = manager.machine
local V    = mach.video
local function T() return mach.time.seconds + mach.time.attoseconds/1e18 end

local SEQ_S   = os.getenv("KN5_PATCHSEQ") or "flute:L2"
local PROBE   = (os.getenv("KN5_PROBE") or "hold"):lower()
local T0      = tonumber(os.getenv("KN5_T0")     or "14.0")
local SETTLE  = tonumber(os.getenv("KN5_SETTLE") or "2.5")
local GAP     = tonumber(os.getenv("KN5_GAP")    or "1.5")
local HOLD    = tonumber(os.getenv("KN5_HOLD")   or "6.0")
local KEYPORT = os.getenv("KN5_KEYPORT") or "KEY2"
local KEYMASK = tonumber(os.getenv("KN5_KEYMASK") or "1")
local LO      = tonumber(os.getenv("KN5_LO")   or "55")
local HI      = tonumber(os.getenv("KN5_HI")   or "72")
local DUR     = tonumber(os.getenv("KN5_DUR")  or "0.60")
local REST    = tonumber(os.getenv("KN5_REST") or "0.30")
local MARKS   = os.getenv("KN5_MARKS")

-- SOUND GROUP buttons, straight off kn5000_cpanel.cpp's PORT_NAMEs.
local SOUNDBTN = {
	piano   = { "CPR_SEG2", 0x01 }, guitar  = { "CPR_SEG2", 0x02 },
	strings = { "CPR_SEG2", 0x04 }, brass   = { "CPR_SEG2", 0x08 },
	flute   = { "CPR_SEG2", 0x10 }, sax     = { "CPR_SEG2", 0x20 },
	organ   = { "CPR_SEG1", 0x01 }, pad     = { "CPR_SEG1", 0x02 },
	synth   = { "CPR_SEG1", 0x04 },
}

-- LCD soft keys and the page keys, likewise from kn5000_cpanel.cpp.
local SOFTKEY = {
	L1 = { "CPL_SEG10", 0x02 }, L2 = { "CPL_SEG10", 0x01 },
	L3 = { "CPL_SEG9",  0x04 }, L4 = { "CPL_SEG9",  0x02 }, L5 = { "CPL_SEG9", 0x01 },
	R1 = { "CPL_SEG8",  0x04 }, R2 = { "CPL_SEG8",  0x02 }, R3 = { "CPL_SEG8", 0x01 },
	R4 = { "CPL_SEG7",  0x02 }, R5 = { "CPL_SEG7",  0x01 },
}
local PAGEUP = { "CPL_SEG2", 0x80 }
local EXIT   = { "CPL_SEG7", 0x08 }

-- ⚠ EVERY PATCH STARTS FROM A KNOWN SCREEN. Without this the panel drifts: a 10-patch
-- sweep with ~11 s between selections was MEASURED to wander onto the ENTERTAINER page
-- part way through, after which every remaining soft key hit that screen instead of the
-- sound list and SEVEN patches in a row re-used the previous patch's wave selector 0x4007.
-- The run looked completely healthy -- ten holds, ten envelopes, ten rows of output -- and
-- would have been reported as "nine of ten organ patches sustain" when nine of them were
-- the SAME patch. Pressing EXIT first, and then checking in analysis that consecutive
-- patches do not share a selector, is what makes the rig's own failure visible.
local PRE_EXIT = (os.getenv("KN5_NOEXIT") or "") == ""

-- ---- parse the patch list -------------------------------------------------------------
local seq = {}
for spec in SEQ_S:gmatch("[^,]+") do
	local g, rest = spec:match("^%s*([%a]+)(.*)$")
	local pageup  = rest:find("%+") ~= nil
	local key     = rest:match(":%s*([LR]%d)")
	seq[#seq+1] = { spec = spec, group = g and g:lower() or nil, pageup = pageup, key = key }
end

local function setfield(tag, mk, v)
	local port = mach.ioport.ports[":cpanel:" .. tag]
	if not port then emu.print_info("### MISSING PORT " .. tag); return end
	for _, f in pairs(port.fields) do if f.mask == mk then f:set_value(v); return end end
	emu.print_info(string.format("### MISSING FIELD %s/0x%02X", tag, mk))
end

-- MIDI note -> (ioport, mask). MIDI = 36 + 12*port + bit.
local function notefield(midi)
	local raw = midi - 36
	if raw < 0 or raw > 60 then return nil end
	return "KEY" .. math.floor(raw / 12), 1 << (raw % 12)
end

local function setkeyraw(tag, mk, v)
	local port = mach.ioport.ports[":" .. tag]
	if not port then emu.print_info("### MISSING KEY PORT " .. tag); return end
	for _, f in pairs(port.fields) do if f.mask == mk then f:set_value(v); return end end
	emu.print_info(string.format("### MISSING KEY FIELD %s/0x%03X", tag, mk))
end

local markf = MARKS and io.open(MARKS, "w") or nil
if markf then markf:write("# patch midi t_on t_off\n") end

emu.print_info(string.format("### PATCH PROBE seq=%s probe=%s T0=%.1f", SEQ_S, PROBE, T0))

-- A patch step is a short PRESS QUEUE (group, maybe PAGE UP, maybe a soft key) followed by
-- the probe. Queueing rather than nesting phases keeps every press 0.25 s long with 0.45 s
-- between presses, which is what the firmware's panel scan expects.
local idx, phase, base, sec = 1, "wait", 0.0, 0
local queue, qi, qstate = {}, 1, ""
local note, t_on = 0, 0.0

_G._probe = emu.register_frame_done(function()
 pcall(function()
	local t = T()
	if t >= sec then
		sec = sec + 2
		emu.print_info(string.format("### t=%d phase=%s step=%d/%d", math.floor(t), phase, idx, #seq))
	end

	if phase == "wait" then
		if t >= T0 then phase = "build"; base = t end

	elseif phase == "build" then
		if idx > #seq then phase = "done"; V:snapshot(); return end
		local s = seq[idx]
		queue = {}
		if PRE_EXIT then queue[#queue+1] = EXIT; queue[#queue+1] = EXIT end
		if s.group and SOUNDBTN[s.group] then queue[#queue+1] = SOUNDBTN[s.group] end
		if s.pageup then queue[#queue+1] = PAGEUP end
		if s.key and SOFTKEY[s.key] then queue[#queue+1] = SOFTKEY[s.key] end
		if s.key and not SOFTKEY[s.key] then emu.print_info("### BAD SOFT KEY " .. tostring(s.key)) end
		qi, qstate = 1, "down"
		emu.print_info(string.format("### t=%.2f PATCH '%s' (%d presses)", t, s.spec, #queue))
		phase = "press"; base = t

	elseif phase == "press" then
		if qi > #queue then
			V:snapshot()
			phase = "settle"; base = t; return
		end
		local b = queue[qi]
		if qstate == "down" then
			setfield(b[1], b[2], 1); qstate = "wdown"; base = t
		elseif qstate == "wdown" and t >= base + 0.25 then
			setfield(b[1], b[2], 0); qstate = "wup"; base = t
		elseif qstate == "wup" and t >= base + 0.45 then
			qi = qi + 1; qstate = "down"
		end

	elseif phase == "settle" then
		if t >= base + SETTLE then
			V:snapshot()
			if PROBE == "sweep" then note = LO else note = -1 end
			phase = (PROBE == "sweep") and "sw_on" or "h_on"
			base = t
		end

	-- ---- HOLD: one key, several seconds. The WAV over the hold IS the envelope. -------
	elseif phase == "h_on" then
		setkeyraw(KEYPORT, KEYMASK, 1); t_on = t
		emu.print_info(string.format("### t=%.6f HOLD ON  '%s'", t, seq[idx].spec))
		phase = "h_hold"; base = t
	elseif phase == "h_hold" then
		if t >= base + HOLD / 2 and not _G._ms then _G._ms = true; V:snapshot() end
		if t >= base + HOLD then
			setkeyraw(KEYPORT, KEYMASK, 0)
			emu.print_info(string.format("### t=%.6f HOLD OFF '%s'", t, seq[idx].spec))
			if markf then markf:write(string.format("%s %d %.6f %.6f\n", seq[idx].spec, -1, t_on, t)); markf:flush() end
			_G._ms = nil
			phase = "gap"; base = t
		end

	-- ---- SWEEP: one short note per MIDI number across a range ------------------------
	elseif phase == "sw_on" then
		local tag, mk = notefield(note)
		if not tag then phase = "gap"; base = t; return end
		setkeyraw(tag, mk, 1); t_on = t
		emu.print_info(string.format("### t=%.6f NOTE ON  %d '%s'", t, note, seq[idx].spec))
		phase = "sw_hold"; base = t
	elseif phase == "sw_hold" then
		if t >= base + DUR then
			local tag, mk = notefield(note)
			setkeyraw(tag, mk, 0)
			if markf then markf:write(string.format("%s %d %.6f %.6f\n", seq[idx].spec, note, t_on, t)); markf:flush() end
			phase = "sw_rest"; base = t
		end
	elseif phase == "sw_rest" then
		if t >= base + REST then
			note = note + 1
			if note > HI then phase = "gap"; base = t else phase = "sw_on" end
		end

	elseif phase == "gap" then
		if t >= base + GAP then idx = idx + 1; phase = "build"; base = t end
	end
 end)
end)
emu.print_info("### kn5000_patch_probe.lua loaded")
