-- timbre_tap2.lua -- as timbre_tap.lua but covering voices 0..15 (so G4/A4 are seen) and
-- dumping the sub-CPU RAM inputs of the traced +0x100 builder, so the arithmetic can be
-- checked with NO free parameters:
--   PART0[+0x67] @ 0x041368+0x67 = 0x0413CF   (the per-part offset added to the base)
--   slot[+0x0c]  @ 0x04308E+ch*0x47+0x0c      (the key the key-scale curve is indexed by)
--   slot[+0x08]  @ 0x04308E+ch*0x47+0x08      (the velocity word, bits 14:8)
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
local seen = {}
_G._ttk = _G._ttk or {}
local installed = false
local st = 0
local seq = {
  {t = 22.0, port = ":KEY2", mask = 0x0001, name = "C4"},
  {t = 25.0, port = ":KEY2", mask = 0x0010, name = "E4"},
  {t = 28.0, port = ":KEY2", mask = 0x0080, name = "G4"},
  {t = 31.0, port = ":KEY2", mask = 0x0200, name = "A4"},
  {t = 34.0, port = ":KEY0", mask = 0x0001, name = "C2"},
  {t = 37.0, port = ":KEY4", mask = 0x0001, name = "C6"},
}
local idx = 1

_G._tt = emu.add_machine_frame_notifier(function()
  local m = manager.machine
  local t = now()
  if not installed and t > 18.0 then
    installed = true
    local prog = m.devices[":subcpu"].spaces["program"]
    _G._prog = prog
    _G._ttk[1] = prog:install_write_tap(0x100000, 0x100001, "ttaddr", function(off, data, mask)
      latch = data & 0xFFFF
    end)
    _G._ttk[2] = prog:install_write_tap(0x100002, 0x100003, "ttdata", function(off, data, mask)
      if not logging then return end
      local a = latch
      local ch = a & 0x3F
      local reg = a & 0xFFC0
      if ch > 15 then return end
      if reg == 0x040 or reg == 0x080 or reg == 0x0C0 or reg == 0x100 or reg == 0x140
         or reg == 0x400 or reg == 0x500 or reg == 0x800 then
        emu.print_error(string.format("[tt] %s ch=%2d reg=+%03X = %04X", tag, ch, reg, data & 0xFFFF))
        seen[ch] = true
      end
    end)
    emu.print_error("[tt] taps installed")
  end
  if installed and idx <= #seq then
    local s = seq[idx]
    if st == 0 and t > s.t then
      tag = s.name; logging = true; seen = {}
      press(s.port, s.mask, 1)
      st = 1
    elseif st == 1 and t > s.t + 0.25 then
      logging = false
      -- dump the RAM inputs for every voice that keyed on in this burst
      local p = _G._prog
      local p67 = p:read_u8(0x0413CF)
      for ch = 0, 15 do
        if seen[ch] then
          local b = 0x04308E + ch * 0x47
          emu.print_error(string.format("[tt] %s RAM ch=%2d key(slot+0c)=%3d vel(slot+08)=%04X part0[+67]=%d(%d)",
            tag, ch, p:read_u8(b + 0x0C), p:read_u16(b + 0x08), p67, (p67 >= 128) and (p67 - 256) or p67))
        end
      end
      st = 2
    elseif st == 2 and t > s.t + 1.2 then
      press(s.port, s.mask, 0)
      st = 0
      idx = idx + 1
    end
  end
end)
