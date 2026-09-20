-- Sample both CPUs' PC every frame; print a histogram at the end.
-- Answers: where is each processor spinning after the panel is cleared?
local d1 = manager.machine.devices[":cpu1"]
local d2 = manager.machine.devices[":cpu2"]
h1 = {}
h2 = {}
n  = 0
local function pcof(d)
  local s = d.state["PC"]
  if s == nil then return -1 end
  return s.value
end
notif = emu.add_machine_frame_notifier(function()
  n = n + 1
  local a = pcof(d1); local b = pcof(d2)
  h1[a] = (h1[a] or 0) + 1
  h2[b] = (h2[b] or 0) + 1
  if n % 120 == 0 then
     print(string.format("SAMPLE n=%d cpu1=%06X cpu2=%06X", n, a, b))
  end
end)
stopnotif = emu.add_machine_stop_notifier(function()
  local function dump(tag, h)
    local t = {}
    for k,v in pairs(h) do t[#t+1] = {k,v} end
    table.sort(t, function(x,y) return x[2] > y[2] end)
    print("=== "..tag.." top PCs of "..n.." samples ===")
    for i=1,math.min(#t,25) do print(string.format("  %06X  %d", t[i][1], t[i][2])) end
  end
  dump("CPU1", h1)
  dump("CPU2", h2)
end)
print("pcprobe armed")
