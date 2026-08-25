-- QUESTION: can any single front-panel button make the FIRMWARE talk to the
-- floppy controller -- and if so, which one?
--
-- wsa1_fdc_probe.lua established that a 200-second boot never touches the FDC:
-- Fdc_Request (prom_a 0xFE66C7) has eight call sites and none is on the boot
-- path.  The service manual's disk menu (DISK LOAD / DISK SAVE / MIDI FILE
-- DIRECT PLAY / DISK FORMAT / LOAD SINGLE SOUND / LOAD SINGLE COMBINATION) is
-- reached from a button, and which button is which legend is emulation gap O,
-- unanswered.  So: press each panel position in turn, one at a time, and watch
-- the two FDC register windows.
--
-- A hit names a (segment, bit) pair AND demonstrates the whole path -- panel
-- MCU HLE -> serial channel 1 -> INT6 -> prom_b's SC1 module -> prom_a's
-- display lists -> Fdc_Request -> upd765a_device.
--
-- Buttons are held for HOLD_FRAMES and released for GAP_FRAMES, and the sweep
-- only starts after START_S seconds, because CPU 1 does not reach the panel
-- until about t=75 s of emulated time (see README.md).
--
-- Run:
--   cd ~/compartilhado/kn7000_mame_build
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 260 -window \
--       -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_fdc_button_sweep.lua
--
-- ⚠ Taps and notifiers are held in globals; MAME's Lua GC collects them
-- otherwise.

local START_S     = 110      -- emulated seconds before the first press
local HOLD_FRAMES = 30       -- 0.5 s held
local GAP_FRAMES  = 30       -- 0.5 s released

_G.hits = 0
_G.sp = manager.machine.devices[":cpu1"].spaces["program"]
_G.taps = {}
local function bump(what)
	_G.hits = _G.hits + 1
	print(string.format("FDC-ACCESS %-6s t=%.2f  while holding %s",
		what, manager.machine.time:as_double(), _G.holding or "(nothing)"))
end
_G.taps[#_G.taps+1] = _G.sp:install_read_tap(0x7b0004, 0x7b0005, "r7b",
	function (o, d, m) bump("7B r") return d end)
_G.taps[#_G.taps+1] = _G.sp:install_write_tap(0x7b0004, 0x7b0005, "w7b",
	function (o, d, m) bump("7B w") return d end)
_G.taps[#_G.taps+1] = _G.sp:install_read_tap(0x7a0000, 0x7a0001, "r7a",
	function (o, d, m) bump("7A r") return d end)
_G.taps[#_G.taps+1] = _G.sp:install_write_tap(0x7a0000, 0x7a0001, "w7a",
	function (o, d, m) bump("7A w") return d end)

-- Build the list of panel positions that actually exist on this machine.
_G.list = {}
for tag, port in pairs(manager.machine.ioport.ports) do
	if tag:find("CP_SEG") then
		for name, field in pairs(port.fields) do
			_G.list[#_G.list+1] = { tag = tag, name = name, field = field }
		end
	end
end
table.sort(_G.list, function (a, b)
	if a.tag == b.tag then return a.name < b.name end
	return a.tag < b.tag
end)
print(string.format("SWEEP: %d panel positions found", #_G.list))

_G.idx, _G.phase, _G.timer, _G.holding = 0, "wait", 0, nil
_G.frames = 0
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.frames = _G.frames + 1
	if manager.machine.time:as_double() < START_S then return end

	if _G.phase == "wait" then
		_G.idx = _G.idx + 1
		if _G.idx > #_G.list then
			if _G.phase ~= "done" then
				_G.phase = "done"
				print(string.format("SWEEP COMPLETE: %d FDC accesses in total", _G.hits))
			end
			return
		end
		local e = _G.list[_G.idx]
		_G.holding = string.format("%s / %s", e.tag, e.name)
		e.field:set_value(1)
		_G.phase, _G.timer = "hold", HOLD_FRAMES
		print(string.format("SWEEP t=%6.1f  press %s", manager.machine.time:as_double(), _G.holding))
	elseif _G.phase == "hold" then
		_G.timer = _G.timer - 1
		if _G.timer <= 0 then
			local e = _G.list[_G.idx]
			e.field:set_value(0)
			_G.phase, _G.timer = "gap", GAP_FRAMES
		end
	elseif _G.phase == "gap" then
		_G.timer = _G.timer - 1
		if _G.timer <= 0 then
			_G.holding = nil
			_G.phase = "wait"
		end
	end
end)
