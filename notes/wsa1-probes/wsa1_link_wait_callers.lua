-- WHO is burning CPU 1's time in Link_WaitBlockDone, and is it a spin or a
-- re-entry?
--
-- wsa1_ui_blockers.lua showed 0xF8E671-0xF8E681 taking ~60% of CPU 1's PC
-- samples.  That range is:
--
--   F8E66D  push HL
--   F8E66E  ld HL,(0x80)          ; snapshot the 8-bit-timer tick
--   F8E671  bit 7,(0x00008A)      ; is a link block still in flight?
--   F8E676  jr Z,0xF8E69E         ; NO -> return WA=0 at once
--   F8E678  ld BC,(0x80)
--   F8E67B  sub BC,HL
--   F8E67D  cp BC,0x01F4          ; 500 ticks = 1.024 s at the real 488.28 Hz
--   F8E681  jr LE,0xF8E671        ; ... spin until the deadline
--   F8E683  DMA3V=0; (0x6007DA)=0; set 1,(P7); res 7,(0x8A); inc (0x6007E1)
--
-- so F8E676 is an immediate exit and F8E678-F8E681 is the deadline spin.  This
-- probe separates the two and names the caller: `call` pushes a 32-bit return
-- address, `push HL` pushes two more bytes, so while the loop runs the caller
-- is at (SP+2).
--
-- It also counts the TIMEOUT path by tapping the error counter at 0x6007E1
-- (`inc 1,(0x6007E1)` is a read-modify-write, so a write tap sees each one),
-- and prints the two screen-state variable pairs so the active UI screen id is
-- visible at the same time.
_G.spin, _G.fast, _G.callers, _G.n = 0, 0, {}, 0
_G.timeouts, _G.aborts = 0, 0

local m   = manager.machine
local sp1 = m.devices[":cpu1"].spaces["program"]
_G.taps = {}
_G.taps[1] = sp1:install_write_tap(0x6007e0, 0x6007e1, "to",
	function (o, d, k) _G.timeouts = _G.timeouts + 1 return d end)
_G.taps[2] = sp1:install_write_tap(0x6007dc, 0x6007dd, "ab",
	function (o, d, k) _G.aborts = _G.aborts + 1 return d end)

_G.sub = emu.add_machine_frame_notifier(function ()
	local cpu = m.devices[":cpu1"]
	local pc  = cpu.state["CURPC"].value
	_G.n = _G.n + 1
	if pc >= 0xf8e678 and pc <= 0xf8e682 then
		_G.spin = _G.spin + 1
	elseif pc >= 0xf8e66d and pc <= 0xf8e677 then
		_G.fast = _G.fast + 1
	end
	if pc >= 0xf8e66d and pc <= 0xf8e682 then
		local s  = cpu.state["SP"].value
		local ra = sp1:read_u32(s + 2) & 0xffffff
		_G.callers[ra] = (_G.callers[ra] or 0) + 1
	end
	if (_G.n % 600) ~= 0 then return end
	print(string.format(
		"t=%6.1f  spin=%d entry=%d timeouts=%d aborts=%d  (0x8A)=%02X  "
		.. "scrA %02X/%02X scrB %02X/%02X  (0x2070..73)=%02X %02X %02X %02X",
		m.time:as_double(), _G.spin, _G.fast, _G.timeouts, _G.aborts,
		sp1:read_u8(0x8a),
		sp1:read_u8(0x2078), sp1:read_u8(0x2079),
		sp1:read_u8(0x207c), sp1:read_u8(0x207d),
		sp1:read_u8(0x2070), sp1:read_u8(0x2071),
		sp1:read_u8(0x2072), sp1:read_u8(0x2073)))
	local a = {}
	for k, v in pairs(_G.callers) do a[#a+1] = {k, v} end
	table.sort(a, function (x, y) return x[2] > y[2] end)
	local s = ""
	for i = 1, math.min(6, #a) do s = s .. string.format(" %06X:%d", a[i][1], a[i][2]) end
	print("CALLERS" .. s)
end)
