-- KN5000 DEMO -> PERFORMANCES -> SOUND -> {PIANO|ORGAN} navigation, scripted.
--
-- Felipe's path, from the top:
--   DEMO -> PERFORMANCES (LCD LEFT 2) -> SOUND (MUTE PART UP 4 or UP 5)
--   -> then PIANO (LCD RIGHT 2) or ORGAN (LCD RIGHT 4).
--
-- Panel bits are read straight off kn5000_cpanel.cpp's PORT_NAMEs (the authoritative
-- physical scan-matrix names):
--   DEMO    = CPL_SEG3  0x01
--   LEFT 2  = CPL_SEG10 0x01
--   UP 4    = CPL_SEG9  0x80      UP 5 = CPL_SEG8 0x20
--   RIGHT 2 = CPL_SEG8  0x02      RIGHT 4 = CPL_SEG7 0x02
--
-- A SNAPSHOT is taken immediately before and ~0.8 s after every press, so the run
-- carries its own proof of which screen each press was issued on. Nothing here reads
-- or writes emulated state other than the buttons.
--
-- env:
--   KN5_TARGET = piano | organ | probe   (probe = walk the menu, press nothing at the end)
--   KN5_T0     = seconds to wait before the first press (default 12)
--   KN5_GAP    = seconds between presses (default 2.0)
--   KN5_UP     = 4 | 5  (which MUTE PART UP selects SOUND; default 4)

local mach = manager.machine
local V    = mach.video
local function T() return mach.time.seconds + mach.time.attoseconds/1e18 end

local TARGET = (os.getenv("KN5_TARGET") or "probe"):lower()
local T0     = tonumber(os.getenv("KN5_T0")  or "12.0")
local GAP    = tonumber(os.getenv("KN5_GAP") or "2.0")
local UPSEL  = (os.getenv("KN5_UP") or "4")

local function setbtn(tag, mk, v)
  local port = mach.ioport.ports[":cpanel:" .. tag]
  if not port then emu.print_info("### MISSING PORT " .. tag); return end
  for _, f in pairs(port.fields) do if f.mask == mk then f:set_value(v) end end
end

-- the press list, built from the target
local UPBTN = (UPSEL == "5") and { "CPL_SEG8", 0x20, "UP 5" } or { "CPL_SEG9", 0x80, "UP 4" }
local seq = {
  { "CPL_SEG3",  0x01, "DEMO" },
  { "CPL_SEG10", 0x01, "LEFT 2 (PERFORMANCES)" },
  UPBTN,
}
if TARGET == "piano" then
  seq[#seq+1] = { "CPL_SEG8", 0x02, "RIGHT 2 (PIANO)" }
elseif TARGET == "organ" then
  seq[#seq+1] = { "CPL_SEG7", 0x02, "RIGHT 4 (ORGAN)" }
end

-- Extra SNAPSHOT TIMES (absolute emulated seconds), comma-separated. The +0.8 s
-- post-press snapshot catches the press but NOT the selection highlight: measured, the
-- LCD draws the orange box around the chosen performance a few seconds later. So the
-- proof-of-screen for a capture run has to be taken during playback, not at the press.
local snaps = {}
for s in (os.getenv("KN5_SNAPS") or ""):gmatch("[^,]+") do snaps[#snaps+1] = tonumber(s) end
table.sort(snaps)
local snapi = 1

local tgport = mach.ioport.ports[":TGMODE"]
emu.print_info(string.format("### NAV target=%s up=%s T0=%.1f GAP=%.1f TGMODE=%s",
  TARGET, UPSEL, T0, GAP, tgport and string.format("0x%02X", tgport:read()) or "MISSING"))

local idx, phase, base, sec = 1, "wait", 0.0, 0
_G._perfnav = emu.register_frame_done(function()
 pcall(function()
  local t = T()
  while snapi <= #snaps and t >= snaps[snapi] do
    V:snapshot()
    emu.print_info(string.format("### t=%.2f SNAP-TIMED (%.1f)", t, snaps[snapi]))
    snapi = snapi + 1
  end
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
    V:snapshot()
    emu.print_info(string.format("### t=%.2f SNAP-BEFORE press %d/%d = %s",
      t, idx, #seq, seq[idx][3]))
    setbtn(seq[idx][1], seq[idx][2], 1)
    phase = "hold"; base = t
  elseif phase == "hold" then
    if t >= base + 0.30 then
      setbtn(seq[idx][1], seq[idx][2], 0)
      emu.print_info(string.format("### t=%.2f RELEASED %s", t, seq[idx][3]))
      phase = "settle"; base = t
    end
  elseif phase == "settle" then
    if t >= base + 0.80 then
      V:snapshot()
      emu.print_info(string.format("### t=%.2f SNAP-AFTER %s", t, seq[idx][3]))
      phase = "gap"; base = t
    end
  elseif phase == "gap" then
    if t >= base + GAP then idx = idx + 1; phase = "pre" end
  end
 end)
end)
emu.print_info("### kn5000_perf_nav.lua loaded")
