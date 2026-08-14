-- KN6000: does the TEXT DRAWER run, and what font pointer does it get?
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local mem  = cpu.spaces["program"]
local dbg  = mach.debugger
local out  = io.open("kn6_txt.log", "w")
local armed, lastlog, counts = false, 0, {}
local bps = {
  {0x484181CF, "TXTDRAW"}, {0x4C0181CF, "aTXTDRAW"},
  {0x4842058B, "FONTH"},   {0x4C02058B, "aFONTH"},
  {0x484205DB, "MEASURE"}, {0x4C0205DB, "aMEASURE"},
  {0x48420312, "FONTINIT"},{0x4C020312, "aFONTINIT"},
}
_G._k6x = emu.add_machine_frame_notifier(function()
  local mt = mach.time
  local t = mt.seconds + mt.attoseconds / 1e18
  if not armed then
    armed = true
    for _, b in ipairs(bps) do
      cpu.debug:bpset(b[1], "1", string.format(
        "printf \"BP %s d0=%%08X d1=%%08X d2=%%08X a0=%%08X a2=%%08X ret=%%08X\", d0,d1,d2,a0,a2,d@(sp) ; g", b[2]))
    end
    dbg.execution_state = "run"
  end
  local cl = dbg.consolelog
  for i = lastlog + 1, #cl do
    local line = tostring(cl[i])
    local tag = line:match("^BP (%S+)")
    if tag then
      counts[tag] = (counts[tag] or 0) + 1
      if counts[tag] <= 8 then out:write(string.format("t=%8.3f %s\n", t, line)) end
    end
  end
  lastlog = #cl
  if t >= 14 and not _G._k6x_done then
    _G._k6x_done = true
    local s = "COUNTS:"
    for k, v in pairs(counts) do s = s .. string.format(" %s=%d", k, v) end
    out:write(s .. "\n")
    out:write(string.format("globals: F658=%08X F65C=%08X F660=%08X F664=%08X F668=%08X\n",
      mem:read_u32(0x5024F658), mem:read_u32(0x5024F65C), mem:read_u32(0x5024F660),
      mem:read_u32(0x5024F664), mem:read_u32(0x5024F668)))
    out:write(string.format("rom 48000200..210: %08X %08X %08X %08X %08X\n",
      mem:read_u32(0x48000200), mem:read_u32(0x48000204), mem:read_u32(0x48000208),
      mem:read_u32(0x4800020C), mem:read_u32(0x48000210)))
    out:flush(); mach:exit()
  end
end)
