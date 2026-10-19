-- snaps.lua -- save a snapshot at each emulated time in $SNAP_TIMES (seconds, space-separated,
-- ascending), then quit. Used by ab_boot.sh to compare two binaries frame for frame.
local mac = manager.machine
local T = {}
for x in (os.getenv("SNAP_TIMES") or "45"):gmatch("%S+") do T[#T + 1] = tonumber(x) end
local i = 1
_G.SNAPS = emu.add_machine_frame_notifier(function()
  local t = mac.time.seconds + mac.time.attoseconds / 1e18
  if i <= #T and t >= T[i] then
    mac.video:snapshot()
    emu.print_error(string.format("SNAP %d at %.3f", i, t))
    i = i + 1
    if i > #T then mac:exit() end
  end
end)
