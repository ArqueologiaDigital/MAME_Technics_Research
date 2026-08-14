local vid = manager.machine.video
local done = {}
emu.register_frame_done(function()
  local t = manager.machine.time.seconds
  for _, tt in ipairs({15, 30, 40}) do
    if t >= tt and not done[tt] then
      done[tt] = true
      vid:snapshot()
    end
  end
end)
