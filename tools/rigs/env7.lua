-- env7.lua: is the TG pipeline alive at all? Install FRESH write taps at t=25 (rule out
-- tap invalidation), press C4 at t=26, then DEMO at t=30 and count voice writes.
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
_G.t1 = mktap(0x98040000, 1, "M", "tgA")
_G.t2 = mktap(0x98050000, 2, "S", "tgB")

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

at(25.0, "fresh taps + clear", function()
  _G.t1 = mktap(0x98040000, 1, "M", "tgA2")
  _G.t2 = mktap(0x98050000, 2, "S", "tgB2")
  nidle = 0; nreal = 0; cap = {}
end)
press(26.0, ":KEYS1", 0x0100, "C4", 1.2)
at(29.0, "post-C4", function()
  log(("POST-C4: idle=%d real=%d"):format(nidle, nreal))
  log("CAP: "..table.concat(cap, " "))
  nidle = 0; nreal = 0; cap = {}
end)
press(30.0, ":cpanel:CPL_SEG6", 0x40, "DEMO")
at(36.0, "post-DEMO", function()
  log(("POST-DEMO: idle=%d real=%d"):format(nidle, nreal))
  log("CAP: "..table.concat(cap, " "))
end)
at(37.0, "exit", function() mac:exit() end)

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
log("env7 armed")
