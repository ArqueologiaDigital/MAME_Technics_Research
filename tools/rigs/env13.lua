-- env13.lua: crisp slow-attack verification -- SOLO the edited tone.
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

press(23.0, ":cpanel:CPR_SEG0", 0x04, "PROGRAM-MENUS")
press(25.0, ":cpanel:CPR_SEG5", 0x10, "SOUND-EDIT")
press(27.0, ":cpanel:CPL_SEG0", 0x20, "AMPLITUDE")
press(29.0, ":cpanel:CPC_SEG11", 0x10, "PAGE-UP")
press(31.0, ":cpanel:CPR_SEG0", 0x01, "SOLO")
key(33.0, 1, "MARK solo-fastatk-on t=33")     -- control: ATK still 0
key(36.0, 0, "MARK solo-fastatk-off t=36")
press(38.0, ":cpanel:CPC_SEG8", 0x01, "ATK up ~52", 4.0)
at(43.0, "snap", function() mac.video:snapshot(); log("SNAP ATK+SOLO") end)
key(43.5, 1, "MARK solo-slowatk-on t=43.5")
key(47.5, 0, "MARK solo-slowatk-off t=47.5")
at(50.0, "exit", function() log("ENV13 DONE"); mac:exit() end)

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
log("env13 armed")
