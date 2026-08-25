-- Does anything ever GATE a tone-generator channel, and does the busy model
-- change what the firmware sees?
--
-- QUESTION IT ANSWERS.  tg_status_r() now answers block 0's read out of a latch
-- driven by the two lifecycle literals the firmware writes to block 0 -- 0x8100
-- GATE and 0x7E00 FREE.  That model is only OBSERVABLE if some code path
-- actually gates a channel.  This script counts, on the 0x0010C000 port itself:
--
--   * every (select, data) write pair, split into block 0 lifecycle words,
--     other per-channel blocks and the thirteen globals;
--   * how many 0x8100 / 0x7E00 words land on block 0 (select < 64), which is
--     exactly the condition tg_data_w() uses to move the latch;
--   * any block-0 word that is NEITHER -- the computed voicerec[+0x29] -- and
--     whether one of those ever COLLIDES with a lifecycle literal, which is the
--     one bounded risk the model carries;
--   * every read of the +4 port, split into the bank query (select 0..3) and the
--     magnitude query (select 0x0180 + chan).
--
-- Nothing here depends on VERBOSE: the taps see the bus, not the log.
--
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 120 -window \
--       -autoboot_script .../wsa1_tg_lifecycle.lua
--
-- Press a key as well on the SX-WSA1 by adding WSA1_TG_PRESS=1, which holds C4
-- from t = 60 s to t = 70 s.

local mac  = manager.machine
local cpu2 = mac.devices[":cpu2"].spaces["program"]

_G.sel = 0
_G.n = { addr = 0, data = 0, blk0 = 0, chan = 0, glob = 0,
         gate = 0, free = 0, computed = 0, collide = 0,
         rd_bank = 0, rd_mag = 0, rd_other = 0 }
_G.first, _G.gatelist = {}, {}

_G.t_addr = cpu2:install_write_tap(0x10c000, 0x10c001, "tgsel", function (o, d, m)
	_G.sel = d & 0xffff; _G.n.addr = _G.n.addr + 1; return d
end)

_G.t_data = cpu2:install_write_tap(0x10c002, 0x10c003, "tgdat", function (o, d, m)
	local s, v = _G.sel, d & 0xffff
	_G.n.data = _G.n.data + 1
	if s < 64 then
		_G.n.blk0 = _G.n.blk0 + 1
		if v == 0x8100 then
			_G.n.gate = _G.n.gate + 1
			if #_G.gatelist < 20 then
				_G.gatelist[#_G.gatelist + 1] =
					string.format("t=%7.2f GATE ch %2d", mac.time:as_double(), s)
			end
		elseif v == 0x7e00 then
			_G.n.free = _G.n.free + 1
		else
			-- The computed word.  It only MATTERS if it can equal a literal, and
			-- that is what `collide` counts -- but a computed word can never be
			-- caught here as a collision, because it is indistinguishable from
			-- the literal by value.  So instead: record the RANGE of high bytes
			-- the computed word actually takes, which is what bounds the risk.
			_G.n.computed = _G.n.computed + 1
			local hi = (v >> 8) & 0xff
			_G.first["hi" .. hi] = (_G.first["hi" .. hi] or 0) + 1
			if hi == 0x7e or hi == 0x81 then _G.n.collide = _G.n.collide + 1 end
		end
	elseif s <= 0x0a7f then
		_G.n.chan = _G.n.chan + 1
	else
		_G.n.glob = _G.n.glob + 1
	end
	return d
end)

_G.t_rd = cpu2:install_read_tap(0x10c004, 0x10c005, "tgrd", function (o, d, m)
	local s = _G.sel
	if s < 4 then _G.n.rd_bank = _G.n.rd_bank + 1
	elseif s >= 0x0180 and s < 0x01c0 then _G.n.rd_mag = _G.n.rd_mag + 1
	else _G.n.rd_other = _G.n.rd_other + 1 end
	return d
end)

_G.key = nil
if os.getenv("WSA1_TG_PRESS") and mac.ioport.ports[":KEY2"] then
	_G.key = mac.ioport.ports[":KEY2"].fields["C4"]
end
_G.down, _G.up = false, false

_G.i = 0
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.i = _G.i + 1
	local t = mac.time:as_double()
	if _G.key and not _G.down and t >= 60.0 then _G.key:set_value(1); _G.down = true
		print("t=60  ---- C4 held ----") end
	if _G.key and not _G.up and t >= 70.0 then _G.key:set_value(0); _G.up = true
		print("t=70  ---- C4 released ----") end
	if (_G.i % 1800) ~= 0 then return end
	print(string.format("t=%6.1f  sel=%d data=%d | blk0=%d (gate=%d free=%d computed=%d) chan=%d glob=%d"
		.. " | reads bank=%d mag=%d other=%d",
		t, _G.n.addr, _G.n.data, _G.n.blk0, _G.n.gate, _G.n.free, _G.n.computed,
		_G.n.chan, _G.n.glob, _G.n.rd_bank, _G.n.rd_mag, _G.n.rd_other))
end)

_G.stop = emu.add_machine_stop_notifier(function ()
	print("---- 0x0010C000 traffic, whole run ----")
	for k, v in pairs(_G.n) do print(string.format("  %-9s %d", k, v)) end
	print("---- first 20 gates ----")
	for _, g in ipairs(_G.gatelist) do print("  " .. g) end
	print("---- high bytes seen on computed block-0 words ----")
	local ks = {}
	for k in pairs(_G.first) do ks[#ks + 1] = k end
	table.sort(ks)
	for _, k in ipairs(ks) do print(string.format("  %s x%d", k, _G.first[k])) end
	if _G.n.gate == 0 then
		print("RESULT: no channel was ever GATED -- the busy model is correct but not yet observable")
	else
		print("RESULT: channels were gated; the busy latch is live")
	end
end)
