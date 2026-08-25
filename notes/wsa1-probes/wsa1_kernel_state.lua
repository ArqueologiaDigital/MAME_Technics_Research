-- QUESTION: the UI draw task at prom_a 0xF8DA00 never dequeues the two display
-- lists screen 0x01 posts (wsa1_draw_task.lua: write index 0x0008, read index
-- 0x0000, free 0x01F7, frozen from t=25 s to t=60 s).  Is the task blocked, or
-- was it never started?
--
-- prom_a's kernel is documented in wsa1-roms-disasm (region banner 0xF8596D):
--
--   task control blocks   0x02F4 + n*12,  n = 1..4;  state byte at +9
--                         state 3 = blocked, 4 = runnable  (0xF859F3, 0xF85A96)
--   ready queue heads     0x032C + level*4
--   semaphore wait heads  0x033C + (s-1)*4,  s = 1..8   (empty == head->next == head)
--   semaphore counts      0x035C + (s-1),    one byte, saturating at 0xFF
--   ROM seed for the counts, 0xF85EBA: 00 01 00 01 00 00 00 00
--
-- Kernel_SemaSignal (0xF859AE) wakes the first waiter if the queue is NOT
-- empty, and otherwise just INCREMENTS the count.  So:
--
--   sem 1 count climbing   => nobody is waiting on it; the draw task is not
--                             blocked there and was probably never started
--   sem 1 count 0, queue non-empty, task state 3 => it IS waiting and the
--                             signal is not reaching it
--
-- Also prints the kernel's pending-tick counter (0xBE, incremented by
-- INTT3_KernelTick at 0xF85600 and drained by Kernel_Dispatch), because a
-- kernel that never drains ticks never reschedules.
-- It also counts LCD writes and takes a snapshot every 10 emulated seconds
-- into snap/wsa1r/, so "the kernel now runs" and "the screen now repaints" are
-- the same measurement.
local m   = manager.machine
local sp1 = m.devices[":cpu1"].spaces["program"]
_G.lcd = 0
_G.taps = {}
_G.taps[1] = sp1:install_write_tap(0x790000, 0x790001, "lcd",
	function (o, d, k) _G.lcd = _G.lcd + 1 return d end)
_G.n = 0
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.n = _G.n + 1
	if (_G.n % 150) ~= 0 then return end
	local sem = ""
	for s = 0, 7 do sem = sem .. string.format("%02X ", sp1:read_u8(0x035c + s)) end
	local q = ""
	for s = 0, 7 do
		local head = 0x033c + s * 4
		q = q .. ((sp1:read_u16(head) == head) and "-" or "W")
	end
	local st = ""
	for t = 1, 4 do
		local tcb = 0x02f4 + t * 12
		st = st .. string.format("t%d:st=%02X lvl=%02X  ", t,
			sp1:read_u8(tcb + 9), sp1:read_u8(tcb + 8))
	end
	print(string.format("t=%6.1f  ticks(0xBE)=%02X  semcount %s waitq %s  %s"
		.. " scrB %02X/%02X  ring rd=%04X wr=%04X  lcd=%d",
		m.time:as_double(), sp1:read_u8(0xbe), sem, q, st,
		sp1:read_u8(0x207c), sp1:read_u8(0x207d),
		sp1:read_u16(0x60040e), sp1:read_u16(0x600412), _G.lcd))
	if (_G.n % 600) == 0 then
		m.video:snapshot()
		print(string.format("SHOT t=%6.1f  lcd=%d", m.time:as_double(), _G.lcd))
	end
end)
