local M = manager.machine
local tag=os.getenv("BTN_TAG"); local name=os.getenv("BTN_NAME")
local function field(pt,nm) local p=M.ioport.ports[pt]; if not p then return nil end
  for k,f in pairs(p.fields) do if f.name==nm then return f end end return nil end
local pressed=false
emu.register_periodic(function()
  local now=M.time:as_double()
  if now>=20.5 and not pressed then M.video:snapshot(); emu.print_error("SNAP_PRE")  -- home screen before press
    local f=field(tag,name); if f then f:set_value(1); emu.print_error("PRESS") else emu.print_error("NOFIELD") end
    pressed=true end
  if pressed and now>=20.9 then local f=field(tag,name); if f then f:set_value(0) end end
  if now>=23 then M.video:snapshot(); emu.print_error("SNAP_POST"); M:exit() end
end)
