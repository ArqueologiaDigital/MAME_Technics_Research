-- b2ab.lua -- B2 verification: COLD chorus+multi toggles (NO sound-dsp interaction)
-- must now feed/produce on u9/u1. B2_CONTROL=1 skips the presses.
local control = os.getenv("B2_CONTROL") == "1"
local function press(p, mm, v)
  local pp = manager.machine.ioport.ports[p]
  for _, f in pairs(pp.fields) do if f.mask == mm then f:set_value(v) end end
end
local function sx24(v) v = v & 0xFFFFFF; if v >= 0x800000 then v = v - 0x1000000 end; return v end
local st = 0
local peaks = {}
local slots = {
  {0xC342, "u0 ret (reverb)"}, {0xC344, "u1 ret (multi)"},
  {0xC346, "u2 ret (sound-dsp)"}, {0xC356, "u9 ret (chorus)"},
  {0xC364, "u1 in"}, {0xC376, "u9 in"},
}
for _, s in ipairs(slots) do peaks[s[1]] = 0 end
_G._b2a = emu.add_machine_frame_notifier(function()
  local m = manager.machine
  local t = m.time.seconds + m.time.attoseconds / 1e18
  local seq = {
    {18.0, ":cpanel:CPR_SEG5", 0x04, 1},  -- COLD CHORUS on
    {18.4, ":cpanel:CPR_SEG5", 0x04, 0},
    {20.0, ":cpanel:CPR_SEG4", 0x04, 1},  -- COLD MULTI on
    {20.4, ":cpanel:CPR_SEG4", 0x04, 0},
  }
  local step = seq[st + 1]
  if step and st < 4 then
    if t > step[1] then
      st = st + 1
      if not control then press(step[2], step[3], step[4]) end
    end
  elseif st == 4 and t > 23.0 then
    press(":KEYS1", 0x0100, 1); st = 5
  elseif st == 5 and t > 26.0 then
    press(":KEYS1", 0x0100, 0); st = 6
  elseif st == 6 and t > 29.0 then
    st = 7
    for _, s in ipairs(slots) do
      emu.print_error(string.format("[b2a] peak |%s @0x%04X| = %d", s[2], s[1], peaks[s[1]]))
    end
    emu.print_error("[b2a] done (control=" .. tostring(control) .. ")")
  end
  if t > 23.0 and t < 29.0 then
    local dsp = m.devices[":dsp"]
    if dsp then
      local dm = dsp.spaces["data"]
      for _, s in ipairs(slots) do
        local ok, v = pcall(function() return dm:read_u32(s[1]) end)
        if ok then local a = math.abs(sx24(v)); if a > peaks[s[1]] then peaks[s[1]] = a end end
      end
    end
  end
end)
