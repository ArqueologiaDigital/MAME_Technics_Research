-- env6.lua: does a Lua set_value C4 press enter the keybed FIFO? Log distinct values
-- read by the firmware from 0x98050004 around the press, and the port live value.
local mac = manager.machine
local function log(s) emu.print_error(s) end
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]

local vals = {}
local nfifo = 0
_G.fifotap = prog:install_read_tap(0x98050004, 0x98050007, "fifor", function(off, data, mask)
  nfifo = nfifo + 1
  local key = ("%08X&%08X"):format(data, mask)
  vals[key] = (vals[key] or 0) + 1
  return nil
end)

local function dumpvals(tag)
  local ks = {}
  for k, n in pairs(vals) do ks[#ks+1] = ("%s x%d"):format(k, n) end
  table.sort(ks)
  log(("VALS %s (reads=%d): %s"):format(tag, nfifo, table.concat(ks, " | ")))
  vals = {}
end

local acts = {}
local function at(t, desc, fn) acts[#acts+1] = {t=t, desc=desc, fn=fn} end

at(24.0, "clear", function() vals = {}; nfifo = 0 end)
at(25.0, "pre", function() dumpvals("PRE") end)
at(26.0, "C4 down", function()
  local p = mac.ioport.ports[":KEYS1"]
  for _, f in pairs(p.fields) do if f.mask == 0x0100 then f:set_value(1) end end
end)
at(26.5, "port val", function()
  local p = mac.ioport.ports[":KEYS1"]
  log(("PORTVAL during press = %04X"):format(p:read()))
end)
at(27.5, "C4 up", function()
  local p = mac.ioport.ports[":KEYS1"]
  for _, f in pairs(p.fields) do if f.mask == 0x0100 then f:clear_value() end end
end)
at(29.0, "post", function() dumpvals("POST-PRESS") end)
at(30.0, "exit", function() mac:exit() end)

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
log("env6 armed")
