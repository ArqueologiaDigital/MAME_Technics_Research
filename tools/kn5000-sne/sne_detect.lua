-- "Sound Name Error" detector for the KN5000 maincpu.
--
-- Exact detector: the ONLY reference to the string 0xEED2A8 in the whole 2 MB program
-- ROM is the copy loop at 0xFEE6A1 (`ld A,(XBC+)`), reached from 0xFEE694 when the
-- name lookup at 0xFEE55A returns a non-zero status.  So a data read of 0xEED2A8
-- happens if and only if the firmware writes "Sound Name Error" into a name buffer.
--
-- Tap A (detailed) covers all three fallback strings:
--   0xEED298 "WRONG SW NUMBER!"  (copied at 0xFEE63F, a different lookup)
--   0xEED2A8 "Sound Name Error"  (copied at 0xFEE6A1)
--   0xEED2B9 "SName Error!!"     (referenced at 0xFEE754)
-- Tap B (counter only) is the POSITIVE CONTROL: a 64 KB window of the same program
-- ROM.  If tap B's count is 0 the tap machinery is not seeing ROM data reads at all
-- and tap A's zero would prove nothing.
--
-- Optional env: SNE_SCHEDULE = path to a press-schedule lua to dofile() afterwards.

local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local sp   = cpu.spaces["program"]
local st   = cpu.state
local function T() return mach.time.seconds + mach.time.attoseconds/1e18 end
local function log(s) emu.print_error("SNE| " .. s) end

log(string.format("space data_width=%d shift=%d", sp.data_width, sp.shift))

_G.SNE = { sne = 0, wrong = 0, sname = 0, ctrl = 0, events = {} }

local function ctx()
	local pc  = st["PC"].value
	local xsp = st["XSSP"].value
	local ok, s = pcall(function()
		return string.format("PC=%06X XSP=%06X argC=%02X argA=%02X dest=%06X",
			pc, xsp, sp:read_u8(xsp + 6), sp:read_u8(xsp + 8), sp:read_u32(xsp + 2))
	end)
	if not ok then s = string.format("PC=%06X XSP=%06X <mem read failed>", pc, xsp) end
	local banks = {}
	for i = 0, 3 do banks[#banks+1] = string.format("%08X", st["XWA"..i].value) end
	return s .. "  XWA0..3=" .. table.concat(banks, ",")
end

_G.SNE.tapA = sp:install_read_tap(0xEED290, 0xEED2C7, "sne_strings",
	function(off, data, mask)
		local a = off
		if a >= 0xEED2A8 and a <= 0xEED2B8 then
			_G.SNE.sne = _G.SNE.sne + 1
			if a <= 0xEED2A9 then   -- first word of the string = one copy loop start
				local line = string.format("!!! SOUND-NAME-ERROR t=%.3f addr=%06X n=%d  %s",
					T(), a, _G.SNE.sne, ctx())
				log(line)
				_G.SNE.events[#_G.SNE.events+1] = line
			end
		elseif a >= 0xEED298 and a <= 0xEED2A7 then
			_G.SNE.wrong = _G.SNE.wrong + 1
			if a <= 0xEED299 then
				local line = string.format("!!! WRONG-SW-NUMBER t=%.3f addr=%06X n=%d  %s",
					T(), a, _G.SNE.wrong, ctx())
				log(line)
				_G.SNE.events[#_G.SNE.events+1] = line
			end
		elseif a >= 0xEED2B9 then
			_G.SNE.sname = _G.SNE.sname + 1
			if a <= 0xEED2BA then
				local line = string.format("!!! SNAME-ERROR t=%.3f addr=%06X n=%d  %s",
					T(), a, _G.SNE.sname, ctx())
				log(line)
				_G.SNE.events[#_G.SNE.events+1] = line
			end
		end
	end)

-- POSITIVE CONTROL: any data read anywhere in 0xEE0000..0xEEFFFF of the same ROM.
_G.SNE.tapB = sp:install_read_tap(0xEE0000, 0xEEFFFF, "sne_control",
	function(off, data, mask)
		_G.SNE.ctrl = _G.SNE.ctrl + 1
	end)

local last = -1
_G.SNE.timer = emu.register_periodic(function()
	local t = math.floor(T())
	if t > last and (t % 5) == 0 then
		last = t
		log(string.format("t=%3ds  SoundNameError=%d  WrongSwNumber=%d  SNameError=%d  CONTROL(ROM reads in 0xEExxxx)=%d",
			t, _G.SNE.sne, _G.SNE.wrong, _G.SNE.sname, _G.SNE.ctrl))
	end
end)

local function final_report()
	log(string.format("FINAL  SoundNameError=%d  WrongSwNumber=%d  SNameError=%d  CONTROL=%d",
		_G.SNE.sne, _G.SNE.wrong, _G.SNE.sname, _G.SNE.ctrl))
	for _, l in ipairs(_G.SNE.events) do log("EVENT " .. l) end
end
_G.SNE.final_report = final_report
local ok, err = pcall(function()
	_G.SNE.stopnotifier = mach:add_machine_stop_notifier(final_report)
end)
if not ok then log("no stop notifier: " .. tostring(err)) end

local sched = os.getenv("SNE_SCHEDULE")
if sched and #sched > 0 then
	log("loading schedule " .. sched)
	dofile(sched)
else
	log("no schedule (boot-only run)")
end
