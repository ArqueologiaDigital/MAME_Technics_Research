local M = manager.machine
emu.register_periodic(function()
  if M.time:as_double()>=10.5 then M.video:snapshot(); M:exit() end
end)
