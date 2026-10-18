-- lcdcap_runtime.lua -- MAME autoboot script, kn7000 (PROGRAM 941), runtime lane.
--
-- Question it answers: with the program-ROM byte at 0x4840000F = 0xFF *in the ROM file*
-- (scratch copy, patch_gate.py), does the four-corner LCD chord (LCDL1+LCDL5+LCDR1+LCDR5,
-- accumulator 0x50021FE0 == 0x00110000) make CaptureLcd write A:\LCDCAP00.BMP onto an inserted
-- FAT12 floppy image?  And does the 1/4/5/8 chord then open the Panel Simulator (byte == 0xFF)
-- instead of the MEMORY DUMP hex viewer (byte != 0xFF)?  Run once with the patched ROM path and
-- once with the stock ROM path (control: nothing may be written).
--
-- Signals read (from the disassembly, 941 addresses):
--   u8  0x4840000F  the gate byte, read through the CPU's program space (= what the ROM file holds)
--   u32 0x50021FC8  CaptureLcd RGB-path file counter: sprintf LCDCAP%02d.BMP then ++ (pc 0x484156C4)
--   s16 0x50071258  floppy fmmopen result (0 = opened; -1/-2/-3/-11 = failures, 0x485326C3..)
--   s16 0x50092584  SD     fmmopen result (same encoding, SD backend 0x4856580E)
--   u8  0x5007125A  ExtMode, the fmm backend selector (0 floppy "A:\", 1 SD, 2 third)
--   u32 0x50021FD8 / 0x50021FDC / 0x50021FE0  UP-held / DOWN-held / both-held index-switch masks
--   FDC registers 0x98020000-0x9802000F and FDC.DACK byte slot 0x98010000-3 (driver kn7000.cpp:974-977)
--   SPI byte mailbox 0x9805000C (SD card data path) -- write count
--
-- Environment: DG_DIR (dir of memdump_lib.lua), DG_OUT (log), RT_OUT (dir for PNG/BIN output),
--              RT_REDIRECT_SD=1 to force the capture's fmm* calls onto the SD backend (see below),
--              RT_HLE_FWRITE=1 to log/stream fmmwrite arguments (needs the debugger; not used by default).

local L = dofile(os.getenv("DG_DIR") .. "/memdump_lib.lua")
local LOG = L.LOG
local P = L.prog
local OUT = os.getenv("RT_OUT") or "."
local REDIRECT_SD = os.getenv("RT_REDIRECT_SD") == "1"

local function hex(v, n) return string.format("%0" .. (n or 8) .. "X", v) end

-- per-build addresses (RT_BUILD=941 default; 942 = SP7001, located by find942.py)
local A941 = { up=0x50021FD8, dn=0x50021FDC, both=0x50021FE0, cnt=0x50021FC8, ff0=0x50021FF0,
               fresA=0x50071258, fresS=0x50092584, ext=0x5007125A, errno=0x500AD390,
               disp_lo=0x48532390, disp_hi=0x48532500, close_lo=0x485323BF, close_hi=0x485323E1 }
local A942 = { up=0x50021FE8, dn=0x50021FEC, both=0x50021FF0, cnt=0x50021FD8, ff0=0x50022000,
               fresA=0x50071268, fresS=0x50092594, ext=0x5007126A, errno=0x500AD3A0,
               disp_lo=0x4853237F, disp_hi=0x485324EF, close_lo=0x485323AE, close_hi=0x485323D0 }
local BUILD = os.getenv("RT_BUILD") or "941"
local AD = (BUILD == "942") and A942 or A941
L.HELD_UP, L.HELD_DN, L.HELD_BOTH = AD.up, AD.dn, AD.both

local scr
for _, s in pairs(manager.machine.screens) do scr = s; break end
local function snap(name) scr:snapshot(OUT .. "/" .. name); LOG("SNAP " .. name) end

-- traffic counters (globals: GC would collect locals)
FDC_RD, FDC_WR, DACK_RD, DACK_WR, SPI_WR = 0, 0, 0, 0, 0
T_FDC_R = P:install_read_tap(0x98020000, 0x9802000F, "rt_fdc_r", function(o, d, m) FDC_RD = FDC_RD + 1 end)
T_FDC_W = P:install_write_tap(0x98020000, 0x9802000F, "rt_fdc_w", function(o, d, m) FDC_WR = FDC_WR + 1 end)
T_DACK_R = P:install_read_tap(0x98010000, 0x98010003, "rt_dack_r", function(o, d, m) DACK_RD = DACK_RD + 1 end)
T_DACK_W = P:install_write_tap(0x98010000, 0x98010003, "rt_dack_w", function(o, d, m) DACK_WR = DACK_WR + 1 end)
T_SPI_W = P:install_write_tap(0x9805000C, 0x9805000F, "rt_spi_w", function(o, d, m) SPI_WR = SPI_WR + 1 end)

local function traffic() return ("fdc r/w=%d/%d dack r/w=%d/%d spi_w=%d"):format(FDC_RD, FDC_WR, DACK_RD, DACK_WR, SPI_WR) end

local function st(tag)
  LOG(("[%s] t=%.2f gate=%02X up=%08X dn=%08X both=%08X | cnt FC8=%d | fmm A=%d SD=%d extmode=%d errno(500AD390)=%d | %s | lcdhash=%s"):format(
     tag, L.mach.time.seconds, P:read_u8(0x4840000F),
     P:read_u32(AD.up), P:read_u32(AD.dn), P:read_u32(AD.both),
     P:read_u32(AD.cnt), P:read_i16(AD.fresA), P:read_i16(AD.fresS),
     P:read_u8(AD.ext), P:read_i32(AD.errno), traffic(), hex(L.lcdhash())))
end

-- who bumps the counter / what fmmopen returns
WT_CNT = P:install_write_tap(AD.cnt, AD.cnt + 3, "rt_cnt", function(off, data, mask)
  LOG(("  TAP counter %08X <- %08X pc=%08X frame=%d"):format(off, data, L.cpu.state["PC"].value, L.frame))
  if REDIRECT_SD and data ~= 0 then REDIRECT_ARMED = true; LOG("  REDIRECT armed: next fmm* dispatch reads ExtMode=1") end
end)
WT_FA = P:install_write_tap(AD.fresA & ~3, (AD.fresA & ~3) + 3, "rt_fmmA", function(off, data, mask)
  if L.frame > 0 then LOG(("  TAP floppy fmm result %08X <- %08X (mask %08X) pc=%08X frame=%d"):format(off, data, mask, L.cpu.state["PC"].value, L.frame)) end
end)
WT_FS = P:install_write_tap(AD.fresS & ~3, (AD.fresS & ~3) + 3, "rt_fmmS", function(off, data, mask)
  if L.frame > 0 then LOG(("  TAP SD fmm result %08X <- %08X (mask %08X) pc=%08X frame=%d"):format(off, data, mask, L.cpu.state["PC"].value, L.frame)) end
end)

-- Optional, emulator-only redirect: the fmm* dispatchers (fmmopen 0x48532395 .. 0x48532500) each
-- read ExtMode with `movbu (0x5007125a),d0`.  While armed (from CaptureLcd's counter write until
-- its fmmclose dispatch at pc 0x485323D3), answer those reads with 1 so the firmware's own SD
-- backend receives the file.  Nothing else sees a changed value: RAM is never written.
if REDIRECT_SD then
  REDIRECT_ARMED = false
  REDIR_N = 0
  T_EXT = P:install_read_tap(AD.ext & ~3, (AD.ext & ~3) + 3, "rt_ext_r", function(off, data, mask)
    if not REDIRECT_ARMED then return nil end
    local sh = 8 * (AD.ext & 3)                               -- ExtMode byte lane (LE): 941 0x5007125A -> lane 2
    if (mask & (0xFF << sh)) == 0 then return nil end
    local pc = L.cpu.state["PC"].value
    if pc < AD.disp_lo or pc > AD.disp_hi then return nil end
    REDIR_N = REDIR_N + 1
    if pc >= AD.close_lo and pc <= AD.close_hi then             -- fmmclose dispatch: last redirected read
      REDIRECT_ARMED = false
      LOG(("  REDIRECT fmmclose read pc=%08X frame=%d (redirected reads=%d), disarmed"):format(pc, L.frame, REDIR_N))
    end
    return (data & ~(0xFF << sh)) | (1 << sh)
  end)
end

local function dump_fb(name)
  -- the composited RGB565 plane 0x9CE00000: 241 rows x 640 px x 2 bytes (row 240 included,
  -- because CaptureLcd's RGB path reads rows 240..1, 0x484157B1)
  local f = io.open(OUT .. "/" .. name, "wb")
  local t = {}
  for i = 0, 241 * 640 * 2 - 1, 4 do
    local v = P:read_u32(0x9CE00000 + i)
    t[#t + 1] = string.char(v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF, (v >> 24) & 0xFF)
    if #t >= 4096 then f:write(table.concat(t)); t = {} end
  end
  f:write(table.concat(t)); f:close()
  LOG("FBDUMP " .. name)
end

local function lcd_corner_chord(tag, hold_frames)
  st(tag .. " before")
  local c0 = P:read_u32(AD.cnt)
  L.setmask("CPL_SEG0", 0x06, 1)         -- LCDL 1 (0x02) + LCDL 5 (0x04): DOWN half, index 0x10/0x14
  L.waituntil(function() return (P:read_u32(AD.dn) & 0x110000) == 0x110000 end, 240)
  st(tag .. " after LCDL1+LCDL5")
  dump_fb(tag .. "_fb_at_chord.bin")
  L.setmask("CPR_SEG5", 0x11, 1)         -- LCDR 1 (0x10) + LCDR 5 (0x01): UP half, index 0x10/0x14
  L.waituntil(function() return P:read_u32(AD.cnt) ~= c0 end, 240)
  st(tag .. " fourth key down")
  -- keep all four held while the capture runs (CaptureLcd is synchronous in the panel task)
  for i = 1, (hold_frames or 1800) / 60 do
    L.waitf(60)
    st(tag .. (" held +%ds"):format(i))
  end
  snap(tag .. "_held.png")
  L.setmask("CPR_SEG5", 0x11, 0); L.waitf(30)
  L.setmask("CPL_SEG0", 0x06, 0); L.waitf(30)
  L.waituntil(function() return P:read_u32(AD.both) == 0 and P:read_u32(AD.up) == 0
                            and P:read_u32(AD.dn) == 0 end, 240)
  L.waitf(120)
  st(tag .. " released")
  snap(tag .. "_after.png")
end

local function main()
  local last, stable = -1, 0
  L.waituntil(function()
    if L.mach.time.seconds < 15 then return false end
    local h = L.lcdhash()
    if h == last then stable = stable + 1 else stable = 0; last = h end
    return stable >= 90
  end, 60 * 120)
  LOG(("build " .. BUILD .. ": boot settled t=%.2f  gate byte read by the CPU = %02X"):format(L.mach.time.seconds, P:read_u8(0x4840000F)))
  snap("00_home.png")
  st("home")

  lcd_corner_chord("A_corners", tonumber(os.getenv("RT_HOLD_FRAMES") or "1800"))

  if os.getenv("RT_PADCHORD") == "1" then
    -- second trigger (0x484149F1): DISPLAY HOLD held, PAD 1 held, PAD 2 pressed -> 0x50021FF0 == 7
    st("A2_pads before")
    local c0 = P:read_u32(AD.cnt)
    L.setmask("CPC_SEG11", 0x40, 1)        -- DISPLAY HOLD -> event 0x7020A0, FF0 |= 1
    L.waituntil(function() return P:read_u32(AD.ff0) == 1 end, 240)
    L.setmask("CPL_SEG6", 0x10, 1)         -- PAD 1 -> event 0x702030 arg 0, FF0 |= 2
    L.waituntil(function() return P:read_u32(AD.ff0) == 3 end, 240)
    dump_fb("A2_pads_fb_at_chord.bin")
    L.setmask("CPL_SEG4", 0x80, 1)         -- PAD 2 -> event 0x702030 arg 1, FF0 |= 4 -> ==7 fires
    L.waituntil(function() return P:read_u32(AD.cnt) ~= c0 end, 240)
    st("A2_pads third key down")
    for i = 1, (tonumber(os.getenv("RT_HOLD_FRAMES") or "1800")) / 60 do
      L.waitf(60)
      if i % 10 == 0 then st(("A2_pads held +%ds"):format(i)) end
    end
    snap("A2_pads_held.png")
    L.setmask("CPL_SEG4", 0x80, 0); L.waitf(30)
    L.setmask("CPL_SEG6", 0x10, 0); L.waitf(30)
    L.setmask("CPC_SEG11", 0x40, 0); L.waitf(60)
    L.setmask("CPC_SEG11", 0x40, 1); L.waitf(30)   -- press DISPLAY HOLD again: undo MT_ToggleHold
    L.setmask("CPC_SEG11", 0x40, 0); L.waitf(120)
    st("A2_pads released")
    snap("A2_pads_after.png")
  end

  -- the 1/4/5/8 chord: byte != 0xFF -> MEMORY DUMP hex viewer; byte == 0xFF -> ChangeMode(0,0)
  local ok = L.open_memdump(90)
  LOG("1/4/5/8 chord reached both=0x99: " .. tostring(ok))
  L.waitf(120)
  st("after 1/4/5/8")
  snap("B_chord_1458.png")

  LOG("done " .. traffic())
  L.mach:exit()
end

L.run(main)
