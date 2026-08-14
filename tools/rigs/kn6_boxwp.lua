-- KN6000: who writes the widget-box interior in the UI index plane?
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local dbg  = mach.debugger
local out  = io.open("kn6_boxwp.log", "w")
local armed, lastlog, n = false, 0, 0
_G._k6b = emu.add_machine_frame_notifier(function()
  local mt = mach.time
  local t = mt.seconds + mt.attoseconds / 1e18
  if not armed then
    armed = true
    -- box interior (x=60,y=50) and (x=370,y=76)
    cpu.debug:wpset(cpu.spaces["program"], "w", 0x50208168, 1, "1",
      "printf \"WA pc=%08X sp=%08X s0=%08X s1=%08X s2=%08X s3=%08X s4=%08X s5=%08X\", pc, sp, d@(sp), d@(sp+4), d@(sp+8), d@(sp+0xc), d@(sp+0x10), d@(sp+0x14) ; g")
    dbg.execution_state = "run"
    out:write("armed\n"); out:flush()
  end
  local cl = dbg.consolelog
  for i = lastlog + 1, #cl do
    local line = tostring(cl[i])
    if line:find("^WA") then
      n = n + 1
      if n <= 60 then out:write(string.format("t=%8.3f %s\n", t, line)) end
    end
  end
  lastlog = #cl
  if t >= 14 and not _G._k6b_done then
    _G._k6b_done = true
    out:write(string.format("total: %d\n", n)); out:flush()
    mach:exit()
  end
end)
