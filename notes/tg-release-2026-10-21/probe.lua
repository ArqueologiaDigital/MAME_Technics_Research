-- probe.lua -- the release probe (README.md here). rig-machine: kn7000 (-bios v13, program 893), -midiin1 probe.mid
--
-- QUESTION IT SERVES: what does the firmware write to the tone generators when a note ends, and what does the
-- emulated tone generator do with it? It logs:
--   TR_OUT/tgw.txt    every TG register write from TR_FROM on, except the 0xFC0x idle refresh:
--                     "t tg addr data pc"; a write to any other port of the window (+4, +6, ... +0x1E) as
--                     "t tg +OFF data pc"  (tg 0 = 0x98040000, 1 = 0x98050000; addr = the latched address halfword;
--                     voice = tg<<6 | addr bits 9:4, register = addr bits 3:0, plane = addr bits 15:10)
--   TR_OUT/tgr.txt    every read of the data port (+2) from TR_FROM on: "t tg addr value pc", addr the latched address
--   TR_OUT/voices.txt every 0.05 s, each voice whose envelope is above zero: "t v gate stage mode env"
--                     (the tonegen's own save items m_gate, m_stage, m_mode, m_env; stage 3 = release)
--   TR_OUT/take.txt   the REVERB state, the keybed presses, the end
-- It presses REVERB off at 27 s (as notes/listen-2026-10-21/midi_take.lua does) so the dry sound is heard, and
-- plays the keybed note C4 (KEYS1 mask 0x0100, key index 0x18) from 32.0 to 33.5 s.
local M = manager.machine
local OUT = assert(os.getenv("TR_OUT"), "set TR_OUT")
local FROM = tonumber(os.getenv("TR_FROM") or "29")
local TEND = tonumber(os.getenv("TR_END") or "79")
local sp = M.devices[":maincpu"].spaces["program"]
local cpu = M.devices[":maincpu"]
local PCS = cpu.state["PC"] or cpu.state["CURPC"]
local log = assert(io.open(OUT .. "/take.txt", "w"))
local tgw = assert(io.open(OUT .. "/tgw.txt", "w"))
local vox = assert(io.open(OUT .. "/voices.txt", "w"))
local function now() return M.time:as_double() end
local function W(fmt, ...) log:write(string.format(fmt, ...) .. "\n"); log:flush() end
local function field(port, mask)
  local p = M.ioport.ports[":cpanel:" .. port] or M.ioport.ports[":" .. port]
  for _, f in pairs(p.fields) do if f.mask == mask then return f end end
  error("no field " .. port .. " " .. mask)
end
local REV = field("CPR_SEG3", 0x04)
local KEY = field("KEYS1", 0x0100)
local function led(n) return math.floor(M.output:get_value(n) or 0) end

-- TG write log. The address halfword is latched at +0, the data at +2 (one 32-bit bus lane each, little-endian).
local addr = { [0] = 0, [1] = 0 }
local function lanes(tg, base)
  return function(offset, data, mask)
    for lane = 0, 1 do
      local m = (mask >> (16 * lane)) & 0xFFFF
      if m ~= 0 then
        local a = (offset & ~3) + 2 * lane - base
        local d = (data >> (16 * lane)) & 0xFFFF
        if a == 0 then addr[tg] = d
        elseif a == 2 then
          if (addr[tg] & 0xFF00) ~= 0xFC00 and now() >= FROM then
            tgw:write(string.format("%.6f %d %04X %04X %08X\n", now(), tg, addr[tg], d, PCS.value))
          end
        elseif now() >= FROM and not (tg == 1 and (a == 0x0C or a == 0x0E)) then   -- other ports (not the SD SPI at 0x9805000C/E)
          tgw:write(string.format("%.6f %d +%02X %04X %08X\n", now(), tg, a, d, PCS.value))
        end
      end
    end
  end
end
_G.TR_T0 = sp:install_write_tap(0x98040000, 0x9804001F, "tg0", lanes(0, 0x98040000))
_G.TR_T1 = sp:install_write_tap(0x98050000, 0x9805001F, "tg1", lanes(1, 0x98050000))
-- the firmware's reads of the data port (the status sweep): "t tg addr value pc", addr = the latched address
local tgr = assert(io.open(OUT .. "/tgr.txt", "w"))
local function rd(tg)
  return function(offset, data, mask)
    if now() >= FROM and ((mask >> 16) & 0xFFFF) ~= 0 then
      tgr:write(string.format("%.6f %d %04X %04X %08X\n", now(), tg, addr[tg], (data >> 16) & 0xFFFF, PCS.value))
    end
  end
end
_G.TR_R0 = sp:install_read_tap(0x98040000, 0x98040003, "tg0r", rd(0))
_G.TR_R1 = sp:install_read_tap(0x98050000, 0x98050003, "tg1r", rd(1))

-- the tone generator's own voice state
local TG = M.devices[":tonegen"]
-- device.items is keyed "<index>/<name>" (e.g. "0/m_env"): find each by its name
local function item(name)
  for k, i in pairs(TG.items) do if k:match("/" .. name .. "$") or k == name then return emu.item(i) end end
  error("no save item " .. name)
end
local gate, stage, mode, env = item("m_gate"), item("m_stage"), item("m_mode"), item("m_env")
local function dbl(bits) return (string.unpack("<d", string.pack("<i8", bits))) end
local nextv = FROM
local function voices(t)
  for v = 0, 127 do
    local e = dbl(env:read(v))
    if e > 0 then
      vox:write(string.format("%.3f %3d %d %d %d %.5f\n", t, v, gate:read(v), stage:read(v), mode:read(v), e))
    end
  end
end

local steps = {
  { 26.5, function() W("t=%.3f before reverb_led=%d", now(), led("cpr_led27")) end },
  { 27.0, function() REV:set_value(1) end },
  { 27.3, function() REV:set_value(0) end },
  { 28.5, function() W("t=%.3f after the REVERB press reverb_led=%d", now(), led("cpr_led27")) end },
  { 32.0, function() KEY:set_value(1); W("t=%.3f keybed C4 down", now()) end },
  { 33.5, function() KEY:set_value(0); W("t=%.3f keybed C4 up", now()) end },
  { TEND, function() W("t=%.3f end", now()); log:close(); tgw:close(); tgr:close(); vox:close(); M:exit() end },
}
local nexts = 1
W("installed: TR_FROM=%.1f TR_END=%.1f", FROM, TEND)
_G.TR = emu.add_machine_frame_notifier(function()
  local t = now()
  while nexts <= #steps and t >= steps[nexts][1] do steps[nexts][2](); nexts = nexts + 1 end
  if t >= nextv and nexts <= #steps then voices(t); nextv = nextv + 0.05 end
end)
