-- probe_step.lua -- measure the KN7000 MEMORY DUMP page-advance ("orange button") timing.
-- Answers: which control advances a page, does HOLDING it auto-repeat, what is the minimum
-- reliable hold/gap, and therefore the maximum safe sweep rate in pages/second.
local DIR = os.getenv("DG_DIR") or "."
local L = dofile(DIR .. "/memdump_lib.lua")
local LOG = L.LOG

local function main()
  -- 1. boot settle -------------------------------------------------------------
  local last, stable = -1, 0
  L.waituntil(function()
    if L.mach.time.seconds < 15 then return false end
    local h = L.lcdhash()
    if h == last then stable = stable + 1 else stable = 0; last = h end
    return stable >= 90
  end, 3600)
  LOG(("BOOT settled t=%.2fs frame=%d hash=%08X"):format(L.mach.time.seconds, L.frame, L.lcdhash()))

  -- 2. open MEMORY DUMP --------------------------------------------------------
  local ok = L.open_memdump(60)
  LOG(("OPEN memdump=%s slot=%d ADR=%08X"):format(tostring(ok), L.slot(), L.addr()))
  if not ok then LOG("ABORT: chord did not fire"); L.mach:exit(); return end

  -- 3. identify the page-advance column ---------------------------------------
  -- Press UP once on each of columns 1..8 (undoing with DOWN) and record the delta.
  LOG("--- column weights (one UP tap each, then one DOWN tap to restore) ---")
  for col = 1, 8 do
    local a0 = L.addr()
    L.tap(col, 1, 20, 20)
    local a1 = L.addr()
    L.tap(col, -1, 20, 20)
    local a2 = L.addr()
    LOG(("  col %2d: %08X -> %08X  delta=%+d (0x%X)   restore=%08X %s"):format(
        col, a0, a1, (a1 - a0), (a1 - a0) & 0xffffffff, a2, (a2 == a0) and "ok" or "MISMATCH"))
  end

  -- park somewhere in program flash so repaints stay in ROM
  L.dial_to(0x48400000, 20, 20)
  LOG(("PARKED ADR=%08X"):format(L.addr()))

  -- 4. does HOLDING the orange button auto-repeat? -----------------------------
  LOG("--- hold test: column 6 UP held for 900 frames (15 s) ---")
  local c = L.COL[6]
  local a0 = L.addr()
  local trans = {}      -- {frame_offset, addr}
  local prev = a0
  L.setbtn(c[1], c[2], 1)
  for i = 1, 900 do
    L.waitf(1)
    local a = L.addr()
    if a ~= prev then trans[#trans + 1] = { i, a }; prev = a end
  end
  L.setbtn(c[1], c[2], 0)
  L.waitf(60)
  LOG(("  held 900 frames: %08X -> %08X, %d address changes while held"):format(a0, L.addr(), #trans))
  if #trans > 0 then
    local s = {}
    for i = 1, math.min(#trans, 40) do s[#s + 1] = ("f+%d=%08X"):format(trans[i][1], trans[i][2]) end
    LOG("  first changes: " .. table.concat(s, " "))
    if #trans >= 3 then
      local gaps = {}
      for i = 2, #trans do gaps[#gaps + 1] = trans[i][1] - trans[i - 1][1] end
      table.sort(gaps)
      LOG(("  repeat interval frames: min=%d median=%d max=%d  (n=%d)"):format(
          gaps[1], gaps[(#gaps + 1) // 2], gaps[#gaps], #gaps))
    end
  end

  -- 5. minimum reliable HOLD (single tap must move exactly one page) -----------
  LOG("--- minimum hold sweep (gap fixed at 30 frames) ---")
  for _, h in ipairs({ 1, 2, 3, 4, 6, 8, 10, 12, 14, 16, 20, 24, 30 }) do
    L.dial_to(0x48400000, 20, 20)
    local b0 = L.addr()
    local n = 5
    for _ = 1, n do L.tap(6, 1, h, 30) end
    L.waitf(30)
    local d = (L.addr() - b0) & 0xffffffff
    LOG(("  hold=%2d frames: %d taps -> delta=0x%X  (want 0x%X) %s"):format(
        h, n, d, n * 0x100, (d == n * 0x100) and "OK" or "MISS"))
  end

  -- 6. minimum reliable GAP ----------------------------------------------------
  LOG("--- minimum gap sweep (hold fixed at 8 frames) ---")
  for _, g in ipairs({ 1, 2, 3, 4, 6, 8, 10, 12, 16, 20, 30 }) do
    L.dial_to(0x48400000, 20, 20)
    local b0 = L.addr()
    local n = 10
    for _ = 1, n do L.tap(6, 1, 8, g) end
    L.waitf(60)
    local d = (L.addr() - b0) & 0xffffffff
    LOG(("  gap=%2d frames: %d taps -> delta=0x%X (want 0x%X) %s   period=%d frames = %.2f pages/s"):format(
        g, n, d, n * 0x100, (d == n * 0x100) and "OK" or "MISS", 8 + g, 60 / (8 + g)))
  end

  LOG("PROBE DONE")
  if L.logf then L.logf:close() end
  L.mach:exit()
end

L.run(main)
L.LOG("probe_step armed")
