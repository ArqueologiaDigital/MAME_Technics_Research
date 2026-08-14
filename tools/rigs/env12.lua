-- env12.lua: A/B envelope verification capture (run with -wavwrite).
-- 1) piano C4 held 5 s (decay shape) + release
-- 2) TAB ORGAN C4 held 3 s (sustain) + release (stop speed)
-- 3) back to PIANO, SOUND EDIT -> AMPLITUDE -> ENVELOPE, ATK -> ~52, C4 held 3 s (slow swell)
local mac = manager.machine
local function log(s) emu.print_error(s) end

local acts = {}
local function at(t, desc, fn) acts[#acts+1] = {t=t, desc=desc, fn=fn} end
local function press(t, tag, mask, desc, hold)
  hold = hold or 0.35
  at(t, desc, function()
    local p = mac.ioport.ports[tag]
    for _, f in pairs(p.fields) do if f.mask == mask then f:set_value(1) end end
  end)
  at(t+hold, "", function()
    local p = mac.ioport.ports[tag]
    for _, f in pairs(p.fields) do if f.mask == mask then f:clear_value() end end
  end)
  return t + hold + 0.3
end
local function key(t, v, label)
  at(t, label, function()
    local p = mac.ioport.ports[":KEYS1"]
    for _, f in pairs(p.fields) do
      if f.mask == 0x0100 then if v==1 then f:set_value(1) else f:clear_value() end end
    end
  end)
end

-- 1) piano (default) C4
key(22.0, 1, "MARK piano-on t=22")
key(27.0, 0, "MARK piano-off t=27")
-- 2) organ
press(30.0, ":cpanel:CPR_SEG3", 0x20, "TAB-ORGAN")
key(33.0, 1, "MARK organ-on t=33")
key(36.0, 0, "MARK organ-off t=36")
-- 3) piano again, edit ATK to ~52
press(39.0, ":cpanel:CPR_SEG4", 0x10, "PIANO")
press(41.5, ":cpanel:CPR_SEG0", 0x04, "PROGRAM-MENUS")
press(43.5, ":cpanel:CPR_SEG5", 0x10, "SOUND-EDIT")
press(45.5, ":cpanel:CPL_SEG0", 0x20, "AMPLITUDE")
press(47.5, ":cpanel:CPC_SEG11", 0x10, "PAGE-UP")
press(49.5, ":cpanel:CPC_SEG8", 0x01, "ATK up ~52", 4.0)
at(54.5, "snap", function() mac.video:snapshot(); log("SNAP ATK-edited") end)
key(55.0, 1, "MARK slowatk-on t=55")
key(59.0, 0, "MARK slowatk-off t=59")
at(62.0, "exit", function() log("AB DONE"); mac:exit() end)

local i = 1
emu.register_periodic(function()
  local now = mac.time.seconds + mac.time.attoseconds/1e18
  while i <= #acts and now >= acts[i].t do
    local a = acts[i]; i = i + 1
    local ok, err = pcall(a.fn)
    if not ok then log("ERR "..tostring(a.desc)..": "..tostring(err))
    elseif a.desc ~= "" then log(("[%6.1f] %s"):format(now, a.desc)) end
  end
end)
log("env12 armed")
