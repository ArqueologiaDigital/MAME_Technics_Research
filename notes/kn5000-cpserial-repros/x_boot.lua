
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
press(2.000, ":cpanel:CPR_SEG2", 0x01, "B0 PIANO", 0.120)
press(2.300, ":cpanel:CPR_SEG2", 0x02, "B1 GUITAR", 0.120)
press(2.600, ":cpanel:CPR_SEG2", 0x04, "B2 STRINGS", 0.120)
press(2.900, ":cpanel:CPR_SEG2", 0x08, "B3 BRASS", 0.120)
press(3.200, ":cpanel:CPR_SEG2", 0x10, "B4 FLUTE", 0.120)
press(3.500, ":cpanel:CPR_SEG2", 0x20, "B5 SAX", 0.120)
press(3.800, ":cpanel:CPR_SEG1", 0x01, "B6 ORGAN", 0.120)
press(4.100, ":cpanel:CPR_SEG1", 0x02, "B7 ORCHPAD", 0.120)
press(4.400, ":cpanel:CPR_SEG1", 0x04, "B8 SYNTH", 0.120)
press(4.700, ":cpanel:CPR_SEG1", 0x08, "B9 BASS", 0.120)
press(5.000, ":cpanel:CPR_SEG1", 0x80, "B10 DRUMKITS", 0.120)
press(5.300, ":cpanel:CPR_SEG2", 0x01, "B11 PIANO", 0.120)
press(5.600, ":cpanel:CPR_SEG2", 0x02, "B12 GUITAR", 0.120)
press(5.900, ":cpanel:CPR_SEG2", 0x04, "B13 STRINGS", 0.120)
press(6.200, ":cpanel:CPR_SEG2", 0x08, "B14 BRASS", 0.120)
press(6.500, ":cpanel:CPR_SEG2", 0x10, "B15 FLUTE", 0.120)
press(6.800, ":cpanel:CPR_SEG2", 0x20, "B16 SAX", 0.120)
press(7.100, ":cpanel:CPR_SEG1", 0x01, "B17 ORGAN", 0.120)
press(7.400, ":cpanel:CPR_SEG1", 0x02, "B18 ORCHPAD", 0.120)
press(7.700, ":cpanel:CPR_SEG1", 0x04, "B19 SYNTH", 0.120)
press(8.000, ":cpanel:CPR_SEG1", 0x08, "B20 BASS", 0.120)
press(8.300, ":cpanel:CPR_SEG1", 0x80, "B21 DRUMKITS", 0.120)
press(8.600, ":cpanel:CPR_SEG2", 0x01, "B22 PIANO", 0.120)
press(8.900, ":cpanel:CPR_SEG2", 0x02, "B23 GUITAR", 0.120)
press(9.200, ":cpanel:CPR_SEG2", 0x04, "B24 STRINGS", 0.120)
press(9.500, ":cpanel:CPR_SEG2", 0x08, "B25 BRASS", 0.120)
press(9.800, ":cpanel:CPR_SEG2", 0x10, "B26 FLUTE", 0.120)
press(10.100, ":cpanel:CPR_SEG2", 0x20, "B27 SAX", 0.120)
press(10.400, ":cpanel:CPR_SEG1", 0x01, "B28 ORGAN", 0.120)
press(10.700, ":cpanel:CPR_SEG1", 0x02, "B29 ORCHPAD", 0.120)
press(11.000, ":cpanel:CPR_SEG1", 0x04, "B30 SYNTH", 0.120)
press(11.300, ":cpanel:CPR_SEG1", 0x08, "B31 BASS", 0.120)
press(11.600, ":cpanel:CPR_SEG1", 0x80, "B32 DRUMKITS", 0.120)
press(11.900, ":cpanel:CPR_SEG2", 0x01, "B33 PIANO", 0.120)
press(12.200, ":cpanel:CPR_SEG2", 0x02, "B34 GUITAR", 0.120)
press(12.500, ":cpanel:CPR_SEG2", 0x04, "B35 STRINGS", 0.120)
press(12.800, ":cpanel:CPR_SEG2", 0x08, "B36 BRASS", 0.120)
press(13.100, ":cpanel:CPR_SEG2", 0x10, "B37 FLUTE", 0.120)
press(13.400, ":cpanel:CPR_SEG2", 0x20, "B38 SAX", 0.120)
press(13.700, ":cpanel:CPR_SEG1", 0x01, "B39 ORGAN", 0.120)
press(14.000, ":cpanel:CPR_SEG1", 0x02, "B40 ORCHPAD", 0.120)
press(14.300, ":cpanel:CPR_SEG1", 0x04, "B41 SYNTH", 0.120)
press(14.600, ":cpanel:CPR_SEG1", 0x08, "B42 BASS", 0.120)
press(14.900, ":cpanel:CPR_SEG1", 0x80, "B43 DRUMKITS", 0.120)
press(15.200, ":cpanel:CPR_SEG2", 0x01, "B44 PIANO", 0.120)
press(15.500, ":cpanel:CPR_SEG2", 0x02, "B45 GUITAR", 0.120)
press(15.800, ":cpanel:CPR_SEG2", 0x04, "B46 STRINGS", 0.120)
press(16.100, ":cpanel:CPR_SEG2", 0x08, "B47 BRASS", 0.120)
press(16.400, ":cpanel:CPR_SEG2", 0x10, "B48 FLUTE", 0.120)
press(16.700, ":cpanel:CPR_SEG2", 0x20, "B49 SAX", 0.120)
press(17.000, ":cpanel:CPR_SEG1", 0x01, "B50 ORGAN", 0.120)
press(17.300, ":cpanel:CPR_SEG1", 0x02, "B51 ORCHPAD", 0.120)
press(17.600, ":cpanel:CPR_SEG1", 0x04, "B52 SYNTH", 0.120)
press(17.900, ":cpanel:CPR_SEG1", 0x08, "B53 BASS", 0.120)
press(18.200, ":cpanel:CPR_SEG1", 0x80, "B54 DRUMKITS", 0.120)
press(18.500, ":cpanel:CPR_SEG2", 0x01, "B55 PIANO", 0.120)
press(18.800, ":cpanel:CPR_SEG2", 0x02, "B56 GUITAR", 0.120)
press(19.100, ":cpanel:CPR_SEG2", 0x04, "B57 STRINGS", 0.120)
press(19.400, ":cpanel:CPR_SEG2", 0x08, "B58 BRASS", 0.120)
press(19.700, ":cpanel:CPR_SEG2", 0x10, "B59 FLUTE", 0.120)
press(20.000, ":cpanel:CPR_SEG2", 0x20, "B60 SAX", 0.120)
press(20.300, ":cpanel:CPR_SEG1", 0x01, "B61 ORGAN", 0.120)
press(20.600, ":cpanel:CPR_SEG1", 0x02, "B62 ORCHPAD", 0.120)
press(20.900, ":cpanel:CPR_SEG1", 0x04, "B63 SYNTH", 0.120)
snap(24.000, "pre")
snap(25.000, "pre2")
press(26.000, ":cpanel:CPR_SEG10", 0x20, "LIVE MENU:DISK", 0.250)
snap(28.000, "disk")
press(29.000, ":cpanel:CPR_SEG10", 0x04, "LIVE MENU:SOUND", 0.250)
snap(31.000, "sound")
press(32.000, ":cpanel:CPR_SEG2", 0x01, "LIVE PIANO", 0.250)
snap(34.000, "piano")
press(35.000, ":cpanel:CPR_SEG1", 0x02, "LIVE ORCHPAD", 0.250)
snap(37.000, "orch")
at(38.000, "done", function() log("RUN DONE"); mac:exit() end)

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
