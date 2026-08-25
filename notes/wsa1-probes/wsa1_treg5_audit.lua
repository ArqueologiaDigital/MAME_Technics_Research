-- ADVERSARIAL FOLLOW-UP to wsa1_timer_rate_audit.lua (2026-08-25).
--
-- QUESTION IT ANSWERS: the INTTR4 dispatch rate measured on the running
-- SX-WSA1R settles at 194 Hz, not the 224 Hz that TREG5 = 15625 (the boot
-- value at prom_a 0xF82712/0xF82715) predicts at phiT1 = fc/8.  Is that
-- because the firmware REPROGRAMMED TREG5, or because INTTR4 requests are
-- being LOST?
--
-- WHAT IS BEING READ: every write to CPU1 internal I/O 0x0032/0x0033 = TREG5
-- (TMP95C061B datasheet 3.9; MAME maps it write-only at tmp95c061.cpp
-- `map(0x000030, 0x000033).w(treg45_w)`, so it cannot simply be read back).
-- The tempo setter at prom_a 0xFAA350 stores 140,000,000/(64*BPM) there.
--
-- HOW TO READ THE RESULT: at phiT1 = fc/8 = 3.5 MHz the predicted INTTR4 rate
-- is 3.5e6 / TREG5.  If that equals the measured rate, no interrupt is being
-- lost and the 224 Hz figure simply belonged to a different TREG5.  If the
-- prediction is HIGHER than the measurement, requests are being coalesced
-- while the CPU has them masked.
--
-- RUN: as for wsa1_timer_rate_audit.lua, substituting this file.

_G.tr4 = 0
_G.t5 = -1
_G.t5w = 0
_G.t0 = nil
local sp = manager.machine.devices[":cpu1"].spaces["program"]

_G.tap84 = sp:install_write_tap(0x000084, 0x000085, "tr4w",
	function (offset, data, mask)
		-- the handler writes 0x0084 TWICE on the wrap interrupt: `inc 1,(XHL)`
		-- at 0xF82EAF makes it 0x60, then `ld (XHL),0x00` at 0xF82EB6 zeroes
		-- it.  Counting both inflates the rate by 1/96 (194 Hz instead of
		-- 192 Hz -- measured, PC census 2026-08-25: F82EB1 x6137, F82EB9 x63).
		-- Count only the increment, i.e. the write whose value is non-zero.
		if (mask & 0x00ff) ~= 0 and (data & 0xff) ~= 0 then
			_G.tr4 = _G.tr4 + 1
		end
		return data
	end)

-- TREG5 low byte at 0x32, high byte at 0x33; the firmware writes low then high
-- (0xF82712 then 0xF82715).  Reassemble both halves as they go past.
_G.lo, _G.hi = 0, 0
_G.tap32 = sp:install_write_tap(0x000032, 0x000033, "treg5",
	function (offset, data, mask)
		if (mask & 0x00ff) ~= 0 then _G.lo = data & 0xff end
		if (mask & 0xff00) ~= 0 then _G.hi = (data >> 8) & 0xff end
		_G.t5 = _G.hi * 256 + _G.lo
		_G.t5w = _G.t5w + 1
		return data
	end)

_G.n = 0
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.n = _G.n + 1
	if (_G.n % 60) ~= 0 then return end
	local t = manager.machine.time:as_double()
	if _G.t0 == nil and _G.tr4 > 0 then _G.t0 = t ; _G.b4 = _G.tr4 end
	local r4 = 0
	if _G.t0 ~= nil and t > _G.t0 + 0.5 then r4 = (_G.tr4 - _G.b4) / (t - _G.t0) end
	local pred = 0
	if _G.t5 > 0 then pred = 28000000 / 8 / _G.t5 end
	print(string.format(
		"t=%6.2f  INTTR4 measured=%7.2f Hz (n=%d)  TREG5=%5d (writes=%d)  predicted=%7.2f Hz",
		t, r4, _G.tr4, _G.t5, _G.t5w, pred))
end)
