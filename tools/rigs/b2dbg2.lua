-- b2dbg2.lua -- breakpoint sweep over the effect-send setters in the RAM library.
--
-- Sibling of the b2* family (effect-bus unit feeds and per-part send setters). Arms seven
-- breakpoints across 0x4C037D0F..0x4C037D8C -- addresses in the 0x4C library window -- and
-- prints d0/d1 at each hit, to see which of the candidate entry points actually runs and with
-- what arguments.
--
--   ./tools/rig.sh b2dbg2 kn7000 -s 30 -- -debug -debugger none
--
-- Needs the debugger. Output goes to stderr, tagged [b2d].

local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local dbg  = mach.debugger
local armed = false
local lastlog = 0
_G._b2d = emu.add_machine_frame_notifier(function()
  local mt = mach.time
  local t = mt.seconds + mt.attoseconds / 1e18
  if not armed then
    armed = true
    for _, a in ipairs({0x4C037D0F, 0x4C037D11, 0x4C037D14, 0x4C037D33, 0x4C037D87, 0x4C037D89, 0x4C037D8C}) do
      cpu.debug:bpset(a, "1", string.format("printf \"HIT %08X d0=%%X d1=%%X\", 0x%X, d0, d1 ; g", a, a))
    end
    dbg.execution_state = "run"
    emu.print_error("[b2d] armed")
  end
  local cl = dbg.consolelog
  for i = lastlog + 1, #cl do
    local line = tostring(cl[i])
    if line:find("HIT") then emu.print_error(string.format("[b2d] t=%.3f %s", t, line)) end
  end
  lastlog = #cl
end)
