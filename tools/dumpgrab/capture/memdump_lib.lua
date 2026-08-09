-- memdump_lib.lua -- shared KN7000 MEMORY DUMP driving primitives for MAME Lua scripts.
--
-- Loaded with dofile() by the capture/probe scripts. Everything it needs comes from
-- environment variables so the same file works from any cwd:
--   DG_OUT   log file path (default /tmp/dg.log)
--
-- Facts this encodes (all from notes/FINDINGS-kn7000-debug-screens.md, re-verified here):
--   * chord to open MEMORY DUMP = UP+DOWN held together on balance columns 1,4,5,8
--     (the firmware compares the both-held accumulator at 0x50021FE0 against exactly 0x99)
--   * the CP-serial HLE delivers ONE PANEL SEGMENT PER UPDATE, so multi-segment chords must
--     be pressed (and released) one segment at a time, waiting for the accumulator to move
--   * viewer address slots: u32 at 0x500012EC + 4*slot, slot selector u16 at 0x5006B524
--   * balance column i (1..8) steps the address by +/-(1 << (4*(8-i)));
--     column 6 = +/-0x100 = exactly ONE 256-byte PAGE  <-- the "orange button"

local M = {}

----------------------------------------------------------------- logging
M.logf = io.open(os.getenv("DG_OUT") or "/tmp/dg.log", "w")
function M.LOG(s)
  emu.print_info(s)
  if M.logf then M.logf:write(s .. "\n"); M.logf:flush() end
end

----------------------------------------------------------------- machine handles
M.mach = manager.machine
M.cpu  = M.mach.devices[":maincpu"]
M.prog = M.cpu.spaces["program"]
M.ioc  = M.mach.ioport

----------------------------------------------------------------- firmware cells
M.HELD_UP   = 0x50021FD8
M.HELD_DN   = 0x50021FDC
M.HELD_BOTH = 0x50021FE0
M.ADR_BASE  = 0x500012EC   -- +4*slot
M.SLOT      = 0x5006B524   -- u16
M.LCDFB     = 0x9CE00000   -- firmware composited RGB565 plane, 640x240

-- balance/mixer column N -> {port, up mask, down mask}.  Ports live under :cpanel:.
M.COL = {
  [1]={"CPC_SEG5",0x10,0x20},  [2]={"CPC_SEG5",0x40,0x80},
  [3]={"CPC_SEG8",0x01,0x02},  [4]={"CPC_SEG8",0x04,0x08},
  [5]={"CPC_SEG8",0x10,0x20},  [6]={"CPC_SEG8",0x40,0x80},
  [7]={"CPC_SEG9",0x01,0x02},  [8]={"CPC_SEG9",0x04,0x08},
  [9]={"CPC_SEG9",0x10,0x20},  [10]={"CPC_SEG9",0x40,0x80},
  [11]={"CPC_SEG10",0x01,0x02},[12]={"CPC_SEG10",0x04,0x08},
  [13]={"CPC_SEG10",0x10,0x20},[14]={"CPC_SEG10",0x40,0x80},
  [15]={"CPC_SEG11",0x01,0x02},[16]={"CPC_SEG11",0x04,0x08},
}
M.EXIT_BTN = {"CPC_SEG11", 0x80}

----------------------------------------------------------------- button helpers
function M.setbtn(p, mk, v)
  local port = M.ioc.ports[":cpanel:" .. p]
  if not port then M.LOG("!! no port :cpanel:" .. p); return false end
  for _, f in pairs(port.fields) do
    if f.mask == mk then f:set_value(v); return true end
  end
  M.LOG(("!! no field %s mask %02X"):format(p, mk))
  return false
end

function M.setmask(p, mask, v)      -- press/release every single-bit field inside mask
  local port = M.ioc.ports[":cpanel:" .. p]
  if not port then M.LOG("!! no port :cpanel:" .. p); return false end
  for _, f in pairs(port.fields) do
    if (f.mask & mask) ~= 0 and (f.mask & (f.mask - 1)) == 0 then f:set_value(v) end
  end
  return true
end

----------------------------------------------------------------- state reads
function M.slot()      return M.prog:read_u16(M.SLOT) end
function M.addr(slot)  return M.prog:read_u32(M.ADR_BASE + 4 * (slot or M.slot())) end
function M.both()      return M.prog:read_u32(M.HELD_BOTH) end

