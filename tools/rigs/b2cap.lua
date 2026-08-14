-- b2cap.lua -- B2 depth-bank capture: log EVERY group-0x20 (effect-bus) TG write
-- while toggling CHORUS/MULTI cold vs after a SOUND-DSP refresh.
-- Sequence: t=20 cold CHORUS on; t=23 cold MULTI on; t=26 SOUND DSP on (refresh);
-- t=29 CHORUS off; t=31 CHORUS on (post-refresh); t=33 MULTI off; t=35 MULTI on.
local function press(p, mm, v)
  local pp = manager.machine.ioport.ports[p]
  if not pp then emu.print_error("[b2] MISSING PORT " .. p) return end
  for _, f in pairs(pp.fields) do if f.mask == mm then f:set_value(v) end end
end
local st = 0
local installed = false
local latch = { [0]=0, [1]=0 }
_G._b2k = _G._b2k or {}
local function now()
  local mt = manager.machine.time
  return mt.seconds + mt.attoseconds / 1e18
end
local function mktap(prog, base, tgi, name)
  return prog:install_write_tap(base, base + 3, name, function(off, data, mask)
    if (mask & 0x0000FFFF) ~= 0 then
      latch[tgi] = data & 0xFFFF
    end
    if (mask & 0xFFFF0000) ~= 0 then
      local val = (data >> 16) & 0xFFFF
      local a = latch[tgi]
      if (a & 0xFC00) == 0x8000 then
        emu.print_error(string.format("[b2] t=%8.3f tg%d GRP20 ch=%02X reg=%X data=%04X",
          now(), tgi, (a >> 4) & 0x3F, a & 0xF, val))
      end
    end
  end)
end
_G._b2 = emu.add_machine_frame_notifier(function()
  local m = manager.machine
  local t = now()
  if not installed and t > 16.0 then
    installed = true
    local prog = m.devices[":maincpu"].spaces["program"]
    _G._b2k[1] = mktap(prog, 0x98040000, 0, "b2tg0")
    _G._b2k[2] = mktap(prog, 0x98050000, 1, "b2tg1")
    emu.print_error("[b2] taps installed t=" .. string.format("%.2f", t))
  end
  local seq = {
    {20.0, ":cpanel:CPR_SEG5", 0x04, 1, "COLD CHORUS press"},
    {20.4, ":cpanel:CPR_SEG5", 0x04, 0, nil},
    {23.0, ":cpanel:CPR_SEG4", 0x04, 1, "COLD MULTI press"},
    {23.4, ":cpanel:CPR_SEG4", 0x04, 0, nil},
    {26.0, ":cpanel:CPR_SEG3", 0x08, 1, "SOUND DSP press (refresh)"},
    {26.4, ":cpanel:CPR_SEG3", 0x08, 0, nil},
    {29.0, ":cpanel:CPR_SEG5", 0x04, 1, "CHORUS press (off, post-refresh)"},
    {29.4, ":cpanel:CPR_SEG5", 0x04, 0, nil},
    {31.0, ":cpanel:CPR_SEG5", 0x04, 1, "CHORUS press (on, post-refresh)"},
    {31.4, ":cpanel:CPR_SEG5", 0x04, 0, nil},
    {33.0, ":cpanel:CPR_SEG4", 0x04, 1, "MULTI press (off, post-refresh)"},
    {33.4, ":cpanel:CPR_SEG4", 0x04, 0, nil},
    {35.0, ":cpanel:CPR_SEG4", 0x04, 1, "MULTI press (on, post-refresh)"},
    {35.4, ":cpanel:CPR_SEG4", 0x04, 0, nil},
  }
  local step = seq[st + 1]
  if step and t > step[1] then
    st = st + 1
    press(step[2], step[3], step[4])
    if step[5] then emu.print_error(string.format("[b2] t=%8.3f === %s ===", t, step[5])) end
  end
end)
