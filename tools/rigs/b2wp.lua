-- b2wp.lua -- watchpoint on the per-part depth shadow block 0x500CE340..47 to
-- catch the writer PCs across cold toggles + the SOUND-DSP refresh.
-- RUN WITH: -debug -debugger none
local function press(p, mm, v)
  local pp = manager.machine.ioport.ports[p]
  if not pp then emu.print_error("[b2w] MISSING PORT " .. p) return end
  for _, f in pairs(pp.fields) do if f.mask == mm then f:set_value(v) end end
end
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local dbg  = mach.debugger
local st = 0
local armed = false
local lastlog = 0
_G._b2w = emu.add_machine_frame_notifier(function()
  local mt = mach.time
  local t = mt.seconds + mt.attoseconds / 1e18
  if not armed then
    armed = true
    if not cpu.debug then emu.print_error("[b2w] cpu.debug nil -- need -debug -debugger none") return end
    cpu.debug:wpset(cpu.spaces["program"], "w", 0x500CE340, 8,
      "1", "printf \"WPHIT a=%08X d=%08X pc=%08X\", wpaddr, wpdata, pc ; g")
    dbg.execution_state = "run"
    emu.print_error("[b2w] watchpoint armed")
  end
  -- drain new console lines
  if cpu.debug and dbg then
    local cl = dbg.consolelog
    for i = lastlog + 1, #cl do
      local line = tostring(cl[i])
      if line:find("WPHIT") then
        emu.print_error(string.format("[b2w] t=%8.3f %s", t, line))
      end
    end
    lastlog = #cl
  end
  local seq = {
    {20.0, ":cpanel:CPR_SEG5", 0x04, 1, "COLD CHORUS"},
    {20.4, ":cpanel:CPR_SEG5", 0x04, 0, nil},
    {23.0, ":cpanel:CPR_SEG4", 0x04, 1, "COLD MULTI"},
    {23.4, ":cpanel:CPR_SEG4", 0x04, 0, nil},
    {26.0, ":cpanel:CPR_SEG3", 0x08, 1, "SOUND DSP refresh"},
    {26.4, ":cpanel:CPR_SEG3", 0x08, 0, nil},
  }
  local step = seq[st + 1]
  if step and t > step[1] then
    st = st + 1
    press(step[2], step[3], step[4])
    if step[5] then emu.print_error(string.format("[b2w] t=%8.3f === %s ===", t, step[5])) end
  end
end)
