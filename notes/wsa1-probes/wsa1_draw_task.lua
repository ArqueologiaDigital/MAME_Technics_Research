-- QUESTION: after the machine leaves the power-on splash (family-B screen 0xAA,
-- the one that prints "ALL INITIAL SETTING!") for screen 0x01, the LCD write
-- count never moves again.  Screen 0x01's ENTER method (prom_a 0xF90D58) does
-- not draw directly -- it ENQUEUES two callbacks and signals a semaphore:
--
--   0xF90DB6  ld XWA,0x00F90DDB / push / call T_F42E84 (= 0xF8DA16 enqueue)
--   0xF90DC2  ld A,0x01 / call T_F42D88 (= 0xF859AE Kernel_SemaSignal)
--   0xF90DC8  ld XWA,0x00F90E4B / push / call T_F42E84
--   0xF90DD4  ld A,0x01 / call T_F42D88
--
-- and the consumer is the draw task at 0xF8DA00:
--
--   0xF8DA00  ld A,0x01 / call T_F42D90 (Kernel_SemaWait)
--   0xF8DA06  call 0xF8DA49            (CallbackQueue_Dequeue -> XIY)
--   0xF8DA0A  cp XIY,0xFFFFFFFF / jr Z,0xF8DA00
--   0xF8DA12  call XIY                 (RUN the callback)
--
-- The ring lives at 0x600416.  ⚠ Its three index fields are at NEGATIVE
-- displacements: TLCS-900's `ld (XBC+d8)` takes a SIGNED byte, so the +0xF8,
-- +0xFC and +0xFE in the listing are -8, -4 and -2 -- read index 0x60040E,
-- write index 0x600412, free count 0x600414, with the 128 four-byte slots
-- above them at 0x600416 (`minc4 0x01FC`).  Init seeds free = 0x01FF and
-- enqueue REFUSES while free < 5 (0xF8DA24 `cp WA,5 / jr C`).  So:
--
--   write index moves  => the screen POSTED its redraw
--   read index moves   => the draw TASK ran and took it
--   neither moves      => the screen never posted
--   posted but not taken => the task is blocked / never scheduled
--
-- Reported alongside the LCD write count and the four screen-state bytes, so
-- "posted / taken / painted" can be told apart in one run.
_G.enq, _G.deq, _G.lcd = 0, 0, 0
local m   = manager.machine
local sp1 = m.devices[":cpu1"].spaces["program"]
_G.taps = {}
_G.taps[1] = sp1:install_write_tap(0x60040e, 0x60040f, "rd",
	function (o, d, k) _G.deq = _G.deq + 1 return d end)
_G.taps[2] = sp1:install_write_tap(0x600412, 0x600413, "wr",
	function (o, d, k) _G.enq = _G.enq + 1 return d end)
_G.taps[3] = sp1:install_write_tap(0x790000, 0x790001, "lcd",
	function (o, d, k) _G.lcd = _G.lcd + 1 return d end)

_G.n = 0
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.n = _G.n + 1
	if (_G.n % 150) ~= 0 then return end
	print(string.format(
		"t=%6.1f  enq=%-5d deq=%-5d lcd=%-6d  ring rd=%04X wr=%04X free=%04X  "
		.. "scrA %02X/%02X scrB %02X/%02X  (2075)=%02X (2095)=%02X (209B)=%04X",
		m.time:as_double(), _G.enq, _G.deq, _G.lcd,
		sp1:read_u16(0x60040e), sp1:read_u16(0x600412), sp1:read_u16(0x600414),
		sp1:read_u8(0x2078), sp1:read_u8(0x2079),
		sp1:read_u8(0x207c), sp1:read_u8(0x207d),
		sp1:read_u8(0x2075), sp1:read_u8(0x2095), sp1:read_u16(0x209b)))
end)
