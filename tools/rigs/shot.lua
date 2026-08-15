-- shot.lua -- one snapshot at t=16 s. The smallest possible rig.
--
-- For "just show me what is on screen" runs. Does NOT exit, so the caller's -s sets the length.
--
--   ./tools/rig.sh shot kn7000 -s 18

local mac=manager.machine; local d=false
emu.register_periodic(function() local t=mac.time.seconds+mac.time.attoseconds/1e18
  if not d and t>=16 then mac.video:snapshot(); d=true end end)
