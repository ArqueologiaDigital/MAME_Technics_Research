-- ballad_verify.lua -- Phase B install verification ("8 Beat 1" fix).
-- Boot to home (default cfg, ~t=20-26), snapshot home, read the 0x54E00000
-- window (mapped synthetic "Technics Rhythms" resource), press RHYTHM GROUP
-- BALLAD (:cpanel:CPL_SEG1 mask 0x10) for 0.4s, snapshot the style list.
-- SUCCESS = distinct per-slot names; FAILURE = ten rows of "8 Beat 1".
local pressed, released, snapped_home, snapped_list, probed = false, false, false, false, false
emu.register_frame_done(function()
	local m = manager.machine
	local t = m.time.seconds + m.time.attoseconds / 1e18
	if t >= 27.0 and not probed then
		probed = true
		local sp = m.devices[":maincpu"].spaces["program"]
		local s = ""
		for i = 0, 15 do s = s .. string.char(sp:read_u8(0x54E00000 + i)) end
		emu.print_error(string.format("[ballad] t=%.2f magic@0x54E00000 = %q", t, s))
		local s2 = ""
		for i = 0, 15 do s2 = s2 .. string.char(sp:read_u8(0x54E10000 + i)) end
		emu.print_error(string.format("[ballad] t=%.2f bytes@0x54E10000 = %q (must NOT be the magic)", t, s2))
	end
	if t >= 27.5 and not snapped_home then
		snapped_home = true
		m.video:snapshot()
		emu.print_error(string.format("[ballad] t=%.2f home snapshot taken", t))
	end
	if t >= 28.0 and not pressed then
		pressed = true
		local p = m.ioport.ports[":cpanel:CPL_SEG1"]
		if p == nil then emu.print_error("[ballad] ERROR: port :cpanel:CPL_SEG1 missing") return end
		p:field(0x10):set_value(1)
		emu.print_error(string.format("[ballad] t=%.2f BALLAD pressed", t))
	end
	if pressed and not released and t >= 28.4 then
		released = true
		m.ioport.ports[":cpanel:CPL_SEG1"]:field(0x10):set_value(0)
		emu.print_error(string.format("[ballad] t=%.2f BALLAD released", t))
	end
	if t >= 30.5 and not snapped_list then
		snapped_list = true
		m.video:snapshot()
		emu.print_error(string.format("[ballad] t=%.2f style-list snapshot taken", t))
	end
end)