function M.lcdhash()   -- cheap sparse hash of the firmware's composited plane
  local h = 5381
  for i = 0, 153599, 257 do h = ((h * 33) + M.prog:read_u32(M.LCDFB + i * 4)) & 0xffffffff end
  return h
end

----------------------------------------------------------------- coroutine scheduler
M.frame = 0
local co = nil
function M.run(main)
  co = coroutine.create(main)
  DG_NOTIFIER = emu.add_machine_frame_notifier(function()   -- MUST be a global: GC kills locals
    M.frame = M.frame + 1
    if M.onframe then M.onframe(M.frame) end
    if co and coroutine.status(co) ~= "dead" then
      local ok, err = coroutine.resume(co)
      if not ok then M.LOG("LUA ERROR: " .. tostring(err)); co = nil end
    end
  end)
end
function M.waitf(n) for _ = 1, (n or 1) do coroutine.yield() end end
function M.waituntil(pred, maxf)
  for _ = 1, (maxf or 600) do
    if pred() then return true end
    coroutine.yield()
  end
  return false
end

----------------------------------------------------------------- reach MEMORY DUMP
-- Presses UP+DOWN on columns 1,4,5,8 -- three panel segments, one at a time, each confirmed
-- by watching the both-held accumulator. Returns true when it reads 0x99.
M.CHORD_SEGS = {
  {"CPC_SEG5", 0x30, 0x01},   -- col 1            -> accumulator bit 0
  {"CPC_SEG8", 0x3C, 0x19},   -- cols 4 and 5     -> bits 3,4
  {"CPC_SEG9", 0x0C, 0x99},   -- col 8            -> bit 7   (target 0x99)
}
function M.open_memdump(settle)
  settle = settle or 60
  for _, s in ipairs(M.CHORD_SEGS) do
    M.setmask(s[1], s[2], 1)
    local ok = M.waituntil(function() return M.both() == s[3] end, 240)
    M.LOG(("  chord seg %s %02X -> both=%08X %s"):format(s[1], s[2], M.both(), ok and "" or "(TIMEOUT)"))
    M.waitf(10)
  end
  local opened = (M.both() == 0x99)
  M.waitf(settle)
  -- release, again one segment at a time, and confirm the accumulator drains
  for i = #M.CHORD_SEGS, 1, -1 do
    local s = M.CHORD_SEGS[i]
    M.setmask(s[1], s[2], 0)
    M.waitf(20)
  end
  M.waituntil(function() return M.both() == 0 end, 240)
  M.LOG(("  chord released, both=%08X"):format(M.both()))
  M.waitf(30)
  return opened
end

----------------------------------------------------------------- one control press
-- A press is a level change on a panel segment; the CP-serial HLE needs the level to be
-- observed by the firmware's 250 Hz scan, hence a minimum hold. hold/gap are in FRAMES (60 Hz).
function M.tap(col, dir, hold, gap)
  local c = M.COL[col]
  local mk = (dir > 0) and c[2] or c[3]
  M.setbtn(c[1], mk, 1)
  M.waitf(hold or 20)
  M.setbtn(c[1], mk, 0)
  M.waitf(gap or 12)
end

----------------------------------------------------------------- dial an address
-- Closed loop: read the live slot cell, take the signed 32-bit difference to the target,
-- press the balance column whose weight is the top nonzero nibble of |delta|. Converges in
-- at most 8 presses per nibble. Column i has weight 1 << (4*(8-i)).
function M.dial_to(target, hold, gap, maxpress)
  maxpress = maxpress or 200
  local presses = 0
  while presses < maxpress do
    local cur = M.addr()
    if cur == target then return true, presses end
    local d = (target - cur) & 0xffffffff
    local sd = (d >= 0x80000000) and (d - 0x100000000) or d
    local mag = (sd < 0) and -sd or sd
    local n = 0                                   -- nibble index 0..7
    while (mag >> ((n + 1) * 4)) ~= 0 do n = n + 1 end
    local col = 8 - n                             -- col 8 = nibble 0
    M.tap(col, (sd > 0) and 1 or -1, hold, gap)
    presses = presses + 1
  end
  return M.addr() == target, presses
end

return M
