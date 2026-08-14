-- sio_core_verify.lua -- SIO-in-CPU-core refactor live verification (Integrate stage).
-- The on-chip SIO moved from driver HLE into the mn10300 core; the panel serial
-- link, MIDI and SD paths must behave exactly as before.
-- (a) boot to home -> snapshot (panel handshake + LCD OK)
-- (b) press RHYTHM GROUP BALLAD (:cpanel:CPL_SEG2 0x08) 0.4s -> snapshot the
--     genre list (panel button events travel cpanel->core FIFO->firmware)
-- (c) press SD MENU (:cpanel:CPR_SEG1 0x80) 0.4s -> snapshot the SD menu
local snap_home, b_press, b_rel, snap_list, sd_press, sd_rel, snap_sd = false, false, false, false, false, false, false
emu.register_frame_done(function()
	local m = manager.machine
	local t = m.time.seconds + m.time.attoseconds / 1e18
	if t >= 27.5 and not snap_home then
		snap_home = true
		m.video:snapshot()
		emu.print_error(string.format("[sio] t=%.2f home snapshot taken", t))
	end
	if t >= 28.0 and not b_press then
		b_press = true
		local p = m.ioport.ports[":cpanel:CPL_SEG2"]
		if p == nil then emu.print_error("[sio] ERROR: port :cpanel:CPL_SEG2 missing") return end
		p:field(0x08):set_value(1)
		emu.print_error(string.format("[sio] t=%.2f BALLAD pressed", t))
	end
	if b_press and not b_rel and t >= 28.4 then
		b_rel = true
		m.ioport.ports[":cpanel:CPL_SEG2"]:field(0x08):set_value(0)
		emu.print_error(string.format("[sio] t=%.2f BALLAD released", t))
	end
	if t >= 30.5 and not snap_list then
		snap_list = true
		m.video:snapshot()
		emu.print_error(string.format("[sio] t=%.2f genre-list snapshot taken", t))
	end
	if t >= 31.0 and not sd_press then
		sd_press = true
		local p = m.ioport.ports[":cpanel:CPR_SEG1"]
		if p == nil then emu.print_error("[sio] ERROR: port :cpanel:CPR_SEG1 missing") return end
		p:field(0x80):set_value(1)
		emu.print_error(string.format("[sio] t=%.2f SD MENU pressed", t))
	end
	if sd_press and not sd_rel and t >= 31.4 then
		sd_rel = true
		m.ioport.ports[":cpanel:CPR_SEG1"]:field(0x80):set_value(0)
		emu.print_error(string.format("[sio] t=%.2f SD MENU released", t))
	end
	if t >= 34.5 and not snap_sd then
		snap_sd = true
		m.video:snapshot()
		emu.print_error(string.format("[sio] t=%.2f SD-menu snapshot taken", t))
	end
end)
