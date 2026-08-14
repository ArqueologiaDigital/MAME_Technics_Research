-- env5.lua: why is the TG quiet? Probe gate 0x500ce380, FIFO polling (0x98050004 reads),
-- idle-refresh counts, and a C4 press at t=30.
local mac = manager.machine
local function log(s) emu.print_error(s) end
local cpu  = mac.devices[":maincpu"]
local prog = cpu.spaces["program"]

local tg_addr = {0,0}
local nidle, nreal = 0, 0
local last = {}
local function tap(base, idx, label)
  prog:install_write_tap(base, base+3, "tgenv"..idx, function(off, data, mask)
    if (mask & 0x0000ffff) ~= 0 then tg_addr[idx] = data & 0xffff end
    if (mask & 0xffff0000) ~= 0 then
      local a = tg_addr[idx]; local d = (data>>16) & 0xffff
      if (a & 0xff00) == 0xfc00 then nidle = nidle + 1
      else nreal = nreal + 1
        if #last < 400 then last[#last+1] = ("%s%03X=%04X"):format(label, a, d) end
      end
    end
    return nil
  end)
end
_G.envtap1 = tap(0x98040000, 1, "M")
_G.envtap2 = tap(0x98050000, 2, "S")

local nfifo = 0
_G.fifotap = prog:install_read_tap(0x98050004, 0x98050007, "fifor", function(off, data, mask)
  nfifo = nfifo + 1
  return nil
end)

local function stat(tag)
  local gate = prog:read_u8(0x500ce380)
  log(("STAT %s: gate500ce380=%02X idle=%d real=%d fiforeads=%d"):format(tag, gate, nidle, nreal, nfifo))
end

local acts = {}
local function at(t, desc, fn) acts[#acts+1] = {t=t, desc=desc, fn=fn} end
local function key(t, v)
  at(t, v==1 and "C4 down" or "C4 up", function()
    for _, f in pairs(mac.ioport.ports[":KEYS1"].fields) do
      if f.mask == 0x0100 then if v==1 then f:set_value(1) else f:clear_value() end end
    end
  end)
end

at(24.0, "s1", function() stat("t24") end)
at(25.0, "s2", function() stat("t25") end)
key(26.0, 1)
key(27.5, 0)
at(29.0, "s3", function() stat("t29-postkey") end)
key(31.0, 1)
key(32.5, 0)
at(34.0, "s4", function() stat("t34-postkey2"); log("LASTW: "..table.concat(last, " ", math.max(1,#last-60))) end)
at(35.0, "exit", function() mac:exit() end)

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
log("env5 armed")
