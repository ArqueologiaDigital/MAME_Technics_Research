-- voicelife_probe.lua -- KN5000 VOICE LIFECYCLE capture.
-- Taps every SubCPU access to the IC303 register port (0x100000 address latch /
-- 0x100002 data) plus the status reads, around one held C4 key press.
local S   = os.getenv("VLDIR") or "."
local mac = manager.machine
local sub = mac.devices[":subcpu"]
local sp  = sub.spaces["program"]

local T_PRESS   = tonumber(os.getenv("VL_PRESS") or "12.0")
local T_RELEASE = tonumber(os.getenv("VL_REL")   or "14.0")
local T_END     = tonumber(os.getenv("VL_END")   or "17.0")
local T_START   = T_PRESS - 0.5

local f = io.open(S .. "/voicelife_trace.txt", "w")
local latch = 0
local n = 0

local function now()
  local t = mac.time
  return t.seconds + t.attoseconds / 1e18
end

_G._vl_wtap = sp:install_write_tap(0x100000, 0x100003, "vlw", function(off, data, mask)
  local t = now()
  if off == 0x100000 or off == 0x100001 then
    latch = data & 0xFFFF
    if t >= T_START and t <= T_END and n < 400000 then
      n = n + 1
      f:write(string.format("%.6f A %04X\n", t, latch))
    end
  else
    if t >= T_START and t <= T_END and n < 400000 then
      n = n + 1
      f:write(string.format("%.6f W %04X %04X\n", t, latch, data & 0xFFFF))
    end
  end
  return nil
end)

_G._vl_rtap = sp:install_read_tap(0x100000, 0x100003, "vlr", function(off, data, mask)
  local t = now()
  if t >= T_START and t <= T_END and n < 400000 then
    n = n + 1
    f:write(string.format("%.6f R %04X %04X @%06X\n", t, latch, data & 0xFFFF, off))
  end
  return nil
end)

local st = 0
emu.register_periodic(function()
  local t = now()
  if st == 0 and t >= T_PRESS then
    st = 1
    local p = mac.ioport.ports[":KEY2"]
    for _, fl in pairs(p.fields) do if fl.mask == 0x001 then fl:set_value(1) end end
    f:write(string.format("%.6f # PRESS C4\n", t))
  elseif st == 1 and t >= T_RELEASE then
    st = 2
    local p = mac.ioport.ports[":KEY2"]
    for _, fl in pairs(p.fields) do if fl.mask == 0x001 then fl:clear_value() end end
    f:write(string.format("%.6f # RELEASE C4\n", t))
  elseif st == 2 and t >= T_END + 0.2 then
    st = 3
    f:write(string.format("%.6f # END n=%d\n", t, n))
    f:close()
    emu.print_error("VOICELIFE DONE n=" .. n)
    mac:exit()
  end
end)
emu.print_error("voicelife_probe armed")
