-- kn7snap.lua -- snapshot the settled KN7000 home screen, then exit.
-- rig-machine: kn7000
--
-- Waits to t=26 s, which is past this driver's boot, so the capture is the home screen rather
-- than a splash frame. shot.lua fires earlier and does not exit.
--
--   ./tools/rig.sh kn7snap kn7000 -s 30

local done=false
emu.register_periodic(function()
  local t=manager.machine.time; local s=t.seconds+t.attoseconds/1e18
  if not done and s>26 then done=true; manager.machine.video:snapshot(); print("[kn7] snapshot at "..s); manager.machine:exit() end
end)
