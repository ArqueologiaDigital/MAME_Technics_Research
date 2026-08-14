-- KN7000: who READS the font descriptor table at 0x50122DB8 ? -> the glyph fetch / text drawer
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local dbg  = mach.debugger
local out  = io.open("kn7_fontrd.log", "w")
local armed, lastlog, n = false, 0, 0
local pcs = {}
_G._k7f = emu.add_machine_frame_notifier(function()
  local mt = mach.time
  local t = mt.seconds + mt.attoseconds / 1e18
  if not armed then
    armed = true
    cpu.debug:wpset(cpu.spaces["program"], "r", 0x50122DB8, 0x40, "1",
      "printf \"RD pc=%08X d0=%08X d1=%08X a0=%08X a1=%08X ret=%08X\", pc, d0, d1, a0, a1, d@(sp) ; g")
    dbg.execution_state = "run"
    out:write("armed\n"); out:flush()
  end
  local cl = dbg.consolelog
  for i = lastlog + 1, #cl do
    local line = tostring(cl[i])
    local pc = line:match("^RD pc=(%x+)")
    if pc then
      n = n + 1
      pcs[pc] = (pcs[pc] or 0) + 1
      if n <= 40 then out:write(string.format("t=%8.3f %s\n", t, line)) end
    end
  end
  lastlog = #cl
  if t >= 20 and not _G._k7f_done then
    _G._k7f_done = true
    local s = "PCS:"
    for k,v in pairs(pcs) do s = s .. string.format(" %s=%d", k, v) end
    out:write(string.format("total: %d\n%s\n", n, s)); out:flush()
    mach:exit()
  end
end)
