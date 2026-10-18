-- verify_chord.lua -- MAME autoboot script, kn7000 PROGRAM 941 (verifier lane chord-verify).
--
-- Questions it answers (independent re-check of lane "chord"):
--  A  stock gate byte (0x16): do the four LCD soft keys LCDL1/LCDR1/LCDL5/LCDR5, pressed ONE AT
--     A TIME, build both-held accumulator 0x50021FE0 = 0x00110000 without running CaptureLcd?
--  B  gate patched to 0xFF, reversed order (R5, R1, L5, L1, one key per step): does the capture
--     counter 0x50021FC8 move only on the 4th key, and not on any release?
--  C  extra both-held pair: with balance column 1 UP+DOWN also held (FE0 bit 0), the 4 keys give
--     0x110001 (no capture); does RELEASING column-1 DOWN (FE0 -> 0x110000) then fire a capture?
--  D  re-fire: with the 4 keys held, does one tap of MUTE UP 1 fire on press AND on release?
--  E1 DISPLAY HOLD, PAD 1, PAD 2 (in that order): capture?
--  E2 PAD 1, PAD 2, then DISPLAY HOLD (FF0 = 7 but no check), then PAD 3: capture on PAD 3?
--  E3 after an E1 capture (FF0 cleared), re-press PAD 2 while DISPLAY HOLD + PAD 1 still held:
--     no capture expected.
-- Signals: u32 0x50021FD8 (0x702001 half held), 0x50021FDC (0x702000 half held), 0x50021FE0
-- (= FD8 & FDC), u32 0x50021FC8 (CaptureLcd RGB-path counter: sprintf then ++ at 0x484156C3),
-- u32 0x50021FF0 (DISPLAY HOLD / pad state), u16 0x50071258 (floppy fopen result),
-- u8 0x5007125A (ExtMode drive selector), u16 0x5000757A (GetLcdMode).
-- Env: DG_DIR (dir of kn7000_mame/tools/dumpgrab/capture/memdump_lib.lua), DG_OUT (log).

local L = dofile(os.getenv("DG_DIR") .. "/memdump_lib.lua")
local LOG, P = L.LOG, L.prog

local function st(tag)
  LOG(("[%s] f=%d gate=%02X FD8=%08X FDC=%08X FE0=%08X FC8=%d FCC=%d FD0=%d FF0=%X fmm=%d ext=%d lcdmode=%d")
    :format(tag, L.frame, P:read_u8(0x4840000F), P:read_u32(0x50021FD8), P:read_u32(0x50021FDC),
      P:read_u32(0x50021FE0), P:read_u32(0x50021FC8), P:read_u32(0x50021FCC), P:read_u32(0x50021FD0),
      P:read_u32(0x50021FF0), P:read_i16(0x50071258), P:read_u8(0x5007125A), P:read_u16(0x5000757A)))
end

CNTF = 0
VT_CNT = P:install_write_tap(0x50021FC8, 0x50021FD3, "v_cnt", function(off, data, mask)
  if off == 0x50021FC8 then CNTF = L.frame end
  LOG(("  TAP cnt %08X <- %08X pc=%08X f=%d"):format(off, data, L.cpu.state["PC"].value, L.frame))
end)
VT_EXT = P:install_write_tap(0x50071258, 0x5007125B, "v_ext", function(off, data, mask)
  if (mask & 0xFFFF) ~= 0 then LASTFMM = L.frame end
  LOG(("  TAP fmm/ext %08X <- %08X mask=%08X pc=%08X f=%d"):format(off, data, mask, L.cpu.state["PC"].value, L.frame))
end)

local K = {   -- port, mask, {cell, bit} the firmware sets while the key is held
  L1 = {"CPL_SEG0", 0x02, 0x50021FDC, 0x00010000}, L5 = {"CPL_SEG0", 0x04, 0x50021FDC, 0x00100000},
  R1 = {"CPR_SEG5", 0x10, 0x50021FD8, 0x00010000}, R5 = {"CPR_SEG5", 0x01, 0x50021FD8, 0x00100000},
  C1U = {"CPC_SEG5", 0x10, 0x50021FD8, 0x1}, C1D = {"CPC_SEG5", 0x20, 0x50021FDC, 0x1},
  HOLD = {"CPC_SEG11", 0x40, 0x50021FF0, 0x1}, PAD1 = {"CPL_SEG6", 0x10, 0x50021FF0, 0x2},
  PAD2 = {"CPL_SEG4", 0x80, 0x50021FF0, 0x4}, PAD3 = {"CPL_SEG4", 0x20, nil, nil},
}
local function cnt() return P:read_u32(0x50021FC8) end
-- every capture attempt ends with the floppy backend storing its fopen result (0x485326C4/BC);
-- CaptureLcd runs synchronously in the UI task, so panel events queue up until it returns.
LASTFMM = 0
local function settle_capture(c_before, f_before)
  if cnt() ~= c_before then
    local ok = L.waituntil(function() return LASTFMM > f_before and L.frame - LASTFMM > 30 end, 900)
    if not ok then LOG("  (capture settle TIMEOUT)") end
  end
