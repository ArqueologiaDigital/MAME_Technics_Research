-- kn6_gate.lua -- which stage of the KN6000 text path runs, and what is the gate word?
-- rig-machine: kn6000
--
-- Arms four routines, each at both its program-ROM and its 0x4C library-alias address (it was
-- not known which mapping executes, so both are armed and whichever fires identifies it):
--   WRAP 0x484180DB · TXT 0x48418112 · SETCTX1 0x48414552 · SETCTX2 0x48415131
-- Every hit also prints the gate word at 0x50010384, and the final value is written at the end.
--
-- The output is a per-stage hit COUNT, so the pipeline can be read off directly: the first
-- stage with zero hits is where text drawing stops.
--
--   ./tools/rig.sh kn6_gate kn6000 -s 16 -- -debug -debugger none
--
-- Needs the debugger. Writes kn6_gate.log in the emulator directory; exits at t=14.

local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local mem  = cpu.spaces["program"]
local dbg  = mach.debugger
local out  = io.open("kn6_gate.log", "w")
local armed, lastlog, counts = false, 0, {}
local bps = {
  {0x484180DB, "WRAP"}, {0x4C0180DB, "aWRAP"},
  {0x48418112, "TXT"},  {0x4C018112, "aTXT"},
  {0x48414552, "SETCTX1"}, {0x4C014552, "aSETCTX1"},
  {0x48415131, "SETCTX2"}, {0x4C015131, "aSETCTX2"},
}
_G._k6g = emu.add_machine_frame_notifier(function()
  local mt = mach.time
  local t = mt.seconds + mt.attoseconds / 1e18
  if not armed then
    armed = true
    for _, b in ipairs(bps) do
      cpu.debug:bpset(b[1], "1", string.format(
        "printf \"BP %s d0=%%08X d1=%%08X d2=%%08X a0=%%08X gate=%%08X\", d0,d1,d2,a0,d@(0x50010384) ; g", b[2]))
    end
    dbg.execution_state = "run"
  end
  local cl = dbg.consolelog
  for i = lastlog + 1, #cl do
    local line = tostring(cl[i])
    local tag = line:match("^BP (%S+)")
    if tag then
      counts[tag] = (counts[tag] or 0) + 1
      if counts[tag] <= 6 then out:write(string.format("t=%8.3f %s\n", t, line)) end
    end
  end
  lastlog = #cl
  if t >= 14 and not _G._k6g_done then
    _G._k6g_done = true
    local s = "COUNTS:"
    for k, v in pairs(counts) do s = s .. string.format(" %s=%d", k, v) end
    out:write(s .. string.format("\nfinal gate *(0x50010384) = %08X\n", mem:read_u32(0x50010384)))
    out:flush(); mach:exit()
  end
end)
