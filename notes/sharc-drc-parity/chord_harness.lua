-- Harness: hold a C major chord on the key bed so the effects DSP has real
-- signal to process.  RULE 12: a DSP test with no notes playing is not a test.
-- The window before PRESS_AT is the deliberate no-stimulus null (RULE 13), so
-- the run carries its own control.
local mac = manager.machine
local PRESS_AT = tonumber(os.getenv('PRESS_AT') or '20')
local STOP_AT  = tonumber(os.getenv('STOP_AT')  or '38')
local WANT = { C4 = true, E4 = true, G4 = true }
local keys = {}
for _, port in pairs(mac.ioport.ports) do
	for fname, f in pairs(port.fields) do
		if WANT[fname] then keys[#keys+1] = f end
	end
end
print(string.format('HARNESS: %d key field(s)', #keys))
local pressed = false
playtap = emu.add_machine_frame_notifier(function ()
	local t = mac.time:as_double()
	if not pressed and t > PRESS_AT then
		pressed = true
		for _, f in ipairs(keys) do f:set_value(1) end
		print('HARNESS: chord down at t=' .. t)
	end
	if t > STOP_AT then mac:exit() end
end)
