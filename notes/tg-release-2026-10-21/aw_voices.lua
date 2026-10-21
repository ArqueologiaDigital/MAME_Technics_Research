-- aw_voices.lua -- Another World's intro (../listen-2026-10-21/aw_intro.lua, run as it is) plus a count of the tone
-- generator's voices (README.md here). Run it with run_aw.sh: AWI_SCRIPT=<this file> run_aw.sh OUT tg wav.
-- QUESTION IT SERVES: does the game's music, played on the tone generator, leave notes hanging? Every emulated second
-- from 80 s on it writes AWI_OUT/voices.txt: "t sounding held oldest" -- the voices whose envelope is above zero, how
-- many of those are still keyed (m_gate), and the age in seconds of the oldest note still sounding (now - m_ton).
-- A hanging note keeps a voice sounding and keyed for good, so "oldest" grows with the clock.
local here = debug.getinfo(1, "S").source:match("^@(.*/)") or "./"
dofile(here .. "../listen-2026-10-21/aw_intro.lua")
local M = manager.machine
local TG = M.devices[":tonegen"]
local function item(name)
  for k, i in pairs(TG.items) do if k:match("/" .. name .. "$") or k == name then return emu.item(i) end end
  error("no save item " .. name)
end
local gate, env, ton = item("m_gate"), item("m_env"), item("m_ton")
local function dbl(bits) return (string.unpack("<d", string.pack("<i8", bits))) end
local out = assert(io.open(os.getenv("AWI_OUT") .. "/voices.txt", "w"))
local nexts = 80
AWV_TICK = emu.add_machine_frame_notifier(function()
  local t = M.time:as_double()
  if t < nexts then return end
  nexts = nexts + 1
  local n, held, oldest = 0, 0, 0.0
  for v = 0, 127 do
    if dbl(env:read(v)) > 0 then
      n = n + 1
      if gate:read(v) ~= 0 then held = held + 1 end
      oldest = math.max(oldest, t - dbl(ton:read(v)))
    end
  end
  out:write(string.format("%.1f %d %d %.1f\n", t, n, held, oldest)); out:flush()
end)
