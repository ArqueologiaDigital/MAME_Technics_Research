-- env3.lua: AMPLITUDE->ENVELOPE 7-parameter sweep.
-- For each on-screen param (ATK PEAK DCY1 SUS1 DCY2 SUS2 RLS): drive to floor/mid/ceiling
-- with the column's balance up/down buttons (hold = auto-repeat ~12.7 steps/s), snapshot the
-- screen (ground-truth values), play C4 and capture ALL group-0 TG writes (note-on block +
-- key-up release burst). Machine-time logged for the parallel -wavwrite capture.
local mac = manager.machine
local function log(s) emu.print_error(s) end
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]

local tg_addr = {0,0}
local watching = false
local cap = {}
local other = 0
local function tap(base, idx, label)
  prog:install_write_tap(base, base+3, "tgenv"..idx, function(off, data, mask)
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
_G.envtap1 = tap(0x98040000, 1, "M")
_G.envtap2 = tap(0x98050000, 2, "S")

local function fld(tag, mask)
  local p = mac.ioport.ports[tag]
  if not p then log("NOPORT "..tag); return nil end
  for _, f in pairs(p.fields) do if f.mask == mask then return f end end
  log(("NOFIELD %s %02X"):format(tag, mask)); return nil
end

local acts = {}
local function at(t, desc, fn) acts[#acts+1] = {t=t, desc=desc, fn=fn} end
local function press(t, tag, mask, desc, hold)
  hold = hold or 0.35
  at(t, desc, function() local f=fld(tag,mask) if f then f:set_value(1) end end)
  at(t+hold, "", function() local f=fld(tag,mask) if f then f:clear_value() end end)
  return t + hold + 0.3
end
local shots = 0
local function snap(t, desc)
  at(t, "", function() mac.video:snapshot(); shots = shots + 1
    log(("SNAP#%d %s"):format(shots-1, desc)) end)
end

-- navigate to the ENVELOPE page
press(23.0, ":cpanel:CPR_SEG0", 0x04, "PROGRAM-MENUS")
press(25.0, ":cpanel:CPR_SEG5", 0x10, "SOUND-EDIT")
press(27.0, ":cpanel:CPL_SEG0", 0x20, "AMPLITUDE")
press(29.0, ":cpanel:CPC_SEG11", 0x10, "PAGE-UP")
snap (31.0, "SWEEP-BASELINE")

-- C4 = KEYS1 mask 0x0100 (idx 0x18); field names are GM-note renamed, so match by mask
local function note(t, label)
  at(t, "", function() watching = true; other = 0; cap = {} end)
  at(t+0.2, "", function()
    local mt = mac.time.seconds + mac.time.attoseconds/1e18
    log(("NOTE-ON %s mt=%.3f"):format(label, mt))
    local f = fld(":KEYS1", 0x0100); if f then f:set_value(1) end
  end)
  at(t+1.4, "", function()
    local mt = mac.time.seconds + mac.time.attoseconds/1e18
    log(("NOTE-OFF %s mt=%.3f"):format(label, mt))
    local f = fld(":KEYS1", 0x0100); if f then f:clear_value() end
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
  -- floor
  t = press(t, p.tag, p.dn, p.name.." to-floor", 10.0)
  snap(t, p.name.."-MIN"); t = t + 0.5
  t = note(t, p.name.."-MIN")
  -- mid (~+51)
  t = press(t, p.tag, p.up, p.name.." to-mid", 4.0)
  snap(t, p.name.."-MID"); t = t + 0.5
  t = note(t, p.name.."-MID")
  -- ceiling
  t = press(t, p.tag, p.up, p.name.." to-max", 6.0)
  snap(t, p.name.."-MAX"); t = t + 0.5
  t = note(t, p.name.."-MAX")
  -- restore approx baseline
  if p.base < 100 then
    t = press(t, p.tag, p.dn, p.name.." restore-floor", 10.0)
    if p.base > 0 then
      t = press(t, p.tag, p.up, p.name.." restore-up", p.base / 12.7)
    end
  end
  snap(t, p.name.."-RESTORED"); t = t + 0.5
end

-- bonus: SUSTAIN PEDAL toggle (PART10 buttons)
t = press(t, ":cpanel:CPC_SEG9", 0x40, "SUSPEDAL-UP")
snap(t, "SUSPEDAL-TOGGLED"); t = t + 0.5
t = note(t, "SUSPEDAL")

at(t + 1.0, "exit", function() log(("SWEEP DONE t=%.1f"):format(t)); mac:exit() end)

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
log(("env3 armed, ends ~%.0f s"):format(t + 2))
