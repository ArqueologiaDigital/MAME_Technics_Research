-- KN7000: watch a UI-plane glyph pixel to catch the text/glyph blitter PC.
-- RUN WITH: -debug -debugger none
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local dbg  = mach.debugger
local out  = io.open("kn7_wp2.log", "w")
local armed = false
local lastlog = 0
local n = 0
_G._k7w = emu.add_machine_frame_notifier(function()
  local mt = mach.time
  local t = mt.seconds + mt.attoseconds / 1e18
  if not armed then
    armed = true
    cpu.debug:wpset(cpu.spaces["program"], "w", 0x50174bf0, 4,
      "1", "printf \"WP pc=%08X d0=%08X d1=%08X a0=%08X a1=%08X a2=%08X a3=%08X ret=%08X\", pc, d0, d1, a0, a1, a2, a3, d@(sp) ; g")
    dbg.execution_state = "run"
    out:write("armed\n"); out:flush()
  end
  local cl = dbg.consolelog
  for i = lastlog + 1, #cl do
    local line = tostring(cl[i])
    if line:find("^WP") then
      n = n + 1
      if n <= 120 then out:write(string.format("t=%8.3f %s\n", t, line)) end
    end
  end
  lastlog = #cl
  if t >= 25 and not _G._k7w_done then
    _G._k7w_done = true
    out:write(string.format("total: %d\n", n)); out:flush()
  end
end)
