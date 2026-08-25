-- QUESTION IT ANSWERS: when the panel HLE asks for the link, does CPU 1's INT6
-- handler ever run -- and if not, what happened to the request?
--
-- Three signals, all on CPU 1:
--   SFR 0x72 INTE67   bits 2:0 = INT6's priority LEVEL, bit 3 = its REQUEST flag.
--                     The SC1 module writes 0x85 (level 5, INT6 armed) and 0x8F
--                     (level 7, which tlcs900_check_irqs never dispatches).
--                     ⚠ Writing bit 3 = 0 CLEARS a pending request, so a 0x85 or
--                     0x8F write that arrives while a request is latched but
--                     masked THROWS THE REQUEST AWAY.
--   RAM (0x2A80)      the SC1 state byte.  0x04 = SC1_StartWordTx has begun a
--                     transmit; 0x20 = INT6_SC1_PeerRequest accepted a request
--                     and is expecting the first received byte.  SEEING 0x20 IS
--                     THE PROOF THAT INT6 WAS DISPATCHED.
--   SFR 0x54 SC1BUF   bytes out (low lane of the 0x54-0x55 word) and in.
--
-- Prints the first 300 events with timestamps, then a summary.
--
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 60 -window \
--       -autoboot_script .../wsa1_sc1_handshake.lua
_G.ev, _G.n20, _G.nrx, _G.ntx = {}, 0, 0, 0
local sp = manager.machine.devices[":cpu1"].spaces["program"]

local function note(s)
	if #_G.ev < 300 then
		_G.ev[#_G.ev+1] = string.format("%8.4f  %s", manager.machine.time:as_double(), s)
	end
end

_G.t_inte = sp:install_write_tap(0x000072, 0x000073, "inte67",
	function (o, d, m)
		if (m & 0x00ff) ~= 0 then note(string.format("INTE67 <- %02X", d & 0xff)) end
		return d
	end)

_G.t_state = sp:install_write_tap(0x002a80, 0x002a81, "state",
	function (o, d, m)
		if (m & 0x00ff) ~= 0 then
			local v = d & 0xff
			if v == 0x20 then _G.n20 = _G.n20 + 1 end
			note(string.format("SC1 state <- %02X", v))
		end
		return d
	end)

_G.t_txw = sp:install_write_tap(0x000054, 0x000055, "sc1w",
	function (o, d, m)
		if (m & 0x00ff) ~= 0 then
			_G.ntx = _G.ntx + 1
			note(string.format("TX %02X   (o=%04X m=%04X pc=%06X)", d & 0xff, o, m,
				manager.machine.devices[":cpu1"].state["CURPC"].value))
		end
		return d
	end)
_G.t_txr = sp:install_read_tap(0x000054, 0x000055, "sc1r",
	function (o, d, m)
		if (m & 0x00ff) ~= 0 then
			_G.nrx = _G.nrx + 1
			note(string.format("RX %02X   (o=%04X m=%04X pc=%06X)", d & 0xff, o, m,
				manager.machine.devices[":cpu1"].state["CURPC"].value))
		end
		return d
	end)

_G.dump = emu.add_machine_stop_notifier(function ()
	for _, l in ipairs(_G.ev) do print(l) end
	print(string.format("---- tx=%d rx=%d  state-0x20 entries (INT6 dispatched)=%d ----",
		_G.ntx, _G.nrx, _G.n20))
end)
