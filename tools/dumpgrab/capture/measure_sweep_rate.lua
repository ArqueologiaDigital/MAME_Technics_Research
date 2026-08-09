-- measure_sweep_rate.lua -- how fast does HOLDING the page-advance button sweep?
--
-- Opens the hidden MEMORY DUMP viewer with the 1/4/5/8 chord, parks ADR0 on a
-- safe ROM page, then PRESSES AND HOLDS "MUTE UP 6" (CPC_SEG8 bit 0x40) -- the
-- 0x100 hex digit, i.e. exactly one 256-byte page per auto-repeat -- and logs
-- the inspected address once per emulated video frame.
--
-- Output on stderr:
--   FRAME <n> <emulated seconds> <ADR0>
-- one line per frame while the button is held.  Post-processing turns that into
-- pages/second and the per-frame page delta histogram (the number that decides
-- whether a 60 Hz capture can see every page).

local M     = manager.machine
local ports = M.ioport.ports
local sp    = M.devices[":maincpu"].spaces["program"]

local ADDR_SLOT0 = 0x500012EC
local HELD_UP, HELD_DN, HELD_BOTH = 0x50021FD8, 0x50021FDC, 0x50021FE0
local START_ADDR = 0x48400000            -- program flash base: safe, read-only
local HOLD_SECONDS = tonumber(os.getenv("HOLD_SECONDS") or "30")

local COL = {
  [1] = {"CPC_SEG5", 0x10, 0x20}, [4] = {"CPC_SEG8", 0x04, 0x08},
  [5] = {"CPC_SEG8", 0x10, 0x20}, [8] = {"CPC_SEG9", 0x04, 0x08},
}
local ADV_PORT, ADV_MASK = "CPC_SEG8", 0x40      -- MUTE UP 6 = the page advance

local function findf(tag, mask)
  local p = ports[":cpanel:" .. tag]
  if not p then return nil end
  for _, f in pairs(p.fields) do if f.mask == mask then return f end end
end
local function fld(c, w) return findf(COL[c][1], COL[c][1 + w]) end
local function u32(a) return sp:read_u32(a) end
local function log(s) emu.print_error(string.format("[%7.2f] %s", M.time:as_double(), s)) end

local plan = {}
for _, c in ipairs({1, 4, 5, 8}) do plan[#plan + 1] = {c, 1}; plan[#plan + 1] = {c, 2} end

local phase, pi, tmark, frames = "boot", 0, 0, 0

emu.register_periodic(function()
  local t = M.time:as_double()

  if phase == "boot" then
    if t >= 24 then log("boot done; driving chord"); pi = 0; phase = "press" end

  elseif phase == "press" then
    pi = pi + 1
    if pi > #plan then phase = "settle"; tmark = t; return end
    local f = fld(plan[pi][1], plan[pi][2]); if f then f:set_value(1) end
    tmark = t; phase = "waitset"
  elseif phase == "waitset" then
    local c, w = plan[pi][1], plan[pi][2]
    local reg = (w == 1) and u32(HELD_UP) or u32(HELD_DN)
    if (reg & (1 << (c - 1))) ~= 0 then phase = "press"
    elseif t - tmark > 10 then log("TIMEOUT setting col " .. c); phase = "press" end

  elseif phase == "settle" then
    if t - tmark > 3 then
      log(string.format("held-accumulator = %08X (want 00000099)", u32(HELD_BOTH)))
      pi = 0; phase = "rel"
    end
  elseif phase == "rel" then
    pi = pi + 1
    if pi > #plan then tmark = t; phase = "opened"; return end
    local f = fld(plan[pi][1], plan[pi][2]); if f then f:set_value(0) end
    tmark = t; phase = "waitclr"
  elseif phase == "waitclr" then
    local c, w = plan[pi][1], plan[pi][2]
    local reg = (w == 1) and u32(HELD_UP) or u32(HELD_DN)
    if (reg & (1 << (c - 1))) == 0 then phase = "rel"
    elseif t - tmark > 10 then phase = "rel" end

  elseif phase == "opened" then
    if t - tmark > 2.0 then
      log(string.format("viewer slot0 address cell = %08X", u32(ADDR_SLOT0)))
      sp:write_u32(ADDR_SLOT0, START_ADDR)
      tmark = t; phase = "parked"
    end
  elseif phase == "parked" then
    if t - tmark > 1.0 then
      local f = findf(ADV_PORT, ADV_MASK)
      if not f then log("FATAL: no page-advance field"); M:exit(); return end
      f:set_value(1)
      log(string.format("HOLD page-advance (MUTE UP 6) from %08X", u32(ADDR_SLOT0)))
      tmark = t; phase = "hold"
    end
  elseif phase == "hold" then
    if t - tmark > HOLD_SECONDS then
      local f = findf(ADV_PORT, ADV_MASK); if f then f:set_value(0) end
      log(string.format("RELEASE at %08X after %.2f s", u32(ADDR_SLOT0), t - tmark))
      tmark = t; phase = "after"
    end
  elseif phase == "after" then
    if t - tmark > 2.0 then
      log(string.format("SETTLED %08X (drift after release)", u32(ADDR_SLOT0)))
      log("ALL DONE"); M:exit()
    end
  end
end)

-- NOTE: the notifier subscription must be held in a global or the Lua GC kills it.
FRAME_SUB = emu.add_machine_frame_notifier(function()
  if phase == "hold" or phase == "parked" or phase == "after" then
    frames = frames + 1
    emu.print_error(string.format("FRAME %d %.6f %08X",
      frames, M.time:as_double(), sp:read_u32(ADDR_SLOT0)))
  end
end)
