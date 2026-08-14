local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local dbg  = mach.debugger
local out  = io.open("kn6_fdesc.log", "w")
local armed, lastlog, counts = false, 0, {}
local bps = {
  {0x4C0181D3, "K6_FONTBASE"},   -- after: d1 = *(0x5024F664), d2 = font id
  {0x4C0181DC, "K6_GLYPHPTR"},   -- a2 = fontrec ; (8,a2) = glyph base
}
_G._k6f = emu.add_machine_frame_notifier(function()
  local mt = mach.time
  local t = mt.seconds + mt.attoseconds / 1e18
  if not armed then
    armed = true
    for _, b in ipairs(bps) do
      cpu.debug:bpset(b[1], "1", string.format(
        "printf \"BP %s d1=%%08X d2=%%08X a2=%%08X\", d1, d2, a2 ; g", b[2]))
    end
    dbg.execution_state = "run"
  end
  local cl = dbg.consolelog
  for i = lastlog + 1, #cl do
    local line = tostring(cl[i])
    local tag = line:match("^BP (%S+)")
    if tag then
      counts[tag] = (counts[tag] or 0) + 1
      if counts[tag] <= 5 then out:write(string.format("t=%8.3f %s\n", t, line)) end
    end
  end
  lastlog = #cl
  if t >= 14 and not _G._k6f_done then
    _G._k6f_done = true
    local s = "COUNTS:"
    for k, v in pairs(counts) do s = s .. string.format(" %s=%d", k, v) end
    out:write(s .. "\n"); out:flush(); mach:exit()
  end
end)
