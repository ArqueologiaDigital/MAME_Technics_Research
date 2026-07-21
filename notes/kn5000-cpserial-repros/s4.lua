
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
press(34.000, ":cpanel:CPR_SEG2", 0x01, "L0 PIANO", 0.250)
press(34.500, ":cpanel:CPR_SEG2", 0x02, "L1 GUITAR", 0.250)
press(35.000, ":cpanel:CPR_SEG2", 0x04, "L2 STRINGS", 0.250)
press(35.500, ":cpanel:CPR_SEG2", 0x08, "L3 BRASS", 0.250)
press(36.000, ":cpanel:CPR_SEG2", 0x10, "L4 FLUTE", 0.250)
press(36.500, ":cpanel:CPR_SEG2", 0x20, "L5 SAX", 0.250)
press(37.000, ":cpanel:CPR_SEG1", 0x01, "L6 ORGAN", 0.250)
press(37.500, ":cpanel:CPR_SEG1", 0x02, "L7 ORCHPAD", 0.250)
press(38.000, ":cpanel:CPR_SEG1", 0x04, "L8 SYNTH", 0.250)
press(38.500, ":cpanel:CPR_SEG1", 0x08, "L9 BASS", 0.250)
press(39.000, ":cpanel:CPR_SEG1", 0x80, "L10 DRUMKITS", 0.250)
press(39.500, ":cpanel:CPR_SEG2", 0x01, "L11 PIANO", 0.250)
press(40.000, ":cpanel:CPR_SEG2", 0x02, "L12 GUITAR", 0.250)
press(40.500, ":cpanel:CPR_SEG2", 0x04, "L13 STRINGS", 0.250)
press(41.000, ":cpanel:CPR_SEG2", 0x08, "L14 BRASS", 0.250)
press(41.500, ":cpanel:CPR_SEG2", 0x10, "L15 FLUTE", 0.250)
press(42.000, ":cpanel:CPR_SEG2", 0x20, "L16 SAX", 0.250)
press(42.500, ":cpanel:CPR_SEG1", 0x01, "L17 ORGAN", 0.250)
press(43.000, ":cpanel:CPR_SEG1", 0x02, "L18 ORCHPAD", 0.250)
press(43.500, ":cpanel:CPR_SEG1", 0x04, "L19 SYNTH", 0.250)
press(44.000, ":cpanel:CPR_SEG1", 0x08, "L20 BASS", 0.250)
press(44.500, ":cpanel:CPR_SEG1", 0x80, "L21 DRUMKITS", 0.250)
press(45.000, ":cpanel:CPR_SEG2", 0x01, "L22 PIANO", 0.250)
press(45.500, ":cpanel:CPR_SEG2", 0x02, "L23 GUITAR", 0.250)
press(46.000, ":cpanel:CPR_SEG2", 0x04, "L24 STRINGS", 0.250)
press(46.500, ":cpanel:CPR_SEG2", 0x08, "L25 BRASS", 0.250)
press(47.000, ":cpanel:CPR_SEG2", 0x10, "L26 FLUTE", 0.250)
press(47.500, ":cpanel:CPR_SEG2", 0x20, "L27 SAX", 0.250)
press(48.000, ":cpanel:CPR_SEG1", 0x01, "L28 ORGAN", 0.250)
press(48.500, ":cpanel:CPR_SEG1", 0x02, "L29 ORCHPAD", 0.250)
press(49.000, ":cpanel:CPR_SEG1", 0x04, "L30 SYNTH", 0.250)
press(49.500, ":cpanel:CPR_SEG1", 0x08, "L31 BASS", 0.250)
press(50.000, ":cpanel:CPR_SEG1", 0x80, "L32 DRUMKITS", 0.250)
snap(51.500, "pre")
snap(52.500, "pre2")
press(53.500, ":cpanel:CPR_SEG10", 0x20, "LIVE MENU:DISK")
snap(55.500, "disk")
press(56.500, ":cpanel:CPR_SEG10", 0x04, "LIVE MENU:SOUND")
snap(58.500, "sound")
press(59.500, ":cpanel:CPR_SEG2", 0x01, "LIVE PIANO")
snap(61.500, "piano")
press(62.500, ":cpanel:CPR_SEG1", 0x02, "LIVE ORCHPAD")
snap(64.500, "orch")
at(65.500, "done", function() log("RUN DONE"); mac:exit() end)

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
