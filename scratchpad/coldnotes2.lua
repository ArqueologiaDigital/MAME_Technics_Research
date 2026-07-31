-- coldnotes2.lua -- THE CLEAN VEHICLE (LEDGER standing rule 2).
--
-- Cold boot, NO panel navigation of any kind (the peq_gain vehicle uploads ~55
-- programs mid-run and CREATES a unit-1 rail -- see 148).  The cold-boot default
-- effects are CHORUS on unit 0 and a reverb on unit 1, which is what we want.
--
-- The boot settles at ~19 s emulated.  A triad is held from t = 21 s to t = 27.5 s,
-- which at 48 kHz DSP frames is ~ 312 000 "loud" frames inside the settled window
-- (the 104/70/81 censuses arm at frame 420 000 = 8.75 s).
--
-- Rule 12: a DSP test with NO NOTES PLAYING is not a test.  The script PRINTS the
-- key-press result, so "the notes did not sound" is visible in the log rather than
-- inferred from a silent census.

local mac = manager.machine
local function log(s) emu.print_error(s) end

local NOTES = { "C4", "E4", "G4" }        -- MIDI 60/64/67

-- The keybed port has been called both :KEY2 and :KEYS2 across driver revisions,
-- so FIND the field by NAME over every port rather than hard-coding either.
local found = {}
local function locate()
	for tag, port in pairs(mac.ioport.ports) do
		for _, f in pairs(port.fields) do
			for _, n in ipairs(NOTES) do
				if f.name == n then found[n] = f; log("coldnotes2: " .. n .. " -> " .. tag) end
			end
		end
	end
	local miss = {}
	for _, n in ipairs(NOTES) do if not found[n] then miss[#miss + 1] = n end end
	if #miss > 0 then log("coldnotes2: ⚠ NOT FOUND: " .. table.concat(miss, ",")) end
	return #miss == 0
end

local function setkeys(v)
	for _, n in ipairs(NOTES) do
		local f = found[n]
		if f then if v == 1 then f:set_value(1) else f:clear_value() end end
	end
end

local phase = 0
emu.register_periodic(function()
	local t = mac.time.seconds + mac.time.attoseconds / 1e18
	if phase == 0 then
		phase = 1
		log(string.format("coldnotes2: located=%s at t=%.2f", tostring(locate()), t))
	elseif phase == 1 and t >= 21.0 then
		phase = 2
		setkeys(1)
		log(string.format("coldnotes2: NOTE ON  t=%.2f", t))
	elseif phase == 2 and t >= 27.5 then
		phase = 3
		setkeys(0)
		log(string.format("coldnotes2: NOTE OFF t=%.2f", t))
	end
end)

log("coldnotes2.lua armed: triad C4/E4/G4 held 21.0 .. 27.5 s")
