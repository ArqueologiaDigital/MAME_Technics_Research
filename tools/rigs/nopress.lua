-- nopress.lua -- the NULL for every button rig: boot, touch nothing, snapshot, exit.
--
-- Pair this with one.lua / late.lua. Without it, "the screen shows X after pressing the button"
-- has no control, and X may be what the machine shows anyway.
--
--   ./tools/rig.sh nopress kn7000 -s 12
--
-- Snapshots at t=10.5 s and exits.

local M = manager.machine
emu.register_periodic(function()
  if M.time:as_double()>=10.5 then M.video:snapshot(); M:exit() end
end)
