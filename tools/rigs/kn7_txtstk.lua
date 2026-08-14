local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local dbg  = mach.debugger
local out  = io.open("kn7_txtstk.log", "w")
local armed, lastlog, n = false, 0, 0
_G._k7s = emu.add_machine_frame_notifier(function()
  local mt = mach.time
  local t = mt.seconds + mt.attoseconds / 1e18
  if not armed then
    armed = true
    cpu.debug:bpset(0x484254FA, "1",
      "printf \"HIT sp=%08X A=%08X B=%08X C=%08X D=%08X E=%08X F=%08X G=%08X\", sp, d@(sp+0x188), d@(sp+0x18c), d@(sp+0x190), d@(sp+0x194), d@(sp+0x198), d@(sp+0x19c), d@(sp+0x1a0) ; g")
    cpu.debug:bpset(0x48425467, "1", "printf \"ENTRY sp=%08X r=%08X\", sp, d@(sp) ; g")
    dbg.execution_state = "run"
  end
  local cl = dbg.consolelog
  for i = lastlog + 1, #cl do
    local line = tostring(cl[i])
    if line:find("^HIT") or line:find("^ENTRY") then
      n = n + 1
      if n <= 12 then out:write(string.format("t=%8.3f %s\n", t, line)) end
    end
  end
  lastlog = #cl
  if t >= 16 and not _G._k7s_done then
    _G._k7s_done = true
    out:write(string.format("total=%d\n", n)); out:flush(); mach:exit()
  end
end)
