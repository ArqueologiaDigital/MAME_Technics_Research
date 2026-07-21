
-- BOOT-WINDOW PROPERTY probe: press only DURING boot, then look at the settled machine.
-- Same press set as b1/ph000's boot window (6 sound-group presses, t=14.0 .. 17.5), no late
-- burst at all, so whatever is on screen after boot is due to the boot presses alone.
local mac = manager.machine
local function log(s) emu.print_error(s) end
local acts = {}
local function at(t, desc, fn) acts[#acts+1] = {t=t, desc=desc, fn=fn} end
local function press(t, tag, mask, desc, hold)
  hold = hold or 0.25
  at(t, desc, function()
    local p = mac.ioport.ports[tag]
    if not p then log("NO PORT "..tag) return end
    for _, f in pairs(p.fields) do if f.mask == mask then f:set_value(1) end end
  end)
  at(t + hold, "", function()
    local p = mac.ioport.ports[tag]
    if not p then return end
    for _, f in pairs(p.fields) do if f.mask == mask then f:clear_value() end end
  end)
end
local shots = 0
local function snap(t, label)
  at(t, "", function()
    mac.video:snapshot(); shots = shots + 1
    log(("SNAP#%04d %s t=%.3f"):format(shots-1, label, mac.time.seconds + mac.time.attoseconds/1e18))
  end)
end
press(14.000, ":cpanel:CPR_SEG2", 0x01, "BW0 PIANO", 0.250)
press(14.700, ":cpanel:CPR_SEG2", 0x02, "BW1 GUITAR", 0.250)
press(15.400, ":cpanel:CPR_SEG2", 0x04, "BW2 STRINGS", 0.250)
press(16.100, ":cpanel:CPR_SEG2", 0x08, "BW3 BRASS", 0.250)
press(16.800, ":cpanel:CPR_SEG2", 0x10, "BW4 FLUTE", 0.250)
press(17.500, ":cpanel:CPR_SEG1", 0x02, "BW5 ORCHPAD", 0.250)
snap(22.000, "settled1")
snap(26.000, "settled2")
press(28.000, ":cpanel:CPR_SEG10", 0x20, "LIVE MENU:DISK")
snap(30.000, "disk")
press(31.000, ":cpanel:CPR_SEG2", 0x01, "LIVE PIANO")
snap(33.000, "piano")
press(34.000, ":cpanel:CPR_SEG1", 0x02, "LIVE ORCHPAD")
snap(36.000, "orch")
at(37.000, "done", function() log("RUN DONE"); mac:exit() end)

local i = 1
emu.register_periodic(function()
  local nw = mac.time.seconds + mac.time.attoseconds/1e18
  while i <= #acts and nw >= acts[i].t do
    local a = acts[i]; i = i + 1
    local ok, err = pcall(a.fn)
    if not ok then log(("ERR t=%.3f %s: %s"):format(nw, tostring(a.desc), tostring(err)))
    elseif a.desc ~= "" then log(("[%8.3f] %s"):format(nw, a.desc)) end
  end
end)
log("harness armed")
