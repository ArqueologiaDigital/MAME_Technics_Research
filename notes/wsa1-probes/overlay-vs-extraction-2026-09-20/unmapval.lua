-- What does a read of each *unmapped-or-noprw* window actually return?
-- Answers: does the extraction's missing noprw()/unmapped window hand the
-- firmware a different value than the overlay's?
local s1 = manager.machine.devices[":cpu1"].spaces["program"]
local s2 = manager.machine.devices[":cpu2"].spaces["program"]
local probes = {
  {"cpu1", s1, 0x7e0008}, {"cpu1", s1, 0x7e000a}, {"cpu1", s1, 0x7e0016},
  {"cpu1", s1, 0x008000}, {"cpu1", s1, 0x780000},
  {"cpu2", s2, 0xc00000}, {"cpu2", s2, 0xc00002},
  {"cpu2", s2, 0xe80000}, {"cpu2", s2, 0xe80002}, {"cpu2", s2, 0xe83232},
}
donenotif = emu.add_machine_frame_notifier(function()
  if probe_done then return end
  probe_done = true
  for _,p in ipairs(probes) do
    local ok, v8  = pcall(function() return p[2]:read_u8(p[3]) end)
    local ok2, v16 = pcall(function() return p[2]:read_u16(p[3]) end)
    print(string.format("PROBE %s %06X  u8=%s u16=%s",
      p[1], p[3], ok and string.format("%02X", v8) or "ERR",
      ok2 and string.format("%04X", v16) or "ERR"))
  end
end)
print("unmapval armed")
