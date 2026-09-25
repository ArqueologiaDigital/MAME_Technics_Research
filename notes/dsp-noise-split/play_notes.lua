-- Stimulus for the noise A/B: hold a chord, then a short scale, on the key bed.
-- RULE 12: a sound test with no notes playing is not a test. The caller also
-- captures a no-stimulus window, because a difference from silence is not a signal.
--
-- Set KN_SILENT=1 in the environment to run the same timeline pressing nothing.
local SILENT = (os.getenv("KN_SILENT") == "1")

local function key(idx)                       -- key index -> port tag + field mask
	return string.format(":KEYS%d", idx // 16), 1 << (idx % 16)
end

local function press(idx, on)
	if SILENT then return end
	local tag, mask = key(idx)
	local p = manager.machine.ioport.ports[tag]
	if p == nil then return end
	for _, f in pairs(p.fields) do
		if f.mask == mask then f:set_value(on and 1 or 0) end
	end
end

local function run()
	emu.wait(12.0)                            -- let the firmware finish booting
	print("KNAUDIO: stimulus start silent=" .. tostring(SILENT))
	local chord = { 0x18, 0x1C, 0x1F }        -- C4 E4 G4
	for _, k in ipairs(chord) do press(k, true) end
	emu.wait(4.0)
	for _, k in ipairs(chord) do press(k, false) end
	emu.wait(1.0)
	for _, k in ipairs({ 0x18, 0x1A, 0x1C, 0x1D, 0x1F, 0x21, 0x23, 0x24 }) do
		press(k, true);  emu.wait(0.5);  press(k, false);  emu.wait(0.1)
	end
	emu.wait(2.0)
	print("KNAUDIO: stimulus done")
end

_G.kn_audio_task = coroutine.create(run)
emu.register_periodic(function ()
	if coroutine.status(_G.kn_audio_task) == "suspended" then
		local ok, err = coroutine.resume(_G.kn_audio_task)
		if not ok then print("KNAUDIO: error " .. tostring(err)) end
	end
end)
