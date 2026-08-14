-- Run B1: the 5 RIGHT soft keys, each from a verified SD MENU state
TRIALS = {
  {tag=":cpanel:CPR_SEG5", mask=0x10, name="LCDR1-LOAD"},
  {tag=":cpanel:CPR_SEG5", mask=0x20, name="LCDR2-SAVE"},
  {tag=":cpanel:CPR_SEG7", mask=0x01, name="LCDR3-MEDLEY"},
  {tag=":cpanel:CPR_SEG6", mask=0x01, name="LCDR4-SDAUDIO"},
  {tag=":cpanel:CPR_SEG5", mask=0x01, name="LCDR5-SDSOUND"},
}
-- Shared SD-MENU trial runner. Define TRIALS (list of {tag,mask,name}) then dofile this.
-- Protocol per trial: probe screen (red RHYTHM badge = home) -> if home press SD CARD LOAD
-- to enter the SD MENU; snap PRE; press stimulus; snap AFTER; press SD CARD LOAD once to
-- normalize (menu/sub-screen -> home). Pixel probe self-calibrates on the home screen.
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
local probe_x, probe_y = nil, nil
local function is_red(v)
  local r, g, b = (v>>16)&0xff, (v>>8)&0xff, v&0xff
  return r > 140 and g < 110 and b < 110
end
local function calibrate()
  local w, h = scr.width, scr.height
  local n, fx, fy = 0, nil, nil
  for y = 0, h-1, 2 do
    for x = 0, w-1, 2 do
      if is_red(scr:pixel(x, y)) then
        n = n + 1
        if not fx then fx, fy = x, y end
      end
    end
  end
  if fx then probe_x, probe_y = fx + 2, fy + 2
    log(("CALIB: %d red px, probe=(%d,%d) screen %dx%d"):format(n, probe_x, probe_y, w, h))
  else log("CALIB FAILED: no red pixels on home screen; fallback probe (65,50)")
    probe_x, probe_y = 65, 50 end
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

at(21.5, "calibrate", calibrate)
press(22.5, ":cpanel:CPR_SEG1", 0x80, "SDLOAD-first-entry")

local t0 = 25.0
for k, tr in ipairs(TRIALS) do
  local base = t0 + (k-1)*6.0
  at(base, "probe "..tr.name, function()
    local home = on_home()
    log(("PROBE before %s: %s"):format(tr.name, home and "HOME" or "not-home"))
    if home then
      local f = fld(":cpanel:CPR_SEG1", 0x80); if f then f:set_value(1) end
    end
  end)
  at(base+0.5, "", function()  -- unconditional release (harmless if not pressed)
    local f = fld(":cpanel:CPR_SEG1", 0x80); if f then f:clear_value() end
  end)
  snap (base+1.8, "PRE-"..tr.name)
  press(base+2.2, tr.tag, tr.mask, tr.name)
  snap (base+4.0, "AFTER-"..tr.name)
  press(base+4.4, ":cpanel:CPR_SEG1", 0x80, "normalize")
end

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
log(("sdnav_lib armed, %d trials, ends ~%.0f"):format(#TRIALS, t0 + #TRIALS*6.0))
