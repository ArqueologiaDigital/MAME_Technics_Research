-- b2bp2.lua -- trap the per-part send setters at their REAL call entries, log
-- part/level args + caller (mdr). RUN WITH: -debug -debugger none
local function press(p, mm, v)
  local pp = manager.machine.ioport.ports[p]
  for _, f in pairs(pp.fields) do if f.mask == mm then f:set_value(v) end end
end
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local dbg  = mach.debugger
local st, armed, lastlog = 0, false, 0
local bps = {
  {0x4C037D14, "REV_LVL "},   -- row0 level(part d0, lvl d1)
  {0x4C037D47, "REV_CMB "},   -- row0 base+level(part d0, base d1, lvl (0x2c,sp))
  {0x4C037D8C, "CHO_LVL "},   -- chorus level
  {0x4C037DC1, "CHO_CMB "},   -- chorus base+level
  {0x4C037E08, "MUL_LVL "},   -- multi level
  {0x4C037E3C, "MUL_CMB "},   -- multi base+level
}
_G._b2b = emu.add_machine_frame_notifier(function()
  local mt = mach.time
  local t = mt.seconds + mt.attoseconds / 1e18
  if not armed then
    armed = true
    for _, b in ipairs(bps) do
      local act = 'printf "SETTER ' .. b[2] .. ' part=%X d1=%X sparg=%X mdr=%08X", d0, d1, b@(sp+0x2c), mdr ; g'
      cpu.debug:bpset(b[1], "1", act)
    end
    dbg.execution_state = "run"
    emu.print_error("[b2b] armed")
  end
  local cl = dbg.consolelog
  for i = lastlog + 1, #cl do
    local line = tostring(cl[i])
    if line:find("SETTER") then emu.print_error(string.format("[b2b] t=%8.3f %s", t, line)) end
  end
  lastlog = #cl
  local seq = {
    {20.0, ":cpanel:CPR_SEG5", 0x04, 1, "COLD CHORUS"},
    {20.4, ":cpanel:CPR_SEG5", 0x04, 0},
    {23.0, ":cpanel:CPR_SEG4", 0x04, 1, "COLD MULTI"},
    {23.4, ":cpanel:CPR_SEG4", 0x04, 0},
    {26.0, ":cpanel:CPR_SEG3", 0x08, 1, "SOUND DSP refresh"},
    {26.4, ":cpanel:CPR_SEG3", 0x08, 0},
  }
  local step = seq[st + 1]
  if step and t > step[1] then
    st = st + 1
    press(step[2], step[3], step[4])
    if step[5] then emu.print_error(string.format("[b2b] t=%8.3f === %s ===", t, step[5])) end
  end
end)
