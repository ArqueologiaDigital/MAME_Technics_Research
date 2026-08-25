-- QUESTION: is the floppy controller reachable and does it answer the exact
-- sequence the firmware's own reset routine performs?
--
-- WHY THIS EXISTS.  wsa1_fdc_probe.lua measured that a 200-second boot of
-- either variant never touches 0x7B0004, 0x7B0005 or 0x7A0000 at all -- the FDC
-- driver's only public entry, Fdc_Request (prom_a 0xFE66C7), is called from
-- eight sites and none of them is on the boot path.  So booting cannot show
-- whether the device is wired correctly.  This script drives the SAME BYTES the
-- firmware would, from Lua, through CPU 1's address space, so every access goes
-- through the driver's address map and through upd765a_device exactly as a
-- firmware access would.  It proves the MAP and the DEVICE, not the firmware.
--
-- The sequence is Fdc_ResetAndIdentifyMedia's (prom_a 0xFE558B), instruction
-- for instruction:
--
--   1. control register 0x7B0004 <- 0x80            (0xFE55C5, the reset)
--   2. wait for MSR & 0xF0 == 0x80                  (0xFE5604-0xFE560D)
--   3. data register 0x7B0005 <- 0x08               (0xFE560F, SENSE INTERRUPT
--                                                    STATUS)
--   4. read result bytes into 0x605A51..            (0xFE561E-0xFE5635)
--   5. repeat from 2 until the first result byte is 0x80, which is ST0's IC
--      field reading "invalid command" -- the standard post-reset drain
--                                                   (0xFE563A)
--
-- PASS is: step 2 is satisfied at once (MSR = 0x80, RQM set, direction
-- CPU->FDC), each SENSE INTERRUPT STATUS returns two bytes, and the loop
-- TERMINATES on ST0 = 0x80.  A controller that is absent reads MSR = 0xFF,
-- which is the firmware's own "no controller" test (Fdc_Op10, error 0xFC).
--
-- It then issues SPECIFY and SENSE DRIVE STATUS, and finally reads back what
-- the drive reports, which is where the honest limitation shows: with no motor
-- line modelled (CPU 1's PA bit 3 is unidentified -- see the block comment in
-- wsa1.cpp) ST3 reports the drive NOT READY, whether or not an image is
-- attached.
--
-- Run (the machine may be left booting; the FDC is independent of it):
--   cd ~/compartilhado/kn7000_mame_build
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 30 -window \
--       -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_fdc_selftest.lua

_G.sp = manager.machine.devices[":cpu1"].spaces["program"]

local MSR  = 0x7b0004      -- read: main status; write: the control register
local FIFO = 0x7b0005      -- read/write: the data register

local function rd(a) return _G.sp:read_u8(a) end
local function wr(a, v) _G.sp:write_u8(a, v) end

local function poll(mask, want, limit)
	for i = 1, limit do
		local s = rd(MSR)
		if (s & mask) == want then return true, s, i end
	end
	return false, rd(MSR), limit
end

_G.fail = 0
local function check(cond, what)
	if not cond then _G.fail = _G.fail + 1 end
	print(string.format("  [%s] %s", cond and "PASS" or "FAIL", what))
end

_G.done = false
_G.sub = emu.add_machine_frame_notifier(function ()
	if _G.done then return end
	_G.done = true

	print("=== SX-WSA1 FDC self-test (device + address map, not the firmware) ===")

	print(string.format("MSR before any write            = 0x%02X", rd(MSR)))
	check(rd(MSR) ~= 0xff, "MSR is not 0xFF (the firmware's 'no controller' code, error 0xFC)")

	-- 1. the reset the firmware writes, and 2. the RQM wait it then does
	wr(MSR, 0x80)
	local ok, s, tries = poll(0xf0, 0x80, 1000)
	print(string.format("after control <- 0x80: MSR      = 0x%02X after %d read(s)", s, tries))
	check(ok, "MSR & 0xF0 == 0x80 (RQM set, direction CPU->FDC) -- 0xFE5604's wait passes")

	-- 3..5. the SENSE INTERRUPT STATUS drain
	local drained, last0 = 0, -1
	for pass = 1, 12 do
		local okw = poll(0x80, 0x80, 1000)
		if not okw then break end
		wr(FIFO, 0x08)                          -- SENSE INTERRUPT STATUS
		local res = {}
		for i = 1, 8 do
			local st = rd(MSR)
			if (st & 0xc0) ~= 0xc0 then break end
			res[#res+1] = rd(FIFO)
		end
		drained = drained + 1
		last0 = res[1] or -1
		local hex = {}
		for _, b in ipairs(res) do hex[#hex+1] = string.format("%02X", b) end
		print(string.format("  SENSE INTERRUPT STATUS #%d -> %s", pass, table.concat(hex, " ")))
		if last0 == 0x80 then break end
	end
	check(last0 == 0x80,
		string.format("the drain TERMINATED on ST0 = 0x80 after %d command(s) (0xFE563A's exit test)", drained))

	-- SPECIFY, the next thing Fdc_ResetAndIdentifyMedia sends (opcode 0x03)
	poll(0xc0, 0x80, 1000)
	wr(FIFO, 0x03) ; poll(0xc0, 0x80, 1000)
	wr(FIFO, 0xcf) ; poll(0xc0, 0x80, 1000)
	wr(FIFO, 0x02)
	local sok, ss = poll(0xf0, 0x80, 1000)
	print(string.format("after SPECIFY: MSR              = 0x%02X", ss))
	check(sok, "SPECIFY consumed its two parameter bytes and left the chip idle")

	-- SENSE DRIVE STATUS (opcode 0x04), which the firmware's operation 11 uses
	poll(0xc0, 0x80, 1000)
	wr(FIFO, 0x04) ; poll(0xc0, 0x80, 1000)
	wr(FIFO, 0x00)                              -- (head & 1) << 2 | (unit & 3)
	local rok = poll(0xc0, 0xc0, 1000)
	local st3 = rok and rd(FIFO) or -1
	print(string.format("SENSE DRIVE STATUS -> ST3       = 0x%02X", st3))
	check(rok, "SENSE DRIVE STATUS returned its one result byte")
	if st3 >= 0 then
		print(string.format("  ST3 decode: FT(0x80)=%d  WP(0x40)=%d  RY(0x20)=%d  T0(0x10)=%d",
			(st3 >> 7) & 1, (st3 >> 6) & 1, (st3 >> 5) & 1, (st3 >> 4) & 1))
		print("  RY = 0 is EXPECTED here: nothing in this driver turns the drive")
		print("  motor on, because what does it on the real board is not identified")
		print("  (CPU 1's PA bit 3).  The firmware would report error 0x31.")
	end

	print(string.format("=== %d check(s) failed ===", _G.fail))
end)
