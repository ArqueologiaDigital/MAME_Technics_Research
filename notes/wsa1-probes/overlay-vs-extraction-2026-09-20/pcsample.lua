-- Sample both CPUs' PC once per frame and print a histogram at stop.
-- Held in globals so the GC cannot collect the notifiers.
hist1 = {}
hist2 = {}
nframes = 0
local mac = manager.machine
local c1 = mac.devices[":cpu1"]
local c2 = mac.devices[":cpu2"]
frame_sub = emu.add_machine_frame_notifier(function()
  nframes = nframes + 1
  local p1 = c1.state["PC"].value
  local p2 = c2.state["PC"].value
  hist1[p1] = (hist1[p1] or 0) + 1
  hist2[p2] = (hist2[p2] or 0) + 1
  if nframes % 60 == 0 then
    print(string.format("PCSAMPLE t=%3ds cpu1=%08X cpu2=%08X", nframes//60, p1, p2))
  end
end)
local function dump(name, h)
  local a = {}
  for k,v in pairs(h) do a[#a+1] = {k,v} end
  table.sort(a, function(x,y) return x[2] > y[2] end)
  for i=1,math.min(#a,15) do
    print(string.format("HIST %s %08X  %d", name, a[i][1], a[i][2]))
  end
end
stop_sub = emu.add_machine_stop_notifier(function()
  print(string.format("PCSAMPLE frames=%d", nframes))
  dump("cpu1", hist1)
  dump("cpu2", hist2)
end)
print("PCSAMPLE armed")
