-- Panel responsiveness: settled boot, slow unambiguous presses, snapshot each.
local mac = manager.machine
local function T() return mac.time.seconds + mac.time.attoseconds/1e18 end
local function btn(tag, mask, v)
  local p = mac.ioport.ports[":"..tag] or mac.ioport.ports[":cpanel:"..tag]
  if not p then emu.print_info("### NO PORT "..tag) return end
  for _, f in pairs(p.fields) do if f.mask == mask then f:set_value(v) end end
end
local seq = {
  {22.0, "CPL_SEG4", 0x40, "AUTO PLAY CHORD"},
  {26.0, "CPL_SEG7", 0x08, "EXIT"},
  {30.0, "CPR_SEG0", 0x01, "R-panel btn0"},
  {34.0, "CPL_SEG3", 0x01, "DEMO"},
  {38.0, "CPL_SEG7", 0x08, "EXIT"},
}
local i, held = 1, nil
_G._t = emu.register_frame_done(function() pcall(function()
  local t = T()
  if held and t >= held[1] then btn(held[2], held[3], 0); held = nil
    mac.video:snapshot(); emu.print_info(string.format("### t=%.1f released", t)) end
  if i <= #seq and t >= seq[i][1] then
    local e = seq[i]; btn(e[2], e[3], 1)
    emu.print_info(string.format("### t=%.1f PRESS %s", t, e[4]))
    held = {t + 0.25, e[2], e[3]}; i = i + 1
  end
end) end)
