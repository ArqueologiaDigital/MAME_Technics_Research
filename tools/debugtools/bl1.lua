-- bl1.lua -- BITMAP LOAD from real media in MAME (kn7000, PROGRAM 941, gate byte poked to 0xFF).
--
-- Question: with a disk image attached, does DEBUG TOOLS > BITMAP LOAD list the .BMP files, and
-- does LOAD (LCDR4) make the firmware itself read the file into 0x502B8000 (fmmopen 0x48532395 at
-- 0x48488727, fmmread 0x48532468 at 0x4848873F) and draw it with Draw2BpFile (0x4848878D)?
--
-- Proof that the bytes came from the medium: before LOAD the first BL_SIZE bytes of the buffer are
-- filled with 0xEE (a poke into the scratch buffer only); after LOAD they are compared with BL_FILE.
--
-- Environment:
--   BL_FILE  host path of the BMP that is on the medium (for the comparison)
--   BL_FAKE  1 = if the firmware's list is empty, write TEST4.BMP / BL_NAME into slots 0 / 1 of the scan window
--            (0x5007105D) and mark the floppy media state valid (0x5006F595 = 3) -- the faked-list
--            trick of the bitmapload lane, used only when the real scan finds nothing
--   BL_NAME  8.3 name to fake (default TEST8.BMP)
--   BL_EXT   if set, value poked into the drive selector byte 0x5007125A before LOAD
--            (0 floppy "A:", 1 SD, 2 third backend)
--   BL_INJECT 1 = write BL_FILE into 0x502B8000 instead of the 0xEE fill (display-path-only
--            fallback; used when no medium can be read)
local R = dofile(os.getenv("RT_DIR") .. "/rt_lib.lua")
local L, LOG, P = R.L, R.LOG, R.P

local function state(tag)
  local names = {}
  for k = 0, 9 do
    local s = R.cstr(0x5007105D + 13 * k, 13)
    if s ~= "" then names[#names + 1] = k .. "=" .. s end
  end
  LOG(("[%s] t=%.2f idx u16 0x5006B52C=%d name 0x5006B52E='%s' media u8 0x5006F595=%d count-1 u16 0x500710E2=%d "
     .. "win %d..%d drivesel u8 0x5007125A=%d sdcwd 0x50092504='%s' list{%s} %s lcdhash=%s"):format(
     tag, L.mach.time.seconds, P:read_u16(0x5006B52C), R.cstr(0x5006B52E, 13), P:read_u8(0x5006F595),
     P:read_u16(0x500710E2), P:read_u16(0x500710E4), P:read_u16(0x500710E6), P:read_u8(0x5007125A),
     R.cstr(0x50092504, 32), table.concat(names, ","), R.screens(), R.hex(L.lcdhash())))
end

local function write_name(slot, s)
  local a = 0x5007105D + 13 * slot
  for i = 0, 12 do P:write_u8(a + i, 0) end
  for i = 1, #s do P:write_u8(a + i - 1, s:byte(i)) end
end

local function compare(data, tag)
  local diff, first = 0, nil
  for i = 1, #data do
    if P:read_u8(0x502B8000 + i - 1) ~= data:byte(i) then
      diff = diff + 1
      if not first then first = i - 1 end
    end
  end
  local tail = {}
  for i = 0, 7 do tail[#tail + 1] = string.format("%02X", P:read_u8(0x502B8000 + #data + i)) end
  LOG(("[%s] buffer 0x502B8000 vs file (%d bytes): %d bytes differ%s; first bytes %02X %02X %02X %02X; "
     .. "8 bytes after the file end: %s"):format(tag, #data, diff,
     first and string.format(" (first at +0x%X)", first) or "", P:read_u8(0x502B8000), P:read_u8(0x502B8001),
     P:read_u8(0x502B8002), P:read_u8(0x502B8003), table.concat(tail, " ")))
  return diff
end

local function main()
  R.settle()
  R.patch_gate()
  R.to_debug_tools("01")
  R.press("LCDR 3")                 -- DEBUG TOOLS: LCDR3 = BITMAP LOAD
  L.waitf(300)
  state("BITMAP LOAD opened")
  R.snap("02_bitmap_load.png")

  local fh = io.open(os.getenv("BL_FILE"), "rb"); local data = fh:read("*a"); fh:close()

  if P:read_u16(0x500710E2) == 0 and R.cstr(0x5007105D, 13) == "" and os.getenv("BL_FAKE") == "1" then
    local nm = os.getenv("BL_NAME") or "TEST8.BMP"
    -- two entries, so that a real UP step makes DbBitmapFileProc (UP path 0x484885C4) strcpy
    -- entry 1's name into 0x5006B52E itself (EV_SHOW only copied entry 0 = "" at open time)
    write_name(0, "TEST4.BMP"); write_name(1, nm)
    P:write_u16(0x500710E4, 0); P:write_u16(0x500710E6, 1); P:write_u16(0x500710E2, 1)
    P:write_u8(0x5006F595, 3)
    LOG("list was empty: faked slot 0 = TEST4.BMP, slot 1 = " .. nm .. ", media state 3")
    R.tap(6, 1); L.waitf(60)          -- col 6 UP: index 0 -> 1
    state("after fake + col 6 UP")
  else
    -- real list: walk it with col 6 UP and back with col 5 DOWN, to show the selector
    for _ = 1, 2 do R.tap(6, 1); state("col 6 UP") end
    R.snap("03_bitmap_load_stepped.png")
    for _ = 1, 3 do R.tap(5, -1); state("col 5 DOWN") end
  end
  R.snap("03_bitmap_load_selected.png")

  if os.getenv("BL_INJECT") == "1" then
    for i = 1, #data do P:write_u8(0x502B8000 + i - 1, data:byte(i)) end
    LOG("BL_INJECT: wrote the file into 0x502B8000 (display path only)")
  else
    for i = 0, #data + 15 do P:write_u8(0x502B8000 + i, 0xEE) end
    LOG(("pre-filled 0x502B8000..+0x%X with 0xEE"):format(#data + 15))
  end
  compare(data, "before LOAD")

  local ext = os.getenv("BL_EXT")
  if ext and ext ~= "" then P:write_u8(0x5007125A, tonumber(ext)); LOG("drive selector 0x5007125A poked = " .. ext) end

  R.press("LCDR 4")                 -- BITMAP LOAD: LCDR4 = LOAD
  L.waitf(600)
  state("after LOAD")
  local diff = compare(data, "after LOAD")
  LOG(diff == 0 and "RESULT: buffer equals the file" or "RESULT: buffer does NOT equal the file")
  R.snap("04_bitmap_disp.png")

  for _, p in ipairs({ {0,0}, {5,5}, {20,30}, {40,10}, {70,10}, {100,40}, {126,62}, {64,32}, {200,100} }) do
    local x, y = p[1], p[2]
    LOG(("pixel (%3d,%3d): fb 0x500D4080 byte %02X, LCD 0x9CE00000 rgb565 %04X"):format(x, y,
        P:read_u8(0x500D4080 + y * 640 + x), P:read_u16(0x9CE00000 + (y * 640 + x) * 2)))
  end

  if ext and ext ~= "" then P:write_u8(0x5007125A, 0); LOG("drive selector restored to 0") end
  R.press("EXIT ("); L.waitf(300)
  state("after EXIT")
  R.snap("05_after_exit.png")
  R.press("EXIT ("); L.waitf(240)
  state("after EXIT 2")
  R.snap("06_after_exit2.png")
  LOG("done")
  L.mach:exit()
end
L.run(main)
