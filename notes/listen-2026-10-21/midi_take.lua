-- midi_take.lua -- one take of the listening test's MIDI file (listen.mid on -midiin1), README.md here.
-- rig-machine: kn7000 (-bios v13, program 893)
--
-- QUESTION IT SERVES: what does listen.mid sound like on the instrument's own wave ROMs with the panel REVERB on (its
-- boot state) and off? It only sets the REVERB state and logs it; the file does the playing.
--   LT_OUT     log folder (LT_OUT/take.txt) and snapshot folder is MAME's -snapshot_directory
--   LT_REVERB  "on" (leave the boot state) or "off" (press REVERB, CPR_SEG3 0x04, at emulated 27.0 s for 0.3 s)
--   LT_END     emulated time to exit (default 69: listen.mid ends at 68)
-- The REVERB state is read back from the firmware's own LED output cpr_led27 (1 = on), at 26.5 s, 28.5 s, at the
-- first note (30.0) and at the end; a snapshot of the screen is taken at 29.5 s. The firmware's DSP dead flag
-- (893: 0x500066D8) is logged too.
local M = manager.machine
local OUT = assert(os.getenv("LT_OUT"), "set LT_OUT")
local REVERB = os.getenv("LT_REVERB") or "on"
local TEND = tonumber(os.getenv("LT_END") or "69")
local DEAD = 0x500066D8
local sp = M.devices[":maincpu"].spaces["program"]
local log = assert(io.open(OUT .. "/take.txt", "w"))
local function now() return M.time:as_double() end
local function W(fmt, ...) log:write(string.format(fmt, ...) .. "\n"); log:flush() end
local function field(port, mask)
  local p = M.ioport.ports[":cpanel:" .. port] or M.ioport.ports[":" .. port]
  for _, f in pairs(p.fields) do if f.mask == mask then return f end end
  error("no field " .. port .. " " .. mask)
end
local REV = field("CPR_SEG3", 0x04)
local function led(n) return math.floor(M.output:get_value(n) or 0) end
local function st(what)
  W("t=%.3f %s reverb_led=%d chorus_led=%d dead=%02X", now(), what, led("cpr_led27"), led("cpr_led29"), sp:read_u8(DEAD))
end
local steps = {
  { 26.5, function() st("before (boot state)") end },
  { 27.0, function() if REVERB == "off" then REV:set_value(1); st("REVERB press") end end },
  { 27.3, function() REV:set_value(0) end },
  { 28.5, function() st("after the press window (LT_REVERB=" .. REVERB .. ")") end },
  { 29.5, function() M.video:snapshot(); st("snapshot") end },
  { 30.0, function() st("first note") end },
  { TEND, function() st("end"); log:close(); M:exit() end },
}
local nexts = 1
W("installed: LT_REVERB=%s LT_END=%.1f", REVERB, TEND)
_G.LT = emu.add_machine_frame_notifier(function()
  local t = now()
  while nexts <= #steps and t >= steps[nexts][1] do steps[nexts][2](); nexts = nexts + 1 end
end)
