-- sanity: bp on TgVoiceRegWrite_entry (hot on any TG write) + dump ALL console lines
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local dbg  = mach.debugger
local armed = false
local lastlog = 0
_G._b2d = emu.add_machine_frame_notifier(function()
  local mt = mach.time
  local t = mt.seconds + mt.attoseconds / 1e18
  if not armed then
    armed = true
    if not cpu.debug then emu.print_error("[b2d] cpu.debug nil") return end
    local ok, err = pcall(function()
      cpu.debug:bpset(0x4C036F9A, "1", "printf \"BP TGWR d0=%X d1=%X ret=%08X\", d0, d1, d@(sp) ; g")
    end)
    emu.print_error("[b2d] bpset ok=" .. tostring(ok) .. " err=" .. tostring(err))
    dbg.execution_state = "run"
  end
  if cpu.debug and dbg then
    local cl = dbg.consolelog
    for i = lastlog + 1, #cl do
      emu.print_error(string.format("[b2d] CL t=%.3f |%s|", t, tostring(cl[i])))
    end
    lastlog = #cl
  end
end)
