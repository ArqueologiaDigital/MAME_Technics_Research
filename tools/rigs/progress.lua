local M = manager.machine
local shots = {8,12,16,20,24,28}
local i=1
emu.register_periodic(function()
  local now=M.time:as_double()
  while i<=#shots and now>=shots[i] do M.video:snapshot(); emu.print_error("SNAP t="..shots[i]); i=i+1 end
  if now>=30 then M:exit() end
end)
