-- timbre_tap.lua -- capture the IC303 note-on register burst for four DIFFERENT
-- PITCH CLASSES on the default RIGHT1 sound (Piano), to test two predictions of the
-- traced note-on builder chain:
--   P1: +0x080 bits[14:12] = LUT_00FBE4[key] = floor(2*(key%12)/3)  (C=0 E=2 G=4 A=6)
--   P2: +0x100 = 0x2400 | V, V = clamp(VP[0x4d]+kf*KS[curve][k']/32+vel*..+0x18, 0, 0x78)
-- Notes: C4 (MIDI 60, raw 24 = KEY2 bit0), E4 (64, KEY2 bit4), G4 (67, KEY2 bit7),
--        A4 (69, KEY2 bit9).
local function press(p, mm, v)
  local pp = manager.machine.ioport.ports[p]
  if not pp then emu.print_error("[tt] MISSING PORT " .. p) return end
  for _, f in pairs(pp.fields) do if f.mask == mm then f:set_value(v) end end
end
local function now()
  local mt = manager.machine.time
  return mt.seconds + mt.attoseconds / 1e18
end
local latch = 0
local logging = false
local tag = ""
_G._ttk = _G._ttk or {}
local installed = false
local st = 0
local seq = {
  {t = 22.0, port = ":KEY2", mask = 0x0001, name = "C4"},
  {t = 25.0, port = ":KEY2", mask = 0x0010, name = "E4"},
  {t = 28.0, port = ":KEY2", mask = 0x0080, name = "G4"},
  {t = 31.0, port = ":KEY2", mask = 0x0200, name = "A4"},
}
local idx = 1

_G._tt = emu.add_machine_frame_notifier(function()
  local m = manager.machine
  local t = now()
  if not installed and t > 18.0 then
    installed = true
    local prog = m.devices[":subcpu"].spaces["program"]
    _G._ttk[1] = prog:install_write_tap(0x100000, 0x100001, "ttaddr", function(off, data, mask)
      latch = data & 0xFFFF
    end)
    _G._ttk[2] = prog:install_write_tap(0x100002, 0x100003, "ttdata", function(off, data, mask)
      if not logging then return end
      local a = latch
      local ch = a & 0x3F
      if ch > 3 then return end          -- only the first few voices
      if a >= 0x600 and a < 0x800 then return end
      emu.print_error(string.format("[tt] %s ch=%d reg=+%03X = %04X", tag, ch, a & 0xFFC0, data & 0xFFFF))
    end)
    emu.print_error("[tt] taps installed")
  end
  if installed and idx <= #seq then
    local s = seq[idx]
    if st == 0 and t > s.t then
      tag = s.name; logging = true
      press(s.port, s.mask, 1)
      st = 1
    elseif st == 1 and t > s.t + 0.25 then
      logging = false
      st = 2
    elseif st == 2 and t > s.t + 1.2 then
      press(s.port, s.mask, 0)
      st = 0
      idx = idx + 1
    end
  end
end)
