-- b2bp.lua -- log args + return addr of the per-part effect-send setters:
--   0x4C037D0F rev-send(part d0, lvl d1)   0x4C037D42 rev-send combined
--   0x4C037D87 chorus  (part d0, lvl d1)   0x4C037DBC chorus combined
--   0x4C037E2E? multi -- trap the write PCs' enclosing entries found by scan.
-- RUN WITH: -debug -debugger none
local function press(p, mm, v)
  local pp = manager.machine.ioport.ports[p]
  if not pp then emu.print_error("[b2b] MISSING PORT " .. p) return end
  for _, f in pairs(pp.fields) do if f.mask == mm then f:set_value(v) end end
end
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local dbg  = mach.debugger
local st = 0
local armed = false
local lastlog = 0
local bps = {
  {0x4C037D11, "REVSND"},
  {0x4C037D44, "REVSND2"},
  {0x4C037D89, "CHORUS"},
  {0x4C037DBE, "CHORUS2"},
}
_G._b2b = emu.add_machine_frame_notifier(function()
  local mt = mach.time
  local t = mt.seconds + mt.attoseconds / 1e18
  if not armed then
    armed = true
    if not cpu.debug then emu.print_error("[b2b] cpu.debug nil") return end
    for _, b in ipairs(bps) do
      cpu.debug:bpset(b[1], "1",
        string.format("printf \"BP %s d0=%%X d1=%%X ret=%%08X\", d0, d1, d@(sp) ; g", b[2]))
    end
    dbg.execution_state = "run"
    emu.print_error("[b2b] breakpoints armed")
  end
  if cpu.debug and dbg then
    local cl = dbg.consolelog
    for i = lastlog + 1, #cl do
      local line = tostring(cl[i])
      if line:find("^BP ") then
        emu.print_error(string.format("[b2b] t=%8.3f %s", t, line))
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
    if step[5] then emu.print_error(string.format("[b2b] t=%8.3f === %s ===", t, step[5])) end
  end
end)
