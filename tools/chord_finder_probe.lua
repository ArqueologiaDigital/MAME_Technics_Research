-- chord_finder_probe.lua  --  KN7000 CHORD FINDER "ear" navigation + note-on detector
-- Run (NO -debug needed), from the build tree:
--   ./kn7000 kn7000 -rompath roms -video none -seconds_to_run 32 \
--       -autoboot_script /ABS/PATH/chord_finder_probe.lua -autoboot_delay 0
-- Output: emu.print_info lines AND an appended log file (LOGPATH below).
-- What it does: waits for HOME, presses APC MODE, then the CHORD FINDER soft-key,
-- reaches the CHORD FINDER screen, saves a state, then SWEEPS the candidate "ear"
-- buttons one at a time (savestate-reset between each). A TG write-tap reports any
-- non-0xFC voice-register writes (= a note-on reaching the tone generator).

local LOGPATH = "/home/fsanches/compartilhado/kn7000_run/chord_finder_probe.log"
local logf = io.open(LOGPATH, "w")
local function LOG(s)
  emu.print_info(s)
  if logf then logf:write(s.."\n"); logf:flush() end
end

local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local prog = cpu.spaces["program"]
local io   = mach.ioport

------------------------------------------------------------------ button helper
-- Iterate the ioport's fields and match by mask (fields are keyed by name).
local function setbtn(p, mk, v)
  local port = io.ports[":"..p]
  if not port then LOG("!! no port :"..p); return false end
  for _,f in pairs(port.fields) do
    if f.mask == mk then f:set_value(v); return true end
  end
  LOG(("!! no field %s mask %04X"):format(p, mk))
  return false
end

------------------------------------------------------------------ LCD hashing
-- Firmware's composited RGB565 image lives at 0x9CE00000 (640x240) -> plain RAM.
local LCD = 0x9ce00000
local function lcdhash()
  local h = 5381
  for i=0,153599,257 do          -- 640*240 = 153600 u32 words; sparse sample
    local w = prog:read_u32(LCD + i*4)
    h = ((h * 33) + w) & 0xffffffff
  end
  return h
end

------------------------------------------------------------------ TG write-tap
-- MN10300 program space is 32-bit LE, byte-addressed. The ADDRESS latch is the
-- low 16 bits of the word (base+0, mem_mask&0x0000FFFF); the DATA port is the
-- high 16 bits (base+2, mem_mask&0xFFFF0000). Idle refresh uses reg-addr 0xFC0x.
local tg_addr   = {0,0}          -- [1]=main IC201, [2]=sub IC205
local voicehits = 0              -- non-0xFC writes seen in the CURRENT probe window
local idlehits  = 0
local watching  = false          -- only count during a press window

local function make_tap(base, idx, label)
  prog:install_write_tap(base, base+3, "tg"..idx.."tap", function(offset, data, mask)
    if (mask & 0x0000ffff) ~= 0 then            -- low lane -> ADDRESS latch
      tg_addr[idx] = data & 0xffff
    end
    if (mask & 0xffff0000) ~= 0 then            -- high lane -> DATA
      local a = tg_addr[idx]
      local d = (data >> 16) & 0xffff
      if (a & 0xff00) == 0xfc00 then
        idlehits = idlehits + 1                 -- 0xFC0x global refresh = ignore
      elseif watching then
        voicehits = voicehits + 1
        local pc = cpu.state["CURPC"].value
        LOG(("  [TGW] %s reg=%04X data=%04X pc=%08X"):format(label, a, d, pc))
      end
    end
    return nil                                  -- non-destructive: don't alter the write
  end)
end
make_tap(0x98040000, 1, "MAIN/IC201")
make_tap(0x98050000, 2, "SUB/IC205")

------------------------------------------------------------------ nav constants
-- Deliverable-1 mappings (kn7000.cpp INPUT_PORTS_START):
--   APC MODE       = SEG03 0x02  "APC / CHORD FINDER"     (line 1119)
--   CHORD FINDER   = SEG0F 0x40  "LCD RIGHT 5 ..."        (line 1244)  [screen-contextual]
local APC_MODE     = {"SEG03", 0x02}
local CHORD_FINDER = {"SEG0F", 0x40}

