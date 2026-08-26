-- wsa1r_layout_button.lua -- does a button WIRED BY THE LAYOUT actually reach the
-- firmware, and does the firmware do the thing the legend says?
--
-- WHY IT READS THE .lay: driving "CP_SEG7 bit 0x08" from a hand-typed constant
-- would only prove the DEVICE works.  This rig opens
-- src/mame/layout/wsa1r.lay, finds the placement whose comment carries the
-- legend it was asked for, and drives the inputtag/inputmask THAT LINE binds.
-- So a wrong binding in the layout shows up here as a wrong (or absent) result.
--
--   BTN="MENU DISK" SNAP_AT=45 DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms \
--       -skip_gameinfo -window -nomax -snapshot_directory <dir> \
--       -autoboot_script ~/compartilhado/kn7000_mame/tools/rigs/wsa1r_layout_button.lua
--
-- Environment:
--   BTN      legend to press, as it appears in the .lay comment  (default "MENU DISK")
--   SNAP_AT  emulated seconds to wait before pressing            (default 45)
--   LAY      path to the layout                                  (default the overlay's)
--
-- Signals, all from CPU 1 RAM and the LCD port, exactly as
-- notes/wsa1-probes/wsa1_ui_press_sweep.lua uses them:
--   (0x2078)/(0x2079) family-A screen, current / requested   (prom_a 0xF864FA)
--   (0x207C)/(0x207D) family-B screen, current / requested   (prom_a 0xF864B0)
--   writes to 0x790000  = the SED1330 data port, i.e. "it repainted"
--   writes of 0x20 to (0x2A80) = INT6_SC1_PeerRequest dispatches, i.e. "the panel
--                                got the CPU's attention at all" (prom_b 0xF5AC0A)
--   writes to 0x2B20..0x2B3F   = the panel's own per-wire button shadow, i.e.
--                                "the firmware decoded a button packet"
--
-- Two snapshots are taken, before the press and after it, so the screen change is
-- visible as well as counted.
--
-- ⚠ Held in a global.  A notifier kept only in a local is collected by MAME's Lua
-- GC and then silently never fires.

local m       = manager.machine
local WANT    = os.getenv("BTN") or "MENU DISK"
-- Optional second press, made AFTER the first one has settled.  This is how the
-- firmware itself is asked which physical key sits beside which screen row: put a
-- menu up with BTN, then press one soft key with BTN2 and see which entry runs.
local WANT2   = os.getenv("BTN2")
local AT      = tonumber(os.getenv("SNAP_AT")) or 45
local LAY     = os.getenv("LAY")
	or "/home/fsanches/compartilhado/kn7000_mame/src/mame/layout/wsa1r.lay"

-- ---------------------------------------------------------------- the binding
local tag, mask, seen = nil, nil, 0
local f = io.open(LAY, "r")
if f == nil then
	emu.print_error("LAYOUT NOT FOUND: " .. LAY)
	m:exit()
	return
end
for line in f:lines() do
	local t, mk = line:match('inputtag="cpanel:(CP_SEG%d+)" inputmask="0x(%x%x)"')
	if t ~= nil then
		seen = seen + 1
		local cm = line:match("<!%-%-(.-)%-%->")
		if cm ~= nil and cm:find(WANT, 1, true) ~= nil and tag == nil then
			tag, mask = t, tonumber(mk, 16)
			emu.print_error(string.format("LAYOUT BINDING  %s -> cpanel:%s mask 0x%02X",
				WANT, tag, mask))
		end
	end
end
f:close()
emu.print_error(string.format("LAYOUT has %d bound buttons", seen))
if tag == nil then
	emu.print_error("NO LAYOUT BINDING for legend: " .. WANT)
	m:exit()
	return
end

local tag2, mask2 = nil, nil
if WANT2 ~= nil then
	local f2 = io.open(LAY, "r")
	for line in f2:lines() do
		local t, mk = line:match('inputtag="cpanel:(CP_SEG%d+)" inputmask="0x(%x%x)"')
		if t ~= nil then
			local cm = line:match("<!%-%-(.-)%-%->")
			if cm ~= nil and cm:find(WANT2, 1, true) ~= nil and tag2 == nil then
				tag2, mask2 = t, tonumber(mk, 16)
			end
		end
	end
	f2:close()
	if tag2 == nil then
		emu.print_error("NO LAYOUT BINDING for second legend: " .. WANT2)
		m:exit()
		return
	end
	emu.print_error(string.format("SECOND BINDING  %s -> cpanel:%s mask 0x%02X",
		WANT2, tag2, mask2))
end

local port = m.ioport.ports[":cpanel:" .. tag]
if port == nil then
	emu.print_error("NO SUCH PORT :cpanel:" .. tag)
	m:exit()
	return
end
local field = nil
for _, fl in pairs(port.fields) do
	if fl.mask == mask then field = fl end
end
if field == nil then
	emu.print_error(string.format("NO FIELD with mask 0x%02X in %s", mask, tag))
	m:exit()
	return
end
emu.print_error("FIELD NAME      " .. field.name)

local field2 = nil
if tag2 ~= nil then
	for _, fl in pairs(m.ioport.ports[":cpanel:" .. tag2].fields) do
		if fl.mask == mask2 then field2 = fl end
	end
end

-- The firmware's own per-wire VALUE shadow for THIS segment.  SC1_RxOp0_ThreeByte
-- (prom_b 0xF5B0FD) computes the index as (wire & 0x0F) | ((wire & 0x40) >> 2) and
-- `ex (XHL),A` stores the new segment mask there, so this byte going from 0 to the
-- pressed mask and back is the firmware DECODING this exact button, not merely
-- taking an interrupt.
local WIRE   = 0xC0 | tonumber(tag:match("CP_SEG(%d+)"))
local SHADOW = 0x2B20 + ((WIRE & 0x0F) | ((WIRE & 0x40) >> 2))
emu.print_error(string.format("WIRE 0x%02X -> shadow byte (0x%04X)", WIRE, SHADOW))

-- ---------------------------------------------------------------- the signals
_G.WB = _G.WB or {}
_G.WB.lcd, _G.WB.int6, _G.WB.shadow = 0, 0, 0
local sp = m.devices[":cpu1"].spaces["program"]
_G.WB.taps = {
	sp:install_write_tap(0x790000, 0x790001, "lcd",
		function (o, d, k) _G.WB.lcd = _G.WB.lcd + 1 return d end),
	sp:install_write_tap(0x002a80, 0x002a81, "int6",
		function (o, d, k)
			if (k & 0x00ff) ~= 0 and (d & 0xff) == 0x20 then _G.WB.int6 = _G.WB.int6 + 1 end
			return d
		end),
	sp:install_write_tap(0x002b20, 0x002b3f, "shadow",
		function (o, d, k) _G.WB.shadow = _G.WB.shadow + 1 return d end),
}

-- The lamp outputs the layout binds, so a press can be shown to move a LAMP and
-- not just a RAM byte.  led%u = LED register*8 + bit (wsa1_cpanel.cpp).
local function lamps()
	local t = {}
	for i = 0, 63 do t[i] = m.output:get_value(string.format("led%d", i)) end
	t[-1] = m.output:get_value("check_led")
	return t
end

local function lamp_diff(a, b)
	local out = {}
	for i = -1, 63 do
		if a[i] ~= b[i] then
			out[#out+1] = string.format("%s %d->%d",
				(i < 0) and "check_led" or ("led" .. i), a[i], b[i])
		end
	end
	return (#out == 0) and "none" or table.concat(out, ", ")
end

local function screens()
	return string.format("%02X/%02X %02X/%02X",
		sp:read_u8(0x2078), sp:read_u8(0x2079), sp:read_u8(0x207c), sp:read_u8(0x207d))
end

-- ---------------------------------------------------------------- the sequence
_G.WB.phase, _G.WB.timer = "wait", 0
_G.WB.h = emu.add_machine_frame_notifier(function ()
	if m.time:as_double() < AT then return end

	if _G.WB.phase == "wait" then
		_G.WB.b_lcd, _G.WB.b_int6, _G.WB.b_shadow = _G.WB.lcd, _G.WB.int6, _G.WB.shadow
		_G.WB.b_scr = screens()
		_G.WB.b_lamp = lamps()
		m.video:snapshot()                       -- BEFORE
		emu.print_error(string.format("BEFORE t=%.1f screens %s  (0x%04X)=%02X",
			m.time:as_double(), _G.WB.b_scr, SHADOW, sp:read_u8(SHADOW)))
		field:set_value(1)
		_G.WB.phase, _G.WB.timer = "hold", 30    -- ~0.5 s at 60 Hz
	elseif _G.WB.phase == "hold" and _G.WB.timer == 15 then
		_G.WB.held_shadow = sp:read_u8(SHADOW)   -- mid-press: the mask must be THERE
		_G.WB.timer = _G.WB.timer - 1
	elseif _G.WB.phase == "hold" then
		_G.WB.timer = _G.WB.timer - 1
		if _G.WB.timer <= 0 then
			field:set_value(0)
			_G.WB.phase, _G.WB.timer = "settle", 90
		end
	elseif _G.WB.phase == "settle" then
		_G.WB.timer = _G.WB.timer - 1
		if _G.WB.timer <= 0 then
			local s = screens()
			emu.print_error(string.format(
				"AFTER  t=%.1f screens %s   dLCD=%d dINT6=%d dSHADOW=%d   %s",
				m.time:as_double(), s,
				_G.WB.lcd - _G.WB.b_lcd, _G.WB.int6 - _G.WB.b_int6,
				_G.WB.shadow - _G.WB.b_shadow,
				(s ~= _G.WB.b_scr) and "*** SCREEN CHANGED" or "screen unchanged"))
			emu.print_error(string.format(
				"SHADOW (0x%04X) while HELD = %02X, expected %02X -> %s",
				SHADOW, _G.WB.held_shadow or 0xFF, mask,
				((_G.WB.held_shadow or 0) == mask)
					and "*** THE FIRMWARE DECODED THIS EXACT BUTTON"
					or  "not decoded"))
			emu.print_error("LAMPS  " .. lamp_diff(_G.WB.b_lamp, lamps()))
			m.video:snapshot()                   -- AFTER
			if field2 ~= nil then
				field2:set_value(1)
				_G.WB.phase, _G.WB.timer = "hold2", 30
			else
				_G.WB.phase = "done"
				m:exit()
			end
		end
	elseif _G.WB.phase == "hold2" then
		_G.WB.timer = _G.WB.timer - 1
		if _G.WB.timer <= 0 then
			field2:set_value(0)
			_G.WB.phase, _G.WB.timer = "settle2", 90
		end
	elseif _G.WB.phase == "settle2" then
		_G.WB.timer = _G.WB.timer - 1
		if _G.WB.timer <= 0 then
			emu.print_error(string.format("SECOND t=%.1f screens %s  after pressing %s",
				m.time:as_double(), screens(), WANT2))
			m.video:snapshot()                   -- AFTER the second press
			_G.WB.phase = "done"
			m:exit()
		end
	end
end)
