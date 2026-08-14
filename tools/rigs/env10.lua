-- env10.lua: where does the RLS param live? Full-class capture (ALL TG writes, any group)
-- for RLS=0 vs RLS=100 vs baseline RLS=44, plus SUSTAIN PEDAL HOLD->LONG.
local mac = manager.machine
local function log(s) emu.print_error(s) end
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]

local tg_addr = {0,0}
local watching = false
local cap = {}
local function mktap(base, idx, label, name)
  return prog:install_write_tap(base, base+3, name, function(off, data, mask)
    if (mask & 0x0000ffff) ~= 0 then tg_addr[idx] = data & 0xffff end
    if (mask & 0xffff0000) ~= 0 then
      local a = tg_addr[idx]; local d = (data>>16) & 0xffff
      if watching and (a & 0xff00) ~= 0xfc00 then
        cap[#cap+1] = ("%s%04X=%04X"):format(label, a, d)
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
local function note(t, label)
  at(t, "", function() watching = true; cap = {} end)
  at(t+0.2, "", function()
    local p = mac.ioport.ports[":KEYS1"]
    for _, f in pairs(p.fields) do if f.mask == 0x0100 then f:set_value(1) end end
  end)
  at(t+1.4, "", function()
    local p = mac.ioport.ports[":KEYS1"]
    for _, f in pairs(p.fields) do if f.mask == 0x0100 then f:clear_value() end end
  end)
  at(t+2.6, "", function()
    watching = false
    log(("CAP %s n=%d: %s"):format(label, #cap, table.concat(cap, " ")))
  end)
  return t + 3.0
end

press(23.0, ":cpanel:CPR_SEG0", 0x04, "PROGRAM-MENUS")
press(25.0, ":cpanel:CPR_SEG5", 0x10, "SOUND-EDIT")
press(27.0, ":cpanel:CPL_SEG0", 0x20, "AMPLITUDE")
press(29.0, ":cpanel:CPC_SEG11", 0x10, "PAGE-UP")
at(31.0, "taps", function()
  _G.t1 = mktap(0x98040000, 1, "M", "tgA")
  _G.t2 = mktap(0x98050000, 2, "S", "tgB")
end)
local t = note(31.5, "BASE-RLS44")
t = press(t, ":cpanel:CPC_SEG9", 0x20, "RLS to-floor", 10.0)
snap(t, "RLS0"); t = t + 0.5
t = note(t, "RLS0")
t = press(t, ":cpanel:CPC_SEG9", 0x10, "RLS to-max", 10.0)
snap(t, "RLS100"); t = t + 0.5
t = note(t, "RLS100")
-- sustain pedal: HOLD -> LONG (down once toggles?)
t = press(t, ":cpanel:CPC_SEG9", 0x80, "SUSPEDAL-DOWN")
snap(t, "SUSPEDAL-B"); t = t + 0.5
t = note(t, "SUSPEDAL-B")
at(t + 1.0, "exit", function() log("ENV10 DONE"); mac:exit() end)

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
log("env10 armed")
