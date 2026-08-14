-- b1.lua -- B1 unit-feed rewiring verification (chorus->u9, sound-dsp->u2, multi->u1).
-- Effect run: toggle SOUND DSP, CHORUS, MULTI on; hold C4; watch each unit's DSP
-- return slot peak (u0 0xC342 reverb / u1 0xC344 multi / u2 0xC346 sound-dsp /
-- u9 0xC356 chorus) + the feed slots. Set B1_CONTROL=1 in env to skip the effect
-- presses (control run: only reverb should be nonzero).
local control = os.getenv("B1_CONTROL") == "1"
local function press(p, mm, v)
  local pp = manager.machine.ioport.ports[p]
  if not pp then emu.print_error("[b1] MISSING PORT " .. p) return end
  for _, f in pairs(pp.fields) do if f.mask == mm then f:set_value(v) end end
end
local function sx24(v) v = v & 0xFFFFFF; if v >= 0x800000 then v = v - 0x1000000 end; return v end
local st = 0
local peaks = {}   -- addr -> peak abs
local slots = {
  {0xC342, "u0 ret (reverb)"}, {0xC344, "u1 ret (multi)"},
  {0xC346, "u2 ret (sound-dsp)"}, {0xC356, "u9 ret (chorus)"},
  {0xC34A, "u4 ret (old chorus slot)"},
  {0xC362, "u0 in"}, {0xC364, "u1 in"}, {0xC366, "u2 in"}, {0xC376, "u9 in"},
  {0xC36A, "u4 in (old chorus feed)"},
}
for _, s in ipairs(slots) do peaks[s[1]] = 0 end
_G._b1 = emu.add_machine_frame_notifier(function()
  local m = manager.machine
  local t = m.time.seconds + m.time.attoseconds / 1e18
  if st == 0 and t > 18.0 then
    if not control then press(":cpanel:CPR_SEG3", 0x08, 1) end
    st = 1
  elseif st == 1 and t > 18.4 then
    if not control then press(":cpanel:CPR_SEG3", 0x08, 0) end
    st = 2
  elseif st == 2 and t > 19.5 then
    if not control then press(":cpanel:CPR_SEG5", 0x04, 1) end
    st = 3
  elseif st == 3 and t > 19.9 then
    if not control then press(":cpanel:CPR_SEG5", 0x04, 0) end
    st = 4
  elseif st == 4 and t > 21.0 then
    if not control then press(":cpanel:CPR_SEG4", 0x04, 1) end
    st = 5
  elseif st == 5 and t > 21.4 then
    if not control then press(":cpanel:CPR_SEG4", 0x04, 0) end
    st = 6
  elseif st == 6 and t > 23.0 then
    press(":KEYS1", 0x0100, 1)
    st = 7
  elseif st == 7 and t > 26.0 then
    press(":KEYS1", 0x0100, 0)
    st = 8
  elseif st == 8 and t > 29.0 then
    st = 9
    for _, s in ipairs(slots) do
      emu.print_error(string.format("[b1] peak |%s @0x%04X| = %d", s[2], s[1], peaks[s[1]]))
    end
    emu.print_error("[b1] done (control=" .. tostring(control) .. ")")
  end
  if t > 23.0 and t < 29.0 then
    local dsp = m.devices[":dsp"]
    if dsp then
      local dm = dsp.spaces["data"]
      for _, s in ipairs(slots) do
        local ok, v = pcall(function() return dm:read_u32(s[1]) end)
        if ok then
          local a = math.abs(sx24(v))
          if a > peaks[s[1]] then peaks[s[1]] = a end
        end
      end
    end
  end
end)
