-- aw_intro.lua -- Another World's intro for listening (README.md here): boot, the program menu, the game, its sample
-- bank, then AWI_LEN emulated seconds of the intro with no input, and exit.
-- rig-machine: kn7000 (-bios v13, program 893), the card build of technics-roms-disasm kn7000/tools/kn7menu/build/card
-- (the menu as the card's root KN7APP.BIN, the game in AW\ with KN7APP.BIN 94910f68...), the owner's loader floppy.
-- The menu route, the bank wait and every address are technics-anotherworld kn7000/probes/cnv/awcnv_round3.lua's
-- (the same game build), cut down to what the intro needs.
--   AWI_OUT   log folder: AWI_OUT/events.txt; AWI_OUT/intro_mark is created (empty) the moment the intro starts, so the
--             runner can note the host's wall clock for a live capture
--   AWI_MODE  "dsp" (the game's own samples on the effects DSP, its default) or "tg" (PART SELECT RIGHT 2 pressed once
--             as the intro starts: the music as MIDI to the instrument's own voices)
--   AWI_LEN   emulated seconds of intro to run before exiting (default 64)
-- Logs: the game's sound mode (DV_MODE: 0 DSP, 1 tone generator, 2 off) before and after the press and at the
-- intro's start, the emulated time of the intro's start (the intro is the game's part 0x3E81), and every emulated
-- second the emulation speed (emulated / wall, from emu.osd_ticks()), as passage.lua does.
local M = manager.machine
local sp = M.devices[":maincpu"].spaces["program"]
local OUT = assert(os.getenv("AWI_OUT"), "set AWI_OUT")
local MODE = os.getenv("AWI_MODE") or "dsp"
local LEN = tonumber(os.getenv("AWI_LEN") or "64")
local DEAD, PANEL = 0x500066D8, 0x5006BE4C
local CV, INTERP, MISC = 0x502DF000, 0x502E1000, 0x502E3000
local CV_STATE, PART, NO_SPLASH = CV, INTERP + 0x102A, MISC + 0x58
local DH = 0x502DA600
local DV_MODE, DV_HOOKED = DH + 0x60, DH + 0x54
local MV, V_NPROG, ORDER, PR_NAME = 0x502C0000, 0x502C0034, 0x502C3800, 0x40

local function now() return M.time:as_double() end
local ev = assert(io.open(OUT .. "/events.txt", "w"))
local function E(...) local s = string.format("%8.2f ", now()) .. string.format(...); ev:write(s, "\n"); ev:flush() end
local function cstr(a, n)
  local s = ""
  for i = 0, (n or 64) - 1 do local c = sp:read_u8(a + i); if c == 0 then break end; s = s .. string.char(c) end
  return s
end
local function field(tag, mask)
  local p = M.ioport.ports[":cpanel:" .. tag] or M.ioport.ports[":" .. tag]
  for _, f in pairs(p.fields) do if f.mask == mask then return f end end
end
local function wait(s) local t = now() + s; while now() < t do coroutine.yield() end end
local function wait_until(cond, s) local t = now() + s; while now() < t do if cond() then return true end; coroutine.yield() end; return cond() end
local function press(tag, mask, hold)
  local f = field(tag, mask)
  local seg = tonumber(tag:match("SEG(%d+)"))
  local byte = PANEL + seg + (tag:sub(1, 3) == "CPR" and 0 or 0x30)
  for try = 1, 6 do
    f:set_value(1)
    if wait_until(function() return (sp:read_u8(byte) & mask) ~= 0 end, 1.0) then
      wait(hold or 0.4); f:set_value(0); return true
    end
    f:set_value(0); E("press %s %02X not seen (try %d): again", tag, mask, try); wait(1.5)
  end
  return false
end

local function to_converter()
  press("CPR_SEG1", 0x04); wait(6)                     -- DISK MENU
  press("CPL_SEG0", 0x20); wait(8)                     -- STYLE CONVERT
  for i = 1, 8 do
    press("CPR_SEG6", 0x01)                            -- OK: KN7LOAD.CNV from the floppy
    if wait_until(function() return sp:read_u32(0x502B9E00) == 0x53374E4B end, 20) then break end
    E("OK %d not taken; again", i)
  end
end
local function run_aw()
  local ok = wait_until(function() return sp:read_u32(MV) == 4 and cstr(0x502BA020, 32) ~= "ANOTHER WORLD" end, 150)
  local n, idx = sp:read_u32(V_NPROG), nil
  for i = 0, n - 1 do if cstr(sp:read_u32(ORDER + 4 * i) + PR_NAME) == "Another World" then idx = idx or i end end
  E("menu: %s, %d programs, Another World at %s", ok and "up" or "NOT UP", n, tostring(idx))
  if not idx then return false end
  for _ = 1, idx // 5 do press("CPR_SEG5", 0x20); wait(1) end
  press("CPL_SEG0", ({ 0x02, 0x08, 0x20, 0x01, 0x04 })[idx % 5 + 1]); wait(1)
  press("CPR_SEG5", 0x01)
  ok = wait_until(function() return cstr(0x502BA020, 32) == "ANOTHER WORLD" end, 30)
  E("RUN: %q at APP_BASE", cstr(0x502BA020, 32))
  return ok
end

local tps = emu.osd_ticks_per_second()
local last_s, last_tick, speed_on, done = nil, nil, false, false
local co = coroutine.create(function()
  wait_until(function() return now() > 30 end, 60)
  E("boot: dead %d", sp:read_u8(DEAD))
  to_converter()
  if not run_aw() then E("ERROR: the game did not start"); return end
  wait_until(function() return sp:read_u32(CV_STATE) >= 2 end, 120)
  sp:write_u32(NO_SPLASH, 0x5EED0FF0)
  wait_until(function() return sp:read_u32(CV_STATE) == 3 end, 600)
  E("bank sent; game sound mode %d, hooked %d", sp:read_u32(DV_MODE), sp:read_u32(DV_HOOKED))
  wait_until(function() return sp:read_u16(PART) == 0x3E81 end, 60)
  local f = io.open(OUT .. "/intro_mark", "w"); if f then f:close() end
  speed_on = true
  local t0 = now()
  E("INTRO START part %04X, game sound mode %d, hooked %d, dead %d", sp:read_u16(PART), sp:read_u32(DV_MODE),
    sp:read_u32(DV_HOOKED), sp:read_u8(DEAD))
  if MODE == "tg" then
    -- The game reads RIGHT 2 only once its loop runs: pressed between the bank's end and the intro (80.7-84.0 s,
    -- 2026-10-21) the panel saw it and the mode stayed 0. So it is pressed here, as the intro starts.
    press("CPR_SEG2", 0x02, 0.3)                       -- PART SELECT RIGHT 2: DSP -> tone generator
    wait_until(function() return sp:read_u32(DV_MODE) == 1 end, 3)
    E("TG SWITCH RIGHT 2 pressed: game sound mode %d (1 = tone generator)", sp:read_u32(DV_MODE))
  end
  wait(LEN - (now() - t0))
  E("END part %04X, game sound mode %d, dead %d", sp:read_u16(PART), sp:read_u32(DV_MODE), sp:read_u8(DEAD))
end)
AWI_TICK = emu.add_machine_frame_notifier(function()
  local t = now()
  local s = math.floor(t)
  if last_s == nil then last_s, last_tick = s, emu.osd_ticks()
  elseif s > last_s then
    local tk = emu.osd_ticks()
    if speed_on then E("SPEED pct=%.1f", 100.0 * (s - last_s) * tps / (tk - last_tick)) end
    last_s, last_tick = s, tk
  end
  if coroutine.status(co) ~= "dead" then
    local ok, err = coroutine.resume(co)
    if not ok then E("ERROR %s", tostring(err)) end
  elseif not done then
    done = true; ev:close(); M:exit()
  end
end)
E("installed (mode %s, %d s of intro)", MODE, LEN)
