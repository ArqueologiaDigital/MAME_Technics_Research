-- Does a power-on SERVICE-MODE chord reach the screen dispatcher -- and if not,
-- how far up the panel chain does a press actually get?
--
-- QUESTION IT ANSWERS.  The ROM says this machine has service screens and says
-- exactly which held control selects each one.  This script holds that chord from
-- t = 0, then presses the same control AGAIN after the boot, and reports every
-- stage of the chain, so that "the chord is decoded correctly out of the ROM" and
-- "the chord fires in this emulator" stay separate claims.
--
-- ★ THE INSTRUMENT IS THE POINT.  "Did an LCD write happen" is the WRONG probe for
-- a panel press: 459 of the 654 dispatch-matrix handler slots are the single
-- address 0xFF42B1, and 0xFF42B1 is a bare `ret`, so most positions doing nothing
-- on the play screen is EXPECTED.  The sensitive stages, in order of proximity to
-- the wire, are the four this script watches:
--
--   1. RAM 0x2B20 + ((wire & 0x0F) | ((wire & 0x40) >> 2))
--        the per-wire VALUE shadow.  SC1_RxOp0_ThreeByte (prom_b 0xF5B0FD) does
--        `ex (XHL),A` at 0xF5B10F, so the shadow takes the new value and the XOR
--        that follows is the change mask that gets queued.  SEG1 = wire 0xC1 =
--        0x2B31.  A press that does not move this NEVER REACHED CPU 1.
--   2. RAM 0x2082 = (pressed ? 0x80 : 0) | control index, written at 0xF8618F
--   3. RAM 0x2070 / 0x2071   a screen was REQUESTED (id, then a flag bit)
--   4. RAM 0x207C            the screen the dispatcher is actually on
--
-- THE TWO CHORDS, both re-read from the ROM by wsa1_service_screen_refutation.py:
--   wsa1r  (0xC4)=2  ONE panel button in SEG1; sub_F953CD tests (0x2B31) for
--                    EQUALITY: 04 -> 0xD9  08 -> 0xDA  10 -> 0xDB  20 -> 0xDC
--   wsa1   (0xC4)=1  TWO KEYBED KEYS an octave apart; sub_F9530B remote-reads
--                    eight bytes from CPU 2's 0x0000FFF0 and needs popcount == 2:
--                    D4+D5 -> 0xD9  E4+E5 -> 0xDA  F4+F5 -> 0xDB  G4+G5 -> 0xDC
--
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 80 -window \
--       -autoboot_script .../wsa1_service_entry.lua
--
-- Pick the target with WSA1_SERVICE_SCREEN=D9|DA|DB|DC (default D9).
-- PASS = (0x207C) reaches 0xD8..0xDD.  Every stage is printed either way, so a
-- FAIL says WHERE it stopped rather than just that it stopped.

local want = (os.getenv("WSA1_SERVICE_SCREEN") or "D9"):upper()
local sel  = { D9 = 0x04, DA = 0x08, DB = 0x10, DC = 0x20 }
local keypair = { D9 = { "D4", "D5" }, DA = { "E4", "E5" },
                  DB = { "F4", "F5" }, DC = { "G4", "G5" } }
local bitmask = sel[want] or 0x04
local keys    = keypair[want] or keypair.D9

local mac   = manager.machine
local cpu1  = mac.devices[":cpu1"].spaces["program"]
_G.cpu2 = mac.ioport.ports[":KEY2"] and mac.devices[":cpu2"].spaces["program"] or nil
local ports = mac.ioport.ports

