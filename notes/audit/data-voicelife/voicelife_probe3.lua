-- voicelife_probe3.lua -- one held C4, audio only (for envelope-at-release analysis).
local mac = manager.machine
local T_PRESS, T_REL, T_END = 12.0, 14.0, 16.0
local st = 0
local function now() local t = mac.time; return t.seconds + t.attoseconds/1e18 end
emu.register_periodic(function()
  local t = now()
  if st == 0 and t >= T_PRESS then
    st = 1
    local p = mac.ioport.ports[":KEY2"]
    for _, f in pairs(p.fields) do if f.mask == 0x001 then f:set_value(1) end end
    emu.print_error(string.format("PRESS %.6f", t))
  elseif st == 1 and t >= T_REL then
    st = 2
    local p = mac.ioport.ports[":KEY2"]
    for _, f in pairs(p.fields) do if f.mask == 0x001 then f:clear_value() end end
    emu.print_error(string.format("RELEASE %.6f", t))
  elseif st == 2 and t >= T_END then
    st = 3
    emu.print_error("PROBE3 DONE")
    mac:exit()
  end
end)
emu.print_error("voicelife_probe3 armed")
