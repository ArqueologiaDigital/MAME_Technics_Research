-- Which candidate RAM windows does the firmware NEVER write during a full boot?
-- Evidence before claiming an address, not after.  Write taps, bus-width aligned.
local mach = manager.machine
local prog = mach.devices[":cpu1"].spaces["program"]
local CAND = {
  { "lowram top   0x007F00", 0x007F00, 0x007FFF },
  { "600k top     0x67FF00", 0x67FF00, 0x67FFFF },
  { "600k 0x67F000", 0x67F000, 0x67F0FF },
  { "600k 0x660000", 0x660000, 0x6600FF },
  { "600k 0x640000", 0x640000, 0x6400FF },
}
local hits, taps = {}, {}
for i, c in ipairs(CAND) do
  hits[i] = 0
  taps[#taps+1] = prog:install_write_tap(c[2], c[3], c[1], function(o, d, m)
    hits[i] = hits[i] + 1
    return d
  end)
end
_G._t = taps
local done = false
_G._f = emu.register_frame_done(function()
  local t = mach.time.seconds + mach.time.attoseconds/1e18
  if t >= 12.0 and not done then
    done = true
    emu.print_error("### RAM WRITE CENSUS over a 12 s boot:")
    for i, c in ipairs(CAND) do
      emu.print_error(string.format("###   %-24s 0x%06X..0x%06X  writes %d %s",
          c[1], c[2], c[3], hits[i], hits[i] == 0 and "  <- UNTOUCHED" or ""))
    end
    mach:exit()
  end
end)
