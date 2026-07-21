
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
press(30.000, ":cpanel:CPR_SEG2", 0x01, "S0 CPR_SEG2/01", 0.120)
press(30.000, ":cpanel:CPR_SEG1", 0x02, "S0 CPR_SEG1/02", 0.120)
press(30.000, ":cpanel:CPL_SEG0", 0x01, "S0 CPL_SEG0/01", 0.120)
press(30.600, ":cpanel:CPR_SEG2", 0x01, "S1 CPR_SEG2/01", 0.120)
press(30.600, ":cpanel:CPR_SEG1", 0x02, "S1 CPR_SEG1/02", 0.120)
press(30.600, ":cpanel:CPL_SEG0", 0x01, "S1 CPL_SEG0/01", 0.120)
press(31.200, ":cpanel:CPR_SEG2", 0x01, "S2 CPR_SEG2/01", 0.120)
press(31.200, ":cpanel:CPR_SEG1", 0x02, "S2 CPR_SEG1/02", 0.120)
press(31.200, ":cpanel:CPL_SEG0", 0x01, "S2 CPL_SEG0/01", 0.120)
press(31.800, ":cpanel:CPR_SEG2", 0x01, "S3 CPR_SEG2/01", 0.120)
press(31.800, ":cpanel:CPR_SEG1", 0x02, "S3 CPR_SEG1/02", 0.120)
press(31.800, ":cpanel:CPL_SEG0", 0x01, "S3 CPL_SEG0/01", 0.120)
press(32.400, ":cpanel:CPR_SEG2", 0x01, "S4 CPR_SEG2/01", 0.120)
press(32.400, ":cpanel:CPR_SEG1", 0x02, "S4 CPR_SEG1/02", 0.120)
press(32.400, ":cpanel:CPL_SEG0", 0x01, "S4 CPL_SEG0/01", 0.120)
press(33.000, ":cpanel:CPR_SEG2", 0x01, "S5 CPR_SEG2/01", 0.120)
press(33.000, ":cpanel:CPR_SEG1", 0x02, "S5 CPR_SEG1/02", 0.120)
press(33.000, ":cpanel:CPL_SEG0", 0x01, "S5 CPL_SEG0/01", 0.120)
press(33.600, ":cpanel:CPR_SEG2", 0x01, "S6 CPR_SEG2/01", 0.120)
press(33.600, ":cpanel:CPR_SEG1", 0x02, "S6 CPR_SEG1/02", 0.120)
press(33.600, ":cpanel:CPL_SEG0", 0x01, "S6 CPL_SEG0/01", 0.120)
press(34.200, ":cpanel:CPR_SEG2", 0x01, "S7 CPR_SEG2/01", 0.120)
press(34.200, ":cpanel:CPR_SEG1", 0x02, "S7 CPR_SEG1/02", 0.120)
press(34.200, ":cpanel:CPL_SEG0", 0x01, "S7 CPL_SEG0/01", 0.120)
press(34.800, ":cpanel:CPR_SEG2", 0x01, "S8 CPR_SEG2/01", 0.120)
press(34.800, ":cpanel:CPR_SEG1", 0x02, "S8 CPR_SEG1/02", 0.120)
press(34.800, ":cpanel:CPL_SEG0", 0x01, "S8 CPL_SEG0/01", 0.120)
press(35.400, ":cpanel:CPR_SEG2", 0x01, "S9 CPR_SEG2/01", 0.120)
press(35.400, ":cpanel:CPR_SEG1", 0x02, "S9 CPR_SEG1/02", 0.120)
press(35.400, ":cpanel:CPL_SEG0", 0x01, "S9 CPL_SEG0/01", 0.120)
press(36.000, ":cpanel:CPR_SEG2", 0x01, "S10 CPR_SEG2/01", 0.120)
press(36.000, ":cpanel:CPR_SEG1", 0x02, "S10 CPR_SEG1/02", 0.120)
press(36.000, ":cpanel:CPL_SEG0", 0x01, "S10 CPL_SEG0/01", 0.120)
press(36.600, ":cpanel:CPR_SEG2", 0x01, "S11 CPR_SEG2/01", 0.120)
press(36.600, ":cpanel:CPR_SEG1", 0x02, "S11 CPR_SEG1/02", 0.120)
press(36.600, ":cpanel:CPL_SEG0", 0x01, "S11 CPL_SEG0/01", 0.120)
press(37.200, ":cpanel:CPR_SEG2", 0x01, "S12 CPR_SEG2/01", 0.120)
press(37.200, ":cpanel:CPR_SEG1", 0x02, "S12 CPR_SEG1/02", 0.120)
press(37.200, ":cpanel:CPL_SEG0", 0x01, "S12 CPL_SEG0/01", 0.120)
press(37.800, ":cpanel:CPR_SEG2", 0x01, "S13 CPR_SEG2/01", 0.120)
press(37.800, ":cpanel:CPR_SEG1", 0x02, "S13 CPR_SEG1/02", 0.120)
press(37.800, ":cpanel:CPL_SEG0", 0x01, "S13 CPL_SEG0/01", 0.120)
press(38.400, ":cpanel:CPR_SEG2", 0x01, "S14 CPR_SEG2/01", 0.120)
press(38.400, ":cpanel:CPR_SEG1", 0x02, "S14 CPR_SEG1/02", 0.120)
press(38.400, ":cpanel:CPL_SEG0", 0x01, "S14 CPL_SEG0/01", 0.120)
press(39.000, ":cpanel:CPR_SEG2", 0x01, "S15 CPR_SEG2/01", 0.120)
press(39.000, ":cpanel:CPR_SEG1", 0x02, "S15 CPR_SEG1/02", 0.120)
press(39.000, ":cpanel:CPL_SEG0", 0x01, "S15 CPL_SEG0/01", 0.120)
press(39.600, ":cpanel:CPR_SEG2", 0x01, "S16 CPR_SEG2/01", 0.120)
press(39.600, ":cpanel:CPR_SEG1", 0x02, "S16 CPR_SEG1/02", 0.120)
press(39.600, ":cpanel:CPL_SEG0", 0x01, "S16 CPL_SEG0/01", 0.120)
press(40.200, ":cpanel:CPR_SEG2", 0x01, "S17 CPR_SEG2/01", 0.120)
press(40.200, ":cpanel:CPR_SEG1", 0x02, "S17 CPR_SEG1/02", 0.120)
press(40.200, ":cpanel:CPL_SEG0", 0x01, "S17 CPL_SEG0/01", 0.120)
press(40.800, ":cpanel:CPR_SEG2", 0x01, "S18 CPR_SEG2/01", 0.120)
press(40.800, ":cpanel:CPR_SEG1", 0x02, "S18 CPR_SEG1/02", 0.120)
press(40.800, ":cpanel:CPL_SEG0", 0x01, "S18 CPL_SEG0/01", 0.120)
press(41.400, ":cpanel:CPR_SEG2", 0x01, "S19 CPR_SEG2/01", 0.120)
press(41.400, ":cpanel:CPR_SEG1", 0x02, "S19 CPR_SEG1/02", 0.120)
press(41.400, ":cpanel:CPL_SEG0", 0x01, "S19 CPL_SEG0/01", 0.120)
snap(44.000, "pre")
snap(45.000, "pre2")
press(46.000, ":cpanel:CPR_SEG10", 0x20, "LIVE MENU:DISK", 0.250)
snap(48.000, "disk")
press(49.000, ":cpanel:CPR_SEG10", 0x04, "LIVE MENU:SOUND", 0.250)
snap(51.000, "sound")
press(52.000, ":cpanel:CPR_SEG2", 0x01, "LIVE PIANO", 0.250)
snap(54.000, "piano")
press(55.000, ":cpanel:CPR_SEG1", 0x02, "LIVE ORCHPAD", 0.250)
snap(57.000, "orch")
at(58.000, "done", function() log("RUN DONE"); mac:exit() end)

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
