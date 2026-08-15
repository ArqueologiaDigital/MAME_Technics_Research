-- money.lua -- THE AUDIO ORACLE. Holds one keybed note so a capture can be hashed.
-- rig-machine: kn7000
--
-- Presses `:KEYS1` mask 0x0100 at t=16 s and releases it at t=17 s. Nothing else. The value is
-- that the resulting WAV is bit-deterministic, so its md5 is gate.sh's regression signal for
-- the whole KN7000 audio path.
--
-- Baseline, recipe and the fault-injection evidence are pinned in this directory's README --
-- read that before re-baselining, because TWO earlier baselines went stale unnoticed and
-- disagreed with each other, which is exactly what an unrun gate looks like.
--
--   ./tools/rig.sh money kn7000 -s 22 -w /tmp/o.wav   # then md5sum /tmp/o.wav
--
-- ⚠ It deliberately does NOT snapshot or exit -- the run length is the caller's -s. And it is a
--   REGRESSION hash: it says nothing changed, never that anything is correct.

_G.m=_G.m or {}; _G.m.st=0
local function press(p,mm,v) local pp=manager.machine.ioport.ports[p]; if not pp then return end; for _,f in pairs(pp.fields) do if f.mask==mm then f:set_value(v) end end end
_G.m.h=emu.add_machine_frame_notifier(function()
  local mt=manager.machine.time; local t=mt.seconds+mt.attoseconds/1e18; local st=_G.m.st
  if st==0 and t>16 then press(":KEYS1",0x0100,1); _G.m.st=1
  elseif st==1 and t>17 then press(":KEYS1",0x0100,0); _G.m.st=2 end
end)
