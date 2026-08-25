-- SX-KN1500 REGRESSION CHECK for the TMP95C061 timer fixes.
--
-- QUESTION IT ANSWERS: the KN1500 shares the TMP95C061 with the SX-WSA1R, and
-- tools/gate.sh SKIPS it ("no screen device"), so nothing in the standing gate
-- can see a timer change break it.  This is the missing check: does the
-- machine still get exactly as far as it used to, and do its timers now run at
-- the rate its own firmware asks for?
--
-- WHAT IS BEING READ, and why each address means what it says.  All ROM
-- addresses are IC15 (technics_qsigt3c16079_5y68-j079_japan_9649eai.ic15,
-- mapped 0xE00000-0xFFFFFF by kn1500.cpp:39-56), disassembled with
-- `unidasm -arch tlcs900`:
--
--   0xFE5F9D  ldio T01MOD,0xED   timer 1 <- phiT256
--   0xFE5FA9  ldio TREG1,0x18    = 24, so at fc = 24 MHz (kn1500.cpp:56)
--                                INTT1 = 24e6/2048/24 = 488.28 Hz -- the SAME
--                                488 Hz design tick as the SX-WSA1R, reached
--                                from a different crystal and a different
--                                TREG1.  Upstream's >>15 gives 30.52 Hz.
--   0xFE5FB5  ldio T4MOD,0x05    timer 4 <- phiT1, CLE = 1
--   0xFE5FC4  ldw (TREG4),0x0001
--   0xFE5FC8  ldw (TREG5),0x3D09 = 15625, so INTTR4 = 24e6/8/15625 = 192.0 Hz
--                                = 96 PPQN at exactly 120.00 BPM
--   0xFE5FCC  ldio TRUN,0xFF     everything runs, 16-bit timers included
--   0xFE6078  ldio INTET54,0x03  INTTR4 level 3, INTTR5 level 0
--   vector 0x50 (0xFFFF50) -> 0xFE6515, the same sequencer routine as the
--                                SX-WSA1R's 0xF82EA2 down to its direct-page
--                                slots; 0xFE6522 `cp (XHL),0x60` = 96 PPQN.
--   vectors 0x54/0x58/0x5C -> 0xFE619C, an INTT0 stub.
--
-- Vector fetches are counted the same way as wsa1_inttr4_dispatch.lua: the CPU
-- reads FFFF00H + vector when it ACCEPTS the interrupt, so the data read is the
-- handler entry point.
--
-- ⚠ ON THIS MACHINE THE VECTOR COUNTS ARE CONTAMINATED, and the probe is built
-- to show it rather than hide it.  The KN1500's boot walks the ROM, so
-- 0xFFFF44..0xFFFF5C also get read as plain data -- which is why INTTR5, INTTR6
-- and INTTR7 all report their "first dispatch" at the SAME timestamp and all
-- resolve to 0xFE619C, an INTT0 stub they could not have been dispatched into
-- (INTET54 = 0x83 leaves INTTR5 at level 0, and INTET76 is never written).
-- Those three rows are therefore a direct read-out of the contamination rate,
-- and the INTTR4 row minus the INTTR5 row is the honest dispatch rate.
-- The SX-WSA1R has no such scan -- its INTTR5/6/7 rows sit at exactly 0 for the
-- whole run -- so wsa1_inttr4_dispatch.lua does not need the correction.
--
-- The handler counters, for reference, disassembled from IC15:
--   INTT1  0xFE634A: `add (0x80),XHL` with XHL = 1, and `incw 1,(0x84)`
--   INTTR4 0xFE6515: `lda XHL,0x86 / inc 1,(XHL) / cp (XHL),0x60` -- 96 PPQN
-- They are NOT tapped here on purpose: this machine spends the whole run in the
-- crt0 RAM test at 0xFA047F-0xFA04A3 (`ld (XIX),0xa5 / cp (XIX),0xa5 / ...`,
-- walking XIX with XBC as the count), which writes 0xA5/0x5A over all of RAM
-- including 0x80 and 0x86.  A write tap there would count the memory test.
--
-- RUN:
--   cd ~/compartilhado/kn7000_mame_build
--   DISPLAY=:0 ./kn7000 kn1500 -rompath ./roms -skip_gameinfo -str 30 -window \
--     -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/kn1500_timer_regression.lua
--
-- PASS is a COMPARISON, not an absolute: the PC histogram must be the same
-- shape as the null build's.  This machine does not boot (its crt0 RAM init
-- reads garbage -- likely a BAD_DUMP IC15), and the fix is not expected to
-- change that.  What must NOT happen is the PC moving into a new hang.
--
-- MEASURED 2026-08-25, 30 s, both builds of the same source tree
-- (notes/wsa1-probes/tlcs900_timer_control.sh switches between them):
--
--                        NULL (upstream timers)      FIXED (this overlay)
--   top PCs              FA0494 FA0497 FA049C ...    FA0497 FA049F FA0494 ...
--   what that is         the crt0 RAM test           the crt0 RAM test
--   INTTR4 handler       FE6515                      FE6515
--   emulated speed       100%                        100%
--
-- i.e. the KN1500 is in exactly the same place, doing exactly the same thing,
-- with and without the fix.  See the full numbers in
-- notes/WSA1-EMULATION-DISASM-GAPS.md.

