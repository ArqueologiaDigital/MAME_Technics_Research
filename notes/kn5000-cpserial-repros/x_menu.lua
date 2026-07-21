
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
press(24.000, ":cpanel:CPR_SEG10", 0x20, "MN0 MENU:DISK", 0.150)
press(24.450, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(24.900, ":cpanel:CPR_SEG10", 0x04, "MN1 MENU:SOUND", 0.150)
press(25.350, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(25.800, ":cpanel:CPR_SEG10", 0x08, "MN2 MENU:CONTROL", 0.150)
press(26.250, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(26.700, ":cpanel:CPR_SEG10", 0x10, "MN3 MENU:MIDI", 0.150)
press(27.150, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(27.600, ":cpanel:CPR_SEG10", 0x20, "MN4 MENU:DISK", 0.150)
press(28.050, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(28.500, ":cpanel:CPR_SEG10", 0x04, "MN5 MENU:SOUND", 0.150)
press(28.950, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(29.400, ":cpanel:CPR_SEG10", 0x08, "MN6 MENU:CONTROL", 0.150)
press(29.850, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(30.300, ":cpanel:CPR_SEG10", 0x10, "MN7 MENU:MIDI", 0.150)
press(30.750, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(31.200, ":cpanel:CPR_SEG10", 0x20, "MN8 MENU:DISK", 0.150)
press(31.650, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(32.100, ":cpanel:CPR_SEG10", 0x04, "MN9 MENU:SOUND", 0.150)
press(32.550, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(33.000, ":cpanel:CPR_SEG10", 0x08, "MN10 MENU:CONTROL", 0.150)
press(33.450, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(33.900, ":cpanel:CPR_SEG10", 0x10, "MN11 MENU:MIDI", 0.150)
press(34.350, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(34.800, ":cpanel:CPR_SEG10", 0x20, "MN12 MENU:DISK", 0.150)
press(35.250, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(35.700, ":cpanel:CPR_SEG10", 0x04, "MN13 MENU:SOUND", 0.150)
press(36.150, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(36.600, ":cpanel:CPR_SEG10", 0x08, "MN14 MENU:CONTROL", 0.150)
press(37.050, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(37.500, ":cpanel:CPR_SEG10", 0x10, "MN15 MENU:MIDI", 0.150)
press(37.950, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(38.400, ":cpanel:CPR_SEG10", 0x20, "MN16 MENU:DISK", 0.150)
press(38.850, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(39.300, ":cpanel:CPR_SEG10", 0x04, "MN17 MENU:SOUND", 0.150)
press(39.750, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(40.200, ":cpanel:CPR_SEG10", 0x08, "MN18 MENU:CONTROL", 0.150)
press(40.650, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(41.100, ":cpanel:CPR_SEG10", 0x10, "MN19 MENU:MIDI", 0.150)
press(41.550, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(42.000, ":cpanel:CPR_SEG10", 0x20, "MN20 MENU:DISK", 0.150)
press(42.450, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(42.900, ":cpanel:CPR_SEG10", 0x04, "MN21 MENU:SOUND", 0.150)
press(43.350, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(43.800, ":cpanel:CPR_SEG10", 0x08, "MN22 MENU:CONTROL", 0.150)
press(44.250, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
press(44.700, ":cpanel:CPR_SEG10", 0x10, "MN23 MENU:MIDI", 0.150)
press(45.150, ":cpanel:CPL_SEG7", 0x08, "EXIT", 0.150)
snap(47.600, "pre")
snap(48.600, "pre2")
press(49.600, ":cpanel:CPR_SEG10", 0x20, "LIVE MENU:DISK", 0.250)
snap(51.600, "disk")
press(52.600, ":cpanel:CPR_SEG10", 0x04, "LIVE MENU:SOUND", 0.250)
snap(54.600, "sound")
press(55.600, ":cpanel:CPR_SEG2", 0x01, "LIVE PIANO", 0.250)
snap(57.600, "piano")
press(58.600, ":cpanel:CPR_SEG1", 0x02, "LIVE ORCHPAD", 0.250)
snap(60.600, "orch")
at(61.600, "done", function() log("RUN DONE"); mac:exit() end)

-- The repro luas in notes/kn5000-cpserial-repros/ rely on their actions being emitted in
-- strictly increasing time order.  Some schedules here press several buttons AT THE SAME
-- INSTANT, which interleaves press/release pairs, so sort explicitly.  (Without this the
-- second and later buttons of a simultaneous group get pressed and released in the same
-- dispatch, i.e. invisibly to the panel's 2-scan / 14 ms confirmation filter.)
table.sort(acts, function(a, b) return a.t < b.t end)
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
