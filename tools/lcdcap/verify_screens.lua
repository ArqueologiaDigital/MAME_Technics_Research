-- verify_screens.lua -- MAME autoboot script, kn7000 PROGRAM 941 with the gate byte patched to
-- 0xFF at boot (verifier lane chord-verify).
-- Questions: (1) with the byte at 0xFF, does balance chord 1/4/5/8 open the Panel Simulator
-- (ChangeMode(0,0)) instead of MEMORY DUMP, and do LCDR5 then LCDL1 lead to DEBUG TOOLS and
-- MEMORY DUMP?  (2) does the four-corner LCD chord (LCDL1+LCDL5+LCDR1+LCDR5) run CaptureLcd
-- (counter u32 0x50021FC8 +1, written at pc 0x484156C4) on each of those screens and on two
-- ordinary screens (PIANO sound list, PROGRAM MENUS)?  (3) what does the screen look like
-- before/after each chord (snapshots)?
-- Env: DG_DIR (dir of memdump_lib.lua), DG_OUT (log file).

local L = dofile(os.getenv("DG_DIR") .. "/memdump_lib.lua")
local LOG, P = L.LOG, L.prog
local scr
for _, s in pairs(manager.machine.screens) do scr = s; break end
local function snap(n) scr:snapshot(n); LOG("SNAP " .. n) end
local function cnt() return P:read_u32(0x50021FC8) end
LASTFMM = 0
VT_EXT = P:install_write_tap(0x50071258, 0x5007125B, "v_ext", function(off, data, mask)
  if (mask & 0xFFFF) ~= 0 then LASTFMM = L.frame end
end)
VT_CNT = P:install_write_tap(0x50021FC8, 0x50021FCB, "v_cnt", function(off, data, mask)
  LOG(("  TAP cnt <- %d pc=%08X f=%d"):format(data, L.cpu.state["PC"].value, L.frame))
end)
local function st(tag)
  LOG(("[%s] f=%d FD8=%08X FDC=%08X FE0=%08X FC8=%d FF0=%X lcdhash=%08X"):format(tag, L.frame,
    P:read_u32(0x50021FD8), P:read_u32(0x50021FDC), P:read_u32(0x50021FE0), cnt(),
    P:read_u32(0x50021FF0), L.lcdhash()))
end
local function press(port, mask, cell, bit)
  L.setmask(port, mask, 1)
  if cell then L.waituntil(function() return (P:read_u32(cell) & bit) == bit end, 900) else L.waitf(30) end
end
local function release(port, mask, cell, bit)
  L.setmask(port, mask, 0)
  if cell then L.waituntil(function() return (P:read_u32(cell) & bit) == 0 end, 900) else L.waitf(30) end
end
local function tapbtn(port, mask, tag)
  L.setmask(port, mask, 1); L.waitf(20); L.setmask(port, mask, 0); L.waitf(150)
  st(tag); snap(tag .. ".png")
end
local function corners(tag)
  local c0, f0 = cnt(), L.frame
  st(tag .. " before"); snap(tag .. "_0before.png")
  press("CPL_SEG0", 0x06, 0x50021FDC, 0x00110000)       -- LCDL1 + LCDL5
  press("CPR_SEG5", 0x11, 0x50021FD8, 0x00110000)       -- LCDR1 + LCDR5
  if cnt() ~= c0 then L.waituntil(function() return LASTFMM > f0 and L.frame - LASTFMM > 30 end, 900) end
  L.waitf(30); st(tag .. " held")
  release("CPR_SEG5", 0x11, 0x50021FD8, 0x00110000)
  release("CPL_SEG0", 0x06, 0x50021FDC, 0x00110000)
  L.waitf(120)
  st(tag .. " released"); snap(tag .. "_1after.png")
  LOG(("RESULT %s: counter %d -> %d"):format(tag, c0, cnt()))
end

local function main()
  local last, stable = -1, 0
  L.waituntil(function()
    if L.mach.time.seconds < 15 then return false end
    local h = L.lcdhash()
    if h == last then stable = stable + 1 else stable = 0; last = h end
    return stable >= 90
  end, 60 * 120)
  manager.machine.memory.regions[":maincpu"]:write_u8(0x0F, 0xFF)
  LOG(("boot settled t=%.2f, gate now %02X"):format(L.mach.time.seconds, P:read_u8(0x4840000F)))
  st("home"); snap("00_home.png")
  corners("10_home")

  local opened = L.open_memdump(120)     -- columns 1,4,5,8 UP+DOWN; with 0xFF -> ChangeMode(0,0)
  LOG("balance chord 1/4/5/8 reached FE0=0x99: " .. tostring(opened))
  L.waitf(120); st("after 1/4/5/8"); snap("20_after_1458.png")
  tapbtn("CPR_SEG5", 0x01, "30_after_LCDR5")
  corners("31_screen_after_LCDR5")
  tapbtn("CPL_SEG0", 0x02, "40_after_LCDL1")
  corners("41_screen_after_LCDL1")

  for i = 1, 4 do tapbtn("CPC_SEG11", 0x80, "50_exit" .. i) end
  tapbtn("CPR_SEG4", 0x10, "60_after_PIANO")
  corners("61_piano")
  for i = 1, 3 do tapbtn("CPC_SEG11", 0x80, "70_exit" .. i) end
  tapbtn("CPR_SEG0", 0x04, "80_after_PROGRAM_MENUS")
  corners("81_program_menus")
  for i = 1, 3 do tapbtn("CPC_SEG11", 0x80, "85_exit" .. i) end

  opened = L.open_memdump(120)
  L.waitf(120); st("after 1/4/5/8 again"); snap("90_after_1458.png")
  corners("91_panelsim")

  LOG("done")
  L.mach:exit()
end

L.run(main)
