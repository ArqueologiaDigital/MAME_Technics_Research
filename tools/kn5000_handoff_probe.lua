-- KN5000: identify the PRODUCER of every group0/bank0 word.
--
-- The +0x000 register takes three kinds of word (0x8100 gate, 0x7E00 free, 0xF0xx/0xFExx
-- "hand-off"). This tap logs each one together with the sub-CPU state that BUILT it, so the
-- word's fields can be attributed to named firmware variables instead of guessed at:
--
--   slot   = 0x04308E + ch*0x47          (voice slot record; the slot index IS the TG channel,
--                                         proven by 0x027338 `muls WA,0x47; (0x0430BB+WA)=0xF000`
--                                         where 0x0430BB = slot base + 0x2D = the hand-off word)
--   part   = slot[+0x04]                 part index 0..0x19
--   p13/p17/p23                          the slot's three record pointers
--   tone0  = *(p17)                      the byte Voice_Build_GateCommand (0x025589) turns into
--                                         the low field: 0xFF - 4*(tone0 & 0x3F), bit8 = tone0!=0
--   prec   = *(0x04136E + part*0x11F)    the part's record pointer
--   prec10 = prec[+0x10]                 its bits 7:6 select which builder runs (0x80 -> the
--                                         BARE twin 0x0255F3, else 0x025589)
--   route  = *(0x04138D + part*0x11F)    the byte Voice_Apply_GateRouting reads (CC 0x9B)
--   pc                                   sub-CPU PC at the store
--
-- Navigation is the same as kn5000_perf_nav.lua / kn5000_tgbus_trace.lua.
-- Env: KN5_TARGET, KN5_T0, KN5_GAP, KN5_HO_T0, KN5_HO_T1, KN5_HOLOG.

local mach = manager.machine
local function T() return mach.time.seconds + mach.time.attoseconds/1e18 end

local TARGET = (os.getenv("KN5_TARGET") or "probe"):lower()
local T0     = tonumber(os.getenv("KN5_T0")  or "12.0")
local GAP    = tonumber(os.getenv("KN5_GAP") or "2.0")
local BT0    = tonumber(os.getenv("KN5_HO_T0") or "22.0")
local BT1    = tonumber(os.getenv("KN5_HO_T1") or "40.0")
local LOG    = os.getenv("KN5_HOLOG") or "/tmp/kn5000_handoff.txt"

local function setbtn(tag, mk, v)
  local port = mach.ioport.ports[":cpanel:" .. tag]
  if not port then emu.print_info("### MISSING PORT " .. tag); return end
  for _, f in pairs(port.fields) do if f.mask == mk then f:set_value(v) end end
end

local seq = {
  { "CPL_SEG3",  0x01, "DEMO" },
  { "CPL_SEG10", 0x01, "LEFT 2 (PERFORMANCES)" },
  { "CPL_SEG9",  0x80, "UP 4" },
}
if TARGET == "piano" then
  seq[#seq+1] = { "CPL_SEG8", 0x02, "RIGHT 2 (PIANO)" }
elseif TARGET == "organ" then
  seq[#seq+1] = { "CPL_SEG7", 0x02, "RIGHT 4 (ORGAN)" }
end

local fh = io.open(LOG, "w")
fh:write("t ch data part prec10 route tone0 p13 p17 p23 pc\n")

local cpu   = mach.devices[":subcpu"]
local space = cpu.spaces["program"]
local latch = 0

local function u8(a)  local ok, v = pcall(function() return space:read_u8(a) end);  return ok and v or -1 end
local function u32(a) local ok, v = pcall(function() return space:read_u32(a) end); return ok and v or -1 end

_G._hotap = space:install_write_tap(0x100000, 0x100003, "handoff", function(offset, data, mask)
  local t = T()
  if t < BT0 or t > BT1 then return end
  if offset == 0x100000 then
    latch = data & 0xFFFF
    return
  end
  if offset ~= 0x100002 then return end
  if latch >= 0x40 then return end          -- group 0 / bank 0 only
  local ch     = latch
  local slot   = 0x04308E + ch * 0x47
  local part   = u8(slot + 0x04)
  local p13    = u32(slot + 0x13) & 0xFFFFFF
  local p17    = u32(slot + 0x17) & 0xFFFFFF
  local p23    = u32(slot + 0x23) & 0xFFFFFF
  local tone0  = (p17 > 0 and p17 < 0x1000000) and u8(p17) or -1
  local prec   = (part >= 0 and part < 0x20) and (u32(0x04136E + part * 0x11F) & 0xFFFFFF) or 0
  local prec10 = (prec > 0 and prec < 0x1000000) and u8(prec + 0x10) or -1
  local route  = (part >= 0 and part < 0x20) and u8(0x04138D + part * 0x11F) or -1
  fh:write(string.format("%.6f %d %04X %d %02X %02X %02X %06X %06X %06X %06X\n",
    t, ch, data & 0xFFFF, part, prec10 & 0xFF, route & 0xFF, tone0 & 0xFF,
    p13, p17, p23, cpu.state["PC"].value))
end)

local tgport = mach.ioport.ports[":TGMODE"]
emu.print_info(string.format("### HANDOFF PROBE target=%s window=[%.1f,%.1f] log=%s",
  TARGET, BT0, BT1, LOG))

local idx, phase, base, sec, closed = 1, "wait", 0.0, 0, false
_G._perfnav = emu.register_frame_done(function()
 pcall(function()
  local t = T()
  if not closed and t > BT1 then fh:flush(); closed = true
    emu.print_info(string.format("### t=%.2f HOLOG FLUSHED", t)) end
  if t >= sec then
    sec = sec + 1
    emu.print_info(string.format("### t=%d phase=%s idx=%d", math.floor(t), phase, idx))
  end
  if phase == "wait" then
    if t >= T0 then phase = "pre"; base = t end
  elseif phase == "pre" then
    if idx > #seq then
      emu.print_info(string.format("### NAV COMPLETE at t=%.2f", t)); phase = "obs"; return
    end
    setbtn(seq[idx][1], seq[idx][2], 1)
    phase = "hold"; base = t
  elseif phase == "hold" then
    if t >= base + 0.30 then setbtn(seq[idx][1], seq[idx][2], 0); phase = "gap"; base = t end
  elseif phase == "gap" then
    if t >= base + GAP then idx = idx + 1; phase = "pre" end
  end
 end)
end)
emu.print_info("### kn5000_handoff_probe.lua loaded")
