-- voicelife_probe2.lua -- KN5000 voice ALLOCATION / reuse capture.
-- Logs, from power-on, every gate write (+0x000 group0/bank0) and every wave-select
-- write (+0x040), plus the status-bitmap reads, while playing a sequence of notes.
local S   = os.getenv("VLDIR") or "."
local mac = manager.machine
local sub = mac.devices[":subcpu"]
local sp  = sub.spaces["program"]

local f = io.open(S .. "/voicelife_alloc.txt", "w")
local latch = 0
local n = 0
local T_END = tonumber(os.getenv("VL_END") or "20.0")

local function now()
  local t = mac.time
  return t.seconds + t.attoseconds / 1e18
end

_G._vl2_w = sp:install_write_tap(0x100000, 0x100003, "vl2w", function(off, data, mask)
  if off == 0x100000 or off == 0x100001 then latch = data & 0xFFFF; return nil end
  local a = latch
  if a < 0x0080 or a == 0x0000 then           -- gate (+0x000) and wave select (+0x040)
    n = n + 1
    if n < 200000 then f:write(string.format("%.6f W %04X %04X\n", now(), a, data & 0xFFFF)) end
  end
  return nil
end)

local prev = {}
_G._vl2_r = sp:install_read_tap(0x100000, 0x100003, "vl2r", function(off, data, mask)
  local d = data & 0xFFFF
  if prev[latch] ~= d then
    prev[latch] = d
    n = n + 1
    if n < 200000 then f:write(string.format("%.6f R %04X %04X\n", now(), latch, d)) end
  end
  return nil
end)

-- press a sequence of single notes, then a 3-note chord
local seq = {
  {12.0, ":KEY2", 0x001, "C4"}, {12.4, ":KEY2", 0x001, nil},
  {13.0, ":KEY2", 0x004, "D4"}, {13.4, ":KEY2", 0x004, nil},
  {14.0, ":KEY2", 0x010, "E4"}, {14.4, ":KEY2", 0x010, nil},
  {15.0, ":KEY2", 0x020, "F4"}, {15.4, ":KEY2", 0x020, nil},
  {16.0, ":KEY2", 0x080, "G4"}, {16.4, ":KEY2", 0x080, nil},
  {17.0, ":KEY2", 0x001, "C4+"}, {17.0, ":KEY2", 0x010, "E4+"}, {17.0, ":KEY2", 0x080, "G4+"},
  {18.0, ":KEY2", 0x001, nil}, {18.0, ":KEY2", 0x010, nil}, {18.0, ":KEY2", 0x080, nil},
}
local i = 1
emu.register_periodic(function()
  local t = now()
  while i <= #seq and t >= seq[i][1] do
    local e = seq[i]; i = i + 1
    local p = mac.ioport.ports[e[2]]
    for _, fl in pairs(p.fields) do
      if fl.mask == e[3] then
        if e[4] then fl:set_value(1) else fl:clear_value() end
      end
    end
    f:write(string.format("%.6f # %s %s\n", t, e[4] and "PRESS" or "RELEASE", e[4] or string.format("%03X", e[3])))
  end
  if t >= T_END then
    f:write(string.format("%.6f # END n=%d\n", t, n))
    f:close()
    emu.print_error("VOICELIFE2 DONE n=" .. n)
    mac:exit()
  end
end)
emu.print_error("voicelife_probe2 armed")
