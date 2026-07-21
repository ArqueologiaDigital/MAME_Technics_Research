-- Slow, unambiguous single presses from a SETTLED boot (no boot-window traffic).
-- This rate is documented as correct on the SHIPPED build too, so it is a valid
-- A-vs-pristine controlled comparison.
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
local function wheel(v)
  local p = mac.ioport.ports[":cpanel:ENCODER"]
  if not p then log("NO ENCODER PORT") return end
  for _, f in pairs(p.fields) do f.user_value = v end
end

snap(26.0, "home_settled")

local seq = {
  {":cpanel:CPL_SEG4", 0x20, "SPLIT_POINT"},
  {":cpanel:CPL_SEG4", 0x40, "AUTO_PLAY_CHORD"},
  {":cpanel:CPL_SEG4", 0x20, "SPLIT_POINT_APC_ON"},
}
local t = 28.0
for i, e in ipairs(seq) do
  press(t, e[1], e[2], "PRESS "..e[3])
  snap(t + 0.40, string.format("%02d_%s_early", i-1, e[3]))
  snap(t + 1.80, string.format("%02d_%s", i-1, e[3]))
  press(t + 2.60, ":cpanel:CPL_SEG7", 0x08, "exit")
  t = t + 4.20
end
press(t, ":cpanel:CPL_SEG4", 0x40, "AUTO_PLAY_CHORD off")
t = t + 1.5
press(t, ":cpanel:CPL_SEG7", 0x08, "EXIT")
snap(t + 3.0, "home_after")
local WT = t + 4.5
for k = 1, 12 do at(WT + k*0.10, "", function() wheel((50+k) % 101) end) end
snap(WT + 3.0, "tempo_up12")
for k = 1, 12 do at(WT + 5.0 + k*0.10, "", function() wheel((62-k) % 101) end) end
snap(WT + 9.0, "tempo_back")
at(WT + 11.0, "done", function() log("RUN DONE"); mac:exit() end)

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
