-- kn6_blit.lua -- KN6000 missing-text investigation: WHO reads and writes the graphics plane?
-- rig-machine: kn6000
--
-- One of four siblings that share the kn6_text_bp.lua breakpoint harness, each arming a
-- different routine. This one takes the two blitter primitives:
--     0x484184e4 GRD  (graphics read)      0x484184fb GWR  (graphics write)
-- Logs entry args + return address, so the CALLERS of the blit primitives can be named.
--
-- Each breakpoint is also armed at its bus ALIASES (0x4c01…, and 0x8c01… in the siblings).
-- The same routine is reachable through more than one mapping and it was not known which one
-- actually executes, so all are armed and whichever fires identifies the live mapping.
--
--   ./tools/rig.sh kn6_blit kn6000 -s 40 -- -debug -debugger none
--
-- Needs the debugger: it uses mach.debugger breakpoints, not memory taps. Writes kn6_blit.log
-- in the emulator directory (NOT the repo -- that directory is overwritten on every publish,
-- so copy anything you want to keep).
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local dbg  = mach.debugger
local out  = io.open("kn6_blit.log", "w")
local armed = false
local lastlog = 0
local counts = {}
local CAP = 40
local bps = {
  {0x484184e4, "GRD"},
  {0x4c0184e4, "aGRD"},
  {0x484184fb, "GWR"},
  {0x4c0184fb, "aGWR"},
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
