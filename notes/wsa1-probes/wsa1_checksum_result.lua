-- Do the two battery-RAM checksums at 0xF82C80 PASS or FAIL, and is that what
-- puts "ALL INITIAL SETTING!" on the panel?
--
-- 0xF82C80 sums 0x100 words from 0x007620 and compares the complement with
-- (0x007FD2), then does the same over 0x617800 against (0x007FD4), and leaves
-- the two verdicts as bits 0 and 1 of the byte at 0x007FD1, which 0xF82CAB
-- branches on.  This prints that byte as it is written, with the PC doing the
-- write, so the verdict is read off the machine instead of being assumed.
local sp = manager.machine.devices[":cpu1"].spaces["program"]
-- NOTE: taps on this 16-bit space must start on a word boundary, so the tap
-- covers 0x7FD0-0x7FD1 and the byte of interest is the HIGH half of the word.
_G.tap = sp:install_write_tap(0x007fd0, 0x007fd1, "verdict",
	function (offset, data, mask)
		local b = (data >> 8) & 0xff
		if (mask & 0xff00) == 0 then return data end   -- low byte only, not ours
		print(string.format("VERDICT t=%.4f  (0x7FD1) <= 0x%02X   bit0(blk1)=%d bit1(blk2)=%d  pc=%06X",
			manager.machine.time:as_double(), b, (b & 1), (b >> 1) & 1,
			manager.machine.devices[":cpu1"].state["CURPC"].value))
		return data
	end)
_G.n = 0
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.n = _G.n + 1
	if (_G.n % 300) ~= 0 then return end
	print(string.format("t=%5.1f  (0x7FD1)=0x%02X", manager.machine.time:as_double(),
		sp:read_u8(0x007fd1)))
end)