local cpu = manager.machine.devices[":maincpu"]
local sp = cpu.spaces["program"]

_G.vec = {
	{ name = "INTT1 ", addr = 0xffff44 },
	{ name = "INTT3 ", addr = 0xffff4c },
	{ name = "INTTR4", addr = 0xffff50 },
	{ name = "INTTR5", addr = 0xffff54 },
	{ name = "INTTR6", addr = 0xffff58 },
	{ name = "INTTR7", addr = 0xffff5c },
}
_G.taps = {}
for i, r in ipairs(_G.vec) do
	r.n = 0 ; r.pc = nil
	_G.taps[i] = sp:install_read_tap(r.addr, r.addr + 1, "v" .. i,
		function (offset, data, mask)
			if (mask & 0x00ff) ~= 0 then
				r.n = r.n + 1
				if r.pc == nil and not r.busy then
					r.busy = true ; local pc = sp:read_u32(r.addr) ; r.busy = false
					r.pc = pc
					print(string.format("FIRST DISPATCH %s t=%.4f -> handler %06X",
						r.name, manager.machine.time:as_double(), r.pc))
				end
			end
			return data
		end)
end

_G.hist = {}
_G.samples = 0
_G.t0 = nil
_G.base = nil
_G.n = 0
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.n = _G.n + 1
	local pc = cpu.state["CURPC"].value
	_G.hist[pc] = (_G.hist[pc] or 0) + 1
	_G.samples = _G.samples + 1
	if (_G.n % 300) ~= 0 then return end
	local t = manager.machine.time:as_double()
	if _G.t0 == nil then
		_G.t0 = t
		_G.base = {}
		for i, r in ipairs(_G.vec) do _G.base[i] = r.n end
		return
	end
	local dt = t - _G.t0
	local s = ""
	for i, r in ipairs(_G.vec) do
		s = s .. string.format(" %s=%.1fHz", r.name, (r.n - _G.base[i]) / dt)
	end
	-- top three PCs, so a move into a NEW hang is visible at a glance
	local ks = {}
	for k in pairs(_G.hist) do ks[#ks+1] = k end
	table.sort(ks, function (a, b) return _G.hist[a] > _G.hist[b] end)
	local top = ""
	for i = 1, math.min(3, #ks) do
		top = top .. string.format(" %06X:%d", ks[i], _G.hist[ks[i]])
	end
	print(string.format("t=%6.2f %s | TRUN=%02X T4MOD=%02X INTET10=%02X 54=%02X | top%s",
		t, s, sp:read_u8(0x20), sp:read_u8(0x38),
		sp:read_u8(0x73), sp:read_u8(0x75), top))
end)
