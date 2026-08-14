-- env14.lua: demo-song regression check (press DEMO, let it play ~25 s)
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
end
press(23.0, ":cpanel:CPL_SEG6", 0x40, "DEMO")
at(26.0, "snap1", function() mac.video:snapshot(); log("SNAP demo screen") end)
press(27.0, ":cpanel:CPL_SEG0", 0x10, "START/STOP")   -- in case it needs a start
at(50.0, "exit", function() log("DEMO CHECK DONE"); mac:exit() end)
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
log("env14 armed")
