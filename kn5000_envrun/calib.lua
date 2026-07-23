-- calib.lua -- find when the KN5000 home screen appears; snapshot every 2s.
local RUNDIR = "/home/fsanches/compartilhado/kn7000_mame/kn5000_envrun"
local logf = io.open(RUNDIR.."/calib.log", "w")
local function LOG(s) emu.print_info(s); if logf then logf:write(s.."\n"); logf:flush() end end
local mach = manager.machine
local last = 0
_G._calib = emu.add_machine_frame_notifier(function()
  local ok,err = pcall(function()
    local t = mach.time.seconds + mach.time.attoseconds/1e18
    if t - last >= 2.0 then
      last = t
      mach.video:snapshot()
      LOG(("snap @ %.2f"):format(t))
    end
  end)
  if not ok then LOG("ERR "..tostring(err)) end
end)
LOG("calib armed")
