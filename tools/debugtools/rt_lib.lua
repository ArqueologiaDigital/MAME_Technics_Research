-- rt_lib.lua -- runtime-lane helpers on top of memdump_lib.lua (kn7000_mame 74a3457, copied here).
--
-- Environment: RT_DIR (this scripts dir), DG_OUT (log file).
-- Provides: boot settle, gate-byte patch, chord -> Panel Simulator -> DEBUG TOOLS, named button
-- presses, snapshots, and a one-line dump of the DEBUG MODE related RAM cells.

local L = dofile(os.getenv("RT_DIR") .. "/memdump_lib.lua")
local P = L.prog
local R = { L = L, P = P, LOG = L.LOG }

function R.hex(v, n) return string.format("%0" .. (n or 8) .. "X", v) end

function R.cstr(a, max)
  local s = ""
  for i = 0, (max or 16) - 1 do
    local c = P:read_u8(a + i)
    if c == 0 then break end
    s = s .. string.char(c)
  end
  return s
end

local function findfield(sub)
  for _, port in pairs(manager.machine.ioport.ports) do
    for name, field in pairs(port.fields) do
      if name:find(sub, 1, true) then return field, name end
    end
  end
  return nil
end

-- press a panel button by (unique) substring of its MAME field name
function R.press(sub, hold, gap)
  local f, nm = findfield(sub)
  if not f then L.LOG("NOTFOUND " .. sub); return false end
  L.LOG(("PRESS %s  t=%.2f"):format(nm, L.mach.time.seconds))
  f:set_value(1); L.waitf(hold or 20); f:set_value(0); L.waitf(gap or 120)
  return true
end

-- hold a button (by substring) for n frames
function R.hold(sub, n)
  local f, nm = findfield(sub)
  if not f then L.LOG("NOTFOUND " .. sub); return false end
  L.LOG(("HOLD %s for %d frames t=%.2f"):format(nm, n, L.mach.time.seconds))
  f:set_value(1); L.waitf(n); f:set_value(0); L.waitf(60)
  return true
end

local scr
for _, s in pairs(manager.machine.screens) do scr = s; break end
function R.snap(name) scr:snapshot(name); L.LOG("SNAP " .. name) end

-- mode/title "now" tables (GetModeNow 0x4842B309 -> u32 0x5000097C[ctx], GetTitleNow
-- 0x4842C982 -> u32 0x5000099C[ctx]); the ctx index comes from func_48414A4F, so print 4 slots
function R.screens()
  local m, t = {}, {}
  for i = 0, 3 do
    m[#m + 1] = R.hex(P:read_u32(0x5000097C + 4 * i))
    t[#t + 1] = R.hex(P:read_u32(0x5000099C + 4 * i))
  end
  return "modeNow[" .. table.concat(m, " ") .. "] titleNow[" .. table.concat(t, " ") .. "]"
end

-- the cells the static DEBUG MODE lane says change together (941 addresses)
function R.dm(tag)
  L.LOG(("[%s] t=%.2f DM(u32 0x5015080C)=%d sdpartFlag(u32 0x5006B5C8)=%d maskPtr(u32 0x500017C0)=%s "
     .. "apcrevFlag(u8 0x500019FC)=%d demo(u32 0x50082948)=%d enum(u32 0x500012C0)=%s %s lcdhash=%s"):format(
     tag, L.mach.time.seconds, P:read_u32(0x5015080C), P:read_u32(0x5006B5C8),
     R.hex(P:read_u32(0x500017C0)), P:read_u8(0x500019FC), P:read_u32(0x50082948),
     R.hex(P:read_u32(0x500012C0)), R.screens(), R.hex(L.lcdhash())))
end

function R.settle()
  local last, stable = -1, 0
  L.waituntil(function()
    if L.mach.time.seconds < 15 then return false end
    local h = L.lcdhash()
    if h == last then stable = stable + 1 else stable = 0; last = h end
    return stable >= 90
  end, 60 * 120)
  L.LOG(("boot settled t=%.2f"):format(L.mach.time.seconds))
end

-- patch the configuration byte 0x4840000F (file offset 0x0F of region :maincpu) to 0xFF
function R.patch_gate()
  local reg = manager.machine.memory.regions[":maincpu"]
  L.LOG("gate byte 0x4840000F before: " .. R.hex(P:read_u8(0x4840000F), 2))
  reg:write_u8(0x0F, 0xFF)
  L.LOG("gate byte 0x4840000F after:  " .. R.hex(P:read_u8(0x4840000F), 2))
end

-- chord 1/4/5/8 (UP+DOWN) -> with gate 0xFF: Panel Simulator 2.1; then LCDR5 -> DEBUG TOOLS
function R.to_debug_tools(prefix)
  local ok = L.open_memdump(90)
  L.LOG("chord 0x99 reached: " .. tostring(ok) .. "  " .. R.screens())
  L.waitf(120)
  R.snap(prefix .. "_panel_simulator.png")
  R.press("LCDR 5")
  L.waitf(120)
  R.snap(prefix .. "_debug_tools.png")
  R.dm(prefix .. " debug tools")
end

-- tap balance column col (1..16), dir +1 UP / -1 DOWN, using memdump_lib's column map
function R.tap(col, dir, hold, gap) L.tap(col, dir, hold or 20, gap or 60); L.waitf(30) end

return R
