-- env9.lua: AMPLITUDE->ENVELOPE 7-parameter sweep, corrected:
--  * write taps installed AFTER boot+navigation (t=31.5) -- taps armed at t=0 die during boot
--  * C4 pressed by port+mask (:KEYS1 0x0100) -- field names are GM-note renamed
-- For each param: floor / mid / ceiling via the column balance buttons (auto-repeat),
-- snapshot the screen (ground truth), play C4, dump every group-0 TG write incl. release.
local mac = manager.machine
local function log(s) emu.print_error(s) end
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]

local tg_addr = {0,0}
local watching = false
local cap = {}
local other = 0
local function mktap(base, idx, label, name)
  return prog:install_write_tap(base, base+3, name, function(off, data, mask)
    if (mask & 0x0000ffff) ~= 0 then tg_addr[idx] = data & 0xffff end
    if (mask & 0xffff0000) ~= 0 then
      local a = tg_addr[idx]; local d = (data>>16) & 0xffff
      if watching and (a & 0xff00) ~= 0xfc00 then
        if a < 0x0400 then cap[#cap+1] = {tg=label, reg=a, data=d}
        else other = other + 1 end
      end
    end
    return nil
  end)
end

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
local shots = 0
local function snap(t, desc)
  at(t, "", function() mac.video:snapshot(); shots = shots + 1
    log(("SNAP#%d %s"):format(shots-1, desc)) end)
end

press(23.0, ":cpanel:CPR_SEG0", 0x04, "PROGRAM-MENUS")
press(25.0, ":cpanel:CPR_SEG5", 0x10, "SOUND-EDIT")
press(27.0, ":cpanel:CPL_SEG0", 0x20, "AMPLITUDE")
press(29.0, ":cpanel:CPC_SEG11", 0x10, "PAGE-UP")
snap (31.0, "SWEEP-BASELINE")
at(31.5, "install taps", function()
  _G.t1 = mktap(0x98040000, 1, "M", "tgA")
  _G.t2 = mktap(0x98050000, 2, "S", "tgB")
end)

local function note(t, label)
  at(t, "", function() watching = true; other = 0; cap = {} end)
  at(t+0.2, "", function()
    log(("NOTE-ON %s"):format(label))
    local p = mac.ioport.ports[":KEYS1"]
    for _, f in pairs(p.fields) do if f.mask == 0x0100 then f:set_value(1) end end
  end)
  at(t+1.4, "", function()
    local p = mac.ioport.ports[":KEYS1"]
    for _, f in pairs(p.fields) do if f.mask == 0x0100 then f:clear_value() end end
  end)
  at(t+2.6, "", function()
    watching = false
    local parts = {}
    for _, w in ipairs(cap) do parts[#parts+1] = ("%s%03X=%04X"):format(w.tg, w.reg, w.data) end
    log(("CAP %s n=%d other=%d: %s"):format(label, #cap, other, table.concat(parts, " ")))
  end)
  return t + 3.0
end

local params = {
  {name="ATK",  tag=":cpanel:CPC_SEG8", up=0x01, dn=0x02, base=0},
  {name="PEAK", tag=":cpanel:CPC_SEG8", up=0x04, dn=0x08, base=100},
  {name="DCY1", tag=":cpanel:CPC_SEG8", up=0x10, dn=0x20, base=84},
  {name="SUS1", tag=":cpanel:CPC_SEG8", up=0x40, dn=0x80, base=0},
  {name="DCY2", tag=":cpanel:CPC_SEG9", up=0x01, dn=0x02, base=78},
  {name="SUS2", tag=":cpanel:CPC_SEG9", up=0x04, dn=0x08, base=0},
  {name="RLS",  tag=":cpanel:CPC_SEG9", up=0x10, dn=0x20, base=44},
}

local t = 32.0
for _, p in ipairs(params) do
  t = press(t, p.tag, p.dn, p.name.." to-floor", 10.0)
  snap(t, p.name.."-MIN"); t = t + 0.5
  t = note(t, p.name.."-MIN")
  t = press(t, p.tag, p.up, p.name.." to-mid", 4.0)
  snap(t, p.name.."-MID"); t = t + 0.5
  t = note(t, p.name.."-MID")
  t = press(t, p.tag, p.up, p.name.." to-max", 6.0)
  snap(t, p.name.."-MAX"); t = t + 0.5
  t = note(t, p.name.."-MAX")
  if p.base < 100 then
    t = press(t, p.tag, p.dn, p.name.." restore-floor", 10.0)
    if p.base > 0 then
      t = press(t, p.tag, p.up, p.name.." restore-up", p.base / 12.7)
    end
  end
  snap(t, p.name.."-RESTORED"); t = t + 0.5
end

t = press(t, ":cpanel:CPC_SEG9", 0x40, "SUSPEDAL-UP")
snap(t, "SUSPEDAL-TOGGLED"); t = t + 0.5
t = note(t, "SUSPEDAL")

at(t + 1.0, "exit", function() log("SWEEP DONE"); mac:exit() end)

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
log(("env9 armed, ends ~%.0f s"):format(t + 2))
