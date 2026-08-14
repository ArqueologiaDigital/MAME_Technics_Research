-- KN7000: who CALLS the text drawer 0x48425467 ?
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local dbg  = mach.debugger
local out  = io.open("kn7_txtcall.log", "w")
local armed, lastlog, rets, n = false, 0, {}, 0
_G._k7c = emu.add_machine_frame_notifier(function()
  local mt = mach.time
  local t = mt.seconds + mt.attoseconds / 1e18
  if not armed then
    armed = true
    for _, a in ipairs({0x48425467, 0x4C425467}) do
      cpu.debug:bpset(a, "1",
        "printf \"BP TD ret=%08X r1=%08X r2=%08X r3=%08X d2=%08X\", d@(sp), d@(sp+4), d@(sp+8), d@(sp+0xc), d2 ; g")
    end
    dbg.execution_state = "run"
  end
  local cl = dbg.consolelog
  for i = lastlog + 1, #cl do
    local line = tostring(cl[i])
    local r = line:match("^BP TD ret=(%x+)")
    if r then
      n = n + 1
      rets[r] = (rets[r] or 0) + 1
      if n <= 15 then out:write(string.format("t=%8.3f %s\n", t, line)) end
    end
  end
  lastlog = #cl
  if t >= 16 and not _G._k7c_done then
    _G._k7c_done = true
    local s = "RETS:"
    for k,v in pairs(rets) do s = s .. string.format(" %s=%d", k, v) end
    out:write(string.format("total=%d\n%s\n", n, s)); out:flush(); mach:exit()
  end
end)
