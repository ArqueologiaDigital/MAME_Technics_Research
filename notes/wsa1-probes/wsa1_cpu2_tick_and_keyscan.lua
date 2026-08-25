-- Does CPU 2's INTT1 tick counter advance, and does the key scanner ever ARM?
--
-- KeyScan_ReadEvent (prom_c 0xF9973D) refuses to touch the key-scan port at
-- 0x00108000 until the one-shot latch at RAM 0x00F329 is 1, and it only sets
-- that latch once the INTT1 tick counter at RAM 0x00F2F3 has passed 1000
-- (0xF9974E cp XBC,0x000003E8).  So a keyboard wired to that port can produce
-- nothing at all unless timer 1 on CPU 2 actually interrupts.
--
-- Signal:
--   tick   -- the 32-bit counter at 0x00F2F3.  Pinned at 0 => INTT1 never fires.
--   arm    -- the byte at 0x00F329.  1 => the scanner is live.
--   TRUN   -- SFR 0x20.  bit 7 prescaler, bit 1 timer 1, bit 0 timer 0.
--   ev/st  -- how many times the firmware has read 0x108000 / 0x108002.
_G.ev, _G.st = 0, 0
local sp = manager.machine.devices[":cpu2"].spaces["program"]
_G.t1 = sp:install_read_tap(0x108000, 0x108001, "evr",
	function (offset, data, mask) _G.ev = _G.ev + 1 return data end)
_G.t2 = sp:install_read_tap(0x108002, 0x108003, "str",
	function (offset, data, mask) _G.st = _G.st + 1 return data end)

_G.n = 0
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.n = _G.n + 1
	if (_G.n % 60) ~= 0 then return end
	print(string.format("t=%6.2f  tick=%d  arm=%d  TRUN=%02X  ev=%d st=%d  cpu2pc=%06X",
		manager.machine.time:as_double(),
		sp:read_u32(0x00F2F3), sp:read_u8(0x00F329), sp:read_u8(0x20),
		_G.ev, _G.st,
		manager.machine.devices[":cpu2"].state["CURPC"].value))
end)
