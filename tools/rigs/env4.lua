-- env4.lua: keypress diagnostic. Home screen, no navigation.
local mac = manager.machine
local function log(s) emu.print_error(s) end
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]

local tg_addr = {0,0}
local nidle, nreal = 0, 0
local cap = {}
local function tap(base, idx, label)
  prog:install_write_tap(base, base+3, "tgenv"..idx, function(off, data, mask)
    if (mask & 0x0000ffff) ~= 0 then tg_addr[idx] = data & 0xffff end
    if (mask & 0xffff0000) ~= 0 then
      local a = tg_addr[idx]; local d = (data>>16) & 0xffff
      if (a & 0xff00) == 0xfc00 then nidle = nidle + 1
      else nreal = nreal + 1
        if #cap < 150 then cap[#cap+1] = ("%s%03X=%04X"):format(label, a, d) end
      end
    end
    return nil
  end)
end
_G.envtap1 = tap(0x98040000, 1, "M")
_G.envtap2 = tap(0x98050000, 2, "S")

local acts = {}
local function at(t, desc, fn) acts[#acts+1] = {t=t, desc=desc, fn=fn} end

at(20.0, "dump-fields", function()
  local p = mac.ioport.ports[":KEYS1"]
  if not p then log("NOPORT :KEYS1") return end
  for _, f in pairs(p.fields) do
    log(("FIELD mask=%04X name='%s' enabled=%s type=%s"):format(
      f.mask, tostring(f.name), tostring(f.enabled), tostring(f.type)))
  end
end)
at(21.0, "tapstat0", function() log(("TAPSTAT idle=%d real=%d"):format(nidle, nreal)) end)
at(22.0, "C4-down", function()
  local p = mac.ioport.ports[":KEYS1"]
  for _, f in pairs(p.fields) do
    if f.mask == 0x0100 then log("pressing field '"..tostring(f.name).."'"); f:set_value(1) end
  end
end)
at(23.5, "C4-up", function()
  local p = mac.ioport.ports[":KEYS1"]
  for _, f in pairs(p.fields) do if f.mask == 0x0100 then f:clear_value() end end
end)
at(25.0, "result", function()
  log(("TAPSTAT idle=%d real=%d"):format(nidle, nreal))
  log("CAP: "..table.concat(cap, " "))
end)
at(26.0, "exit", function() mac:exit() end)

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
log("env4 armed")
