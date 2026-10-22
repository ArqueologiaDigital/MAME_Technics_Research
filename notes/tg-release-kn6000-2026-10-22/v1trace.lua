-- v1trace.lua -- every write to the KN6000 TG window 0x98050000-3 between 37.0 and 37.06 s, with voice 1's state (m_gate,
-- m_stage, m_env) as the tonegen last updated it. QUESTION IT SERVED: what released voice 1 about 10 ms after its note-on?
-- Answer: nothing in this window -- which pointed at a write outside it (0x98040002, the "Device-A" byte pair; README.md).
-- Run with TR_OUT set and -midiin1 probe.mid; it exits at 37.1 s.
local M = manager.machine
local OUT = os.getenv("TR_OUT")
local sp = M.devices[":maincpu"].spaces["program"]
local f = assert(io.open(OUT .. "/v1.txt", "w"))
local TG = M.devices[":tonegen"]
local function item(name)
  for k, i in pairs(TG.items) do if k:match("/" .. name .. "$") then return emu.item(i) end end
end
local gate, stage, env = item("m_gate"), item("m_stage"), item("m_env")
local function dbl(bits) return (string.unpack("<d", string.pack("<i8", bits))) end
local addr = 0
_G.T = sp:install_write_tap(0x98050000, 0x98050003, "t", function(o, d, m)
  local t = M.time:as_double()
  for lane = 0, 1 do
    if ((m >> (16 * lane)) & 0xFFFF) ~= 0 then
      local x = (d >> (16 * lane)) & 0xFFFF
      if lane == 0 then addr = x
      elseif t >= 37.0 and t < 37.06 then
        f:write(string.format("%.6f %04X %04X | v1 g%d s%d e%.4f\n", t, addr, x, gate:read(1), stage:read(1), dbl(env:read(1))))
      end
    end
  end
  if t > 37.1 then f:close(); M:exit() end
end)
