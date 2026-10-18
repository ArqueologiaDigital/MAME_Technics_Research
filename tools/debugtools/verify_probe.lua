-- verify_probe.lua -- the bitmapload VERIFIER's own MAME probe (kn7000, PROGRAM 941).
--
-- Questions it answers (each with the RAM signal it reads):
--   Q1 which balance columns step the BITMAP FILE index?  u16 0x5006B52C before/after one tap of
--      every column 1..8, UP and DOWN, starting from index 1 of a faked 3-entry list.
--   Q2 does holding a column auto-repeat, and does the index stop at 9 with >10 files?
--      (window 0x500710E4..E6 = 0..9, count-1 0x500710E2 = 14)
--   Q3 does LOAD (LCDR4) run the floppy fmmopen backend?  u16 0x50071258 is written only by the
--      floppy open backend 0x48532643 (0 ok, -1/-2/-3/-11 errors); a sentinel 0x1234 is put there
--      before LOAD.
--   Q4 what does Draw2BpFile put in the 8-bpp plane 0x500D4080 / RGB565 plane 0x9CE00000 /
--      raw palette 0x50031490 / RGB565 palette 0x50122AAC for each test BMP?  Dumped to files,
--      checked offline by check_dumps.py.  Rejection is visible as the palette sentinel
--      (raw slot 0x20 = 0x00123456, RGB565 slot 0x20 = 0x1234) surviving.
--   Q5 does the image stay, and where does EXIT go (index reset? rescan?).
--
-- Env: DG_DIR (memdump_lib.lua dir), DG_OUT (log), VP_OUT (dump dir), VP_BMPDIR (test BMP dir)

local L = dofile(os.getenv("DG_DIR") .. "/memdump_lib.lua")
local LOG, P = L.LOG, L.prog
local OUT = os.getenv("VP_OUT")
local BMPDIR = os.getenv("VP_BMPDIR")

local function hex(v, n) return string.format("%0" .. (n or 8) .. "X", v) end
local function cstr(a, max)
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
end
local function press(sub, hold, gap)
  local f, nm = findfield(sub)
  if not f then LOG("NOTFOUND " .. sub); return end
  LOG("PRESS " .. nm)
  f:set_value(1); L.waitf(hold or 20); f:set_value(0); L.waitf(gap or 120)
end
local scr
for _, s in pairs(manager.machine.screens) do scr = s; break end
local function snap(name) scr:snapshot(name); LOG("SNAP " .. name) end
local function state(tag)
  LOG(("[%s] t=%.2f idx=%d name='%s' media(F595)=%d cc5=%d cnt-1(E2)=%d win=%d..%d ext(125A)=%d "
     .. "open(1258)=%04X lcdhash=%s"):format(tag, L.mach.time.seconds, P:read_u16(0x5006B52C),
     cstr(0x5006B52E, 13), P:read_u8(0x5006F595), P:read_u8(0x50000CC5), P:read_u16(0x500710E2),
     P:read_u16(0x500710E4), P:read_u16(0x500710E6), P:read_u8(0x5007125A), P:read_u16(0x50071258),
     hex(L.lcdhash())))
end
local function write_name(slot, s)
  local a = 0x5007105D + 13 * slot
  for i = 0, 12 do P:write_u8(a + i, 0) end
  for i = 1, #s do P:write_u8(a + i - 1, s:byte(i)) end