-- EAR button: exact ioport bit is NOT established (panel board-decode for the
-- bottom "balance" soft-key row is unresolved). Candidates = the bottom balance
-- buttons from notes/panel-descriptor-map.md (rightmost first). The TG-tap tells
-- us which one is the ear: the one that emits a burst of non-0xFC voice writes.
local EAR_CANDIDATES = {
  {"SEG11", 0x02},   -- Balance/Ctrl 2 (ev2008 a2) -- rightmost of the 2008 group
  {"SEG0E", 0x01},   -- Balance/Ctrl 2 (ev2009 a2)
  {"SEG10", 0x02},   -- Balance/Ctrl 1 (ev2008 a1)
  {"SEG0E", 0x02},   -- Balance/Ctrl 1 (ev2009 a1)
  {"SEG0F", 0x02},   -- Balance/Ctrl 0 (ev2008 a0)
  {"SEG0D", 0x02},   -- Balance/Ctrl 0 (ev2009 a0)
}

local HOLD = 30      -- frames to hold a press (>=14 required by the 250Hz scan)

------------------------------------------------------------------ schedule
local frame  = 0
local cand   = 0                 -- index into EAR_CANDIDATES currently under test
local plan   = {}                -- {frame -> fn}
local function at(f, fn) plan[f] = fn end

-- Phase 1: navigate to CHORD FINDER, save a state there.
at( 60, function() LOG(("t=%.1fs HOME hash=%08X"):format(frame/60, lcdhash())) end)
at(1020, function()
  LOG(("t=%.1fs press APC MODE (%s %02X)"):format(frame/60, APC_MODE[1], APC_MODE[2]))
  setbtn(APC_MODE[1], APC_MODE[2], 1) end)
at(1020+HOLD, function() setbtn(APC_MODE[1], APC_MODE[2], 0) end)
at(1085, function() LOG(("t=%.1fs APC SELECT? hash=%08X"):format(frame/60, lcdhash())) end)
at(1090, function()
  LOG(("t=%.1fs press CHORD FINDER (%s %02X)"):format(frame/60, CHORD_FINDER[1], CHORD_FINDER[2]))
  setbtn(CHORD_FINDER[1], CHORD_FINDER[2], 1) end)
at(1090+HOLD, function() setbtn(CHORD_FINDER[1], CHORD_FINDER[2], 0) end)
at(1160, function()
  LOG(("t=%.1fs CHORD FINDER? hash=%08X  -- saving state 'cf'"):format(frame/60, lcdhash()))
  mach:save("cf") end)

-- Phase 2: sweep the ear candidates. Each cycle: load 'cf', press candidate,
-- watch the tap for ~30 frames, report. 120-frame budget per candidate.
local SWEEP_START = 1240
local PER = 120
for i=1,#EAR_CANDIDATES do
  local base = SWEEP_START + (i-1)*PER
  local c = EAR_CANDIDATES[i]
  at(base, function() mach:load("cf") end)                     -- reset to CF screen
  at(base+30, function()
      cand = i; voicehits = 0; watching = true
      LOG(("t=%.1fs [cand %d] press EAR? %s %02X (hash=%08X)")
          :format(frame/60, i, c[1], c[2], lcdhash()))
      setbtn(c[1], c[2], 1) end)
  at(base+30+HOLD, function() setbtn(c[1], c[2], 0) end)
  at(base+PER-5, function()
      watching = false
      LOG(("t=%.1fs [cand %d] %s %02X -> %d non-FC voice writes  hash=%08X %s")
          :format(frame/60, i, c[1], c[2], voicehits, lcdhash(),
                  voicehits>0 and "  <<< NOTE-ON FIRED" or ""))
      end)
end
at(SWEEP_START + #EAR_CANDIDATES*PER + 10, function()
  LOG(("DONE. idle(0xFC0x) writes seen total=%d"):format(idlehits))
  if logf then logf:close() end
end)

------------------------------------------------------------------ driver
emu.add_machine_frame_notifier(function()
  frame = frame + 1
  local fn = plan[frame]
  if fn then fn() end
end)
LOG("chord_finder_probe.lua armed")
