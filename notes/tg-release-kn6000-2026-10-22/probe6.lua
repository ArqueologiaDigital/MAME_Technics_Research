-- probe6.lua -- the KN6000 version of ../tg-release-2026-10-21/probe.lua (README.md here). rig-machine: kn6000,
-- -midiin1 probe.mid (../tg-release-2026-10-21/gen_probe_mid.py).
--
-- QUESTION IT SERVES: does the KN6000 firmware poll its tone generator (IC213, one window at 0x98050000) for
-- voice status the way the KN7000's TgVoiceStatusSweep does, and what does it write when a note ends? It logs:
--   TR_OUT/tgw.txt    every TG register write from TR_FROM on, except the 0xFC0x addresses: "t addr data pc"
--                     (addr = the latched address halfword; voice = addr bits 9:4, register = bits 3:0)
--   TR_OUT/tgr.txt    every read of the data port 0x98050002 from TR_FROM on: "t addr value pc", addr = the
--                     latched address (the KN7000 sweep reads 0xFC08+g and 0xFC02|ch<<4)
--   TR_OUT/voices.txt every 0.05 s, each voice whose envelope is above zero: "t v gate stage mode env"
--                     (stage 3 = release)
local M = manager.machine
local OUT = assert(os.getenv("TR_OUT"), "set TR_OUT")
local FROM = tonumber(os.getenv("TR_FROM") or "29")
local TEND = tonumber(os.getenv("TR_END") or "79")
local sp = M.devices[":maincpu"].spaces["program"]
local cpu = M.devices[":maincpu"]
local PCS = cpu.state["PC"] or cpu.state["CURPC"]
local log = assert(io.open(OUT .. "/take.txt", "w"))
local tgw = assert(io.open(OUT .. "/tgw.txt", "w"))
local tgr = assert(io.open(OUT .. "/tgr.txt", "w"))
local vox = assert(io.open(OUT .. "/voices.txt", "w"))
local function now() return M.time:as_double() end
local function W(fmt, ...) log:write(string.format(fmt, ...) .. "\n"); log:flush() end

-- The address halfword is latched at +0, the data at +2 (one 32-bit bus lane each, little-endian).
local addr = 0
_G.TR_T1 = sp:install_write_tap(0x98050000, 0x98050003, "tg1", function(offset, data, mask)
  for lane = 0, 1 do
    if ((mask >> (16 * lane)) & 0xFFFF) ~= 0 then
      local d = (data >> (16 * lane)) & 0xFFFF
      if lane == 0 then addr = d
      elseif (addr & 0xFF00) ~= 0xFC00 and now() >= FROM then
        tgw:write(string.format("%.6f %04X %04X %08X\n", now(), addr, d, PCS.value))
      end
    end
  end
end)
_G.TR_R1 = sp:install_read_tap(0x98050000, 0x98050003, "tg1r", function(offset, data, mask)
  if now() >= FROM and ((mask >> 16) & 0xFFFF) ~= 0 then
    tgr:write(string.format("%.6f %04X %04X %08X\n", now(), addr, (data >> 16) & 0xFFFF, PCS.value))
  end
end)

local TG = M.devices[":tonegen"]
local function item(name)
  for k, i in pairs(TG.items) do if k:match("/" .. name .. "$") or k == name then return emu.item(i) end end
  error("no save item " .. name)
end
local gate, stage, mode, env = item("m_gate"), item("m_stage"), item("m_mode"), item("m_env")
local function dbl(bits) return (string.unpack("<d", string.pack("<i8", bits))) end
local nextv = FROM
local function voices(t)
  for v = 0, 63 do
    local e = dbl(env:read(v))
    if e > 0 then
      vox:write(string.format("%.3f %3d %d %d %d %.5f\n", t, v, gate:read(v), stage:read(v), mode:read(v), e))
    end
  end
end

W("installed: TR_FROM=%.1f TR_END=%.1f", FROM, TEND)
local done = false
_G.TR = emu.add_machine_frame_notifier(function()
  local t = now()
  if done then return end
  if t >= TEND then
    done = true
    W("t=%.3f end", t); log:close(); tgw:close(); tgr:close(); vox:close(); M:exit(); return
  end
  if t >= nextv then voices(t); nextv = nextv + 0.05 end
end)
