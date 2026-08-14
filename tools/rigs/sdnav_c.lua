-- Run C: DATA dial, PAGE UP/DOWN, EXIT, DISPLAY HOLD on the SD MENU
local mac = manager.machine
local function log(s) emu.print_error(s) end
local scr = nil
for _, s in pairs(mac.screens) do scr = s break end
local function fld(tag, mask)
  local p = mac.ioport.ports[tag]
  if not p then log("NOPORT "..tag); return nil end
  for _, f in pairs(p.fields) do if f.mask == mask then return f end end
  log(("NOFIELD %s %02X"):format(tag, mask)); return nil
end
local probe_x, probe_y = 346, 146
local function is_red(v)
  local r, g, b = (v>>16)&0xff, (v>>8)&0xff, v&0xff
  return r > 140 and g < 110 and b < 110
end
local function on_home() return is_red(scr:pixel(probe_x, probe_y)) end
local acts = {}
local function at(t, desc, fn) acts[#acts+1] = {t=t, desc=desc, fn=fn} end
local function press(t, tag, mask, desc)
  at(t, desc.." DOWN", function() local f=fld(tag,mask) if f then f:set_value(1) end end)
  at(t+0.4, desc.." UP", function() local f=fld(tag,mask) if f then f:clear_value() end end)
end
local shots = 0
local function snap(t, desc)
  at(t, "", function() mac.video:snapshot(); shots = shots + 1
    log(("SNAP#%04d %s"):format(shots-1, desc)) end)
end
local function ensure_menu(t, name)
  at(t, "probe "..name, function()
    local home = on_home()
    log(("PROBE before %s: %s"):format(name, home and "HOME" or "not-home"))
    if home then local f = fld(":cpanel:CPR_SEG1", 0x80); if f then f:set_value(1) end end
  end)
  at(t+0.5, "", function() local f = fld(":cpanel:CPR_SEG1", 0x80); if f then f:clear_value() end end)
end
local function dial(t, v)
  at(t, ("dial=%d"):format(v), function() local f=fld(":DIAL",0xff) if f then f:set_value(v) end end)
end

press(22.5, ":cpanel:CPR_SEG1", 0x80, "SDLOAD-first-entry")
-- Trial 1: DATA dial up 4 steps of +4, then back down
ensure_menu(25.0, "DIAL")
snap(26.8, "PRE-DIAL")
dial(27.2, 4) dial(27.5, 8) dial(27.8, 12) dial(28.1, 16)
snap(29.5, "AFTER-DIAL-UP16")
dial(29.8, 12) dial(30.1, 8) dial(30.4, 4) dial(30.7, 0)
snap(32.0, "AFTER-DIAL-DOWN16")
-- Trial 2: PAGE UP
ensure_menu(32.5, "PAGEUP")
snap(34.3, "PRE-PAGEUP")
press(34.7, ":cpanel:CPC_SEG11", 0x10, "PAGEUP")
snap(36.5, "AFTER-PAGEUP")
press(36.9, ":cpanel:CPR_SEG1", 0x80, "normalize")
-- Trial 3: PAGE DOWN
ensure_menu(39.0, "PAGEDN")
snap(40.8, "PRE-PAGEDN")
press(41.2, ":cpanel:CPC_SEG11", 0x20, "PAGEDN")
snap(43.0, "AFTER-PAGEDN")
press(43.4, ":cpanel:CPR_SEG1", 0x80, "normalize")
-- Trial 4: EXIT
ensure_menu(45.5, "EXIT")
snap(47.3, "PRE-EXIT")
press(47.7, ":cpanel:CPC_SEG11", 0x80, "EXIT")
snap(49.5, "AFTER-EXIT")
press(49.9, ":cpanel:CPR_SEG1", 0x80, "normalize")
-- Trial 5: DISPLAY HOLD
ensure_menu(52.0, "DHOLD")
snap(53.8, "PRE-DHOLD")
press(54.2, ":cpanel:CPC_SEG11", 0x40, "DHOLD")
snap(56.0, "AFTER-DHOLD")

local i = 1
emu.register_periodic(function()
  local t = mac.time.seconds + mac.time.attoseconds/1e18
  while i <= #acts and t >= acts[i].t do
    local a = acts[i]; i = i + 1
    local ok, err = pcall(a.fn)
    if not ok then log("ERR "..a.desc..": "..tostring(err))
    elseif a.desc ~= "" then log(("[%5.1f] %s"):format(t, a.desc)) end
  end
end)
log("sdnav_c armed")
