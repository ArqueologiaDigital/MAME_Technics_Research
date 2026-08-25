-- Did the serial EEPROM's 62 calibration bytes actually reach the firmware?
--
-- The chain being tested, all of it on CPU 2:
--   EEPROM_LoadCalibration (0xFC8B0B) clocks 33 words out of the Microwire
--   device on P6.5 / P8.3 / P8.4 / P8.5, checks word 0x1F against their sum and
--   word 0x20 against 0x5AA5, and returns a pointer to RAM 0x00E2A1 or 0;
--   NoteTrim_BuildFromCalibration (0xF997FA) then fills the 61 signed trims at
--   RAM 0x0084DA with ToneGen_VelCurve_Trim51[clamp(cal[n] - 0x4B, 0, 50)], or
--   with zeros if the pointer was null.
--
-- Signal: the 61 bytes at 0x0084DA.  All zero means the load FAILED (or the
-- EEPROM is blank, which is the driver's default state).  With the image that
-- notes/wsa1-probes/make_wsa1_eeprom.py writes, a working path must print
--   -12 -12 -11 -10 -10 -9 -9 -8 -8 -7 -7 -6 -5 -5 -4 -4 -3 -3 -2 -2 -1 -1
--   0 0 0 0 0 1 1 2 2 3 3 4 4 4 5 5 6 6 6 7 7 8 8 8 9 9 10 10 10 10 ... 10
--
-- The trim table is built once, from MAIN's power-on init chain (0xF98B99), so
-- run with -str 80 or more.
_G.cs, _G.sk = 0, 0
_G.p6, _G.p8 = 0, 0

local sp = manager.machine.devices[":cpu2"].spaces["program"]

-- P6 is internal address 0x12, P8 is 0x18.  Count the edges the EEPROM driver
-- makes, so that "no trims" can be told apart from "no traffic at all".
_G.t_p6 = sp:install_write_tap(0x12, 0x13, "p6w", function (offset, data, mask)
	local v = data & 0xff
	if ((v ~ _G.p6) & 0x20) ~= 0 then _G.cs = _G.cs + 1 end
	_G.p6 = v
	return data
end)
_G.t_p8 = sp:install_write_tap(0x18, 0x19, "p8w", function (offset, data, mask)
	local v = data & 0xff
	if ((v ~ _G.p8) & 0x08) ~= 0 then _G.sk = _G.sk + 1 end
	_G.p8 = v
	return data
end)

_G.n = 0
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.n = _G.n + 1
	if (_G.n % 300) ~= 0 then return end

	local trims, nonzero = {}, 0
	for i = 0, 60 do
		local b = sp:read_u8(0x0084DA + i)
		if b > 127 then b = b - 256 end
		if b ~= 0 then nonzero = nonzero + 1 end
		trims[#trims + 1] = tostring(b)
	end
	print(string.format("t=%6.2f  CS edges=%d  SK edges=%d  nonzero trims=%d",
		manager.machine.time:as_double(), _G.cs, _G.sk, nonzero))
	print("          trim[0..60] = " .. table.concat(trims, " "))
end)
