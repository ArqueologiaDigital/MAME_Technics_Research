-- ADVERSARIAL RE-CHECK of the two tmp95c061 timer fixes (2026-08-25).
--
-- QUESTION IT ANSWERS: with the overlay's PRESCALE_T1..T256 = 3/5/7/11 and the
-- new 16-bit timer counter in place, do the two Technics-visible interrupt
-- rates come out at the values the SX-WSA1R firmware is written against?
--
-- WHAT IS BEING READ, and why that address means what it says:
--
--  * writes to the WORD at CPU1 RAM 0x0080 -- prom_a's INTT1 handler (vector
--    0x44 -> 0xF82D0B) is the only producer; the boot block waits on it at
--    0xF82804 (`cp (0x80),0x0384`, i.e. 900 ticks).  RATE = INTT1 rate.
--    THE TAP SCALE IS NOW PRIMARY-SOURCED, which it was not when the fix was
--    written.  Toshiba, "TLCS-900/H Series TMP95C061BFG / TMP95C061BDFG",
--    doc rev 2003-03-31 (the 2011 Pb-free reissue is at
--    https://media.digikey.com/pdf/Data%20Sheets/Toshiba%20PDFs/TLCS-900,H%20Series.pdf),
--    page 95C061B-84, Figure 3.8 (2) "Prescaler": the oscillator fc goes
--    through a 1/4 divider into a 9-bit prescaler, and the accompanying
--    "Cycle" table reads, verbatim,
--        phiT1   (8/fc)      320 ns  @ fc = 25 MHz
--        phiT4   (32/fc)     1.28 us
--        phiT16  (128/fc)    5.12 us
--        phiT256 (2048/fc)   81.92 us
--    i.e. shifts 3, 5, 7, 11 -- what this build uses.  Page 95C061B-95,
--    Table 3.8 (2), repeats phiT1 = 8/fc, and page 95C061B-105, Figure
--    3.9 (3), gives the 16-bit timer's T4CLK as 01 = phiT1 (8/fc),
--    10 = phiT4 (32/fc), 11 = phiT16 (128/fc).  Upstream MAME's
--    >>7/>>9/>>11/>>15 is uniformly 16x slow against all three.
--
--    prom_a programs T01MOD = 0x0D (0xF826EB) -> timer 1 clocked from phiT256,
--    TREG1 = 0x1C = 28 (0xF826F4), so at fc = 28 MHz the EXPECTED rate is
--    28e6/2048/28 = 488.28 Hz.  Upstream MAME's >>15 predicts 30.52 Hz.
--
--  * writes to the BYTE at CPU1 RAM 0x0084 -- prom_a's INTTR4 handler
--    (vector 0x50 -> 0xF82EA2) does `inc 1,(XHL)` on it and wraps it at 0x60
--    = 96 (0xF82EB1), i.e. 96 PPQN.  RATE = INTTR4 rate.  prom_a programs
--    T4MOD = 0x05 (0xF82703) -> phiT1 + UC4-clear-on-TREG5, TREG4 = 1
--    (0xF8270C/0F), TREG5 = 0x3D09 = 15625 (0xF82712/15), TRUN = 0xB7
--    (0xF8272A).  phiT1 = 8/fc (same datasheet figure), so the BOOT value
--    predicts 28e6/8/15625 = 224.0 Hz = 96 PPQN at 140 BPM -- but that is a
--    TRANSIENT: the firmware then stores TREG5 = 18229 (120 BPM) and the
--    steady state is 28e6/8/18229 = 192.00 Hz.  See wsa1_treg5_audit.lua.
--    Upstream MAME never counted these timers at all, so upstream predicts 0.
--
--  * the interrupt-priority registers INTET10/32/54/76 (internal I/O 0x73-0x76)
--    and TRUN/T4MOD/T5MOD, sampled live.  A 16-bit timer that RUNS but whose
--    INTE* byte is 0 cannot dispatch, which is what decides whether the
--    overlay's timer-5 modelling can be observed on this machine at all.
--    All three read handlers are side-effect free (tmp95c061.cpp inte_r,
--    trun_r, t4mod_r, t5mod_r).
--
-- RUN:
--   cd ~/compartilhado/kn7000_mame_build
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 40 -window \
--     -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_timer_rate_audit.lua
--
-- PASS: the "INTT1" column settles at 488 +/- 2 Hz, and the per-second DELTA of
-- the INTTR4 count settles at 192 (the running average stays high for a long
-- time because of the 224 Hz boot transient).
--
-- MEASURED 2026-08-25 on wsa1r, build 5d35cf0:
--   INTT1  = 488.28 Hz  (predicted 488.281)
--   INTTR4 = 192.00 Hz  (predicted 3.5e6/18229 = 192.00) -- 96 PPQN at 120 BPM
--   TRUN=BB T4MOD=25 T5MOD=22  INTET10=38 32=28 54=83 76=80
-- The INTET76 = 0x80 reading matters: both of timer 5's interrupt LEVELS are
-- 0, so INTTR6/INTTR7 are never dispatched on this machine, and the overlay's
-- decision to ignore T5MOD<CLE> (bit 2, "clear disable" per datasheet Figure
-- 3.9 (3)) is not observable here -- but it is still wrong: with T5MOD = 0x02
-- the real UC5 free-runs to 0xFFFF, so INTTR7's request flag should be set at
-- (28e6/32)/65536 = 13.3 Hz, not at /15000 = 58.3 Hz.

_G.t1 = 0
_G.tr4 = 0
_G.t0 = nil
local sp = manager.machine.devices[":cpu1"].spaces["program"]

-- held in globals: a tap collected by the GC is silently dead.
_G.tap80 = sp:install_write_tap(0x000080, 0x000081, "t1w",
	function (offset, data, mask) _G.t1 = _G.t1 + 1 return data end)
-- the program space is 16 bits wide, so a tap range must be word-aligned;
-- 0x0084 is the LOW byte of that word, so count only accesses whose byte mask
-- actually covers it (a write to 0x0085 alone must not be counted).
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

_G.n = 0
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.n = _G.n + 1
	if (_G.n % 60) ~= 0 then return end
	local t = manager.machine.time:as_double()
	-- start the window once the boot block has actually programmed the timers
	if _G.t0 == nil and _G.t1 > 0 then
		_G.t0 = t ; _G.b1 = _G.t1 ; _G.b4 = _G.tr4
	end
	local r1, r4 = 0, 0
	if _G.t0 ~= nil and t > _G.t0 + 0.5 then
		r1 = (_G.t1 - _G.b1) / (t - _G.t0)
		r4 = (_G.tr4 - _G.b4) / (t - _G.t0)
	end
	print(string.format(
		"t=%6.2f  INTT1=%7.2f Hz (n=%d)  INTTR4=%7.2f Hz (n=%d)  " ..
		"TRUN=%02X T4MOD=%02X T5MOD=%02X  INTET10=%02X 32=%02X 54=%02X 76=%02X",
		t, r1, _G.t1, r4, _G.tr4,
		sp:read_u8(0x20), sp:read_u8(0x38), sp:read_u8(0x48),
		sp:read_u8(0x73), sp:read_u8(0x74), sp:read_u8(0x75), sp:read_u8(0x76)))
end)
