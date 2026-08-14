local done=false
emu.register_periodic(function()
  local t=manager.machine.time; local s=t.seconds+t.attoseconds/1e18
  if not done and s>26 then done=true; manager.machine.video:snapshot(); print("[kn7] snapshot at "..s); manager.machine:exit() end
end)
