-- dm5.lua -- DEBUG MODE effect 4 (APC SELECT debug window) reached through the DEBUG TOOLS mode/title
-- enumerator (col 11 UP/DOWN steps u32 0x500012C0, LCDR5 jumps), and effect 1 (PART SETTING list).
-- DM_ON=1: DEBUG MODE ON (col 2 UP); DM_ON=0: OFF (negative control). Same key sequence otherwise.
-- Signals: u32 0x500012C0 enumerator value; title u32 0x5000099C[1]; u32 0x50007874..80 APC waits;
-- u16 0x5006B5CE current part, u16 0x5006B5D0 list limit.
local R = dofile(os.getenv("RT_DIR") .. "/rt_lib.lua")
local L, LOG, P = R.L, R.LOG, R.P
local ON = os.getenv("DM_ON") == "1"
local function enum() return P:read_u32(0x500012C0) end
local function apc(tag)
  LOG(("[%s] APC waits 0x50007874=%d 0x50007878=%d 0x5000787C=%d 0x50007880=%d  %s"):format(tag,
      P:read_u32(0x50007874), P:read_u32(0x50007878), P:read_u32(0x5000787C), P:read_u32(0x50007880), R.screens()))
end

local function main()
  R.settle()
  R.patch_gate()
  R.to_debug_tools("01")
  if ON then R.tap(2, 1) end
  R.dm(ON and "DM set ON" or "DM left OFF")

  -- enumerator: single taps first, to see the step
  for i = 1, 3 do local b = enum(); R.tap(11, 1); LOG(("col 11 UP: enum %08X -> %08X"):format(b, enum())) end
  R.snap("02_enum_after_3_up.png")
  -- then hold col 11 UP (firmware auto-repeat) until close to title 0xED
  local target = 0x000F00ED
  L.setbtn("CPC_SEG10", 0x01, 1)
  local ok = L.waituntil(function() return enum() >= target - 6 and enum() < 0x00100000 end, 60 * 120)
  L.setbtn("CPC_SEG10", 0x01, 0)
  L.waitf(60)
  LOG(("held col 11 UP: reached=%s enum %08X"):format(tostring(ok), enum()))
  for _ = 1, 20 do
    local e = enum()
    if e == target then break end
    R.tap(11, (e < target) and 1 or -1)
    LOG(("tap: enum %08X -> %08X"):format(e, enum()))
  end
  R.snap("03_enum_at_target.png")
  R.press("LCDR 5"); L.waitf(300)    -- jump
  R.dm("after LCDR5 jump")
  apc("jumped")
  R.snap("04_after_jump.png")
  if P:read_u32(0x5000099C + 4) == target then
    for _, c in ipairs({8, 9, 10, 11}) do R.tap(c, 1); apc(("col %d UP"):format(c)) end
    R.snap("05_apc_after_up.png")
    for _, c in ipairs({8, 9, 10, 11}) do R.tap(c, -1); apc(("col %d DOWN"):format(c)) end
    R.snap("06_apc_after_down.png")
  end
  R.press("EXIT ("); L.waitf(240)
  LOG("after EXIT " .. R.screens())
  R.snap("07_after_exit.png")
  R.press("EXIT ("); L.waitf(240)
  LOG("after EXIT 2 " .. R.screens())

  -- effect 1: PART SETTING, step PART SELECT with LCDL1 (upper arrow) 34 times
  R.press("PROGRAM MENUS"); L.waitf(180)
  R.press("LCDL 1"); L.waitf(240)   -- SOUND
  R.press("LCDL 1"); L.waitf(300)   -- PART SETTING
  LOG(("PART SETTING start: part %d limit 0x%X %s"):format(P:read_u16(0x5006B5CE), P:read_u16(0x5006B5D0), R.screens()))
  R.snap("08_part_00.png")
  for i = 1, 34 do
    local b = P:read_u16(0x5006B5CE)
    R.press("LCDL 1", 12, 50)
    LOG(("LCDL1 #%d: part %d -> %d"):format(i, b, P:read_u16(0x5006B5CE)))
    R.snap(("08_part_%02d.png"):format(i))
  end
  LOG("done")
  L.mach:exit()
end
L.run(main)
