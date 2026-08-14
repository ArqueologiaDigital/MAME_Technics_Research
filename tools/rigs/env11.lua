-- env11.lua: (a) organ baseline r0-r2 (per-sound attack encoding), (b) RLS sweep on a
-- SUSTAINING sound (organ) incl. key-up writes, (c) FILTER ENVELOPE probe: does the
-- filter-EG ATK move r4..rA? (identify the second register bank)
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
local function note(t, label, dur)
  dur = dur or 1.2
  at(t, "", function() watching = true; cap = {} end)
  at(t+0.2, "", function()
    local p = mac.ioport.ports[":KEYS1"]
    for _, f in pairs(p.fields) do if f.mask == 0x0100 then f:set_value(1) end end
  end)
  at(t+0.2+dur, "", function()
    local p = mac.ioport.ports[":KEYS1"]
    for _, f in pairs(p.fields) do if f.mask == 0x0100 then f:clear_value() end end
  end)
  at(t+0.2+dur+1.2, "", function()
    watching = false
    log(("CAP %s n=%d: %s"):format(label, #cap, table.concat(cap, " ")))
  end)
  return t + dur + 3.0
end

-- select TAB ORGAN sound for R1
press(22.0, ":cpanel:CPR_SEG3", 0x20, "TAB-ORGAN")
snap (24.0, "ORGAN-SELECT")
-- into sound edit
press(24.5, ":cpanel:CPR_SEG0", 0x04, "PROGRAM-MENUS")
press(26.5, ":cpanel:CPR_SEG5", 0x10, "SOUND-EDIT")
press(28.5, ":cpanel:CPL_SEG0", 0x20, "AMPLITUDE")
press(30.5, ":cpanel:CPC_SEG11", 0x10, "PAGE-UP")
snap (32.5, "ORGAN-ENVELOPE")
at(33.0, "taps", function()
  _G.t1 = mktap(0x98040000, 1, "M", "tgA")
  _G.t2 = mktap(0x98050000, 2, "S", "tgB")
end)
local t = note(33.5, "ORGAN-BASE")
t = press(t, ":cpanel:CPC_SEG9", 0x20, "RLS to-floor", 10.0)
snap(t, "ORGAN-RLS0"); t = t + 0.5
t = note(t, "ORGAN-RLS0")
t = press(t, ":cpanel:CPC_SEG9", 0x10, "RLS to-max", 10.0)
snap(t, "ORGAN-RLS100"); t = t + 0.5
t = note(t, "ORGAN-RLS100")
-- FILTER ENVELOPE probe: EXIT to SOUND EDIT MENU? PAGE back then FILTER = LCDL5.
t = press(t, ":cpanel:CPC_SEG11", 0x80, "EXIT")           -- back to SOUND EDIT MENU
snap(t, "AFTER-EXIT"); t = t + 0.3
t = press(t, ":cpanel:CPL_SEG0", 0x04, "FILTER(LCDL5)")   -- FILTER EDIT page 1/4
t = press(t, ":cpanel:CPC_SEG11", 0x10, "PAGE-UP")        -- 2/4
t = press(t, ":cpanel:CPC_SEG11", 0x10, "PAGE-UP")        -- 3/4 FILTER ENVELOPE
snap(t, "FILTER-ENV"); t = t + 0.5
t = note(t, "FILTER-BASE")
-- sweep the filter-EG ATK column: on p171 3/4 layout, ATK likely PART3-column too
t = press(t, ":cpanel:CPC_SEG8", 0x01, "F-ATK up-hold", 6.0)
snap(t, "FILTER-ATKMAX"); t = t + 0.5
t = note(t, "FILTER-ATKMAX")
at(t + 1.0, "exit", function() log("ENV11 DONE"); mac:exit() end)

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
log("env11 armed")
