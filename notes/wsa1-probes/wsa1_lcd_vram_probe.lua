-- Does CPU 1's boot ever reach the panel init?  Sample the SED1330's display
-- RAM once a second and report how many bytes are non-zero, plus whether the
-- host has programmed a plausible geometry.
_G.probe_n = 0
_G.probe_sub = emu.add_machine_frame_notifier(function ()
	_G.probe_n = _G.probe_n + 1
	if (_G.probe_n % 60) ~= 0 then return end
	local dev = manager.machine.devices[":lcdc"]
	if dev == nil then print("PROBE: no :lcdc device") return end
	local sp = nil
	for k, v in pairs(dev.spaces) do sp = v end
	if sp == nil then print("PROBE: lcdc has no space") return end
	local nz, first = 0, -1
	for a = 0, 0x7fff do
		local b = sp:read_u8(a)
		if b ~= 0 then nz = nz + 1 ; if first < 0 then first = a end end
	end
	print(string.format("PROBE t=%ds  display RAM non-zero bytes = %d  first at 0x%04X",
		_G.probe_n // 60, nz, first))
end)
