-- progress.lua -- snapshot the BOOT SEQUENCE at 8, 12, 16, 20, 24 and 28 s, then exit.
--
-- For "where does it get stuck / when does the UI appear" questions, where a single late
-- snapshot cannot distinguish "never drew" from "drew and then cleared".
--
--   ./tools/rig.sh progress kn6000 -s 32
--
-- Prints SNAP t=<n> per frame captured; exits at t=30.

local M = manager.machine
local shots = {8,12,16,20,24,28}
local i=1
emu.register_periodic(function()
  local now=M.time:as_double()
  while i<=#shots and now>=shots[i] do M.video:snapshot(); emu.print_error("SNAP t="..shots[i]); i=i+1 end
  if now>=30 then M:exit() end
end)
