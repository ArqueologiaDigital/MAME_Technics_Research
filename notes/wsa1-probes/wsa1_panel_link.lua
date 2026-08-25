-- QUESTION IT ANSWERS: with the control-panel HLE wired up, does CPU 1's
-- serial channel 1 actually carry traffic in both directions, and does the
-- machine still boot to the same screen?
--
-- What it reads, and why each signal means what it says:
--
--   SFR 0x54 SC1BUF  every byte the firmware clocks out (eleven `ld (0x54),A`
--                    sites, prom_b) and the two it reads back (0xF5AEEE,
--                    0xF5AF51).  ⚠ 0x54 is an odd byte in a 16-bit space, so the
--                    tap covers the word 0x54-0x55 and the count is per ACCESS.
--   RAM  (0x2A85)    bit 3 is set by SC1_Cmd_E0_ReadStatus (prom_b 0xF5AAA9)
--                    if and only if the rx WRITE index moved while it waited --
--                    i.e. "the panel answered".  THIS IS THE HANDSHAKE FLAG.
--   RAM  (0x2A80)    the SC1 state machine's state byte, used as a byte offset
--                    into the 11-entry table at 0xF5AC67.
--   RAM 0x20D0..7    Panel_RefreshLeds' LED WANT buffer; 0x20F0..7 is what it
--                    believes it has already sent.  Non-zero means the
--                    foreground is asking for LEDs.
--   RAM  (0x219A)    the count of decoded panel events waiting at 0x2000.
--
-- Snapshots every 15 emulated seconds into snap/wsa1r/.
--
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 130 -window \
--       -autoboot_script .../wsa1_panel_link.lua
_G.txr, _G.txw = 0, 0
_G.log = {}
local sp = manager.machine.devices[":cpu1"].spaces["program"]
-- ⚠ 0x54 (SC1BUF) and 0x55 (SC1CR) share one 16-bit word, so the tap sees both.
-- Separate them by the byte lane: mask 0x00FF is SC1BUF, 0xFF00 is SC1CR.
_G.t1 = sp:install_write_tap(0x000054, 0x000055, "sc1w",
	function (o, d, m)
		if (m & 0x00ff) ~= 0 then
			_G.txw = _G.txw + 1
			if #_G.log < 400 then
				_G.log[#_G.log+1] = string.format("%7.3f TX %02X",
					manager.machine.time:as_double(), d & 0xff)
			end
		end
		return d
	end)
_G.t2 = sp:install_read_tap(0x000054, 0x000055, "sc1r",
	function (o, d, m)
		if (m & 0x00ff) ~= 0 then
			_G.txr = _G.txr + 1
			if #_G.log < 400 then
				_G.log[#_G.log+1] = string.format("%7.3f RX %02X",
					manager.machine.time:as_double(), d & 0xff)
			end
		end
		return d
	end)
_G.dump = emu.add_machine_stop_notifier(function ()
	print("---- SC1BUF byte log ----")
	for _, l in ipairs(_G.log) do print(l) end
	print(string.format("---- %d bytes out, %d in ----", _G.txw, _G.txr))
end)

local function rb(a) return sp:read_u8(a) end

_G.n, _G.shots = 0, 0
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.n = _G.n + 1
	if (_G.n % 300) ~= 0 then return end           -- every 5 s at 60 fps
	local leds = ""
	for a = 0x20d0, 0x20d7 do leds = leds .. string.format("%02X", rb(a)) end
	local sent = ""
	for a = 0x20f0, 0x20f7 do sent = sent .. string.format("%02X", rb(a)) end
	print(string.format(
		"t=%6.1f  sc1_w=%-5d sc1_r=%-4d  state=%02X flags2A85=%02X  ledwant=%s ledsent=%s  events=%d  pc=%06X",
		manager.machine.time:as_double(), _G.txw, _G.txr,
		rb(0x2a80), rb(0x2a85), leds, sent, rb(0x219a),
		manager.machine.devices[":cpu1"].state["CURPC"].value))
	if (_G.n % 900) == 0 then
		_G.shots = _G.shots + 1
		manager.machine.video:snapshot()
		print(string.format("SHOT %d at t=%.1f", _G.shots, manager.machine.time:as_double()))
	end
end)
