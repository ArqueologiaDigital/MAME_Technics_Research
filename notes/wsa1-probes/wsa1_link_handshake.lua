-- Why does CPU 2 stop being able to SEND on the inter-processor link?
--
-- Link_SendChunk (prom_c 0xF999BE) will not write its header byte until PA bit 3
-- reads 1 -- "the far receiver is idle" -- and gives up after 0x4E20 = 20000
-- spins (0xF999D0-0xF999DF).  Under the driver's cross-wiring, PA bit 3 IS
-- CPU 1's P7 bit 1.  This probe records what PA actually reads on CPU 2, what
-- CPU 1 last wrote to P7, and how many bytes CPU 2 has managed to send, around a
-- key press at t = 76 s.
--
-- Signal: a histogram of PA read values.  Bit 3 set (0xF9, 0xFD, ...) means the
-- far side is idle and a send can start; bit 3 clear (0xF5, 0xF7, ...) means it
-- cannot, and 20000 of them in a row is one timed-out attempt.
--
-- RESULT, 2026-08-25, -str 82:
--   t=68  tx=0  P7 last written 0xE7 (bit 1 SET, idle)   PA reads 0x00/0xFD
--   t=72  tx=2  P7 last written 0xE1                     PA reads 0xF5 x40013
--   t=76  PRESS
--   t=82  tx=2  P7 last written 0xC5 (bit 1 CLEAR)       PA reads 0xF5 x60051,
--                                                                  0xF7 x20027
-- So CPU 2 sends exactly ONE packet -- two bytes, a header plus one payload --
-- and after it CPU 1 leaves P7 bit 1 LOW for good.  Every later send, including
-- the { 0x90, note, velocity } that a key press produces, burns its 20000 spins
-- and is dropped.  The key event IS decoded (see wsa1_keybed_note.lua); it never
-- leaves the processor.
--
-- ⚠ This is NOT caused by the keybed model, and not by the 2026-08-25 tmp95c061
-- P6 fix: every write this probe sees on CPU 1 lands in the HIGH byte of the
-- 0x12/0x13 word, i.e. on P7 (0x13) and never on P6 (0x12), so CPU 1 makes no
-- runtime P6 write at all.  What has to be looked at is CPU 1's INT0_LinkByte
-- (0xF8E47F) and INTTC3_LinkDmaDone (0xF8E54F): something on that side arms
-- micro-DMA channel 3, drops the busy line, and never raises it again.
_G.pa_hist = {}
_G.p7_last = -1
_G.tx = 0
local cpu2 = manager.machine.devices[":cpu2"].spaces["program"]
local cpu1 = manager.machine.devices[":cpu1"].spaces["program"]

-- A tap in a 16-bit space must start on a word boundary, so P6 (0x12) and P7
-- (0x13) are covered together and told apart by which byte lane carries data.
_G.t_pa = cpu2:install_read_tap(0x1e, 0x1f, "par", function (offset, data, mask)
	local v = data & 0xff
	_G.pa_hist[v] = (_G.pa_hist[v] or 0) + 1
	return data
end)
_G.t_p7 = cpu1:install_write_tap(0x12, 0x13, "p7w", function (offset, data, mask)
	_G.p7_last = data & 0xffff
	return data
end)
_G.t_tx = cpu2:install_write_tap(0x100000, 0x100001, "tx", function (offset, data, mask)
	_G.tx = _G.tx + 1 return data
end)

_G.key = manager.machine.ioport.ports[":KEY2"].fields["C4"]
_G.p, _G.r = false, false
_G.n = 0
_G.sub = emu.add_machine_frame_notifier(function ()
	local t = manager.machine.time:as_double()
	if not _G.p and t >= 76.0 then _G.key:set_value(1); _G.p = true
		print(string.format("t=%6.2f ---- PRESS ----", t)) end
	if not _G.r and t >= 78.0 then _G.key:set_value(0); _G.r = true end
	_G.n = _G.n + 1
	if (_G.n % 120) ~= 0 then return end
	local s = {}
	for v, c in pairs(_G.pa_hist) do s[#s + 1] = string.format("%02X:%d", v, c) end
	table.sort(s)
	print(string.format("t=%6.2f tx=%d  p7last=%04X  PA reads: %s",
		t, _G.tx, _G.p7_last & 0xffff, table.concat(s, " ")))
end)
