-- env8.lua: does the SOUND EDIT ENVELOPE screen audition the keybed?
-- Navigate there, install FRESH taps, press C4 (count idle+real), then EXIT home and
-- press C4 again as a control in the same session.
local mac = manager.machine
local function log(s) emu.print_error(s) end
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]

local tg_addr = {0,0}
local nidle, nreal = 0, 0
local cap = {}
local function mktap(base, idx, label, name)
  return prog:install_write_tap(base, base+3, name, function(off, data, mask)
    if (mask & 0x0000ffff) ~= 0 then tg_addr[idx] = data & 0xffff end
    if (mask & 0xffff0000) ~= 0 then
      local a = tg_addr[idx]; local d = (data>>16) & 0xffff
      if (a & 0xff00) == 0xfc00 then nidle = nidle + 1
      else nreal = nreal + 1
        if #cap < 120 then cap[#cap+1] = ("%s%03X=%04X"):format(label, a, d) end
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
snap (31.0, "EDIT-SCREEN")
at(32.0, "taps", function()
  _G.t1 = mktap(0x98040000, 1, "M", "tgA")
  _G.t2 = mktap(0x98050000, 2, "S", "tgB")
  nidle = 0; nreal = 0; cap = {}
end)
press(33.0, ":KEYS1", 0x0100, "C4-on-edit", 1.2)
at(36.0, "post", function()
  log(("EDIT-SCREEN C4: idle=%d real=%d"):format(nidle, nreal))
  log("CAP: "..table.concat(cap, " "))
end)
press(37.0, ":cpanel:CPC_SEG11", 0x80, "EXIT")
snap (39.0, "AFTER-EXIT")
at(39.5, "clear", function() nidle = 0; nreal = 0; cap = {} end)
press(40.0, ":KEYS1", 0x0100, "C4-home", 1.2)
at(43.0, "post2", function()
  log(("HOME C4: idle=%d real=%d"):format(nidle, nreal))
  log("CAP: "..table.concat(cap, " "))
end)
at(44.0, "exit", function() mac:exit() end)

local i = 1
emu.register_periodic(function()
  local t = mac.time.seconds + mac.time.attoseconds/1e18
  while i <= #acts and t >= acts[i].t do
    local a = acts[i]; i = i + 1
    local ok, err = pcall(a.fn)
    if not ok then log("ERR "..a.desc..": "..tostring(err))
    elseif a.desc ~= "" then log(("[%5.1f] %s"):format(t, a.desc)) end
  end
end)
log("env8 armed")
