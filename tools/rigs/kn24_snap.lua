-- kn24_snap.lua -- snapshot the KN2400 at 15, 30 and 40 s.
-- rig-machine: kn2400
--
-- Three shots because this model's screen is the thing under investigation (it draws icons but
-- renders text as solid bars -- notes/FINDINGS-kn2400-table-rom.md) and it settles late.
--
--   ./tools/rig.sh kn24_snap kn2400 -s 42
--
-- Does not exit; the caller's -s ends the run.

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
