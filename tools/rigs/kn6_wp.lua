-- watchpoints on framebuffer pixels that DO receive content -> catch the blitter PC.
-- RUN WITH: kn6000 -debug -debugger none
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local dbg  = mach.debugger
local out  = io.open("kn6_wp.log", "w")
local armed = false
local lastlog = 0
local n = 0
_G._k6w = emu.add_machine_frame_notifier(function()
  local mt = mach.time
  local t = mt.seconds + mt.attoseconds / 1e18
  if not armed then
    armed = true
    -- gray tile pixel + a border pixel + first content row pixel
    cpu.debug:wpset(cpu.spaces["program"], "w", 0x9ce16a50, 4,
      "1", "printf \"WPA pc=%08X pcval=%08X d0=%08X a0=%08X a1=%08X\", pc, pc, d0, a0, a1 ; g")
    cpu.debug:wpset(cpu.spaces["program"], "w", 0x9ce01420, 4,
      "1", "printf \"WPB pc=%08X d0=%08X a0=%08X a1=%08X\", pc, d0, a0, a1 ; g")
    dbg.execution_state = "run"
    out:write("armed\n"); out:flush()
  end
  local cl = dbg.consolelog
  for i = lastlog + 1, #cl do
    local line = tostring(cl[i])
    if line:find("^WP") then
      n = n + 1
      if n <= 200 then out:write(string.format("t=%8.3f %s\n", t, line)) end
    end
  end
  lastlog = #cl
  if t >= 20 and not _G._k6w_done then
    _G._k6w_done = true
    out:write(string.format("total WP hits: %d\n", n)); out:flush()
  end
end)
