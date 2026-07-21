
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
press(24.000, ":cpanel:CPR_SEG8", 0x20, "START/STOP (rhythm on)", 0.250)
press(26.000, ":cpanel:CPR_SEG2", 0x01, "R0 PIANO", 0.100)
press(26.500, ":cpanel:CPR_SEG2", 0x02, "R1 GUITAR", 0.100)
press(27.000, ":cpanel:CPR_SEG2", 0x04, "R2 STRINGS", 0.100)
press(27.500, ":cpanel:CPR_SEG2", 0x08, "R3 BRASS", 0.100)
press(28.000, ":cpanel:CPR_SEG2", 0x10, "R4 FLUTE", 0.100)
press(28.500, ":cpanel:CPR_SEG2", 0x20, "R5 SAX", 0.100)
press(29.000, ":cpanel:CPR_SEG1", 0x01, "R6 ORGAN", 0.100)
press(29.500, ":cpanel:CPR_SEG1", 0x02, "R7 ORCHPAD", 0.100)
press(30.000, ":cpanel:CPR_SEG1", 0x04, "R8 SYNTH", 0.100)
press(30.500, ":cpanel:CPR_SEG1", 0x08, "R9 BASS", 0.100)
press(31.000, ":cpanel:CPR_SEG1", 0x80, "R10 DRUMKITS", 0.100)
press(31.500, ":cpanel:CPR_SEG2", 0x01, "R11 PIANO", 0.100)
press(32.000, ":cpanel:CPR_SEG2", 0x02, "R12 GUITAR", 0.100)
press(32.500, ":cpanel:CPR_SEG2", 0x04, "R13 STRINGS", 0.100)
press(33.000, ":cpanel:CPR_SEG2", 0x08, "R14 BRASS", 0.100)
press(33.500, ":cpanel:CPR_SEG2", 0x10, "R15 FLUTE", 0.100)
press(34.000, ":cpanel:CPR_SEG2", 0x20, "R16 SAX", 0.100)
press(34.500, ":cpanel:CPR_SEG1", 0x01, "R17 ORGAN", 0.100)
press(35.000, ":cpanel:CPR_SEG1", 0x02, "R18 ORCHPAD", 0.100)
press(35.500, ":cpanel:CPR_SEG1", 0x04, "R19 SYNTH", 0.100)
press(36.000, ":cpanel:CPR_SEG1", 0x08, "R20 BASS", 0.100)
press(36.500, ":cpanel:CPR_SEG1", 0x80, "R21 DRUMKITS", 0.100)
press(37.000, ":cpanel:CPR_SEG2", 0x01, "R22 PIANO", 0.100)
press(37.500, ":cpanel:CPR_SEG2", 0x02, "R23 GUITAR", 0.100)
press(38.000, ":cpanel:CPR_SEG2", 0x04, "R24 STRINGS", 0.100)
press(38.500, ":cpanel:CPR_SEG2", 0x08, "R25 BRASS", 0.100)
press(39.000, ":cpanel:CPR_SEG2", 0x10, "R26 FLUTE", 0.100)
press(39.500, ":cpanel:CPR_SEG2", 0x20, "R27 SAX", 0.100)
press(40.000, ":cpanel:CPR_SEG1", 0x01, "R28 ORGAN", 0.100)
press(40.500, ":cpanel:CPR_SEG1", 0x02, "R29 ORCHPAD", 0.100)
press(41.000, ":cpanel:CPR_SEG1", 0x04, "R30 SYNTH", 0.100)
press(41.500, ":cpanel:CPR_SEG1", 0x08, "R31 BASS", 0.100)
press(42.000, ":cpanel:CPR_SEG1", 0x80, "R32 DRUMKITS", 0.100)
press(42.500, ":cpanel:CPR_SEG2", 0x01, "R33 PIANO", 0.100)
press(43.000, ":cpanel:CPR_SEG2", 0x02, "R34 GUITAR", 0.100)
press(43.500, ":cpanel:CPR_SEG2", 0x04, "R35 STRINGS", 0.100)
press(44.000, ":cpanel:CPR_SEG2", 0x08, "R36 BRASS", 0.100)
press(44.500, ":cpanel:CPR_SEG2", 0x10, "R37 FLUTE", 0.100)
press(45.000, ":cpanel:CPR_SEG2", 0x20, "R38 SAX", 0.100)
press(45.500, ":cpanel:CPR_SEG1", 0x01, "R39 ORGAN", 0.100)
press(46.500, ":cpanel:CPL_SEG2", 0x01, "FILL IN 1", 0.250)
press(47.500, ":cpanel:CPL_SEG4", 0x02, "VARIATION 2", 0.250)
press(48.500, ":cpanel:CPR_SEG8", 0x20, "START/STOP (rhythm off)", 0.250)
snap(51.000, "pre")
snap(52.000, "pre2")
press(53.000, ":cpanel:CPR_SEG10", 0x20, "LIVE MENU:DISK", 0.250)
snap(55.000, "disk")
press(56.000, ":cpanel:CPR_SEG10", 0x04, "LIVE MENU:SOUND", 0.250)
snap(58.000, "sound")
press(59.000, ":cpanel:CPR_SEG2", 0x01, "LIVE PIANO", 0.250)
snap(61.000, "piano")
press(62.000, ":cpanel:CPR_SEG1", 0x02, "LIVE ORCHPAD", 0.250)
snap(64.000, "orch")
at(65.000, "done", function() log("RUN DONE"); mac:exit() end)

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
