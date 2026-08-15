-- one.lua -- press one named button EARLY (t=8 s), snapshot, exit.
--
-- The early half of the pair with late.lua (t=20.5, settled). Selected by BTN_TAG/BTN_NAME so
-- one rig sweeps any binding. Compare against nopress.lua, or a press that changes nothing is
-- indistinguishable from a press that never registered.
--
--   BTN_TAG=":cpanel:CPR_SEG4" BTN_NAME="PIANO (SW4)" ./tools/rig.sh one kn7000 -s 12
--
-- Prints PRESS <tag>/<name> or ⚠ NOFIELD <tag>/<name>; snapshots and exits at t=10.5.

local M = manager.machine
local tag = os.getenv("BTN_TAG")
local name = os.getenv("BTN_NAME")
local function field(porttag, nm)
  local p = M.ioport.ports[porttag]; if not p then return nil end
  for k,f in pairs(p.fields) do if f.name==nm then return f end end
  return nil
end
local fired=false
emu.register_periodic(function()
  local now=M.time:as_double()
  if not fired and now>=8.0 then
    local f=field(tag,name)
    if f then f:set_value(1); emu.print_error("PRESS "..tag.."/"..name) else emu.print_error("NOFIELD "..tag.."/"..name) end
    fired=true
  end
  if fired and now>=8.4 then local f=field(tag,name); if f then f:set_value(0) end end
  if now>=10.5 then M.video:snapshot(); emu.print_error("SNAP"); M:exit() end
end)
