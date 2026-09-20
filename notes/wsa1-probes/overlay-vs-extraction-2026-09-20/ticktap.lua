-- WHO increments CPU 1's tick counter at RAM 0x0080, and how often?
-- The counter is the timebase every firmware delay loop counts (prom_b
-- 0xF5AA97, prom_a 0xF8E67D).  Tap held in a global so the GC cannot eat it.
local s1 = manager.machine.devices[":cpu1"].spaces["program"]
local cpu1 = manager.machine.devices[":cpu1"]
writers = {}
count = 0
tap = s1:install_write_tap(0x80, 0x81, "ticktap", function(offset, data, mask)
  count = count + 1
  local pc = cpu1.state["PC"].value
  writers[pc] = (writers[pc] or 0) + 1
  return data
end)
local n = 0
tnotif = emu.add_machine_frame_notifier(function()
  n = n + 1
  if n % 300 == 0 then print(string.format("TICKTAP f=%d writes=%d", n, count)) end
end)
stoptap = emu.add_machine_stop_notifier(function()
  local t = {}
  for k,v in pairs(writers) do t[#t+1]={k,v} end
  table.sort(t, function(a,b) return a[2]>b[2] end)
  print("=== writers of RAM 0x80 (total "..count..") ===")
  for i=1,math.min(#t,10) do print(string.format("  PC %06X  %d", t[i][1], t[i][2])) end
end)
print("ticktap armed")