_G.held = {}
if ports[":KEY2"] then
	_G.held[#_G.held + 1] = ports[":KEY2"].fields[keys[1]]
	_G.held[#_G.held + 1] = ports[":KEY3"].fields[keys[2]]
	print(string.format("chord: keybed %s + %s  -> screen 0x%s", keys[1], keys[2], want))
else
	for _, f in pairs(ports[":cpanel:CP_SEG1"].fields) do
		if f.mask == bitmask then _G.held[#_G.held + 1] = f end
	end
	print(string.format("chord: panel SEG1 mask 0x%02X -> screen 0x%s", bitmask, want))
end
if #_G.held == 0 then print("ERROR: no field matched -- nothing is being held") end
for _, f in ipairs(_G.held) do f:set_value(1) end

local function now() return mac.time:as_double() end
local function pc() return mac.devices[":cpu1"].state["CURPC"].value end

_G.shadow, _G.ctrl, _G.reqs = {}, {}, {}
-- ⚠ 16-bit bus: a tap's `offset` is the WORD base and the byte lane is in the
-- mask, so an odd byte address arrives as (base, mask 0xFF00).  Decoding that
-- here is not cosmetic -- reading the wrong lane turns "wire 0xC1 never reports"
-- into "wire 0xC1 reports nonsense", which is a different bug.
local function lane(o, d, m)
	if (m & 0x00ff) ~= 0 then return o, d & 0xff end
	return o + 1, (d >> 8) & 0xff
end
_G.t_shadow = cpu1:install_write_tap(0x2b20, 0x2b3f, "panelshadow", function (o, d, m)
	if #_G.shadow < 80 then
		local a, v = lane(o, d, m)
		_G.shadow[#_G.shadow + 1] = string.format("t=%6.2f pc=%06X (0x%04X)<-%02X", now(), pc(), a, v)
	end
	return d
end)
-- ⚠ Taps must cover a whole 16-bit word on this bus; the byte lane is separated
-- by the access mask, exactly as wsa1_sc1_handshake.lua does for SC1BUF/SC1CR.
_G.t_ctrl = cpu1:install_write_tap(0x2082, 0x2083, "ctrlbyte", function (o, d, m)
	if #_G.ctrl < 60 and (m & 0x00ff) ~= 0 then
		_G.ctrl[#_G.ctrl + 1] = string.format("t=%6.2f pc=%06X (0x2082)<-%02X", now(), pc(), d & 0xff)
	end
	return d
end)
_G.t_req = cpu1:install_write_tap(0x2070, 0x2071, "screenreq", function (o, d, m)
	if #_G.reqs < 60 then
		_G.reqs[#_G.reqs + 1] = string.format("t=%6.2f pc=%06X (0x%04X)<-%04X", now(), pc(), o, d)
	end
	return d
end)

_G.n, _G.best, _G.repressed, _G.snapped = 0, 0, false, false
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.n = _G.n + 1

	-- Release and re-press after the boot, so one run also answers "does a press
	-- reach CPU 1 at all once the machine is up?".
	if not _G.repressed and now() >= 50.0 then
		_G.repressed = true
		for _, f in ipairs(_G.held) do f:set_value(0) end
		print(string.format("t=%6.2f  ---- released ----", now()))
	end
	if _G.repressed and now() >= 55.0 and not _G.snapped then
		_G.snapped = true
		for _, f in ipairs(_G.held) do f:set_value(1) end
		print(string.format("t=%6.2f  ---- pressed again ----", now()))
	end

	if (_G.n % 300) ~= 0 then return end

	-- KEYBOARD ONLY: the chord's raw material is CPU 2's 61-key state bitmap at
	-- 0x0000FFF0 (KeyScan_InitKeyStateBitmap, prom_c 0xF9988D).  sub_F9530B needs
	-- POPCOUNT == 2 across those eight bytes, so printing the popcount separates
	-- "CPU 1 never asked" from "there was nothing to find".
	if _G.cpu2 then
		local bits, hex = 0, {}
		for i = 0, 7 do
			local b = _G.cpu2:read_u8(0x0000fff0 + i)
			hex[#hex + 1] = string.format("%02X", b)
			while b ~= 0 do bits = bits + (b & 1); b = b >> 1 end
		end
		print(string.format("            cpu2 keybitmap 0x0000FFF0 = %s  popcount=%d (the chord needs 2)",
			table.concat(hex, " "), bits))
	end
	local s7c = cpu1:read_u8(0x207c)
	if s7c > _G.best then _G.best = s7c end
	print(string.format("t=%6.1f  (2070)=%02X (2071)=%02X (207A)=%02X (207C)=%02X  (2B31)=%02X (2082)=%02X",
		now(), cpu1:read_u8(0x2070), cpu1:read_u8(0x2071), cpu1:read_u8(0x207a),
		s7c, cpu1:read_u8(0x2b31), cpu1:read_u8(0x2082)))
end)

_G.stop = emu.add_machine_stop_notifier(function ()
	local function dump(label, t)
		print("---- " .. label .. " (" .. #t .. ") ----")
		for _, r in ipairs(t) do print("  " .. r) end
	end
	dump("stage 1: panel value shadow 0x2B20-0x2B3F", _G.shadow)
	dump("stage 2: control byte 0x2082", _G.ctrl)
	dump("stage 3: screen request 0x2070/0x2071", _G.reqs)
	local s7c = cpu1:read_u8(0x207c)
	print(string.format("FINAL (207C)=%02X  highest seen=%02X", s7c, _G.best))
	if s7c >= 0xd8 and s7c <= 0xdd then
		print("PASS: a SERVICE SCREEN is on the dispatcher")
	else
		print("FAIL: the chord never reached the dispatcher")
	end
end)