end
local function key(name, v, expect_bit)
  local k = K[name]
  local c0, f0 = cnt(), L.frame
  L.setbtn(k[1], k[2], v)
  if k[3] and expect_bit ~= false then
    local ok = L.waituntil(function()
      local on = (P:read_u32(k[3]) & k[4]) ~= 0
      return (v == 1) == on
    end, 900)
    if not ok then LOG("  (bit wait TIMEOUT for " .. name .. ")") end
  else
    L.waitf(90)
  end
  L.waitf(20)
  settle_capture(c0, f0)
  st(("%s %s"):format(name, v == 1 and "DOWN" or "UP"))
end
local function relall(names)
  for _, n in ipairs(names) do key(n, 0, false); L.waitf(40) end
  L.waituntil(function() return P:read_u32(0x50021FD8) == 0 and P:read_u32(0x50021FDC) == 0 end, 900)
  L.waitf(60); st("all released")
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
  st("home")

  LOG("== A stock gate, L1 R1 L5 R5 one at a time")
  local c0 = cnt()
  key("L1", 1); key("R1", 1); key("L5", 1); key("R5", 1)
  LOG(("A result: FE0=%08X counter %d -> %d"):format(P:read_u32(0x50021FE0), c0, cnt()))
  relall({"L1", "L5", "R1", "R5"})

  manager.machine.memory.regions[":maincpu"]:write_u8(0x0F, 0xFF)
  LOG(("gate patched, program-space read 0x4840000F = %02X"):format(P:read_u8(0x4840000F)))

  LOG("== B gate FF, reversed order R5 R1 L5 L1, then release one at a time")
  c0 = cnt()
  key("R5", 1); key("R1", 1); key("L5", 1)
  local c3 = cnt()
  key("L1", 1)
  local c4 = cnt()
  LOG(("  capture blocked the UI task for %d frames (counter write -> last fopen result write)"):format(LASTFMM - CNTF))
  key("L1", 0); key("L5", 0); key("R1", 0); key("R5", 0)
  LOG(("B result: after 3 keys %d->%d, after 4th %d, after releases %d"):format(c0, c3, c4, cnt()))
  relall({})

  LOG("== C extra both-held column 1, then release its DOWN half while the 4 keys stay held")
  c0 = cnt()
  key("C1U", 1); key("C1D", 1)
  key("L1", 1); key("L5", 1); key("R1", 1); key("R5", 1)
  local cc = cnt()
  key("C1D", 0)
  LOG(("C result: with col1 held counter %d->%d (FE0 then 0x110001); after releasing col1 DOWN %d")
    :format(c0, cc, cnt()))
  relall({"L1", "L5", "R1", "R5", "C1U"})

  LOG("== D re-fire while held: tap MUTE UP 1 once")
  key("L1", 1); key("L5", 1); key("R1", 1); key("R5", 1)
  local cd = cnt()
  key("C1U", 1); local cdp = cnt(); key("C1U", 0)
  LOG(("D result: chord -> %d, MUTE UP 1 press -> %d, release -> %d"):format(cd, cdp, cnt()))
  relall({"L1", "L5", "R1", "R5"})

  LOG("== E1 DISPLAY HOLD, PAD 1, PAD 2")
  c0 = cnt()
  key("HOLD", 1); key("PAD1", 1); key("PAD2", 1, false)
  local e1 = cnt()
  LOG("== E3 (continuing) release+re-press PAD 2 with HOLD and PAD 1 still down")
  key("PAD2", 0, false); key("PAD2", 1, false)
  LOG(("E1 result %d->%d ; E3 result %d (expect unchanged) FF0=%X"):format(c0, e1, cnt(), P:read_u32(0x50021FF0)))
  relall({"PAD2", "PAD1", "HOLD"})

  LOG("== E2 PAD 1, PAD 2, then DISPLAY HOLD, then PAD 3")
  c0 = cnt()
  key("PAD1", 1); key("PAD2", 1); key("HOLD", 1)
  local e2a = cnt()
  key("PAD3", 1)
  LOG(("E2 result: FF0 before PAD 3 was 7? counter after HOLD %d->%d ; after PAD 3 %d"):format(c0, e2a, cnt()))
  relall({"PAD3", "PAD2", "PAD1", "HOLD"})

  LOG("done")
  L.mach:exit()
end

L.run(main)
