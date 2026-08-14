-- kn6_text_bp.lua -- KN6000 text investigation: execution breakpoints on the 5
-- play-screen draw routines called from the redraw at 0x484064c6/0x48406529,
-- plus the widget-draw dispatcher 0x487f5d88. Logs entry args + return addr.
-- RUN WITH: kn6000 -debug -debugger none
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local dbg  = mach.debugger
local out  = io.open("kn7_fn.log", "w")
local armed = false
local lastlog = 0
local counts = {}
local CAP = 40
local bps = {
  {0x48425467, "TXTFN"},
}
_G._k6t = emu.add_machine_frame_notifier(function()
  local mt = mach.time
  local t = mt.seconds + mt.attoseconds / 1e18
  if not armed then
    armed = true
    for _, b in ipairs(bps) do
      cpu.debug:bpset(b[1], "1",
        string.format("printf \"BP %s a0=%%08X a1=%%08X d0=%%08X d1=%%08X ret=%%08X\", a0, a1, d0, d1, d@(sp) ; g", b[2]))
    end
    dbg.execution_state = "run"
    out:write("armed\n"); out:flush()
  end
  local cl = dbg.consolelog
  for i = lastlog + 1, #cl do
    local line = tostring(cl[i])
    local tag = line:match("^BP (%S+)")
    if tag then
      counts[tag] = (counts[tag] or 0) + 1
      if counts[tag] <= 25 then
        out:write(string.format("t=%8.3f %s\n", t, line))
      end
    end
  end
  lastlog = #cl
  if t >= 30 and not _G._k6t_done then
    _G._k6t_done = true
    local s = "COUNTS:"
    for k, v in pairs(counts) do s = s .. string.format(" %s=%d", k, v) end
    out:write(s .. "\n"); out:flush()
    mach.video:snapshot()
  end
end)
