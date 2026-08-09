-- measure_repaint.lua -- is the 191 ms/page sweep rate set by the firmware's
-- auto-repeat TIMER or by how long one full repaint takes?
--
-- The viewer re-reads every displayed byte on every repaint, so a read tap on
-- ONE inspected byte timestamps every repaint.  The byte at 0x48400000 is 0xDC
-- (>= 0x20), so per repaint it is read exactly 5 times: 2 in the hex loop
-- (0x48487B8C, 0x48487B97) and 3 in the ASCII loop (0x48487C5A, 0x48487C67,
-- 0x48487C6C).
--
-- Phase 1 (idle, no button):  gives the MT_SeleDraw repaint period, which the
--   code sets to 0x78 app-timer ticks -> the app tick in milliseconds.
-- Phase 2 (page-advance held): gives the repaint burst length and spacing while
--   sweeping.

local M     = manager.machine
local ports = M.ioport.ports
local sp    = M.devices[":maincpu"].spaces["program"]

local ADDR_SLOT0 = 0x500012EC
local HELD_UP, HELD_DN, HELD_BOTH = 0x50021FD8, 0x50021FDC, 0x50021FE0
local WATCH = 0x48400000

local COL = {
  [1] = {"CPC_SEG5", 0x10, 0x20}, [4] = {"CPC_SEG8", 0x04, 0x08},
  [5] = {"CPC_SEG8", 0x10, 0x20}, [8] = {"CPC_SEG9", 0x04, 0x08},
}
local ADV_PORT, ADV_MASK = "CPC_SEG8", 0x40

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

local phase, pi, tmark = "boot", 0, 0
TAPPING = false

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
    elseif t - tmark > 10 then phase = "press" end
  elseif phase == "settle" then
    if t - tmark > 3 then
      log(string.format("held-accumulator = %08X", u32(HELD_BOTH))); pi = 0; phase = "rel"
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
      sp:write_u32(ADDR_SLOT0, WATCH)
      tmark = t; phase = "park"
    end
  elseif phase == "park" then
    if t - tmark > 1.5 then
      log("TAP ON (idle phase)"); TAPPING = "idle"; tmark = t; phase = "idle"
    end
  elseif phase == "idle" then
    if t - tmark > 25.0 then
      TAPPING = false
      local f = findf(ADV_PORT, ADV_MASK); if f then f:set_value(1) end
      log("HOLD page-advance"); tmark = t; phase = "warm"
    end
  elseif phase == "warm" then
    if t - tmark > 1.0 then log("TAP ON (sweep phase)"); TAPPING = "sweep"; tmark = t; phase = "sweep" end
  elseif phase == "sweep" then
    if t - tmark > 5.0 then
      TAPPING = false
      local f = findf(ADV_PORT, ADV_MASK); if f then f:set_value(0) end
      log(string.format("done, addr = %08X", u32(ADDR_SLOT0)))
      log("ALL DONE"); M:exit()
    end
  end
end)

-- the taps must live in globals or the GC eats them.  Read taps are word
-- granular, so tap the first word of row 0 and the last word of row 15: the
-- gap between them is one full repaint, the gap between successive row-0
-- bursts is the repaint period.
TAP_FIRST = sp:install_read_tap(WATCH, WATCH + 3, "row0", function(offset, data, mask)
  if TAPPING then emu.print_error(string.format("RD %s FIRST %.6f", TAPPING, M.time:as_double())) end
  return data
end)
TAP_LAST = sp:install_read_tap(WATCH + 0xFC, WATCH + 0xFF, "row15", function(offset, data, mask)
  if TAPPING then emu.print_error(string.format("RD %s LAST %.6f", TAPPING, M.time:as_double())) end
  return data
end)
