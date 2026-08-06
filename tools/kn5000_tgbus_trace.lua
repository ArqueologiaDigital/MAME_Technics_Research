-- KN5000: navigate to a DEMO PERFORMANCE and trace the RAW tone-generator bus.
--
-- Same navigation as kn5000_perf_nav.lua, plus a write tap on the sub-CPU's
-- 0x100000..0x100003 window (address latch / data). Every (t, addr, data) pair is
-- appended to KN5_BUSLOG so the ORDER of the note-on burst can be read directly,
-- instead of being inferred from the tone generator's own end-of-burst snapshot.
--
-- Only writes in [KN5_BUS_T0, KN5_BUS_T1] are logged, and only for channels in
-- KN5_BUS_CH (comma list, empty = all), so the file stays small.

local mach = manager.machine
local V    = mach.video
local function T() return mach.time.seconds + mach.time.attoseconds/1e18 end

local TARGET = (os.getenv("KN5_TARGET") or "probe"):lower()
local T0     = tonumber(os.getenv("KN5_T0")  or "12.0")
local GAP    = tonumber(os.getenv("KN5_GAP") or "2.0")
local BT0    = tonumber(os.getenv("KN5_BUS_T0") or "30.0")
local BT1    = tonumber(os.getenv("KN5_BUS_T1") or "31.0")
local LOG    = os.getenv("KN5_BUSLOG") or "/tmp/kn5000_buslog.txt"

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
fh:write("# t addr data  (raw tone-generator bus writes)\n")

local space = mach.devices[":subcpu"].spaces["program"]
local latch = 0
-- Held in a GLOBAL: a tap that is only a local is silently reaped by the GC.
_G._tgtap = space:install_write_tap(0x100000, 0x100003, "tgbus", function(offset, data, mask)
  local t = T()
  if t < BT0 or t > BT1 then return end
  if offset == 0x100000 then
    latch = data & 0xFFFF
  elseif offset == 0x100002 then
    fh:write(string.format("%.6f %04X %04X\n", t, latch, data & 0xFFFF))
  end
end)

local tgport = mach.ioport.ports[":TGMODE"]
emu.print_info(string.format("### BUSTRACE target=%s window=[%.1f,%.1f] log=%s TGMODE=%s",
  TARGET, BT0, BT1, LOG, tgport and string.format("0x%02X", tgport:read()) or "MISSING"))

local idx, phase, base, sec, closed = 1, "wait", 0.0, 0, false
_G._perfnav = emu.register_frame_done(function()
 pcall(function()
  local t = T()
  if not closed and t > BT1 then fh:flush(); closed = true
    emu.print_info(string.format("### t=%.2f BUSLOG FLUSHED", t)) end
  if t >= sec then
    sec = sec + 1
    emu.print_info(string.format("### t=%d TGMODE=0x%02X phase=%s idx=%d", math.floor(t),
      tgport and tgport:read() or 255, phase, idx))
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
    if t >= base + 0.30 then
      setbtn(seq[idx][1], seq[idx][2], 0)
      phase = "gap"; base = t
    end
  elseif phase == "gap" then
    if t >= base + GAP then idx = idx + 1; phase = "pre" end
  end
 end)
end)
emu.print_info("### kn5000_tgbus_trace.lua loaded")