end
local function dump(fname, addr, len)
  local parts = {}
  for i = 0, len - 1, 4 do parts[#parts + 1] = string.pack("<I4", P:read_u32(addr + i)) end
  local fh = io.open(OUT .. "/" .. fname, "wb"); fh:write(table.concat(parts)); fh:close()
end
local function inject(name, maxb)
  local fh = io.open(BMPDIR .. "/" .. name, "rb"); local data = fh:read("*a"); fh:close()
  if maxb and #data > maxb then data = data:sub(1, maxb) end
  for i = 1, #data do P:write_u8(0x502B8000 + i - 1, data:byte(i)) end
  LOG(("injected %s: %d bytes at 0x502B8000"):format(name, #data))
end

local function main()
  local last, stable = -1, 0
  L.waituntil(function()
    if L.mach.time.seconds < 15 then return false end
    local h = L.lcdhash()
    if h == last then stable = stable + 1 else stable = 0; last = h end
    return stable >= 90
  end, 60 * 120)
  LOG(("boot settled t=%.2f"):format(L.mach.time.seconds))

  local reg = manager.machine.memory.regions[":maincpu"]
  LOG("gate byte before " .. hex(P:read_u8(0x4840000F), 2))
  reg:write_u8(0x0F, 0xFF)
  LOG("gate byte after  " .. hex(P:read_u8(0x4840000F), 2))
  LOG("chord 0x99: " .. tostring(L.open_memdump(90)))
  L.waitf(120); snap("v01_panel_sim.png")
  press("LCDR 5"); L.waitf(120); snap("v02_debug_tools.png")
  press("LCDR 3"); L.waitf(240); state("BITMAP LOAD shown"); snap("v03_bitmap_load.png")

  -- Q1: column map
  local function fake3()
    write_name(0, "AAA.BMP"); write_name(1, "BBB.BMP"); write_name(2, "CCC.BMP")
    for k = 3, 9 do write_name(k, "") end
    P:write_u16(0x500710E4, 0); P:write_u16(0x500710E6, 2); P:write_u16(0x500710E2, 2)
    P:write_u8(0x5006F595, 3)
  end
  fake3()
  for col = 1, 8 do
    for _, dir in ipairs({1, -1}) do
      P:write_u16(0x5006B52C, 1)
      L.tap(col, dir, 20, 60); L.waitf(30)
      LOG(("Q1 col %d %s: idx 1 -> %d"):format(col, dir > 0 and "UP" or "DOWN", P:read_u16(0x5006B52C)))
    end
  end
  -- Q2: hold col 6 UP with a 15-file list (window 0..9)
  for k = 0, 9 do write_name(k, ("F%02d.BMP"):format(k)) end
  P:write_u16(0x500710E4, 0); P:write_u16(0x500710E6, 9); P:write_u16(0x500710E2, 14)
  P:write_u16(0x5006B52C, 0)
  L.setbtn("CPC_SEG8", 0x40, 1)
  for k = 1, 8 do L.waitf(30); LOG(("Q2 holding col6 UP %.1f s: idx %d"):format(k * 0.5, P:read_u16(0x5006B52C))) end
  L.setbtn("CPC_SEG8", 0x40, 0); L.waitf(60)
  LOG(("Q2 released: idx %d name '%s'"):format(P:read_u16(0x5006B52C), cstr(0x5006B52E, 13)))
  snap("v04_tencap.png")

  local tests = {
    {"T8.BMP"}, {"F4.BMP"}, {"TALL.BMP"}, {"NEG.BMP"}, {"B24.BMP"}, {"B2.BMP"}, {"B1.BMP"},
    {"WIDE.BMP"}, {"FULL8.BMP", 98304},
  }
  for n, t in ipairs(tests) do
    local tag = t[1]:gsub("%.BMP", "")
    fake3(); P:write_u16(0x5006B52C, 0)
    L.tap(6, 1, 20, 60); L.waitf(30)         -- idx 0 -> 1, name BBB.BMP (real stepping)
    state(tag .. " before LOAD")
    P:write_u16(0x50071258, 0x1234)
    P:write_u32(0x50031490 + 4 * 0x20, 0x00123456); P:write_u16(0x50122AAC + 2 * 0x20, 0x1234)
    inject(t[1], t[2])
    press("LCDR 4"); L.waitf(300)
    state(tag .. " after LOAD")
    snap("v05_" .. tag .. ".png")
    dump(tag .. "_fb.bin", 0x500D4080, 640 * 240)
    dump(tag .. "_lcd.bin", 0x9CE00000, 640 * 240 * 2)
    dump(tag .. "_palraw.bin", 0x50031490, 1024)
    dump(tag .. "_pal565.bin", 0x50122AAC, 512)
    if n == 1 then
      local h1 = L.lcdhash(); L.waitf(300)
      LOG(("Q5 persistence: lcdhash %s -> %s after 5 s"):format(hex(h1), hex(L.lcdhash())))
    end
    if t[1] == "FULL8.BMP" then dump("FULL8_after_502D0000.bin", 0x502D0000, 0x10000) end
    press("EXIT ("); L.waitf(300)
    state(tag .. " after EXIT")
    if n == 1 then snap("v06_after_exit.png") end
  end
  press("EXIT ("); L.waitf(200); snap("v07_after_exit2.png")
  state("after 2nd EXIT")
  LOG("done")
  L.mach:exit()
end

L.run(main)
