-- Programmatic button-press test for the KN5000 panel.
-- Presses named ioport fields on the cpanel device and snapshots the LCD.
local M = manager.machine
local ports = M.ioport.ports

local function findfield(porttag, name)
  local p = ports[porttag]
  if not p then emu.print_error("NO PORT "..porttag); return nil end
  for k,f in pairs(p.fields) do
    if f.name == name then return f end
  end
  emu.print_error("NO FIELD "..name.." in "..porttag)
  return nil
end

local function press(porttag, name)
  local f = findfield(porttag, name)
  if f then f:set_value(1) end
end
local function release(porttag, name)
  local f = findfield(porttag, name)
  if f then f:set_value(0) end
end

local seq = {
  {t=8.0,  fn=function() M.video:snapshot(); emu.print_error("SNAP boot") end},
  {t=8.5,  fn=function() press(":cpanel:CPR_SEG2","PIANO"); emu.print_error("PRESS PIANO") end},
  {t=8.9,  fn=function() release(":cpanel:CPR_SEG2","PIANO") end},
  {t=9.6,  fn=function() M.video:snapshot(); emu.print_error("SNAP after PIANO") end},
  {t=10.2, fn=function() press(":cpanel:CPL_SEG0","POP & BALLAD"); emu.print_error("PRESS POP") end},
  {t=10.6, fn=function() release(":cpanel:CPL_SEG0","POP & BALLAD") end},
  {t=11.3, fn=function() M.video:snapshot(); emu.print_error("SNAP after POP") end},
  {t=11.9, fn=function() press(":cpanel:CPR_SEG10","MENU: DISK"); emu.print_error("PRESS DISK") end},
  {t=12.3, fn=function() release(":cpanel:CPR_SEG10","MENU: DISK") end},
  {t=13.0, fn=function() M.video:snapshot(); emu.print_error("SNAP after DISK") end},
  {t=13.6, fn=function() press(":cpanel:CPR_SEG10","MENU: SOUND"); emu.print_error("PRESS PROGRAM MENU (SOUND)") end},
  {t=14.0, fn=function() release(":cpanel:CPR_SEG10","MENU: SOUND") end},
  {t=14.7, fn=function() M.video:snapshot(); emu.print_error("SNAP after SOUND MENU") end},
  {t=15.3, fn=function() press(":cpanel:CPR_SEG4","LEFT"); emu.print_error("PRESS PART SELECT LEFT") end},
  {t=15.7, fn=function() release(":cpanel:CPR_SEG4","LEFT") end},
  {t=16.4, fn=function() M.video:snapshot(); emu.print_error("SNAP after PART LEFT") end},
  {t=17.0, fn=function() emu.print_error("DONE"); M:exit() end},
}

local idx = 1
local function tick()
  local now = M.time:as_double()
  while idx <= #seq and now >= seq[idx].t do
    seq[idx].fn()
    idx = idx + 1
  end
end
emu.register_periodic(tick)
emu.print_error("btntest.lua loaded")
